# -*- coding: utf-8 -*-
"""
Suíte de Testes Unitários da Integração Workspace x AutoPranche (Fase 1).
Testa a resolução de metadados cadastrais V1 e a montagem/despacho do comando
pelo WorkspaceActionDispatcher conforme os contratos estritos aprovados.
"""

from datetime import datetime
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_actions import WorkspaceActionDispatcher
from prancha.autoprancha_core import (
    PROJETISTA_OFICIAL_IM3,
    MetadadosPranchaV1,
    resolver_metadados_prancha,
)


@pytest.fixture
def mock_workspace_prancha(tmp_path):
    """Cria um workspace mockado válido para testes de prancha."""
    sob_id = "A057349839"
    root = tmp_path / f"SOB_{sob_id}"
    root.mkdir()

    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG_DUMMY_CONTENT")

    return ProjectWorkspace(
        sob_id=sob_id,
        sob_name=f"SOB_{sob_id}",
        root_dir=root,
        base_sigla="PE",
        dwg_principal=dwg,
        artefatos={
            "DWG": ProjectArtifact(chave="DWG", rotulo="DWG Principal", status=ArtifactStatus.EXISTE, caminho=dwg),
        },
        metadados={
            "titulo": "Alimentador São Gonçalo - Reforma de Rede",
            "municipio": "São Gonçalo",
            "bairro": "Alcântara",
            "endereco": "Rua Yolanda Saad Abuzaid 150",
        },
    )


class TestResolucaoMetadadosPrancha:
    """Testes da camada de resolução controlada de metadados cadastrais V1."""

    def test_metadados_completos(self, mock_workspace_prancha):
        meta = resolver_metadados_prancha(mock_workspace_prancha)
        assert isinstance(meta, MetadadosPranchaV1)
        assert meta.sob_id == "A057349839"
        assert meta.titulo == "ALIMENTADOR SÃO GONÇALO - REFORMA DE REDE"
        assert meta.municipio == "SÃO GONÇALO"
        assert meta.bairro == "ALCÂNTARA"
        assert meta.endereco == "RUA YOLANDA SAAD ABUZAID 150"
        assert meta.folha == "1 de 1"
        assert meta.projetista == PROJETISTA_OFICIAL_IM3
        assert meta.data == datetime.now().strftime("%d/%m/%Y")

    def test_fallbacks_campos_ausentes(self, tmp_path):
        root = tmp_path / "SOB_A012345678"
        root.mkdir()
        ws_sem_meta = ProjectWorkspace(
            sob_id="A012345678",
            sob_name="SOB_A012345678",
            root_dir=root,
            metadados={},
        )
        meta = resolver_metadados_prancha(ws_sem_meta)
        assert meta.sob_id == "A012345678"
        # Contrato Estrito: sem fallback arbitrário de REDE DE DISTRIBUICAO
        assert meta.titulo == "-"
        assert meta.municipio == "-"
        assert meta.bairro == "-"
        assert meta.endereco == "-"
        assert meta.folha == "1 de 1"
        assert meta.projetista == "JONATAS LAMPA"

        # Garantir que não há strings proibidas
        d = meta.para_dicionario()
        for k, v in d.items():
            assert v != "X", f"Campo {k} não pode ser 'X'"
            assert v != "NULL", f"Campo {k} não pode ser 'NULL'"
            assert v != "DESCONHECIDO", f"Campo {k} não pode ser 'DESCONHECIDO'"
            assert v != "SEM INFORMAÇÃO", f"Campo {k} não pode ser 'SEM INFORMAÇÃO'"

    def test_sob_id_obrigatorio_ausente_ou_invalido(self, tmp_path):
        root = tmp_path / "SOB_INVALIDA"
        root.mkdir()

        ws_sem_sob = ProjectWorkspace(
            sob_id="",
            sob_name="SOB_SEM_ID",
            root_dir=root,
        )
        with pytest.raises(ValueError, match="sob_id obrigatório ausente"):
            resolver_metadados_prancha(ws_sem_sob)

        ws_desconhecida = ProjectWorkspace(
            sob_id="SOB-DESCONHECIDA",
            sob_name="SOB_DESCONHECIDA",
            root_dir=root,
        )
        with pytest.raises(ValueError, match="sob_id obrigatório ausente"):
            resolver_metadados_prancha(ws_desconhecida)

        with pytest.raises(ValueError, match="sob_id obrigatório ausente"):
            resolver_metadados_prancha(None)

    def test_contrato_especifico_cada_metadado(self, tmp_path):
        root = tmp_path / "SOB_A999"
        root.mkdir()

        # 1. SOB vem exclusivamente de workspace.sob_id
        ws1 = ProjectWorkspace(sob_id="A999888777", sob_name="SOB_A999888777", root_dir=root)
        meta1 = resolver_metadados_prancha(ws1)
        assert meta1.sob_id == "A999888777"

        # 2. Município disponível é utilizado
        ws2 = ProjectWorkspace(sob_id="A999888777", sob_name="SOB_A999888777", root_dir=root, metadados={"municipio": "Niterói"})
        assert resolver_metadados_prancha(ws2).municipio == "NITERÓI"

        # 3. Bairro disponível é utilizado
        ws3 = ProjectWorkspace(sob_id="A999888777", sob_name="SOB_A999888777", root_dir=root, metadados={"bairro": "Icaraí"})
        assert resolver_metadados_prancha(ws3).bairro == "ICARAÍ"

        # 4. Endereço disponível é utilizado
        ws4 = ProjectWorkspace(sob_id="A999888777", sob_name="SOB_A999888777", root_dir=root, metadados={"endereco": "Av. Sete de Setembro 50"})
        assert resolver_metadados_prancha(ws4).endereco == "AV. SETE DE SETEMBRO 50"

        # 5, 6, 7. Ausência resulta em '-'
        ws_vazio = ProjectWorkspace(sob_id="A999888777", sob_name="SOB_A999888777", root_dir=root, metadados={})
        meta_v = resolver_metadados_prancha(ws_vazio)
        assert meta_v.municipio == "-"
        assert meta_v.bairro == "-"
        assert meta_v.endereco == "-"

        # 8. Título não recebe automaticamente REDE DE DISTRIBUICAO sem regra contratual
        assert meta_v.titulo == "-"
        assert meta_v.titulo != f"REDE DE DISTRIBUICAO - {ws_vazio.sob_id}"

    def test_exportacao_json_metadados(self, mock_workspace_prancha, tmp_path):
        meta = resolver_metadados_prancha(mock_workspace_prancha)
        json_out = tmp_path / "prancha_contexto.json"
        p_ret = meta.gravar_json(json_out)
        assert p_ret.exists()
        import json
        carregado = json.loads(p_ret.read_text(encoding="utf-8"))
        assert carregado["SOB"] == "A057349839"
        assert carregado["PROJETISTA"] == "JONATAS LAMPA"
        assert carregado["FOLHA"] == "1 de 1"
        assert carregado["TITULO"] == "ALIMENTADOR SÃO GONÇALO - REFORMA DE REDE"


class TestWorkspaceActionDispatcherPrancha:
    """Testes de montagem e despacho de comandos do AutoPranche pelo Dispatcher."""

    def test_montar_comando_prancha_sucesso(self, mock_workspace_prancha):
        cmd = WorkspaceActionDispatcher.montar_comando_prancha(mock_workspace_prancha)
        assert isinstance(cmd, list)
        assert cmd[0] == sys.executable
        assert "autoprancha_core.py" in cmd[1]
        assert "--sob" in cmd
        assert "A057349839" in cmd
        assert "--root" in cmd
        assert str(mock_workspace_prancha.root_dir) in cmd
        assert "--dwg" in cmd
        assert str(mock_workspace_prancha.dwg_principal) in cmd

    def test_montar_comando_prancha_contexto_invalido(self, tmp_path):
        root = tmp_path / "SOB_SEM_ID"
        root.mkdir()
        ws_invalido = ProjectWorkspace(sob_id="", sob_name="", root_dir=root)

        with pytest.raises(ValueError, match="sob_id obrigatório ausente|não pode ser vazio"):
            WorkspaceActionDispatcher.montar_comando_prancha(ws_invalido)

        with pytest.raises(ValueError, match="sob_id obrigatório ausente"):
            WorkspaceActionDispatcher.montar_comando_prancha(None)

    def test_executar_prancha_despacho(self, mock_workspace_prancha):
        mock_proc = MagicMock(spec=subprocess.Popen)
        with patch.object(WorkspaceActionDispatcher, "_lancar_processo", return_value=mock_proc) as mock_lancar:
            proc = WorkspaceActionDispatcher.executar_prancha(mock_workspace_prancha)
            assert proc == mock_proc
            mock_lancar.assert_called_once()
            cmd_enviado = mock_lancar.call_args[0][0]
            assert "autoprancha_core.py" in cmd_enviado[1]
            assert "A057349839" in cmd_enviado
