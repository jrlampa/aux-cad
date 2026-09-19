# -*- coding: utf-8 -*-
"""
test_sob_progress_gui.py - Suíte de Testes da Interface de Progresso e Feedback Visual (Seção 19 / GUI).
Testa ProgressoObserver, SobProgressGUI, transições de estados, cancelamento seguro
e integração do SobOrchestrator com o sistema de callbacks.
"""

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from sob.sob_core import (
    SobCancellationRequestedError,
    SobValidationError,
)
from sob.sob_manager import SobOrchestrator, main
from sob.sob_progress_gui import ProgressoObserver, SobProgressGUI


@pytest.fixture
def temp_workspace():
    """Cria workspace temporário isolado."""
    temp_dir = tempfile.mkdtemp(prefix="test_sob_gui_")
    origem_base = Path(temp_dir) / "prancha.dwg"
    with open(origem_base, "wb") as f:
        f.write(b"AC1032" + b"\x00" * 200)

    destino_dir = Path(temp_dir) / "DESTINO"
    destino_dir.mkdir(parents=True, exist_ok=True)

    yield {
        "root": Path(temp_dir),
        "origem_base": origem_base,
        "destino_dir": destino_dir,
    }
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestProgressoObserver:
    """Testes unitários para a classe ProgressoObserver."""

    def test_observer_envio_e_recebimento_de_eventos(self):
        obs = ProgressoObserver()
        assert not obs.cancelamento_solicitado()

        obs.notificar(
            etapa="VALIDAR_SOB",
            descricao="Validando formato e identificador da SOB...",
            etapa_num=2,
            total_etapas=12,
            percentual=16.6,
            estado="EM_EXECUCAO",
        )

        ev = obs.obter_evento()
        assert ev is not None
        assert ev["tipo"] == "PROGRESSO"
        assert ev["etapa"] == "VALIDAR_SOB"
        assert ev["etapa_num"] == 2
        assert ev["percentual"] == 16.6
        assert ev["estado"] == "EM_EXECUCAO"

    def test_observer_solicitar_cancelamento(self):
        obs = ProgressoObserver()
        assert not obs.cancelamento_solicitado()

        obs.solicitar_cancelamento()
        assert obs.cancelamento_solicitado()

        ev = obs.obter_evento()
        assert ev is not None
        assert ev["tipo"] == "PROGRESSO"
        assert ev["etapa"] == "CANCELAMENTO"
        assert ev["estado"] == "CANCELAMENTO"

    def test_observer_finalizar(self):
        obs = ProgressoObserver()
        res_mock = {"sucesso": True, "status": "CONCLUÍDO"}
        obs.finalizar(res_mock)

        ev = obs.obter_evento()
        assert ev is not None
        assert ev["tipo"] == "FINALIZADO"
        assert ev["resultado"]["sucesso"] is True


@pytest.fixture
def tk_root():
    """Fornece instância Tk compartilhada para testes visuais rápidos."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestSobProgressGUIWidgets:
    """Testes de montagem e transição de estados da interface Tkinter."""

    def test_gui_inicializacao_e_elementos(self, tk_root):
        tarefa_mock = MagicMock(return_value={"sucesso": True, "status": "CONCLUÍDO"})
        gui = SobProgressGUI(sob_id="A057349839", tarefa_executora=tarefa_mock, root=tk_root)

        assert gui.sob_id == "A057349839"
        assert "A057349839" in gui.root.children.get("!frame").children.get("!label2").cget("text")
        assert gui.btn_cancelar.cget("text") == "Cancelar"

        gui._fechar_janela()

    def test_gui_atualizacao_progresso_determinado_e_indeterminado(self, tk_root):
        gui = SobProgressGUI(sob_id="A057349839", tarefa_executora=MagicMock(), root=tk_root)

        # Atualização indeterminada
        ev_indet = {
            "etapa": "SHAREPOINT_AUTENTICACAO",
            "descricao": "Autenticando no SharePoint corporativo...",
            "etapa_num": 5,
            "total_etapas": 12,
            "percentual": None,
            "estado": "EM_EXECUCAO",
        }
        gui._atualizar_progresso(ev_indet)
        assert "Etapa 5 de 12" in gui.lbl_etapa_badge.cget("text")
        assert "Autenticando no SharePoint corporativo..." in gui.lbl_descricao.cget("text")
        assert str(gui.progresso_bar["mode"]) == "indeterminate"

        # Atualização determinada
        ev_det = {
            "etapa": "DOWNLOAD_GOMNET",
            "descricao": "Baixando anexos identificados no GOMNET...",
            "etapa_num": 10,
            "total_etapas": 12,
            "percentual": 75.0,
            "estado": "EM_EXECUCAO",
        }
        gui._atualizar_progresso(ev_det)
        assert str(gui.progresso_bar["mode"]) == "determinate"
        assert gui.progresso_bar["value"] == 75.0

        gui._fechar_janela()

    def test_gui_finalizacao_sucesso(self, tk_root):
        gui = SobProgressGUI(sob_id="A057349839", tarefa_executora=MagicMock(), root=tk_root)
        res_sucesso = {
            "sucesso": True,
            "status": "CONCLUÍDO",
            "SOB_ROOT": "C:\\fake\\SOB_A057349839",
            "rollback": "ROLLBACK_NÃO_NECESSÁRIO",
        }
        gui._tratar_finalizacao(res_sucesso)

        assert gui.lbl_etapa_badge.cget("text") == "Concluído"
        assert "sucesso" in gui.lbl_descricao.cget("text").lower()
        assert gui.btn_fechar.winfo_manager() == "pack"

        gui._fechar_janela()

    def test_gui_finalizacao_bloqueado_e_erro(self, tk_root):
        gui = SobProgressGUI(sob_id="A057349839", tarefa_executora=MagicMock(), root=tk_root)
        res_bloq = {
            "sucesso": False,
            "status": "BLOQUEADO",
            "etapa": "DOWNLOAD_CROQUI",
            "mensagem": "Falha no download dos arquivos",
            "rollback": "ROLLBACK_CONCLUÍDO",
        }
        gui._tratar_finalizacao(res_bloq)

        assert gui.lbl_etapa_badge.cget("text") == "Operação Bloqueada"
        assert "DOWNLOAD_CROQUI" in gui.lbl_descricao.cget("text")
        assert "ROLLBACK_CONCLUÍDO" in gui.lbl_mensagem_final.cget("text")
        assert gui.btn_fechar.winfo_manager() == "pack"

        gui._fechar_janela()

    def test_gui_solicitar_cancelamento(self, tk_root):
        gui = SobProgressGUI(sob_id="A057349839", tarefa_executora=MagicMock(), root=tk_root)
        gui._solicitar_cancelamento()

        assert gui.observer.cancelamento_solicitado()
        assert gui.btn_cancelar.cget("state") == "disabled"
        assert "Cancelando..." in gui.btn_cancelar.cget("text")

        gui._fechar_janela()


class TestOrchestratorProgressCallbacks:
    """Testes de emissão de eventos de progresso pelo SobOrchestrator."""

    def test_notificacoes_emitidas_ao_longo_do_fluxo(self, temp_workspace):
        eventos = []

        def callback_teste(ev):
            eventos.append(ev)

        orch = SobOrchestrator(origem_base=temp_workspace["origem_base"])
        res = orch.executar(
            sob_raw="A057349839",
            destino_dir=str(temp_workspace["destino_dir"]),
            baixar_croqui_sp=False,
            consultar_gomnet=False,
            callback_progresso=callback_teste,
        )

        assert res["sucesso"] is True
        assert len(eventos) >= 5

        # Verifica etapas cruciais presentes nos eventos recebidos
        etapas_notificadas = [ev.get("etapa") for ev in eventos if isinstance(ev, dict)]
        assert "INICIANDO" in etapas_notificadas
        assert "VALIDAR_SOB" in etapas_notificadas
        assert "VALIDAR_DESTINO" in etapas_notificadas
        assert "VALIDAR_BASE_TEMPLATE" in etapas_notificadas
        assert "CONCLUIDO" in etapas_notificadas

    def test_cancelamento_na_fase_a(self, temp_workspace):
        obs = ProgressoObserver()
        obs.solicitar_cancelamento()

        orch = SobOrchestrator(origem_base=temp_workspace["origem_base"])
        res = orch.executar(
            sob_raw="A057349839",
            destino_dir=str(temp_workspace["destino_dir"]),
            baixar_croqui_sp=False,
            consultar_gomnet=False,
            callback_progresso=obs,
            verificador_cancelamento=obs,
        )

        assert res["sucesso"] is False
        assert res["status"] == "BLOQUEADO"
        assert "cancelada" in res["mensagem"].lower()
        assert res["rollback"] == "ROLLBACK_NÃO_NECESSÁRIO"

    def test_cancelamento_na_fase_b_com_rollback(self, temp_workspace):
        obs = ProgressoObserver()

        # Configura cancelamento para ocorrer logo após a criação da estrutura
        def interceptor_progresso(ev):
            if ev.get("etapa") == "CRIAR_BASE_DWG":
                obs.solicitar_cancelamento()

        orch = SobOrchestrator(origem_base=temp_workspace["origem_base"])

        # Chamamos com o interceptor
        res = orch.executar(
            sob_raw="A057349839",
            destino_dir=str(temp_workspace["destino_dir"]),
            baixar_croqui_sp=False,
            consultar_gomnet=False,
            callback_progresso=interceptor_progresso,
            verificador_cancelamento=obs,
        )

        assert res["sucesso"] is False
        assert res["status"] == "BLOQUEADO"
        assert "cancelada" in res["mensagem"].lower()
        # O rollback foi acionado pois arquivos/pastas foram criados na Fase B
        assert res["rollback"] in ("ROLLBACK_CONCLUÍDO", "ROLLBACK_PARCIAL")


class TestMainHeadlessFlag:
    """Testa execução de main com flag --no-ui."""

    @patch("sob.sob_manager.SobOrchestrator.executar")
    def test_main_com_flag_no_ui(self, mock_exec, temp_workspace):
        mock_exec.return_value = {"sucesso": True, "status": "CONCLUÍDO"}

        with patch("sys.argv", [
            "sob_manager.py",
            "--sob", "A057349839",
            "--destino", str(temp_workspace["destino_dir"]),
            "--sem-sharepoint",
            "--no-ui",
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_exec.assert_called_once()


class TestSobProgressGUIIntervencao:
    """Testa os métodos e componentes visuais de intervenção manual da SobProgressGUI."""

    def test_acoes_botoes_intervencao(self, temp_workspace):
        gui = SobProgressGUI(
            sob_id="A057349839",
            tarefa_executora=lambda obs: {"sucesso": True},
        )
        try:
            # 1. Abrir SharePoint
            with patch("sob_fallback_manual.abrir_busca_sharepoint_navegador") as mock_abrir:
                gui._abrir_sharepoint()
                mock_abrir.assert_called_once_with("A057349839", gui._url_busca)

            # 2. Selecionar pasta
            with patch("tkinter.filedialog.askdirectory", return_value=str(temp_workspace["destino_dir"])):
                gui._selecionar_pasta_dialog()
                assert gui._pasta_selecionada == temp_workspace["destino_dir"]

            # 3. Confirmar intervenção
            gui._confirmar_intervencao()
            ev = gui.observer.obter_evento()
            # O observer recebeu a resposta via responder_intervencao
            assert gui.observer._resposta_intervencao == {"caminho": str(temp_workspace["destino_dir"])}

            # 4. Confirmar sem croqui
            gui._confirmar_sem_croqui()
            assert gui.observer._resposta_intervencao == {"sem_croqui": True}

            # 5. Cancelar intervenção
            gui._cancelar_intervencao()
            assert gui.observer._resposta_intervencao == {"cancelar": True}

            # 6. Evento de INTERVENCAO_USUARIO na UI
            gui._atualizar_progresso({
                "tipo": "PROGRESSO",
                "etapa": "INTERVENCAO_USUARIO",
                "descricao": "Ação necessária no SharePoint",
                "estado": "INTERVENCAO_USUARIO",
                "detalhes": {"url_busca": "https://teste.sp", "pasta_sugerida": str(temp_workspace["root"])},
            })
            assert gui.lbl_etapa_badge["text"] == "Ação Necessária"
            assert gui._url_busca == "https://teste.sp"

            # 7. Evento de FALHA_VALIDACAO_MANUAL
            gui._atualizar_progresso({
                "tipo": "PROGRESSO",
                "etapa": "FALHA_VALIDACAO_MANUAL",
                "descricao": "Nenhum arquivo válido encontrado",
                "estado": "FALHA_VALIDACAO_MANUAL",
                "detalhes": {"pasta": str(temp_workspace["root"])},
            })
            assert "Não foi possível validar o download" in gui.lbl_etapa_badge["text"]
        finally:
            gui.root.destroy()


class TestSobCliModule:
    """Testa o módulo sob_cli diretamente."""

    @patch("sob.sob_manager.SobOrchestrator.executar")
    def test_cli_execucao_com_json_out(self, mock_exec, temp_workspace):
        from sob_cli import main as cli_main

        mock_exec.return_value = {"sucesso": True, "status": "CONCLUÍDO"}
        json_file = temp_workspace["root"] / "resultado.json"

        with pytest.raises(SystemExit) as exc:
            cli_main([
                "--sob", "A057349839",
                "--destino", str(temp_workspace["destino_dir"]),
                "--sem-sharepoint",
                "--no-ui",
                "--json-out", str(json_file),
            ])
        assert exc.value.code == 0
        assert json_file.exists()
