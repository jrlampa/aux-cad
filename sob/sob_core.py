# -*- coding: utf-8 -*-
"""
Módulo de Domínio do Projeto SOB (sob_core.py).
Responsabilidade única: Validação de entradas, normalização de nomes,
gestão segura de diretórios e operações com arquivos DWG locais.
"""

from pathlib import Path
import re
import shutil
from typing import Tuple, Union


class SobValidationError(ValueError):
    """Exceção para erros de validação de número ou formato da SOB."""
    pass


class SobDirectoryExistsError(FileExistsError):
    """Exceção levantada quando a pasta da SOB já existe no destino selecionado."""
    pass


class SobFileNotFoundError(FileNotFoundError):
    """Exceção levantada quando arquivos essenciais (como arquivo-base) não existem."""
    pass


def normalizar_sob(sob_raw: str) -> str:
    """
    Normaliza o número da SOB fornecido pelo usuário.
    Garante o prefixo 'SOB_' sem duplicações.
    
    Exemplos:
        'A057349839'      -> 'SOB_A057349839'
        'SOB_A057349839'  -> 'SOB_A057349839'
        'sob_a057349839'  -> 'SOB_A057349839'
        '  A057349839  '  -> 'SOB_A057349839'
    """
    if not sob_raw or not isinstance(sob_raw, str):
        raise SobValidationError("O número da SOB não pode ser vazio.")

    limpo = sob_raw.strip().upper()
    if not limpo:
        raise SobValidationError("O número da SOB não pode ser vazio.")

    # Remove repetições acidentais de SOB_ no início
    while limpo.startswith("SOB_"):
        limpo = limpo[4:].strip()

    if not limpo:
        raise SobValidationError("Número da SOB inválido após remoção do prefixo.")

    return f"SOB_{limpo}"


# Matriz Oficial de Nomenclatura (Seção 0-A)
NOME_PASTA_CROQUI = "CROQUI"
NOME_ARQUIVO_BASE_DWG = "BASE_SOB_DESENHO.dwg"


def obter_sob_id(sob_raw: str) -> str:
    """
    Retorna exclusivamente o SOB_ID (número puro informado pelo usuário, sem prefixo 'SOB_').
    Utilizado para pesquisa no SharePoint, identificação interna, validações e logs.
    
    Exemplos:
        'A057349839'     -> 'A057349839'
        'SOB_A057349839' -> 'A057349839'
    """
    normalizada = normalizar_sob(sob_raw)
    return normalizada[4:]


def obter_sob_name(sob_raw: str) -> str:
    """
    Retorna o SOB_NAME (nome padronizado da pasta local: 'SOB_' + SOB_ID).
    Garante que nunca seja gerado 'SOB_SOB_...'.
    
    Exemplos:
        'A057349839'     -> 'SOB_A057349839'
        'SOB_A057349839' -> 'SOB_A057349839'
    """
    return normalizar_sob(sob_raw)


def extrair_codigo_sob(sob_raw: str) -> str:
    """Alias para obter_sob_id (compatibilidade retroativa)."""
    return obter_sob_id(sob_raw)


def derivar_caminhos_sob(sob_raw: str, destination_root: Union[str, Path]) -> dict:
    """
    Constrói de forma centralizada e canônica a cadeia completa de caminhos (Seção 0-A):
    SOB_ID -> SOB_NAME -> DESTINATION_ROOT -> SOB_ROOT -> CROQUI_DIR -> BASE_DWG
    """
    sob_id = obter_sob_id(sob_raw)
    sob_name = f"SOB_{sob_id}"
    dest_root = Path(destination_root).resolve()
    sob_root = dest_root / sob_name
    croqui_dir = sob_root / NOME_PASTA_CROQUI
    base_dwg = sob_root / NOME_ARQUIVO_BASE_DWG

    return {
        "SOB_ID": sob_id,
        "SOB_NAME": sob_name,
        "DESTINATION_ROOT": dest_root,
        "SOB_ROOT": sob_root,
        "CROQUI_DIR": croqui_dir,
        "BASE_DWG": base_dwg,
    }


def validar_sob(sob_raw: str) -> bool:
    """
    Valida se a SOB possui formato alfanumérico e tamanho razoável.
    Retorna True se válida, False se inválida.
    """
    if not sob_raw or not isinstance(sob_raw, str):
        return False

    texto = sob_raw.strip().upper()
    if not texto:
        return False

    # Deve conter apenas letras, dígitos, sublinhados ou hífens
    # Código deve ter entre 3 e 30 caracteres
    padrao = r"^(SOB_)?[A-Z0-9_\-]+$"
    if not re.match(padrao, texto):
        return False

    codigo = texto[4:] if texto.startswith("SOB_") else texto
    return 3 <= len(codigo) <= 30


def verificar_pasta_sob_existente(destino: Union[str, Path], pasta_sob: str) -> bool:
    """
    Verifica se a pasta da SOB já existe no diretório selecionado.
    """
    caminho_destino = Path(destino) / pasta_sob
    return caminho_destino.exists()


def criar_estrutura_sob(
    destino: Union[str, Path],
    pasta_sob: str,
) -> Tuple[Path, Path]:
    """
    Cria a estrutura de pastas do projeto:
    [DESTINO]/[pasta_sob]/
    └── CROQUI/
    
    Retorna uma tupla (SOB_ROOT, CROQUI_DIR).
    Lança SobDirectoryExistsError se a pasta raiz da SOB já existir.
    """
    destino_path = Path(destino).resolve()
    if not destino_path.exists():
        raise SobFileNotFoundError(f"Diretório de destino inexistente: {destino_path}")

    sob_root = destino_path / pasta_sob
    if sob_root.exists():
        raise SobDirectoryExistsError(
            "A pasta da SOB já existe no local selecionado.\n"
            "Nenhum arquivo foi sobrescrito."
        )

    croqui_dir = sob_root / "CROQUI"

    # Criação da estrutura
    sob_root.mkdir(parents=True, exist_ok=False)
    croqui_dir.mkdir(parents=True, exist_ok=False)

    return sob_root, croqui_dir


def copiar_arquivo_base(
    origem_base: Union[str, Path],
    sob_root: Union[str, Path],
    nome_destino: str = "BASE_SOB_DESENHO.dwg",
) -> Path:
    """
    Copia o arquivo-base DWG para a raiz da SOB.
    O arquivo original permanece absolutamente intacto.
    
    Retorna o caminho absoluto do arquivo copiado.
    """
    origem_path = Path(origem_base).resolve()
    if not origem_path.is_file():
        raise SobFileNotFoundError(
            f"Arquivo-base não encontrado no caminho: {origem_path}"
        )

    sob_root_path = Path(sob_root).resolve()
    if not sob_root_path.is_dir():
        raise SobFileNotFoundError(
            f"Diretório da SOB inexistente para cópia: {sob_root_path}"
        )

    destino_arquivo = sob_root_path / nome_destino

    # Cópia segura preservando metadados
    shutil.copy2(origem_path, destino_arquivo)

    if not destino_arquivo.is_file() or destino_arquivo.stat().st_size == 0:
        raise IOError(f"Falha na validação pós-cópia do arquivo {destino_arquivo}")

    return destino_arquivo


def validar_arquivo_dwg(caminho_dwg: Union[str, Path]) -> bool:
    """
    Valida a existência e integridade básica de um arquivo DWG.
    Verifica se o arquivo existe, possui tamanho > 0 e cabeçalho DWG padrão (AC10...).
    """
    p = Path(caminho_dwg).resolve()
    if not p.is_file():
        return False

    if p.stat().st_size < 100:
        return False

    try:
        with open(p, "rb") as f:
            header = f.read(6)
            # Cabeçalhos válidos do AutoCAD começam com AC10 (ex: AC1032, AC1027, etc.)
            return header.startswith(b"AC10")
    except Exception:
        return False
