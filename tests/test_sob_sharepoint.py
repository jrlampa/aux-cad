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


# =============================================================================
# TESTES ESPECÍFICOS — BUSCA PRIORITÁRIA "Levantamentos de campo" & FALLBACK
# =============================================================================

def test_caso_1_encontrado_na_pasta_prioritaria_nao_executa_fallback():
    """
    Caso 1 — Encontrado na pasta prioritária:
    SOB -> Levantamentos de campo -> croqui encontrado -> fallback NÃO executado.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    resultado_mock_prio = {
        "texto": "SOB_A057349839\nModificado recentemente",
        "sob": "A057349839",
        "origem": "LEVANTAMENTOS_DE_CAMPO",
    }
    client.buscar_em_levantamentos_campo = MagicMock(return_value=resultado_mock_prio)
    client.localizar_pasta_sob_existente = MagicMock()

    res = client.localizar_pasta_sob("A057349839")

    assert res == resultado_mock_prio
    client.buscar_em_levantamentos_campo.assert_called_once_with("A057349839")
    client.localizar_pasta_sob_existente.assert_not_called()


def test_caso_2_nao_encontrado_na_pasta_prioritaria_executa_fallback():
    """
    Caso 2 — Não encontrado na pasta prioritária:
    SOB -> Levantamentos de campo -> zero resultados -> fallback executado.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    resultado_mock_fallback = {
        "texto": "SOB_A057349839\nEncontrado na busca geral",
        "sob": "A057349839",
        "origem": "BUSCA_GERAL_SHAREPOINT",
    }
    client.buscar_em_levantamentos_campo = MagicMock(return_value=None)
    client.localizar_pasta_sob_existente = MagicMock(return_value=resultado_mock_fallback)

    res = client.localizar_pasta_sob("A057349839")

    assert res == resultado_mock_fallback
    client.buscar_em_levantamentos_campo.assert_called_once_with("A057349839")
    client.localizar_pasta_sob_existente.assert_called_once_with("A057349839")


def test_caso_3_resultados_invalidos_na_pasta_prioritaria_executa_fallback():
    """
    Caso 3 — Resultados encontrados, mas inválidos:
    Levantamentos de campo -> itens temporários ou com extensões impróprias ->
    nenhum croqui válido -> fallback executado.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    # Valida método interno _item_eh_croqui_valido
    assert client._item_eh_croqui_valido("~$A057349839.dwg", "A057349839") is False
    assert client._item_eh_croqui_valido("A057349839.tmp", "A057349839") is False
    assert client._item_eh_croqui_valido("A057349839.exe", "A057349839") is False
    assert client._item_eh_croqui_valido("A057349839.crdownload", "A057349839") is False
    assert client._item_eh_croqui_valido("OUTRA_SOB_11111.dwg", "A057349839") is False
    assert client._item_eh_croqui_valido("A057349839_croqui.dwg", "A057349839") is True
    assert client._item_eh_croqui_valido("SOB_A057349839", "A057349839") is True

    # Simula mock do driver retornando apenas arquivos inválidos
    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/..."
    row_invalido = MagicMock()
    row_invalido.text = "~$A057349839.dwg"
    mock_driver.find_elements.return_value = [row_invalido]
    client.driver = mock_driver

    resultado_mock_fb = {"texto": "SOB_A057349839", "sob": "A057349839"}
    client.localizar_pasta_sob_existente = MagicMock(return_value=resultado_mock_fb)

    res = client.localizar_pasta_sob("A057349839")
    assert res == resultado_mock_fb
    client.localizar_pasta_sob_existente.assert_called_once_with("A057349839")


def test_caso_4_multiplos_resultados_preserva_comportamento_conflito():
    """
    Caso 4 — Múltiplos resultados na busca prioritária:
    Verificar que levanta SobConflictError com as ocorrências e preserva o comportamento.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/..."
    row1 = MagicMock()
    row1.text = "SOB_A057349839_SUBPASTA_A\nItem 1"
    row2 = MagicMock()
    row2.text = "SOB_A057349839_SUBPASTA_B\nItem 2"
    mock_driver.find_elements.return_value = [row1, row2]
    client.driver = mock_driver

    with pytest.raises(SobConflictError) as exc_info:
        client.localizar_pasta_sob("A057349839")

    assert "[FALHA] Foram encontradas múltiplas correspondências ambíguas." in str(exc_info.value)
    assert len(exc_info.value.ocorrencias) == 2


def test_caso_5_erro_nao_fatal_na_busca_prioritaria_executa_fallback():
    """
    Caso 5 — Erro não fatal na busca prioritária:
    Verificar que falha de rede/elemento em Levantamentos de campo não interrompe o processo,
    acionando o fallback de forma segura.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    client.buscar_em_levantamentos_campo = MagicMock(side_effect=RuntimeError("Timeout no elemento da pasta"))
    resultado_mock_fb = {"texto": "SOB_A057349839", "sob": "A057349839"}
    client.localizar_pasta_sob_existente = MagicMock(return_value=resultado_mock_fb)

    res = client.localizar_pasta_sob("A057349839")
    assert res == resultado_mock_fb
    client.localizar_pasta_sob_existente.assert_called_once_with("A057349839")


def test_caso_6_erro_autenticacao_nao_mascarado_como_nao_encontrado():
    """
    Caso 6 — Erro de autenticação/acesso:
    Verificar que falha de autenticação NÃO é capturada nem mascarada como 'não encontrado'.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    client.buscar_em_levantamentos_campo = MagicMock(
        side_effect=SobAuthenticationError("[FALHA] Não foi possível autenticar no SharePoint.")
    )
    client.localizar_pasta_sob_existente = MagicMock()

    with pytest.raises(SobAuthenticationError) as exc_info:
        client.localizar_pasta_sob("A057349839")

    assert "[FALHA] Não foi possível autenticar no SharePoint." in str(exc_info.value)
    client.localizar_pasta_sob_existente.assert_not_called()


@pytest.mark.parametrize("sob_input", [
    "a057349839",
    "A057349839",
    " A057349839 ",
    "SOB_a057349839",
    "SOB_A057349839",
])
def test_caso_7_sob_normalizada(sob_input):
    """
    Caso 7 — SOB normalizada:
    Verificar comportamento com variações de caixa, espaços e prefixos de SOB.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/..."
    row = MagicMock()
    row.text = "SOB_A057349839\nModificado há 1 dia"
    mock_driver.find_elements.return_value = [row]
    client.driver = mock_driver

    res = client.localizar_pasta_sob(sob_input)
    assert res["sob"] == "A057349839"
    assert "SOB_A057349839" in res["texto"]


def test_busca_mesma_sob_multiplos_artefatos_nao_eh_conflito():
    """
    Caso: A057526153 (pasta), A057526153_CROQUI.pdf, A057526153_FOTOS.zip
    Resultado: NÃO É CONFLITO. Reconhece artefatos da mesma SOB e prioriza a pasta.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/sites/HBT-EnelRJ-Sul/Documentos"

    row_pasta = MagicMock()
    row_pasta.text = "A057526153\nClaudia Carvalho\nterça-feira às 11:44"

    row_croqui = MagicMock()
    row_croqui.text = "A057526153_CROQUI.pdf\nClaudia Carvalho\nterça-feira às 11:44"

    row_fotos = MagicMock()
    row_fotos.text = "A057526153_FOTOS.zip\nClaudia Carvalho\nterça-feira às 11:44"

    mock_driver.find_elements.return_value = [row_pasta, row_croqui, row_fotos]
    client.driver = mock_driver

    res = client.localizar_pasta_sob_existente("A057526153")
    assert res is not None
    # Deve priorizar a pasta cujo nome é exatamente o SOB_ID
    assert "A057526153" in res["texto"]
    assert "A057526153_CROQUI.pdf" not in res["texto"]


def test_busca_sobs_diferentes_eh_conflito():
    """
    Caso: A057526153 e A057526154 retornados no mesmo lote de busca.
    Resultado: CONFLITO. Identidades de SOB distintas no mesmo lote geram SobConflictError.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/sites/HBT-EnelRJ-Sul/Documentos"

    row_sob1 = MagicMock()
    row_sob1.text = "A057526153\nObra 1"

    row_sob2 = MagicMock()
    row_sob2.text = "A057526154\nObra 2"

    mock_driver.find_elements.return_value = [row_sob1, row_sob2]
    client.driver = mock_driver

    # Busca abrangente trazendo duas SOBs distintas
    with pytest.raises(SobConflictError) as exc_info:
        client.localizar_pasta_sob_existente("5752615")

    assert "[FALHA] Foram encontradas múltiplas correspondências ambíguas." in str(exc_info.value)

    # Valida também via invocação direta de _resolver_itens_sob
    with pytest.raises(SobConflictError):
        client._resolver_itens_sob(
            [{"texto": "A057526153\nObra 1"}, {"texto": "A057526154\nObra 2"}],
            "A057526153",
            "https://sharepoint.com",
        )


def test_busca_somente_croqui_encontrado():
    """
    Caso: Somente A057526153_CROQUI.pdf encontrado (sem pasta separada).
    Resultado: SOB ENCONTRADA. Retorna com sucesso o arquivo de croqui.
    """
    client = SharePointClient(login="user", senha="pwd")
    client._autenticado = True

    mock_driver = MagicMock()
    mock_driver.current_url = "https://hbtengenharia1.sharepoint.com/sites/HBT-EnelRJ-Sul/Documentos"

    row_croqui = MagicMock()
    row_croqui.text = "A057526153_CROQUI.pdf\nClaudia Carvalho"

    mock_driver.find_elements.return_value = [row_croqui]
    client.driver = mock_driver

    res = client.localizar_pasta_sob_existente("A057526153")
    assert res is not None
    assert "A057526153_CROQUI.pdf" in res["texto"]


def test_seletores_modernos_sharepoint_em_baixar_pasta_por_url(tmp_path: Path):
    """
    Valida a resolução dos seletores semânticos modernos do SharePoint
    (data-automationid='selection-checkbox', aria-label='Selecionar todas as linhas')
    onde o botão de Download só surge no DOM após a marcação do checkbox.
    """
    client = SharePointClient(login="user", senha="pwd")
    mock_driver = MagicMock()
    client.driver = mock_driver
    client._autenticado = True

    dest = tmp_path / "CROQUI_SELETORES"
    dest.mkdir(parents=True, exist_ok=True)
    # Arquivo simulado para satisfazer _aguardar_e_processar_download
    (dest / "A057526153_CROQUI.pdf").write_bytes(b"%PDF-1.4 DADOS REAIS")

    mock_chk = MagicMock()
    mock_chk.get_attribute.return_value = "selection-checkbox"

    mock_btn_dl = MagicMock()
    mock_btn_dl.is_displayed.return_value = True
    mock_btn_dl.text = "Baixar"

    checkbox_selecionado = False

    def mock_find_elements(by, selector):
        nonlocal checkbox_selecionado
        if "selection-checkbox" in selector or "Selecionar todas" in selector:
            return [mock_chk]
        if "downloadCommand" in selector or "Baixar" in selector:
            return [mock_btn_dl] if checkbox_selecionado else []
        return []

    def mock_execute_script(script, elem):
        nonlocal checkbox_selecionado
        if elem == mock_chk:
            checkbox_selecionado = True

    mock_driver.find_elements.side_effect = mock_find_elements
    mock_driver.execute_script.side_effect = mock_execute_script

    url_teste = "https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/A057526153"
    arqs = client.baixar_pasta_por_url(url_teste, dest)

    assert len(arqs) >= 1
    # Verifica que o script JS foi executado para clicar no checkbox moderno e no botão de download
    assert mock_driver.execute_script.call_count >= 2
    assert checkbox_selecionado is True
