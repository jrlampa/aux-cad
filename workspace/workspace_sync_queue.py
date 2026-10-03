"""Fila determinística de intenção futura de sincronização e idempotência (P2.5).

Persiste intenções operacionais locais quando offline/indisponível sem executar
nenhum worker, scheduler ou sincronização automática em background.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SyncStatus(str, Enum):
    """Status padronizados de intenções na fila de sincronização."""
    PENDING = "PENDING"
    READY = "READY"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SyncItem:
    """Item imutável de intenção de sincronização externa com idempotência."""
    sync_id: str
    operation_id: str
    idempotency_key: str
    correlation_id: str
    operation: str
    provider_id: str
    sob_id: str
    artifact: Dict[str, Any]
    created_at: str
    status: SyncStatus = SyncStatus.PENDING
    updated_at: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        operation_id: str,
        idempotency_key: str,
        operation: str,
        provider_id: str,
        sob_id: str,
        artifact: Dict[str, Any],
        correlation_id: Optional[str] = None,
        status: SyncStatus = SyncStatus.PENDING,
    ) -> SyncItem:
        if not operation_id or not idempotency_key or not operation or not provider_id or not sob_id:
            raise ValueError("Campos obrigatórios de SyncItem não podem ser vazios.")

        now = _now_utc()
        return cls(
            sync_id=uuid.uuid4().hex,
            operation_id=operation_id.strip(),
            idempotency_key=idempotency_key.strip(),
            correlation_id=correlation_id.strip() if correlation_id else uuid.uuid4().hex,
            operation=operation.strip(),
            provider_id=provider_id.strip().lower(),
            sob_id=sob_id.strip().upper(),
            artifact=dict(artifact),
            created_at=now,
            status=status,
            updated_at=now,
        )

    def with_status(self, new_status: SyncStatus, error: Optional[str] = None) -> SyncItem:
        return SyncItem(
            sync_id=self.sync_id,
            operation_id=self.operation_id,
            idempotency_key=self.idempotency_key,
            correlation_id=self.correlation_id,
            operation=self.operation,
            provider_id=self.provider_id,
            sob_id=self.sob_id,
            artifact=self.artifact,
            created_at=self.created_at,
            status=new_status,
            updated_at=_now_utc(),
            error_message=error,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


SYNC_QUEUE_FILE = "sync_queue.json"


class SyncQueue:
    """
    Fila de intenção local persistida em .oxcad/sync_queue.json.
    Garante deduplicação por IdempotencyKey e não executa chamadas de rede.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.queue_path = self.project_root / ".oxcad" / SYNC_QUEUE_FILE

    def _read_data(self) -> Dict[str, Any]:
        if not self.queue_path.exists():
            return {"schema": 1, "items": []}
        try:
            return json.loads(self.queue_path.read_text(encoding="utf-8"))
        except Exception:
            return {"schema": 1, "items": []}

    def _write_data(self, data: Dict[str, Any]) -> None:
        folder = self.queue_path.parent
        folder.mkdir(parents=True, exist_ok=True)
        temp = self.queue_path.with_name(f".sync-{uuid.uuid4().hex}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            temp.replace(self.queue_path)
        finally:
            if temp.exists():
                temp.unlink()

    def enqueue(self, item: SyncItem) -> Tuple[SyncItem, bool]:
        """
        Adiciona intenção na fila com verificação de idempotência.
        Retorna (SyncItem, bool_is_new).
        Se já existir item com mesma idempotency_key, retorna o existente sem duplicar.
        """
        data = self._read_data()
        items_raw = data.get("items", [])

        # Verificação de idempotência
        for raw in items_raw:
            if raw.get("idempotency_key") == item.idempotency_key:
                existing = SyncItem(
                    sync_id=raw["sync_id"],
                    operation_id=raw["operation_id"],
                    idempotency_key=raw["idempotency_key"],
                    correlation_id=raw["correlation_id"],
                    operation=raw["operation"],
                    provider_id=raw["provider_id"],
                    sob_id=raw["sob_id"],
                    artifact=raw.get("artifact", {}),
                    created_at=raw["created_at"],
                    status=SyncStatus(raw["status"]),
                    updated_at=raw.get("updated_at"),
                    error_message=raw.get("error_message"),
                )
                return existing, False

        # Adiciona novo item
        items_raw.append(item.to_dict())
        data["items"] = items_raw
        self._write_data(data)
        return item, True

    def list_items(
        self,
        status: Optional[SyncStatus] = None,
        sob_id: Optional[str] = None,
    ) -> List[SyncItem]:
        """Lista determinística dos itens persistidos na fila."""
        data = self._read_data()
        result = []
        for raw in data.get("items", []):
            if status is not None and raw.get("status") != status.value:
                continue
            if sob_id is not None and raw.get("sob_id", "").upper() != sob_id.strip().upper():
                continue
            result.append(
                SyncItem(
                    sync_id=raw["sync_id"],
                    operation_id=raw["operation_id"],
                    idempotency_key=raw["idempotency_key"],
                    correlation_id=raw["correlation_id"],
                    operation=raw["operation"],
                    provider_id=raw["provider_id"],
                    sob_id=raw["sob_id"],
                    artifact=raw.get("artifact", {}),
                    created_at=raw["created_at"],
                    status=SyncStatus(raw["status"]),
                    updated_at=raw.get("updated_at"),
                    error_message=raw.get("error_message"),
                )
            )
        return result

    def get_by_idempotency_key(self, key: str) -> Optional[SyncItem]:
        data = self._read_data()
        for raw in data.get("items", []):
            if raw.get("idempotency_key") == key.strip():
                return self._parse_item(raw)
        return None

    def get_by_sync_id(self, sync_id: str) -> Optional[SyncItem]:
        """Recupera item na fila pelo seu sync_id único."""
        data = self._read_data()
        for raw in data.get("items", []):
            if raw.get("sync_id") == sync_id.strip():
                return self._parse_item(raw)
        return None

    def get_by_operation_id(self, operation_id: str) -> Optional[SyncItem]:
        """Recupera item na fila pelo seu operation_id."""
        data = self._read_data()
        for raw in data.get("items", []):
            if raw.get("operation_id") == operation_id.strip():
                return self._parse_item(raw)
        return None

    def update_item(self, item: SyncItem) -> bool:
        """
        Atualiza item existente na fila por sync_id mantendo atomicidade.
        Retorna True se localizado e atualizado, False caso contrário.
        """
        data = self._read_data()
        items = data.get("items", [])
        found = False
        for i, raw in enumerate(items):
            if raw.get("sync_id") == item.sync_id:
                items[i] = item.to_dict()
                found = True
                break
        if found:
            data["items"] = items
            self._write_data(data)
        return found

    def update_status(
        self,
        sync_id: str,
        new_status: SyncStatus,
        error: Optional[str] = None,
    ) -> Optional[SyncItem]:
        """
        Atualiza deterministicamente o status e mensagem de erro de um item na fila.
        Garante idempotência e registro de auditoria com updated_at em UTC.
        """
        data = self._read_data()
        items = data.get("items", [])
        updated_item = None
        for i, raw in enumerate(items):
            if raw.get("sync_id") == sync_id.strip():
                raw["status"] = new_status.value
                raw["updated_at"] = _now_utc()
                raw["error_message"] = error
                updated_item = self._parse_item(raw)
                items[i] = raw
                break
        if updated_item:
            data["items"] = items
            self._write_data(data)
        return updated_item

    @staticmethod
    def _parse_item(raw: Dict[str, Any]) -> SyncItem:
        return SyncItem(
            sync_id=raw["sync_id"],
            operation_id=raw["operation_id"],
            idempotency_key=raw["idempotency_key"],
            correlation_id=raw["correlation_id"],
            operation=raw["operation"],
            provider_id=raw["provider_id"],
            sob_id=raw["sob_id"],
            artifact=raw.get("artifact", {}),
            created_at=raw["created_at"],
            status=SyncStatus(raw["status"]),
            updated_at=raw.get("updated_at"),
            error_message=raw.get("error_message"),
        )
