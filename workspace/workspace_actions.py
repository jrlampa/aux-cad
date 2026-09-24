# -*- coding: utf-8 -*-
"""
Módulo de Ações e Despacho do Workspace da SOB/Projeto (aux cad).
Responsabilidade única: Despacho e encaminhamento de ações sobre artefatos existentes
e inicialização contextual de módulos especializados (CQT, Orçamento, CPFC).

Diretrizes arquiteturais:
- Camada fina: NÃO contém regras de engenharia nem cálculos.
- Reutiliza exclusivamente pontos de entrada consolidados e contratos reais.
- Execução não-bloqueante via subprocessos e integração nativa com o SO.
"""

import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union

from workspace.workspace_core import ProjectArtifact, ProjectWorkspace

# Raiz canônica do repositório aux cad
BASE_DIR = Path(__file__).resolve().parent.parent


class WorkspaceActionDispatcher:
    """
    Despachante único e centralizado de ações da camada de Workspace.
    Encaminha solicitações do projetista para o sistema operacional ou para os módulos
    especialistas (CQT, Orçamento, CPFC) sem duplicação de lógica ou bloqueio de interface.
    """

    @staticmethod
    def _resolver_caminho(alvo: Union[ProjectArtifact, Path, str]) -> Optional[Path]:
        """Extrai e normaliza o caminho a partir de um artefato ou string/Path."""
        if isinstance(alvo, ProjectArtifact):
            return alvo.caminho
        if isinstance(alvo, (str, Path)):
            return Path(alvo)
        return None

    @classmethod
    def abrir_artefato(cls, artefato: Union[ProjectArtifact, Path, str]) -> bool:
        """
        Abre o arquivo ou diretório no aplicativo padrão do Windows de forma não-bloqueante.
        Não copia, não altera e valida a existência física antes da chamada.
        Retorna True em caso de sucesso, ou False se o alvo não existir.
        """
        caminho = cls._resolver_caminho(artefato)
        if not caminho or not caminho.exists():
            return False

        caminho_res = caminho.resolve()
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(caminho_res))
            else:
                # Fallback para ambientes não-Windows (ex: suíte CI em Linux)
                subprocess.Popen(["xdg-open", str(caminho_res)])
            return True
        except Exception as err:
            print(f"[WorkspaceActionDispatcher] Erro ao abrir artefato: {err}")
            return False

    @classmethod
    def localizar_artefato(cls, artefato: Union[ProjectArtifact, Path, str]) -> bool:
        """
        Abre o Windows Explorer com foco e seleção sobre o arquivo, ou abre o diretório.
        Valida existência prévia sem disparar aplicativos associados.
        Retorna True em caso de sucesso, ou False se o alvo não existir.
        """
        caminho = cls._resolver_caminho(artefato)
        if not caminho or not caminho.exists():
            return False

        caminho_res = caminho.resolve()
        try:
            if sys.platform == "win32":
                if caminho_res.is_file():
                    # Formato oficial do Windows: explorer.exe /select,"C:\...\arquivo.ext"
                    cmd = f'explorer.exe /select,"{caminho_res}"'
                    subprocess.Popen(cmd)
                else:
                    # Formato para diretório: explorer.exe "C:\...\diretorio"
                    cmd = f'explorer.exe "{caminho_res}"'
                    subprocess.Popen(cmd)
            else:
                # Fallback não-Windows para testes
                alvo = str(caminho_res.parent if caminho_res.is_file() else caminho_res)
                subprocess.Popen(["xdg-open", alvo])
            return True
        except Exception as err:
            print(f"[WorkspaceActionDispatcher] Erro ao localizar artefato: {err}")
            return False

    @classmethod
    def montar_comando_cqt(
        cls,
        workspace: ProjectWorkspace,
        template_path: Optional[Union[str, Path]] = None,
        cad_json: Optional[Union[str, Path]] = None,
        dest_file: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do módulo CQT conforme o contrato real
        de cqt/cqt_excel_manager.py: [template] [cad_json] [dest_file].
        O caminho de destino é derivado contextualmente do Workspace.
        """
        raiz = Path(base_dir or BASE_DIR)
        cqt_script = raiz / "cqt" / "cqt_excel_manager.py"

        # 1. Destino derivado do Workspace (planilha existente ou CQT_{SOB}.xlsm na raiz da SOB)
        if dest_file:
            dest_final = Path(dest_file)
        elif workspace.cqt_planilha and workspace.cqt_planilha.exists():
            dest_final = workspace.cqt_planilha
        else:
            dest_final = workspace.root_dir / f"CQT_{workspace.sob_id}.xlsm"

        # 2. Template CQT
        if template_path:
            tpl_final = Path(template_path)
        else:
            tpl_cand = raiz / "modelos" / "cqt_modelo.xlsm"
            tpl_final = tpl_cand if tpl_cand.exists() else None

        # 3. JSON de intercâmbio do CAD
        json_final = str(cad_json) if cad_json else ""

        return [
            sys.executable,
            str(cqt_script),
            str(tpl_final) if tpl_final else "",
            json_final,
            str(dest_final),
        ]

    @classmethod
    def executar_cqt(
        cls,
        workspace: ProjectWorkspace,
        template_path: Optional[Union[str, Path]] = None,
        cad_json: Optional[Union[str, Path]] = None,
        dest_file: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> subprocess.Popen:
        """
        Inicia o módulo CQT em subprocesso desacoplado, sem travar a interface do Workspace.
        """
        cmd = cls.montar_comando_cqt(
            workspace=workspace,
            template_path=template_path,
            cad_json=cad_json,
            dest_file=dest_file,
            base_dir=base_dir,
        )
        return cls._lancar_processo(cmd, cwd=base_dir or BASE_DIR)

    @classmethod
    def montar_comando_orcamento(
        cls,
        workspace: ProjectWorkspace,
        dados_json: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do módulo Orçamento conforme o contrato
        de orcamento/orcamento_manager.py: --projeto <SOB> [--json <caminho>].
        Não inventa dados de empreiteira ou território, permitindo que a GUI gerencie.
        """
        raiz = Path(base_dir or BASE_DIR)
        orc_script = raiz / "orcamento" / "orcamento_manager.py"

        cmd = [
            sys.executable,
            str(orc_script),
            "--projeto",
            workspace.sob_id,
        ]

        json_alvo = dados_json
        if not json_alvo:
            # Verifica se há dados CAD exportados previamente
            cand_json = workspace.root_dir / "orcamento_dados.json"
            if cand_json.exists() and cand_json.is_file():
                json_alvo = cand_json
            else:
                art = workspace.artefatos.get("ORCAMENTO")
                if art and art.caminho and art.caminho.suffix.lower() == ".json" and art.caminho.exists():
                    json_alvo = art.caminho

        if json_alvo:
            cmd.extend(["--json", str(json_alvo)])

        return cmd

    @classmethod
    def executar_orcamento(
        cls,
        workspace: ProjectWorkspace,
        dados_json: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> subprocess.Popen:
        """
        Inicia a GUI do módulo de Orçamento em subprocesso desacoplado.
        """
        cmd = cls.montar_comando_orcamento(
            workspace=workspace,
            dados_json=dados_json,
            base_dir=base_dir,
        )
        return cls._lancar_processo(cmd, cwd=base_dir or BASE_DIR)

    @classmethod
    def montar_comando_cpfc(
        cls,
        workspace: ProjectWorkspace,
        base_dir: Optional[Path] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do módulo CPFC conforme o contrato
        de cpfc/cpfc_manager.py: [pasta_destino] [projeto_inicial].
        """
        raiz = Path(base_dir or BASE_DIR)
        cpfc_script = raiz / "cpfc" / "cpfc_manager.py"

        return [
            sys.executable,
            str(cpfc_script),
            str(workspace.root_dir),
            workspace.sob_id,
        ]

    @classmethod
    def executar_cpfc(
        cls,
        workspace: ProjectWorkspace,
        base_dir: Optional[Path] = None,
    ) -> subprocess.Popen:
        """
        Inicia a interface do CPFC pré-apontando para a pasta da SOB e o identificador do projeto.
        """
        cmd = cls.montar_comando_cpfc(workspace=workspace, base_dir=base_dir)
        return cls._lancar_processo(cmd, cwd=base_dir or BASE_DIR)

    @staticmethod
    def _lancar_processo(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.Popen:
        """
        Lança subprocesso desvinculado para evitar travamento da aplicação ou console chamador.
        """
        dir_exec = str(cwd or BASE_DIR)
        kwargs: Dict[str, Any] = {"cwd": dir_exec}

        if sys.platform == "win32":
            creation_flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            if creation_flag:
                kwargs["creationflags"] = creation_flag

        return subprocess.Popen(cmd, **kwargs)
