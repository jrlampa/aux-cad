# -*- coding: utf-8 -*-
"""
Testes Unitários para a Integração com SharePoint (sob_sharepoint.py).
Cobre: Leitura de .env, sanitização de segurança, validação de downloads,
tratamento de falha de autenticação (Critério 07) e SOB inexistente (Critério 08).
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from sob_sharepoint import (
    obter_credenciais_sharepoint,
    sanitizar_mensagem,
    SharePointClient,
    SobEnvNotFoundError,
    SobCredentialError,
    SobAuthenticationError,
    SobNotFoundError,
    SobConflictError,
    SobDownloadIncompleteError,
)


def test_obter_credenciais_env_inexistente(tmp_path: Path):
    """Valida erro quando arquivo .env não existe."""
    env_inexistente = tmp_path / ".env_nao_existe"
    with pytest.raises(SobEnvNotFoundError):
        obter_credenciais_sharepoint(caminho_env=env_inexistente)


def test_obter_credenciais_chaves_ausentes(tmp_path: Path):
    """Valida erro quando variáveis do SharePoint não existem no .env."""
    env_vazio = tmp_path / ".env"
    env_vazio.write_text("OUTRA_VAR=123\n", encoding="utf-8")

    with pytest.raises(SobCredentialError) as exc_info:
        obter_credenciais_sharepoint(caminho_env=env_vazio)
    assert "SHAREPOINT_ID" in str(exc_info.value)


def test_obter_credenciais_senha_ausente(tmp_path: Path):
    """Valida erro quando apenas SHAREPOINT_ID está configurado."""
    env_sem_senha = tmp_path / ".env"
    env_sem_senha.write_text("SHAREPOINT_ID=usuario@hbt.com\n", encoding="utf-8")

    with pytest.raises(SobCredentialError) as exc_info:
        obter_credenciais_sharepoint(caminho_env=env_sem_senha)
    assert "SHAREPOINT_SENHA" in str(exc_info.value)


def test_obter_credenciais_sucesso(tmp_path: Path):
    """Valida carregamento correto de login e senha."""
    env_valido = tmp_path / ".env"
    env_valido.write_text(
        'SHAREPOINT_ID="teste.user@hbt.com.br"\n'
        'SHAREPOINT_SENHA="SenhaSuperSecreta123!"\n',
        encoding="utf-8",
    )

    login, senha = obter_credenciais_sharepoint(caminho_env=env_valido)
    assert login == "teste.user@hbt.com.br"
    assert senha == "SenhaSuperSecreta123!"


def test_seguranca_sanitizar_mensagem():
    """Garante que credenciais e senhas são estritamente mascaradas em logs e mensagens."""
    segredo = "SenhaUltraSecreta999"
    msg = f"Erro ao tentar conectar com senha={segredo} para usuario@teste.com"
    sanitizada = sanitizar_mensagem(msg, [segredo])

    assert segredo not in sanitizada
    assert "******" in sanitizada


def test_validar_download_sucesso(tmp_path: Path):
    """Valida download bem-sucedido com arquivos íntegros."""
    croqui = tmp_path / "CROQUI"
    croqui.mkdir()
    (croqui / "croqui_01.pdf").write_bytes(b"%PDF-1.4 123456789")
    (croqui / "foto_campo.jpg").write_bytes(b"\xFF\xD8\xFF 123456789")

    client = SharePointClient(login="user", senha="pwd", headless=True)
    assert client.validar_download(croqui) is True


def test_validar_download_vazio(tmp_path: Path):
    """Rejeita diretório vazio."""
    croqui = tmp_path / "CROQUI"
    croqui.mkdir()

    client = SharePointClient(login="user", senha="pwd", headless=True)
    assert client.validar_download(croqui) is False


def test_validar_download_incompleto_crdownload(tmp_path: Path):
    """Rejeita download com arquivo temporário .crdownload."""
    croqui = tmp_path / "CROQUI"
    croqui.mkdir()
    (croqui / "croqui.pdf.crdownload").write_bytes(b"dados parciais")

    client = SharePointClient(login="user", senha="pwd", headless=True)
    with pytest.raises(SobDownloadIncompleteError):
        client.validar_download(croqui)


def test_validar_download_arquivo_zero_bytes(tmp_path: Path):
    """Rejeita download com arquivo de zero bytes."""
    croqui = tmp_path / "CROQUI"
    croqui.mkdir()
    (croqui / "arquivo_vazio.txt").write_bytes(b"")

    client = SharePointClient(login="user", senha="pwd", headless=True)
    with pytest.raises(SobDownloadIncompleteError):
        client.validar_download(croqui)


def test_criterio_07_falha_autenticacao():
    """
    TESTE 07 — Falha de autenticação:
    Com credencial inválida:
    PROCESSO INTERROMPIDO
    FALHA NA AUTENTICAÇÃO DO SHAREPOINT
    Não prosseguir.
    """
    # 1. Testa verificação direta de mensagem de erro
    with pytest.raises(SobAuthenticationError) as exc_info1:
        SharePointClient._verificar_erro_login(
            "Sua conta ou senha está incorreta. Se você não se lembra de sua senha, redefina-a agora."
        )

    msg1 = str(exc_info1.value)
    assert "PROCESSO INTERROMPIDO" in msg1
    assert "FALHA NA AUTENTICAÇÃO DO SHAREPOINT" in msg1
    assert "Conta ou senha incorreta" in msg1

    # 2. Testa fluxo completo no cliente quando URL permanece no login Microsoft
    client = SharePointClient(login="usuario_invalido@hbt.com.br", senha="senha_errada")
    mock_driver = MagicMock()
    mock_driver.current_url = "https://login.microsoftonline.com/cc77ec9c-4b55-44f5-8ad6-47a90e9883b5/login"
    mock_body = MagicMock()
    mock_body.text = "Sua conta ou senha está incorreta."
    mock_driver.find_element.return_value = mock_body
    mock_driver.find_elements.return_value = []
    client.driver = mock_driver

    with patch("selenium.webdriver.support.ui.WebDriverWait.until", return_value=MagicMock()):
        with pytest.raises(SobAuthenticationError) as exc_info2:
            client.autenticar()

    msg2 = str(exc_info2.value)
    assert "PROCESSO INTERROMPIDO" in msg2
    assert "FALHA NA AUTENTICAÇÃO DO SHAREPOINT" in msg2


def test_criterio_08_sob_inexistente():
    """
    TESTE 08 — SOB inexistente:
    Com uma SOB inexistente:
    SOB NÃO ENCONTRADA NO SHAREPOINT
    Não criar um projeto incompleto.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/sites/HBT-EnelRJ-Sul/Documentos%20Compartilhados"
    # Não encontra nenhuma linha correspondente
    mock_driver.find_elements.return_value = []
    client.driver = mock_driver

    with pytest.raises(SobNotFoundError) as exc_info:
        client.localizar_pasta_sob("A999999999")

    msg = str(exc_info.value)
    assert "SOB NÃO ENCONTRADA NO SHAREPOINT" in msg


def test_sob_multiplos_resultados_conflito():
    """Valida detecção de ambiguidade quando múltiplos resultados diferentes são retornados."""
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/..."

    row1 = MagicMock()
    row1.text = "SOB_A057349839_OBRA_A"
    row2 = MagicMock()
    row2.text = "SOB_A057349839_OBRA_B_DUPLICADA"

    mock_driver.find_elements.return_value = [row1, row2]
    client.driver = mock_driver

    with pytest.raises(SobConflictError) as exc_info:
        client.localizar_pasta_sob("A057349839")

    assert "Múltiplos resultados conflitantes" in str(exc_info.value)


def test_fechar_driver():
    """Valida fechamento seguro do driver."""
    client = SharePointClient(login="user", senha="pwd")
    mock_driver = MagicMock()
    client.driver = mock_driver
    client._autenticado = True

    client.fechar()
    assert client.driver is None
    assert client._autenticado is False
    mock_driver.quit.assert_called_once()


def test_localizar_pasta_sob_sucesso():
    """Valida localização bem-sucedida de pasta da SOB."""
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/sites/..."

    row = MagicMock()
    row.text = "SOB_A057349839\nModificado há 2 dias"
    mock_driver.find_elements.return_value = [row]
    client.driver = mock_driver

    res = client.localizar_pasta_sob("A057349839")
    assert res["sob"] == "A057349839"
    assert "SOB_A057349839" in res["texto"]


def test_baixar_croqui(tmp_path: Path):
    """Valida chamada a baixar_croqui."""
    client = SharePointClient(login="user", senha="pwd")
    client.driver = MagicMock()
    dest = tmp_path / "croqui_down"

    mock_elem = MagicMock()
    mock_elem.find_elements.return_value = []
    pasta_info = {"elemento": mock_elem, "sob": "A057349839"}

    # Cria arquivo fake para simular download concluído
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "arquivo1.pdf").write_bytes(b"%PDF teste")

    arquivos = client.baixar_croqui(pasta_info, dest)
    assert len(arquivos) >= 1
    mock_elem.click.assert_called_once()


def test_autenticar_ja_em_sharepoint():
    """Valida autenticação imediata quando o navegador já está no SharePoint."""
    client = SharePointClient(login="user", senha="pwd")
    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/sites/HBT-EnelRJ-Sul/Documentos"
    client.driver = mock_driver

    client.autenticar()
    assert client._autenticado is True


def test_autenticar_usuario_nao_reconhecido():
    """Valida detecção de erro quando o e-mail não existe no Azure AD."""
    client = SharePointClient(login="nao_existe@hbt.com.br", senha="pwd")
    mock_driver = MagicMock()
    mock_driver.current_url = "https://login.microsoftonline.com/..."

    mock_err = MagicMock()
    mock_err.is_displayed.return_value = True
    mock_driver.find_elements.side_effect = lambda by, val: [mock_err] if val == "usernameError" else []
    client.driver = mock_driver

    with patch("selenium.webdriver.support.ui.WebDriverWait.until", return_value=MagicMock()):
        with pytest.raises(SobAuthenticationError) as exc_info:
            client.autenticar()

    assert "Usuário não reconhecido pela Microsoft" in str(exc_info.value)


def test_obter_credenciais_sem_dotenv(tmp_path: Path):
    """Valida leitura direta do .env sem a biblioteca python-dotenv."""
    import sob_sharepoint
    orig_dotenv = sob_sharepoint.load_dotenv
    sob_sharepoint.load_dotenv = None

    try:
        env_file = tmp_path / ".env_fallback"
        env_file.write_text(
            'SHAREPOINT_ID=direto@hbt.com.br\n'
            'SHAREPOINT_SENHA=senha123\n',
            encoding="utf-8",
        )
        login, senha = sob_sharepoint.obter_credenciais_sharepoint(caminho_env=env_file)
        assert login == "direto@hbt.com.br"
        assert senha == "senha123"
    finally:
        sob_sharepoint.load_dotenv = orig_dotenv


def test_criar_driver_mock_chrome(tmp_path: Path):
    """Valida fallback para Chrome quando Edge levanta exceção."""
    client = SharePointClient(login="user", senha="pwd")
    with patch("selenium.webdriver.Edge", side_effect=Exception("Edge ausente")):
        with patch("selenium.webdriver.Chrome", return_value=MagicMock()) as mock_chrome:
            client._criar_driver(pasta_download=tmp_path)
            assert client.driver is not None
            mock_chrome.assert_called_once()
