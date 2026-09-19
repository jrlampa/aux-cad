"""
Módulo de Idempotência e Repetição Segura da Operação SOB (Seção 19).

Garante que a mesma operação possa ser repetida após conclusão, falha na Fase B,
rollback completo, rollback parcial ou interrupção inesperada, sem jamais duplicar,
sobrescrever, mesclar ou corromper arquivos de execuções anteriores.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger("SOB.Idempotencia")

NOME_ARQUIVO_MANIFESTO = ".sob_state.json"


def gerar_run_id() -> str:
    """
    Gera um identificador técnico único da execução (Seção 19.14).
    Não substitui SOB_ID nem altera nomes canônicos de arquivos/diretórios.
    """
    return f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def gravar_manifesto_execucao(sob_root: Union[str, Path], dados: Dict[str, Any]) -> bool:
    """
    Persiste atomicamente o manifesto de estado da execução em .sob_state.json (Seção 19.5 & 19.15).
    """
    p_root = Path(sob_root).resolve()
    if not p_root.exists() or not p_root.is_dir():
        return False

    manifesto_path = p_root / NOME_ARQUIVO_MANIFESTO
    manifesto_tmp = p_root / f"{NOME_ARQUIVO_MANIFESTO}.tmp"

    try:
        conteudo = json.dumps(dados, indent=2, ensure_ascii=False)
        manifesto_tmp.write_text(conteudo, encoding="utf-8")
        manifesto_tmp.replace(manifesto_path)
        return True
    except Exception as e:
        logger.warning(f"Não foi possível gravar o manifesto de estado: {e}")
        if manifesto_tmp.exists():
            try:
                manifesto_tmp.unlink()
            except Exception:
                pass
        return False


def ler_manifesto_execucao(sob_root: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """
    Lê o manifesto de estado persistido da execução anterior em .sob_state.json (Seção 19.5).
    """
    p_root = Path(sob_root).resolve()
    manifesto_path = p_root / NOME_ARQUIVO_MANIFESTO
    if not manifesto_path.exists() or not manifesto_path.is_file():
        return None

    try:
        texto = manifesto_path.read_text(encoding="utf-8")
        return json.loads(texto)
    except Exception as e:
        logger.warning(f"Erro ao ler manifesto em {manifesto_path}: {e}")
        return None


def classificar_sob_root(
    destination_root: Union[str, Path],
    sob_name: str,
    nome_dwg_base: str = "BASE_SOB_DESENHO.dwg",
) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    """
    Analisa e classifica o estado de SOB_ROOT conforme a Seção 19.2 a 19.6.

    Retorna:
        Tuple[classificacao, mensagem_explicativa, manifesto]
    """
    dest_path = Path(destination_root).resolve()
    sob_root = dest_path / sob_name

    if not sob_root.exists():
        return ("NAO_EXISTE", "Diretório SOB_ROOT não existe. Pronto para nova execução.", None)

    manifesto = ler_manifesto_execucao(sob_root)

    # Caso 1: Pasta existe mas NÃO possui manifesto da execução
    if not manifesto:
        return (
            "EXISTE_E_NÃO_É_DA_EXECUÇÃO",
            f"[FALHA] A pasta da SOB já existe em {sob_root}.\n"
            "Operação interrompida para evitar sobrescrita ou mistura de projetos.",
            None,
        )

    status_manifesto = manifesto.get("status")
    rollback_manifesto = manifesto.get("rollback")

    # Caso 2: Execução anterior comprovadamente concluída (Seção 19.7)
    if status_manifesto == "CONCLUÍDO":
        base_dwg = sob_root / nome_dwg_base
        croqui_dir = sob_root / "CROQUI"

        # Confere se os arquivos fundamentais continuam íntegros no disco
        if base_dwg.is_file() and croqui_dir.is_dir():
            return (
                "EXISTE_E_ESTÁ_CONCLUÍDA",
                "[INFO] A SOB já possui uma execução concluída neste destino.",
                manifesto,
            )
        else:
            return (
                "EXISTE_EM_ESTADO_INCONSISTENTE",
                "[FALHA] Existe uma execução anterior em estado incompleto.\n"
                "A operação não será repetida automaticamente para evitar mistura ou sobrescrita de arquivos.",
                manifesto,
            )

    # Caso 3: Execução anterior terminou em ROLLBACK_PARCIAL (Seção 19.9)
    if rollback_manifesto == "ROLLBACK_PARCIAL":
        return (
            "EXISTE_E_ESTÁ_INCOMPLETA",
            "[FALHA] Existe uma execução anterior em estado incompleto.\n"
            "A operação não será repetida automaticamente para evitar mistura ou sobrescrita de arquivos.",
            manifesto,
        )

    # Caso 4: Execução anterior interrompida ou com status BLOQUEADO (Seção 19.10)
    return (
        "EXISTE_E_ESTÁ_INCOMPLETA",
        "[FALHA] Existe uma execução anterior em estado incompleto.\n"
        "A operação não será repetida automaticamente para evitar mistura ou sobrescrita de arquivos.",
        manifesto,
    )


def verificar_arquivo_download_idempotente(
    arquivo_local: Union[str, Path],
    tamanho_esperado: Optional[int] = None,
    hash_esperado: Optional[str] = None,
) -> str:
    """
    Verifica se um arquivo a ser baixado já existe localmente e se é idêntico ou divergente (Seção 19.11).

    Retorna:
        "NAO_EXISTE": o arquivo ainda não existe no destino local.
        "IDENTICO": o arquivo existe com mesmo tamanho e hash compatíveis.
        "DIVERGENTE": o arquivo existe com conteúdo conflitante.
    """
    p = Path(arquivo_local).resolve()
    if not p.exists() or not p.is_file():
        return "NAO_EXISTE"

    # Verificação de tamanho
    if tamanho_esperado is not None and p.stat().st_size != tamanho_esperado:
        return "DIVERGENTE"

    # Verificação de hash SHA-256 se fornecido
    if hash_esperado:
        import hashlib
        sha = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        if sha.hexdigest().lower() != hash_esperado.lower():
            return "DIVERGENTE"

    return "IDENTICO"
