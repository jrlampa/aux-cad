"""Contratos e repositório de validação de campo e evidências locais (P2.5).

Garante integridade e rastreabilidade técnica no DWG/SOB sem dependência de serviços externos.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sob.sob_core import calcular_hash_arquivo
from workspace.workspace_validation import ValidationContext
from workspace import workspace_pending


class FieldValidationStatus(str, Enum):
    """Status padronizados de validação técnica em campo."""
    OK = "OK"
    ALERTA = "ALERTA"
    ERRO = "ERRO"
    NAO_VERIFICADO = "NAO_VERIFICADO"
    NAO_APLICAVEL = "NAO_APLICAVEL"
    NAO_DISPONIVEL = "NAO_DISPONIVEL"


class EvidenceStatus(str, Enum):
    """Status de integridade de uma evidência técnica vinculada."""
    VALID = "VALID"
    MISSING = "MISSING"
    CHANGED = "CHANGED"
    CORRUPT = "CORRUPT"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class FieldEvidenceReference:
    """Referência segura e verificável para evidência técnica local."""
    evidence_id: str
    sob_id: str
    database_fingerprint: str
    path: str
    type: str  # foto, pdf, dwg, kmz, kml, csv, relatorio, anotacao, notas
    size: int
    sha256: str
    created_at: str
    modified_at: str
    source: str

    @classmethod
    def from_file(
        cls,
        file_path: Path,
        sob_id: str,
        database_fingerprint: str,
        evidence_type: str,
        source: str = "campo",
    ) -> FieldEvidenceReference:
        resolved = Path(file_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Arquivo de evidência não encontrado: {file_path}")

        stat = resolved.stat()
        file_hash = calcular_hash_arquivo(resolved)
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")

        return cls(
            evidence_id=uuid.uuid4().hex,
            sob_id=sob_id.strip(),
            database_fingerprint=database_fingerprint.strip(),
            path=str(resolved),
            type=evidence_type.strip().lower(),
            size=stat.st_size,
            sha256=file_hash,
            created_at=_now_utc(),
            modified_at=mtime,
            source=source.strip(),
        )

    def verify_integrity(
        self,
        current_sob_id: Optional[str] = None,
        current_fingerprint: Optional[str] = None,
    ) -> EvidenceStatus:
        """Verifica a integridade binária e soberania de identidade da evidência."""
        if current_sob_id and current_sob_id.strip().upper() != self.sob_id.strip().upper():
            return EvidenceStatus.IDENTITY_MISMATCH
        if current_fingerprint and current_fingerprint.strip() != self.database_fingerprint.strip():
            return EvidenceStatus.IDENTITY_MISMATCH

        target = Path(self.path)
        if not target.exists():
            return EvidenceStatus.MISSING

        try:
            current_hash = calcular_hash_arquivo(target)
            if current_hash != self.sha256:
                return EvidenceStatus.CHANGED
        except Exception:
            return EvidenceStatus.CORRUPT

        return EvidenceStatus.VALID

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FieldValidationItem:
    """Item de validação técnica contextual associado a SOB/DWG."""
    validation_id: str
    sob_id: str
    project_root: str
    dwg_path: str
    database_fingerprint: str
    timestamp: str
    operator_context: Dict[str, Any]
    category: str
    question: str
    expected: Any
    observed: Any
    status: FieldValidationStatus
    evidence_references: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def validate_identity(
        self,
        current_sob_id: str,
        current_dwg: str,
        current_fingerprint: str,
    ) -> bool:
        """Garante que a validação não pertença silenciosamente a outro projeto/DWG."""
        if not current_sob_id or not current_dwg or not current_fingerprint:
            return False

        sob_match = self.sob_id.strip().upper() == current_sob_id.strip().upper()
        fingerprint_match = self.database_fingerprint.strip() == current_fingerprint.strip()

        # Normalização de caminho DWG
        try:
            self_dwg = str(Path(self.dwg_path).resolve())
            curr_dwg = str(Path(current_dwg).resolve())
            dwg_match = self_dwg.lower() == curr_dwg.lower()
        except Exception:
            dwg_match = self.dwg_path.strip().lower() == current_dwg.strip().lower()

        return sob_match and fingerprint_match and dwg_match

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class FieldChecklist:
    """Coleção estruturada e determinística de validações de campo."""

    def __init__(self, items: Optional[List[FieldValidationItem]] = None):
        self._items: List[FieldValidationItem] = list(items) if items else []

    @property
    def items(self) -> List[FieldValidationItem]:
        return list(self._items)

    def add_item(self, item: FieldValidationItem) -> None:
        self._items.append(item)

    def summary(self) -> Dict[str, Any]:
        counts = {
            "total": len(self._items),
            "ok": 0,
            "alerta": 0,
            "erro": 0,
            "nao_verificado": 0,
            "nao_aplicavel": 0,
            "nao_disponivel": 0,
        }
        for item in self._items:
            key = item.status.value.lower()
            if key in counts:
                counts[key] += 1
            else:
                counts[key] = 1
        return counts

    @classmethod
    def create_default(
        cls,
        sob_id: str,
        project_root: str,
        dwg_path: str,
        database_fingerprint: str,
        operator: str = "operador_campo",
    ) -> FieldChecklist:
        """Cria o checklist padrão de campo com verificações essenciais."""
        now = _now_utc()
        op_ctx = {"operator": operator, "host": "local_cad"}

        default_specs = [
            ("Identidade", "SOB identificado", "CONFIRMADO", "CONFIRMADO", FieldValidationStatus.OK),
            ("Identidade", "DWG identificado", "CONFIRMADO", "CONFIRMADO", FieldValidationStatus.OK),
            ("Identidade", "Fingerprint confirmado", "CONFIRMADO", "CONFIRMADO", FieldValidationStatus.OK),
            ("Projeto", "Arquivos necessários disponíveis", "DISPONÍVEL", "DISPONÍVEL", FieldValidationStatus.OK),
            ("Projeto", "Evidência complementar ausente", "COMPLETO", "PENDENTE", FieldValidationStatus.ALERTA),
            ("Campo", "Item verificado em campo", "CONFORME", "CONFORME", FieldValidationStatus.OK),
            ("Campo", "Item divergente identificado", "CONFORME", "DIVERGENTE", FieldValidationStatus.ERRO),
            ("Campo", "Item ainda não vistoriado", "VISTORIADO", "PENDENTE", FieldValidationStatus.NAO_VERIFICADO),
        ]

        items = []
        for cat, q, exp, obs, st in default_specs:
            items.append(
                FieldValidationItem(
                    validation_id=uuid.uuid4().hex,
                    sob_id=sob_id,
                    project_root=project_root,
                    dwg_path=dwg_path,
                    database_fingerprint=database_fingerprint,
                    timestamp=now,
                    operator_context=op_ctx,
                    category=cat,
                    question=q,
                    expected=exp,
                    observed=obs,
                    status=st,
                )
            )
        return cls(items)


# ==============================================================================
# PERSISTÊNCIA ATÔMICA E INTEGRAÇÃO COM PENDÊNCIAS EXISTENTES (.oxcad/pending.json)
# ==============================================================================

FIELD_VALIDATION_STORE = "field_validations.json"


def save_field_validations(
    project_root: Path,
    sob_id: str,
    database_fingerprint: str,
    dwg_path: str,
    items: List[FieldValidationItem],
    evidences: Optional[List[FieldEvidenceReference]] = None,
) -> Path:
    """Salva atomicamente as validações de campo em .oxcad/field_validations.json."""
    folder = Path(project_root) / ".oxcad"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / FIELD_VALIDATION_STORE

    payload = {
        "schema": 1,
        "sob_id": sob_id,
        "database_fingerprint": database_fingerprint,
        "dwg_path": dwg_path,
        "updated_at": _now_utc(),
        "items": [it.to_dict() for it in items],
        "evidences": [ev.to_dict() for ev in evidences] if evidences else [],
    }

    temp = target.with_name(f".field-{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        temp.replace(target)
    finally:
        if temp.exists():
            temp.unlink()

    return target


def load_field_validations(
    project_root: Path,
    expected_sob_id: Optional[str] = None,
    expected_fingerprint: Optional[str] = None,
) -> Tuple[List[FieldValidationItem], List[FieldEvidenceReference]]:
    """Carrega as validações de campo garantindo validação de soberania."""
    target = Path(project_root) / ".oxcad" / FIELD_VALIDATION_STORE
    if not target.exists():
        return [], []

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as err:
        raise ValueError(f"STORE_INVALID: Falha na leitura de {target}") from err

    if expected_sob_id and data.get("sob_id", "").upper() != expected_sob_id.strip().upper():
        raise ValueError("IDENTITY_MISMATCH: SOB_ID diverge do contexto esperado.")
    if expected_fingerprint and data.get("database_fingerprint", "") != expected_fingerprint.strip():
        raise ValueError("IDENTITY_MISMATCH: DatabaseFingerprint diverge do contexto esperado.")

    items: List[FieldValidationItem] = []
    for raw in data.get("items", []):
        items.append(
            FieldValidationItem(
                validation_id=raw["validation_id"],
                sob_id=raw["sob_id"],
                project_root=raw["project_root"],
                dwg_path=raw["dwg_path"],
                database_fingerprint=raw["database_fingerprint"],
                timestamp=raw["timestamp"],
                operator_context=raw.get("operator_context", {}),
                category=raw["category"],
                question=raw["question"],
                expected=raw.get("expected"),
                observed=raw.get("observed"),
                status=FieldValidationStatus(raw["status"]),
                evidence_references=raw.get("evidence_references", []),
                notes=raw.get("notes"),
            )
        )

    evidences: List[FieldEvidenceReference] = []
    for raw in data.get("evidences", []):
        evidences.append(
            FieldEvidenceReference(
                evidence_id=raw["evidence_id"],
                sob_id=raw["sob_id"],
                database_fingerprint=raw["database_fingerprint"],
                path=raw["path"],
                type=raw["type"],
                size=raw["size"],
                sha256=raw["sha256"],
                created_at=raw["created_at"],
                modified_at=raw["modified_at"],
                source=raw["source"],
            )
        )

    return items, evidences


def sync_divergence_to_pending(
    context: ValidationContext,
    item: FieldValidationItem,
    responsible: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Integra uma divergência de campo (ERRO ou ALERTA) ao cadastro autoritativo
    existente de pendências (.oxcad/pending.json), evitando duplicidades.
    """
    if item.status not in (FieldValidationStatus.ERRO, FieldValidationStatus.ALERTA):
        return None

    if not item.validate_identity(
        context.sob_id,
        str(context.dwg_path or ""),
        str(context.database_fingerprint or ""),
    ):
        raise ValueError("IDENTITY_MISMATCH: Validação não pertence ao DWG/SOB ativo.")

    severity = "ERRO" if item.status == FieldValidationStatus.ERRO else "ALERTA"
    description = f"[CAMPO] {item.category}: {item.question} (Esperado: {item.expected}, Observado: {item.observed})"

    # Verificar se já existe pendência aberta com mesma descrição e SOB
    existing = workspace_pending.list_pending(context)
    for p in existing:
        if p.get("description") == description and p.get("status") in ("ABERTA", "EM_ANDAMENTO"):
            return p  # Já registrado, não duplica

    # Criação da nova pendência usando o mecanismo autoritativo existente
    return workspace_pending.create(
        context=context,
        description=description,
        severity=severity,
        responsible=responsible,
    )
