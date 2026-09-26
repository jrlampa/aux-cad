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
    obter_url_sharepoint,
    sanitizar_mensagem,
    SharePointClient,
    SHAREPOINT_URL_PADRAO,
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
    assert "[FALHA] Credenciais do SharePoint não configuradas." in str(exc_info.value)


def test_obter_credenciais_senha_ausente(tmp_path: Path):
    """Valida erro quando apenas SHAREPOINT_ID está configurado."""
    env_sem_senha = tmp_path / ".env"
    env_sem_senha.write_text("SHAREPOINT_ID=usuario@hbt.com\n", encoding="utf-8")

    with pytest.raises(SobCredentialError) as exc_info:
        obter_credenciais_sharepoint(caminho_env=env_sem_senha)
    assert "[FALHA] Credenciais do SharePoint não configuradas." in str(exc_info.value)


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
    """Rejeita diretório vazio com mensagem da Seção 14.17."""
    croqui = tmp_path / "CROQUI"
    croqui.mkdir()

    client = SharePointClient(login="user", senha="pwd", headless=True)
    with pytest.raises(SobDownloadIncompleteError) as exc_info:
        client.validar_download(croqui)
    assert "[FALHA] Download reportado como concluído, porém o conteúdo não foi encontrado em CROQUI_DIR." in str(exc_info.value)


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
    [FALHA] Não foi possível autenticar no SharePoint.
    """
    # 1. Testa verificação direta de mensagem de erro
    with pytest.raises(SobAuthenticationError) as exc_info1:
        SharePointClient._verificar_erro_login(
            "Sua conta ou senha está incorreta. Se você não se lembra de sua senha, redefina-a agora."
        )

    msg1 = str(exc_info1.value)
    assert "[FALHA] Não foi possível autenticar no SharePoint." in msg1

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
    assert "[FALHA] Não foi possível autenticar no SharePoint." in msg2


def test_criterio_08_sob_inexistente():
    """
    TESTE 08 — SOB inexistente:
    Com uma SOB inexistente:
    [FALHA] SOB A999999999 não encontrada no SharePoint.
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
    assert (
        "[FALHA] SOB não encontrada." in msg
        or "[FALHA] SOB A999999999 não encontrada no SharePoint." in msg
    )


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

    assert (
        "[FALHA] Foram encontradas múltiplas correspondências ambíguas." in str(exc_info.value)
        or "[FALHA] Foram encontradas múltiplas correspondências para a SOB." in str(exc_info.value)
    )


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

    assert "[FALHA] Não foi possível autenticar no SharePoint." in str(exc_info.value)


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


def test_obter_url_sharepoint_padrao(tmp_path: Path):
    """Valida que a URL padrão do SharePoint aponta para a pasta Levantamentos de campo."""
    env_sem_url = tmp_path / ".env"
    env_sem_url.write_text("OUTRA=1\n", encoding="utf-8")

    url = obter_url_sharepoint(caminho_env=env_sem_url)
    assert url == SHAREPOINT_URL_PADRAO
    assert "HBT-EnelRJ-Sul" in url
    assert "IgALh51uFX0fRovCUeVsprYWAWYGyn7GwehC6BrYpg9KcFc" in url


def test_obter_url_sharepoint_customizada_env(tmp_path: Path):
    """Valida que SHAREPOINT_URL definida no .env sobrescreve a URL padrão."""
    env_com_url = tmp_path / ".env"
    custom_url = "https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/PASTA_CUSTOM"
    env_com_url.write_text(f'SHAREPOINT_URL="{custom_url}"\n', encoding="utf-8")

    url = obter_url_sharepoint(caminho_env=env_com_url)
    assert url == custom_url


def test_baixar_croqui_pasta_inteira_zip_com_subpasta(tmp_path: Path):
    """Valida que o download de uma pasta inteira compactada em ZIP pelo SharePoint é extraído e nivelado."""
    import zipfile

    client = SharePointClient(login="user", senha="pwd")
    client.driver = MagicMock()
    dest = tmp_path / "CROQUI"
    dest.mkdir(parents=True, exist_ok=True)

    # Simula o arquivo ZIP que o SharePoint gera ao baixar uma pasta inteira:
    # Contém uma subpasta SOB_A057389468 com arquivos dentro
    zip_path = dest / "SOB_A057389468.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("SOB_A057389468/croqui_levantamento.dwg", b"DWG DADOS REAIS")
        zf.writestr("SOB_A057389468/fotos/poste_01.jpg", b"FOTO DADOS REAIS")

    pasta_info = {"elemento": MagicMock(), "sob": "A057389468"}
    arquivos = client.baixar_croqui(pasta_info, dest)

    # O zip original deve ter sido removido
    assert not zip_path.exists()
    # Os arquivos devem ter sido extraídos diretamente para a raiz do destino
    dwg_extraido = dest / "croqui_levantamento.dwg"
    foto_extraida = dest / "fotos" / "poste_01.jpg"
    assert dwg_extraido.exists()
    assert foto_extraida.exists()
    assert client.validar_download(dest) is True


def test_baixar_pasta_por_url_zip_extraido_e_nivelado(tmp_path: Path):
    """Valida que baixar_pasta_por_url navega até o link, clica em baixar e processa o zip."""
    import zipfile

    client = SharePointClient(login="user", senha="pwd")
    client.driver = MagicMock()
    client._autenticado = True
    dest = tmp_path / "CROQUI_URL"
    dest.mkdir(parents=True, exist_ok=True)

    # Simula o ZIP baixado via navegador
    zip_path = dest / "PastaCompartilhada.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("PastaCompartilhada/desenho.dwg", b"DWG REAIS")

    url = "https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/compartilhada"
    arquivos = client.baixar_pasta_por_url(url, dest)

    client.driver.get.assert_called_with(url)
    assert not zip_path.exists()
    assert (dest / "desenho.dwg").exists()
    assert client.validar_download(dest) is True


def test_baixar_croqui_delega_para_baixar_pasta_por_url(tmp_path: Path):
    """Valida que baixar_croqui delega para baixar_pasta_por_url quando tipo é url_direta."""
    client = SharePointClient(login="user", senha="pwd")
    client.baixar_pasta_por_url = MagicMock(return_value=[tmp_path / "arquivo.dwg"])

    url = "https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/teste"
    pasta_info = {"tipo": "url_direta", "url": url, "sob": "A057349839"}

    res = client.baixar_croqui(pasta_info, tmp_path)
    client.baixar_pasta_por_url.assert_called_once_with(url, tmp_path)
    assert len(res) == 1


