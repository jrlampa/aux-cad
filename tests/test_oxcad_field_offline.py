"""Suíte de testes automatizados para OXCAD P2.5 — Validação de campo e operação resiliente/offline.

Cobre rigorosamente as 30 exigências contratuais:
1. Core AVAILABLE
2. Core UNAVAILABLE
3. ONLINE
4. OFFLINE
5. UNKNOWN
6. Integration AVAILABLE
7. Integration PARTIAL
8. Integration UNAVAILABLE
9. Integration NOT_CONFIGURED
10. Derivação NORMAL
11. Derivação DEGRADED
12. Derivação OFFLINE
13. Derivação BLOCKED
14. Operação local em OFFLINE
15. Operação externa bloqueada em OFFLINE
16. Operação bloqueada por provider indisponível
17. Identidade válida
18. IDENTITY_MISMATCH
19. Evidência válida
20. Hash de evidência
21. Evidência inexistente
22. Evidência alterada
23. Checklist offline
24. Persistência de validação
25. Pendência integrada ao mecanismo existente
26. Sincronização PENDING_EXTERNAL_SYNC
27. Idempotência
28. Ausência de execução automática da fila
29. Ausência de secrets
30. Regressão dos contratos P2.4
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from sob.sob_core import calcular_hash_arquivo
from workspace.workspace_operational_states import (
    ConnectivityMode,
    CoreStatus,
    IntegrationAvailability,
    OperationalMode,
    OperationalStateContext,
    derive_system_mode,
    evaluate_operation_mode,
)
from workspace.workspace_field_validation import (
    EvidenceStatus,
    FieldChecklist,
    FieldEvidenceReference,
    FieldValidationItem,
    FieldValidationStatus,
    load_field_validations,
    save_field_validations,
    sync_divergence_to_pending,
)
from workspace.workspace_sync_queue import (
    SyncItem,
    SyncQueue,
    SyncStatus,
)
from workspace.workspace_validation import ValidationContext
from workspace.workspace_integrations import (
    IntegrationRegistry,
    IntegrationStatus,
)


@pytest.fixture
def mock_project_env(tmp_path: Path):
    """Cria um ambiente de projeto isolado e válido."""
    sob_id = "A057526153"
    dwg_path = tmp_path / "BASE_DWG.dwg"
    dwg_path.write_text("DWG_BINARY_MOCK_CONTENT", encoding="utf-8")
    fingerprint = "{MOCK-FINGERPRINT-GUID-0001}"
    cqt_path = tmp_path / "cqt.xlsx"
    cqt_path.write_text("CQT_MOCK", encoding="utf-8")

    ctx = ValidationContext(
        execution_id="exec-p25-01",
        correlation_id="corr-p25-01",
        sob_id=sob_id,
        dwg_path=str(dwg_path),
        dwg_identity=fingerprint,
        database_fingerprint=fingerprint,
        project_root=tmp_path,
        cqt_path=cqt_path,
        host_verified=True,
    )
    return {
        "root": tmp_path,
        "sob_id": sob_id,
        "dwg_path": str(dwg_path),
        "fingerprint": fingerprint,
        "context": ctx,
    }


# ==============================================================================
# TESTES 1 A 5 — DIMENSÕES BÁSICAS: CORE E CONECTIVIDADE
# ==============================================================================

def test_01_core_status_available():
    ctx = OperationalStateContext.create(core_status=CoreStatus.AVAILABLE)
    assert ctx.core_status == CoreStatus.AVAILABLE
    assert ctx.core_status.value == "AVAILABLE"


def test_02_core_status_unavailable():
    ctx = OperationalStateContext.create(core_status=CoreStatus.UNAVAILABLE)
    assert ctx.core_status == CoreStatus.UNAVAILABLE
    assert ctx.operational_mode == OperationalMode.BLOCKED


def test_03_connectivity_mode_online():
    ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.ONLINE,
        integration_availability=IntegrationAvailability.AVAILABLE,
    )
    assert ctx.connectivity_mode == ConnectivityMode.ONLINE
    assert ctx.operational_mode == OperationalMode.NORMAL


def test_04_connectivity_mode_offline():
    ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.OFFLINE,
    )
    assert ctx.connectivity_mode == ConnectivityMode.OFFLINE
    assert ctx.operational_mode == OperationalMode.OFFLINE
    assert "local disponível" in ctx.ui_message.lower()


def test_05_connectivity_mode_unknown():
    ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.UNKNOWN,
    )
    assert ctx.connectivity_mode == ConnectivityMode.UNKNOWN
    # Quando desconhecido, o sistema é conservador e opera em modo OFFLINE seguro
    assert ctx.operational_mode == OperationalMode.OFFLINE


# ==============================================================================
# TESTES 6 A 9 — INTEGRAÇÃO AVAILABILITY
# ==============================================================================

def test_06_integration_availability_available():
    mode = derive_system_mode(
        CoreStatus.AVAILABLE,
        ConnectivityMode.ONLINE,
        IntegrationAvailability.AVAILABLE,
    )
    assert mode == OperationalMode.NORMAL


def test_07_integration_availability_partial():
    mode = derive_system_mode(
        CoreStatus.AVAILABLE,
        ConnectivityMode.ONLINE,
        IntegrationAvailability.PARTIAL,
    )
    assert mode == OperationalMode.DEGRADED


def test_08_integration_availability_unavailable():
    mode = derive_system_mode(
        CoreStatus.AVAILABLE,
        ConnectivityMode.ONLINE,
        IntegrationAvailability.UNAVAILABLE,
    )
    assert mode == OperationalMode.DEGRADED


def test_09_integration_availability_not_configured():
    mode = derive_system_mode(
        CoreStatus.AVAILABLE,
        ConnectivityMode.ONLINE,
        IntegrationAvailability.NOT_CONFIGURED,
    )
    assert mode == OperationalMode.DEGRADED


# ==============================================================================
# TESTES 10 A 13 — DERIVAÇÃO CONTRATUAL DOS 4 MODOS OPERACIONAIS
# ==============================================================================

def test_10_derivacao_normal():
    # Core AVAILABLE + ONLINE + Integrações AVAILABLE -> NORMAL
    ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.ONLINE,
        integration_availability=IntegrationAvailability.AVAILABLE,
    )
    assert ctx.operational_mode == OperationalMode.NORMAL
    assert "online completa" in ctx.ui_message.lower()


def test_11_derivacao_degraded():
    # Core AVAILABLE + ONLINE + Integração indisponível/não configurada -> DEGRADED
    ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.ONLINE,
        integration_availability=IntegrationAvailability.UNAVAILABLE,
    )
    assert ctx.operational_mode == OperationalMode.DEGRADED
    assert "parcial" in ctx.ui_message.lower()


def test_12_derivacao_offline():
    # Core AVAILABLE + OFFLINE -> OFFLINE
    ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.OFFLINE,
        integration_availability=IntegrationAvailability.NOT_CONFIGURED,
    )
    assert ctx.operational_mode == OperationalMode.OFFLINE
    assert "local disponível" in ctx.ui_message.lower()


def test_13_derivacao_blocked():
    # Core UNAVAILABLE -> BLOCKED independentemente dos demais
    ctx = OperationalStateContext.create(
        core_status=CoreStatus.UNAVAILABLE,
        connectivity_mode=ConnectivityMode.ONLINE,
        integration_availability=IntegrationAvailability.AVAILABLE,
    )
    assert ctx.operational_mode == OperationalMode.BLOCKED
    assert "bloqueada" in ctx.ui_message.lower() or "inoperante" in ctx.ui_message.lower()


# ==============================================================================
# TESTES 14 A 16 — CAPACIDADES E BLOQUEIOS POR OPERAÇÃO
# ==============================================================================

def test_14_operacao_local_em_offline():
    # Abertura de DWG e validação local continuam operacionais em modo OFFLINE
    sys_ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.OFFLINE,
        integration_availability=IntegrationAvailability.NOT_CONFIGURED,
    )
    op_mode = evaluate_operation_mode(
        sys_ctx,
        requires_connectivity=False,
        is_local_supported=True,
    )
    assert op_mode == OperationalMode.OFFLINE


def test_15_operacao_externa_bloqueada_em_offline():
    # Operação que exige conectividade (ex: download SharePoint) é bloqueada em OFFLINE
    sys_ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.OFFLINE,
    )
    op_mode = evaluate_operation_mode(
        sys_ctx,
        requires_connectivity=True,
        is_local_supported=False,
    )
    assert op_mode == OperationalMode.BLOCKED


def test_16_operacao_bloqueada_por_provider_indisponivel():
    # Operação que depende de um provider específico não configurado
    sys_ctx = OperationalStateContext.create(
        core_status=CoreStatus.AVAILABLE,
        connectivity_mode=ConnectivityMode.ONLINE,
        integration_availability=IntegrationAvailability.PARTIAL,
    )
    # Provedor "sap" não configurado / indisponível
    checker = lambda pid: False if pid == "sap" else True
    op_mode = evaluate_operation_mode(
        sys_ctx,
        requires_connectivity=True,
        required_providers=["sap"],
        provider_checker=checker,
    )
    assert op_mode == OperationalMode.BLOCKED


# ==============================================================================
# TESTES 17 E 18 — IDENTIDADE E SOBERANIA DO DWG (IDENTITY_MISMATCH)
# ==============================================================================

def test_17_identidade_valida(mock_project_env):
    item = FieldValidationItem(
        validation_id="val-01",
        sob_id=mock_project_env["sob_id"],
        project_root=str(mock_project_env["root"]),
        dwg_path=mock_project_env["dwg_path"],
        database_fingerprint=mock_project_env["fingerprint"],
        timestamp="2026-10-02T12:00:00Z",
        operator_context={"op": "user1"},
        category="Identidade",
        question="SOB confere?",
        expected="CONFIRMADO",
        observed="CONFIRMADO",
        status=FieldValidationStatus.OK,
    )
    assert item.validate_identity(
        current_sob_id=mock_project_env["sob_id"],
        current_dwg=mock_project_env["dwg_path"],
        current_fingerprint=mock_project_env["fingerprint"],
    ) is True


def test_18_identity_mismatch(mock_project_env):
    item = FieldValidationItem(
        validation_id="val-02",
        sob_id=mock_project_env["sob_id"],
        project_root=str(mock_project_env["root"]),
        dwg_path=mock_project_env["dwg_path"],
        database_fingerprint=mock_project_env["fingerprint"],
        timestamp="2026-10-02T12:00:00Z",
        operator_context={},
        category="Identidade",
        question="SOB confere?",
        expected="CONFIRMADO",
        observed="CONFIRMADO",
        status=FieldValidationStatus.OK,
    )
    # SOB divergente
    assert item.validate_identity("SOB_DIVERGENTE", mock_project_env["dwg_path"], mock_project_env["fingerprint"]) is False
    # Fingerprint divergente
    assert item.validate_identity(mock_project_env["sob_id"], mock_project_env["dwg_path"], "FP_DIVERGENTE") is False
    # DWG divergente
    assert item.validate_identity(mock_project_env["sob_id"], "outro.dwg", mock_project_env["fingerprint"]) is False


# ==============================================================================
# TESTES 19 A 22 — EVIDÊNCIAS TÉCNICAS E INTEGRIDADE HASH SHA-256
# ==============================================================================

def test_19_evidencia_valida(mock_project_env):
    img = mock_project_env["root"] / "foto_poste.jpg"
    img.write_bytes(b"\xFF\xD8\xFF_JPEG_IMAGE_RAW_BYTES_VALID")

    ev = FieldEvidenceReference.from_file(
        file_path=img,
        sob_id=mock_project_env["sob_id"],
        database_fingerprint=mock_project_env["fingerprint"],
        evidence_type="foto",
        source="camera_campo",
    )
    assert ev.size > 0
    assert ev.type == "foto"
    assert ev.verify_integrity(mock_project_env["sob_id"], mock_project_env["fingerprint"]) == EvidenceStatus.VALID


def test_20_hash_de_evidencia(mock_project_env):
    doc = mock_project_env["root"] / "relatorio.pdf"
    doc.write_text("PDF_CONTENT_TEST_HASH", encoding="utf-8")
    expected_hash = calcular_hash_arquivo(doc)

    ev = FieldEvidenceReference.from_file(
        file_path=doc,
        sob_id=mock_project_env["sob_id"],
        database_fingerprint=mock_project_env["fingerprint"],
        evidence_type="pdf",
    )
    assert ev.sha256 == expected_hash


def test_21_evidencia_inexistente(mock_project_env):
    ev = FieldEvidenceReference(
        evidence_id="ev-missing",
        sob_id=mock_project_env["sob_id"],
        database_fingerprint=mock_project_env["fingerprint"],
        path=str(mock_project_env["root"] / "inexistente.pdf"),
        type="pdf",
        size=100,
        sha256="abc123hash",
        created_at="2026-10-02T12:00:00Z",
        modified_at="2026-10-02T12:00:00Z",
        source="campo",
    )
    assert ev.verify_integrity() == EvidenceStatus.MISSING


def test_22_evidencia_alterada(mock_project_env):
    f = mock_project_env["root"] / "nota.txt"
    f.write_text("CONTEUDO_ORIGINAL", encoding="utf-8")
    ev = FieldEvidenceReference.from_file(
        file_path=f,
        sob_id=mock_project_env["sob_id"],
        database_fingerprint=mock_project_env["fingerprint"],
        evidence_type="anotacao",
    )
    assert ev.verify_integrity() == EvidenceStatus.VALID

    # Modifica o conteúdo para simular alteração/adulteração externa
    f.write_text("CONTEUDO_MODIFICADO_SEM_AUTORIZACAO", encoding="utf-8")
    assert ev.verify_integrity() == EvidenceStatus.CHANGED


# ==============================================================================
# TESTES 23 E 24 — CHECKLIST OFFLINE E PERSISTÊNCIA ATÔMICA
# ==============================================================================

def test_23_checklist_offline(mock_project_env):
    checklist = FieldChecklist.create_default(
        sob_id=mock_project_env["sob_id"],
        project_root=str(mock_project_env["root"]),
        dwg_path=mock_project_env["dwg_path"],
        database_fingerprint=mock_project_env["fingerprint"],
    )
    summary = checklist.summary()
    assert summary["total"] == 8
    assert summary["ok"] >= 4
    assert summary["alerta"] >= 1
    assert summary["erro"] >= 1
    assert summary["nao_verificado"] >= 1


def test_24_persistencia_de_validacao(mock_project_env):
    checklist = FieldChecklist.create_default(
        sob_id=mock_project_env["sob_id"],
        project_root=str(mock_project_env["root"]),
        dwg_path=mock_project_env["dwg_path"],
        database_fingerprint=mock_project_env["fingerprint"],
    )
    saved_path = save_field_validations(
        project_root=mock_project_env["root"],
        sob_id=mock_project_env["sob_id"],
        database_fingerprint=mock_project_env["fingerprint"],
        dwg_path=mock_project_env["dwg_path"],
        items=checklist.items,
    )
    assert saved_path.exists()
    assert saved_path.name == "field_validations.json"

    loaded_items, loaded_evidences = load_field_validations(
        project_root=mock_project_env["root"],
        expected_sob_id=mock_project_env["sob_id"],
        expected_fingerprint=mock_project_env["fingerprint"],
    )
    assert len(loaded_items) == 8

    # Rejeição com IDENTITY_MISMATCH se sob divergir
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        load_field_validations(
            project_root=mock_project_env["root"],
            expected_sob_id="SOB_OUTRO",
        )


# ==============================================================================
# TESTES 25 A 28 — INTEGRAÇÃO DE PENDÊNCIAS E FILA DE SINCRONIZAÇÃO FUTURA
# ==============================================================================

def test_25_pendencia_integrada_ao_mecanismo_existente(mock_project_env):
    # Cria uma validação com status ERRO
    item_erro = FieldValidationItem(
        validation_id="val-divergencia-01",
        sob_id=mock_project_env["sob_id"],
        project_root=str(mock_project_env["root"]),
        dwg_path=mock_project_env["dwg_path"],
        database_fingerprint=mock_project_env["fingerprint"],
        timestamp="2026-10-02T12:00:00Z",
        operator_context={"op": "user1"},
        category="Estruturas",
        question="Vão entre postes conforme projeto?",
        expected="45m",
        observed="58m",
        status=FieldValidationStatus.ERRO,
    )

    # Sincroniza para o store autoritativo de pendências .oxcad/pending.json
    pending_record = sync_divergence_to_pending(
        context=mock_project_env["context"],
        item=item_erro,
        responsible="Engenharia de Campo",
    )
    assert pending_record is not None
    assert pending_record["status"] == "ABERTA"
    assert pending_record["severity"] == "ERRO"
    assert "Vão entre postes" in pending_record["description"]

    # Teste de não duplicação: tentar sincronizar novamente retorna a mesma pendência
    segunda_chamada = sync_divergence_to_pending(
        context=mock_project_env["context"],
        item=item_erro,
    )
    assert segunda_chamada["id"] == pending_record["id"]


def test_26_sincronizacao_pending_external_sync(mock_project_env):
    queue = SyncQueue(mock_project_env["root"])

    # Cria intenção de upload para SharePoint enquanto offline
    item = SyncItem.create(
        operation_id="op-upload-dwg",
        idempotency_key="idemp-dwg-v1",
        operation="upload_artifact",
        provider_id="sharepoint",
        sob_id=mock_project_env["sob_id"],
        artifact={"file": "BASE_DWG.dwg", "size": 1024},
        status=SyncStatus.PENDING,
    )

    enqueued, is_new = queue.enqueue(item)
    assert is_new is True
    # O status deve ser explicitamente PENDING e NUNCA SUCCEEDED
    assert enqueued.status == SyncStatus.PENDING
    assert enqueued.status != SyncStatus.SUCCEEDED


def test_27_idempotencia_da_fila(mock_project_env):
    queue = SyncQueue(mock_project_env["root"])

    item1 = SyncItem.create(
        operation_id="op-1",
        idempotency_key="CHAVE_IDEMPOTENTE_UNICA_123",
        operation="sync_work_order",
        provider_id="sap",
        sob_id=mock_project_env["sob_id"],
        artifact={"os": "OS-9988"},
    )
    enqueued1, is_new1 = queue.enqueue(item1)
    assert is_new1 is True

    # Mesma chave de idempotência com outros dados transitórios
    item2 = SyncItem.create(
        operation_id="op-2",
        idempotency_key="CHAVE_IDEMPOTENTE_UNICA_123",
        operation="sync_work_order",
        provider_id="sap",
        sob_id=mock_project_env["sob_id"],
        artifact={"os": "OS-9988-TENTATIVA2"},
    )
    enqueued2, is_new2 = queue.enqueue(item2)
    assert is_new2 is False
    assert enqueued2.sync_id == enqueued1.sync_id
    assert len(queue.list_items()) == 1


def test_28_ausencia_de_execucao_automatica_da_fila(mock_project_env):
    queue = SyncQueue(mock_project_env["root"])

    item = SyncItem.create(
        operation_id="op-sem-worker",
        idempotency_key="idemp-no-worker",
        operation="export_ged",
        provider_id="onedrive",
        sob_id=mock_project_env["sob_id"],
        artifact={"name": "ged_doc"},
    )
    queue.enqueue(item)

    # A fila é puramente declarativa e persistente; nenhum worker altera o status automaticamente
    items = queue.list_items()
    assert len(items) == 1
    assert items[0].status == SyncStatus.PENDING


# ==============================================================================
# TESTES 29 E 30 — SEGURANÇA E REGRESSÃO DOS CONTRATOS P2.4
# ==============================================================================

def test_29_ausencia_de_secrets_em_evidencias_e_fila(mock_project_env):
    queue = SyncQueue(mock_project_env["root"])
    item = SyncItem.create(
        operation_id="op-sec",
        idempotency_key="idemp-sec",
        operation="test_auth",
        provider_id="microsoft.graph",
        sob_id=mock_project_env["sob_id"],
        artifact={"metadado": "publico"},
    )
    queue.enqueue(item)

    raw_json = (mock_project_env["root"] / ".oxcad" / "sync_queue.json").read_text(encoding="utf-8")
    for forbidden in ["password", "secret", "token", "Bearer", "client_secret", "cookie"]:
        assert forbidden not in raw_json


def test_30_regressao_dos_contratos_p24():
    registry = IntegrationRegistry.create_default()
    assert registry.get("microsoft.graph") is not None
    assert registry.get("sap") is not None
    assert registry.get("sharepoint") is not None
    assert registry.get("local") is not None

    desc_graph = registry.get("microsoft.graph").descriptor
    assert desc_graph.configuration_status.value == "NOT_CONFIGURED"

    local_provider = registry.get("local")
    assert local_provider.descriptor.configuration_status.value == "CONFIGURED"
    # Ausência de chamadas externas reais
    res = local_provider.check_availability()
    assert res.status == IntegrationStatus.SUCCESS
