# -*- coding: utf-8 -*-
"""
Suíte de Testes Unitários da Camada de Ações do Workspace (aux cad).
Testa WorkspaceActionDispatcher: abertura de artefatos, localização no Explorer,
montagem e despacho de comandos para CQT, Orçamento e CPFC com contratos reais.
"""

from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_actions import WorkspaceActionDispatcher


@pytest.fixture
def mock_workspace(tmp_path):
    """Cria um contexto realista de Workspace para testes de ações."""
    sob_id = "A057349839"
    root = tmp_path / f"SOB_{sob_id}"
    root.mkdir()

    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG_TESTE")

    cqt = root / f"CQT_{sob_id}.xlsm"
    cqt.write_bytes(b"CQT_TESTE")

    orc = root / f"ORCAMENTO_{sob_id}.xlsx"
    orc.write_bytes(b"ORCAMENTO_TESTE")

    cpfc = root / f"PE_{sob_id}_CPFC_REN1.059.xlsx"
    cpfc.write_bytes(b"CPFC_TESTE")

    return ProjectWorkspace(
        sob_id=sob_id,
        sob_name=f"SOB_{sob_id}",
        root_dir=root,
        base_sigla="PE",
        dwg_principal=dwg,
        cqt_planilha=cqt,
        orcamento_planilha=orc,
        cpfc_planilha=cpfc,
        artefatos={
            "DWG": ProjectArtifact(chave="DWG", rotulo="DWG Principal", status=ArtifactStatus.EXISTE, caminho=dwg),
            "CQT": ProjectArtifact(chave="CQT", rotulo="CQT", status=ArtifactStatus.EXISTE, caminho=cqt),
            "ORCAMENTO": ProjectArtifact(chave="ORCAMENTO", rotulo="Orçamento", status=ArtifactStatus.EXISTE, caminho=orc),
            "CPFC": ProjectArtifact(chave="CPFC", rotulo="CPFC", status=ArtifactStatus.EXISTE, caminho=cpfc),
        }
    )


class TestAbrirArtefato:
    """Testes da ação ABRIR artefato no sistema operacional."""

    def test_abrir_artefato_existente_via_project_artifact(self, mock_workspace):
        art = mock_workspace.artefatos["DWG"]
        with patch("os.startfile", create=True) as mock_startfile:
            sucesso = WorkspaceActionDispatcher.abrir_artefato(art)
            assert sucesso is True
            mock_startfile.assert_called_once_with(str(art.caminho.resolve()))

    def test_abrir_artefato_existente_via_path(self, mock_workspace):
        caminho = mock_workspace.cqt_planilha
        with patch("os.startfile", create=True) as mock_startfile:
            sucesso = WorkspaceActionDispatcher.abrir_artefato(caminho)
            assert sucesso is True
            mock_startfile.assert_called_once_with(str(caminho.resolve()))

    def test_abrir_artefato_existente_via_str(self, mock_workspace):
        caminho_str = str(mock_workspace.cpfc_planilha)
        with patch("os.startfile", create=True) as mock_startfile:
            sucesso = WorkspaceActionDispatcher.abrir_artefato(caminho_str)
            assert sucesso is True
            mock_startfile.assert_called_once_with(str(Path(caminho_str).resolve()))

    def test_abrir_diretorio_existente(self, mock_workspace):
        pasta = mock_workspace.root_dir
        with patch("os.startfile", create=True) as mock_startfile:
            sucesso = WorkspaceActionDispatcher.abrir_artefato(pasta)
            assert sucesso is True
            mock_startfile.assert_called_once_with(str(pasta.resolve()))

    def test_abrir_artefato_inexistente_retorna_false(self, tmp_path):
        falso = tmp_path / "arquivo_inexistente.dwg"
        with patch("os.startfile", create=True) as mock_startfile:
            sucesso = WorkspaceActionDispatcher.abrir_artefato(falso)
            assert sucesso is False
            mock_startfile.assert_not_called()

    def test_abrir_artifact_sem_caminho_retorna_false(self):
        art = ProjectArtifact(chave="MEMORIAL", rotulo="Memorial", status=ArtifactStatus.NAO_EXISTE, caminho=None)
        with patch("os.startfile", create=True) as mock_startfile:
            sucesso = WorkspaceActionDispatcher.abrir_artefato(art)
            assert sucesso is False
            mock_startfile.assert_not_called()


class TestLocalizarArtefato:
    """Testes da ação LOCALIZAR artefato no Windows Explorer."""

    def test_localizar_arquivo_chama_explorer_select(self, mock_workspace):
        art = mock_workspace.artefatos["ORCAMENTO"]
        with patch("subprocess.Popen") as mock_popen:
            sucesso = WorkspaceActionDispatcher.localizar_artefato(art)
            assert sucesso is True
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert cmd.startswith("explorer.exe /select,")
            assert str(art.caminho.resolve()) in cmd

    def test_localizar_diretorio_chama_explorer_direto(self, mock_workspace):
        pasta = mock_workspace.root_dir
        with patch("subprocess.Popen") as mock_popen:
            sucesso = WorkspaceActionDispatcher.localizar_artefato(pasta)
            assert sucesso is True
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert cmd.startswith("explorer.exe ")
            assert "/select," not in cmd
            assert str(pasta.resolve()) in cmd

    def test_localizar_inexistente_retorna_false(self, tmp_path):
        falso = tmp_path / "nao_existe.xlsx"
        with patch("subprocess.Popen") as mock_popen:
            sucesso = WorkspaceActionDispatcher.localizar_artefato(falso)
            assert sucesso is False
            mock_popen.assert_not_called()

    def test_resolver_caminho_tipo_invalido_retorna_none(self):
        assert WorkspaceActionDispatcher._resolver_caminho(12345) is None

    def test_abrir_artefato_fallback_nao_windows(self, mock_workspace):
        art = mock_workspace.artefatos["DWG"]
        with patch("os.startfile", side_effect=AttributeError), patch("subprocess.Popen") as mock_popen:
            # Simula ambiente onde hasattr(os, "startfile") é falso
            with patch("workspace.workspace_actions.hasattr", return_value=False):
                sucesso = WorkspaceActionDispatcher.abrir_artefato(art)
                assert sucesso is True
                mock_popen.assert_called_once_with(["xdg-open", str(art.caminho.resolve())])

    def test_abrir_artefato_excecao_retorna_false(self, mock_workspace):
        art = mock_workspace.artefatos["DWG"]
        with patch("os.startfile", side_effect=OSError("Permissao negada")):
            sucesso = WorkspaceActionDispatcher.abrir_artefato(art)
            assert sucesso is False

    def test_localizar_artefato_fallback_nao_windows(self, mock_workspace):
        art = mock_workspace.artefatos["ORCAMENTO"]
        with patch("sys.platform", "linux"), patch("subprocess.Popen") as mock_popen:
            sucesso = WorkspaceActionDispatcher.localizar_artefato(art)
            assert sucesso is True
            mock_popen.assert_called_once_with(["xdg-open", str(art.caminho.parent.resolve())])

    def test_localizar_diretorio_fallback_nao_windows(self, mock_workspace):
        pasta = mock_workspace.root_dir
        with patch("sys.platform", "linux"), patch("subprocess.Popen") as mock_popen:
            sucesso = WorkspaceActionDispatcher.localizar_artefato(pasta)
            assert sucesso is True
            mock_popen.assert_called_once_with(["xdg-open", str(pasta.resolve())])

    def test_localizar_artefato_excecao_retorna_false(self, mock_workspace):
        art = mock_workspace.artefatos["ORCAMENTO"]
        with patch("subprocess.Popen", side_effect=OSError("Falha ao abrir Explorer")):
            sucesso = WorkspaceActionDispatcher.localizar_artefato(art)
            assert sucesso is False


class TestExecutarCQT:
    """Testes da montagem de comando e despacho do módulo CQT."""

    def test_montar_comando_cqt_padrao(self, mock_workspace, tmp_path):
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(mock_workspace, base_dir=tmp_path)
        assert cmd[0] == sys.executable
        assert "cqt_excel_manager.py" in cmd[1]
        # Arg 1: template (vazio ou template detectado)
        # Arg 2: cad_json ("")
        assert cmd[3] == ""
        # Arg 3: destino derivado da planilha do workspace
        assert cmd[4] == str(mock_workspace.cqt_planilha)

    def test_montar_comando_cqt_sem_planilha_previa(self, tmp_path):
        root = tmp_path / "SOB_NOVA"
        root.mkdir()
        ws = ProjectWorkspace(sob_id="NOVA123", sob_name="SOB_NOVA123", root_dir=root)

        cmd = WorkspaceActionDispatcher.montar_comando_cqt(ws, base_dir=tmp_path)
        # Destino derivado automaticamente no padrão CQT_{SOB}.xlsm
        assert cmd[4] == str(root / "CQT_NOVA123.xlsm")

    def test_montar_comando_cqt_customizado(self, mock_workspace, tmp_path):
        template = tmp_path / "custom_template.xlsm"
        template.write_bytes(b"tpl")
        cad_json = tmp_path / "cad_export.json"
        cad_json.write_text("{}", encoding="utf-8")
        dest_custom = tmp_path / "custom_dest.xlsm"

        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            mock_workspace,
            template_path=template,
            cad_json=cad_json,
            dest_file=dest_custom,
            base_dir=tmp_path
        )
        assert cmd[2] == str(template)
        assert cmd[3] == str(cad_json)
        assert cmd[4] == str(dest_custom)

    def test_executar_cqt_dispara_subprocesso(self, mock_workspace, tmp_path):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            proc = WorkspaceActionDispatcher.executar_cqt(mock_workspace, base_dir=tmp_path)
            assert proc is not None
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            assert args[0][0] == sys.executable
            assert "cqt_excel_manager.py" in args[0][1]
            assert kwargs["cwd"] == str(tmp_path)


class TestExecutarOrcamento:
    """Testes da montagem de comando e despacho do módulo Orçamento."""

    def test_montar_comando_orcamento_basico(self, mock_workspace, tmp_path):
        cmd = WorkspaceActionDispatcher.montar_comando_orcamento(mock_workspace, base_dir=tmp_path)
        assert cmd[0] == sys.executable
        assert "orcamento_manager.py" in cmd[1]
        assert "--projeto" in cmd
        assert cmd[cmd.index("--projeto") + 1] == mock_workspace.sob_id
        # Sem --json se não houver arquivo json
        assert "--json" not in cmd

    def test_montar_comando_orcamento_com_json_explicito(self, mock_workspace, tmp_path):
        json_file = tmp_path / "dados.json"
        cmd = WorkspaceActionDispatcher.montar_comando_orcamento(
            mock_workspace,
            dados_json=json_file,
            base_dir=tmp_path
        )
        assert "--json" in cmd
        assert cmd[cmd.index("--json") + 1] == str(json_file)

    def test_montar_comando_orcamento_com_json_detectado_no_workspace(self, mock_workspace, tmp_path):
        json_detectado = mock_workspace.root_dir / "orcamento_dados.json"
        json_detectado.write_text("{}", encoding="utf-8")

        cmd = WorkspaceActionDispatcher.montar_comando_orcamento(mock_workspace, base_dir=tmp_path)
        assert "--json" in cmd
        assert cmd[cmd.index("--json") + 1] == str(json_detectado)

    def test_executar_orcamento_dispara_subprocesso(self, mock_workspace, tmp_path):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            proc = WorkspaceActionDispatcher.executar_orcamento(mock_workspace, base_dir=tmp_path)
            assert proc is not None
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            assert args[0][0] == sys.executable
            assert "orcamento_manager.py" in args[0][1]
            assert kwargs["cwd"] == str(tmp_path)


class TestExecutarCPFC:
    """Testes da montagem de comando e despacho do módulo CPFC."""

    def test_montar_comando_cpfc(self, mock_workspace, tmp_path):
        cmd = WorkspaceActionDispatcher.montar_comando_cpfc(mock_workspace, base_dir=tmp_path)
        assert cmd[0] == sys.executable
        assert "cpfc_manager.py" in cmd[1]
        # sys.argv[1] = pasta_destino (str(root_dir))
        assert cmd[2] == str(mock_workspace.root_dir)
        # sys.argv[2] = projeto_inicial (sob_id)
        assert cmd[3] == mock_workspace.sob_id

    def test_executar_cpfc_dispara_subprocesso(self, mock_workspace, tmp_path):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            proc = WorkspaceActionDispatcher.executar_cpfc(mock_workspace, base_dir=tmp_path)
            assert proc is not None
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            assert args[0][0] == sys.executable
            assert "cpfc_manager.py" in args[0][1]
            assert args[0][2] == str(mock_workspace.root_dir)
            assert args[0][3] == mock_workspace.sob_id
            assert kwargs["cwd"] == str(tmp_path)
