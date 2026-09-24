# -*- coding: utf-8 -*-
"""
Pacote Workspace da SOB/Projeto (AUX CAD).
Coordenação de contexto centralizado para projetos de engenharia da rede de distribuição.
"""

from pathlib import Path
from typing import Optional, Union

from workspace.workspace_core import (
    ArtifactStatus,
    ProjectArtifact,
    ProjectWorkspace,
)
from workspace.workspace_scanner import WorkspaceScanner


def carregar_workspace(
    sob_raw: str,
    root_dir: Optional[Union[str, Path]] = None,
    base: str = "PE",
) -> ProjectWorkspace:
    """
    Carrega ou descobre o Workspace a partir do identificador da SOB.
    Se root_dir não for informado, procura em pastas canônicas da máquina local.
    """
    sob_limpa = WorkspaceScanner.extrair_sob_de_texto(sob_raw) or sob_raw.strip().upper()

    if root_dir is not None:
        p_root = Path(root_dir).resolve()
    else:
        # Busca diretório canônico padrão
        possiveis_pastas = [
            Path.cwd() / f"SOB_{sob_limpa}",
            Path.cwd() / "sobs" / f"SOB_{sob_limpa}",
            Path.home() / "OneDrive" / "SOB" / f"SOB_{sob_limpa}",
            Path.cwd(),
        ]
        p_root = possiveis_pastas[-1]
        for cand in possiveis_pastas[:-1]:
            if cand.is_dir():
                p_root = cand
                break

    return WorkspaceScanner.scan(p_root, sob_id=sob_limpa)


def abrir_workspace_dwg(dwg_path: Union[str, Path]) -> ProjectWorkspace:
    """
    Carrega o Workspace diretamente a partir do arquivo DWG ativo no AutoCAD.
    Extrai a SOB do nome do DWG e define a pasta do DWG como raiz do Workspace.
    """
    p_dwg = Path(dwg_path).resolve()
    p_dir = p_dwg.parent if p_dwg.is_file() else p_dwg
    sob_detectada = WorkspaceScanner.extrair_sob_de_texto(p_dwg.name)
    return WorkspaceScanner.scan(p_dir, sob_id=sob_detectada)


def detectar_workspace_diretorio(root_dir: Union[str, Path]) -> ProjectWorkspace:
    """
    Varre e carrega o Workspace a partir de qualquer diretório informado.
    """
    return WorkspaceScanner.scan(root_dir)


__all__ = [
    "ArtifactStatus",
    "ProjectArtifact",
    "ProjectWorkspace",
    "WorkspaceScanner",
    "carregar_workspace",
    "abrir_workspace_dwg",
    "detectar_workspace_diretorio",
]
