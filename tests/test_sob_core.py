# -*- coding: utf-8 -*-
"""
Testes Unitários para o Núcleo do Módulo SOB (sob_core.py).
Cobre: Normalização, validação, proteção de diretórios e cópia do DWG.
"""

from pathlib import Path
import pytest
import shutil

from sob_core import (
    normalizar_sob,
    extrair_codigo_sob,
    validar_sob,
    verificar_pasta_sob_existente,
    criar_estrutura_sob,
    copiar_arquivo_base,
    validar_arquivo_dwg,
    SobValidationError,
    SobDirectoryExistsError,
    SobFileNotFoundError,
)


def test_criterio_01_normalizar_sob_sem_prefixo():
    """TESTE 01 — SOB sem prefixo: A057349839 -> SOB_A057349839"""
    assert normalizar_sob("A057349839") == "SOB_A057349839"


def test_criterio_02_normalizar_sob_com_prefixo():
    """TESTE 02 — SOB com prefixo: SOB_A057349839 -> SOB_A057349839 (nunca duplicar)"""
    assert normalizar_sob("SOB_A057349839") == "SOB_A057349839"
    # Testa variações acidentais
    assert normalizar_sob("SOB_SOB_A057349839") == "SOB_A057349839"
    assert normalizar_sob("sob_a057349839") == "SOB_A057349839"
    assert normalizar_sob("  A057349839  ") == "SOB_A057349839"


def test_normalizar_sob_invalidos():
    """Valida rejeição de entradas vazias ou inválidas."""
    with pytest.raises(SobValidationError):
        normalizar_sob("")
    with pytest.raises(SobValidationError):
        normalizar_sob("   ")
    with pytest.raises(SobValidationError):
        normalizar_sob("SOB_")


def test_extrair_codigo_sob():
    """Valida extração apenas do código numérico/alfanumérico."""
    assert extrair_codigo_sob("A057349839") == "A057349839"
    assert extrair_codigo_sob("SOB_A057349839") == "A057349839"
    assert extrair_codigo_sob("sob_xyz123") == "XYZ123"


def test_validar_sob():
    """Valida regras de formato da SOB."""
    assert validar_sob("A057349839") is True
    assert validar_sob("SOB_A057349839") is True
    assert validar_sob("123456") is True
    assert validar_sob("SOB-1234") is True

    # Inválidos
    assert validar_sob("") is False
    assert validar_sob("ab") is False  # Muito curto
    assert validar_sob("SOB_A*123") is False  # Caractere proibido
    assert validar_sob(None) is False


def test_criterio_03_criar_estrutura_pastas(tmp_path: Path):
    """TESTE 03 — Estrutura: SOB_A057349839/CROQUI"""
    pasta_sob = "SOB_A057349839"
    sob_root, croqui_dir = criar_estrutura_sob(tmp_path, pasta_sob)

    assert sob_root.exists()
    assert sob_root.is_dir()
    assert sob_root.name == pasta_sob
    assert croqui_dir.exists()
    assert croqui_dir.is_dir()
    assert croqui_dir.name == "CROQUI"
    assert croqui_dir.parent == sob_root


def test_criterio_09_protecao_pasta_existente(tmp_path: Path):
    """
    TESTE 09 — Pasta existente:
    Se a pasta já existir: NÃO SOBRESCREVER, NÃO APAGAR, NÃO MISTURAR CONTEÚDO.
    Interrompe e informa mensagem padronizada.
    """
    pasta_sob = "SOB_A057349839"
    pasta_existente = tmp_path / pasta_sob
    pasta_existente.mkdir()

    # Cria arquivo sentinela para provar que nada foi alterado ou apagado
    arquivo_sentinela = pasta_existente / "arquivo_original.txt"
    arquivo_sentinela.write_text("conteudo protegido intacto", encoding="utf-8")

    assert verificar_pasta_sob_existente(tmp_path, pasta_sob) is True

    with pytest.raises(SobDirectoryExistsError) as exc_info:
        criar_estrutura_sob(tmp_path, pasta_sob)

    msg = str(exc_info.value)
    assert "A pasta da SOB já existe." in msg
    assert "Operação interrompida para evitar sobrescrita ou mistura de projetos." in msg

    # Garante que o arquivo sentinela permanece 100% intacto
    assert arquivo_sentinela.exists()
    assert arquivo_sentinela.read_text(encoding="utf-8") == "conteudo protegido intacto"


def test_criterio_05_copiar_arquivo_base(tmp_path: Path):
    """
    TESTE 05 — Arquivo-base:
    Deve existir: SOB_A057349839/BASE_SOB_DESENHO.dwg
    O arquivo original prancha.dwg deve permanecer absolutamente intacto.
    """
    # Cria modelo fake de prancha.dwg com header AC1032
    modelos_dir = tmp_path / "modelos"
    modelos_dir.mkdir()
    prancha_orig = modelos_dir / "prancha.dwg"
    conteudo_fake = b"AC1032" + (b"\x00" * 200) + b"MODELO_ORIGINAL_PRANCHA"
    prancha_orig.write_bytes(conteudo_fake)

    # Cria pasta da SOB
    sob_root = tmp_path / "SOB_A057349839"
    sob_root.mkdir()

    # Executa a cópia
    destino = copiar_arquivo_base(prancha_orig, sob_root)

    assert destino.exists()
    assert destino.name == "BASE_SOB_DESENHO.dwg"
    assert destino.parent == sob_root
    assert destino.read_bytes() == conteudo_fake

    # Valida que o arquivo original está 100% intacto
    assert prancha_orig.exists()
    assert prancha_orig.read_bytes() == conteudo_fake

    # Valida integridade via função de validação de DWG
    assert validar_arquivo_dwg(destino) is True


def test_copiar_arquivo_base_inexistente(tmp_path: Path):
    """Valida erro se o arquivo-base original não for encontrado."""
    sob_root = tmp_path / "SOB_A057349839"
    sob_root.mkdir()

    inexistente = tmp_path / "modelos" / "inexistente.dwg"
    with pytest.raises(SobFileNotFoundError):
        copiar_arquivo_base(inexistente, sob_root)


def test_validar_arquivo_dwg_invalidos(tmp_path: Path):
    """Valida detecção de arquivos que não são DWG válidos."""
    # Arquivo vazio
    arq_vazio = tmp_path / "vazio.dwg"
    arq_vazio.write_bytes(b"")
    assert validar_arquivo_dwg(arq_vazio) is False

    # Arquivo pequeno / sem header AC10
    arq_txt = tmp_path / "fake.dwg"
    arq_txt.write_bytes(b"ISSO NAO E DWG" + (b"0" * 150))
    assert validar_arquivo_dwg(arq_txt) is False

    # Arquivo inexistente
    assert validar_arquivo_dwg(tmp_path / "nao_existe.dwg") is False


def test_sob_package_init():
    """Valida exportações do pacote sob/__init__.py."""
    import sob
    assert hasattr(sob, "normalizar_sob")
    assert hasattr(sob, "validar_sob")
    assert hasattr(sob, "criar_estrutura_sob")


def test_padronizacao_secao_0a_nomenclatura(tmp_path: Path):
    """
    Valida Matriz Oficial de Nomenclatura da Seção 0-A:
    SOB_ID, SOB_NAME, DESTINATION_ROOT, SOB_ROOT, CROQUI_DIR, BASE_DWG.
    """
    from sob_core import (
        obter_sob_id,
        obter_sob_name,
        derivar_caminhos_sob,
        NOME_PASTA_CROQUI,
        NOME_ARQUIVO_BASE_DWG,
    )

    # 1. SOB_ID: número puro, sem SOB_
    assert obter_sob_id("A057349839") == "A057349839"
    assert obter_sob_id("SOB_A057349839") == "A057349839"
    assert obter_sob_id("sob_sob_A057349839") == "A057349839"

    # 2. SOB_NAME: "SOB_" + SOB_ID (nunca SOB_SOB_...)
    assert obter_sob_name("A057349839") == "SOB_A057349839"
    assert obter_sob_name("SOB_A057349839") == "SOB_A057349839"

    # 3. Derivação Canônica Centralizada
    dest_root = tmp_path / "Projetos" / "ENEL"
    dest_root.mkdir(parents=True)

    caminhos = derivar_caminhos_sob("A057349839", dest_root)

    assert caminhos["SOB_ID"] == "A057349839"
    assert caminhos["SOB_NAME"] == "SOB_A057349839"
    assert caminhos["DESTINATION_ROOT"] == dest_root.resolve()
    assert caminhos["SOB_ROOT"] == (dest_root / "SOB_A057349839").resolve()
    assert caminhos["CROQUI_DIR"] == (dest_root / "SOB_A057349839" / NOME_PASTA_CROQUI).resolve()
    assert caminhos["BASE_DWG"] == (dest_root / "SOB_A057349839" / caminhos["NOME_BASE_DWG"]).resolve()
    assert caminhos["CROQUI_DIR"].name == "CROQUI"
    assert caminhos["BASE_DWG"].name == "PE_A057349839_DESENHO.dwg"

    # Teste com base informada explicitamente (ex: CF - Cabo Frio)
    caminhos_cf = derivar_caminhos_sob("A057349839", dest_root, base="CF")
    assert caminhos_cf["BASE_DWG"].name == "CF_A057349839_DESENHO.dwg"
    assert caminhos_cf["BASE_SIGLA"] == "CF"


def test_secao_14_validar_sob_name():
    """Valida regras estritas da Seção 14.4 para SOB_NAME."""
    from sob_core import validar_sob_name

    assert validar_sob_name("SOB_A057349839") is True
    assert validar_sob_name("SOB_1234567") is True

    # Separadores de diretório proibidos
    assert validar_sob_name("SOB_A0573/49839") is False
    assert validar_sob_name("SOB_A0573\\49839") is False

    # Caracteres proibidos em diretórios Windows
    assert validar_sob_name("SOB_A0573:49839") is False
    assert validar_sob_name("SOB_A0573*49839") is False
    assert validar_sob_name("SOB_A0573?49839") is False
    assert validar_sob_name("SOB_A0573<49839") is False
    assert validar_sob_name("SOB_A0573>49839") is False
    assert validar_sob_name("SOB_A0573|49839") is False

    # Proibição de repetição de prefixo SOB_SOB_
    assert validar_sob_name("SOB_SOB_A057349839") is False
    assert validar_sob_name("") is False


def test_secao_14_bloqueio_base_dwg_preexistente(tmp_path: Path):
    """Valida bloqueio se BASE_DWG já existir antes da cópia (Seção 14.10)."""
    from sob_core import copiar_arquivo_base, SobFileExistsError

    # Cria modelo fake
    prancha = tmp_path / "prancha.dwg"
    prancha.write_bytes(b"AC1032" + (b"\x00" * 150))

    sob_root = tmp_path / "SOB_A057349839"
    sob_root.mkdir()

    # Pre-cria BASE_SOB_DESENHO.dwg
    dwg_existente = sob_root / "BASE_SOB_DESENHO.dwg"
    dwg_existente.write_bytes(b"AC1032" + (b"\x00" * 150))

    with pytest.raises(SobFileExistsError) as exc_info:
        copiar_arquivo_base(prancha, sob_root)

    assert "[FALHA] O arquivo BASE_SOB_DESENHO.dwg já existe." in str(exc_info.value)


def test_secao_14_integridade_hash_falha(tmp_path: Path, monkeypatch):
    """Valida falha se houver divergência de hash pós-cópia (Seção 14.12)."""
    from sob_core import copiar_arquivo_base, SobIntegrityError
    import sob_core

    prancha = tmp_path / "prancha.dwg"
    prancha.write_bytes(b"AC1032" + (b"\x00" * 150))

    sob_root = tmp_path / "SOB_A057349839"
    sob_root.mkdir()

    # Simula alteração do hash na validação de destino
    contador = 0
    def fake_hash(p):
        nonlocal contador
        contador += 1
        return f"hash_fake_{contador}"

    monkeypatch.setattr(sob_core, "calcular_hash_arquivo", fake_hash)

    with pytest.raises(SobIntegrityError) as exc_info:
        copiar_arquivo_base(prancha, sob_root)

    assert "[FALHA] A cópia do arquivo-modelo não passou na validação de integridade." in str(exc_info.value)


def test_secao_14_preservacao_arquivo_modelo_original(tmp_path: Path):
    """Valida que o arquivo-modelo original permanece idêntico em bytes e hash (Seção 14.13)."""
    from sob_core import copiar_arquivo_base, calcular_hash_arquivo

    prancha = tmp_path / "prancha.dwg"
    conteudo_bin = b"AC1032" + (b"\x00" * 250) + b"INTEGRIDADE_ABSOLUTA"
    prancha.write_bytes(conteudo_bin)
    hash_esperado = calcular_hash_arquivo(prancha)

    sob_root = tmp_path / "SOB_A057349839"
    sob_root.mkdir()

    copiar_arquivo_base(prancha, sob_root)

    assert prancha.exists()
    assert prancha.read_bytes() == conteudo_bin
    assert calcular_hash_arquivo(prancha) == hash_esperado


def test_secao_14_remover_estrutura_incompleta(tmp_path: Path):
    """Valida limpeza controlada de estrutura incompleta (Seção 14.8)."""
    from sob_core import remover_estrutura_incompleta

    # 1. Estrutura válida da SOB
    sob_root = tmp_path / "SOB_A057349839"
    sob_root.mkdir()
    (sob_root / "CROQUI").mkdir()
    (sob_root / "CROQUI" / "arq.txt").write_text("parcial")

    removido = remover_estrutura_incompleta(sob_root)
    assert removido is True
    assert not sob_root.exists()

    # 2. Pasta não SOB não pode ser removida por segurança
    pasta_terceiro = tmp_path / "ProjetosImportantes"
    pasta_terceiro.mkdir()
    (pasta_terceiro / "segredo.txt").write_text("nao toque")

    removido_terceiro = remover_estrutura_incompleta(pasta_terceiro)
    assert removido_terceiro is False
    assert pasta_terceiro.exists()

