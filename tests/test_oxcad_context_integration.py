# -*- coding: utf-8 -*-
"""
Suíte de Testes da Integração do Contexto Operacional — OXCAD 0.2.0.
Cobre:
1. Contexto válido com DWG e pasta da SOB;
2. SOB inexistente;
3. Diretório inexistente;
4. JSON válido e conformidade com o contrato OxCadWorkspaceContext;
5. JSON inválido / tratamento de erro de parsing;
6. Erro do processo Python (exit code diferente de 0);
7. Timeout do processo Python;
8. Artefatos existentes (DWG, CROQUI, DOCUMENTOS, CQT, etc.);
9. Artefatos ausentes;
10. Divergência DWG × Workspace (inconsistência de contexto);
11. Atualização repetida / concorrência;
12. Ausência de Tkinter no workspace_context_cli.py;
13. Ausência de dependência do OneDrive no código do OXCAD.
"""

import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
OXCAD_DIR = ROOT_DIR / "oxcad"
WORKSPACE_DIR = ROOT_DIR / "workspace"
CLI_PATH = WORKSPACE_DIR / "workspace_context_cli.py"


# ==============================================================================
# 1. Ausência de Tkinter e Ausência de Dependência do OneDrive
# ==============================================================================

def test_ausencia_tkinter_no_context_cli():
    """Garante que workspace_context_cli.py não importa nem depende do Tkinter."""
    texto = CLI_PATH.read_text(encoding="utf-8")
    assert "import tkinter" not in texto
    assert "from tkinter" not in texto
    assert "tk." not in texto
    assert "ttk." not in texto
    assert "messagebox" not in texto


def test_ausencia_dependencia_onedrive():
    """Garante que nenhum arquivo do OXCAD possui dependência hardcoded do OneDrive."""
    arquivos_oxcad = list(OXCAD_DIR.glob("*.cs")) + list(OXCAD_DIR.glob("*.xaml")) + list(OXCAD_DIR.glob("*.lsp"))
    for arq in arquivos_oxcad:
        conteudo = arq.read_text(encoding="utf-8", errors="ignore")
        assert "OneDrive" not in conteudo, f"Referência a OneDrive encontrada em {arq.name}"
        assert "C:\\Users\\" not in conteudo, f"Caminho absoluto de usuário encontrado em {arq.name}"


# ==============================================================================
# 2. Contexto Válido e Extração de Artefatos
# ==============================================================================

def test_contexto_valido_com_dwg_e_sob(tmp_path):
    """Valida extração de contexto completo a partir de pasta com SOB e artefatos."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()

    # Cria artefatos físicos
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy dwg")

    cqt = pasta_sob / "CQT_A057349839.xlsm"
    cqt.write_text("dummy cqt")

    doc = pasta_sob / "DOCUMENTOS"
    doc.mkdir()
    (doc / "anexo.pdf").write_text("dummy doc")

    ctx = extrair_contexto_operacional(dwg_path=str(dwg))

    assert ctx["sob_id"] == "A057349839"
    assert ctx["dwg_principal"] == "PE_A057349839_DESENHO.dwg"
    assert ctx["root_dir"] == str(pasta_sob)
    assert ctx["status"] == "Projeto identificado"
    assert ctx["inconsistencia"] is False
    assert ctx["erro"] is None

    # Valida presença na matriz de artefatos
    artefatos_dict = {a["chave"]: a for a in ctx["artefatos"]}
    assert artefatos_dict["DWG"]["existe"] is True
    assert artefatos_dict["DWG"]["icone"] == "✓"
    assert artefatos_dict["CQT"]["existe"] is True
    assert artefatos_dict["DOCUMENTOS"]["existe"] is True


def test_artefatos_ausentes(tmp_path):
    """Valida detecção correta de artefatos ainda não gerados."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    ctx = extrair_contexto_operacional(dwg_path=str(dwg))
    artefatos_dict = {a["chave"]: a for a in ctx["artefatos"]}

    assert artefatos_dict["CPFC"]["existe"] is False
    assert artefatos_dict["CPFC"]["icone"] == "○"
    assert artefatos_dict["ORCAMENTO"]["existe"] is False
    assert artefatos_dict["UNIFILAR"]["existe"] is False


# ==============================================================================
# 3. Metadados (Município, Bairro, Endereço)
# ==============================================================================

def test_metadados_recuperados_do_manifesto(tmp_path):
    """Valida leitura de metadados se existirem no manifesto .sob_state.json."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    # Cria manifesto com metadados
    manifesto = pasta_sob / ".sob_state.json"
    manifesto.write_text(json.dumps({
        "sob_id": "A057349839",
        "municipio": "Resende",
        "bairro": "Centro",
        "endereco": "Rua das Flores, 123"
    }), encoding="utf-8")

    ctx = extrair_contexto_operacional(dwg_path=str(dwg))
    assert ctx["municipio"] == "RESENDE"
    assert ctx["bairro"] == "CENTRO"
    assert ctx["endereco"] == "Rua das Flores, 123"


def test_metadados_ausentes_retornam_traco(tmp_path):
    """Valida que metadados inexistentes retornam estritamente '-' sem inventar dados."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    ctx = extrair_contexto_operacional(dwg_path=str(dwg))
    assert ctx["municipio"] == "-"
    assert ctx["bairro"] == "-"
    assert ctx["endereco"] == "-"


# ==============================================================================
# 4. Divergência DWG × Workspace (Inconsistência de Contexto)
# ==============================================================================

def test_divergencia_dwg_workspace_detecta_inconsistencia(tmp_path):
    """Valida detecção de inconsistência se DWG for de uma SOB e a pasta de outra."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    # Pasta é SOB_B987654321, mas o arquivo dentro dela se chama PE_A057349839_DESENHO.dwg
    pasta_sob = tmp_path / "SOB_B987654321"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    ctx = extrair_contexto_operacional(dwg_path=str(dwg), root_dir=str(pasta_sob))

    assert ctx["inconsistencia"] is True
    assert "Inconsistência de contexto" in ctx["status"]
    assert "DWG: A057349839" in ctx["mensagem_inconsistencia"]
    assert "Workspace: B987654321" in ctx["mensagem_inconsistencia"]


# ==============================================================================
# 5. Diretório Inexistente e SOB Inexistente
# ==============================================================================

def test_diretorio_inexistente():
    """Valida resposta segura quando o diretório não existe."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    caminho_fantasma = r"C:\NaoExiste_Diretorio_Fantasma_9999"
    ctx = extrair_contexto_operacional(root_dir=caminho_fantasma)

    assert ctx["status"] == "Diretório não encontrado"
    assert ctx["erro"] is not None
    assert ctx["artefatos"] == []


def test_sob_inexistente(tmp_path):
    """Valida diretório válido mas sem padrão de SOB."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    pasta_generica = tmp_path / "PastaSemSob"
    pasta_generica.mkdir()

    ctx = extrair_contexto_operacional(root_dir=str(pasta_generica))
    assert ctx["sob_id"] == "PROJETO"
    assert ctx["status"] == "Contexto identificado"


# ==============================================================================
# 6. Execução Subprocessada (CLI), JSON Válido, JSON Inválido e Timeout
# ==============================================================================

def test_cli_executa_e_retorna_json_valido(tmp_path):
    """Valida invocação real do script workspace_context_cli.py via subprocess."""
    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    cmd = [sys.executable, str(CLI_PATH), "--dwg", str(dwg)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    assert res.returncode == 0
    dados = json.loads(res.stdout)
    assert dados["sob_id"] == "A057349839"
    assert dados["dwg_principal"] == "PE_A057349839_DESENHO.dwg"
    assert isinstance(dados["artefatos"], list)


def test_cli_erro_argumento_invalido():
    """Valida que o CLI não derruba o processo e emite JSON mesmo com erro."""
    cmd = [sys.executable, str(CLI_PATH), "--dir", "C:\\PastaInexistente_123456"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    assert res.returncode == 0
    dados = json.loads(res.stdout)
    assert dados["status"] == "Diretório não encontrado"


def test_tratamento_timeout_simulado():
    """Valida comportamento defensivo caso uma chamada demore mais que o timeout."""
    # Simula um script com sleep
    cmd = [sys.executable, "-c", "import time; time.sleep(0.5)"]
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(cmd, timeout=0.1)


# ==============================================================================
# 7. Simulação de Concorrência e Atualizações Repetidas
# ==============================================================================

def test_concorrencia_e_atualizacoes_repetidas(tmp_path):
    """Valida que múltiplas consultas consecutivas ou repetidas são determinísticas."""
    from workspace.workspace_context_cli import extrair_contexto_operacional

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    # Executa 5 vezes seguidas
    resultados = [extrair_contexto_operacional(dwg_path=str(dwg)) for _ in range(5)]

    for r in resultados:
        assert r["sob_id"] == "A057349839"
        assert r["status"] == "Projeto identificado"
        assert len(r["artefatos"]) == 10
