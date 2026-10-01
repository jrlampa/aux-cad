import os
import sys
import pytest

# Injeta a raiz do projeto e as pastas de módulos no sys.path para garantir resolução universal
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)

for path in [ROOT_DIR, os.path.join(ROOT_DIR, "sob"), os.path.join(ROOT_DIR, "cqt"), os.path.join(ROOT_DIR, "ambiental")]:
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture
def simulated_host_protocol(monkeypatch):
    """Unit-only envelope for P0/P1 behavior; never proof of a real DWG."""
    monkeypatch.setattr(
        "workspace.workspace_context_cli._autocad_parent_verified",
        lambda acad_pid: True,
    )
    def envelope(dwg_path, sob_id, fingerprint="test-only-fingerprint",
                 execution_id="test-only-execution", correlation_id="test-only-correlation"):
        return {
            "contract_version": 1, "project_scope_status": "Bound",
            "dwg_path": str(dwg_path), "sob_id": sob_id,
            "dwg_identity": fingerprint, "context_generation": 1,
            "execution_id": execution_id, "correlation_id": correlation_id,
        }
    return envelope
