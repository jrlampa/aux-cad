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

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Union

from workspace.workspace_core import ProjectArtifact, ProjectWorkspace
from common.logging_config import get_logger

logger = get_logger("oxcad.workspace.actions")

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
    def abrir_artefato(
        cls,
        artefato: Union[ProjectArtifact, Path, str],
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
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
            logger.info(
                f"Abrindo artefato físico: {caminho_res.name}",
                extra={
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "dwg_path": str(caminho_res),
                    "action": "abrir",
                }
            )
            if hasattr(os, "startfile"):
                os.startfile(str(caminho_res))
            else:
                # Fallback para ambientes não-Windows (ex: suíte CI em Linux)
                subprocess.Popen(["xdg-open", str(caminho_res)])
            return True
        except Exception as err:
            logger.error(
                f"Erro ao abrir artefato {caminho_res}: {err}",
                exc_info=True,
                extra={
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "dwg_path": str(caminho_res),
                    "action": "abrir",
                }
            )
            return False

    @classmethod
    def localizar_artefato(
        cls,
        artefato: Union[ProjectArtifact, Path, str],
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
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
            logger.info(
                f"Localizando artefato no Explorer: {caminho_res.name}",
                extra={
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "dwg_path": str(caminho_res),
                    "action": "localizar",
                }
            )
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
            logger.error(
                f"Erro ao localizar artefato {caminho_res}: {err}",
                exc_info=True,
                extra={
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "dwg_path": str(caminho_res),
                    "action": "localizar",
                }
            )
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

        Validações:
        1. workspace deve ser válido;
        2. workspace.sob_id deve existir e não ser vazio;
        3. workspace.root_dir deve existir no disco;
        4. entradas inválidas geram ValueError ou FileNotFoundError controlado.
        """
        if not workspace:
            raise ValueError("Contexto de Workspace inválido: workspace não informado.")

        if not hasattr(workspace, "sob_id") or workspace.sob_id is None:
            raise ValueError("Contexto de Workspace inválido: sob_id obrigatório ausente.")

        sob_str = str(workspace.sob_id).strip().upper()
        if not sob_str:
            raise ValueError("Contexto de Workspace inválido: sob_id não pode ser vazio.")

        if not hasattr(workspace, "root_dir") or not workspace.root_dir:
            raise ValueError("Contexto de Workspace inválido: root_dir obrigatório.")

        root_path = Path(workspace.root_dir)
        if not root_path.exists():
            raise FileNotFoundError(f"Diretório raiz da SOB não existe no disco: {workspace.root_dir}")

        raiz = Path(base_dir or BASE_DIR)
        cqt_script = raiz / "cqt" / "cqt_excel_manager.py"
        if not cqt_script.exists():
            cqt_script = Path(BASE_DIR) / "cqt" / "cqt_excel_manager.py"

        if not cqt_script.exists():
            raise FileNotFoundError(f"Script do módulo CQT não encontrado em: {cqt_script}")

        # 1. Template CQT oficial
        if template_path:
            tpl_path = Path(template_path)
            if not tpl_path.exists():
                raise FileNotFoundError(f"Modelo CQT especificado não encontrado: {template_path}")
            tpl_final = tpl_path
        else:
            tpl_cand = raiz / "modelos" / "cqt_modelo.xlsm"
            if not tpl_cand.exists():
                tpl_cand = Path(BASE_DIR) / "modelos" / "cqt_modelo.xlsm"
            if not tpl_cand.exists():
                raise FileNotFoundError(f"Modelo CQT oficial não encontrado em: {tpl_cand}")
            tpl_final = tpl_cand

        # 2. JSON de intercâmbio do CAD (dados de engenharia)
        json_final = ""
        if cad_json and Path(cad_json).exists():
            json_final = str(Path(cad_json))
        elif (root_path / "cqt_cad_input.json").exists():
            json_final = str(root_path / "cqt_cad_input.json")

        # 3. Destino derivado do Workspace (dest_file explícito, ou cqt_planilha existente, ou CQT_{SOB}.xlsm na raiz da SOB)
        if dest_file:
            dest_final = Path(dest_file)
        elif getattr(workspace, "cqt_planilha", None) and Path(workspace.cqt_planilha).exists():
            dest_final = Path(workspace.cqt_planilha)
        else:
            dest_final = root_path / f"CQT_{sob_str}.xlsm"

        return [
            sys.executable,
            str(cqt_script),
            str(tpl_final),
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
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
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
        return cls._lancar_processo(
            cmd,
            cwd=base_dir or BASE_DIR,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )

    @classmethod
    def montar_comando_orcamento(
        cls,
        workspace: ProjectWorkspace,
        dados_json: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do módulo Orçamento conforme o contrato
        de orcamento/orcamento_manager.py: --projeto <SOB> [--municipio <MUN>] [--json <caminho>].

        Validações:
        1. workspace deve ser válido;
        2. workspace.sob_id deve existir e não ser vazio;
        3. entradas inválidas geram ValueError controlado.

        Propagação de Contexto:
        - sob_id vem exclusivamente de workspace.sob_id;
        - municipio é propagado a partir de workspace.metadados quando disponível;
        - JSON de engenharia CAD existente é preservado e encaminhado via --json.
        """
        if not workspace or not hasattr(workspace, "sob_id") or not workspace.sob_id:
            raise ValueError("Contexto de Workspace inválido: sob_id obrigatório ausente.")

        sob_str = str(workspace.sob_id).strip().upper()
        if not sob_str:
            raise ValueError("Contexto de Workspace inválido: sob_id não pode ser vazio.")

        raiz = Path(base_dir or BASE_DIR)
        orc_script = raiz / "orcamento" / "orcamento_manager.py"
        if not orc_script.exists():
            orc_script = Path(BASE_DIR) / "orcamento" / "orcamento_manager.py"

        cmd = [
            sys.executable,
            str(orc_script),
            "--projeto",
            sob_str,
        ]

        # Propagação contextual de município quando disponível nos metadados
        metadados = getattr(workspace, "metadados", None) or {}
        municipio = metadados.get("municipio") or metadados.get("cidade")
        if municipio and str(municipio).strip():
            cmd.extend(["--municipio", str(municipio).strip()])

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
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        Inicia a GUI do módulo de Orçamento em subprocesso desacoplado.
        """
        cmd = cls.montar_comando_orcamento(
            workspace=workspace,
            dados_json=dados_json,
            base_dir=base_dir,
        )
        return cls._lancar_processo(
            cmd,
            cwd=base_dir or BASE_DIR,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )

    @classmethod
    def montar_comando_cpfc(
        cls,
        workspace: ProjectWorkspace,
        dados_json: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do módulo CPFC conforme o contrato
        de cpfc/cpfc_manager.py: [pasta_destino] [projeto_inicial] ou [arquivo.json].

        Validações:
        1. workspace deve ser válido;
        2. workspace.sob_id deve existir;
        3. workspace.sob_id não pode ser vazio;
        4. entradas inválidas geram ValueError controlado.

        Propagação de Contexto:
        - sob_id vem exclusivamente de workspace.sob_id;
        - root_dir vem exclusivamente de workspace.root_dir;
        - municipio e endereco podem ser obtidos de workspace.metadados;
        - Se dados_json não for fornecido e houver metadados (municipio/endereco),
          cria um arquivo JSON temporário padronizado para intercâmbio com o CPFC.
        """
        if not workspace or not hasattr(workspace, "sob_id") or not workspace.sob_id:
            raise ValueError("Contexto de Workspace inválido: sob_id obrigatório ausente.")

        sob_str = str(workspace.sob_id).strip().upper()
        if not sob_str:
            raise ValueError("Contexto de Workspace inválido: sob_id não pode ser vazio.")

        raiz = Path(base_dir or BASE_DIR)
        cpfc_script = raiz / "cpfc" / "cpfc_manager.py"
        if not cpfc_script.exists():
            cpfc_script = Path(BASE_DIR) / "cpfc" / "cpfc_manager.py"

        # Se um JSON explícito foi fornecido, utiliza diretamente
        if dados_json:
            return [
                sys.executable,
                str(cpfc_script),
                str(dados_json),
            ]

        # Verifica se há metadados contextuais opcionais a propagar
        metadados = getattr(workspace, "metadados", None) or {}
        municipio = metadados.get("municipio")
        endereco = metadados.get("endereco")

        if municipio or endereco:
            # Cria JSON temporário de intercâmbio com ciclo de vida controlado
            payload: Dict[str, Any] = {
                "projeto": sob_str,
                "pasta_destino": str(workspace.root_dir),
            }
            if municipio:
                payload["municipio"] = str(municipio).strip()
            if endereco:
                payload["endereco"] = str(endereco).strip()

            prefixo = f"cpfc_contexto_{sob_str}_"
            temp_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix=prefixo,
                delete=False,
                encoding="utf-8",
            )
            try:
                json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            finally:
                temp_file.close()

            return [
                sys.executable,
                str(cpfc_script),
                str(Path(temp_file.name).resolve()),
            ]

        # Caso padrão sem metadados adicionais: passagem direta de pasta e sob_id
        return [
            sys.executable,
            str(cpfc_script),
            str(workspace.root_dir),
            sob_str,
        ]

    @classmethod
    def executar_cpfc(
        cls,
        workspace: ProjectWorkspace,
        dados_json: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        Inicia a interface do CPFC pré-apontando para a pasta da SOB e o identificador do projeto.
        """
        cmd = cls.montar_comando_cpfc(
            workspace=workspace,
            dados_json=dados_json,
            base_dir=base_dir,
        )
        return cls._lancar_processo(
            cmd,
            cwd=base_dir or BASE_DIR,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )

    @classmethod
    def montar_comando_sob(
        cls,
        workspace: Optional[ProjectWorkspace] = None,
        base_dir: Optional[Path] = None,
        resultado_json: Optional[Union[str, Path]] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do preparador oficial SOB conforme
        o contrato de sob/sob_launcher_gui.py.
        """
        raiz = Path(base_dir or BASE_DIR)
        sob_script = raiz / "sob" / "sob_launcher_gui.py"
        if not sob_script.exists():
            raise FileNotFoundError(f"Launcher oficial da SOB não encontrado em: {sob_script}")

        cmd = [
            sys.executable,
            str(sob_script),
        ]
        if resultado_json:
            cmd.extend(["--resultado-json", str(resultado_json)])
        return cmd

    @classmethod
    def executar_sob(
        cls,
        workspace: Optional[ProjectWorkspace] = None,
        base_dir: Optional[Path] = None,
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        resultado_json: Optional[Union[str, Path]] = None,
    ) -> subprocess.Popen:
        """
        Inicia o diálogo interativo do Preparador de SOB oficial em subprocesso desacoplado,
        sem bloquear a interface do Workspace.
        """
        cmd = cls.montar_comando_sob(
            workspace=workspace,
            base_dir=base_dir,
            resultado_json=resultado_json,
        )
        proc = cls._lancar_processo(
            cmd,
            cwd=base_dir or BASE_DIR,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )
        if resultado_json:
            setattr(proc, "resultado_json_path", Path(resultado_json).resolve())
        return proc

    @classmethod
    def montar_comando_ambiental(
        cls,
        workspace: ProjectWorkspace,
        template_path: Optional[Union[str, Path]] = None,
        pts_json: Optional[Union[str, Path]] = None,
        boxes_txt: Optional[Union[str, Path]] = None,
        fuso: int = 23,
        base_dir: Optional[Path] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do módulo Ambiental conforme o contrato
        de ambiental/memorial_ambiental_generator.py:
        [template_docx] [pts_json] [boxes_txt] [fuso_utm] [out_dir].
        O diretório de saída é contextualmente direcionado para a pasta da SOB (workspace.root_dir).
        """
        if not workspace:
            raise ValueError("Contexto de Workspace inválido: workspace não informado.")

        if not hasattr(workspace, "sob_id") or not workspace.sob_id:
            raise ValueError("Contexto de Workspace inválido: sob_id obrigatório ausente.")

        sob_str = str(workspace.sob_id).strip().upper()
        if not sob_str:
            raise ValueError("Contexto de Workspace inválido: sob_id não pode ser vazio.")

        if not hasattr(workspace, "root_dir") or not workspace.root_dir:
            raise ValueError("Contexto de Workspace inválido: root_dir obrigatório.")

        root_path = Path(workspace.root_dir)
        if not root_path.exists():
            raise FileNotFoundError(f"Diretório raiz da SOB não existe no disco: {workspace.root_dir}")

        raiz = Path(base_dir or BASE_DIR)
        script_amb = raiz / "ambiental" / "memorial_ambiental_generator.py"
        if not script_amb.exists():
            script_amb = Path(BASE_DIR) / "ambiental" / "memorial_ambiental_generator.py"

        if not script_amb.exists():
            raise FileNotFoundError(f"Script do módulo Ambiental não encontrado em: {script_amb}")

        # 1. Resolução do Template Word (.docx)
        tpl_final = ""
        if template_path:
            if Path(template_path).exists():
                tpl_final = str(Path(template_path).resolve())
        else:
            tpl_candidatos = [
                Path(r"G:\Meu Drive\1-HBT\04_MODELOS\MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx"),
                Path(r"G:\Meu Drive\1-HBT\05_PROJETOS_HISTORICOS\SETEMBRO\MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx"),
                raiz / "ambiental" / "modelos" / "MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx",
                Path(r"G:\Meu Drive\1-HBT\MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx"),
            ]
            for tpl_cand in tpl_candidatos:
                if tpl_cand.exists():
                    tpl_final = str(tpl_cand.resolve())
                    break

        # 2. Resolução de Pontos / Postes JSON
        pts_final = ""
        if pts_json and Path(pts_json).exists():
            pts_final = str(Path(pts_json).resolve())
        elif (root_path / "kmz_points_input.json").exists():
            pts_final = str((root_path / "kmz_points_input.json").resolve())
        elif Path(r"C:\Temp\kmz_points_input.json").exists():
            pts_final = str(Path(r"C:\Temp\kmz_points_input.json").resolve())

        # 3. Resolução de Caixas / Restrições TXT
        boxes_final = ""
        if boxes_txt and Path(boxes_txt).exists():
            boxes_final = str(Path(boxes_txt).resolve())
        elif (root_path / "kmz_boxes.txt").exists():
            boxes_final = str((root_path / "kmz_boxes.txt").resolve())
        elif Path(r"C:\Temp\kmz_boxes.txt").exists():
            boxes_final = str(Path(r"C:\Temp\kmz_boxes.txt").resolve())

        # 4. Fuso UTM e Pasta de Destino (Subpasta de Licenciamento Ambiental LIC.AMB)
        fuso_str = str(fuso) if fuso else "23"
        pasta_amb = root_path
        subpastas_candidatas = [
            "LIC.AMB", "Licen.Ambiental", "LICEN.AMBIENTAL", "LIC.AMBIENTAL",
            "LICEN.AMB", "Licenciamento Ambiental", "LICENCIAMENTO AMBIENTAL",
            "1_Documentos",
        ]
        for sub in subpastas_candidatas:
            cand = root_path / sub
            if cand.is_dir():
                pasta_amb = cand
                break
        else:
            if (root_path / ".sob_state.json").exists() or any(root_path.glob("*.dwg")):
                cand_lic = root_path / "LIC.AMB"
                try:
                    cand_lic.mkdir(parents=True, exist_ok=True)
                    pasta_amb = cand_lic
                except Exception:
                    pasta_amb = root_path

        out_dir_str = str(pasta_amb.resolve())

        return [
            sys.executable,
            str(script_amb),
            tpl_final,
            pts_final,
            boxes_final,
            fuso_str,
            out_dir_str,
        ]

    @classmethod
    def executar_ambiental(
        cls,
        workspace: ProjectWorkspace,
        template_path: Optional[Union[str, Path]] = None,
        pts_json: Optional[Union[str, Path]] = None,
        boxes_txt: Optional[Union[str, Path]] = None,
        fuso: int = 23,
        base_dir: Optional[Path] = None,
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        Inicia o módulo Ambiental (MemorialGUI) em subprocesso desacoplado,
        sem bloquear a interface do Workspace e direcionando as saídas para a pasta da SOB.
        """
        cmd = cls.montar_comando_ambiental(
            workspace=workspace,
            template_path=template_path,
            pts_json=pts_json,
            boxes_txt=boxes_txt,
            fuso=fuso,
            base_dir=base_dir,
        )
        return cls._lancar_processo(
            cmd,
            cwd=base_dir or BASE_DIR,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )

    @classmethod
    def montar_comando_prancha(
        cls,
        workspace: ProjectWorkspace,
        dados_json: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> List[str]:
        """
        Monta a lista de argumentos de execução do módulo AutoPranche conforme o contrato
        de prancha/autoprancha_core.py: --sob <SOB> --root <DIR> [--dwg <DWG>] [--json <DADOS>].
        Valida que o contexto possui sob_id e diretório válidos.
        """
        if not workspace or not hasattr(workspace, "sob_id") or not workspace.sob_id:
            raise ValueError("Contexto de Workspace inválido: sob_id obrigatório ausente.")

        sob_str = str(workspace.sob_id).strip().upper()
        if not sob_str:
            raise ValueError("Contexto de Workspace inválido: sob_id não pode ser vazio.")

        raiz = Path(base_dir or BASE_DIR)
        prancha_script = raiz / "prancha" / "autoprancha_core.py"
        if not prancha_script.exists():
            raise FileNotFoundError(f"Script do módulo AutoPranche não encontrado em: {prancha_script}")

        cmd = [
            sys.executable,
            str(prancha_script),
            "--sob",
            sob_str,
            "--root",
            str(workspace.root_dir),
            "--exportar-contexto",
        ]

        if getattr(workspace, "dwg_principal", None) and Path(workspace.dwg_principal).exists():
            cmd.extend(["--dwg", str(workspace.dwg_principal)])

        if dados_json:
            cmd.extend(["--json", str(dados_json)])

        return cmd

    @classmethod
    def executar_prancha(
        cls,
        workspace: ProjectWorkspace,
        dados_json: Optional[Union[str, Path]] = None,
        base_dir: Optional[Path] = None,
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        Inicia a rotina/orquestrador do AutoPranche em subprocesso desacoplado,
        sem bloquear a interface do Workspace.
        """
        cmd = cls.montar_comando_prancha(
            workspace=workspace,
            dados_json=dados_json,
            base_dir=base_dir,
        )
        return cls._lancar_processo(
            cmd,
            cwd=base_dir or BASE_DIR,
            correlation_id=correlation_id,
            execution_id=execution_id,
        )


    @staticmethod
    def _lancar_processo(
        cmd: List[str],
        cwd: Optional[Path] = None,
        correlation_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> subprocess.Popen:
        """
        Lança subprocesso desvinculado para evitar travamento da aplicação ou console chamador.
        Registra observabilidade estruturada e PID de lançamento.
        """
        dir_exec = str(cwd or BASE_DIR)
        kwargs: Dict[str, Any] = {"cwd": dir_exec}

        if sys.platform == "win32":
            creation_flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            if creation_flag:
                kwargs["creationflags"] = creation_flag

        logger.info(
            f"Lançando subprocesso: {Path(cmd[1]).name if len(cmd) > 1 else (cmd[0] if cmd else '')}",
            extra={
                "command": cmd,
                "cwd": dir_exec,
                "correlation_id": correlation_id,
                "execution_id": execution_id,
            }
        )
        proc = subprocess.Popen(cmd, **kwargs)
        logger.info(
            f"Subprocesso em execução (PID {proc.pid})",
            extra={
                "subproc_pid": proc.pid,
                "pid": proc.pid,
                "command": cmd,
                "correlation_id": correlation_id,
                "execution_id": execution_id,
            }
        )
        return proc

