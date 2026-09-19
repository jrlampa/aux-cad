# -*- coding: utf-8 -*-
"""
test_sob_fallback_manual.py - Testes unitários e de integração para o fallback manual
e a regra de criação da estrutura do projeto independente do download do croqui.
"""

from pathlib import Path
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from sob_core import (
    SobCancellationRequestedError,
    SobConflictError,
)
from sob_fallback_manual import (
    gerar_url_busca_sharepoint,
    copiar_para_clipboard,
    abrir_busca_sharepoint_navegador,
    validar_arquivos_manuais,
    copiar_arquivos_manuais_para_croqui,
    executar_fallback_intervencao_manual,
)
from sob_progress_gui import ProgressoObserver
from sob_manager import SobOrchestrator


@pytest.fixture
def temp_workspace():
    """Cria workspace temporário com modelo DWG e diretório de destino."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_fallback_"))
    destino = temp_dir / "DESTINO"
    destino.mkdir()
    downloads = temp_dir / "DOWNLOADS"
    downloads.mkdir()

    modelo = temp_dir / "prancha.dwg"
    # Cabeçalho mínimo válido DWG
    with open(modelo, "wb") as f:
        f.write(b"AC1032" + b"\x00" * 200)

    yield {
        "root": temp_dir,
        "destino": destino,
        "downloads": downloads,
        "modelo": modelo,
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# 1. TESTES UNITÁRIOS DE URL E CLIPBOARD
# =============================================================================

class TestFallbackUrlEClipboard:
    def test_gerar_url_busca_sharepoint(self):
        url = gerar_url_busca_sharepoint("A057349839")
        assert "A057349839" in url
        assert "search.aspx/siteall?q=A057349839" in url

    def test_gerar_url_busca_com_prefixo_sob(self):
        url = gerar_url_busca_sharepoint("SOB_A057349839")
        assert "q=A057349839" in url

    def test_copiar_para_clipboard_mock(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_popen.return_value = mock_proc
            assert copiar_para_clipboard("A057349839") is True
            mock_popen.assert_called_once()

    def test_abrir_busca_sharepoint_navegador(self):
        with patch("webbrowser.open") as mock_wb, patch("sob_fallback_manual.copiar_para_clipboard") as mock_clip:
            url = abrir_busca_sharepoint_navegador("A057349839")
            mock_wb.assert_called_once()
            mock_clip.assert_called_once_with("A057349839")
            assert "A057349839" in url


# =============================================================================
# 2. VALIDAÇÃO RIGOROSA DE ARQUIVOS MANUAIS
# =============================================================================

class TestValidacaoArquivosManuais:
    def test_validar_diretorio_inexistente(self, temp_workspace):
        inexistente = temp_workspace["root"] / "pasta_fantasma"
        assert validar_arquivos_manuais(inexistente, "A057349839") == []

    def test_rejeitar_arquivo_vazio_e_temporario(self, temp_workspace):
        d = temp_workspace["downloads"]
        # Arquivo 0 bytes
        vazio = d / "SOB_A057349839.dwg"
        vazio.touch()

        # Arquivos temporários
        (d / "~$SOB_A057349839.docx").write_text("temp", encoding="utf-8")
        (d / "SOB_A057349839.dwg.download").write_text("temp", encoding="utf-8")

        encontrados = validar_arquivos_manuais(d, "A057349839")
        assert len(encontrados) == 0

    def test_rejeitar_pagina_erro_html(self, temp_workspace):
        d = temp_workspace["downloads"]
        falso_dwg = d / "SOB_A057349839.dwg"
        falso_dwg.write_bytes(b"<!DOCTYPE html><html><body>403 Forbidden</body></html>")

        encontrados = validar_arquivos_manuais(d, "A057349839")
        assert len(encontrados) == 0

    def test_aceitar_arquivos_validos(self, temp_workspace):
        d = temp_workspace["downloads"]
        valido_dwg = d / "SOB_A057349839_Croqui.dwg"
        valido_dwg.write_bytes(b"AC1032" + b"\x01" * 100)

        valido_pdf = d / "A057349839_Relatorio.pdf"
        valido_pdf.write_bytes(b"%PDF-1.4" + b"\x00" * 50)

        encontrados = validar_arquivos_manuais(d, "A057349839")
        assert len(encontrados) == 2
        nomes = [f.name for f in encontrados]
        assert "SOB_A057349839_Croqui.dwg" in nomes
        assert "A057349839_Relatorio.pdf" in nomes


# =============================================================================
# 3. CÓPIA DE ARQUIVOS MANUAIS PARA CROQUI
# =============================================================================

class TestCopiaArquivosManuaisParaCroqui:
    def test_copia_com_validacao_atomica(self, temp_workspace):
        origem = temp_workspace["downloads"] / "croqui_A057349839.pdf"
        origem.write_bytes(b"%PDF-1.4" + b"\x05" * 200)

        croqui_dir = temp_workspace["destino"] / "SOB_A057349839" / "CROQUI"

        criados = copiar_arquivos_manuais_para_croqui([origem], croqui_dir)
        assert len(criados) == 1
        assert criados[0].exists()
        assert criados[0].stat().st_size == origem.stat().st_size
        assert not (croqui_dir / f"{origem.name}.download").exists()


# =============================================================================
# 4. ORQUESTRAÇÃO DE INTERVENÇÃO MANUAL (executar_fallback_intervencao_manual)
# =============================================================================

class TestOrquestracaoFallbackIntervencao:
    def test_falha_em_modo_headless_sem_observer(self):
        with pytest.raises(SobConflictError) as exc:
            executar_fallback_intervencao_manual(
                sob_id="A057349839",
                ocorrencias=[{"nome": "Pasta 1"}, {"nome": "Pasta 2"}],
                url_busca="",
                callback_progresso=None,
                abrir_navegador=False,
            )
        assert "Múltiplas ocorrências" in str(exc.value)

    def test_cancelamento_pelo_usuario(self):
        observer = ProgressoObserver()

        def _responder_cancel():
            # Simula ação do usuário clicando em Cancelar
            observer.responder_intervencao({"cancelar": True})

        import threading
        t = threading.Timer(0.1, _responder_cancel)
        t.start()

        with pytest.raises(SobCancellationRequestedError):
            executar_fallback_intervencao_manual(
                sob_id="A057349839",
                ocorrencias=[{"nome": "Pasta 1"}, {"nome": "Pasta 2"}],
                url_busca="",
                callback_progresso=observer,
                abrir_navegador=False,
            )
        t.join()

    def test_continuar_sem_croqui(self):
        observer = ProgressoObserver()

        def _responder_sem_croqui():
            observer.responder_intervencao({"sem_croqui": True})

        import threading
        t = threading.Timer(0.1, _responder_sem_croqui)
        t.start()

        res = executar_fallback_intervencao_manual(
            sob_id="A057349839",
            ocorrencias=[{"nome": "Pasta 1"}, {"nome": "Pasta 2"}],
            url_busca="",
            callback_progresso=observer,
            abrir_navegador=False,
        )
        t.join()

        assert res["sucesso"] is True
        assert res["sem_croqui"] is True
        assert res["status_croqui"] == "SEM_ARQUIVOS"
        assert len(res["arquivos"]) == 0

    def test_continuar_com_arquivos_validos(self, temp_workspace):
        d = temp_workspace["downloads"]
        arq_croqui = d / "croqui_A057349839.pdf"
        arq_croqui.write_bytes(b"%PDF-1.4" + b"\x00" * 80)

        observer = ProgressoObserver()

        def _responder_caminho():
            observer.responder_intervencao({"caminho": str(d)})

        import threading
        t = threading.Timer(0.1, _responder_caminho)
        t.start()

        res = executar_fallback_intervencao_manual(
            sob_id="A057349839",
            ocorrencias=[{"nome": "Pasta 1"}, {"nome": "Pasta 2"}],
            url_busca="",
            callback_progresso=observer,
            abrir_navegador=False,
        )
        t.join()

        assert res["sucesso"] is True
        assert res["sem_croqui"] is False
        assert len(res["arquivos"]) == 1
        assert res["status_croqui"] == "DOWNLOAD_MANUAL_VALIDADO"


# =============================================================================
# 5. TESTES INTEGRADOS: ESTRUTURA DO PROJETO INDEPENDENTE DO CROQUI
# =============================================================================

class TestEstruturaProjetoIndependenteDoCroqui:
    def test_multiplas_ocorrencias_com_download_manual_cria_estrutura_e_dwg(self, temp_workspace):
        """
        Cenário:
        SharePoint retorna múltiplas ocorrências -> Intervenção manual bem-sucedida.
        Obrigatório:
        - Pré-validação NÃO cria SOB_ROOT antes da intervenção.
        - Fase B cria SOB_ROOT, CROQUI, copia arquivos manuais e BASE_SOB_DESENHO.dwg.
        """
        # Mock do cliente SharePoint levantando SobConflictError com 2 ocorrências
        mock_sp = MagicMock()
        mock_sp.autenticar.return_value = True
        mock_sp.localizar_pasta_sob.side_effect = SobConflictError(
            "Conflito de ocorrências",
            ocorrencias=[{"id": 1}, {"id": 2}],
            url_busca="https://sp/search?q=A057349839",
        )

        # Prepara arquivo manual na pasta de downloads
        d = temp_workspace["downloads"]
        arq_croqui = d / "A057349839_croqui.pdf"
        arq_croqui.write_bytes(b"%PDF-1.4" + b"\x01" * 100)

        observer = ProgressoObserver()

        def _responder():
            observer.responder_intervencao({"caminho": str(d)})

        import threading
        t = threading.Timer(0.2, _responder)
        t.start()

        orch = SobOrchestrator(
            origem_base=temp_workspace["modelo"],
            sharepoint_client=mock_sp,
        )

        with patch("sob_fallback_manual.abrir_busca_sharepoint_navegador"):
            res = orch.executar(
                sob_raw="A057349839",
                destino_dir=temp_workspace["destino"],
                baixar_croqui_sp=True,
                abrir_cad=False,
                callback_progresso=observer,
                verificador_cancelamento=observer,
            )
        t.join()

        assert res["sucesso"] is True
        assert res["status"] == "CONCLUÍDO"

        sob_root = Path(res["SOB_ROOT"])
        assert sob_root.is_dir()

        croqui_dir = Path(res["CROQUI_DIR"])
        assert croqui_dir.is_dir()
        # Arquivo manual foi copiado
        assert (croqui_dir / arq_croqui.name).exists()

        base_dwg = Path(res["BASE_DWG"])
        assert base_dwg.is_file()
        assert base_dwg.name == "BASE_SOB_DESENHO.dwg"
        assert base_dwg.stat().st_size > 0

    def test_multiplas_ocorrencias_com_sem_croqui_cria_estrutura_obrigatoria(self, temp_workspace):
        """
        Cenário fundamental:
        Usuário decide continuar sem arquivos de croqui (CROQUI = SEM_ARQUIVOS).
        Obrigatório:
        - Sistema registra explicitamente CROQUI = SEM_ARQUIVOS.
        - Obrigatoriamente cria SOB_ROOT.
        - Obrigatoriamente cria CROQUI (mesmo vazio).
        - Obrigatoriamente copia BASE_TEMPLATE para BASE_SOB_DESENHO.dwg.
        - Valida BASE_DWG e conclui com sucesso.
        """
        mock_sp = MagicMock()
        mock_sp.autenticar.return_value = True
        mock_sp.localizar_pasta_sob.side_effect = SobConflictError(
            "Múltiplas ocorrências",
            ocorrencias=[{"id": 10}, {"id": 20}],
            url_busca="https://sp/search?q=A057349839",
        )

        observer = ProgressoObserver()

        def _responder_sem_croqui():
            observer.responder_intervencao({"sem_croqui": True})

        import threading
        t = threading.Timer(0.2, _responder_sem_croqui)
        t.start()

        orch = SobOrchestrator(
            origem_base=temp_workspace["modelo"],
            sharepoint_client=mock_sp,
        )

        with patch("sob_fallback_manual.abrir_busca_sharepoint_navegador"):
            res = orch.executar(
                sob_raw="A057349839",
                destino_dir=temp_workspace["destino"],
                baixar_croqui_sp=True,
                abrir_cad=False,
                callback_progresso=observer,
                verificador_cancelamento=observer,
            )
        t.join()

        assert res["sucesso"] is True
        assert res["status"] == "CONCLUÍDO"
        assert res["CROQUI"] == "SEM_ARQUIVOS"

        # Estrutura obrigatória criada e validada
        sob_root = Path(res["SOB_ROOT"])
        assert sob_root.is_dir()
        croqui_dir = Path(res["CROQUI_DIR"])
        assert croqui_dir.is_dir()
        base_dwg = Path(res["BASE_DWG"])
        assert base_dwg.is_file()
        assert base_dwg.name == "BASE_SOB_DESENHO.dwg"
        assert base_dwg.stat().st_size == temp_workspace["modelo"].stat().st_size

    def test_cancelamento_durante_intervencao_nao_cria_arquivos(self, temp_workspace):
        """
        Cenário:
        Usuário cancela durante o diálogo de intervenção.
        Obrigatório:
        - Status = BLOQUEADO.
        - Nenhuma pasta (SOB_ROOT, CROQUI) e nenhum arquivo criado.
        """
        mock_sp = MagicMock()
        mock_sp.autenticar.return_value = True
        mock_sp.localizar_pasta_sob.side_effect = SobConflictError(
            "Múltiplas ocorrências",
            ocorrencias=[{"id": 10}, {"id": 20}],
            url_busca="https://sp/search?q=A057349839",
        )

        observer = ProgressoObserver()

        def _responder_cancel():
            observer.responder_intervencao({"cancelar": True})

        import threading
        t = threading.Timer(0.2, _responder_cancel)
        t.start()

        orch = SobOrchestrator(
            origem_base=temp_workspace["modelo"],
            sharepoint_client=mock_sp,
        )

        with patch("sob_fallback_manual.abrir_busca_sharepoint_navegador"):
            res = orch.executar(
                sob_raw="A057349839",
                destino_dir=temp_workspace["destino"],
                baixar_croqui_sp=True,
                abrir_cad=False,
                callback_progresso=observer,
                verificador_cancelamento=observer,
            )
        t.join()

        assert res["sucesso"] is False
        assert res["status"] == "BLOQUEADO"

        # Nada foi criado no destino!
        pastas_criadas = list(temp_workspace["destino"].iterdir())
        assert len(pastas_criadas) == 0
