"""Interface CLI deterministica para o Executor de Integracoes Externas (P3).

Permite inspecionar a fila SyncQueue e disparar a execucao sincrona sob demanda
com validacao estrita de soberania e saida padronizada em JSON.

Exemplos de uso:
  python -m workspace.workspace_integration_cli --action status --project-root .
  python -m workspace.workspace_integration_cli --action status --project-root . --sync-id <ID>
  python -m workspace.workspace_integration_cli --action executar --project-root . --sync-id <ID> --sob A057526153 --dwg /caminho/desenho.dwg --fingerprint GUID_123
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workspace.workspace_context import ProjectContext
from workspace.workspace_integration_executor import IntegrationExecutor
from workspace.workspace_integrations import (
    IntegrationContext, IntegrationRegistry, IntegrationResult, WorkOrderQuery,
)
from workspace.workspace_sync_queue import SyncQueue, SyncStatus


def _montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI do Executor de Integracoes do OXCAD (P3)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--action",
        choices=["status", "executar", "consultar"],
        required=True,
        help="Acao a executar: 'status' para inspecionar fila ou 'executar' para processar item.",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=".",
        help="Diretorio raiz do projeto OXCAD.",
    )
    parser.add_argument(
        "--sync-id",
        type=str,
        default=None,
        help="Identificador unico (sync_id) do item na fila.",
    )
    parser.add_argument(
        "--sob",
        type=str,
        default=None,
        help="Identificador da SOB associada ao contexto do DWG ativo.",
    )
    parser.add_argument(
        "--dwg",
        type=str,
        default=None,
        help="Caminho do arquivo DWG ativo para validacao de autoridade.",
    )
    parser.add_argument(
        "--fingerprint",
        type=str,
        default=None,
        help="FingerprintGuid do DWG ativo.",
    )
    parser.add_argument(
        "--force-reexec",
        action="store_true",
        help="Forca a tentativa de execucao de item em estado terminal.",
    )
    parser.add_argument("--grupo", default=None)
    parser.add_argument("--query-sob", default=None)
    parser.add_argument("--independent-query", action="store_true")
    parser.add_argument("--correlation-id", default=None)
    parser.add_argument("--execution-id", default=None)
    return parser


def _query_credentials():
    from dotenv import dotenv_values

    values = dotenv_values(
        Path(__file__).resolve().parents[1] / ".env", interpolate=False
    )
    username = os.environ.get("UNIVERSA_ID") or values.get("UNIVERSA_ID")
    password = os.environ.get("UNIVERSA_SENHA") or values.get("UNIVERSA_SENHA")
    values.clear()
    return username, password


def _query_executor() -> IntegrationExecutor:
    from workspace.workspace_universalizacao_provider import (
        UniversalizacaoProvider,
    )

    registry = IntegrationRegistry.create_default()
    provider = UniversalizacaoProvider(
        credential_supplier=_query_credentials
    )
    registry.register(provider)
    return IntegrationExecutor(registry)


def handle_consultar(
    project_context: ProjectContext, query: WorkOrderQuery,
    executor: IntegrationExecutor | None = None,
    independent_query: bool = False,
) -> Dict[str, Any]:
    if not query.is_valid():
        result = IntegrationResult.invalid_request(
            "Grupo A/B e SOB obrigatorios."
        )
    else:
        try:
            context = project_context.to_integration_context()
        except ValueError:
            result = IntegrationResult.invalid_request(
                "Contexto de integracao invalido."
            )
        else:
            result = (executor or _query_executor()).execute_query(
                "universalizacao", query, context,
                independent_query=independent_query,
            )
    payload = asdict(result)
    payload["status"] = result.status.value
    return {
        "sucesso": result.is_success, "query_identity": query.to_dict(),
        "resultado": payload,
    }


def handle_status(queue: SyncQueue, sync_id: str | None, sob: str | None) -> Dict[str, Any]:
    if sync_id:
        item = queue.get_by_sync_id(sync_id)
        if not item:
            return {"sucesso": False, "erro": f"Item com sync_id '{sync_id}' nao localizado."}
        return {"sucesso": True, "item": item.to_dict()}

    items = queue.list_items(sob_id=sob)
    return {
        "sucesso": True,
        "total": len(items),
        "itens": [item.to_dict() for item in items],
    }


def handle_executar(
    queue: SyncQueue,
    sync_id: str | None,
    sob: str | None,
    dwg: str | None,
    fingerprint: str | None,
    project_root: Path,
    force_reexec: bool = False,
) -> Dict[str, Any]:
    if not sync_id:
        return {"sucesso": False, "erro": "Parametro '--sync-id' obrigatorio para acao 'executar'."}
    if not sob:
        return {"sucesso": False, "erro": "Parametro '--sob' obrigatorio para acao 'executar'."}
    if not dwg:
        return {"sucesso": False, "erro": "Parametro '--dwg' obrigatorio para acao 'executar'."}
    if not fingerprint:
        return {"sucesso": False, "erro": "Parametro '--fingerprint' obrigatorio para acao 'executar'."}

    try:
        proj_ctx = ProjectContext(
            sob_id=sob,
            dwg_path=dwg,
            database_fingerprint=fingerprint,
            project_root=project_root,
        )
        context = proj_ctx.to_integration_context()
    except Exception as e:
        return {"sucesso": False, "erro": f"Contexto de integracao invalido: {e}"}

    executor = IntegrationExecutor()
    res = executor.execute_sync_id(queue, sync_id, context, force_reexec=force_reexec)
    return {
        "sucesso": res.success,
        "resultado": res.to_dict(),
    }


def main() -> int:
    parser = _montar_parser()
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if args.action == "consultar":
        context = ProjectContext(
            sob_id=args.sob or "", dwg_path=args.dwg,
            database_fingerprint=args.fingerprint, project_root=project_root,
            correlation_id=args.correlation_id, execution_id=args.execution_id,
        )
        query_out = handle_consultar(
            context, WorkOrderQuery(args.grupo, args.query_sob),
            independent_query=args.independent_query,
        )
        sys.stdout.write(json.dumps(query_out, ensure_ascii=True) + "\n")
        return 0 if query_out["sucesso"] else 1
    queue = SyncQueue(project_root)
    out: Dict[str, Any]

    if args.action == "status":
        out = handle_status(queue, args.sync_id, args.sob)
    elif args.action == "executar":
        out = handle_executar(
            queue=queue,
            sync_id=args.sync_id,
            sob=args.sob,
            dwg=args.dwg,
            fingerprint=args.fingerprint,
            project_root=project_root,
            force_reexec=args.force_reexec,
        )
    else:
        out = {"sucesso": False, "erro": f"Acao desconhecida: {args.action}"}

    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return 0 if out.get("sucesso") else 1


if __name__ == "__main__":
    sys.exit(main())
