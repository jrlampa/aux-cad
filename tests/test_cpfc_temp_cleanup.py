"""
test_cpfc_temp_cleanup.py - Testes de ciclo de vida e remoção segura de arquivos cpfc_contexto_*.json

Testes obrigatórios:
1. Cleanup normal: arquivo criado -> processo consome -> arquivo removido após término.
2. Não remover arquivo de outra execução: se existirem A e B, limpa exclusivamente A e preserva B.
3. Falha do processamento: falha do app é propagada sem mascaramento e cleanup é garantido no finally.
4. Arquivo inexistente: cleanup idempotente sem exceção funcional.
5. Falha de remoção: falha em unlink (ex: PermissionError) emite aviso e não derruba o app.
6. Ciclo de vida assíncrono: comprovar que durante o mainloop o arquivo permanece e só é removido ao terminar.
7. Preservação de JSON comum: arquivos de intercâmbio de usuário sem o prefixo temporário não são tocados.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
import pytest

from cpfc import cpfc_manager
from cpfc.cpfc_manager import (
    limpar_arquivo_temporario_contexto,
    carregar_dados_intercambio,
    main,
)


class MockGUIOk:
    """Mock da interface que simula ciclo de vida normal."""
    def __init__(self, projeto_inicial, pasta_padrao, dados_iniciais):
        self.projeto = projeto_inicial
        self.pasta = pasta_padrao
        self.dados = dados_iniciais
        self.mainloop_executado = False

    def mainloop(self):
        self.mainloop_executado = True


def test_1_cleanup_normal(monkeypatch, tmp_path):
    """Teste 1: arquivo temporário de contexto é consumido e removido após a execução."""
    temp_json = tmp_path / "cpfc_contexto_A057032667_teste.json"
    temp_json.write_text(
        json.dumps({"projeto": "A057032667", "municipio": "Rio de Janeiro"}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert temp_json.is_file()

    monkeypatch.setattr(cpfc_manager, "CPFCManagerGUI", MockGUIOk)
    monkeypatch.setattr(sys, "argv", ["cpfc_manager.py", str(temp_json)])

    main()

    # O arquivo deve ter sido removido com sucesso
    assert not temp_json.exists()


def test_2_nao_remover_arquivo_de_outra_execucao(monkeypatch, tmp_path):
    """Teste 2: cada processo remove exclusivamente o seu próprio arquivo temporário."""
    arq_a = tmp_path / "cpfc_contexto_PROJ_A_111.json"
    arq_b = tmp_path / "cpfc_contexto_PROJ_B_222.json"
    arq_a.write_text(json.dumps({"projeto": "PROJ_A"}), encoding="utf-8")
    arq_b.write_text(json.dumps({"projeto": "PROJ_B"}), encoding="utf-8")

    assert arq_a.is_file()
    assert arq_b.is_file()

    # Execução A apontando exclusivamente para arq_a
    monkeypatch.setattr(cpfc_manager, "CPFCManagerGUI", MockGUIOk)
    monkeypatch.setattr(sys, "argv", ["cpfc_manager.py", str(arq_a)])

    main()

    # A foi removido, B permanece intacto
    assert not arq_a.exists()
    assert arq_b.exists()


def test_3_falha_do_processamento_preserva_erro_e_executa_cleanup(monkeypatch, tmp_path):
    """Teste 3: se houver exceção no CPFC, ela é propagada e o cleanup ocorre no finally."""
    temp_json = tmp_path / "cpfc_contexto_FALHA_999.json"
    temp_json.write_text(json.dumps({"projeto": "FALHA"}), encoding="utf-8")
    assert temp_json.is_file()

    class MockGUIFalha:
        def __init__(self, projeto_inicial, pasta_padrao, dados_iniciais):
            pass

        def mainloop(self):
            raise RuntimeError("Erro fatal simulado na GUI")

    monkeypatch.setattr(cpfc_manager, "CPFCManagerGUI", MockGUIFalha)
    monkeypatch.setattr(sys, "argv", ["cpfc_manager.py", str(temp_json)])

    with pytest.raises(RuntimeError, match="Erro fatal simulado na GUI"):
        main()

    # Mesmo com o erro fatal, o finally garantiu a exclusão do temporário
    assert not temp_json.exists()


def test_4_arquivo_inexistente_sem_excecao(tmp_path):
    """Teste 4: cleanup executado em arquivo que já não existe não gera erro (idempotente)."""
    arquivo_inexistente = tmp_path / "cpfc_contexto_INEXISTENTE_000.json"
    assert not arquivo_inexistente.exists()

    resultado = limpar_arquivo_temporario_contexto(str(arquivo_inexistente))
    assert resultado is False

    # Argumentos vazios ou nulos
    assert limpar_arquivo_temporario_contexto(None) is False
    assert limpar_arquivo_temporario_contexto("") is False


def test_5_falha_de_remocao_nao_derruba_aplicacao(monkeypatch, tmp_path, capsys):
    """Teste 5: falha de I/O em unlink emite aviso e não quebra a saída normal do CPFC."""
    temp_json = tmp_path / "cpfc_contexto_LOCK_777.json"
    temp_json.write_text(json.dumps({"projeto": "LOCK"}), encoding="utf-8")
    assert temp_json.is_file()

    def mock_unlink_com_erro(self):
        raise PermissionError("Arquivo bloqueado por outro processo")

    monkeypatch.setattr(Path, "unlink", mock_unlink_com_erro)
    monkeypatch.setattr(cpfc_manager, "CPFCManagerGUI", MockGUIOk)
    monkeypatch.setattr(sys, "argv", ["cpfc_manager.py", str(temp_json)])

    # Execução deve concluir sem crash
    main()

    captured = capsys.readouterr()
    assert "[AVISO CPFC] Não foi possível remover arquivo temporário de contexto" in captured.out


def test_6_ciclo_de_vida_assincrono_nao_remocao_prematura(monkeypatch, tmp_path):
    """
    Teste 6: comprovar que o arquivo temporário permanece presente durante todo
    o ciclo de vida do processo filho (mainloop) e só é removido após seu término.
    """
    temp_json = tmp_path / "cpfc_contexto_ASYNC_333.json"
    temp_json.write_text(json.dumps({"projeto": "ASYNC"}), encoding="utf-8")
    assert temp_json.is_file()

    estado_durante_execucao = {"arquivo_existia_no_mainloop": False}

    class MockGUIAsync:
        def __init__(self, projeto_inicial, pasta_padrao, dados_iniciais):
            pass

        def mainloop(self):
            # Durante a execução do processo filho, o arquivo DEVE continuar existindo no disco
            estado_durante_execucao["arquivo_existia_no_mainloop"] = temp_json.is_file()

    monkeypatch.setattr(cpfc_manager, "CPFCManagerGUI", MockGUIAsync)
    monkeypatch.setattr(sys, "argv", ["cpfc_manager.py", str(temp_json)])

    main()

    # Comprova que NÃO houve remoção prematura
    assert estado_durante_execucao["arquivo_existia_no_mainloop"] is True
    # Comprova que ao término do processo filho o arquivo foi removido
    assert not temp_json.exists()


def test_7_preservacao_de_json_comum_de_usuario(monkeypatch, tmp_path):
    """
    Teste 7: arquivos JSON legítimos de projetos fornecidos pelo usuário sem o padrão
    'cpfc_contexto_*.json' NÃO são removidos após a execução do CPFC.
    """
    json_usuario = tmp_path / "meus_dados_cadastro.json"
    json_usuario.write_text(json.dumps({"projeto": "USER_PROJECT"}), encoding="utf-8")
    assert json_usuario.is_file()

    monkeypatch.setattr(cpfc_manager, "CPFCManagerGUI", MockGUIOk)
    monkeypatch.setattr(sys, "argv", ["cpfc_manager.py", str(json_usuario)])

    main()

    # O arquivo do usuário DEVE ser preservado intacto
    assert json_usuario.is_file()
