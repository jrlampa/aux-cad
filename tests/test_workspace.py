# -*- coding: utf-8 -*-
"""
Suíte de Testes Unitários do Módulo Workspace da SOB/Projeto (aux cad).
Testa detecção de artefatos, identificação de SOB, tratamento de ausências,
diretório inexistente, múltiplos candidatos e determinismo.
"""

from pathlib import Path
import pytest

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_scanner import WorkspaceScanner
from workspace import carregar_workspace, abrir_workspace_dwg, detectar_workspace_diretorio


@pytest.fixture
def mock_sob_dir(tmp_path):
    """
    Cria uma estrutura completa e realista de SOB com múltiplos artefatos:
    - Raiz: SOB_A057349839
    - DWG: PE_A057349839_DESENHO.dwg
    - CROQUI/: fotos e geo
    - CROQUI/ANEXOS/: documentos GOMNET
    - Ambiental: CHECKLIST_A057349839.xlsx, MEMORIAL_DESCRITIVO_A057349839.docx, CROQUI_AMBIENTAL_A057349839.png
    - CQT: CQT_A057349839.xlsm
    - Orçamento: ORCAMENTO_A057349839.xlsx
    - CPFC: PE_A057349839_CPFC_REN1.059.xlsx
    - Unifilar: UNIFILAR_A057349839.json
    """
    sob_id = "A057349839"
    root = tmp_path / f"SOB_{sob_id}"
    root.mkdir()

    # 1. DWG
    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG_TESTE_BINARY_CONTENT_DUMMY_HEADER")

    # 2. CROQUI
    croqui = root / "CROQUI"
    croqui.mkdir()
    (croqui / "foto1.jpg").write_bytes(b"\xFF\xD8\xFF\xE0_TEST_JPEG")
    (croqui / "foto2.png").write_bytes(b"\x89PNG_TEST_PNG")
    (croqui / "campo.kmz").write_bytes(b"PK_TEST_KMZ")

    # 3. ANEXOS GOMNET
    anexos = croqui / "ANEXOS"
    anexos.mkdir()
    (anexos / "formulario_atendimento.pdf").write_bytes(b"%PDF_TEST")
    (anexos / "viabilidade.docx").write_bytes(b"PK_DOCX")

    # 4. Ambiental
    (root / f"CHECKLIST_{sob_id}.xlsx").write_bytes(b"PK_XLSX_CHECKLIST")
    (root / f"MEMORIAL_DESCRITIVO_{sob_id}.docx").write_bytes(b"PK_DOCX_MEMORIAL")
    (root / f"CROQUI_AMBIENTAL_{sob_id}.png").write_bytes(b"\x89PNG_SATELLITE")

    # 5. CQT
    (root / f"CQT_{sob_id}.xlsm").write_bytes(b"PK_XLSM_CQT")

    # 6. Orçamento
    (root / f"ORCAMENTO_{sob_id}.xlsx").write_bytes(b"PK_XLSX_ORCAMENTO")

    # 7. CPFC
    (root / f"PE_{sob_id}_CPFC_REN1.059.xlsx").write_bytes(b"PK_XLSX_CPFC")

    # 8. Unifilar
    (root / f"UNIFILAR_{sob_id}.json").write_text('{"ponto": "SG40995", "sucesso": true}', encoding="utf-8")

    return {
        "sob_id": sob_id,
        "root": root,
        "dwg": dwg,
        "croqui": croqui,
        "anexos": anexos,
    }


class TestWorkspaceBasics:
    """Testes de inicialização básica e entidades de domínio."""

    def test_project_artifact_properties(self, tmp_path):
        arquivo = tmp_path / "teste.dwg"
        arquivo.write_text("dummy")

        art = ProjectArtifact(
            chave="DWG",
            rotulo="Desenho Principal",
            status=ArtifactStatus.EXISTE,
            caminho=arquivo,
            detalhes={"tamanho": 5}
        )
        assert art.existe is True
        dados = art.para_dicionario()
        assert dados["chave"] == "DWG"
        assert dados["status"] == "EXISTE"
        assert dados["detalhes"]["tamanho"] == 5

    def test_project_artifact_inexistente(self, tmp_path):
        art = ProjectArtifact(
            chave="CQT",
            rotulo="Planilha CQT",
            status=ArtifactStatus.NAO_EXISTE,
            caminho=tmp_path / "inexistente.xlsx"
        )
        assert art.existe is False

    def test_workspace_status_de(self, tmp_path):
        ws = ProjectWorkspace(
            sob_id="A123456789",
            sob_name="SOB_A123456789",
            root_dir=tmp_path,
            artefatos={
                "DWG": ProjectArtifact(chave="DWG", rotulo="DWG", status=ArtifactStatus.EXISTE),
                "CQT": ProjectArtifact(chave="CQT", rotulo="CQT", status=ArtifactStatus.NAO_EXISTE)
            }
        )
        assert ws.status_de("DWG") == ArtifactStatus.EXISTE
        assert ws.status_de("CQT") == ArtifactStatus.NAO_EXISTE
        assert ws.status_de("OUTRO") == ArtifactStatus.NAO_EXISTE


class TestWorkspaceScanner:
    """Testes de detecção analítica e varredura do Workspace."""

    def test_extrair_sob_de_diferentes_textos(self):
        assert WorkspaceScanner.extrair_sob_de_texto("SOB_A057349839") == "A057349839"
        assert WorkspaceScanner.extrair_sob_de_texto("PE_A057349839_DESENHO.dwg") == "A057349839"
        assert WorkspaceScanner.extrair_sob_de_texto("CF_B987654321_DESENHO.dwg") == "B987654321"
        assert WorkspaceScanner.extrair_sob_de_texto("CHECKLIST_A057349839.xlsx") == "A057349839"
        assert WorkspaceScanner.extrair_sob_de_texto("A057349839") == "A057349839"
        assert WorkspaceScanner.extrair_sob_de_texto("pasta_qualquer") is None
        assert WorkspaceScanner.extrair_sob_de_texto("") is None

    def test_varredura_completa_de_workspace(self, mock_sob_dir):
        root = mock_sob_dir["root"]
        sob_id = mock_sob_dir["sob_id"]

        ws = WorkspaceScanner.scan(root)

        assert ws.sob_id == sob_id
        assert ws.sob_name == f"SOB_{sob_id}"
        assert ws.root_dir == root
        assert ws.base_sigla == "PE"

        # DWG
        assert ws.dwg_principal is not None
        assert ws.dwg_principal.name == f"PE_{sob_id}_DESENHO.dwg"
        assert ws.status_de("DWG") == ArtifactStatus.EXISTE

        # Croqui
        assert ws.croqui_dir is not None
        assert ws.status_de("CROQUI") == ArtifactStatus.EXISTE
        det_croqui = ws.artefatos["CROQUI"].detalhes
        assert det_croqui["total_arquivos"] == 3
        assert det_croqui["fotos"] == 2
        assert det_croqui["geometrias"] == 1

        # Documentos / Anexos GOMNET
        assert ws.documentos_dir is not None
        assert ws.status_de("DOCUMENTOS") == ArtifactStatus.EXISTE
        assert ws.artefatos["DOCUMENTOS"].detalhes["total_arquivos"] == 2

        # Ambiental
        assert ws.checklist_ambiental is not None
        assert ws.memorial_ambiental is not None
        assert ws.croqui_ambiental is not None
        assert ws.status_de("CHECKLIST_AMBIENTAL") == ArtifactStatus.EXISTE
        assert ws.status_de("MEMORIAL_AMBIENTAL") == ArtifactStatus.EXISTE
        assert ws.status_de("CROQUI_AMBIENTAL") == ArtifactStatus.EXISTE

        # CQT, Orçamento, CPFC, Unifilar
        assert ws.cqt_planilha is not None
        assert ws.status_de("CQT") == ArtifactStatus.EXISTE
        assert ws.orcamento_planilha is not None
        assert ws.status_de("ORCAMENTO") == ArtifactStatus.EXISTE
        assert ws.cpfc_planilha is not None
        assert ws.status_de("CPFC") == ArtifactStatus.EXISTE
        assert ws.unifilar_path is not None
        assert ws.status_de("UNIFILAR") == ArtifactStatus.EXISTE

        # Metadados
        assert ws.metadados["total_artefatos_detectados"] == 10
        assert ws.metadados["total_artefatos_monitorados"] == 10

    def test_tratamento_de_ausencia_total_de_artefatos(self, tmp_path):
        """Pasta vazia da SOB não deve falhar nem criar arquivos."""
        pasta_vazia = tmp_path / "SOB_A057000000"
        pasta_vazia.mkdir()

        ws = WorkspaceScanner.scan(pasta_vazia)

        assert ws.sob_id == "A057000000"
        assert ws.dwg_principal is None
        assert ws.croqui_dir is None
        assert ws.documentos_dir is None
        assert ws.status_de("DWG") == ArtifactStatus.NAO_EXISTE
        assert ws.status_de("CROQUI") == ArtifactStatus.NAO_EXISTE
        assert ws.status_de("DOCUMENTOS") == ArtifactStatus.NAO_EXISTE
        assert ws.status_de("CHECKLIST_AMBIENTAL") == ArtifactStatus.NAO_EXISTE
        assert ws.status_de("CQT") == ArtifactStatus.NAO_EXISTE
        assert ws.status_de("ORCAMENTO") == ArtifactStatus.NAO_EXISTE
        assert ws.metadados["total_artefatos_detectados"] == 0

        # Garante que nenhum arquivo foi criado pela varredura
        assert list(pasta_vazia.iterdir()) == []

    def test_diretorio_inexistente(self, tmp_path):
        pasta_fantasma = tmp_path / "PASTA_NAO_EXISTE"
        ws = WorkspaceScanner.scan(pasta_fantasma, sob_id="A999999999")

        assert ws.sob_id == "A999999999"
        assert ws.metadados["erro"] == "DIRETORIO_INEXISTENTE"
        assert ws.status_de("STATUS") == ArtifactStatus.NAO_EXISTE

    def test_multiplos_candidatos_dwg_prioriza_canonico(self, tmp_path):
        sob_id = "A057111222"
        root = tmp_path / f"SOB_{sob_id}"
        root.mkdir()

        # Cria 3 arquivos DWG candidatos
        (root / "outro_projeto.dwg").write_bytes(b"dwg1")
        (root / f"PE_{sob_id}_DESENHO.dwg").write_bytes(b"dwg_oficial")
        (root / f"RASCUNHO_{sob_id}.dwg").write_bytes(b"dwg_rascunho")

        ws = WorkspaceScanner.scan(root)
        assert ws.dwg_principal is not None
        assert ws.dwg_principal.name == f"PE_{sob_id}_DESENHO.dwg"

    def test_multiplos_candidatos_checklist_prioriza_mais_recente(self, tmp_path):
        sob_id = "A057333444"
        root = tmp_path / f"SOB_{sob_id}"
        root.mkdir()

        f_antigo = root / f"CHECKLIST_{sob_id}_100000.xlsx"
        f_antigo.write_bytes(b"antigo")
        f_recente = root / f"CHECKLIST_{sob_id}.xlsx"
        f_recente.write_bytes(b"recente")

        ws = WorkspaceScanner.scan(root)
        assert ws.checklist_ambiental is not None
        # Ambos possuem o padrão, scanner seleciona confiavelmente
        assert ws.status_de("CHECKLIST_AMBIENTAL") == ArtifactStatus.EXISTE

    def test_determinismo_da_varredura(self, mock_sob_dir):
        """Múltiplas chamadas sucessivas devem produzir exatamente o mesmo resultado."""
        root = mock_sob_dir["root"]

        resumo1 = WorkspaceScanner.scan(root).obter_resumo()
        resumo2 = WorkspaceScanner.scan(root).obter_resumo()

        assert resumo1 == resumo2


class TestWorkspaceHighLevelHelpers:
    """Testes dos utilitários de alto nível expostos em workspace."""

    def test_abrir_workspace_dwg(self, mock_sob_dir):
        dwg = mock_sob_dir["dwg"]
        ws = abrir_workspace_dwg(dwg)

        assert ws.sob_id == mock_sob_dir["sob_id"]
        assert ws.root_dir == mock_sob_dir["root"]
        assert ws.dwg_principal == dwg

    def test_carregar_workspace_com_root_explicito(self, mock_sob_dir):
        ws = carregar_workspace(mock_sob_dir["sob_id"], root_dir=mock_sob_dir["root"])
        assert ws.sob_id == mock_sob_dir["sob_id"]
        assert ws.status_de("DWG") == ArtifactStatus.EXISTE

    def test_detectar_workspace_diretorio(self, mock_sob_dir):
        ws = detectar_workspace_diretorio(mock_sob_dir["root"])
        assert ws.sob_id == mock_sob_dir["sob_id"]

    def test_formatar_relatorio_texto(self, mock_sob_dir):
        ws = WorkspaceScanner.scan(mock_sob_dir["root"])
        texto = ws.formatar_relatorio_texto()

        assert f"WORKSPACE — SOB {mock_sob_dir['sob_id']}" in texto
        assert "✓ Encontrado" in texto
        assert "Desenho DWG Principal" in texto
        assert "Checklist Ambiental (.xlsx)" in texto
        assert "Queda de Tensão BT (CQT)" in texto


class TestWorkspaceCLI:
    """Testes da interface de linha de comando (CLI) do Workspace."""

    def test_cli_modo_texto(self, mock_sob_dir, monkeypatch, capsys):
        from workspace import workspace_cli

        args = ["workspace_cli.py", "--dir", str(mock_sob_dir["root"])]
        monkeypatch.setattr("sys.argv", args)

        workspace_cli.main()
        captured = capsys.readouterr()

        assert f"WORKSPACE — SOB {mock_sob_dir['sob_id']}" in captured.out
        assert "✓ Encontrado" in captured.out

    def test_cli_modo_json(self, mock_sob_dir, monkeypatch, capsys):
        import json
        from workspace import workspace_cli

        args = ["workspace_cli.py", "--dir", str(mock_sob_dir["root"]), "--json"]
        monkeypatch.setattr("sys.argv", args)

        workspace_cli.main()
        captured = capsys.readouterr()

        dados = json.loads(captured.out)
        assert dados["sob_id"] == mock_sob_dir["sob_id"]
        assert dados["artefatos"]["DWG"]["status"] == "EXISTE"
        assert dados["artefatos"]["CROQUI"]["status"] == "EXISTE"
        assert dados["metadados"]["total_artefatos_detectados"] == 10

