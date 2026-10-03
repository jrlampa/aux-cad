"""CLI dedicado para governança de revisão técnica e aprovação do OXCAD (P2.7A).

Ponte entre a interface WPF do AutoCAD e o domínio workspace_review.py.
Não duplica regras de negócio, persistência, pendências ou entregas.
Recebe contexto explícito do AutoCAD e valida a soberania antes de executar.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from workspace import workspace_pending, workspace_review
from workspace.workspace_review import (
    FindingSeverity,
    FindingStatus,
    GateEligibilityStatus,
    ReviewStatus,
)
from workspace.workspace_context import build_validation_context
from workspace.workspace_validation import ValidationContext


def _build_context(args: argparse.Namespace) -> ValidationContext:
    return build_validation_context(args, default_origin="oxcad.palette")


def _extract_operator(args: argparse.Namespace, default: str = "revisor") -> str:
    return (
        getattr(args, "operator", None)
        or getattr(args, "reviewer", None)
        or getattr(args, "actor", None)
        or getattr(args, "approver", None)
        or getattr(args, "author", None)
        or default
    )


def _resolve_review(context: ValidationContext, review_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if review_id:
        return workspace_review.get_review(context, review_id)
    reviews = workspace_review.list_reviews(context)
    return reviews[-1] if reviews else None


def _calculate_counts(review: Optional[Dict[str, Any]], context: ValidationContext) -> Dict[str, int]:
    if not review:
        return {
            "total_findings": 0,
            "critical_major_findings": 0,
            "blocking_pendings": 0,
            "evidences": 0,
        }

    findings = review.get("findings", [])
    total_findings = len(findings)
    crit_major = sum(
        1
        for f in findings
        if f.get("status") == FindingStatus.OPEN.value
        and f.get("severity") in {FindingSeverity.CRITICAL.value, FindingSeverity.MAJOR.value}
    )

    evidences = set(review.get("evidence_references", []))
    for f in findings:
        evidences.update(f.get("evidence_references", []))

    blocking_pendings = 0
    try:
        all_pendings = workspace_pending.list_pending(context)
        ref_ids = set(review.get("pending_references", []))
        blocking_pendings = sum(
            1
            for p in all_pendings
            if p.get("status") in {"ABERTA", "EM_ANDAMENTO"}
            and (
                p.get("severity") in {"BLOQUEANTE", "ALTA", "ERRO"}
                or p.get("id") in ref_ids
            )
        )
    except Exception:
        pass

    return {
        "total_findings": total_findings,
        "critical_major_findings": crit_major,
        "blocking_pendings": blocking_pendings,
        "evidences": len(evidences),
    }


def handle_status(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        return {
            "success": True,
            "has_review": False,
            "review": None,
            "gate": None,
            "counts": _calculate_counts(None, context),
        }

    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])
    return {
        "success": True,
        "has_review": True,
        "review": review,
        "gate": gate,
        "counts": _calculate_counts(review, context),
    }


def handle_iniciar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    rev_id = args.review_id
    review = _resolve_review(context, rev_id)
    operator = _extract_operator(args, "revisor")

    if not review:
        revision_id = args.revision_id or "REV-01"
        review = workspace_review.create_review(
            context=context,
            revision_id=revision_id,
            source_snapshot_id=args.snapshot_id,
            notes=args.notes,
            evidence_references=args.evidence or [],
            operator=operator,
        )

    if review["status"] == ReviewStatus.DRAFT.value:
        review = workspace_review.transition_review(
            context=context,
            review_id=review["review_id"],
            target_status=ReviewStatus.IN_REVIEW.value,
            reason=args.notes or "Iniciando revisão técnica via paleta OXCAD.",
            operator=operator,
        )

    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])
    return {
        "success": True,
        "action": "iniciar",
        "review": review,
        "gate": gate,
        "counts": _calculate_counts(review, context),
    }


def handle_gate(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        raise ValueError("REVIEW_NOT_FOUND")

    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])
    return {
        "success": True,
        "action": "gate",
        "review": review,
        "gate": gate,
        "counts": _calculate_counts(review, context),
    }


def handle_achado(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        raise ValueError("REVIEW_NOT_FOUND")

    create_pending = bool(getattr(args, "create_pending", False) or getattr(args, "creates_pending", False))
    finding = workspace_review.add_finding(
        context=context,
        review_id=review["review_id"],
        severity=args.severity,
        category=args.category or "Geral",
        description=args.description,
        evidence_references=args.evidence or [],
        pending_reference=args.pending_ref,
        create_pending_if_missing=create_pending,
        notes=args.notes,
    )

    updated_rev = workspace_review.get_review(context, review["review_id"])
    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])

    return {
        "success": True,
        "action": "achado",
        "finding": finding,
        "review": updated_rev,
        "gate": gate,
        "counts": _calculate_counts(updated_rev, context),
    }


def handle_solicitar_alteracoes(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        raise ValueError("REVIEW_NOT_FOUND")

    updated_rev = workspace_review.transition_review(
        context=context,
        review_id=review["review_id"],
        target_status=ReviewStatus.CHANGES_REQUIRED.value,
        reason=args.reason or "Alterações requeridas pelo revisor.",
        operator=_extract_operator(args, "revisor"),
    )
    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])

    return {
        "success": True,
        "action": "solicitar_alteracoes",
        "review": updated_rev,
        "gate": gate,
        "counts": _calculate_counts(updated_rev, context),
    }


def handle_aprovar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        raise ValueError("REVIEW_NOT_FOUND")

    decision_note = getattr(args, "decision_note", None) or getattr(args, "comments", None) or "Revisão formalmente aprovada via paleta OXCAD."
    approval = workspace_review.approve_review(
        context=context,
        review_id=review["review_id"],
        confirmed=True,
        decision_note=decision_note,
        operator=_extract_operator(args, "revisor_aprovador"),
    )
    updated_rev = workspace_review.get_review(context, review["review_id"])
    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])

    return {
        "success": True,
        "action": "aprovar",
        "approval": approval,
        "review": updated_rev,
        "gate": gate,
        "counts": _calculate_counts(updated_rev, context),
    }


def handle_rejeitar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        raise ValueError("REVIEW_NOT_FOUND")

    updated_rev = workspace_review.transition_review(
        context=context,
        review_id=review["review_id"],
        target_status=ReviewStatus.REJECTED.value,
        reason=args.reason or "Revisão tecnicamente rejeitada.",
        operator=_extract_operator(args, "revisor"),
    )
    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])

    return {
        "success": True,
        "action": "rejeitar",
        "review": updated_rev,
        "gate": gate,
        "counts": _calculate_counts(updated_rev, context),
    }


def handle_cancelar(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        raise ValueError("REVIEW_NOT_FOUND")

    updated_rev = workspace_review.transition_review(
        context=context,
        review_id=review["review_id"],
        target_status=ReviewStatus.CANCELLED.value,
        reason=args.reason or "Revisão cancelada.",
        operator=_extract_operator(args, "revisor"),
    )
    gate = workspace_review.evaluate_approval_gate(context, review["review_id"])

    return {
        "success": True,
        "action": "cancelar",
        "review": updated_rev,
        "gate": gate,
        "counts": _calculate_counts(updated_rev, context),
    }


def handle_rastreabilidade(args: argparse.Namespace) -> Dict[str, Any]:
    context = _build_context(args)
    review = _resolve_review(context, args.review_id)
    if not review:
        raise ValueError("REVIEW_NOT_FOUND")

    chain = workspace_review.build_traceability_chain(context, review["review_id"])
    return {
        "success": True,
        "action": "rastreabilidade",
        "chain": chain,
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
        description="CLI de Governança e Revisão Técnica OXCAD (P2.7A)",
        parents=[common_parser]
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Obter status da revisão", parents=[common_parser])
    p_status.add_argument("--review-id", help="ID da revisão específica (opcional)")

    # iniciar
    p_iniciar = subparsers.add_parser("iniciar", help="Iniciar revisão técnica", parents=[common_parser])
    p_iniciar.add_argument("--review-id", help="ID da revisão existente para transicionar (opcional)")
    p_iniciar.add_argument("--revision-id", default="REV-01", help="ID da versão técnica (ex: REV-01)")
    p_iniciar.add_argument("--snapshot-id", help="ID do snapshot existente associado")
    p_iniciar.add_argument("--notes", help="Notas ou parecer inicial")
    p_iniciar.add_argument("--operator", help="Nome/identificador do revisor")
    p_iniciar.add_argument("--reviewer", help="Alias para --operator")
    p_iniciar.add_argument("--evidence", action="append", help="Caminho de evidência (pode repetir)")

    # gate
    p_gate = subparsers.add_parser("gate", help="Avaliar Approval Gate", parents=[common_parser])
    p_gate.add_argument("--review-id", help="ID da revisão")

    # achado
    p_achado = subparsers.add_parser("achado", help="Registrar achado técnico", parents=[common_parser])
    p_achado.add_argument("--review-id", help="ID da revisão")
    p_achado.add_argument("--severity", required=True, choices=["INFO", "MINOR", "MAJOR", "CRITICAL"], help="Severidade")
    p_achado.add_argument("--category", default="Geral", help="Categoria do achado")
    p_achado.add_argument("--description", required=True, help="Descrição técnica do achado")
    p_achado.add_argument("--location", help="Localização ou DWG do achado")
    p_achado.add_argument("--evidence", action="append", help="Evidência associada")
    p_achado.add_argument("--pending-ref", help="ID de pendência existente")
    p_achado.add_argument("--create-pending", action="store_true", help="Criar pendência autoritativa se não existir")
    p_achado.add_argument("--creates-pending", action="store_true", help="Alias para --create-pending")
    p_achado.add_argument("--author", help="Alias para --operator")
    p_achado.add_argument("--operator", help="Nome do autor do achado")
    p_achado.add_argument("--notes", help="Notas adicionais")

    # solicitar-alteracoes
    p_sol = subparsers.add_parser("solicitar-alteracoes", help="Solicitar alterações técnicas", parents=[common_parser])
    p_sol.add_argument("--review-id", help="ID da revisão")
    p_sol.add_argument("--reason", required=True, help="Motivo da solicitação de alterações")
    p_sol.add_argument("--operator", help="Nome/identificador do revisor")
    p_sol.add_argument("--actor", help="Alias para --operator")

    # aprovar
    p_apr = subparsers.add_parser("aprovar", help="Aprovar revisão formalmente", parents=[common_parser])
    p_apr.add_argument("--review-id", help="ID da revisão")
    p_apr.add_argument("--decision-note", help="Parecer de aprovação")
    p_apr.add_argument("--comments", help="Alias para --decision-note")
    p_apr.add_argument("--operator", help="Nome/identificador do aprovador")
    p_apr.add_argument("--approver", help="Alias para --operator")

    # rejeitar
    p_rej = subparsers.add_parser("rejeitar", help="Rejeitar revisão técnica", parents=[common_parser])
    p_rej.add_argument("--review-id", help="ID da revisão")
    p_rej.add_argument("--reason", required=True, help="Motivo da rejeição")
    p_rej.add_argument("--operator", help="Nome/identificador do revisor")
    p_rej.add_argument("--actor", help="Alias para --operator")

    # cancelar
    p_can = subparsers.add_parser("cancelar", help="Cancelar rascunho de revisão", parents=[common_parser])
    p_can.add_argument("--review-id", help="ID da revisão")
    p_can.add_argument("--reason", required=True, help="Motivo do cancelamento")
    p_can.add_argument("--operator", help="Nome/identificador do revisor")
    p_can.add_argument("--actor", help="Alias para --operator")

    # rastreabilidade
    p_ras = subparsers.add_parser("rastreabilidade", help="Obter cadeia de rastreabilidade completa", parents=[common_parser])
    p_ras.add_argument("--review-id", help="ID da revisão")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
        cmd_map = {
            "status": handle_status,
            "iniciar": handle_iniciar,
            "gate": handle_gate,
            "achado": handle_achado,
            "solicitar-alteracoes": handle_solicitar_alteracoes,
            "aprovar": handle_aprovar,
            "rejeitar": handle_rejeitar,
            "cancelar": handle_cancelar,
            "rastreabilidade": handle_rastreabilidade,
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
