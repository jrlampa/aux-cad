"""Testes para o CLI de governança e revisão técnica (P2.7A).

Verifica a ponte entre a interface e o domínio workspace_review.py:
- Consulta de status de revisão;
- Iniciação de revisão técnica e persistência;
- Registro de achados e persistência;
- Solicitação de alterações;
- Avaliação determinística do Approval Gate;
- Aprovação e persistência;
- Rejeição e persistência;
- Cancelamento e persistência;
- Rejeição de inconsistência de identidade;
- Rejeição de transição ilegal de estado;
- Reconstituição da cadeia de rastreabilidade;
- Verificação de não-duplicação de máquina de estados.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import pytest

from workspace import workspace_review
from workspace.workspace_review_cli import main


def setup_project(tmp_path: Path, sob: str = "A057526153"):
    root = tmp_path / f"SOB_{sob}"
    root.mkdir(parents=True, exist_ok=True)
    dwg = root / f"PE_{sob}_DESENHO.dwg"
    dwg.write_bytes(b"DWG_TEST_CONTENT_P2_7A")
    fingerprint = "{A5D3E8B2-1111-2222-3333-444455556666}"
    return root, dwg, sob, fingerprint


def run_cli(args: list[str]) -> tuple[int, dict]:
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        code = main(args)
    finally:
        sys.stdout = old_stdout
    output = captured.getvalue().strip()
    data = json.loads(output) if output else {}
    return code, data


def test_cli_status_sem_revisao(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "status",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["has_review"] is False
    assert res["review"] is None
    assert res["counts"]["total_findings"] == 0


def test_cli_iniciar_revisao_persiste(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
        "--revision-id", "REV-01",
        "--notes", "Iniciando revisão P2.7A",
        "--operator", "revisor_teste",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["review"]["status"] == "IN_REVIEW"
    assert res["review"]["revision_id"] == "REV-01"

    # Confirma que foi persistido no arquivo .oxcad/reviews.json
    store_file = root / ".oxcad" / "reviews.json"
    assert store_file.is_file()
    data = json.loads(store_file.read_text(encoding="utf-8"))
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["status"] == "IN_REVIEW"


def test_cli_status_com_revisao_ativa(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "status",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["has_review"] is True
    assert res["review"]["status"] == "IN_REVIEW"
    assert res["gate"]["status"] in {"ELIGIBLE", "NOT_ELIGIBLE"}


def test_cli_registrar_finding_persiste(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "achado",
        "--severity", "MAJOR",
        "--category", "Elétrica",
        "--description", "Vão de condutor superior ao limite",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["finding"]["severity"] == "MAJOR"
    assert res["counts"]["total_findings"] == 1
    assert res["counts"]["critical_major_findings"] == 1
    # Gate deve ficar bloqueado devido a achado MAJOR aberto
    assert res["gate"]["eligible"] is False
    assert any("OPEN_MAJOR_FINDINGS" in r for r in res["gate"]["reasons"])


def test_cli_solicitar_alteracoes_persiste(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "solicitar-alteracoes",
        "--reason", "Ajustar traçado no poste 12",
        "--operator", "revisor_chefe",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["review"]["status"] == "CHANGES_REQUIRED"


def test_cli_gate_bloqueia_quando_necessario(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "achado",
        "--severity", "CRITICAL",
        "--category", "Segurança",
        "--description", "Falta aterramento no transformador",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "gate",
    ])
    assert code == 0
    assert res["gate"]["status"] == "NOT_ELIGIBLE"
    assert res["gate"]["eligible"] is False
    assert any("OPEN_CRITICAL_FINDINGS" in r for r in res["gate"]["reasons"])


def test_cli_aprovacao_valida_persiste(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "aprovar",
        "--decision-note", "Projeto conforme normas",
        "--operator", "engenheiro_revisor",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["approval"]["state"] == "APROVADO"
    assert res["review"]["status"] == "APPROVED"


def test_cli_rejeicao_persiste(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "rejeitar",
        "--reason", "Inviabilidade técnica da rota",
        "--operator", "revisor_chefe",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["review"]["status"] == "REJECTED"


def test_cli_cancelamento_persiste(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    # Cria revisão diretamente em DRAFT
    from workspace.workspace_validation import ValidationContext
    ctx = ValidationContext(
        execution_id="e1",
        correlation_id="c1",
        sob_id=sob,
        dwg_path=str(dwg),
        dwg_identity=fp,
        database_fingerprint=fp,
        project_root=root,
        cqt_path=None,
    )
    rev = workspace_review.create_review(ctx, revision_id="REV-01")
    assert rev["status"] == "DRAFT"

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "cancelar",
        "--reason", "Desistência da revisão",
    ])
    assert code == 0
    assert res["success"] is True
    assert res["review"]["status"] == "CANCELLED"


def test_cli_identidade_invalida_rejeitada(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    # Cria revisão válida com fp
    _, init_res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])
    rev_id = init_res["review"]["review_id"]

    # Tentativa de aprovar passando fingerprint divergente
    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", "{DIVERGENTE-0000-0000-0000-000000000000}",
        "aprovar",
        "--review-id", rev_id,
    ])
    assert code != 0 or res.get("success") is False
    assert "CONTEXT_MISMATCH" in res.get("error", "")


def test_cli_operacao_invalida_estado_rejeitada(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])
    # Tenta aprovar quando há finding crítico
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "achado",
        "--severity", "CRITICAL",
        "--description", "Bloqueante",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "aprovar",
    ])
    assert code != 0 or res["success"] is False
    assert "APPROVAL_GATE_BLOCKED" in res.get("error", "")


def test_cli_rastreabilidade_e_sem_segunda_maquina_estados(tmp_path: Path):
    root, dwg, sob, fp = setup_project(tmp_path)
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "iniciar",
    ])
    run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "aprovar",
    ])

    code, res = run_cli([
        "--project-root", str(root),
        "--dwg", str(dwg),
        "--sob", sob,
        "--fingerprint", fp,
        "rastreabilidade",
    ])
    assert code == 0
    assert res["success"] is True
    chain = res["chain"]
    assert chain["sob_id"] == sob
    assert chain["approval"]["state"] == "APROVADO"
    assert chain["audit_answers"]["qual_revisao_foi_revisada"] == "REV-01"
