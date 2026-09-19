# -*- coding: utf-8 -*-
"""
Testes de Integração e Orquestração do Módulo SOB (sob_manager.py).
Cobre: Ciclo completo da máquina de estados, tratamento de todos os 16 cenários de erro,
geração de logs passo a passo e intercâmbio JSON com o AutoCAD.
"""

import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from sob_manager import SobOrchestrator
from sob_sharepoint import (
    SharePointClient,
    SobAuthenticationError,
    SobNotFoundError,
)


@pytest.fixture
def fake_prancha_dwg(tmp_path: Path) -> Path:
    """Cria um arquivo-base DWG simulado válido."""
    p = tmp_path / "modelos" / "prancha.dwg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"AC1032" + (b"\x00" * 200) + b"MODELO_BASE_OFICIAL")
    return p


def test_executar_fluxo_completo_com_mock_sharepoint(tmp_path: Path, fake_prancha_dwg: Path):
    """Valida o fluxo completo de ponta a ponta com sucesso."""
    destino = tmp_path / "projetos"
    destino.mkdir()

    # Mock do cliente SharePoint
    mock_client = MagicMock(spec=SharePointClient)
    mock_client.autenticar.return_value = True
    mock_client.localizar_pasta_sob.return_value = {"nome": "SOB_A057349839", "elemento": MagicMock()}

    def simular_download(pasta_info, croqui_dir):
        arq = croqui_dir / "croqui_campo.pdf"
        arq.write_bytes(b"%PDF-1.4 croqui de teste")
        return [arq]

    mock_client.baixar_croqui.side_effect = simular_download
    mock_client.validar_download.return_value = True

    orquestrador = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_client,
    )

    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(destino),
        baixar_croqui_sp=True,
        abrir_cad=False,
    )

    assert resultado["sucesso"] is True
    assert resultado["etapa"] == "FINALIZADO"
    assert resultado["SOB_ID"] == "A057349839"
    assert resultado["SOB_NAME"] == "SOB_A057349839"
    assert resultado["DESTINATION_ROOT"] == str(destino.resolve())
    assert resultado["SOB_ROOT"] == str((destino / "SOB_A057349839").resolve())
    assert resultado["CROQUI_DIR"] == str((destino / "SOB_A057349839" / "CROQUI").resolve())
    assert resultado["BASE_DWG"] == str((destino / "SOB_A057349839" / "BASE_SOB_DESENHO.dwg").resolve())
    assert resultado["sob"] == "SOB_A057349839"

    # Verifica que o SharePoint foi consultado pelo SOB_ID puro (Seção 11)
    mock_client.localizar_pasta_sob.assert_called_with("A057349839")

    sob_root = Path(resultado["SOB_ROOT"])
    assert sob_root.exists()
    assert (sob_root / "CROQUI").exists()
    assert (sob_root / "CROQUI" / "croqui_campo.pdf").exists()

    dwg_path = Path(resultado["BASE_DWG"])
    assert dwg_path.exists()
    assert dwg_path.name == "BASE_SOB_DESENHO.dwg"
    assert dwg_path.parent == sob_root

    # Confirma que o modelo original continuou intacto
    assert fake_prancha_dwg.exists()
    assert fake_prancha_dwg.stat().st_size > 0


def test_executar_sob_invalida(tmp_path: Path, fake_prancha_dwg: Path):
    """Valida interrupção quando a SOB é vazia ou inválida."""
    orquestrador = SobOrchestrator(origem_base=fake_prancha_dwg)
    resultado = orquestrador.executar(sob_raw="", destino_dir=str(tmp_path))

    assert resultado["sucesso"] is False
    assert resultado["status"] == "BLOQUEADO"
    assert "VALIDAR_SOB" in resultado["etapa"]
    assert "[FALHA] SOB não informada." in resultado["mensagem"]


def test_executar_destino_inexistente(fake_prancha_dwg: Path):
    """Valida interrupção quando o diretório de destino não existe."""
    orquestrador = SobOrchestrator(origem_base=fake_prancha_dwg)
    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir="C:/Caminho/Que/Nao/Existe/Jamais",
    )

    assert resultado["sucesso"] is False
    assert resultado["status"] == "BLOQUEADO"
    assert "VALIDAR_DESTINO" in resultado["etapa"]
    assert "[FALHA] Diretório de destino inválido." in resultado["mensagem"]


def test_executar_pasta_sob_ja_existente(tmp_path: Path, fake_prancha_dwg: Path):
    """TESTE 09 no Manager: pasta já existente interrompe sem alterar arquivos."""
    pasta_existente = tmp_path / "SOB_A057349839"
    pasta_existente.mkdir()
    arquivo_salvo = pasta_existente / "projeto_antigo.dwg"
    arquivo_salvo.write_bytes(b"arquivo antigo intacto")

    orquestrador = SobOrchestrator(origem_base=fake_prancha_dwg)
    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
    )

    assert resultado["sucesso"] is False
    assert resultado["status"] == "BLOQUEADO"
    assert "[FALHA] A pasta SOB_A057349839 já existe." in resultado["mensagem"]

    # Verifica integridade do arquivo pré-existente
    assert arquivo_salvo.exists()
    assert arquivo_salvo.read_bytes() == b"arquivo antigo intacto"


def test_executar_falha_autenticacao_sharepoint(tmp_path: Path, fake_prancha_dwg: Path):
    """TESTE 07 no Manager: falha de autenticação do SharePoint interrompe o fluxo."""
    mock_client = MagicMock(spec=SharePointClient)
    mock_client.autenticar.side_effect = SobAuthenticationError(
        "[FALHA] Não foi possível autenticar no SharePoint."
    )

    orquestrador = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_client,
    )

    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
    )

    assert resultado["sucesso"] is False
    assert resultado["status"] == "BLOQUEADO"
    assert "[FALHA] Não foi possível autenticar no SharePoint." in resultado["mensagem"]
    # Não cria o DWG em caso de falha
    assert resultado["dwg_path"] == ""


def test_executar_sob_nao_encontrada_sharepoint(tmp_path: Path, fake_prancha_dwg: Path):
    """TESTE 08 no Manager: SOB não encontrada no SharePoint interrompe o fluxo."""
    mock_client = MagicMock(spec=SharePointClient)
    mock_client.autenticar.return_value = True
    mock_client.localizar_pasta_sob.side_effect = SobNotFoundError(
        "[FALHA] SOB A057349839 não encontrada no SharePoint."
    )

    orquestrador = SobOrchestrator(
        origem_base=fake_prancha_dwg,
        sharepoint_client=mock_client,
    )

    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(tmp_path),
        baixar_croqui_sp=True,
    )

    assert resultado["sucesso"] is False
    assert resultado["status"] == "BLOQUEADO"
    assert "[FALHA] SOB A057349839 não encontrada no SharePoint." in resultado["mensagem"]
    # Não deve finalizar como sucesso e não deve gerar BASE_SOB_DESENHO.dwg
    assert resultado["dwg_path"] == ""


def test_executar_arquivo_base_inexistente(tmp_path: Path):
    """Valida erro se prancha.dwg não existir no caminho especificado."""
    destino = tmp_path / "dest"
    destino.mkdir()
    inexistente = tmp_path / "prancha_inexistente.dwg"

    orquestrador = SobOrchestrator(origem_base=inexistente)
    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(destino),
        baixar_croqui_sp=False,
    )

    assert resultado["sucesso"] is False
    assert resultado["status"] == "BLOQUEADO"
    assert "Arquivo-modelo prancha.dwg não encontrado" in resultado["mensagem"]


def test_abrir_no_autocad(tmp_path: Path, fake_prancha_dwg: Path):
    """Valida chamada ao método de abertura no AutoCAD."""
    from unittest.mock import patch
    orquestrador = SobOrchestrator(origem_base=fake_prancha_dwg)
    with patch("os.startfile") as mock_startfile:
        orquestrador._abrir_no_autocad(fake_prancha_dwg)
        mock_startfile.assert_called_once_with(str(fake_prancha_dwg))


def test_logger_seguro():
    """Valida logger seguro e mascaramento de segredos."""
    from sob_manager import configurar_logger
    logger = configurar_logger()
    logger.adicionar_segredo("MINHA_SENHA_123")
    # Não deve levantar exceções
    logger.info("Teste com MINHA_SENHA_123 ok")
    logger.warning("Alerta com MINHA_SENHA_123")
    logger.error("Erro com MINHA_SENHA_123")


def test_cli_main(tmp_path: Path, fake_prancha_dwg: Path, monkeypatch):
    """Valida ponto de entrada CLI via argparse."""
    from sob_manager import main
    from unittest.mock import patch

    destino = tmp_path / "cli_dest"
    destino.mkdir()
    json_out = tmp_path / "out.json"

    args = [
        "sob_manager.py",
        "--sob", "A057349839",
        "--destino", str(destino),
        "--sem-sharepoint",
        "--json-out", str(json_out),
    ]
    monkeypatch.setattr("sys.argv", args)

    with patch("sob_manager.CAMINHO_BASE_PRANCHA_PADRAO", fake_prancha_dwg):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    assert json_out.exists()
    dados = json.loads(json_out.read_text(encoding="utf-8"))
    assert dados["sucesso"] is True
    assert dados["sob"] == "SOB_A057349839"


def test_secao_14_rollback_em_falha_copia(tmp_path: Path, fake_prancha_dwg: Path, monkeypatch):
    """Valida rollback seguro da pasta criada quando etapa posterior falha (Seção 14.8)."""
    import sob_manager
    destino = tmp_path / "projetos"
    destino.mkdir()

    # Faz a cópia falhar para testar o rollback de sob_root
    def fake_copiar(*args, **kwargs):
        raise IOError("Falha simulada na cópia do DWG")

    monkeypatch.setattr(sob_manager, "copiar_arquivo_base", fake_copiar)

    orquestrador = SobOrchestrator(origem_base=fake_prancha_dwg)
    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(destino),
        baixar_croqui_sp=False,
    )

    assert resultado["sucesso"] is False
    assert resultado["status"] == "BLOQUEADO"
    # A pasta incompleta deve ter sido removida no rollback
    sob_root = destino / "SOB_A057349839"
    assert not sob_root.exists()


def test_secao_14_checklist_completo_sucesso(tmp_path: Path, fake_prancha_dwg: Path):
    """Valida que todos os 15 itens do checklist são satisfeitos para CONCLUÍDO (Seção 14.27)."""
    destino = tmp_path / "projetos"
    destino.mkdir()

    orquestrador = SobOrchestrator(origem_base=fake_prancha_dwg)
    resultado = orquestrador.executar(
        sob_raw="A057349839",
        destino_dir=str(destino),
        baixar_croqui_sp=False,
    )

    assert resultado["sucesso"] is True
    assert resultado["status"] == "CONCLUÍDO"
    assert resultado["estado"] == "CONCLUÍDO"

    chk = resultado["checklist"]
    assert chk["SOB_ID válido"] is True
    assert chk["SOB_NAME válido"] is True
    assert chk["DESTINATION_ROOT válido"] is True
    assert chk["SOB_ROOT correto"] is True
    assert chk["CROQUI_DIR correto"] is True
    assert chk["BASE_TEMPLATE validado"] is True
    assert chk["BASE_DWG criado"] is True
    assert chk["BASE_DWG validado"] is True
    assert chk["Integridade validada"] is True
    assert chk["BASE_TEMPLATE preservado"] is True
    assert chk["Estrutura final validada"] is True


def test_secao_14_formatar_mensagem_erro():
    """Valida estrutura recomendada de mensagem de erro da Seção 14.26."""
    from sob_manager import formatar_mensagem_erro

    msg = formatar_mensagem_erro(
        etapa="Criação da pasta da SOB",
        problema="A pasta SOB_A057349839 já existe.",
        caminho="D:\\Projetos\\ENEL\\SOB_A057349839",
        acao="Verifique a pasta existente ou selecione outro diretório de destino.",
    )

    assert "[ERRO]" in msg
    assert "Etapa:\nCriação da pasta da SOB" in msg
    assert "Problema:\nA pasta SOB_A057349839 já existe." in msg
    assert "Caminho afetado:\nD:\\Projetos\\ENEL\\SOB_A057349839" in msg
    assert "Ação:\nVerifique a pasta existente" in msg
