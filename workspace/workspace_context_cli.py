# -*- coding: utf-8 -*-
"""
Interface Headless de Contexto Operacional do Workspace para OXCAD.
Responsabilidade única: Receber o caminho do DWG ou diretório, consultar
o ProjectWorkspace e o WorkspaceScanner, detectar eventuais inconsistências
e retornar estritamente um contrato JSON serializável.

NÃO contém Tkinter.
NÃO contém execução de especialistas ou ações de engenharia.
"""

import argparse
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union
import warnings
from datetime import datetime, timezone

# Suprime warnings de pacotes terceiros (ex: urllib3/requests) para manter stdout 100% JSON limpo
warnings.filterwarnings("ignore")

# Garante a resolução correta dos módulos do projeto
_curr_dir = Path(__file__).resolve().parent
_root_dir = _curr_dir.parent
for _d in [str(_curr_dir), str(_root_dir)]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_scanner import WorkspaceScanner
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_time import (
    carregar_tempo_projeto,
    iniciar_ou_retomar_tempo,
    pausar_tempo,
    concluir_tempo,
    reabrir_tempo,
    inicializar_tempo_projeto,
    tratar_interrupcao_se_necessario,
    atualizar_heartbeat_tempo,
)
import time
import uuid
import zipfile
from common.logging_config import get_logger, registrar_evento_obrigatorio

logger = get_logger("oxcad.workspace.cli")


def _obter_metadados_locais(root_dir: Path, sob_id: str) -> Dict[str, str]:
    """
    Recupera metadados (Município, Bairro, Endereço) de arquivos conhecidos
    da SOB caso existam, retornando '-' para campos inexistentes.
    Nunca inventa dados.
    """
    meta = {
        "municipio": "-",
        "bairro": "-",
        "endereco": "-",
    }

    if not root_dir.exists() or not root_dir.is_dir():
        return meta

    # 1. Tenta ler de .sob_state.json (manifesto de preparação da SOB)
    manifesto_path = root_dir / ".sob_state.json"
    if manifesto_path.exists() and manifesto_path.is_file():
        try:
            dados = json.loads(manifesto_path.read_text(encoding="utf-8"))
            if dados.get("municipio"):
                meta["municipio"] = str(dados["municipio"]).strip().upper()
            if dados.get("bairro"):
                meta["bairro"] = str(dados["bairro"]).strip().upper()
            if dados.get("endereco"):
                meta["endereco"] = str(dados["endereco"]).strip()
        except Exception:
            pass

    # 2. Tenta ler de preferências ambientais se município estiver vazio
    if meta["municipio"] == "-":
        pref_amb = root_dir / "preferencias_ambiental.json"
        if pref_amb.exists() and pref_amb.is_file():
            try:
                dados_amb = json.loads(pref_amb.read_text(encoding="utf-8"))
                if dados_amb.get("municipio"):
                    meta["municipio"] = str(dados_amb["municipio"]).strip().upper()
            except Exception:
                pass

    return meta


def _normalizar_project_scope(sob_id: Optional[str]) -> Optional[str]:
    if not isinstance(sob_id, str):
        return None
    candidato = sob_id.strip().upper()
    if candidato.startswith("SOB_") or not re.fullmatch(
        r"[A-Z0-9_-]{3,30}", candidato
    ):
        return None
    return candidato


def _autocad_parent_verified(acad_pid: Optional[int]) -> bool:
    if sys.platform != "win32" or acad_pid != os.getppid():
        return False
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.QueryFullProcessImageNameW.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x1000, 0, acad_pid)
        if not handle:
            return False
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = ctypes.c_ulong(len(buffer))
            return bool(kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)
            )) and Path(buffer.value).name.casefold() == "acad.exe"
        finally:
            kernel32.CloseHandle(handle)
    except (OSError, AttributeError, ValueError):
        return False


def _verificar_envelope_host(
    payload: Optional[Dict[str, Any]], dwg_path: Optional[str],
    sob_id: Optional[str], dwg_identity: Optional[str],
    execution_id: Optional[str], correlation_id: Optional[str],
    acad_pid: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    if not isinstance(payload, dict) or not _autocad_parent_verified(acad_pid):
        return None, "DWG_CONTEXT_NOT_VERIFIED"
    required = ("sob_id", "dwg_path", "dwg_identity", "context_generation")
    if (payload.get("contract_version") != 1
            or payload.get("project_scope_status") != "Bound"
            or any(not payload.get(name) for name in required)
            or type(payload.get("context_generation")) is not int
            or payload["context_generation"] < 1):
        return None, "DWG_CONTEXT_NOT_VERIFIED"
    host_sob = _normalizar_project_scope(payload["sob_id"])
    host_dwg = payload["dwg_path"]
    host_fingerprint = payload["dwg_identity"]
    if (host_sob is None or not isinstance(host_dwg, str)
            or not isinstance(host_fingerprint, str)
            or not host_fingerprint.strip()):
        return None, "DWG_CONTEXT_NOT_VERIFIED"
    if (sob_id is not None and sob_id != host_sob
            or dwg_path is not None and Path(dwg_path).resolve() != Path(host_dwg).resolve()
            or dwg_identity is not None and dwg_identity.casefold() != host_fingerprint.casefold()
            or execution_id is not None and execution_id != payload.get("execution_id")
            or correlation_id is not None and correlation_id != payload.get("correlation_id")):
        return None, "DWG_CONTEXT_INCOMPATIBLE"
    return {
        "sob_id": host_sob, "dwg_path": str(Path(host_dwg).resolve()),
        "dwg_identity": host_fingerprint,
        "execution_id": payload.get("execution_id"),
        "correlation_id": payload.get("correlation_id"),
        "context_generation": payload["context_generation"],
    }, "CONTEXTO_VERIFICADO"


def _resolver_project_scope(
    root_dir: Path,
    dwg_path: Optional[str],
    sob_id_vinculado: Optional[str],
    require_existing_dwg: bool = True,
) -> Dict[str, Any]:
    """Valida a identidade persistida contra o manifesto e os DWGs locais."""
    if sob_id_vinculado is None or (
        isinstance(sob_id_vinculado, str) and not sob_id_vinculado.strip()
    ):
        return {
            "status": "Unbound",
            "sob_id": None,
            "candidates": [],
            "error": "PROJECT_SCOPE_UNBOUND",
        }
    if not isinstance(sob_id_vinculado, str):
        return {
            "status": "Invalid",
            "sob_id": None,
            "candidates": [],
            "error": "INVALID_SOB_ID",
        }

    sob_id = _normalizar_project_scope(sob_id_vinculado)
    if not sob_id:
        return {
            "status": "Invalid",
            "sob_id": None,
            "candidates": [],
            "error": "INVALID_SOB_ID",
        }

    manifesto_path = root_dir / ".sob_state.json"
    if not manifesto_path.is_file():
        return {
            "status": "Unbound",
            "sob_id": sob_id,
            "candidates": [],
            "error": "PROJECT_SCOPE_UNVERIFIABLE",
        }

    try:
        manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {
            "status": "Invalid",
            "sob_id": sob_id,
            "candidates": [],
            "error": "PROJECT_MANIFEST_INVALID",
        }

    if not isinstance(manifesto, dict):
        return {
            "status": "Invalid",
            "sob_id": sob_id,
            "candidates": [],
            "error": "PROJECT_MANIFEST_INVALID",
        }

    sob_manifesto = _normalizar_project_scope(manifesto.get("sob_id"))
    if not sob_manifesto:
        return {
            "status": "Invalid",
            "sob_id": sob_id,
            "candidates": [],
            "error": "MANIFEST_SOB_ID_INVALID",
        }

    status_manifesto = str(manifesto.get("status", "")).strip().upper()
    if status_manifesto not in {"CONCLUÍDO", "CONCLUIDO"}:
        return {
            "status": "NotFound",
            "sob_id": sob_id,
            "candidates": [sob_manifesto],
            "error": "PROJECT_MANIFEST_NOT_COMPLETED",
        }

    candidatas = set(
        WorkspaceScanner.detectar_sobs_candidatas(
            root_dir,
            excluir_dwg=dwg_path,
        )
    )
    candidatas.add(sob_manifesto)
    if sob_manifesto != sob_id:
        candidatas.add(sob_id)
        return {
            "status": "Ambiguous",
            "sob_id": sob_id,
            "candidates": sorted(candidatas),
            "error": "PROJECT_SCOPE_MANIFEST_MISMATCH",
        }

    base_dwg = manifesto.get("base_dwg")
    if not isinstance(base_dwg, str) or not base_dwg.strip() or not dwg_path:
        return {
            "status": "Invalid",
            "sob_id": sob_id,
            "candidates": sorted(candidatas),
            "error": "PROJECT_DWG_UNVERIFIABLE",
        }
    base_path = Path(base_dwg)
    if not base_path.is_absolute():
        base_path = root_dir / base_path
    if (base_path.resolve() != Path(dwg_path).resolve()
            or Path(dwg_path).resolve().parent != root_dir.resolve()
            or (require_existing_dwg and not Path(dwg_path).is_file())):
        return {
            "status": "Invalid",
            "sob_id": sob_id,
            "candidates": sorted(candidatas),
            "error": "PROJECT_DWG_MISMATCH",
        }

    if len(candidatas) > 1:
        return {
            "status": "Ambiguous",
            "sob_id": sob_id,
            "candidates": sorted(candidatas),
            "error": "MULTIPLE_PROJECT_CANDIDATES",
        }

    return {
        "status": "Bound",
        "sob_id": sob_id,
        "candidates": sorted(candidatas),
        "error": None,
    }


def _contexto_project_scope_indisponivel(
    status_scope: str,
    root_dir: Path,
    dwg_path: Optional[str],
    sob_id: Optional[str],
    candidates: List[str],
    error: Optional[str],
) -> Dict[str, Any]:
    mensagens = {
        "Unbound": "Contexto não identificado",
        "NotFound": "Identidade de projeto não localizada",
        "Ambiguous": "Ambiguidade de contexto",
        "Invalid": "Vínculo de projeto inválido",
    }
    dwg_nome = Path(dwg_path).name if dwg_path else "-"
    return {
        "sob_id": sob_id or "-",
        "root_dir": str(root_dir),
        "dwg_principal": dwg_nome,
        "municipio": "-",
        "bairro": "-",
        "endereco": "-",
        "artefatos": [],
        "status": mensagens.get(status_scope, "Contexto não identificado"),
        "inconsistencia": status_scope == "Ambiguous",
        "mensagem_inconsistencia": ", ".join(candidates) if candidates else "",
        "project_scope_status": status_scope,
        "project_scope_resolved": False,
        "project_scope_candidates": candidates,
        "erro": error,
    }


def _gerar_matriz_artefatos(ws: ProjectWorkspace) -> List[Dict[str, Any]]:
    """
    Normaliza a matriz de artefatos para apresentação na paleta OXCAD.
    Mapeia os principais artefatos monitorados com rótulos amigáveis.
    """
    ordem_chaves = [
        ("DWG", "DWG Principal"),
        ("CROQUI", "Pasta de Croqui de Campo"),
        ("DOCUMENTOS", "Documentos e Anexos"),
        ("CHECKLIST_AMBIENTAL", "Checklist Ambiental"),
        ("MEMORIAL_AMBIENTAL", "Memorial Ambiental"),
        ("CROQUI_AMBIENTAL", "Croqui Satélite"),
        ("CQT", "Queda de Tensão (CQT)"),
        ("ORCAMENTO", "Orçamento de Materiais"),
        ("CPFC", "Participação Financeira (CPFC)"),
        ("UNIFILAR", "Diagrama Unifilar"),
    ]

    matriz = []
    for chave, rotulo in ordem_chaves:
        art = ws.artefatos.get(chave)
        st = art.status.value if art else ArtifactStatus.NAO_EXISTE.value
        existe = (st == ArtifactStatus.EXISTE.value)
        caminho_str = str(art.caminho) if (art and art.caminho) else None
        nome_arquivo = art.caminho.name if (art and art.caminho) else None

        matriz.append({
            "chave": chave,
            "rotulo": rotulo,
            "status": st,
            "existe": existe,
            "icone": "✓" if existe else "○",
            "caminho": caminho_str,
            "nome_arquivo": nome_arquivo,
        })

    return matriz


def extrair_contexto_operacional(
    dwg_path: Optional[str] = None,
    root_dir: Optional[str] = None,
    sob_id_esperada: Optional[str] = None,
    acad_pid: Optional[int] = None,
    acad_token: Optional[str] = None,
    correlation_id: Optional[str] = None,
    require_project_scope: bool = False,
    host_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extrai o contexto operacional completo conectando o DWG ou diretório
    ao ProjectWorkspace e WorkspaceScanner.
    """
    require_project_scope = require_project_scope or sob_id_esperada is not None
    verified = None
    if require_project_scope:
        verified, reason = _verificar_envelope_host(
            host_context, dwg_path, sob_id_esperada, None, None,
            correlation_id, acad_pid,
        )
        if verified is None:
            return {
                "sob_id": None, "artefatos": [], "project_scope_resolved": False,
                "project_scope_status": "Incompatible" if reason == "DWG_CONTEXT_INCOMPATIBLE" else "Unverified",
                "erro": reason, "status": "Contexto DWG não verificado",
            }
        dwg_path = verified["dwg_path"]
        sob_id_esperada = verified["sob_id"]
        if root_dir and Path(root_dir).resolve() != Path(dwg_path).parent:
            return {
                "sob_id": None, "artefatos": [], "project_scope_resolved": False,
                "project_scope_status": "Incompatible",
                "erro": "DWG_CONTEXT_INCOMPATIBLE", "status": "Contexto DWG incompatível",
            }
    t_inicio = time.perf_counter()
    logger.info(
        "Iniciando extração de contexto operacional",
        extra={
            "correlation_id": correlation_id,
            "dwg_path": dwg_path,
            "root_dir": root_dir,
            "action": "consultar_contexto"
        }
    )
    # 1. Determinação de diretório e arquivo DWG
    p_dwg: Optional[Path] = None
    p_root: Optional[Path] = None
    sob_dwg: Optional[str] = None

    if dwg_path:
        p_dwg = Path(dwg_path).resolve()
        sob_dwg = WorkspaceScanner.extrair_sob_de_texto(p_dwg.name)
        if not root_dir:
            p_root = p_dwg.parent
        else:
            p_root = Path(root_dir).resolve()
    elif root_dir:
        p_root = Path(root_dir).resolve()

    if not p_root:
        p_root = Path.cwd()

    # 2. Verificação de existência física do diretório
    if not p_root.exists() or not p_root.is_dir():
        return {
            "sob_id": sob_id_esperada or sob_dwg or "-",
            "root_dir": str(p_root),
            "dwg_principal": p_dwg.name if p_dwg else "-",
            "municipio": "-",
            "bairro": "-",
            "endereco": "-",
            "artefatos": [],
            "status": "Diretório não encontrado",
            "inconsistencia": False,
            "mensagem_inconsistencia": "",
            "project_scope_status": (
                "NotFound" if require_project_scope else "NotRequired"
            ),
            "project_scope_resolved": False,
            "project_scope_candidates": [],
            "erro": f"Diretório inexistente ou inacessível: {p_root}",
        }

    scope_result: Optional[Dict[str, Any]] = None
    if require_project_scope:
        scope_result = {"status": "Bound", "sob_id": sob_id_esperada,
                        "candidates": [sob_id_esperada], "error": None} if verified else _resolver_project_scope(
            p_root,
            dwg_path,
            sob_id_esperada,
        )
        if scope_result["status"] != "Bound":
            return _contexto_project_scope_indisponivel(
                status_scope=scope_result["status"],
                root_dir=p_root,
                dwg_path=dwg_path,
                sob_id=scope_result["sob_id"],
                candidates=scope_result["candidates"],
                error=scope_result["error"],
            )
        sob_id_esperada = scope_result["sob_id"]

    # 3. Execução da varredura pelo scanner oficial
    # O scanner examina o diretório e seus arquivos para determinar a SOB do Workspace
    ws = WorkspaceScanner.scan(p_root, sob_id=sob_id_esperada)

    # 4. Avaliação de Inconsistência de Contexto (Seção 13)
    inconsistencia = False
    msg_inconsistencia = ""

    # Se o nome do DWG aponta explicitamente para uma SOB diferente da SOB do Workspace da pasta
    if (
        not require_project_scope
        and sob_dwg
        and ws.sob_id
        and sob_dwg != ws.sob_id
        and ws.sob_id != "PROJETO"
    ):
        inconsistencia = True
        msg_inconsistencia = f"DWG: {sob_dwg} | Workspace: {ws.sob_id}"
        status_texto = "⚠ Inconsistência de contexto"
    else:
        # Se não há conflito com a pasta e o DWG tem SOB, adota a SOB do DWG caso ws seja genérico
        if ws.sob_id == "PROJETO" and sob_dwg:
            ws = WorkspaceScanner.scan(p_root, sob_id=sob_dwg)

        if ws.sob_id and ws.sob_id != "PROJETO":
            status_texto = "Projeto identificado"
        else:
            status_texto = "Contexto identificado"

    # 5. Recuperação de Metadados locais
    metadados = _obter_metadados_locais(p_root, ws.sob_id)

    # 6. Matriz de artefatos normalizada
    artefatos_lista = _gerar_matriz_artefatos(ws)

    # 7. Nome do DWG exibido
    dwg_exibido = "-"
    if ws.dwg_principal and ws.dwg_principal.exists():
        dwg_exibido = ws.dwg_principal.name
    elif p_dwg:
        dwg_exibido = p_dwg.name

    # 8. Estado do apontamento de tempo do projeto (OXCAD 0.5.2 com detecção por PID + Token de Sessão)
    entry_tempo = tratar_interrupcao_se_necessario(ws.root_dir, pid_atual=acad_pid, token_sessao_atual=acad_token)
    if not entry_tempo:
        entry_tempo = carregar_tempo_projeto(ws.root_dir)

    if entry_tempo:
        tempo_dados = entry_tempo.para_dicionario()
    else:
        tempo_dados = {
            "sob_id": ws.sob_id if ws.sob_id else "-",
            "dwg_path": dwg_exibido if dwg_exibido != "-" else None,
            "estado": "NaoIniciado",
            "data_hora_inicio": None,
            "data_hora_fim": None,
            "tempo_acumulado_segundos": 0.0,
            "sessao_atual_inicio": None,
            "ultima_atualizacao": None,
            "ultima_atividade": None,
            "pid_processo": None,
            "token_sessao": None,
            "tempo_total_segundos": 0.0,
            "tempo_formatado": "00:00:00",
            "inicio_formatado": "-",
            "fim_formatado": "-",
            "sessoes": [],
        }

    duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
    logger.info(
        f"Contexto operacional extraído com sucesso ({duracao_ms:.1f}ms)",
        extra={
            "correlation_id": correlation_id,
            "sob_id": ws.sob_id if ws.sob_id else "-",
            "dwg_path": dwg_exibido,
            "duration_ms": duracao_ms,
            "result": "sucesso",
            "action": "consultar_contexto"
        }
    )

    return {
        "sob_id": ws.sob_id if ws.sob_id else "-",
        "root_dir": str(ws.root_dir),
        "dwg_principal": dwg_exibido,
        "municipio": metadados["municipio"],
        "bairro": metadados["bairro"],
        "endereco": metadados["endereco"],
        "artefatos": artefatos_lista,
        "status": status_texto,
        "inconsistencia": inconsistencia,
        "mensagem_inconsistencia": msg_inconsistencia,
        "project_scope_status": (
            scope_result["status"] if scope_result else "NotRequired"
        ),
        "project_scope_resolved": (
            scope_result is not None and scope_result["status"] == "Bound"
        ),
        "project_scope_candidates": (
            scope_result["candidates"] if scope_result else []
        ),
        "tempo": tempo_dados,
        "correlation_id": correlation_id,
        "erro": None,
    }


def _executar_acao_operacional_impl(
    acao: str,
    dwg_path: Optional[str] = None,
    root_dir: Optional[str] = None,
    alvo: Optional[str] = None,
    acad_pid: Optional[int] = None,
    acad_token: Optional[str] = None,
    correlation_id: Optional[str] = None,
    sob_id_esperada: Optional[str] = None,
    require_project_scope: bool = False,
    execution_id: Optional[str] = None,
    dwg_identity: Optional[str] = None,
    execution_origin: str = "cli",
    wait_for_completion: bool = False,
    validation_rules: Optional[List[str]] = None,
    snapshot_id: Optional[str] = None,
    revision: Optional[str] = None,
    host_verified: bool = False,
    pending_id: Optional[str] = None,
    pending_description: Optional[str] = None,
    pending_severity: Optional[str] = None,
    pending_status: Optional[str] = None,
    pending_responsible: Optional[str] = None,
    pending_validation: Optional[Dict[str, Any]] = None,
    package_id: Optional[str] = None,
    delivery_artifacts: Optional[List[str]] = None,
    delivery_validations: Optional[List[Dict[str, Any]]] = None,
    delivery_snapshots: Optional[List[str]] = None,
    approval_confirmed: bool = False,
    acknowledge_issues: bool = False,
    decision_note: Optional[str] = None,
    revocation_reason: Optional[str] = None,
    caminho_explicito_sob: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Executa uma ação do Workspace através do WorkspaceActionDispatcher existente.
    Retorna um dicionário estruturado com o resultado da execução.
    """
    t_inicio = time.perf_counter()
    acao_limpa = (acao or "").strip().lower()

    logger.info(
        f"Recebida solicitação de ação: {acao_limpa}",
        extra={
            "correlation_id": correlation_id,
            "action": acao_limpa,
            "dwg_path": dwg_path,
            "alvo": alvo,
            "acad_pid": acad_pid,
            "execution_id": execution_id,
            "dwg_identity": dwg_identity,
            "origin": execution_origin,
        }
    )

    # Resolve o contexto físico preliminar
    p_dwg = Path(dwg_path).resolve() if dwg_path else None
    p_root = Path(root_dir).resolve() if root_dir else (p_dwg.parent if p_dwg else Path.cwd())

    if require_project_scope:
        scope_result = {"status": "Bound", "sob_id": sob_id_esperada,
                        "candidates": [sob_id_esperada], "error": None} if host_verified else _resolver_project_scope(
            p_root,
            dwg_path,
            sob_id_esperada,
        )
        if scope_result["status"] != "Bound":
            return {
                "sucesso": False,
                "acao": acao_limpa,
                "estado": "Requer especificação",
                "mensagem": _contexto_project_scope_indisponivel(
                    scope_result["status"],
                    p_root,
                    dwg_path,
                    scope_result["sob_id"],
                    scope_result["candidates"],
                    scope_result["error"],
                )["status"],
                "project_scope_status": scope_result["status"],
                "project_scope_candidates": scope_result["candidates"],
                "pid": None,
                "correlation_id": correlation_id,
                "erro": scope_result["error"],
            }
        sob_id_esperada = scope_result["sob_id"]

    # Ações dedicadas ao controle operacional de tempo do projeto (OXCAD 0.5.2)
    if acao_limpa in ("tempo_iniciar", "tempo_retomar"):
        sob_id_cand = sob_id_esperada
        if not sob_id_cand and p_dwg:
            sob_id_cand = WorkspaceScanner.extrair_sob_de_texto(p_dwg.name)
        if not sob_id_cand:
            ws_tmp = WorkspaceScanner.scan(p_root)
            sob_id_cand = ws_tmp.sob_id or "PROJETO"
        entry = iniciar_ou_retomar_tempo(
            p_root,
            sob_id_cand,
            dwg_path=str(p_dwg) if p_dwg else None,
            pid=acad_pid,
            token_sessao=acad_token,
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
        return {
            "sucesso": True,
            "acao": acao_limpa,
            "estado": entry.estado.value,
            "mensagem": f"Apontamento de tempo em execução ({entry.obter_tempo_formatado()}).",
            "pid": acad_pid,
            "erro": None,
        }

    if acao_limpa == "tempo_pausar":
        entry = pausar_tempo(
            p_root,
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
        if entry:
            return {
                "sucesso": True,
                "acao": acao_limpa,
                "estado": entry.estado.value,
                "mensagem": f"Apontamento pausado em {entry.obter_tempo_formatado()}.",
                "pid": None,
                "erro": None,
            }
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": "Nenhum apontamento ativo para pausar.",
            "pid": None,
            "erro": "Registro de tempo não encontrado.",
        }

    if acao_limpa == "tempo_heartbeat":
        entry = atualizar_heartbeat_tempo(p_root, pid=acad_pid, token_sessao=acad_token)
        return {
            "sucesso": True,
            "acao": acao_limpa,
            "estado": entry.estado.value if entry else "NaoIniciado",
            "mensagem": "Heartbeat de sessão registrado.",
            "pid": acad_pid,
            "erro": None,
        }

    if acao_limpa == "tempo_interromper":
        entry = tratar_interrupcao_se_necessario(p_root, forcar_interrupcao=True)
        return {
            "sucesso": True,
            "acao": acao_limpa,
            "estado": entry.estado.value if entry else "Pausado",
            "mensagem": "Sessão interrompida consolidada com sucesso.",
            "pid": None,
            "erro": None,
        }

    if acao_limpa == "tempo_concluir":
        entry = concluir_tempo(
            p_root,
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
        if entry:
            return {
                "sucesso": True,
                "acao": acao_limpa,
                "estado": entry.estado.value,
                "mensagem": f"Apontamento concluído. Tempo total: {entry.obter_tempo_formatado()}.",
                "pid": None,
                "erro": None,
            }
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": "Nenhum apontamento ativo para concluir.",
            "pid": None,
            "erro": "Registro de tempo não encontrado.",
        }

    if acao_limpa == "tempo_reabrir":
        entry = reabrir_tempo(
            p_root,
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
        if entry:
            return {
                "sucesso": True,
                "acao": acao_limpa,
                "estado": entry.estado.value,
                "mensagem": "Apontamento reaberto com histórico preservado.",
                "pid": None,
                "erro": None,
            }
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": "Nenhum apontamento encontrado para reabrir.",
            "pid": None,
            "erro": "Registro de tempo não encontrado.",
        }

    # Tratamento específico: Unifilar requer interação manual no AutoCAD
    if acao_limpa == "unifilar":
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Requer especificação",
            "mensagem": "O Diagrama Unifilar requer interação gráfica dentro do AutoCAD (comandos UNIFILAR ou PROTECAO).",
            "pid": None,
            "erro": None,
        }

    # Resolve o contexto físico
    p_dwg = Path(dwg_path).resolve() if dwg_path else None
    p_root = Path(root_dir).resolve() if root_dir else (p_dwg.parent if p_dwg else Path.cwd())

    # Ação de abrir artefato físico
    if acao_limpa == "abrir":
        alvo_path = Path(alvo).resolve() if alvo else p_dwg
        if not alvo_path or not alvo_path.exists():
            return {
                "sucesso": False,
                "acao": acao_limpa,
                "estado": "Falhou",
                "mensagem": f"Artefato não encontrado no disco: {alvo_path}",
                "pid": None,
                "correlation_id": correlation_id,
                "erro": "Arquivo ou diretório inexistente.",
            }
        ok = WorkspaceActionDispatcher.abrir_artefato(
            alvo_path,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )
        return {
            "sucesso": ok,
            "acao": acao_limpa,
            "estado": "Concluído" if ok else "Falhou",
            "mensagem": f"Artefato aberto no aplicativo padrão: {alvo_path.name}" if ok else "Falha ao abrir artefato.",
            "pid": None,
            "correlation_id": correlation_id,
            "erro": None if ok else "Falha no despacho do sistema operacional.",
        }

    # Ação de localizar no Explorer
    if acao_limpa == "localizar":
        alvo_path = Path(alvo).resolve() if alvo else p_root
        ok = WorkspaceActionDispatcher.localizar_artefato(
            alvo_path,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )
        return {
            "sucesso": ok,
            "acao": acao_limpa,
            "estado": "Concluído" if ok else "Falhou",
            "mensagem": f"Localizado no Explorer: {alvo_path.name}" if ok else "Falha ao abrir Explorer.",
            "pid": None,
            "correlation_id": correlation_id,
            "erro": None if ok else "Falha no despacho do Explorer.",
        }

    # Demais ações requerem resolução de ProjectWorkspace
    ws = WorkspaceScanner.scan(p_root, sob_id=sob_id_esperada)
    arquivos_antes = _capturar_arquivos_execucao(p_root) if acao_limpa in {
        "cqt", "orcamento", "cpfc", "ambiental"
    } else {}

    try:
        proc: Optional[Any] = None
        resultado_json_path: Optional[Path] = None

        if acao_limpa.startswith("entrega_"):
            from workspace.workspace_delivery import approve, generate, revoke, verify
            from workspace.workspace_validation import ValidationContext

            delivery_context = ValidationContext(
                execution_id=execution_id or "",
                correlation_id=correlation_id or "",
                sob_id=ws.sob_id,
                dwg_path=str(p_dwg) if p_dwg else None,
                dwg_identity=dwg_identity,
                database_fingerprint=dwg_identity,
                project_root=p_root,
                cqt_path=ws.cqt_planilha,
                revision=revision or None,
                origin=execution_origin,
                host_verified=host_verified,
            )
            if acao_limpa == "entrega_gerar":
                delivery_result = generate(
                    delivery_context, delivery_artifacts,
                    delivery_validations, delivery_snapshots,
                )
            elif acao_limpa == "entrega_verificar":
                delivery_result = verify(delivery_context, package_id or "")
            elif acao_limpa == "entrega_aprovar":
                approve(
                    delivery_context, package_id or "", confirmed=approval_confirmed,
                    acknowledge_issues=acknowledge_issues,
                    decision_note=decision_note,
                )
                delivery_result = verify(delivery_context, package_id or "")
            elif acao_limpa == "entrega_revogar":
                revoked = revoke(delivery_context, package_id or "", revocation_reason)
                delivery_result = {
                    "status": "REVOKED", "approval_valid": False,
                    "package_id": package_id, "approval": revoked,
                }
            else:
                raise ValueError("DELIVERY_ACTION_INVALID")
            status = delivery_result["status"]
            success = status in {"UNAPPROVED", "CONFIRMED", "REVOKED"}
            delivery_event = {
                    "action": acao_limpa,
                    "operation": "delivery.action",
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "sob_id": ws.sob_id,
                    "dwg_path": str(p_dwg) if p_dwg else None,
                    "dwg_identity": dwg_identity,
                    "origin": execution_origin,
                    "delivery_package_id": delivery_result.get("package_id", package_id),
                    "delivery_status": status,
                    "delivery_manifest_sha256": delivery_result.get("manifest_sha256"),
                    "delivery_approval_state": (
                        delivery_result.get("approval") or {}
                    ).get("state"),
            }
            if success and acao_limpa in {
                "entrega_gerar", "entrega_aprovar", "entrega_revogar"
            }:
                try:
                    registrar_evento_obrigatorio(
                        logger, f"{acao_limpa}: {status}", delivery_event
                    )
                except OSError:
                    if acao_limpa == "entrega_aprovar":
                        revoke(
                            delivery_context, package_id or "",
                            "Falha no registro obrigatório de aprovação",
                        )
                    raise
            else:
                (logger.info if success else logger.warning)(
                    f"{acao_limpa}: {status}", extra=delivery_event
                )
            return {
                "sucesso": success, "acao": acao_limpa,
                "estado": "Concluído" if success else "Falhou",
                "mensagem": f"{acao_limpa}: {status}",
                "delivery_result": delivery_result,
                "pid": None, "erro": None if success else status,
            }

        if acao_limpa.startswith("pendencia_"):
            from workspace.workspace_pending import (
                create as create_pending,
                get as get_pending,
                list_pending,
                update as update_pending,
            )
            from workspace.workspace_validation import ValidationContext

            pending_context = ValidationContext(
                execution_id=execution_id or "",
                correlation_id=correlation_id or "",
                sob_id=ws.sob_id,
                dwg_path=str(p_dwg) if p_dwg else None,
                dwg_identity=dwg_identity,
                database_fingerprint=dwg_identity,
                project_root=p_root,
                cqt_path=ws.cqt_planilha,
                origin=execution_origin,
                host_verified=host_verified,
            )
            if acao_limpa == "pendencia_criar":
                pending_result = create_pending(
                    pending_context, pending_description, pending_severity,
                    validation=pending_validation, snapshot_id=snapshot_id,
                    responsible=pending_responsible,
                )
            elif acao_limpa == "pendencia_listar":
                pending_result = list_pending(pending_context)
            elif acao_limpa == "pendencia_obter":
                pending_result = get_pending(pending_context, pending_id)
            elif acao_limpa in {
                "pendencia_atualizar", "pendencia_resolver",
                "pendencia_descartar", "pendencia_reabrir",
            }:
                status = {
                    "pendencia_resolver": "RESOLVIDA",
                    "pendencia_descartar": "DESCARTADA",
                    "pendencia_reabrir": "ABERTA",
                }.get(acao_limpa, pending_status)
                pending_result = update_pending(
                    pending_context, pending_id, status=status,
                    description=pending_description,
                    responsible=pending_responsible,
                )
            else:
                raise ValueError("PENDING_ACTION_INVALID")
            pending_event = {
                    "action": acao_limpa,
                    "operation": "pending.change" if acao_limpa not in {
                        "pendencia_listar", "pendencia_obter"
                    } else "pending.read",
                    "pending_id": pending_result.get("id") if isinstance(
                        pending_result, dict
                    ) else None,
                    "pending_status": pending_result.get("status") if isinstance(
                        pending_result, dict
                    ) else None,
                    "pending_evidence": pending_result.get("evidence") if isinstance(
                        pending_result, dict
                    ) else None,
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "sob_id": ws.sob_id,
                    "dwg_path": str(p_dwg) if p_dwg else None,
                    "dwg_identity": dwg_identity,
                    "origin": execution_origin,
            }
            if acao_limpa in {"pendencia_listar", "pendencia_obter"}:
                logger.info(f"{acao_limpa} concluída.", extra=pending_event)
            else:
                registrar_evento_obrigatorio(
                    logger, f"{acao_limpa} concluída.", pending_event
                )
            return {
                "sucesso": True, "acao": acao_limpa,
                "estado": "Concluído", "mensagem": "Operação de pendência concluída.",
                "pending_result": pending_result,
                "pid": None, "erro": None,
            }

        if acao_limpa in {"versao_capturar", "versao_listar", "versao_verificar", "versao_recuperar"}:
            from workspace.workspace_validation import ValidationContext
            from workspace.workspace_versions import capture, inspect, list_snapshots, restore

            version_context = ValidationContext(
                execution_id=execution_id or "",
                correlation_id=correlation_id or "",
                sob_id=ws.sob_id,
                dwg_path=str(p_dwg) if p_dwg else None,
                dwg_identity=dwg_identity,
                database_fingerprint=dwg_identity,
                project_root=p_root,
                cqt_path=ws.cqt_planilha,
                revision=revision or None,
                origin=execution_origin,
                host_verified=host_verified,
            )
            if acao_limpa == "versao_capturar":
                version_result = capture(version_context, alvo or "")
            elif acao_limpa == "versao_listar":
                version_result = list_snapshots(version_context, alvo or "")
            elif acao_limpa == "versao_verificar":
                version_result = inspect(version_context, snapshot_id or "")
            else:
                version_result = restore(version_context, snapshot_id or "")
            status = version_result["status"]
            success = status in {"CAPTURED", "FOUND", "NO_SNAPSHOTS", "INTACT", "RESTORED"}
            version_event = {
                    "action": acao_limpa,
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "sob_id": ws.sob_id,
                    "dwg_path": str(p_dwg) if p_dwg else None,
                    "dwg_identity": dwg_identity,
                    "origin": execution_origin,
                    "version_snapshot_id": version_result.get("snapshot_id", snapshot_id),
                    "version_status": status,
                    "version_manifest": version_result.get("manifest"),
            }
            if success and acao_limpa in {"versao_capturar", "versao_recuperar"}:
                registrar_evento_obrigatorio(
                    logger, f"{acao_limpa}: {status}", version_event
                )
            else:
                (logger.info if success else logger.warning)(
                    f"{acao_limpa}: {status}", extra=version_event
                )
            return {
                "sucesso": success,
                "acao": acao_limpa,
                "estado": "Concluído" if success else "Falhou",
                "mensagem": f"{acao_limpa}: {status}",
                "version_result": version_result,
                "pid": None,
                "erro": None if success else status,
            }

        if acao_limpa == "validar":
            from workspace.workspace_validation import (
                ValidationContext,
                ValidationEngine,
                ValidationStatus,
            )

            execution_id_final = execution_id or uuid.uuid4().hex
            correlation_id_final = correlation_id or uuid.uuid4().hex
            validation_context = ValidationContext(
                execution_id=execution_id_final,
                correlation_id=correlation_id_final,
                sob_id=ws.sob_id,
                dwg_path=str(p_dwg) if p_dwg else None,
                dwg_identity=dwg_identity,
                database_fingerprint=dwg_identity,
                project_root=p_root,
                cqt_path=ws.cqt_planilha,
                origin=execution_origin,
                host_verified=host_verified,
            )
            validation_results = ValidationEngine().validate(
                validation_context,
                requested_rules=validation_rules,
            )
            resultados_dict = [result.to_dict() for result in validation_results]
            counts = {
                status.value: sum(1 for item in validation_results if item.status == status)
                for status in ValidationStatus
            }
            for result in validation_results:
                nivel = logging.ERROR if result.status.value == "ERRO" else (
                    logging.WARNING if result.status.value == "ALERTA" else logging.INFO
                )
                registrar_evento_obrigatorio(
                    logger,
                    f"Validação {result.rule_id}: {result.status.value}",
                    {
                        "execution_id": execution_id_final,
                        "correlation_id": correlation_id_final,
                        "sob_id": ws.sob_id,
                        "dwg_path": str(p_dwg) if p_dwg else None,
                        "dwg_identity": dwg_identity,
                        "origin": execution_origin,
                        "action": "validar",
                        "validation_rule_id": result.rule_id,
                        "validation_status": result.status.value,
                        "validation_source": result.source.to_dict(),
                        "validation_value": result.value,
                        "validation_criterion": result.criterion,
                    },
                    level=nivel,
                )

            resumo = " | ".join(
                f"{counts.get(status, 0)} {status}"
                for status in ("OK", "ALERTA", "ERRO", "NÃO DISPONÍVEL")
            )
            return {
                "sucesso": True,
                "acao": "validar",
                "estado": "Concluído",
                "mensagem": f"Validação concluída: {resumo}",
                "correlation_id": correlation_id_final,
                "execution_id": execution_id_final,
                "execution_state": "Concluído",
                "sob_id": ws.sob_id,
                "dwg_path": str(p_dwg) if p_dwg else None,
                "dwg_identity": dwg_identity,
                "validation_summary": counts,
                "validation_results": resultados_dict,
                "pid": None,
                "erro": None,
            }
        elif acao_limpa == "cqt":
            proc = WorkspaceActionDispatcher.executar_cqt(
                ws,
                correlation_id=correlation_id,
                execution_id=execution_id,
            )
            nome_modulo = "CQT (Queda de Tensão BT)"
        elif acao_limpa == "orcamento":
            proc = WorkspaceActionDispatcher.executar_orcamento(
                ws,
                correlation_id=correlation_id,
                execution_id=execution_id,
            )
            nome_modulo = "Orçamento de Materiais"
        elif acao_limpa == "cpfc":
            proc = WorkspaceActionDispatcher.executar_cpfc(
                ws,
                correlation_id=correlation_id,
                execution_id=execution_id,
            )
            nome_modulo = "Participação Financeira (CPFC)"
        elif acao_limpa == "ambiental":
            proc = WorkspaceActionDispatcher.executar_ambiental(
                ws,
                correlation_id=correlation_id,
                execution_id=execution_id,
            )
            nome_modulo = "Memorial e Checklist Ambiental"
        elif acao_limpa == "prancha":
            proc = WorkspaceActionDispatcher.executar_prancha(
                ws,
                correlation_id=correlation_id,
                execution_id=execution_id,
            )
            exit_code = proc.wait() if proc and wait_for_completion else None
            duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
            return {
                "sucesso": exit_code is None,
                "acao": "prancha",
                "estado": "Executando..." if exit_code is None else "Falhou",
                "mensagem": "AutoPrancha requer AUTOPRANCHA no AutoCAD; não há entregável verificado." if exit_code == 0 else "Módulo AutoPranche iniciado ou falhou.",
                "pid": proc.pid if proc else None,
                "correlation_id": correlation_id,
                "duration_ms": round(duracao_ms, 2),
                "exit_code": exit_code,
                "erro": "ARTIFACT_NOT_VERIFIED" if exit_code == 0 else None,
            }
        elif acao_limpa == "sob":
            exec_tag = execution_id or uuid.uuid4().hex[:8]
            resultado_json_path = (
                Path(tempfile.gettempdir()) / f"oxcad_sob_res_{exec_tag}.json"
            )
            proc = WorkspaceActionDispatcher.executar_sob(
                ws,
                correlation_id=correlation_id,
                execution_id=execution_id,
                resultado_json=resultado_json_path,
            )
            nome_modulo = "Preparador de SOB"
        else:
            return {
                "sucesso": False,
                "acao": acao_limpa,
                "estado": "Requer especificação",
                "mensagem": f"Ação '{acao}' não homologada ou requer especificação adicional.",
                "pid": None,
                "correlation_id": correlation_id,
                "erro": "Ação desconhecida.",
            }

        pid = proc.pid if proc else None
        exit_code = proc.wait() if proc and wait_for_completion else None
        res_json = resultado_json_path if acao_limpa == "sob" else None
        artefato_gerado = (
            _artefato_tecnico_gerado(acao_limpa, ws, arquivos_antes)
            if exit_code == 0 and acao_limpa in {
                "cqt", "orcamento", "cpfc", "ambiental"
            } else (
                _artefato_sob_gerado(
                    ws=ws,
                    p_root=p_root,
                    sob_id_esperada=sob_id_esperada,
                    caminho_explicito=caminho_explicito_sob,
                    resultado_json=res_json,
                )
                if exit_code == 0 and acao_limpa == "sob"
                else exit_code != 0
            )
        )
        motivo_artefato = (
            "ARTIFACT_NOT_VERIFIED"
            if exit_code == 0 and not artefato_gerado else None
        )
        duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
        if exit_code is None or (exit_code == 0 and not motivo_artefato):
            logger.info(
                f"Ação {acao_limpa} encaminhada ({duracao_ms:.1f}ms)",
                extra={
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "action": acao_limpa,
                    "duration_ms": duracao_ms,
                    "process_id": pid,
                    "result": "sucesso" if exit_code == 0 else "executando",
                },
            )
        else:
            logger.error(
                f"Subprocesso de {acao_limpa} terminou sem entregável verificado ({exit_code})",
                extra={
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "action": acao_limpa,
                    "duration_ms": duracao_ms,
                    "process_id": pid,
                    "exit_code": exit_code,
                    "result": "falha",
                    "error": motivo_artefato,
                },
            )
        return {
            "sucesso": exit_code in (None, 0) and motivo_artefato is None,
            "acao": acao_limpa,
            "estado": "Executando..." if exit_code is None else (
                "Concluído" if exit_code == 0 and not motivo_artefato else "Falhou"
            ),
            "mensagem": (
                f"Módulo {nome_modulo} iniciou sem conclusão verificada."
                if exit_code is None else
                f"Módulo {nome_modulo} não produziu entregável verificado."
                if motivo_artefato else
                f"Módulo {nome_modulo} concluiu com entregável verificado."
                if exit_code == 0 else
                f"Módulo {nome_modulo} terminou com exit code {exit_code}."
            ),
            "pid": pid,
            "correlation_id": correlation_id,
            "duration_ms": round(duracao_ms, 2),
            "exit_code": exit_code,
            "erro": motivo_artefato or (
                None if exit_code in (None, 0) else f"Exit code {exit_code}"
            ),
        }

    except Exception as ex:
        duracao_ms = (time.perf_counter() - t_inicio) * 1000.0
        logger.error(
            f"Erro ao disparar ação {acao_limpa} ({duracao_ms:.1f}ms): {ex}",
            exc_info=True,
            extra={
                "correlation_id": correlation_id,
                "execution_id": execution_id,
                "action": acao_limpa,
                "duration_ms": duracao_ms,
                "result": "falha",
                "sob_id": sob_id_esperada,
                "dwg_path": str(p_dwg) if p_dwg else None,
                "dwg_identity": dwg_identity,
                "origin": execution_origin,
                "delivery_package_id": package_id if acao_limpa.startswith("entrega_") else None,
            }
        )
        return {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": f"Erro ao disparar ação {acao_limpa}: {ex}",
            "pid": None,
            "correlation_id": correlation_id,
            "duration_ms": round(duracao_ms, 2),
            "erro": str(ex),
            "exception_type": type(ex).__name__,
        }


def _artefato_tecnico_gerado(
    acao: str, ws: ProjectWorkspace, antes: Dict[str, Tuple[int, int]]
) -> bool:
    atualizado = WorkspaceScanner.scan(ws.root_dir, sob_id=ws.sob_id)
    campos = {
        "cqt": ("cqt_planilha",),
        "orcamento": ("orcamento_planilha",),
        "cpfc": ("cpfc_planilha",),
        "ambiental": ("checklist_ambiental",),
    }
    for campo in campos.get(acao, ()):
        path = getattr(atualizado, campo, None)
        if not path or not path.is_file() or ws.sob_id not in path.name.upper():
            continue
        stat = path.stat()
        if (not stat.st_size or antes.get(str(path.resolve()))
                == (stat.st_size, stat.st_mtime_ns)):
            continue
        if path.suffix.lower() in {".xlsx", ".xlsm", ".docx"}:
            if not zipfile.is_zipfile(path):
                continue
        return True
    return False


def _artefato_sob_gerado(
    ws: Optional[ProjectWorkspace] = None,
    p_root: Optional[Path] = None,
    sob_id_esperada: Optional[str] = None,
    caminho_explicito: Optional[Union[str, Path]] = None,
    resultado_json: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Verifica evidências reais do contrato da ação 'sob':
    1. Consome o caminho explícito da pasta/manifesto da SOB criada nesta execução
       (via caminho_explicito direto ou via arquivo de resultado estruturado da execução).
    2. Valida fisicamente:
       - Diretório da SOB existe e é diretório;
       - Manifesto .sob_state.json existe e é arquivo com tamanho > 0;
       - JSON é válido e parseável;
       - status == 'CONCLUÍDO';
       - sob_id está presente, válido e coincide com o esperado (se informado);
       - base_dwg existe fisicamente no disco, possui tamanho > 0 e pertence à pasta da SOB.
    3. Se o caminho explícito não estiver disponível ou for inválido, rejeita determinística
       e imediatamente (sem varredura aleatória ou busca em diretórios históricos).
    """
    caminho_alvo: Optional[Path] = None

    if caminho_explicito:
        caminho_alvo = Path(caminho_explicito).resolve()
    elif resultado_json:
        p_res = Path(resultado_json).resolve()
        if p_res.is_file() and p_res.stat().st_size > 0:
            try:
                dados_res = json.loads(p_res.read_text(encoding="utf-8"))
                if isinstance(dados_res, dict):
                    m_path = dados_res.get("manifesto_path")
                    s_root = dados_res.get("SOB_ROOT") or dados_res.get("sob_root")
                    if m_path:
                        caminho_alvo = Path(m_path).resolve()
                    elif s_root:
                        caminho_alvo = Path(s_root).resolve()
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                caminho_alvo = None

    if not caminho_alvo:
        return False

    pasta_sob: Path
    manifesto_path: Path

    if caminho_alvo.is_file():
        if caminho_alvo.name == ".sob_state.json":
            manifesto_path = caminho_alvo
            pasta_sob = caminho_alvo.parent.resolve()
        else:
            return False
    elif caminho_alvo.is_dir():
        pasta_sob = caminho_alvo.resolve()
        manifesto_path = pasta_sob / ".sob_state.json"
    else:
        return False

    if not pasta_sob.is_dir():
        return False

    if not manifesto_path.is_file() or manifesto_path.stat().st_size == 0:
        return False

    try:
        dados = json.loads(manifesto_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    if not isinstance(dados, dict):
        return False

    status_man = str(dados.get("status", "")).strip().upper()
    if status_man not in {"CONCLUÍDO", "CONCLUIDO"}:
        return False

    sob_man = _normalizar_project_scope(dados.get("sob_id"))
    if not sob_man:
        return False

    id_esperado_norm = _normalizar_project_scope(sob_id_esperada)
    if id_esperado_norm and sob_man != id_esperado_norm:
        return False

    base_dwg_str = dados.get("base_dwg")
    if not isinstance(base_dwg_str, str) or not base_dwg_str.strip():
        return False

    p_dwg = Path(base_dwg_str)
    if not p_dwg.is_absolute():
        p_dwg = pasta_sob / p_dwg
    p_dwg = p_dwg.resolve()

    if not p_dwg.is_file() or p_dwg.stat().st_size == 0:
        return False

    if p_dwg.parent.resolve() != pasta_sob.resolve():
        return False

    return True


def _capturar_arquivos_execucao(root_dir: Path) -> Dict[str, Tuple[int, int]]:
    snapshot: Dict[str, Tuple[int, int]] = {}
    if not root_dir.is_dir():
        return snapshot

    pastas = [root_dir]
    try:
        pastas.extend(
            pasta for pasta in root_dir.iterdir()
            if pasta.is_dir() and pasta.name.casefold() != ".oxcad"
        )
    except OSError:
        return snapshot

    for pasta in pastas:
        try:
            for caminho in pasta.iterdir():
                if not caminho.is_file() or caminho.name.startswith("~"):
                    continue
                if caminho.suffix.lower() not in {
                    ".dwg", ".xls", ".xlsx", ".xlsm", ".csv", ".docx",
                    ".pdf", ".json", ".txt", ".png", ".jpg", ".jpeg",
                    ".kmz", ".kml", ".gpx", ".svg",
                }:
                    continue
                try:
                    info = caminho.stat()
                    snapshot[str(caminho.resolve())] = (info.st_size, info.st_mtime_ns)
                except OSError:
                    continue
        except OSError:
            continue
    return snapshot


def _artefatos_alterados(
    before: Dict[str, Tuple[int, int]],
    after: Dict[str, Tuple[int, int]],
) -> List[Dict[str, Any]]:
    artifacts = []
    for caminho, stamp in after.items():
        old = before.get(caminho)
        if old == stamp:
            continue
        path = Path(caminho)
        try:
            timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            continue
        artifacts.append({
            "path": caminho,
            "type": path.suffix.lower().lstrip("."),
            "operation": "modificado" if old is not None else "criado",
            "exists": path.is_file(),
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        })
    return artifacts


def executar_acao_operacional(
    acao: str,
    dwg_path: Optional[str] = None,
    root_dir: Optional[str] = None,
    alvo: Optional[str] = None,
    acad_pid: Optional[int] = None,
    acad_token: Optional[str] = None,
    correlation_id: Optional[str] = None,
    sob_id_esperada: Optional[str] = None,
    require_project_scope: bool = False,
    execution_id: Optional[str] = None,
    dwg_identity: Optional[str] = None,
    execution_origin: str = "workspace.cli",
    wait_for_completion: bool = False,
    execution_managed_by_host: bool = False,
    validation_rules: Optional[List[str]] = None,
    snapshot_id: Optional[str] = None,
    revision: Optional[str] = None,
    pending_id: Optional[str] = None,
    pending_description: Optional[str] = None,
    pending_severity: Optional[str] = None,
    pending_status: Optional[str] = None,
    pending_responsible: Optional[str] = None,
    pending_validation: Optional[Dict[str, Any]] = None,
    package_id: Optional[str] = None,
    delivery_artifacts: Optional[List[str]] = None,
    delivery_validations: Optional[List[Dict[str, Any]]] = None,
    delivery_snapshots: Optional[List[str]] = None,
    approval_confirmed: bool = False,
    acknowledge_issues: bool = False,
    decision_note: Optional[str] = None,
    revocation_reason: Optional[str] = None,
    host_context: Optional[Dict[str, Any]] = None,
    caminho_explicito_sob: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Executa uma ação e registra seu ciclo sem duplicar o histórico JSONL."""
    acao_limpa = (acao or "").strip().lower()
    exige_dwg_verificado = acao_limpa.startswith(
        ("versao_", "pendencia_", "entrega_", "tempo_")
    ) or acao_limpa in {
        "validar", "cqt", "orcamento", "cpfc", "ambiental", "prancha", "unifilar",
    }
    verified = None
    if exige_dwg_verificado or host_context is not None:
        require_project_scope = True
        verified, reason = _verificar_envelope_host(
            host_context, dwg_path, sob_id_esperada, dwg_identity,
            execution_id, correlation_id, acad_pid,
        )
        if verified is None or not verified["execution_id"] or not verified["correlation_id"]:
            reason = reason if verified is None else "DWG_CONTEXT_NOT_VERIFIED"
            return {
                "sucesso": False, "acao": acao_limpa,
                "estado": "Requer especificação",
                "mensagem": "Contexto DWG não verificado pelo AutoCAD.",
                "project_scope_status": "Incompatible" if reason == "DWG_CONTEXT_INCOMPATIBLE" else "Unverified",
                "project_scope_resolved": False,
                "erro": reason, "pid": None,
            }
        dwg_path = verified["dwg_path"]
        sob_id_esperada = verified["sob_id"]
        dwg_identity = verified["dwg_identity"]
        execution_id = verified["execution_id"]
        correlation_id = verified["correlation_id"]
        execution_origin = "oxcad.palette"
        execution_managed_by_host = bool(execution_managed_by_host)
    cid = correlation_id or uuid.uuid4().hex
    p_dwg = Path(dwg_path).resolve() if dwg_path else None
    p_root = Path(root_dir).resolve() if root_dir else (
        p_dwg.parent if p_dwg else Path.cwd()
    )
    if verified is not None and p_root != p_dwg.parent:
        return {
            "sucesso": False, "acao": acao_limpa,
            "estado": "Requer especificação", "project_scope_status": "Incompatible",
            "erro": "DWG_CONTEXT_INCOMPATIBLE", "pid": None,
        }

    if require_project_scope:
        scope = {"status": "Bound", "sob_id": sob_id_esperada} if verified else _resolver_project_scope(
            p_root, dwg_path, sob_id_esperada
        )
        if scope["status"] != "Bound":
            return _executar_acao_operacional_impl(
                acao_limpa,
                dwg_path=dwg_path,
                root_dir=root_dir,
                alvo=alvo,
                acad_pid=acad_pid,
                acad_token=acad_token,
                correlation_id=cid,
                sob_id_esperada=sob_id_esperada,
                require_project_scope=True,
                execution_origin=execution_origin,
                host_verified=verified is not None,
            )
        sob_id_esperada = scope["sob_id"]

    if acao_limpa == "tempo_heartbeat":
        return _executar_acao_operacional_impl(
            acao_limpa,
            dwg_path=dwg_path,
            root_dir=root_dir,
            alvo=alvo,
            acad_pid=acad_pid,
            acad_token=acad_token,
            correlation_id=cid,
            sob_id_esperada=sob_id_esperada,
            require_project_scope=require_project_scope,
            dwg_identity=dwg_identity,
            execution_origin=execution_origin,
            host_verified=verified is not None,
        )

    exec_id = execution_id or uuid.uuid4().hex
    while exec_id.casefold() == cid.casefold():
        exec_id = uuid.uuid4().hex

    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    before = _capturar_arquivos_execucao(p_root)
    context = {
        "execution_id": exec_id,
        "correlation_id": cid,
        "sob_id": sob_id_esperada,
        "dwg_path": str(p_dwg) if p_dwg else dwg_path,
        "dwg_identity": dwg_identity,
        "action": acao_limpa,
        "origin": execution_origin,
        "operation": "action_execution.transition",
    }

    def registrar_estado(state: str, message: str, **extra: Any) -> None:
        if execution_managed_by_host:
            return
        record = dict(context)
        record.update(extra)
        record["execution_state"] = state
        record["result"] = state
        record["started_at"] = started_at.isoformat().replace("+00:00", "Z")
        level = logger.error if state == "Falhou" else logger.info
        level(message, extra=record)

    registrar_estado("Iniciado", f"Execução {acao_limpa} iniciada.")
    registrar_estado("Executando", f"Execução {acao_limpa} em andamento.")
    exception: Optional[Exception] = None
    try:
        result = _executar_acao_operacional_impl(
            acao_limpa,
            dwg_path=dwg_path,
            root_dir=root_dir,
            alvo=alvo,
            acad_pid=acad_pid,
            acad_token=acad_token,
            correlation_id=cid,
            sob_id_esperada=sob_id_esperada,
            require_project_scope=require_project_scope,
            execution_id=exec_id,
            dwg_identity=dwg_identity,
            execution_origin=execution_origin,
            wait_for_completion=wait_for_completion,
            validation_rules=validation_rules,
            snapshot_id=snapshot_id,
            revision=revision,
            pending_id=pending_id,
            pending_description=pending_description,
            pending_severity=pending_severity,
            pending_status=pending_status,
            pending_responsible=pending_responsible,
            pending_validation=pending_validation,
            package_id=package_id,
            delivery_artifacts=delivery_artifacts,
            delivery_validations=delivery_validations,
            delivery_snapshots=delivery_snapshots,
            approval_confirmed=approval_confirmed,
            acknowledge_issues=acknowledge_issues,
            decision_note=decision_note,
            revocation_reason=revocation_reason,
            host_verified=verified is not None,
            caminho_explicito_sob=caminho_explicito_sob,
        )
    except Exception as ex:
        exception = ex
        logger.exception(
            f"Exceção na execução {exec_id} da ação {acao_limpa}",
            extra={**context, "operation": "action_execution.exception"},
        )
        result = {
            "sucesso": False,
            "acao": acao_limpa,
            "estado": "Falhou",
            "mensagem": f"Exceção ao executar {acao_limpa}: {ex}",
            "erro": str(ex),
            "pid": None,
        }

    terminal = result.get("estado") != "Executando..."
    if result.get("estado") == "Requer especificação":
        terminal_state = "Falhou"
        result["erro"] = result.get("erro") or result.get("mensagem")
    elif not result.get("sucesso"):
        terminal_state = "Falhou"
    elif terminal:
        terminal_state = "Concluído"
    else:
        terminal_state = "Executando"

    finished_at = datetime.now(timezone.utc) if terminal else None
    duration_ms = (time.perf_counter() - started_perf) * 1000.0
    artifacts = _artefatos_alterados(before, _capturar_arquivos_execucao(p_root)) if terminal else []
    result.update({
        "execution_id": exec_id,
        "execution_state": terminal_state,
        "correlation_id": cid,
        "sob_id": sob_id_esperada,
        "dwg_path": str(p_dwg) if p_dwg else dwg_path,
        "dwg_identity": dwg_identity,
        "action": acao_limpa,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z") if finished_at else None,
        "duration_ms": round(duration_ms, 2),
        "artifacts": artifacts,
        "origin": execution_origin,
    })
    if exception is not None:
        result["exception_type"] = type(exception).__name__

    if terminal:
        registrar_estado(
            terminal_state,
            result.get("mensagem", f"Execução {terminal_state.lower()}"),
            duration_ms=duration_ms,
            finished_at=result["finished_at"],
            artifacts=artifacts,
            error=result.get("erro"),
            pid=result.get("pid"),
        )
    return result


def main():
    parser = argparse.ArgumentParser(description="AUX CAD — Headless Context and Action CLI for OXCAD")
    parser.add_argument("--dwg", type=str, help="Caminho do arquivo DWG ativo")
    parser.add_argument("--dir", type=str, help="Caminho do diretório raiz do projeto")
    parser.add_argument("--sob", type=str, help="Identificador SOB esperado (opcional)")
    parser.add_argument("--acao", type=str, help="Ação do Dispatcher a executar (ex: cqt, orcamento, cpfc, ambiental, prancha, sob, abrir)")
    parser.add_argument("--alvo", type=str, help="Caminho do artefato alvo para ações como abrir ou localizar")
    parser.add_argument("--acad-pid", type=int, help="Identificador de processo (PID) do AutoCAD chamador")
    parser.add_argument("--acad-token", type=str, help="Token/SessionId identificador único do AutoCAD chamador")
    parser.add_argument("--correlation-id", type=str, default=None, help="Identificador único de correlação da operação")
    parser.add_argument(
        "--require-project-scope",
        action="store_true",
        help="Exige ProjectScope persistido e validado no DWG",
    )
    parser.add_argument("--execution-id", type=str, default=None)
    parser.add_argument("--dwg-identity", type=str, default=None)
    parser.add_argument("--execution-origin", type=str, default="workspace.cli")
    parser.add_argument("--wait-for-completion", action="store_true")
    parser.add_argument("--execution-managed-by-host", action="store_true")
    parser.add_argument("--host-context-stdin", action="store_true")
    parser.add_argument("--validation-rule", action="append", default=None)
    parser.add_argument("--snapshot-id", type=str, default=None)
    parser.add_argument("--revision", type=str, default=None)
    parser.add_argument("--pending-id", type=str, default=None)
    parser.add_argument("--pending-description", type=str, default=None)
    parser.add_argument("--pending-severity", type=str, default=None)
    parser.add_argument("--pending-status", type=str, default=None)
    parser.add_argument("--pending-responsible", type=str, default=None)
    parser.add_argument("--pending-validation-json", type=str, default=None)
    parser.add_argument("--package-id", type=str, default=None)
    parser.add_argument("--delivery-artifact", action="append", default=None)
    parser.add_argument("--delivery-validations-json", type=str, default=None)
    parser.add_argument("--delivery-snapshot", action="append", default=None)
    parser.add_argument("--confirm-approval", action="store_true")
    parser.add_argument("--acknowledge-issues", action="store_true")
    parser.add_argument("--decision-note", type=str, default=None)
    parser.add_argument("--revocation-reason", type=str, default=None)
    parser.add_argument("--caminho-explicito-sob", type=str, default=None, help="Caminho explícito da pasta/manifesto da SOB")

    args = parser.parse_args()
    correlation_id = args.correlation_id or uuid.uuid4().hex

    try:
        host_context = None
        if args.host_context_stdin:
            envelope = sys.stdin.readline(8193)
            if not envelope or len(envelope) > 8192:
                raise ValueError("DWG_CONTEXT_NOT_VERIFIED")
            host_context = json.loads(envelope)
            if not isinstance(host_context, dict):
                raise ValueError("DWG_CONTEXT_NOT_VERIFIED")
        # Se uma ação foi solicitada, executa o despacho
        if args.acao:
            resultado = executar_acao_operacional(
                acao=args.acao,
                dwg_path=args.dwg,
                root_dir=args.dir,
                alvo=args.alvo,
                acad_pid=args.acad_pid,
                acad_token=args.acad_token,
                correlation_id=correlation_id,
                sob_id_esperada=args.sob,
                require_project_scope=args.require_project_scope,
                execution_id=args.execution_id,
                dwg_identity=args.dwg_identity,
                execution_origin=args.execution_origin,
                wait_for_completion=args.wait_for_completion,
                execution_managed_by_host=args.execution_managed_by_host,
                validation_rules=args.validation_rule,
                snapshot_id=args.snapshot_id,
                revision=args.revision,
                pending_id=args.pending_id,
                pending_description=args.pending_description,
                pending_severity=args.pending_severity,
                pending_status=args.pending_status,
                pending_responsible=args.pending_responsible,
                pending_validation=(
                    json.loads(args.pending_validation_json)
                    if args.pending_validation_json else None
                ),
                package_id=args.package_id,
                delivery_artifacts=args.delivery_artifact,
                delivery_validations=(
                    json.loads(args.delivery_validations_json)
                    if args.delivery_validations_json else None
                ),
                delivery_snapshots=args.delivery_snapshot,
                approval_confirmed=args.confirm_approval,
                acknowledge_issues=args.acknowledge_issues,
                decision_note=args.decision_note,
                revocation_reason=args.revocation_reason,
                host_context=host_context,
                caminho_explicito_sob=args.caminho_explicito_sob,
            )
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
            sys.exit(0 if resultado["sucesso"] else 1)

        # Caso contrário, consulta o contexto operacional
        resultado = extrair_contexto_operacional(
            dwg_path=args.dwg,
            root_dir=args.dir,
            sob_id_esperada=args.sob,
            acad_pid=args.acad_pid,
            acad_token=args.acad_token,
            correlation_id=correlation_id,
            require_project_scope=args.require_project_scope,
            host_context=host_context,
        )
        # Saída JSON estrita na stdout com utf-8
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        sys.exit(0)
    except Exception as ex:
        logger.error(
            f"Erro fatal na execução CLI: {ex}",
            exc_info=True,
            extra={
                "correlation_id": correlation_id,
                "execution_id": args.execution_id,
                "action": args.acao,
                "sob_id": args.sob,
                "dwg_path": args.dwg,
                "dwg_identity": args.dwg_identity,
                "origin": args.execution_origin,
            },
        )
        erro_json = {
            "sucesso": False,
            "acao": args.acao,
            "estado": "Falhou",
            "execution_id": args.execution_id,
            "execution_state": "Falhou",
            "correlation_id": correlation_id,
            "sob_id": args.sob or "-",
            "dwg_path": args.dwg,
            "dwg_identity": args.dwg_identity,
            "origin": args.execution_origin,
            "erro": str(ex),
            "root_dir": args.dir or "-",
            "dwg_principal": args.dwg or "-",
            "municipio": "-",
            "bairro": "-",
            "endereco": "-",
            "artefatos": [],
            "status": "Erro na execução CLI",
            "inconsistencia": False,
            "mensagem_inconsistencia": "",
            "correlation_id": correlation_id,
            "erro": str(ex),
        }
        print(json.dumps(erro_json, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()

