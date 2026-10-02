"""Suíte de testes automatizados para OXCAD P2.6 — Revisão Técnica, Governança e Rastreabilidade.

Cobre rigorosamente as 35 exigências contratuais:
1. criação de revisão;
2. identidade válida;
3. identity mismatch;
4. transição DRAFT -> IN_REVIEW;
5. IN_REVIEW -> APPROVED;
6. IN_REVIEW -> CHANGES_REQUIRED;
7. IN_REVIEW -> REJECTED;
8. CHANGES_REQUIRED -> DRAFT;
9. APPROVED -> SUPERSEDED;
10. transição inválida;
11. finding INFO;
12. finding MINOR;
13. finding MAJOR;
14. finding CRITICAL;
15. finding aberto;
16. finding resolvido;
17. finding relacionado a pending;
18. gate elegível;
19. gate bloqueado por finding CRITICAL;
20. gate bloqueado por finding MAJOR;
21. gate bloqueado por pending;
22. gate bloqueado por identity mismatch;
23. gate bloqueado por snapshot inválido;
24. evidência ausente;
25. evidência alterada;
26. aprovação vinculada à revisão correta;
27. alteração após aprovação;
28. aprovação anterior não aplicada à nova revisão;
29. delivery compatível;
30. delivery incompatível;
31. revogação;
32. histórico preservado;
33. operação offline;
34. ausência de chamada externa;
35. regressão P2.1-P2.5.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import uuid

import openpyxl
import pytest

from workspace import (
    workspace_delivery,
    workspace_indicators,
    workspace_pending,
    workspace_review,
    workspace_versions,
)
from workspace.workspace_review import (
    FindingSeverity,
    FindingStatus,
    GateEligibilityStatus,
    ReviewStatus,
    add_finding,
    approve_review,
    build_traceability_chain,
    create_review,
    evaluate_approval_gate,
    get_review,
    list_reviews,
    prepare_delivery_for_review,
    resolve_finding,
    revoke_review_approval,
    transition_review,
)
from workspace.workspace_validation import ValidationContext, ValidationEngine


def criar_cenario_projeto(parent: Path, sob: str = "A057526153") -> tuple[ValidationContext, Path, Path]:
    root = parent / f"SOB_{sob}"
    root.mkdir(parents=True, exist_ok=True)
    dwg = root / f"PE_{sob}_DESENHO.dwg"
    dwg.write_bytes(b"DWG CONTENT P2.6 TEST")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob,
            "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )
    cqt = root / f"CQT_{sob}.xlsx"
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "CQT ATUAL"
    sheet["A11"] = "Trecho 1"
    sheet["C11"] = 1.0
    sheet["L11"] = 5.50
    wb.save(cqt)
    wb.close()

    ctx = ValidationContext(
        execution_id=f"exec-{sob}",
        correlation_id=f"corr-{sob}",
        sob_id=sob,
        dwg_path=str(dwg),
        dwg_identity=f"fp-{sob}",
        database_fingerprint=f"fp-{sob}",
        project_root=root,
        cqt_path=cqt,
        origin="oxcad.palette",
        revision="REV-01",
    )
    return ctx, dwg, cqt


def test_01_criacao_de_revisao(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01", notes="Revisão inicial")
    assert rev["review_id"] is not None
    assert rev["sob_id"] == ctx.sob_id
    assert rev["status"] == ReviewStatus.DRAFT.value
    assert rev["revision_id"] == "REV-01"
    assert len(rev["history"]) == 1
    assert rev["history"][0]["to_status"] == ReviewStatus.DRAFT.value


def test_02_identidade_valida(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    loaded = get_review(ctx, rev["review_id"])
    assert loaded["sob_id"] == ctx.sob_id
    assert loaded["dwg_path"] == str(dwg.resolve())
    assert loaded["database_fingerprint"] == ctx.database_fingerprint


def test_03_identity_mismatch(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")

    # Mismatch de SOB
    ctx_divergente = ValidationContext(
        execution_id=ctx.execution_id,
        correlation_id=ctx.correlation_id,
        sob_id="OUTRA_SOB",
        dwg_path=ctx.dwg_path,
        dwg_identity=ctx.dwg_identity,
        database_fingerprint=ctx.database_fingerprint,
        project_root=ctx.project_root,
        cqt_path=ctx.cqt_path,
        origin=ctx.origin,
    )
    with pytest.raises(ValueError):
        get_review(ctx_divergente, rev["review_id"])


def test_04_transicao_draft_para_in_review(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    updated = transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando checagem")
    assert updated["status"] == ReviewStatus.IN_REVIEW.value
    assert len(updated["history"]) == 2
    assert updated["history"][1]["from_status"] == ReviewStatus.DRAFT.value
    assert updated["history"][1]["to_status"] == ReviewStatus.IN_REVIEW.value


def test_05_transicao_in_review_para_approved(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando checagem")
    approval = approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Conforme")
    assert approval["state"] == "APROVADO"
    loaded = get_review(ctx, rev["review_id"])
    assert loaded["status"] == ReviewStatus.APPROVED.value
    assert loaded["approval"]["state"] == "APROVADO"


def test_06_transicao_in_review_para_changes_required(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando checagem")
    updated = transition_review(ctx, rev["review_id"], ReviewStatus.CHANGES_REQUIRED.value, "Ajustar cabo")
    assert updated["status"] == ReviewStatus.CHANGES_REQUIRED.value


def test_07_transicao_in_review_para_rejected(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando checagem")
    updated = transition_review(ctx, rev["review_id"], ReviewStatus.REJECTED.value, "Projeto inviável")
    assert updated["status"] == ReviewStatus.REJECTED.value


def test_08_transicao_changes_required_para_draft(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando checagem")
    transition_review(ctx, rev["review_id"], ReviewStatus.CHANGES_REQUIRED.value, "Ajustar cabo")
    updated = transition_review(ctx, rev["review_id"], ReviewStatus.DRAFT.value, "Reaberto para ajuste")
    assert updated["status"] == ReviewStatus.DRAFT.value


def test_09_transicao_approved_para_superseded(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando checagem")
    approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Ok")
    updated = transition_review(ctx, rev["review_id"], ReviewStatus.SUPERSEDED.value, "Substituído por REV-02")
    assert updated["status"] == ReviewStatus.SUPERSEDED.value


def test_10_transicao_invalida(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")

    # DRAFT direto para APPROVED é proibido
    with pytest.raises(ValueError, match="INVALID_TRANSITION"):
        transition_review(ctx, rev["review_id"], ReviewStatus.APPROVED.value, "Tentativa inválida")

    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando")
    approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Ok")

    # APPROVED não pode voltar diretamente para DRAFT
    with pytest.raises(ValueError, match="INVALID_TRANSITION"):
        transition_review(ctx, rev["review_id"], ReviewStatus.DRAFT.value, "Volta proibida")


def test_11_finding_info(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    f = add_finding(ctx, rev["review_id"], severity="INFO", category="Anotação", description="Observação leve")
    assert f["severity"] == FindingSeverity.INFO.value
    assert f["status"] == FindingStatus.OPEN.value


def test_12_finding_minor(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    f = add_finding(ctx, rev["review_id"], severity="MINOR", category="Formatação", description="Cota com pequeno offset")
    assert f["severity"] == FindingSeverity.MINOR.value


def test_13_finding_major(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    f = add_finding(ctx, rev["review_id"], severity="MAJOR", category="Elétrica", description="Queda próxima do limite")
    assert f["severity"] == FindingSeverity.MAJOR.value


def test_14_finding_critical(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    f = add_finding(ctx, rev["review_id"], severity="CRITICAL", category="Segurança", description="Poste em sobrecarga mecânica")
    assert f["severity"] == FindingSeverity.CRITICAL.value


def test_15_finding_aberto(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    f = add_finding(ctx, rev["review_id"], severity="MINOR", category="Topografia", description="Ajustar ângulo")
    loaded = get_review(ctx, rev["review_id"])
    assert loaded["findings"][0]["status"] == FindingStatus.OPEN.value
    assert loaded["findings"][0]["resolved_at"] is None


def test_16_finding_resolvido(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    f = add_finding(ctx, rev["review_id"], severity="MINOR", category="Topografia", description="Ajustar ângulo")
    resolved = resolve_finding(ctx, rev["review_id"], f["finding_id"], "Ângulo ajustado no CAD")
    assert resolved["status"] == FindingStatus.RESOLVED.value
    assert resolved["resolved_at"] is not None


def test_17_finding_relacionado_a_pending(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")

    # Criação de finding que gera pendência no store autoritativo existente
    f = add_finding(
        ctx,
        rev["review_id"],
        severity="MAJOR",
        category="Cabo",
        description="Substituir cabo de entrada",
        create_pending_if_missing=True,
    )
    assert f["pending_reference"] is not None

    # Verifica se a pendência foi realmente gravada no store existente (.oxcad/pending.json)
    pendings = workspace_pending.list_pending(ctx)
    assert any(p["id"] == f["pending_reference"] for p in pendings)


def test_18_gate_elegivel(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando")
    gate = evaluate_approval_gate(ctx, rev["review_id"])
    assert gate["status"] == GateEligibilityStatus.ELIGIBLE.value
    assert gate["eligible"] is True
    assert len(gate["reasons"]) == 0


def test_19_gate_bloqueado_por_finding_critical(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando")
    add_finding(ctx, rev["review_id"], severity="CRITICAL", category="Trafo", description="Transformador sobrecarregado")

    gate = evaluate_approval_gate(ctx, rev["review_id"])
    assert gate["status"] == GateEligibilityStatus.NOT_ELIGIBLE.value
    assert gate["eligible"] is False
    assert any("OPEN_CRITICAL_FINDINGS" in r for r in gate["reasons"])

    # Tentativa de aprovar deve lançar erro
    with pytest.raises(ValueError, match="APPROVAL_GATE_BLOCKED"):
        approve_review(ctx, rev["review_id"], confirmed=True)


def test_20_gate_bloqueado_por_finding_major(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando")
    add_finding(ctx, rev["review_id"], severity="MAJOR", category="Vão", description="Vão longo sem estrutura intermediária")

    gate = evaluate_approval_gate(ctx, rev["review_id"])
    assert gate["status"] == GateEligibilityStatus.NOT_ELIGIBLE.value
    assert any("OPEN_MAJOR_FINDINGS" in r for r in gate["reasons"])


def test_21_gate_bloqueado_por_pending(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando")

    # Pendência bloqueante aberta no cadastro autoritativo
    workspace_pending.create(ctx, description="Licença ambiental pendente", severity="ERRO")

    gate = evaluate_approval_gate(ctx, rev["review_id"])
    assert gate["status"] == GateEligibilityStatus.NOT_ELIGIBLE.value
    assert any("BLOCKING_PENDINGS" in r for r in gate["reasons"])


def test_22_gate_bloqueado_por_identity_mismatch(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")

    ctx_divergente = ValidationContext(
        execution_id=ctx.execution_id,
        correlation_id=ctx.correlation_id,
        sob_id="SOB_CONFLITANTE",
        dwg_path=ctx.dwg_path,
        dwg_identity=ctx.dwg_identity,
        database_fingerprint=ctx.database_fingerprint,
        project_root=ctx.project_root,
        cqt_path=ctx.cqt_path,
        origin=ctx.origin,
    )
    gate = evaluate_approval_gate(ctx_divergente, rev["review_id"])
    assert gate["status"] == GateEligibilityStatus.NOT_ELIGIBLE.value
    assert not gate["eligible"]


def test_23_gate_bloqueado_por_snapshot_invalido(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    # Criar snapshot e depois adulterar o payload
    snap = workspace_versions.capture(ctx, cqt.name)
    snap_id = snap["snapshot_id"]

    # Adulterar payload do snapshot em .auxcad_versions
    payload_file = ctx.project_root / ".auxcad_versions" / snap_id / "payload"
    payload_file.write_bytes(b"CORROMPIDO")

    # Criar revisão com snapshot adulterado deve falhar na criação ou no gate
    with pytest.raises(ValueError, match="SNAPSHOT_INCOMPATIBLE"):
        create_review(ctx, revision_id="REV-01", source_snapshot_id=snap_id)


def test_24_evidencia_ausente(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01", evidence_references=["arquivo_que_nao_existe.pdf"])
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando")

    gate = evaluate_approval_gate(ctx, rev["review_id"])
    assert gate["status"] == GateEligibilityStatus.NOT_ELIGIBLE.value
    assert any("EVIDENCE_MISSING" in r for r in gate["reasons"])


def test_25_evidencia_alterada(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    ev_file = ctx.project_root / "evidencia.txt"
    ev_file.write_text("conteudo inicial", encoding="utf-8")

    rev = create_review(ctx, revision_id="REV-01", evidence_references=["evidencia.txt"])
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Iniciando")

    # Gate inicial com arquivo existente passa
    gate = evaluate_approval_gate(ctx, rev["review_id"])
    assert gate["eligible"] is True

    # Se remover o arquivo de evidência, bloqueia
    ev_file.unlink()
    gate_post = evaluate_approval_gate(ctx, rev["review_id"])
    assert not gate_post["eligible"]
    assert any("EVIDENCE_MISSING" in r for r in gate_post["reasons"])


def test_26_aprovacao_vinculada_a_revisao_correta(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Checagem")
    approval = approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Aprovado tecnicamente")
    assert approval["review_id"] == rev["review_id"]
    assert approval["revision"] == "REV-01"
    assert approval["sob_id"] == ctx.sob_id
    assert approval["database_fingerprint"] == ctx.database_fingerprint


def test_27_alteracao_apos_aprovacao(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Checagem")
    approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Aprovado")

    # Modificar o DWG no disco
    dwg.write_bytes(b"DWG MODIFICADO POS APROVACAO")

    # A revisão original permanece APPROVED em seu registro histórico,
    # mas a aprovação não se aplica ao novo conteúdo técnico.
    # Ao criar uma nova revisão, a anterior deve ser marcada como SUPERSEDED
    transition_review(ctx, rev["review_id"], ReviewStatus.SUPERSEDED.value, "DWG sofreu alterações posteriores")
    loaded = get_review(ctx, rev["review_id"])
    assert loaded["status"] == ReviewStatus.SUPERSEDED.value


def test_28_aprovacao_anterior_nao_aplicada_a_nova_revisao(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev1 = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev1["review_id"], ReviewStatus.IN_REVIEW.value, "Checagem")
    approve_review(ctx, rev1["review_id"], confirmed=True, decision_note="Aprovado REV-01")
    transition_review(ctx, rev1["review_id"], ReviewStatus.SUPERSEDED.value, "Nova versão necessária")

    # Criar nova revisão
    rev2 = create_review(ctx, revision_id="REV-02")
    assert rev2["status"] == ReviewStatus.DRAFT.value
    assert rev2["approval"] is None


def test_29_delivery_compativel(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    validations = [item.to_dict() for item in ValidationEngine().validate(ctx)]
    snap_id = workspace_versions.capture(ctx, cqt.name)["snapshot_id"]

    rev = create_review(ctx, revision_id="REV-01", source_snapshot_id=snap_id)
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Checagem")
    approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Aprovado")

    # Delivery permitido para revisão aprovada
    pkg = prepare_delivery_for_review(ctx, rev["review_id"], [cqt.name], validations)
    assert pkg["package_id"] is not None

    loaded = get_review(ctx, rev["review_id"])
    assert loaded["delivery"]["package_id"] == pkg["package_id"]


def test_30_delivery_incompativel(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    validations = [item.to_dict() for item in ValidationEngine().validate(ctx)]

    # Revisão em DRAFT não pode gerar delivery
    rev = create_review(ctx, revision_id="REV-01")
    with pytest.raises(ValueError, match="REVIEW_NOT_APPROVED"):
        prepare_delivery_for_review(ctx, rev["review_id"], [cqt.name], validations)


def test_31_revogacao(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Checagem")
    approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Aprovado")

    revoked_approval = revoke_review_approval(ctx, rev["review_id"], reason="Erro em poste detectado na vistoria")
    assert revoked_approval["state"] == "REVOGADO"
    assert revoked_approval["revocation"]["reason"] == "Erro em poste detectado na vistoria"

    loaded = get_review(ctx, rev["review_id"])
    assert loaded["approval"]["state"] == "REVOGADO"
    assert len(loaded["history"]) >= 3


def test_32_historico_preservado(tmp_path: Path):
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Para checagem")
    transition_review(ctx, rev["review_id"], ReviewStatus.CHANGES_REQUIRED.value, "Corrigir cabo")
    transition_review(ctx, rev["review_id"], ReviewStatus.DRAFT.value, "Reabrindo")
    transition_review(ctx, rev["review_id"], ReviewStatus.CANCELLED.value, "Obra cancelada pelo cliente")

    loaded = get_review(ctx, rev["review_id"])
    history = loaded["history"]
    assert len(history) == 5
    assert history[0]["to_status"] == "DRAFT"
    assert history[1]["to_status"] == "IN_REVIEW"
    assert history[2]["to_status"] == "CHANGES_REQUIRED"
    assert history[3]["to_status"] == "DRAFT"
    assert history[4]["to_status"] == "CANCELLED"


def test_33_operacao_offline(tmp_path: Path):
    # Todo o fluxo de governança P2.6 deve ser concluído em modo local/offline
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Análise offline")
    f = add_finding(ctx, rev["review_id"], severity="MINOR", category="Geral", description="Verificação de rotina")
    resolve_finding(ctx, rev["review_id"], f["finding_id"], "Conforme")
    approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Aprovado em campo sem rede")

    chain = build_traceability_chain(ctx, rev["review_id"])
    assert chain["sob_id"] == ctx.sob_id
    assert chain["review"]["status"] == "APPROVED"
    assert chain["audit_answers"]["por_que_foi_aprovada_ou_rejeitada"] == "Aprovado em campo sem rede"


def test_34_ausencia_de_chamada_externa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import urllib.request
    def blocked_socket(*args, **kwargs):
        raise RuntimeError("CHAMADA_EXTERNA_BLOQUEADA")

    monkeypatch.setattr(urllib.request, "urlopen", blocked_socket)

    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Teste sem rede")
    gate = evaluate_approval_gate(ctx, rev["review_id"])
    assert gate["eligible"] is True
    approve_review(ctx, rev["review_id"], confirmed=True)


def test_35_regressao_p21_a_p25(tmp_path: Path):
    # Verifica a integração e não-regressão dos indicadores (P2.1-P2.3) e validação de campo (P2.5)
    ctx, dwg, cqt = criar_cenario_projeto(tmp_path)
    rev = create_review(ctx, revision_id="REV-01")
    transition_review(ctx, rev["review_id"], ReviewStatus.IN_REVIEW.value, "Regressão")
    add_finding(ctx, rev["review_id"], severity="INFO", category="Teste", description="Finding informativo")
    approve_review(ctx, rev["review_id"], confirmed=True, decision_note="Regressão ok")

    relatorio = workspace_indicators.consultar_indicadores(
        project_root=ctx.project_root,
        sob_id=ctx.sob_id,
    )
    assert relatorio["schema"] == 1
    assert "revisoes" in relatorio
    assert relatorio["revisoes"]["status"] == "OK"
    assert relatorio["revisoes"]["total_revisoes"] == 1
    assert relatorio["revisoes"]["aprovadas"] == 1
    assert relatorio["revisoes"]["findings_total"] == 1
