# -*- coding: utf-8 -*-
"""
test_sob_sharepoint_telemetry.py - Testes de telemetria estruturada e não-intrusiva do SharePoint.

Cobre os 9 cenários mandatórios:
1. Busca prioritária encontrada (priority.start, priority.result="found", croqui.found).
2. Busca prioritária não encontrada + fallback (priority.not_found -> fallback.start -> fallback.result).
3. Identificação do croqui encontrado (sharepoint.croqui.found preservando retorno).
4. Download bem-sucedido (download.start, download.success com total_arquivos e duracao_ms).
5. Erro de download (download.start, download.error com duracao_ms e exceção preservada).
6. Erro na busca prioritária (priority.result="error", fallback executado).
7. Logger ausente (logger=None não quebra execução).
8. Proteção de dados sensíveis (sem vazamento de senha, token, cookie, credencial).
9. Não alteração do contrato de retorno das funções.
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from sob.sob_sharepoint import (
    SharePointClient,
    SobNotFoundError,
    SobDownloadError,
)


def _criar_client_mockado(logger=None) -> SharePointClient:
    """Instancia um SharePointClient com credenciais fictícias e mock de driver autenticado."""
    client = SharePointClient(
        login="usuario.teste@im3brasil.com.br",
        senha="SenhaUltraSecreta!123",
        headless=True,
        logger=logger,
    )
    client.driver = MagicMock()
    client._autenticado = True
    return client


def test_1_busca_prioritaria_encontrada():
    """Teste 1: Verifica priority.start e priority.result=found quando o croqui é achado na prioridade."""
    client = _criar_client_mockado()

    resultado_mock = {
        "texto": "SOB_A057389468 - CROQUI DE CAMPO\nModificado por João",
        "elemento": MagicMock(),
        "sob": "A057389468",
    }
    client.buscar_em_levantamentos_campo = MagicMock(return_value=resultado_mock)
    client.localizar_pasta_sob_existente = MagicMock()

    retorno = client.localizar_pasta_sob("A057389468")

    assert retorno == resultado_mock
    client.localizar_pasta_sob_existente.assert_not_called()

    eventos = client.eventos_telemetria
    nomes_eventos = [e["event"] for e in eventos]

    assert "sharepoint.search.priority.start" in nomes_eventos
    assert "sharepoint.search.priority.result" in nomes_eventos
    assert "sharepoint.croqui.found" in nomes_eventos

    # Valida resultado prioritário
    ev_prio = next(e for e in eventos if e["event"] == "sharepoint.search.priority.result")
    assert ev_prio["result"] == "found"
    assert ev_prio["origem"] == "Levantamentos de campo"
    assert "duracao_ms" in ev_prio

    # Valida croqui encontrado
    ev_croqui = next(e for e in eventos if e["event"] == "sharepoint.croqui.found")
    assert ev_croqui["sob_id"] == "A057389468"
    assert "SOB_A057389468" in ev_croqui["nome_arquivo"]


def test_2_busca_prioritaria_nao_encontrada_com_fallback():
    """Teste 2: Verifica prioridade not_found seguido de fallback.start e fallback.result."""
    client = _criar_client_mockado()

    client.buscar_em_levantamentos_campo = MagicMock(return_value=None)
    resultado_fb_mock = {
        "texto": "SOB_A057389468_PASTA_GERAL",
        "elemento": MagicMock(),
        "sob": "A057389468",
    }
    client.localizar_pasta_sob_existente = MagicMock(return_value=resultado_fb_mock)

    retorno = client.localizar_pasta_sob("A057389468")

    assert retorno == resultado_fb_mock

    eventos = client.eventos_telemetria
    nomes_eventos = [e["event"] for e in eventos]

    assert nomes_eventos == [
        "sharepoint.search.priority.start",
        "sharepoint.search.priority.result",
        "sharepoint.search.fallback.start",
        "sharepoint.search.fallback.result",
        "sharepoint.croqui.found",
    ]

    ev_prio_res = eventos[1]
    assert ev_prio_res["result"] == "not_found"

    ev_fb_res = eventos[3]
    assert ev_fb_res["result"] == "found"
    assert ev_fb_res["origem"] == "busca_existente"
    assert "duracao_ms" in ev_fb_res


def test_3_croqui_encontrado_preserva_retorno():
    """Teste 3: Verifica sharepoint.croqui.found sem alterar retorno funcional existente."""
    client = _criar_client_mockado()

    resultado_esperado = {
        "texto": "SOB_B999999999",
        "elemento": MagicMock(),
        "sob": "B999999999",
        "custom_key": 42,
    }
    client.buscar_em_levantamentos_campo = MagicMock(return_value=resultado_esperado)

    res = client.localizar_pasta_sob("B999999999")
    assert res is resultado_esperado
    assert res["custom_key"] == 42

    ev_croqui = next(e for e in client.eventos_telemetria if e["event"] == "sharepoint.croqui.found")
    assert ev_croqui["sob_id"] == "B999999999"
    assert ev_croqui["nome_arquivo"] == "SOB_B999999999"


def test_4_download_bem_sucedido(tmp_path: Path):
    """Teste 4: Verifica download.start e download.success com total_arquivos e duracao_ms."""
    client = _criar_client_mockado()

    arquivos_baixados = [tmp_path / "croqui1.pdf", tmp_path / "croqui2.dwg"]
    client._aguardar_e_processar_download = MagicMock(return_value=arquivos_baixados)

    pasta_info = {
        "sob": "A057389468",
        "elemento": MagicMock(),
    }

    retorno = client.baixar_croqui(pasta_info, tmp_path)

    assert retorno == arquivos_baixados

    eventos = client.eventos_telemetria
    nomes_eventos = [e["event"] for e in eventos]

    assert "sharepoint.download.start" in nomes_eventos
    assert "sharepoint.download.success" in nomes_eventos

    ev_success = next(e for e in eventos if e["event"] == "sharepoint.download.success")
    assert ev_success["sob_id"] == "A057389468"
    assert ev_success["total_arquivos"] == "2"
    assert "duracao_ms" in ev_success


def test_5_erro_de_download(tmp_path: Path):
    """Teste 5: Verifica download.start e download.error preservando a exceção original."""
    client = _criar_client_mockado()

    client._aguardar_e_processar_download = MagicMock(side_effect=SobDownloadError("Falha de conexão durante download"))

    pasta_info = {
        "sob": "A057389468",
        "elemento": MagicMock(),
    }

    with pytest.raises(SobDownloadError, match="Falha de conexão durante download"):
        client.baixar_croqui(pasta_info, tmp_path)

    eventos = client.eventos_telemetria
    nomes_eventos = [e["event"] for e in eventos]

    assert "sharepoint.download.start" in nomes_eventos
    assert "sharepoint.download.error" in nomes_eventos

    ev_err = next(e for e in eventos if e["event"] == "sharepoint.download.error")
    assert ev_err["sob_id"] == "A057389468"
    assert ev_err["erro"] == "SobDownloadError"
    assert "duracao_ms" in ev_err


def test_6_erro_na_busca_prioritaria_aciona_fallback():
    """Teste 6: Exceção não-fatal na busca prioritária registra priority.result=error e aciona fallback."""
    client = _criar_client_mockado()

    client.buscar_em_levantamentos_campo = MagicMock(side_effect=RuntimeError("Timeout no DOM do SharePoint"))
    resultado_fb = {"texto": "SOB_OK", "elemento": MagicMock(), "sob": "A123"}
    client.localizar_pasta_sob_existente = MagicMock(return_value=resultado_fb)

    res = client.localizar_pasta_sob("A123")
    assert res == resultado_fb

    eventos = client.eventos_telemetria
    ev_prio_res = next(e for e in eventos if e["event"] == "sharepoint.search.priority.result")
    assert ev_prio_res["result"] == "error"
    assert ev_prio_res["erro"] == "RuntimeError"

    assert any(e["event"] == "sharepoint.search.fallback.start" for e in eventos)
    assert any(e["event"] == "sharepoint.search.fallback.result" for e in eventos)


def test_7_logger_ausente_nao_quebra_execucao():
    """Teste 7: Instanciação e execução com logger=None funciona sem erro."""
    client = _criar_client_mockado(logger=None)
    assert client.logger is None

    resultado_mock = {"texto": "SOB_SEM_LOGGER", "sob": "A000"}
    client.buscar_em_levantamentos_campo = MagicMock(return_value=resultado_mock)

    # Executa sem exceção
    res = client.localizar_pasta_sob("A000")
    assert res == resultado_mock
    assert len(client.eventos_telemetria) >= 2


def test_8_dados_sensiveis_sao_estritamente_protegidos():
    """Teste 8: Garante que senhas, tokens, cookies e credenciais não vazam na telemetria."""
    client = _criar_client_mockado()
    senha_secreta = client.senha
    assert senha_secreta == "SenhaUltraSecreta!123"

    # Testa diretamente a emissão de telemetria com chaves perigosas e valores contendo a senha
    client._telemetria(
        "sharepoint.test.security",
        sob_id="A057389468",
        senha="SenhaUltraSecreta!123",
        token="Bearer_token_12345",
        cookie="FedAuth=xyz",
        credencial="ID:usuario,SENHA:123",
        mensagem=f"Erro de login com senha {senha_secreta}",
    )

    ev_sec = client.eventos_telemetria[-1]

    # Chaves proibidas devem ter sido descartadas
    assert "senha" not in ev_sec
    assert "token" not in ev_sec
    assert "cookie" not in ev_sec
    assert "credencial" not in ev_sec

    # Valor confidencial deve ter sido mascarado
    assert senha_secreta not in str(ev_sec)
    assert "******" in ev_sec.get("mensagem", "")


def test_9_nao_alteracao_do_contrato(tmp_path: Path):
    """Teste 9: Garante que os retornos das funções mantêm os tipos e estruturas originais."""
    client = _criar_client_mockado()

    pasta_retorno = {"texto": "SOB_CONTRATO", "sob": "A999", "elemento": MagicMock()}
    client.buscar_em_levantamentos_campo = MagicMock(return_value=pasta_retorno)

    res_loc = client.localizar_pasta_sob("A999")
    assert isinstance(res_loc, dict)
    assert res_loc["sob"] == "A999"

    client._aguardar_e_processar_download = MagicMock(return_value=[tmp_path / "doc.pdf"])
    res_dl = client.baixar_croqui(pasta_retorno, tmp_path)
    assert isinstance(res_dl, list)
    assert len(res_dl) == 1
    assert isinstance(res_dl[0], Path)
