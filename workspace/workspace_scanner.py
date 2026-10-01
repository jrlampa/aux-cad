# -*- coding: utf-8 -*-
"""
Módulo de Varredura e Detecção do Workspace da SOB/Projeto (aux cad).
Responsabilidade única: Inspecionar e detectar artefatos de engenharia no sistema de arquivos
de forma não-destrutiva, determinística e exclusivamente em modo leitura.
"""

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from sob.sob_core import obter_sob_id, obter_sob_name, validar_sob_id
    from sob.sob_bases import normalizar_sigla_base
except ModuleNotFoundError:
    from sob_core import obter_sob_id, obter_sob_name, validar_sob_id
    from sob_bases import normalizar_sigla_base

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace


class WorkspaceScanner:
    """
    Camada analítica responsável por escanear o diretório do projeto e
    mapear todos os artefatos de engenharia relacionados à SOB.
    """

    @staticmethod
    def extrair_sob_de_texto(texto: str) -> Optional[str]:
        """
        Extrai o identificador da SOB a partir de uma string qualquer (nome de pasta ou arquivo).
        Exemplos:
          - 'SOB_A057349839' -> 'A057349839'
          - 'PE_A057349839_DESENHO.dwg' -> 'A057349839'
          - 'CHECKLIST_A057349839.xlsx' -> 'A057349839'
          - 'A057349839' -> 'A057349839'
        """
        if not texto:
            return None

        # 1. Padrão oficial SOB_...
        match_sob = re.search(r"SOB_([A-Z0-9_\-]+)", texto, re.IGNORECASE)
        if match_sob:
            candidato = match_sob.group(1).upper()
            if validar_sob_id(candidato):
                return candidato

        # 2. Padrão oficial de DWG {BASE}_{SOB}_DESENHO
        match_dwg = re.search(r"[A-Z]{2}_([A-Z0-9_\-]+)_DESENHO", texto, re.IGNORECASE)
        if match_dwg:
            candidato = match_dwg.group(1).upper()
            if validar_sob_id(candidato):
                return candidato

        # 3. Padrão alfanumérico padrão de SOB da concessionária (ex: A057349839, B123456789)
        match_alfa = re.search(r"(?:^|[^A-Z0-9])([A-Z][0-9]{8,12})(?:[^A-Z0-9]|$)", texto, re.IGNORECASE)
        if match_alfa:
            candidato = match_alfa.group(1).upper()
            if validar_sob_id(candidato):
                return candidato

        # 4. Fallback se tiver prefixo explícito SOB_ ou contiver dígitos de engenharia
        texto_limpo = texto.strip().upper()
        if texto_limpo.startswith("SOB_"):
            texto_limpo = texto_limpo[4:]
            if validar_sob_id(texto_limpo):
                return texto_limpo

        if any(c.isdigit() for c in texto_limpo) and validar_sob_id(texto_limpo):
            return texto_limpo

        return None

    @classmethod
    def detectar_sob_em_diretorio(cls, root_dir: Union[str, Path]) -> Optional[str]:
        """
        Tenta descobrir a SOB examinando o nome da pasta ou os arquivos contidos nela.
        """
        p = Path(root_dir).resolve()
        if not p.exists() or not p.is_dir():
            return None

        # 1. Tenta extrair do nome da própria pasta
        sob_pasta = cls.extrair_sob_de_texto(p.name)
        if sob_pasta:
            return sob_pasta

        # 2. Tenta extrair de arquivos DWG na pasta
        for f in p.glob("*.dwg"):
            sob_dwg = cls.extrair_sob_de_texto(f.name)
            if sob_dwg:
                return sob_dwg

        # 3. Tenta extrair de outros arquivos da pasta
        for f in p.iterdir():
            if f.is_file():
                sob_f = cls.extrair_sob_de_texto(f.name)
                if sob_f:
                    return sob_f

        return None

    @classmethod
    def detectar_sobs_candidatas(
        cls,
        root_dir: Union[str, Path],
        excluir_dwg: Optional[Union[str, Path]] = None,
    ) -> List[str]:
        """Retorna SOBs sugeridas por DWGs sem escolher uma."""
        p_root = Path(root_dir).resolve()
        if not p_root.exists() or not p_root.is_dir():
            return []

        caminho_excluido = Path(excluir_dwg).resolve() if excluir_dwg else None
        candidatas = set()
        pastas = [p_root]
        pastas.extend(path for path in p_root.iterdir() if path.is_dir())

        for pasta in pastas:
            manifesto = pasta / ".sob_state.json"
            if manifesto.is_file():
                try:
                    dados = json.loads(manifesto.read_text(encoding="utf-8"))
                    sob_id = cls.extrair_sob_de_texto(
                        str(dados.get("sob_id", ""))
                    )
                    if sob_id:
                        candidatas.add(sob_id)
                except (
                    OSError,
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    AttributeError,
                ):
                    pass

            for dwg in pasta.glob("*_DESENHO.dwg"):
                if caminho_excluido and dwg.resolve() == caminho_excluido:
                    continue
                sob_id = cls.extrair_sob_de_texto(dwg.name)
                if sob_id:
                    candidatas.add(sob_id)

        return sorted(candidatas)

    @classmethod
    def detectar_base_sigla(cls, root_dir: Path, sob_id: str) -> str:
        """
        Detecta a sigla de base técnica da concessionária (ex: 'PE', 'CF', 'NI')
        a partir do nome do DWG existente ou assume 'PE' por padrão.
        """
        padrao = re.compile(rf"^([A-Z]{{2}})_{re.escape(sob_id)}_DESENHO\.dwg$", re.IGNORECASE)
        for f in root_dir.glob("*.dwg"):
            m = padrao.match(f.name)
            if m:
                return normalizar_sigla_base(m.group(1))

        # Procura qualquer DWG com prefixo de 2 letras
        padrao_geral = re.compile(r"^([A-Z]{{2}})_.*_DESENHO\.dwg$", re.IGNORECASE)
        for f in root_dir.glob("*.dwg"):
            m = padrao_geral.match(f.name)
            if m:
                return normalizar_sigla_base(m.group(1))

        return "PE"

    @classmethod
    def detectar_dwg_principal(cls, root_dir: Path, sob_id: str, base_sigla: str) -> Tuple[Optional[Path], ArtifactStatus, Dict[str, Any]]:
        """Localiza o arquivo DWG principal do projeto."""
        candidatos: List[Path] = []

        # 1. Prioridade absoluta: {BASE}_{SOB}_DESENHO.dwg
        nome_oficial = f"{base_sigla}_{sob_id}_DESENHO.dwg"
        path_oficial = root_dir / nome_oficial
        if path_oficial.exists() and path_oficial.is_file():
            return path_oficial, ArtifactStatus.EXISTE, {"tamanho_bytes": path_oficial.stat().st_size, "tipo": "canônico"}

        # 2. Prioridade 2: Qualquer {BASE}_{SOB}_DESENHO.dwg com outra base
        for f in root_dir.glob(f"*_{sob_id}_DESENHO.dwg"):
            if f.is_file():
                return f, ArtifactStatus.EXISTE, {"tamanho_bytes": f.stat().st_size, "tipo": "base_alternativa"}

        # 3. Prioridade 3: Qualquer DWG contendo o número da SOB
        for f in root_dir.glob(f"*{sob_id}*.dwg"):
            if f.is_file():
                candidatos.append(f)

        if candidatos:
            candidatos.sort(key=lambda x: x.stat().st_size, reverse=True)
            escolhido = candidatos[0]
            return escolhido, ArtifactStatus.EXISTE, {"tamanho_bytes": escolhido.stat().st_size, "tipo": "correspondência_sob"}

        # 4. Prioridade 4: Arquivo *_DESENHO.dwg
        desenhos = [f for f in root_dir.glob("*_DESENHO.dwg") if f.is_file()]
        if desenhos:
            return desenhos[0], ArtifactStatus.EXISTE, {"tamanho_bytes": desenhos[0].stat().st_size, "tipo": "sufixo_desenho"}

        # 5. Prioridade 5: Primeiro DWG não-temporário encontrado
        dwgs = [f for f in root_dir.glob("*.dwg") if f.is_file() and not f.name.startswith("~")]
        if dwgs:
            return dwgs[0], ArtifactStatus.EXISTE, {"tamanho_bytes": dwgs[0].stat().st_size, "tipo": "dwg_geral"}

        return None, ArtifactStatus.NAO_EXISTE, {}

    @classmethod
    def detectar_croqui(cls, root_dir: Path) -> Tuple[Optional[Path], ArtifactStatus, Dict[str, Any]]:
        """Verifica a existência da pasta de croqui e contabiliza seus arquivos."""
        pastas_candidatas = ["CROQUI", "CROQUIS", "Levantamento", "LEVANTAMENTO"]
        pasta_alvo: Optional[Path] = None

        for nome in pastas_candidatas:
            cand = root_dir / nome
            if cand.exists() and cand.is_dir():
                pasta_alvo = cand
                break

        if not pasta_alvo:
            return None, ArtifactStatus.NAO_EXISTE, {"total_arquivos": 0}

        extensoes_foto = {".jpg", ".jpeg", ".png", ".bmp"}
        extensoes_geo = {".kmz", ".kml", ".gpx"}
        extensoes_doc = {".pdf", ".docx", ".xlsx", ".txt"}

        arquivos = [f for f in pasta_alvo.iterdir() if f.is_file() and not f.name.startswith("~")]
        qtd_fotos = sum(1 for f in arquivos if f.suffix.lower() in extensoes_foto)
        qtd_geo = sum(1 for f in arquivos if f.suffix.lower() in extensoes_geo)
        qtd_doc = sum(1 for f in arquivos if f.suffix.lower() in extensoes_doc)

        detalhes = {
            "total_arquivos": len(arquivos),
            "fotos": qtd_fotos,
            "geometrias": qtd_geo,
            "documentos": qtd_doc,
        }
        return pasta_alvo, ArtifactStatus.EXISTE, detalhes

    @classmethod
    def detectar_documentos(cls, root_dir: Path, croqui_dir: Optional[Path]) -> Tuple[Optional[Path], ArtifactStatus, Dict[str, Any]]:
        """Localiza anexos do GOMNET ou pasta de documentos técnicos."""
        candidatos = []
        if croqui_dir and (croqui_dir / "ANEXOS").is_dir():
            candidatos.append(croqui_dir / "ANEXOS")
        if (root_dir / "DOCUMENTOS").is_dir():
            candidatos.append(root_dir / "DOCUMENTOS")
        if (root_dir / "ANEXOS").is_dir():
            candidatos.append(root_dir / "ANEXOS")

        if candidatos:
            pasta_doc = candidatos[0]
            arquivos = [f for f in pasta_doc.iterdir() if f.is_file() and not f.name.startswith("~")]
            return pasta_doc, ArtifactStatus.EXISTE, {"total_arquivos": len(arquivos), "pasta": pasta_doc.name}

        # Checa se há PDFs soltos na pasta da SOB
        pdfs = [f for f in root_dir.glob("*.pdf") if f.is_file()]
        if pdfs:
            return root_dir, ArtifactStatus.EXISTE, {"total_arquivos": len(pdfs), "pasta": "raiz"}

        return None, ArtifactStatus.NAO_EXISTE, {"total_arquivos": 0}

    @classmethod
    def detectar_arquivo_por_padroes(cls, root_dir: Path, padroes: List[str]) -> Optional[Path]:
        """Busca o primeiro arquivo correspondente à lista de padrões fornecida."""
        for padrao in padroes:
            arquivos = [f for f in root_dir.glob(padrao) if f.is_file() and not f.name.startswith("~")]
            if arquivos:
                # Ordena pelos mais recentes
                arquivos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return arquivos[0]
        return None

    @classmethod
    def scan(cls, root_dir: Union[str, Path], sob_id: Optional[str] = None) -> ProjectWorkspace:
        """
        Escaneia o diretório e monta o ProjectWorkspace completo.
        Opera estritamente em modo de leitura (zero modificações em disco).
        """
        p_root = Path(root_dir).resolve()
        if not p_root.exists() or not p_root.is_dir():
            # Retorna contexto seguro indicando inexistência
            sob_id_seguro = sob_id or "DESCONHECIDO"
            return ProjectWorkspace(
                sob_id=sob_id_seguro,
                sob_name=f"SOB_{sob_id_seguro}",
                root_dir=p_root,
                artefatos={
                    "STATUS": ProjectArtifact(
                        chave="STATUS",
                        rotulo="Status do Diretório",
                        status=ArtifactStatus.NAO_EXISTE,
                        detalhes={"erro": "Diretório raiz não encontrado ou inacessível."},
                    )
                },
                metadados={"erro": "DIRETORIO_INEXISTENTE"}
            )

        # 1. Determina o SOB_ID
        id_final = sob_id
        if not id_final:
            id_final = cls.detectar_sob_em_diretorio(p_root)
        if not id_final:
            id_final = cls.extrair_sob_de_texto(p_root.name) or "PROJETO"

        id_final = obter_sob_id(id_final) if validar_sob_id(id_final) else id_final.upper()
        sob_name = f"SOB_{id_final}"

        # 2. Base da Concessionária
        base_sigla = cls.detectar_base_sigla(p_root, id_final)

        # 3. DWG Principal
        dwg_path, st_dwg, det_dwg = cls.detectar_dwg_principal(p_root, id_final, base_sigla)

        # 4. Croqui de Campo
        croqui_path, st_croqui, det_croqui = cls.detectar_croqui(p_root)

        # 5. Documentos e Anexos
        doc_path, st_doc, det_doc = cls.detectar_documentos(p_root, croqui_path)

        # 6. Ambiental (Checklist, Memorial, Croqui Satélite)
        chk_path = cls.detectar_arquivo_por_padroes(p_root, [
            f"CHECKLIST_{id_final}*.xlsx",
            f"CHECKLIST*{id_final}*.xlsx",
            "CHECKLIST*.xlsx",
            "*checklist*.xlsx"
        ])
        st_chk = ArtifactStatus.EXISTE if chk_path else ArtifactStatus.NAO_EXISTE

        mem_path = cls.detectar_arquivo_por_padroes(p_root, [
            f"MEMORIAL_DESCRITIVO_{id_final}*.docx",
            f"MEMORIAL*{id_final}*.docx",
            "MEMORIAL*.docx",
            "*memorial*.docx"
        ])
        st_mem = ArtifactStatus.EXISTE if mem_path else ArtifactStatus.NAO_EXISTE

        crq_amb_path = cls.detectar_arquivo_por_padroes(p_root, [
            f"CROQUI_AMBIENTAL_{id_final}*.png",
            f"CROQUI_AMBIENTAL*{id_final}*.png",
            "CROQUI_AMBIENTAL*.png",
            "*croqui_ambiental*.png"
        ])
        st_crq_amb = ArtifactStatus.EXISTE if crq_amb_path else ArtifactStatus.NAO_EXISTE

        # 7. CQT (Queda de Tensão BT)
        cqt_path = cls.detectar_arquivo_por_padroes(p_root, [
            f"CQT_{id_final}*.xls*",
            f"*CQT*_{id_final}*.xls*",
            "CQT*.xls*",
            "*queda*tensao*.xls*"
        ])
        st_cqt = ArtifactStatus.EXISTE if cqt_path else ArtifactStatus.NAO_EXISTE

        # 8. Orçamento de Materiais e Mão de Obra
        orc_path = cls.detectar_arquivo_por_padroes(p_root, [
            f"ORCAMENTO_{id_final}*.xlsx",
            f"*ORCAMENTO*_{id_final}*.xlsx",
            f"sisORCA_{id_final}*.xlsx",
            f"sisORÇA_{id_final}*.xlsx",
            "ORCAMENTO*.xlsx",
            "sisORCA*.xlsx",
            "sisORÇA*.xlsx"
        ])
        st_orc = ArtifactStatus.EXISTE if orc_path else ArtifactStatus.NAO_EXISTE

        # 9. CPFC (Participação Financeira)
        cpfc_path = cls.detectar_arquivo_por_padroes(p_root, [
            f"*_{id_final}_CPFC*.xlsx",
            f"CPFC_{id_final}*.xlsx",
            "*CPFC*.xlsx"
        ])
        st_cpfc = ArtifactStatus.EXISTE if cpfc_path else ArtifactStatus.NAO_EXISTE

        # 10. Diagrama Unifilar
        unifilar_path = cls.detectar_arquivo_por_padroes(p_root, [
            f"UNIFILAR_{id_final}*.json",
            f"*unifilar*_{id_final}*.json",
            "UNIFILAR*.json",
            "*unifilar*.json"
        ])
        st_unifilar = ArtifactStatus.EXISTE if unifilar_path else ArtifactStatus.NAO_EXISTE

        # Montagem do mapa de artefatos
        artefatos: Dict[str, ProjectArtifact] = {
            "DWG": ProjectArtifact(chave="DWG", rotulo="Desenho DWG Principal", status=st_dwg, caminho=dwg_path, detalhes=det_dwg),
            "CROQUI": ProjectArtifact(chave="CROQUI", rotulo="Pasta de Croqui de Campo", status=st_croqui, caminho=croqui_path, detalhes=det_croqui),
            "DOCUMENTOS": ProjectArtifact(chave="DOCUMENTOS", rotulo="Documentos e Anexos", status=st_doc, caminho=doc_path, detalhes=det_doc),
            "CHECKLIST_AMBIENTAL": ProjectArtifact(chave="CHECKLIST_AMBIENTAL", rotulo="Checklist Ambiental (.xlsx)", status=st_chk, caminho=chk_path),
            "MEMORIAL_AMBIENTAL": ProjectArtifact(chave="MEMORIAL_AMBIENTAL", rotulo="Memorial Ambiental (.docx)", status=st_mem, caminho=mem_path),
            "CROQUI_AMBIENTAL": ProjectArtifact(chave="CROQUI_AMBIENTAL", rotulo="Croqui Ambiental Satélite (.png)", status=st_crq_amb, caminho=crq_amb_path),
            "CQT": ProjectArtifact(chave="CQT", rotulo="Queda de Tensão BT (CQT)", status=st_cqt, caminho=cqt_path),
            "ORCAMENTO": ProjectArtifact(chave="ORCAMENTO", rotulo="Orçamento de Materiais (.xlsx)", status=st_orc, caminho=orc_path),
            "CPFC": ProjectArtifact(chave="CPFC", rotulo="Participação Financeira CPFC (.xlsx)", status=st_cpfc, caminho=cpfc_path),
            "UNIFILAR": ProjectArtifact(chave="UNIFILAR", rotulo="Diagrama Unifilar / Proteção", status=st_unifilar, caminho=unifilar_path),
        }

        return ProjectWorkspace(
            sob_id=id_final,
            sob_name=sob_name,
            root_dir=p_root,
            base_sigla=base_sigla,
            dwg_principal=dwg_path,
            croqui_dir=croqui_path,
            documentos_dir=doc_path,
            checklist_ambiental=chk_path,
            memorial_ambiental=mem_path,
            croqui_ambiental=crq_amb_path,
            cqt_planilha=cqt_path,
            orcamento_planilha=orc_path,
            cpfc_planilha=cpfc_path,
            unifilar_path=unifilar_path,
            artefatos=artefatos,
            metadados={
                "total_artefatos_detectados": sum(1 for a in artefatos.values() if a.status == ArtifactStatus.EXISTE),
                "total_artefatos_monitorados": len(artefatos),
            }
        )
