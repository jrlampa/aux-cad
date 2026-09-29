import subprocess
from pathlib import Path


def test_dt02_semantic_graph_harness():
    repository = Path(__file__).resolve().parents[1]
    project = repository / "tests" / "dt02_harness" / "DT02Harness.csproj"
    result = subprocess.run(
        ["dotnet", "run", "--project", str(project), "--configuration", "Release"],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DT-02: 30 tests passed." in result.stdout
