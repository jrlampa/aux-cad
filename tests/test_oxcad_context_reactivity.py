import json
from pathlib import Path
import shutil
import subprocess

from workspace.workspace_context_cli import (
    _executar_acao_operacional_impl,
    _resolver_project_scope,
    extrair_contexto_operacional,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
GATE_HARNESS = (
    ROOT_DIR / "tests" / "oxcad_context_gate" / "OxCadContextGateHarness.csproj"
)


def _criar_projeto(root: Path, sob_id: str) -> Path:
    root.mkdir(parents=True)
    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob_id,
            "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )
    return dwg


def test_abrir_dwg_vinculado_resolve_sua_sob(tmp_path: Path):
    dwg_a = _criar_projeto(tmp_path / "SOB_A", "A057349839")

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg_a),
        sob_id_esperada="A057349839",
        require_project_scope=True,
    )

    assert _resolver_project_scope(dwg_a.parent, str(dwg_a), "A057349839")["status"] == "Bound"
    assert contexto["project_scope_resolved"] is False
    assert contexto["project_scope_status"] == "Unverified"


def test_trocar_para_outro_dwg_vinculado_muda_o_contexto(tmp_path: Path):
    dwg_a = _criar_projeto(tmp_path / "SOB_A", "A057349839")
    dwg_b = _criar_projeto(tmp_path / "SOB_B", "B123456789")

    contexto_a = extrair_contexto_operacional(
        dwg_path=str(dwg_a),
        sob_id_esperada="A057349839",
        require_project_scope=True,
    )
    contexto_b = extrair_contexto_operacional(
        dwg_path=str(dwg_b),
        sob_id_esperada="B123456789",
        require_project_scope=True,
    )

    assert contexto_a["project_scope_status"] == "Unverified"
    assert contexto_b["project_scope_status"] == "Unverified"
    assert _resolver_project_scope(dwg_b.parent, str(dwg_b), "B123456789")["status"] == "Bound"


def test_trocar_para_dwg_sem_vinculo_nao_reutiliza_sob_anterior(
    tmp_path: Path,
):
    dwg = tmp_path / "sem_vinculo" / "PE_A057349839_DESENHO.dwg"
    dwg.parent.mkdir()
    dwg.write_bytes(b"DWG")

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg), require_project_scope=True
    )

    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["status"] == "Contexto DWG não verificado"
    assert contexto["artefatos"] == []


def test_dwg_com_vinculo_invalido_nao_resolve_contexto(tmp_path: Path):
    dwg = _criar_projeto(tmp_path / "SOB_A", "A057349839")

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg),
        sob_id_esperada="SOB_INVÁLIDA",
        require_project_scope=True,
    )

    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["project_scope_resolved"] is False
    assert contexto["artefatos"] == []


def test_guard_real_cobre_troca_rapida_fechamento_saveas_e_resposta_atrasada():
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        import pytest
        pytest.skip(".NET SDK não disponível para o harness do guard C#")

    result = subprocess.run(
        [
            dotnet,
            "run",
            "--project",
            str(GATE_HARNESS),
            "--configuration",
            "Release",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "all assertions passed" in result.stdout


def test_eventos_autocad_disparam_refresh_e_invalida_documento_fechado():
    plugin = (ROOT_DIR / "oxcad" / "Plugin.cs").read_text(encoding="utf-8")
    control_path = ROOT_DIR / "oxcad" / "OxCadControl.xaml.cs"
    control = control_path.read_text(encoding="utf-8")

    assert "DocumentActivated += OnDocumentActivated" in plugin
    assert "DocumentCreated += OnDocumentCreated" in plugin
    assert "DocumentToBeDestroyed += OnDocumentToBeDestroyed" in plugin
    assert "DocumentDestroyed += OnDocumentDestroyed" in plugin
    assert "document.CommandEnded += OnDocumentCommandEnded" in plugin
    assert "NotificarDocumentoFechando" in plugin
    assert "_contextRefreshGate.Invalidate()" in control


def test_acao_depois_da_troca_usa_sob_do_dwg_atual(tmp_path: Path):
    dwg_a = _criar_projeto(tmp_path / "SOB_A", "A057349839")
    dwg_b = _criar_projeto(tmp_path / "SOB_B", "B123456789")

    contexto_atual = extrair_contexto_operacional(
        dwg_path=str(dwg_b),
        sob_id_esperada="B123456789",
        require_project_scope=True,
    )
    assert contexto_atual["project_scope_status"] == "Unverified"
    resultado = _executar_acao_operacional_impl(
        "tempo_iniciar",
        dwg_path=str(dwg_b),
        sob_id_esperada="B123456789",
        require_project_scope=True,
    )

    assert resultado["sucesso"] is True
    time_entry = json.loads(
        (dwg_b.parent / ".oxcad" / "time.json").read_text(encoding="utf-8")
    )
    assert time_entry["sob_id"] == "B123456789"
    assert not (dwg_a.parent / ".oxcad" / "time.json").exists()