# -*- coding: utf-8 -*-
"""
Módulo de Domínio do Projeto SOB (sob_core.py).
Responsabilidade única: Validação de entradas, normalização de nomes,
gestão segura de diretórios e operações com arquivos DWG locais.
"""

from pathlib import Path
import re
import shutil
from typing import Optional, Tuple, Union


class SobValidationError(ValueError):
    """Exceção para erros de validação de número ou formato da SOB."""
    pass


class SobDirectoryExistsError(FileExistsError):
    """Exceção levantada quando a pasta da SOB já existe no destino selecionado."""
    pass


class SobFileExistsError(FileExistsError):
    """Exceção levantada quando o arquivo BASE_DWG já existe no destino."""
    pass


class SobFileNotFoundError(FileNotFoundError):
    """Exceção levantada quando arquivos essenciais (como arquivo-base) não existem."""
    pass


class SobPermissionError(PermissionError):
    """Exceção levantada quando não há permissão para criar diretórios."""
    pass


class SobIntegrityError(IOError):
    """Exceção levantada quando a cópia ou integridade do DWG falha."""
    pass


def normalizar_sob(sob_raw: str) -> str:
    """
    Normaliza o número da SOB fornecido pelo usuário.
    Garante o prefixo 'SOB_' sem duplicações.
    """
    if not sob_raw or not isinstance(sob_raw, str):
        raise SobValidationError("[FALHA] SOB não informada.")

    limpo = sob_raw.strip().upper()
    if not limpo:
        raise SobValidationError("[FALHA] SOB não informada.")

    # Remove repetições acidentais de SOB_ no início
    while limpo.startswith("SOB_"):
        limpo = limpo[4:].strip()

    if not limpo:
        raise SobValidationError(
            "[FALHA] Número da SOB inválido.\nInforme uma SOB válida."
        )

    return f"SOB_{limpo}"


# Matriz Oficial de Nomenclatura (Seção 0-A)
NOME_PASTA_CROQUI = "CROQUI"
NOME_ARQUIVO_BASE_DWG = "BASE_SOB_DESENHO.dwg"
CAMINHO_BASE_TEMPLATE_PADRAO = (
    Path(__file__).resolve().parent.parent / "modelos" / "prancha.dwg"
)


def obter_sob_id(sob_raw: str) -> str:
    """
    Retorna exclusivamente o SOB_ID (número puro informado pelo usuário, sem prefixo 'SOB_').
    Utilizado para pesquisa no SharePoint, identificação interna, validações e logs.
    """
    normalizada = normalizar_sob(sob_raw)
    sob_id = normalizada[4:]
    if not validar_sob_id(sob_id):
        raise SobValidationError(
            "[FALHA] Número da SOB inválido.\nInforme uma SOB válida."
        )
    return sob_id


def validar_sob_id(sob_id: str) -> bool:
    """
    Valida se o SOB_ID puro possui formato alfanumérico e tamanho razoável.
    """
    if not sob_id or not isinstance(sob_id, str):
        return False
    texto = sob_id.strip().upper()
    if not texto:
        return False
    # SOB_ID não pode conter o prefixo SOB_
    if texto.startswith("SOB_"):
        return False
    padrao = r"^[A-Z0-9_\-]+$"
    if not re.match(padrao, texto):
        return False
    return 3 <= len(texto) <= 30


def validar_sob_name(sob_name: str) -> bool:
    """
    Valida as restrições da Seção 14.4 para SOB_NAME:
    - SOB_NAME != vazio
    - Não contém separadores de diretório (/ ou \\)
    - Não contém caracteres inválidos para pasta no SO (< > : " / \\ | ? *)
    - Não contém outro prefixo SOB_ (ex: SOB_SOB_...)
    """
    if not sob_name or not isinstance(sob_name, str):
        return False
    if not sob_name.startswith("SOB_"):
        return False
    # Verifica duplicação de prefixo
    if sob_name.startswith("SOB_SOB_"):
        return False
    # Verifica separadores e caracteres proibidos
    caracteres_proibidos = set('<>:"/\\|?*')
    if any(c in caracteres_proibidos for c in sob_name):
        return False
    # Código após SOB_ deve ser válido
    sob_id = sob_name[4:]
    return validar_sob_id(sob_id)


def obter_sob_name(sob_raw: str) -> str:
    """
    Retorna o SOB_NAME (nome padronizado da pasta local: 'SOB_' + SOB_ID).
    Garante que nunca seja gerado 'SOB_SOB_...'.
    """
    sob_id = obter_sob_id(sob_raw)
    sob_name = f"SOB_{sob_id}"
    if not validar_sob_name(sob_name):
        raise SobValidationError("[FALHA] Nome da pasta da SOB inválido.")
    return sob_name


def extrair_codigo_sob(sob_raw: str) -> str:
    """Alias para obter_sob_id (compatibilidade retroativa)."""
    return obter_sob_id(sob_raw)


def validar_sob(sob_raw: str) -> bool:
    """
    Valida se a SOB possui formato alfanumérico e tamanho razoável.
    Retorna True se válida, False se inválida.
    """
    try:
        sob_id = obter_sob_id(sob_raw)
        return validar_sob_id(sob_id)
    except Exception:
        return False


def derivar_caminhos_sob(
    sob_raw: str,
    destination_root: Union[str, Path],
    base_template: Optional[Union[str, Path]] = None,
) -> dict:
    """
    Constrói de forma centralizada e canônica a cadeia completa de caminhos (Seção 0-A & Seção 14):
    SOB_ID -> SOB_NAME -> DESTINATION_ROOT -> SOB_ROOT -> CROQUI_DIR -> BASE_DWG
    """
    sob_id = obter_sob_id(sob_raw)
    sob_name = obter_sob_name(sob_raw)

    if not destination_root or not str(destination_root).strip():
        raise SobValidationError("[FALHA] Diretório de destino inválido.")

    dest_root = Path(destination_root).resolve()
    if not dest_root.is_dir():
        raise SobValidationError("[FALHA] Diretório de destino inválido.")

    sob_root = dest_root / sob_name

    # Proteção de Path Traversal: sob_root deve estar estritamente contido em dest_root
    try:
        sob_root.relative_to(dest_root)
    except ValueError:
        raise SobValidationError("[FALHA] Nome da pasta da SOB inválido.")

    croqui_dir = sob_root / NOME_PASTA_CROQUI
    base_template_path = Path(base_template).resolve() if base_template else CAMINHO_BASE_TEMPLATE_PADRAO
    base_dwg = sob_root / NOME_ARQUIVO_BASE_DWG

    return {
        "SOB_ID": sob_id,
        "SOB_NAME": sob_name,
        "DESTINATION_ROOT": dest_root,
        "SOB_ROOT": sob_root,
        "CROQUI_DIR": croqui_dir,
        "BASE_TEMPLATE": base_template_path,
        "BASE_DWG": base_dwg,
    }


def verificar_pasta_sob_existente(destino: Union[str, Path], pasta_sob: str) -> bool:
    """
    Verifica se a pasta da SOB já existe no diretório selecionado.
    """
    caminho_destino = Path(destino).resolve() / pasta_sob
    return caminho_destino.exists()


def validar_permissao_criacao(destino: Union[str, Path]) -> bool:
    """
    Valida a permissão de criação no diretório de destino (Seção 17, Etapa 07).
    """
    import os
    p = Path(destino).resolve()
    if not p.exists() or not p.is_dir():
        return False
    return os.access(p, os.W_OK)


def criar_estrutura_sob(
    destino: Union[str, Path],
    pasta_sob: str,
) -> Tuple[Path, Path]:
    """
    Cria a estrutura de pastas do projeto de forma sequencial e controlada (Seção 14.6 & 14.7 & 17):
    1. Validar permissão de escrita em destino
    2. SOB_ROOT -> verifica fisicamente
    3. CROQUI_DIR -> verifica fisicamente
    
    Retorna uma tupla (SOB_ROOT, CROQUI_DIR).
    """
    destino_path = Path(destino).resolve()
    if not destino_path.exists() or not destino_path.is_dir():
        raise SobValidationError(f"[FALHA] Diretório de destino inválido: {destino_path}")

    if not validar_permissao_criacao(destino_path):
        raise SobPermissionError(
            "[FALHA] O diretório selecionado não permite a criação da estrutura da SOB."
        )

    sob_root = destino_path / pasta_sob
    if sob_root.exists():
        raise SobDirectoryExistsError(
            "[FALHA] A pasta da SOB já existe.\n"
            "Operação interrompida para evitar sobrescrita ou mistura de projetos."
        )

    croqui_dir = sob_root / NOME_PASTA_CROQUI

    # Criação controlada e verificação física (Etapas B01 e B02)
    try:
        sob_root.mkdir(parents=False, exist_ok=False)
    except Exception as e:
        raise IOError(f"[FALHA] Não foi possível criar SOB_ROOT: {sob_root} ({e})")

    if not sob_root.is_dir():
        raise IOError(f"[FALHA] Não foi possível criar SOB_ROOT: {sob_root}")

    try:
        croqui_dir.mkdir(parents=False, exist_ok=False)
    except Exception as e:
        # Rollback seguro de sob_root caso croqui_dir falhe na criação imediata
        try:
            sob_root.rmdir()
        except Exception:
            pass
        raise IOError(f"[FALHA] Não foi possível criar CROQUI_DIR: {croqui_dir} ({e})")

    if not croqui_dir.is_dir():
        try:
            sob_root.rmdir()
        except Exception:
            pass
        raise IOError(f"[FALHA] Não foi possível criar CROQUI_DIR: {croqui_dir}")

    return sob_root, croqui_dir


def calcular_hash_arquivo(caminho: Union[str, Path]) -> str:
    """
    Calcula o hash SHA-256 de um arquivo para conferência de integridade binária.
    """
    import hashlib
    p = Path(caminho).resolve()
    sha256 = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def copiar_arquivo_base(
    origem_base: Union[str, Path],
    sob_root: Union[str, Path],
    nome_destino: str = NOME_ARQUIVO_BASE_DWG,
) -> Path:
    """
    Copia o arquivo-base DWG para a raiz da SOB com rigorosas validações de integridade
    (Seções 14.9, 14.10, 14.11, 14.12, 14.13 e 17):
    1. Validar existência, legibilidade e formato DWG de BASE_TEMPLATE
    2. Calcular hash de integridade inicial de BASE_TEMPLATE
    3. Validar que BASE_DWG NÃO existe antes da cópia
    4. Executar cópia preservando metadados
    5. Validar existência, tamanho > 0 e integridade de hash de BASE_DWG
    6. Validar que BASE_TEMPLATE permanece intacto (mesmo hash inicial)
    """
    import os
    origem_path = Path(origem_base).resolve()
    if not origem_path.is_file() or not os.access(origem_path, os.R_OK):
        raise SobFileNotFoundError(
            f"[FALHA] Arquivo-modelo prancha.dwg não encontrado ou inacessível: {origem_path}"
        )

    if not validar_arquivo_dwg(origem_path):
        raise SobIntegrityError(
            f"[FALHA] Arquivo-modelo prancha.dwg corrompido ou formato DWG inválido: {origem_path}"
        )

    hash_origem_antes = calcular_hash_arquivo(origem_path)

    sob_root_path = Path(sob_root).resolve()
    if not sob_root_path.is_dir():
        raise SobFileNotFoundError(
            f"[FALHA] Diretório da SOB inexistente para cópia: {sob_root_path}"
        )

    destino_arquivo = sob_root_path / nome_destino

    # Seção 14.10: BASE_DWG NÃO pode existir antes da cópia
    if destino_arquivo.exists():
        raise SobFileExistsError(
            f"[FALHA] O arquivo {nome_destino} já existe."
        )

    # Cópia segura preservando metadados
    try:
        shutil.copy2(origem_path, destino_arquivo)
    except Exception as e:
        raise IOError(f"[FALHA] Não foi possível criar {nome_destino}: {e}")

    # Seção 14.11 e 14.12: Validações pós-cópia e integridade de hash
    if not destino_arquivo.is_file() or destino_arquivo.stat().st_size == 0:
        raise IOError(f"[FALHA] Não foi possível criar {nome_destino}.")

    hash_destino = calcular_hash_arquivo(destino_arquivo)
    if hash_destino != hash_origem_antes:
        try:
            destino_arquivo.unlink(missing_ok=True)
        except Exception:
            pass
        raise SobIntegrityError(
            "[FALHA] A cópia do arquivo-modelo não passou na validação de integridade."
        )

    # Seção 14.13: Validação do arquivo-modelo original após a cópia
    if not origem_path.is_file():
        raise SobIntegrityError(
            "[FALHA CRÍTICA] O arquivo-modelo original foi alterado."
        )

    hash_origem_depois = calcular_hash_arquivo(origem_path)
    if hash_origem_depois != hash_origem_antes:
        raise SobIntegrityError(
            "[FALHA CRÍTICA] O arquivo-modelo original foi alterado."
        )

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


def remover_estrutura_incompleta(sob_root: Union[str, Path]) -> bool:
    """
    Realiza a limpeza controlada de uma estrutura criada nesta execução que falhou (Seções 14.8 e 18).
    Não realiza exclusão recursiva indiscriminada (proibição de rmtree genérico conforme Seção 18.1).
    Remove apenas os arquivos derivados do processo e diretórios esvaziados pertencentes à SOB.
    """
    p = Path(sob_root).resolve()
    if not p.exists() or not p.is_dir():
        return False

    if not p.name.startswith("SOB_"):
        return False

    try:
        # Ordem inversa de limpeza segura (Seção 18.10)
        base_dwg = p / NOME_ARQUIVO_BASE_DWG
        if base_dwg.is_file():
            try:
                base_dwg.unlink()
            except Exception:
                pass

        croqui_dir = p / NOME_PASTA_CROQUI
        if croqui_dir.is_dir():
            for item in list(croqui_dir.iterdir()):
                if item.is_file():
                    try:
                        item.unlink()
                    except Exception:
                        pass
            try:
                croqui_dir.rmdir()
            except Exception:
                pass

        # Remove manifesto de estado se presente
        for manifest_file in (p / ".sob_state.json", p / ".sob_state.json.tmp"):
            if manifest_file.is_file():
                try:
                    manifest_file.unlink()
                except Exception:
                    pass

        try:
            p.rmdir()
        except Exception:
            return False

        return not p.exists()
    except Exception:
        return False


def sanitizar_mensagem(texto: str, segredos: Optional[Union[list, Tuple]] = None) -> str:
    """
    Remove segredos e credenciais de mensagens ou logs.
    Garante que senhas nunca apareçam em logs ou telas.
    """
    if not texto:
        return ""

    resultado = texto
    if segredos:
        for s in segredos:
            if s and len(s) >= 3:
                resultado = resultado.replace(s, "******")

    # Sanitização extra de padrões comuns
    resultado = re.sub(r'(password|senha|passwd|pwd)\s*=\s*([^\s&]+)', r'\1=******', resultado, flags=re.IGNORECASE)
    return resultado

