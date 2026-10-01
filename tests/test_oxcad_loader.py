from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
LOADER_FILE = ROOT_DIR / "oxcad" / "oxcad_loader.lsp"


def test_oxcad_loader_sintaxe_parenteses_balanceados():
    """Garante que a sintaxe LISP está 100% balanceada em parênteses e aspas."""
    conteudo = LOADER_FILE.read_text(encoding="utf-8")
    balance = 0
    in_str = False
    escape = False

    for char in conteudo:
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
        else:
            if char == '"':
                in_str = True
            elif char == "(":
                balance += 1
            elif char == ")":
                balance -= 1
                assert balance >= 0, "Parêntese de fechamento sem correspondente"

    assert balance == 0, "Parênteses desbalanceados no oxcad_loader.lsp"
    assert not in_str, "String não terminada no oxcad_loader.lsp"


def test_oxcad_loader_usa_command_netload_e_nao_vl_cmdf_cego():
    """Garante uso de command _.NETLOAD para tolerância nativa a caminhos com espaços."""
    conteudo = LOADER_FILE.read_text(encoding="utf-8")
    assert 'command "_.NETLOAD" dll-path' in conteudo
    assert 'vl-cmdf "_.NETLOAD"' not in conteudo


def test_oxcad_loader_verifica_registro_antes_de_recarregar():
    """Garante que DLL já carregada não dispara NETLOAD redundante."""
    conteudo = LOADER_FILE.read_text(encoding="utf-8")
    # c:oxcad-load-dll verifica getcname antes de iniciar o netload
    assert '(or (getcname "OXCAD_DIAGNOSTICO") (getcname "OXCAD"))' in conteudo


def test_oxcad_loader_bloqueia_oxcad_quando_netload_falhar():
    """Se a DLL não estiver carregada nem registrar comando, c:OXCAD não chama o comando .NET."""
    conteudo = LOADER_FILE.read_text(encoding="utf-8")
    # c:OXCAD deve ter guarda de verificação de registro/carregamento
    assert 'defun c:OXCAD ( / command-result )' in conteudo
    assert '(if (or (getcname "OXCAD_DIAGNOSTICO")' in conteudo
    assert 'A paleta OXCAD nao sera aberta porque a DLL nao foi carregada.' in conteudo


def test_oxcad_loader_mensagens_claras_de_erro_sem_suprimir():
    """Garante que erros de carregamento ou registro não são mascarados."""
    conteudo = LOADER_FILE.read_text(encoding="utf-8")
    assert "DLL OxCadPaleta.dll nao encontrada em bin/Release." in conteudo
    assert "NETLOAD terminou, mas os comandos do OXCAD nao foram registrados." in conteudo
    assert "Falha na execucao do NETLOAD:" in conteudo
    assert "Falha ao executar OXCAD:" in conteudo


def test_oxcad_loader_todos_os_comandos_possuem_guarda():
    """Garante que FECHAR_OXCAD, RECARREGAR_OXCAD e OXCAD_DIAGNOSTICO possuem guardas de registro."""
    conteudo = LOADER_FILE.read_text(encoding="utf-8")
    assert "defun c:FECHAR_OXCAD" in conteudo
    assert "defun c:RECARREGAR_OXCAD" in conteudo
    assert "defun c:OXCAD_DIAGNOSTICO" in conteudo
    assert "A paleta OXCAD nao esta carregada." in conteudo
