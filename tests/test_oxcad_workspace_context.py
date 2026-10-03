"""
Testes unitários do módulo centralizador de contexto compartilhado (Frente C).
Garante aderência aos contratos de autoridade de identidade, imutabilidade e conversão.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pytest

from workspace.workspace_context import (
    ProjectContext,
    build_integration_context,
    build_validation_context,
    extract_operator,
    normalize_sob_id,
    parse_project_context,
)


def test_normalize_sob_id():
    assert normalize_sob_id(None) == ""
    assert normalize_sob_id("") == ""
    assert normalize_sob_id("   ") == ""
    assert normalize_sob_id("A057526153") == "A057526153"
    assert normalize_sob_id("sob_A057526153") == "A057526153"
    assert normalize_sob_id("  SOB_b12345  ") == "B12345"


def test_extract_operator():
    args = argparse.Namespace(operator="eng_joao")
    assert extract_operator(args) == "eng_joao"

    args_empty = argparse.Namespace()
    op = extract_operator(args_empty, default="padrao")
    assert bool(op)


def test_project_context_is_bound():
    unbound = ProjectContext(
        sob_id="",
        dwg_path=None,
        database_fingerprint=None,
        project_root=Path.cwd(),
    )
    assert not unbound.is_bound

    bound = ProjectContext(
        sob_id="A057526153",
        dwg_path="c:/test/desenho.dwg",
        database_fingerprint="GUID-123",
        project_root=Path("c:/test"),
    )
    assert bound.is_bound


def test_project_context_to_validation_context(tmp_path: Path):
    dwg = tmp_path / "desenho.dwg"
    dwg.touch()

    ctx = ProjectContext(
        sob_id="A057526153",
        dwg_path=str(dwg),
        database_fingerprint="FINGERPRINT-ABC",
        project_root=tmp_path,
        revision_id="REV-02",
        origin="oxcad.delivery",
    )

    val_ctx = ctx.to_validation_context(host_verified=True)
    assert val_ctx.sob_id == "A057526153"
    assert val_ctx.dwg_path == str(dwg)
    assert val_ctx.database_fingerprint == "FINGERPRINT-ABC"
    assert val_ctx.dwg_identity == "FINGERPRINT-ABC"
    assert val_ctx.revision == "REV-02"
    assert val_ctx.origin == "oxcad.delivery"
    assert val_ctx.host_verified is True
    assert val_ctx.project_root == tmp_path


def test_project_context_to_integration_context(tmp_path: Path):
    dwg = tmp_path / "desenho.dwg"
    dwg.touch()

    ctx = ProjectContext(
        sob_id="A057526153",
        dwg_path=str(dwg),
        database_fingerprint="FINGERPRINT-ABC",
        project_root=tmp_path,
    )

    integ_ctx = ctx.to_integration_context()
    assert integ_ctx.sob_id == "A057526153"
    assert integ_ctx.dwg_path == str(dwg)
    assert integ_ctx.database_fingerprint == "FINGERPRINT-ABC"
    assert integ_ctx.validate_sovereignty("A057526153", "FINGERPRINT-ABC") is True


def test_project_context_to_integration_context_rejection(tmp_path: Path):
    # Fails if SOB is empty
    ctx_no_sob = ProjectContext(
        sob_id="",
        dwg_path=str(tmp_path / "a.dwg"),
        database_fingerprint="FP",
        project_root=tmp_path,
    )
    with pytest.raises(ValueError, match="sob_id obrigatorio"):
        ctx_no_sob.to_integration_context()

    # Fails if DWG is empty
    ctx_no_dwg = ProjectContext(
        sob_id="A057526153",
        dwg_path=None,
        database_fingerprint="FP",
        project_root=tmp_path,
    )
    with pytest.raises(ValueError, match="dwg_path obrigatorio"):
        ctx_no_dwg.to_integration_context()

    # Fails if Fingerprint is empty
    ctx_no_fp = ProjectContext(
        sob_id="A057526153",
        dwg_path=str(tmp_path / "a.dwg"),
        database_fingerprint="",
        project_root=tmp_path,
    )
    with pytest.raises(ValueError, match="database_fingerprint obrigatorio"):
        ctx_no_fp.to_integration_context()


def test_parse_project_context(tmp_path: Path):
    dwg = tmp_path / "desenho.dwg"
    dwg.touch()

    args = argparse.Namespace(
        sob="sob_A057526153",
        dwg=str(dwg),
        fingerprint="GUID-999",
        project_root=str(tmp_path),
        revision_id="REV-03",
    )

    ctx = parse_project_context(args, default_origin="oxcad.test")
    assert ctx.sob_id == "A057526153"
    assert ctx.dwg_path == str(dwg.resolve())
    assert ctx.database_fingerprint == "GUID-999"
    assert ctx.project_root == tmp_path.resolve()
    assert ctx.revision_id == "REV-03"
    assert ctx.origin == "oxcad.test"


def test_parse_project_context_inferred_root(tmp_path: Path):
    sub = tmp_path / "subpasta"
    sub.mkdir()
    dwg = sub / "desenho.dwg"
    dwg.touch()

    args = argparse.Namespace(
        sob="A057526153",
        dwg=str(dwg),
        fingerprint="GUID-999",
    )

    ctx = parse_project_context(args)
    assert ctx.project_root == sub.resolve()


def test_build_helpers(tmp_path: Path):
    dwg = tmp_path / "desenho.dwg"
    dwg.touch()

    args = argparse.Namespace(
        sob="A057526153",
        dwg=str(dwg),
        fingerprint="FP-1",
        project_root=str(tmp_path),
    )

    val = build_validation_context(args, default_origin="test.val")
    assert val.sob_id == "A057526153"
    assert val.origin == "test.val"

    integ = build_integration_context(args)
    assert integ.sob_id == "A057526153"
    assert integ.dwg_path == str(dwg.resolve())
