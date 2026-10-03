"""CLI dedicado para reconciliação de entrega e governança de sincronização offline (P2.7B).

Ponte entre a interface WPF do AutoCAD, os serviços de entrega local (workspace_delivery.py)
e a fila determinística de sincronização offline (workspace_sync_queue.py).
Não duplica regras de negócio, persistência, pendências ou entregas.
Recebe contexto explícito do AutoCAD e valida a soberania antes de executar.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import uuid

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from workspace import (
    workspace_delivery,
    workspace_delivery_reconciliation,
    workspace_review,
)
from workspace.workspace_sync_queue import (
    SyncQueue,
    SyncStatus,
)
from workspace.workspace_validation import ValidationContext


def _build_context(args: argparse.Namespace) -> ValidationContext:
    root_arg = getattr(args, "project_root", None)
    dwg_arg = getattr(args, "dwg", None)
    sob_arg = getattr(args, "sob", "")
    fp_arg = getattr(args, "fingerprint", "")

    root = Path(root_arg).resolve() if root_arg else Path.cwd().resolve()
    dwg = Path(dwg_arg).resolve() if dwg_arg else None
    sob = sob_arg.strip().upper() if sob_arg else ""
    fingerprint = fp_arg.strip() if fp_arg else ""
    correlation = getattr(args, "correlation_id", None) or uuid.uuid4().hex
    execution = uuid.uuid4().hex
    origin = getattr(args, "origin", None) or "oxcad.delivery"

    return ValidationContext(
        execution_id=execution,
        correlation_id=correlation,
        sob_id=sob,
        dwg_path=str(dwg) if dwg else None,
        dwg_identity=fingerprint,
        database_fingerprint=fingerprint,
        project_root=root,
        cqt_path=None,
        revision=getattr(args, "revision_id", None) or "REV-01",
        origin=origin,
        host_verified=True,
    )


def handle_status(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review_id = getattr(args, "review_id", None)
    res = workspace_delivery_reconciliation.get_delivery_status(context, review_id=review_id)
    return {
        "success": True,
        "action": "status",
        "data": res,
    }


def handle_reconciliar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review_id = getattr(args, "review_id", None)
    package_id = getattr(args, "package_id", None)
    result = workspace_delivery_reconciliation.reconcile_delivery(
        context=context,
        review_id=review_id,
        package_id=package_id,
    )
    return {
        "success": True,
        "action": "reconciliar",
        "reconciliation": result.to_dict(),
    }


def handle_preparar_sync(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review_id = getattr(args, "review_id", None)
    package_id = getattr(args, "package_id", None)
    provider_id = getattr(args, "provider_id", "sharepoint") or "sharepoint"
    correlation_id = getattr(args, "correlation_id", None)

    rec_res, sync_item = workspace_delivery_reconciliation.prepare_sync_queue_for_delivery(
        context=context,
        review_id=review_id,
        package_id=package_id,
        provider_id=provider_id,
        correlation_id=correlation_id,
    )

    return {
        "success": True,
        "action": "preparar_sync",
        "reconciliation": rec_res.to_dict(),
        "sync_item": sync_item.to_dict() if sync_item else None,
    }


def handle_gerar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review_id = getattr(args, "review_id", None)
    if not review_id:
        revs = workspace_review.list_reviews(context)
        if not revs:
            raise ValueError("REVIEW_NOT_FOUND")
        review_id = revs[-1]["review_id"]

    artifacts = getattr(args, "artifacts", []) or []
    validations = getattr(args, "validations", []) or []

    # Se artefatos não forem informados explicitamente, seleciona DWG ativo e artefatos de contexto
    if not artifacts and context.dwg_path:
        root = context.project_root.resolve()
        dwg_rel = Path(context.dwg_path).resolve().relative_to(root).as_posix()
        artifacts = [dwg_rel]

    # Prepara entrega utilizando o domínio existente de revisão
    pkg = workspace_review.prepare_delivery_for_review(
        context=context,
        review_id=review_id,
        artifacts=artifacts,
        validations=validations,
    )

    return {
        "success": True,
        "action": "gerar",
        "package": pkg,
    }


def handle_fila_listar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    queue = SyncQueue(context.project_root)
    filter_status = None
    if getattr(args, "status", None):
        try:
            filter_status = SyncStatus(args.status.strip().upper())
        except ValueError:
            raise ValueError(f"Status de sincronização inválido: {args.status}")

    items = queue.list_items(status=filter_status, sob_id=context.sob_id or None)
    return {
        "success": True,
        "action": "fila_listar",
        "count": len(items),
        "items": [item.to_dict() for item in items],
    }


def handle_fila_atualizar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    sync_id = getattr(args, "sync_id", None)
    if not sync_id:
        raise ValueError("SYNC_ID_OBRIGATORIO")

    status_str = getattr(args, "status", None)
    if not status_str:
        raise ValueError("STATUS_OBRIGATORIO")

    try:
        new_status = SyncStatus(status_str.strip().upper())
    except ValueError:
        raise ValueError(f"Status inválido: {status_str}. Permitidos: {[s.value for s in SyncStatus]}")

    error_msg = getattr(args, "error", None)
    queue = SyncQueue(context.project_root)
    updated = queue.update_status(sync_id=sync_id, new_status=new_status, error=error_msg)
    if not updated:
        raise ValueError(f"Item com sync_id '{sync_id}' não encontrado na fila.")

    return {
        "success": True,
        "action": "fila_atualizar",
        "item": updated.to_dict(),
    }


def create_parser() -> argparse.ArgumentParser:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--project-root", default=argparse.SUPPRESS, help="Diretório raiz do projeto")
    common_parser.add_argument("--dwg", default=argparse.SUPPRESS, help="Caminho completo do DWG ativo")
    common_parser.add_argument("--sob", default=argparse.SUPPRESS, help="Identificador SOB")
    common_parser.add_argument("--fingerprint", default=argparse.SUPPRESS, help="DatabaseFingerprint / GUID do DWG")
    common_parser.add_argument("--correlation-id", default=argparse.SUPPRESS, help="Correlation ID da operação")
    common_parser.add_argument("--origin", default=argparse.SUPPRESS, help="Origem da chamada")

    parser = argparse.ArgumentParser(
        description="CLI de Fechamento de Entrega e Reconciliação Offline OXCAD (P2.7B)",
        parents=[common_parser]
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Obter status de entrega e fila", parents=[common_parser])
    p_status.add_argument("--review-id", help="ID da revisão específica (opcional)")

    # reconciliar
    p_rec = subparsers.add_parser("reconciliar", help="Executar reconciliação determinística da entrega", parents=[common_parser])
    p_rec.add_argument("--review-id", help="ID da revisão específica (opcional)")
    p_rec.add_argument("--package-id", help="ID do pacote de entrega específico (opcional)")

    # preparar-sync
    p_sync = subparsers.add_parser("preparar-sync", help="Reconciliar entrega e preparar intenção na SyncQueue", parents=[common_parser])
    p_sync.add_argument("--review-id", help="ID da revisão específica (opcional)")
    p_sync.add_argument("--package-id", help="ID do pacote de entrega específico (opcional)")
    p_sync.add_argument("--provider-id", default="sharepoint", help="Provedor de destino (padrão: sharepoint)")

    # gerar
    p_gerar = subparsers.add_parser("gerar", help="Gerar pacote de entrega para revisão aprovada", parents=[common_parser])
    p_gerar.add_argument("--review-id", help="ID da revisão aprovada")
    p_gerar.add_argument("--artifacts", action="append", help="Caminho relativo do artefato para incluir")

    # fila-listar
    p_list = subparsers.add_parser("fila-listar", help="Listar itens da SyncQueue", parents=[common_parser])
    p_list.add_argument("--status", help="Filtrar por status (PENDING, READY, BLOCKED, FAILED, SUCCEEDED)")

    # fila-atualizar
    p_upd = subparsers.add_parser("fila-atualizar", help="Atualizar status de item da SyncQueue", parents=[common_parser])
    p_upd.add_argument("--sync-id", required=True, help="ID único do item na fila")
    p_upd.add_argument("--status", required=True, help="Novo status (PENDING, READY, BLOCKED, FAILED, SUCCEEDED)")
    p_upd.add_argument("--error", help="Mensagem de erro ou bloqueio (opcional)")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
        cmd_map = {
            "status": handle_status,
            "reconciliar": handle_reconciliar,
            "preparar-sync": handle_preparar_sync,
            "gerar": handle_gerar,
            "fila-listar": handle_fila_listar,
            "fila-atualizar": handle_fila_atualizar,
        }
        handler = cmd_map.get(args.command)
        if not handler:
            raise ValueError(f"Comando desconhecido: {args.command}")

        payload = handler(args)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    except Exception as error:
        err_payload = {
            "success": False,
            "error": str(error),
            "error_type": type(error).__name__,
        }
        print(json.dumps(err_payload, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
