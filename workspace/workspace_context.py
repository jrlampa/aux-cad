"""
Módulo centralizador de contexto compartilhado de projetos OXCAD.
Frente C: Contrato unificado de contexto entre módulos C# e Python.

Regras fundamentais de governança:
1. O AutoCAD/C# é a única autoridade da identidade técnica (SOB_ID, DWG, FingerprintGuid, ProjectRoot).
2. O Python não fabrica identidades; apenas analisa, valida e projeta contextos recebidos do host.
3. Imutabilidade e ausência de singletons globais ou persistência redundante.
4. Nenhum dado que represente identidade, revisão, operador ou rastreabilidade real pode receber
   valor fictício sintético (ex.: "REV-01", "operador"). Preferência estrita por None ou campo obrigatório.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import getpass
from pathlib import Path
from typing import Optional
import uuid

from workspace.workspace_validation import ValidationContext
from workspace.workspace_integrations import IntegrationContext


def normalize_sob_id(sob_id: Optional[str]) -> str:
    """Normaliza o identificador SOB_ID para formato canônico em maiúsculas."""
    if not sob_id or not isinstance(sob_id, str):
        return ""
    cand = sob_id.strip().upper()
    if cand.startswith("SOB_"):
        cand = cand[4:]
    return cand


def extract_operator(args: argparse.Namespace) -> Optional[str]:
    """
    Extrai o operador do argumento CLI ou da sessão real do sistema operacional.
    Retorna None se não for informado, evitando a criação de operadores fictícios.
    """
    for attr in ("operator", "reviewer", "actor", "approver", "author"):
        val = getattr(args, attr, None)
        if val and str(val).strip():
            return str(val).strip()
    try:
        user = getpass.getuser()
        if user and user.strip():
            return user.strip()
    except Exception:
        pass
    return None


@dataclass(frozen=True)
class ProjectContext:
    """
    Contrato imutável de contexto unificado de projeto do lado Python.
    Representa a projeção fiel da autoridade C# do AutoCAD.
    Todos os campos de identidade e rastreabilidade refletem estritamente a autoridade host.
    """
    sob_id: str
    dwg_path: Optional[str]
    database_fingerprint: Optional[str]
    project_root: Path
    revision_id: Optional[str] = None
    origin: Optional[str] = None
    operator: Optional[str] = None
    correlation_id: Optional[str] = None
    execution_id: Optional[str] = None

    @property
    def is_bound(self) -> bool:
        """Indica se o contexto possui SOB vinculada."""
        return bool(self.sob_id and self.sob_id.strip())

    def to_validation_context(
        self,
        host_verified: bool = True,
        default_origin: str = "workspace.cli",
    ) -> ValidationContext:
        """Projeta para ValidationContext consumido por revisão e reconciliação."""
        exec_id = self.execution_id or uuid.uuid4().hex
        corr_id = self.correlation_id or exec_id
        fp = self.database_fingerprint or ""

        return ValidationContext(
            execution_id=exec_id,
            correlation_id=corr_id,
            sob_id=self.sob_id,
            dwg_path=self.dwg_path,
            dwg_identity=fp,
            database_fingerprint=fp,
            project_root=self.project_root,
            cqt_path=None,
            revision=self.revision_id,
            origin=self.origin or default_origin,
            host_verified=host_verified,
        )

    def to_integration_context(self) -> IntegrationContext:
        """
        Projeta para IntegrationContext consumido por gateways e provedores externos.
        Rejeita categoricamente contextos parciais ou desprovidos de autoridade DWG.
        """
        if not self.is_bound:
            raise ValueError("sob_id obrigatorio e nao pode ser vazio para IntegrationContext.")
        if not self.dwg_path or not str(self.dwg_path).strip():
            raise ValueError("dwg_path obrigatorio para IntegrationContext.")
        if not self.database_fingerprint or not str(self.database_fingerprint).strip():
            raise ValueError("database_fingerprint obrigatorio para IntegrationContext.")

        identifiers: dict[str, str] = {}
        if self.correlation_id is not None:
            identifiers["correlation_id"] = self.correlation_id
        if self.execution_id is not None:
            identifiers["execution_id"] = self.execution_id
        return IntegrationContext(
            sob_id=self.sob_id,
            project_root=str(self.project_root.resolve()),
            dwg_path=self.dwg_path,
            database_fingerprint=self.database_fingerprint,
            **identifiers,
        )


def parse_project_context(
    args: argparse.Namespace,
    default_origin: Optional[str] = None,
) -> ProjectContext:
    """
    Analisa argumentos CLI e monta o ProjectContext normalizado sem duplicar lógica
    e sem criar identidades sintéticas.
    """
    root_arg = getattr(args, "project_root", None)
    dwg_arg = getattr(args, "dwg", None)
    sob_arg = getattr(args, "sob", "")
    fp_arg = getattr(args, "fingerprint", "")
    rev_arg = getattr(args, "revision_id", None)
    orig_arg = getattr(args, "origin", None)
    corr_arg = getattr(args, "correlation_id", None)
    exec_arg = getattr(args, "execution_id", None)

    # Resolução de DWG e Root
    dwg_str: Optional[str] = None
    if dwg_arg and str(dwg_arg).strip():
        dwg_str = str(Path(str(dwg_arg).strip()).resolve())

    if root_arg and str(root_arg).strip():
        root = Path(str(root_arg).strip()).resolve()
    elif dwg_str:
        root = Path(dwg_str).parent.resolve()
    else:
        root = Path.cwd().resolve()

    sob = normalize_sob_id(sob_arg)
    fp = str(fp_arg).strip() if fp_arg else None
    rev = str(rev_arg).strip() if rev_arg else None
    origin = str(orig_arg).strip() if orig_arg else default_origin
    corr = str(corr_arg).strip() if corr_arg else None
    execution = str(exec_arg).strip() if exec_arg else None
    operator = extract_operator(args)

    return ProjectContext(
        sob_id=sob,
        dwg_path=dwg_str,
        database_fingerprint=fp,
        project_root=root,
        revision_id=rev,
        origin=origin,
        operator=operator,
        correlation_id=corr,
        execution_id=execution,
    )


def build_validation_context(
    args: argparse.Namespace,
    default_origin: str = "oxcad.palette",
    host_verified: bool = True,
) -> ValidationContext:
    """Gera um ValidationContext a partir dos argumentos CLI de forma centralizada."""
    ctx = parse_project_context(args, default_origin=default_origin)
    return ctx.to_validation_context(host_verified=host_verified, default_origin=default_origin)


def build_integration_context(args: argparse.Namespace) -> IntegrationContext:
    """Gera um IntegrationContext a partir dos argumentos CLI de forma centralizada."""
    ctx = parse_project_context(args)
    return ctx.to_integration_context()
