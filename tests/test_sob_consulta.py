from pathlib import Path

import pytest

from sob.sob_consulta import baixar_sob, consultar_sob
from sob.sob_gomnet import GomnetAnexo, GomnetError, GomnetNotFoundError


@pytest.fixture

def anexo():
    return GomnetAnexo(
        id_arquivo="123",
        nome_arquivo="Projeto.dwg",
        tipo="CAD",
        categoria="PROJETO",
        descricao="Projeto",
        data_gravacao="",
        usuario="",
        url_download="https://gomnet/download/123",
    )


class FakeGomnetClient:
    def __init__(self, anexos):
        self.anexos = anexos
        self.baixados = []

    def localizar_sob_e_listar_anexos(self, sob_id):
        return self.anexos

    def baixar_anexo_atomico(self, anexo, destino):
        caminho = Path(destino)
        caminho.write_bytes(b"conteudo")
        self.baixados.append(caminho)
        return caminho


def test_consultar_sob_retorna_anexos_e_nao_inventa_status(anexo):
    resultado = consultar_sob("A057219996", FakeGomnetClient([anexo]))

    assert resultado["success"] is True
    assert resultado["status"] is None
    assert "não encontrado" in resultado["status_mensagem"].lower()
    assert resultado["anexos"][0]["nome"] == "Projeto.dwg"
    assert resultado["anexos"][0]["extensao"] == ".dwg"


def test_consultar_sob_inclui_status_retorno_gomnet(anexo):
    client = FakeGomnetClient([anexo])
    client.obter_status_sob = lambda sob_id: "Em Execução"

    resultado = consultar_sob("A057219996", client)

    assert resultado["status"] == "Em Execução"
    assert resultado["status_mensagem"] == ""


def test_consultar_sob_distingue_status_vazio(anexo):
    client = FakeGomnetClient([anexo])
    client.obter_status_sob = lambda sob_id: ""

    resultado = consultar_sob("A057219996", client)

    assert resultado["status"] is None
    assert resultado["status_mensagem"] == "Status cadastral em branco no GOMNET."


def test_consultar_sob_preserva_anexos_se_consulta_status_falhar(anexo):
    client = FakeGomnetClient([anexo])

    def falhar_status(sob_id):
        raise GomnetError("A grade de acompanhamento não respondeu.")

    client.obter_status_sob = falhar_status
    resultado = consultar_sob("A057219996", client)

    assert resultado["success"] is True
    assert len(resultado["anexos"]) == 1
    assert resultado["status"] is None
    assert "grade de acompanhamento" in resultado["status_mensagem"]


def test_consultar_sob_retorna_mensagem_sem_anexos():
    resultado = consultar_sob("A057219996", FakeGomnetClient([]))

    assert resultado["success"] is True
    assert resultado["anexos"] == []
    assert resultado["message"] == "Nenhum projeto ou anexo vinculado a esta SOB."


def test_consultar_sob_preserva_erro_de_sob_nao_encontrada():
    class ClientNaoEncontrado(FakeGomnetClient):
        def localizar_sob_e_listar_anexos(self, sob_id):
            raise GomnetNotFoundError(f"SOB {sob_id} não encontrada no GOMNET.")

    with pytest.raises(GomnetNotFoundError, match="não encontrada"):
        consultar_sob("A057219996", ClientNaoEncontrado([]))


def test_baixar_sob_cria_subpasta_e_salva_anexos(tmp_path, anexo):
    client = FakeGomnetClient([anexo])
    resultado = baixar_sob("A057219996", tmp_path, client)

    pasta = tmp_path / "PROJETO CONSULTADO"
    assert resultado["success"] is True
    assert Path(resultado["diretorio"]) == pasta
    assert (pasta / "Projeto.dwg").read_bytes() == b"conteudo"
    assert client.baixados == [pasta / "Projeto.dwg"]


def test_baixar_sob_sem_anexos_nao_cria_pasta(tmp_path):
    resultado = baixar_sob("A057219996", tmp_path, FakeGomnetClient([]))

    assert resultado["success"] is False
    assert resultado["error_code"] == "SEM_ANEXOS"
    assert not (tmp_path / "PROJETO CONSULTADO").exists()


def test_baixar_sob_usa_diretorio_exato(tmp_path, anexo):
    pasta_exata = tmp_path / "CROQUI" / "ANEXOS"
    resultado = baixar_sob(
        "A057219996",
        client=FakeGomnetClient([anexo]),
        diretorio_download=pasta_exata,
    )

    assert resultado["success"] is True
    assert Path(resultado["diretorio"]) == pasta_exata.resolve()
    assert (pasta_exata / "Projeto.dwg").read_bytes() == b"conteudo"


def test_baixar_sob_nao_sobrescreve_arquivo_existente(tmp_path, anexo):
    (tmp_path / "Projeto.dwg").write_bytes(b"arquivo original")

    resultado = baixar_sob(
        "A057219996",
        client=FakeGomnetClient([anexo]),
        diretorio_download=tmp_path,
    )

    assert resultado["success"] is False
    assert resultado["error_code"] == "ARQUIVO_EXISTENTE"
    assert (tmp_path / "Projeto.dwg").read_bytes() == b"arquivo original"


def test_contexto_sob_igual_ao_ativo_consulta_e_download_normais(tmp_path, anexo):
    """Cenário 1: SOB consultada igual à SOB do contexto ativo OXCAD."""
    client_cons = FakeGomnetClient([anexo])
    res_cons = consultar_sob("A057219996", client=client_cons, contexto_ativo_sob="A057219996")

    assert res_cons["success"] is True
    assert res_cons["status_contexto"] == "CONGRUENTE"
    assert res_cons["congruente"] is True
    assert res_cons["divergencia"] is False
    assert res_cons["vinculado_projeto_ativo"] is True

    client_dl = FakeGomnetClient([anexo])
    res_dl = baixar_sob(
        "A057219996",
        destino_base=tmp_path,
        client=client_dl,
        contexto_ativo_sob="A057219996",
    )
    assert res_dl["success"] is True
    assert res_dl["divergencia"] is False
    assert res_dl["vinculado_projeto_ativo"] is True
    assert len(client_dl.baixados) == 1


def test_contexto_sob_diferente_do_ativo_classifica_divergencia(anexo):
    """Cenário 2: SOB consultada diferente da SOB do projeto ativo."""
    client = FakeGomnetClient([anexo])
    res = consultar_sob("A057219996", client=client, contexto_ativo_sob="A057385505")

    assert res["success"] is True
    assert res["status_contexto"] == "DIVERGENTE"
    assert res["congruente"] is False
    assert res["divergencia"] is True
    assert res["vinculado_projeto_ativo"] is False
    assert "diverge do projeto ativo" in res["contexto"]["mensagem"]


def test_ausencia_de_contexto_oxcad_trata_como_operacao_avulsa(tmp_path, anexo):
    """Cenário 3: Ausência de contexto OXCAD vinculado ao DWG."""
    client_cons = FakeGomnetClient([anexo])
    res_cons = consultar_sob("A057219996", client=client_cons, contexto_ativo_sob=None)

    assert res_cons["success"] is True
    assert res_cons["status_contexto"] == "SEM_CONTEXTO"
    assert res_cons["congruente"] is False
    assert res_cons["divergencia"] is False
    assert res_cons["vinculado_projeto_ativo"] is False

    client_dl = FakeGomnetClient([anexo])
    res_dl = baixar_sob("A057219996", destino_base=tmp_path, client=client_dl, contexto_ativo_sob="")
    assert res_dl["success"] is True
    assert res_dl["vinculado_projeto_ativo"] is False
    assert res_dl["divergencia"] is False


def test_consulta_sob_divergente_permitida(anexo):
    """Cenário 4: Consulta de SOB divergente é permitida e retorna anexos com aviso."""
    client = FakeGomnetClient([anexo])
    res = consultar_sob("A057219996", client=client, contexto_ativo_sob="A057111222")

    assert res["success"] is True
    assert len(res["anexos"]) == 1
    assert res["divergencia"] is True
    assert res["status_contexto"] == "DIVERGENTE"


def test_download_sob_divergente_exige_confirmacao(tmp_path, anexo):
    """Cenário 5: Download de SOB divergente sem confirmação é bloqueado preventivamente."""
    client = FakeGomnetClient([anexo])
    res = baixar_sob(
        "A057219996",
        destino_base=tmp_path,
        client=client,
        contexto_ativo_sob="A057999888",
        confirmar_divergencia=False,
    )

    assert res["success"] is False
    assert res["error_code"] == "CONFIRMACAO_DIVERGENCIA_NECESSARIA"
    assert res["divergencia"] is True
    assert len(client.baixados) == 0
    assert not (tmp_path / "PROJETO CONSULTADO").exists()


def test_cancelamento_da_confirmacao_nao_executa_download(tmp_path, anexo):
    """Cenário 6: Sem confirmação não há download; com confirmação o download é executado."""
    client = FakeGomnetClient([anexo])

    # 1. Simula cancelamento pelo usuário (sem flag de confirmação)
    res_cancelado = baixar_sob(
        "A057219996",
        destino_base=tmp_path,
        client=client,
        contexto_ativo_sob="A057385505",
        confirmar_divergencia=False,
    )
    assert res_cancelado["success"] is False
    assert len(client.baixados) == 0

    # 2. Simula confirmação explícita pelo usuário
    res_confirmado = baixar_sob(
        "A057219996",
        destino_base=tmp_path,
        client=client,
        contexto_ativo_sob="A057385505",
        confirmar_divergencia=True,
    )
    assert res_confirmado["success"] is True
    assert res_confirmado["divergencia"] is True
    assert res_confirmado["vinculado_projeto_ativo"] is False
    assert res_confirmado["pertence_a_sob_consultada"] is True
    assert len(client.baixados) == 1


def test_identidade_nao_pode_ser_fabricada_pelo_python():
    """Cenário 7: O Python não pode fabricar identidade e rejeita contextos inválidos."""
    from sob.sob_consulta import avaliar_contexto_oxcad

    # Rejeita entrada inválida sem formato oficial (caracteres especiais proibidos)
    avaliacao_invalida = avaliar_contexto_oxcad("A057219996", "SOB_INVALIDA#@!XYZ")
    assert avaliacao_invalida["status_contexto"] == "CONTEXTO_INVALIDO"
    assert avaliacao_invalida["congruente"] is False
    assert avaliacao_invalida["vinculado_projeto_ativo"] is False

    # Confirma que sem contexto explícito o Python nunca presume que o projeto é ativo
    avaliacao_vazia = avaliar_contexto_oxcad("A057219996", None)
    assert avaliacao_vazia["status_contexto"] == "SEM_CONTEXTO"
    assert avaliacao_vazia["vinculado_projeto_ativo"] is False
