# -*- coding: utf-8 -*-
"""
Testes unitários automatizados para a Integração com GOMNET (Seção 19).
Cobre:
- Autenticação e gestão de sessão HTTP
- Extração de anexos no modal Upload.aspx
- Filtragem de anexarArquivo.gif (apenas arquivos reais da SOB)
- Download atômico e validação de integridade física
- Rejeição de páginas HTML de erro ASP.NET
- Criação e armazenamento canônico em CROQUI\\ANEXOS
- Rastreamento em GOMNET_ATTACHMENTS e GOMNET_CREATED_FILES
- Rollback seguro em caso de falha de download
- Idempotência (reuso de arquivo idêntico e bloqueio de divergente)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from sob.sob_gomnet import (
    GomnetAnexo,
    GomnetClient,
    GomnetAuthError,
    GomnetDownloadError,
    carregar_credenciais_gomnet,
)
from sob.sob_manager import SobOrchestrator
from sob.sob_rollback import RollbackContext


HTML_LOGIN_FORM = """
<html>
<body>
    <form id="form1">
        <input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="VS_TEST_123" />
        <input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="VSG_TEST_456" />
        <input type="text" name="txtBoxLogin" id="txtBoxLogin" />
        <input type="password" name="txtBoxSenha" id="txtBoxSenha" />
    </form>
</body>
</html>
"""

HTML_UPLOAD_COM_ANEXOS = """
<html>
<body>
    <input type="hidden" name="txtBoxNumSOB" id="txtBoxNumSOB" value="A057219996" />
    <table id="gridviewUploads">
        <tr>
            <th>TIPO</th><th>CATEGORIA</th><th>NOME DO ARQUIVO</th><th>DESCRIÇÃO</th><th>DATA DA GRAVAÇÃO</th><th>USUÁRIO</th><th>EXCLUIR</th>
        </tr>
        <tr>
            <td>CAD</td><td>PROJETO</td>
            <td><a id="gridviewUploads_ctl02_LinkButton1" onclick="baixarAnexo(this);">TE_A057219996_DESENHO.dwg</a></td>
            <td>Desenho do projeto</td>
            <td>12/09/2026 23:32:23</td>
            <td>A00437 - FABIO BARIGOSSI</td>
            <td></td>
            <td><input type="hidden" name="gridviewUploads$ctl02$HiddenField3" value="34193856" /></td>
        </tr>
        <tr>
            <td>OUT</td><td>PROJETO</td>
            <td><a id="gridviewUploads_ctl03_LinkButton1" onclick="baixarAnexo(this);">CQT_A057219996.xlsm</a></td>
            <td>Queda de tensao</td>
            <td>12/09/2026 23:32:54</td>
            <td>A00437 - FABIO BARIGOSSI</td>
            <td></td>
            <td><input type="hidden" name="gridviewUploads$ctl03$HiddenField3" value="34193858" /></td>
        </tr>
        <tr>
            <td>IMG</td><td>INTERFACE</td>
            <td><a id="gridviewUploads_ctl04_LinkButton1" onclick="baixarAnexo(this);">anexarArquivo.gif</a></td>
            <td>Icone de interface</td>
            <td>12/09/2026 23:32:54</td>
            <td>SISTEMA</td>
            <td></td>
            <td><input type="hidden" name="gridviewUploads$ctl04$HiddenField3" value="99999999" /></td>
        </tr>
    </table>
</body>
</html>
"""

HTML_UPLOAD_SEM_ANEXOS = """
<html>
<body>
    <table id="gridviewUploads">
        <tr><td>Não existem dados para serem exibidos.</td></tr>
    </table>
</body>
</html>
"""


def test_carregar_credenciais_gomnet_sucesso(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'GOMNET_LOGIN="USR_TESTE"\nGOMNET_SENHA="PWD_SECRET_123"\nGOMNET_URL="http://gomnet-test/login.aspx"\n',
        encoding="utf-8",
    )
    user, pwd, url = carregar_credenciais_gomnet(env_file)
    assert user == "USR_TESTE"
    assert pwd == "PWD_SECRET_123"
    assert url == "http://gomnet-test/login.aspx"


def test_carregar_credenciais_gomnet_ausente(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('OUTRA_VAR="123"\n', encoding="utf-8")
    with pytest.raises(GomnetAuthError):
        carregar_credenciais_gomnet(env_file)


def test_gomnet_login_sucesso():
    client = GomnetClient(usuario="USR_TESTE", senha="PWD_TESTE", login_url="http://gomnet/login.aspx")
    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.text = HTML_LOGIN_FORM

    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_post.text = "<html><body>Login OK</body></html>"

    with patch.object(client.session, "get", return_value=mock_get), \
         patch.object(client.session, "post", return_value=mock_post):
        assert client.autenticar() is True
        assert client.autenticado is True


def test_gomnet_login_falha():
    client = GomnetClient(usuario="USR_TESTE", senha="PWD_ERRADA", login_url="http://gomnet/login.aspx")
    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.text = HTML_LOGIN_FORM

    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_post.text = "<html><body>txtBoxLogin txtBoxSenha Senha Incorreta</body></html>"

    with patch.object(client.session, "get", return_value=mock_get), \
         patch.object(client.session, "post", return_value=mock_post):
        with pytest.raises(GomnetAuthError):
            client.autenticar()


def test_gomnet_listar_anexos_filtra_gif():
    client = GomnetClient(usuario="USR_TESTE", senha="PWD_TESTE", login_url="http://gomnet/login.aspx")
    client.autenticado = True

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = HTML_UPLOAD_COM_ANEXOS

    with patch.object(client.session, "get", return_value=mock_resp):
        anexos = client.localizar_sob_e_listar_anexos("A057219996")
        assert len(anexos) == 2  # DWG e XLSM, descartando anexarArquivo.gif
        nomes = [a.nome_arquivo for a in anexos]
        assert "TE_A057219996_DESENHO.dwg" in nomes
        assert "CQT_A057219996.xlsm" in nomes
        assert "anexarArquivo.gif" not in nomes

        dwg_anexo = anexos[0]
        assert dwg_anexo.id_arquivo == "34193856"
        assert dwg_anexo.tipo == "CAD"
        assert dwg_anexo.categoria == "PROJETO"
        assert "DownloadArquivo.aspx?id=34193856" in dwg_anexo.url_download


def test_gomnet_listar_anexos_sem_registros():
    client = GomnetClient(usuario="USR_TESTE", senha="PWD_TESTE", login_url="http://gomnet/login.aspx")
    client.autenticado = True

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = HTML_UPLOAD_SEM_ANEXOS

    with patch.object(client.session, "get", return_value=mock_resp):
        anexos = client.localizar_sob_e_listar_anexos("A000000000")
        assert anexos == []


def test_gomnet_download_atomico_sucesso(tmp_path):
    client = GomnetClient(usuario="USR_TESTE", senha="PWD_TESTE", login_url="http://gomnet/login.aspx")
    client.autenticado = True

    anexo = GomnetAnexo(
        id_arquivo="34193856",
        nome_arquivo="TE_DESENHO.dwg",
        tipo="CAD",
        categoria="PROJETO",
        descricao="",
        data_gravacao="",
        usuario="",
        url_download="http://gomnet/DownloadArquivo.aspx?id=34193856",
    )

    destino = tmp_path / "CROQUI" / "ANEXOS" / "TE_DESENHO.dwg"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/octet-stream"}
    mock_resp.iter_content.return_value = [b"AC1015", b"conteudo_dwg_valido"]
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(client.session, "get", return_value=mock_resp):
        resultado = client.baixar_anexo_atomico(anexo, destino)
        assert resultado.is_file()
        assert resultado.read_bytes().startswith(b"AC1015")
        assert not destino.with_name("TE_DESENHO.dwg.download").exists()


def test_gomnet_download_rejeita_html_erro(tmp_path):
    client = GomnetClient(usuario="USR_TESTE", senha="PWD_TESTE", login_url="http://gomnet/login.aspx")
    client.autenticado = True

    anexo = GomnetAnexo(
        id_arquivo="34193856",
        nome_arquivo="TE_DESENHO.dwg",
        tipo="CAD",
        categoria="PROJETO",
        descricao="",
        data_gravacao="",
        usuario="",
        url_download="http://gomnet/DownloadArquivo.aspx?id=34193856",
    )

    destino = tmp_path / "CROQUI" / "ANEXOS" / "TE_DESENHO.dwg"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.iter_content.return_value = [b"<!DOCTYPE html><html><body>Erro 500</body></html>"]
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(GomnetDownloadError) as exc:
            client.baixar_anexo_atomico(anexo, destino)
        assert "página HTML de erro" in str(exc.value)
        assert not destino.exists()
        assert not destino.with_name("TE_DESENHO.dwg.download").exists()


def test_gomnet_download_rejeita_arquivo_vazio(tmp_path):
    client = GomnetClient(usuario="USR_TESTE", senha="PWD_TESTE", login_url="http://gomnet/login.aspx")
    client.autenticado = True

    anexo = GomnetAnexo(
        id_arquivo="34193856",
        nome_arquivo="TE_DESENHO.dwg",
        tipo="CAD",
        categoria="PROJETO",
        descricao="",
        data_gravacao="",
        usuario="",
        url_download="http://gomnet/DownloadArquivo.aspx?id=34193856",
    )

    destino = tmp_path / "CROQUI" / "ANEXOS" / "TE_DESENHO.dwg"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.iter_content.return_value = []
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(GomnetDownloadError) as exc:
            client.baixar_anexo_atomico(anexo, destino)
        assert "0 bytes" in str(exc.value)
        assert not destino.exists()


def test_gomnet_integracao_orchestrator(tmp_path):
    destino_root = tmp_path / "Projetos"
    destino_root.mkdir()

    # Cria prancha.dwg válida para base_template
    base_tpl = tmp_path / "prancha.dwg"
    base_tpl.write_bytes(b"AC1032" + b"\x00" * 200)

    # Mock GomnetClient
    mock_gomnet = MagicMock(spec=GomnetClient)
    mock_gomnet.autenticado = True
    anexo_dwg = GomnetAnexo(
        id_arquivo="101",
        nome_arquivo="anexo_projeto.dwg",
        tipo="CAD",
        categoria="PROJETO",
        descricao="DWG GOMNET",
        data_gravacao="19/09/2026",
        usuario="A001",
        url_download="http://gomnet/dl/101",
    )
    mock_gomnet.localizar_sob_e_listar_anexos.return_value = [anexo_dwg]

    def mock_baixar(anexo, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"AC1015" + b"\x00" * 50)
        return dest

    mock_gomnet.baixar_anexo_atomico.side_effect = mock_baixar

    orchestrator = SobOrchestrator(
        origem_base=base_tpl,
        sharepoint_client=None,
        gomnet_client=mock_gomnet,
    )

    resultado = orchestrator.executar(
        sob_raw="A057219996",
        destino_dir=str(destino_root),
        baixar_croqui_sp=False,
        consultar_gomnet=True,
    )

    assert resultado["status"] == "CONCLUÍDO"
    assert resultado["sucesso"] is True
    assert len(resultado["GOMNET_ATTACHMENTS"]) == 1
    assert len(resultado["GOMNET_CREATED_FILES"]) == 1

    anexo_salvo = Path(resultado["GOMNET_CREATED_FILES"][0])
    assert anexo_salvo.is_file()
    assert anexo_salvo.name == "anexo_projeto.dwg"
    assert anexo_salvo.parent.name == "ANEXOS"
    assert anexo_salvo.parent.parent.name == "CROQUI"


def test_gomnet_rollback_em_falha_parcial(tmp_path):
    destino_root = tmp_path / "Projetos"
    destino_root.mkdir()

    base_tpl = tmp_path / "prancha.dwg"
    base_tpl.write_bytes(b"AC1032" + b"\x00" * 200)

    mock_gomnet = MagicMock(spec=GomnetClient)
    mock_gomnet.autenticado = True
    anexo_1 = GomnetAnexo("1", "ok.pdf", "OUT", "PROJ", "", "", "", "http://dl/1")
    anexo_2 = GomnetAnexo("2", "falha.pdf", "OUT", "PROJ", "", "", "", "http://dl/2")
    mock_gomnet.localizar_sob_e_listar_anexos.return_value = [anexo_1, anexo_2]

    def mock_baixar_falha(anexo, dest):
        if anexo.id_arquivo == "1":
            dest = Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"%PDF-1.4\nconteudo")
            return dest
        raise GomnetDownloadError("Erro simulado de rede no anexo 2")

    mock_gomnet.baixar_anexo_atomico.side_effect = mock_baixar_falha

    orchestrator = SobOrchestrator(
        origem_base=base_tpl,
        sharepoint_client=None,
        gomnet_client=mock_gomnet,
    )

    resultado = orchestrator.executar(
        sob_raw="A057219996",
        destino_dir=str(destino_root),
        baixar_croqui_sp=False,
        consultar_gomnet=True,
    )

    assert resultado["status"] == "BLOQUEADO"
    assert resultado["rollback"] == "ROLLBACK_CONCLUÍDO"

    # Confirma que a pasta da SOB foi limpa sem deixar resíduos
    sob_root = destino_root / "SOB_A057219996"
    assert not sob_root.exists()


def test_gomnet_falha_autenticacao_perguntar_usuario_continuar_sucesso(tmp_path):
    """
    Testa que erro ao autenticar no GOMNET não causa rollback se o usuário
    optar por continuar a preparação da SOB sem o fluxo do GOMNET.
    """
    destino_root = tmp_path / "Projetos"
    destino_root.mkdir()

    base_tpl = tmp_path / "prancha.dwg"
    base_tpl.write_bytes(b"AC1032" + b"\x00" * 200)

    mock_gomnet = MagicMock(spec=GomnetClient)
    mock_gomnet.autenticar.side_effect = GomnetAuthError("Falha de conexão / timeout com GOMNET")

    orchestrator = SobOrchestrator(
        origem_base=base_tpl,
        sharepoint_client=None,
        gomnet_client=mock_gomnet,
    )

    # Simula callback onde o usuário escolhe CONTINUAR (True)
    mock_cb = MagicMock()
    mock_cb.cancelamento_solicitado.return_value = False
    mock_cb.perguntar_continuar_sem_gomnet.return_value = True

    resultado = orchestrator.executar(
        sob_raw="A057219996",
        destino_dir=str(destino_root),
        baixar_croqui_sp=False,
        consultar_gomnet=True,
        callback_progresso=mock_cb,
    )

    # O processo NÃO deve ter feito rollback; deve ter concluído com sucesso
    assert resultado["status"] == "CONCLUÍDO"
    assert resultado["sucesso"] is True
    assert resultado.get("GOMNET_IGNORADO") is True
    assert mock_cb.perguntar_continuar_sem_gomnet.called

    sob_root = destino_root / "SOB_A057219996"
    assert sob_root.is_dir()
    dwg_file = sob_root / "PE_A057219996_DESENHO.dwg"
    assert dwg_file.is_file()


def test_gomnet_falha_download_perguntar_usuario_continuar_sucesso(tmp_path):
    """
    Testa que erro ao baixar anexos do GOMNET não causa rollback se o usuário
    optar por continuar a preparação da SOB sem os anexos do GOMNET.
    """
    destino_root = tmp_path / "Projetos"
    destino_root.mkdir()

    base_tpl = tmp_path / "prancha.dwg"
    base_tpl.write_bytes(b"AC1032" + b"\x00" * 200)

    mock_gomnet = MagicMock(spec=GomnetClient)
    mock_gomnet.autenticado = True
    anexo_1 = GomnetAnexo("1", "ok.pdf", "OUT", "PROJ", "", "", "", "http://dl/1")
    mock_gomnet.localizar_sob_e_listar_anexos.return_value = [anexo_1]
    mock_gomnet.baixar_anexo_atomico.side_effect = GomnetDownloadError("Erro de rede no download")

    orchestrator = SobOrchestrator(
        origem_base=base_tpl,
        sharepoint_client=None,
        gomnet_client=mock_gomnet,
    )

    # Simula callback onde o usuário escolhe CONTINUAR (True)
    mock_cb = MagicMock()
    mock_cb.cancelamento_solicitado.return_value = False
    mock_cb.perguntar_continuar_sem_gomnet.return_value = True

    resultado = orchestrator.executar(
        sob_raw="A057219996",
        destino_dir=str(destino_root),
        baixar_croqui_sp=False,
        consultar_gomnet=True,
        callback_progresso=mock_cb,
    )

    # O processo NÃO deve ter feito rollback; deve ter concluído com sucesso
    assert resultado["status"] == "CONCLUÍDO"
    assert resultado["sucesso"] is True
    assert resultado.get("GOMNET_DOWNLOAD_IGNORADO") is True
    assert mock_cb.perguntar_continuar_sem_gomnet.called

    sob_root = destino_root / "SOB_A057219996"
    assert sob_root.is_dir()
    dwg_file = sob_root / "PE_A057219996_DESENHO.dwg"
    assert dwg_file.is_file()


def test_gomnet_falha_perguntar_usuario_escolhe_rollback(tmp_path):
    """
    Testa que se o usuário for perguntado e optar por NÃO continuar (False),
    o rollback é executado e o processo é bloqueado.
    """
    destino_root = tmp_path / "Projetos"
    destino_root.mkdir()

    base_tpl = tmp_path / "prancha.dwg"
    base_tpl.write_bytes(b"AC1032" + b"\x00" * 200)

    mock_gomnet = MagicMock(spec=GomnetClient)
    mock_gomnet.autenticado = True
    anexo_1 = GomnetAnexo("1", "falha.pdf", "OUT", "PROJ", "", "", "", "http://dl/1")
    mock_gomnet.localizar_sob_e_listar_anexos.return_value = [anexo_1]
    mock_gomnet.baixar_anexo_atomico.side_effect = GomnetDownloadError("Erro no download")

    orchestrator = SobOrchestrator(
        origem_base=base_tpl,
        sharepoint_client=None,
        gomnet_client=mock_gomnet,
    )

    # Simula callback onde o usuário escolhe FAZER ROLLBACK (False)
    mock_cb = MagicMock()
    mock_cb.cancelamento_solicitado.return_value = False
    mock_cb.perguntar_continuar_sem_gomnet.return_value = False

    resultado = orchestrator.executar(
        sob_raw="A057219996",
        destino_dir=str(destino_root),
        baixar_croqui_sp=False,
        consultar_gomnet=True,
        callback_progresso=mock_cb,
    )

    assert resultado["status"] == "BLOQUEADO"
    assert resultado["rollback"] == "ROLLBACK_CONCLUÍDO"

    # Confirma que a pasta da SOB foi removida pelo rollback
    sob_root = destino_root / "SOB_A057219996"
    assert not sob_root.exists()


def test_progresso_observer_perguntar_continuar_sem_gomnet():
    """Testa o método perguntar_continuar_sem_gomnet do ProgressoObserver."""
    from sob.sob_progress_gui import ProgressoObserver

    obs = ProgressoObserver()
    dados_teste = {"erro": "Conexão recusada"}

    # Responde em outra thread para desbloquear
    import threading
    def _responder():
        import time
        time.sleep(0.05)
        obs.responder_intervencao(True)

    t = threading.Thread(target=_responder)
    t.start()

    resp = obs.perguntar_continuar_sem_gomnet(dados_teste)
    t.join()

    assert resp is True
    ev = obs.obter_evento()
    assert ev["tipo"] == "PROGRESSO"
    assert ev["etapa"] == "INTERVENCAO_GOMNET"

