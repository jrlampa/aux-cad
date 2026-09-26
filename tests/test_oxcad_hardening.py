# -*- coding: utf-8 -*-
"""
Testes de Endurecimento Operacional e Resiliência do OXCAD 0.4.0.
Cobre:
- Extração resiliente de JSON em saídas com poluição/warnings de terceiros;
- Supressão de warnings para manter stdout estritamente limpa;
- Integridade do contrato JSON sob saídas parciais ou com erro de processo;
- Propagação correta de versão 0.4.0 entre csproj e UI;
- Diagnóstico defensivo para ações e parâmetros nulos/inválidos;
- Comportamento determinístico de fallbacks de timeout e diretório raiz.
"""

import json
from pathlib import Path
import re
import subprocess
import sys
import pytest

from workspace.workspace_context_cli import extrair_contexto_operacional, executar_acao_operacional

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_versao_oxcad_0_5_3_propagada():
    """Valida que a versão 0.5.3 foi propagada no .csproj e no rodapé do .xaml."""
    csproj_path = ROOT_DIR / "oxcad" / "OxCadPaleta.csproj"
    xaml_path = ROOT_DIR / "oxcad" / "OxCadControl.xaml"

    assert csproj_path.exists()
    assert xaml_path.exists()

    csproj_content = csproj_path.read_text(encoding="utf-8")
    assert "<Version>0.5.3</Version>" in csproj_content
    assert "<AssemblyVersion>0.5.3.0</AssemblyVersion>" in csproj_content

    xaml_content = xaml_path.read_text(encoding="utf-8")
    assert "OXCAD 0.5.3 • AUX CAD" in xaml_content


def test_extracao_resiliente_json_com_warnings_externos():
    """Simula a lógica de ExtrairJsonValido implementada no C# garantindo robustez a ruído."""
    saida_poluida = (
        "UserWarning: urllib3 v2.0 only supports OpenSSL 1.1.1+\n"
        "DeprecationWarning: distutils is deprecated\n"
        "{\n"
        '  "sob_id": "SOB_123456",\n'
        '  "status": "Projeto identificado",\n'
        '  "artefatos": []\n'
        "}\n"
        "Process finished with exit code 0\n"
    )

    # Extrai o primeiro '{' e último '}'
    inicio = saida_poluida.find("{")
    fim = saida_poluida.rfind("}")
    assert inicio >= 0 and fim > inicio

    json_limpo = saida_poluida[inicio : fim + 1].strip()
    dados = json.loads(json_limpo)
    assert dados["sob_id"] == "SOB_123456"
    assert dados["status"] == "Projeto identificado"


def test_cli_stdout_completamente_limpa_de_warnings(tmp_path):
    """Executa workspace_context_cli.py via subprocesso e garante que a saída seja 100% JSON sem ruído."""
    dwg = tmp_path / "SOB_999999.dwg"
    dwg.touch()

    cmd = [
        sys.executable,
        str(ROOT_DIR / "workspace" / "workspace_context_cli.py"),
        "--dwg",
        str(dwg),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert proc.returncode == 0

    stdout_raw = proc.stdout.strip()
    assert stdout_raw.startswith("{")
    assert stdout_raw.endswith("}")

    # Não deve ter warnings nas primeiras linhas
    dados = json.loads(stdout_raw)
    assert dados["sob_id"] == "999999"
    assert "artefatos" in dados


def test_cli_acao_invalida_retorna_json_requer_especificacao():
    """Valida que uma ação não mapeada retorna exit code 1 e status 'Requer especificação' com JSON válido."""
    cmd = [
        sys.executable,
        str(ROOT_DIR / "workspace" / "workspace_context_cli.py"),
        "--acao",
        "acao_inexistente_xyz",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert proc.returncode == 1

    stdout_raw = proc.stdout.strip()
    dados = json.loads(stdout_raw)
    assert dados["sucesso"] is False
    assert dados["estado"] == "Requer especificação"
    assert "não homologada" in dados["mensagem"]


def test_cli_acao_unifilar_mantem_preservacao_autocad():
    """Valida que o Unifilar permanece classificado como Requer especificação (requer AutoCAD)."""
    resultado = executar_acao_operacional(acao="unifilar")
    assert resultado["sucesso"] is False
    assert resultado["estado"] == "Requer especificação"
    assert "UNIFILAR" in resultado["mensagem"]
    assert "PROTECAO" in resultado["mensagem"]


def test_endurecimento_workspace_service_cs_contem_metodos_resilientes():
    """Valida no código fonte de WorkspaceService.cs que todos os métodos de endurecimento existem."""
    cs_path = ROOT_DIR / "oxcad" / "WorkspaceService.cs"
    assert cs_path.exists()
    content = cs_path.read_text(encoding="utf-8")

    assert "ExtrairJsonValido" in content
    assert "EncerrarProcessoETodosOsFilhos" in content
    assert "ObterTimeoutMilissegundos" in content
    assert "taskkill.exe" in content
    assert "System.ComponentModel.Win32Exception" in content
    assert "AUXCAD_ROOT" in content
    assert "InstanciaSessionToken" in content
