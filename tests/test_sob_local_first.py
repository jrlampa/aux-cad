# -*- coding: utf-8 -*-
"""
Suíte de testes para a Frente 4: Preparação Local antes de SharePoint e GOMNET.

Cenários obrigatórios testados:
A. SharePoint disponível: local → SharePoint → GOMNET
B. SharePoint indisponível + usuário ignora: local → SharePoint falha → ignorar → GOMNET
C. SharePoint indisponível + usuário cancela: local → SharePoint falha → rollback
D. GOMNET disponível: local → SharePoint → GOMNET
E. GOMNET indisponível + usuário ignora: local → SharePoint → GOMNET falha → continuar
F. GOMNET indisponível + usuário cancela: local → SharePoint → GOMNET falha → rollback
G. Falha durante criação/cópia/renomeação: não consultar SharePoint nem GOMNET
H. Arquivos preexistentes: rollback não deve removê-los
I. Reexecução: não deve destruir estrutura válida existente
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from sob_manager import SobOrchestrator
from sob_sharepoint import (
    SharePointClient,
    SobAuthenticationError,
    SobSharepointUnavailableError,
)
from sob_gomnet import GomnetClient, GomnetAnexo


@pytest.fixture
def fake_prancha_dwg(tmp_path: Path) -> Path:
    f = tmp_path / "modelos" / "prancha.dwg"
    f.parent.mkdir(parents=True, exist_ok=True)
    # Header binário válido de DWG AutoCAD (AC1032 para 2018+)
    f.write_bytes(b"AC1032" + b"\x00" * 200)
    return f


def test_cenario_a_sharepoint_disponivel(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário A: SharePoint disponível: local → SharePoint → GOMNET."""
    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.localizar_pasta_sob.return_value = {"url": "https://sp/sob_1", "nome": "SOB_A057349839"}
    mock_sp.baixar_croqui.return_value = []

    mock_gom = MagicMock(spec=GomnetClient)
    mock_gom.localizar_sob_e_listar_anexos.return_value = []

    ordem_execucao = []

    def tracking_sp_localizar(*args, **kwargs):
        ordem_execucao.append("SHAREPOINT")
        return {"url": "https://sp/sob_1", "nome": "SOB_A057349839"}

    def tracking_gom_localizar(*args, **kwargs):
        ordem_execucao.append("GOMNET")
        return []

    mock_sp.localizar_pasta_sob.side_effect = tracking_sp_localizar
    mock_gom.localizar_sob_e_listar_anexos.side_effect = tracking_gom_localizar

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
        gomnet_client=mock_gom,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
        consultar_gomnet=True,
        abrir_cad=False,
    )

    assert resultado["sucesso"] is True
    assert resultado["estado"] == "CONCLUÍDO"
    assert ordem_execucao == ["SHAREPOINT", "GOMNET"]
    # Valida estrutura local criada
    sob_dir = tmp_path / "SOB_A057349839"
    assert sob_dir.is_dir()
    assert (sob_dir / "CROQUI").is_dir()
    assert (sob_dir / "PE_A057349839_DESENHO.dwg").is_file()


def test_cenario_b_sharepoint_indisponivel_usuario_ignora(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário B: SharePoint indisponível + usuário ignora: local → SharePoint falha → ignorar → GOMNET."""
    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.autenticar.side_effect = SobSharepointUnavailableError("Servidor SharePoint indisponível")

    mock_gom = MagicMock(spec=GomnetClient)
    mock_gom.localizar_sob_e_listar_anexos.return_value = []

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
        gomnet_client=mock_gom,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
        consultar_gomnet=True,
        abrir_cad=False,
        continuar_sem_sharepoint_em_falha=True,  # Usuário IGNORA e continua
    )

    assert resultado["sucesso"] is True
    assert resultado["SHAREPOINT_IGNORADO"] is True
    assert mock_gom.autenticar.called
    assert mock_gom.localizar_sob_e_listar_anexos.called
    # Estrutura local foi preservada
    sob_dir = tmp_path / "SOB_A057349839"
    assert (sob_dir / "PE_A057349839_DESENHO.dwg").is_file()


def test_cenario_c_sharepoint_indisponivel_usuario_cancela(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário C: SharePoint indisponível + usuário cancela: local → SharePoint falha → rollback."""
    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.autenticar.side_effect = SobSharepointUnavailableError("Servidor SharePoint fora do ar")

    mock_gom = MagicMock(spec=GomnetClient)

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
        gomnet_client=mock_gom,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
        consultar_gomnet=True,
        abrir_cad=False,
        continuar_sem_sharepoint_em_falha=False,  # Usuário CANCELA e solicita rollback
    )

    assert resultado["sucesso"] is False
    assert resultado["rollback"] == "ROLLBACK_CONCLUÍDO"
    # GOMNET não pode ter sido consultado se SharePoint falhou e usuário cancelou
    assert not mock_gom.autenticar.called
    # Rollback removeu os diretórios criados pela execução
    assert not (tmp_path / "SOB_A057349839").exists()


def test_cenario_d_gomnet_disponivel(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário D: GOMNET disponível: local → SharePoint → GOMNET."""
    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.localizar_pasta_sob.return_value = {"url": "https://sp", "nome": "SOB_A057349839"}
    mock_sp.baixar_croqui.return_value = []

    mock_gom = MagicMock(spec=GomnetClient)
    mock_gom.localizar_sob_e_listar_anexos.return_value = [
        GomnetAnexo(
            id_arquivo="1",
            nome_arquivo="anexo1.pdf",
            tipo="PDF",
            categoria="CROQUI",
            descricao="Croqui",
            data_gravacao="2026-09-30",
            usuario="admin",
            url_download="https://gomnet/1",
        )
    ]
    def mock_baixar(anexo, destino):
        p = Path(destino)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4 Fake")
        return p

    mock_gom.baixar_anexo_atomico.side_effect = mock_baixar

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
        gomnet_client=mock_gom,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
        consultar_gomnet=True,
        abrir_cad=False,
    )

    assert resultado["sucesso"] is True
    assert (tmp_path / "SOB_A057349839" / "CROQUI" / "ANEXOS" / "anexo1.pdf").is_file()


def test_cenario_e_gomnet_indisponivel_usuario_ignora(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário E: GOMNET indisponível + usuário ignora: local → SharePoint → GOMNET falha → continuar."""
    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.localizar_pasta_sob.return_value = {"url": "https://sp", "nome": "SOB_A057349839"}
    mock_sp.baixar_croqui.return_value = []

    mock_gom = MagicMock(spec=GomnetClient)
    mock_gom.autenticar.side_effect = Exception("Falha de conexão com GOMNET")

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
        gomnet_client=mock_gom,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
        consultar_gomnet=True,
        abrir_cad=False,
        continuar_sem_gomnet_em_falha=True,  # Usuário opta por ignorar falha do GOMNET
    )

    assert resultado["sucesso"] is True
    assert resultado["GOMNET_IGNORADO"] is True
    # Estrutura local foi preservada e validada
    assert (tmp_path / "SOB_A057349839" / "PE_A057349839_DESENHO.dwg").is_file()


def test_cenario_f_gomnet_indisponivel_usuario_cancela(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário F: GOMNET indisponível + usuário cancela: local → SharePoint → GOMNET falha → rollback."""
    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.localizar_pasta_sob.return_value = {"url": "https://sp", "nome": "SOB_A057349839"}
    mock_sp.baixar_croqui.return_value = []

    mock_gom = MagicMock(spec=GomnetClient)
    mock_gom.autenticar.side_effect = Exception("Erro crítico de rede no GOMNET")

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
        gomnet_client=mock_gom,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
        consultar_gomnet=True,
        abrir_cad=False,
        continuar_sem_gomnet_em_falha=False,  # Usuário cancela quando GOMNET falha
    )

    assert resultado["sucesso"] is False
    assert resultado["rollback"] == "ROLLBACK_CONCLUÍDO"
    # Rollback removeu os diretórios criados pela execução
    assert not (tmp_path / "SOB_A057349839").exists()


def test_cenario_g_falha_na_criacao_local_nao_chama_externos(tmp_path: Path, monkeypatch):
    """Cenário G: Falha durante criação/cópia/renomeação: não consultar SharePoint nem GOMNET."""
    # Modelo corrompido / inválido
    dwg_corrompido = tmp_path / "bad.dwg"
    dwg_corrompido.write_bytes(b"LIXO_NAO_DWG")

    mock_sp = MagicMock(spec=SharePointClient)
    mock_gom = MagicMock(spec=GomnetClient)

    orch = SobOrchestrator(
        origem_base=dwg_corrompido,
        sharepoint_client=mock_sp,
        gomnet_client=mock_gom,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path / "saida"),
        baixar_croqui_sp=True,
        consultar_gomnet=True,
        abrir_cad=False,
    )

    assert resultado["sucesso"] is False
    # Nenhum cliente externo pode ter sido acionado
    assert not mock_sp.autenticar.called
    assert not mock_gom.autenticar.called


def test_cenario_h_arquivos_preexistentes_preservados_no_rollback(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário H: Arquivos preexistentes fora do SOB: rollback não deve removê-los."""
    arquivo_preexistente = tmp_path / "arquivo_intocavel.txt"
    arquivo_preexistente.write_text("DADO PREEXISTENTE IMPORTANTE", encoding="utf-8")

    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.autenticar.side_effect = SobAuthenticationError("Falha proposital de auth")

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
    )

    resultado = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
        abrir_cad=False,
        continuar_sem_sharepoint_em_falha=False,
    )

    assert resultado["sucesso"] is False
    assert resultado["rollback"] == "ROLLBACK_CONCLUÍDO"
    # Arquivo preexistente permaneceu 100% intacto
    assert arquivo_preexistente.is_file()
    assert arquivo_preexistente.read_text(encoding="utf-8") == "DADO PREEXISTENTE IMPORTANTE"


def test_cenario_i_reexecucao_preserva_estrutura_valida(tmp_path: Path, fake_prancha_dwg: Path):
    """Cenário I: Reexecução não deve destruir estrutura válida existente."""
    mock_sp = MagicMock(spec=SharePointClient)
    mock_sp.localizar_pasta_sob.return_value = {"url": "https://sp", "nome": "SOB_A057349839"}
    mock_sp.baixar_croqui.return_value = []

    orch = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_sp,
    )

    # 1ª execução bem-sucedida
    res1 = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=False,
        consultar_gomnet=False,
        abrir_cad=False,
    )
    assert res1["sucesso"] is True
    sob_dwg = tmp_path / "SOB_A057349839" / "PE_A057349839_DESENHO.dwg"
    assert sob_dwg.is_file()

    # Adiciona um marcador no DWG existente
    sob_dwg.write_bytes(b"AC1032_MODIFICADO_PELO_PROJETISTA")

    # 2ª execução com a mesma SOB deve ser bloqueada por SobDirectoryExistsError ou idempotência
    res2 = orch.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=False,
        consultar_gomnet=False,
        abrir_cad=False,
    )

    assert res2["sucesso"] is False
    assert res2["status"] == "BLOQUEADO"
    # O arquivo DWG modificado pelo projetista NÃO foi sobrescrito ou destruído
    assert sob_dwg.read_bytes() == b"AC1032_MODIFICADO_PELO_PROJETISTA"
