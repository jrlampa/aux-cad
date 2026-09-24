# -*- coding: utf-8 -*-
"""
Módulo Central do Workspace da SOB/Projeto (aux cad).
Responsabilidade única: Representação do modelo de domínio, entidades de contexto
e contrato central de artefatos da SOB/projeto.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ArtifactStatus(str, Enum):
    """Estado de detecção de um artefato de engenharia no Workspace."""
    EXISTE = "EXISTE"
    NAO_EXISTE = "NAO_EXISTE"
    NAO_APLICAVEL = "NAO_APLICAVEL"


@dataclass
class ProjectArtifact:
    """Representa um artefato detectado ou associado ao Workspace."""
    chave: str
    rotulo: str
    status: ArtifactStatus = ArtifactStatus.NAO_EXISTE
    caminho: Optional[Path] = None
    detalhes: Dict[str, Any] = field(default_factory=dict)

    @property
    def existe(self) -> bool:
        """Verifica se o artefato existe fisicamente."""
        return self.status == ArtifactStatus.EXISTE and self.caminho is not None and self.caminho.exists()

    def para_dicionario(self) -> Dict[str, Any]:
        """Converte o artefato em dicionário legível e serializável."""
        return {
            "chave": self.chave,
            "rotulo": self.rotulo,
            "status": self.status.value,
            "caminho": str(self.caminho) if self.caminho else None,
            "detalhes": self.detalhes,
        }


@dataclass
class ProjectWorkspace:
    """
    Contexto Central e Unificado da SOB / Projeto.
    Reúne e coordena todos os artefatos de engenharia (DWG, Croqui, Documentos,
    Ambiental, CQT, Unifilar, Orçamento, CPFC) sem duplicação de lógica ou dados.
    """
    sob_id: str
    sob_name: str
    root_dir: Path
    base_sigla: str = "PE"
    dwg_principal: Optional[Path] = None
    croqui_dir: Optional[Path] = None
    documentos_dir: Optional[Path] = None
    checklist_ambiental: Optional[Path] = None
    memorial_ambiental: Optional[Path] = None
    croqui_ambiental: Optional[Path] = None
    cqt_planilha: Optional[Path] = None
    orcamento_planilha: Optional[Path] = None
    cpfc_planilha: Optional[Path] = None
    unifilar_path: Optional[Path] = None
    artefatos: Dict[str, ProjectArtifact] = field(default_factory=dict)
    metadados: Dict[str, Any] = field(default_factory=dict)

    def obter_artefato(self, chave: str) -> Optional[ProjectArtifact]:
        """Recupera um artefato registrado pelo seu identificador."""
        return self.artefatos.get(chave)

    def status_de(self, chave: str) -> ArtifactStatus:
        """Retorna o status de um artefato específico."""
        art = self.artefatos.get(chave)
        return art.status if art else ArtifactStatus.NAO_EXISTE

    def obter_resumo(self) -> Dict[str, Any]:
        """Retorna um resumo estruturado de todos os componentes do Workspace."""
        return {
            "sob_id": self.sob_id,
            "sob_name": self.sob_name,
            "root_dir": str(self.root_dir),
            "base_sigla": self.base_sigla,
            "dwg_principal": str(self.dwg_principal) if self.dwg_principal else None,
            "croqui_dir": str(self.croqui_dir) if self.croqui_dir else None,
            "documentos_dir": str(self.documentos_dir) if self.documentos_dir else None,
            "checklist_ambiental": str(self.checklist_ambiental) if self.checklist_ambiental else None,
            "memorial_ambiental": str(self.memorial_ambiental) if self.memorial_ambiental else None,
            "croqui_ambiental": str(self.croqui_ambiental) if self.croqui_ambiental else None,
            "cqt_planilha": str(self.cqt_planilha) if self.cqt_planilha else None,
            "orcamento_planilha": str(self.orcamento_planilha) if self.orcamento_planilha else None,
            "cpfc_planilha": str(self.cpfc_planilha) if self.cpfc_planilha else None,
            "unifilar_path": str(self.unifilar_path) if self.unifilar_path else None,
            "artefatos": {k: v.para_dicionario() for k, v in self.artefatos.items()},
            "metadados": self.metadados,
        }

    def formatar_relatorio_texto(self) -> str:
        """
        Formata o estado do Workspace em formato de texto limpo e amigável (pt-BR),
        ideal para logs, terminais e diálogos no AutoCAD.
        """
        linhas = [
            f"=======================================================",
            f"  WORKSPACE — SOB {self.sob_id}",
            f"=======================================================",
            f"Raiz: {self.root_dir}",
            f"Base: {self.base_sigla}",
            "",
            "ARTEFATOS DO PROJETO:",
        ]

        def _icone(st: ArtifactStatus) -> str:
            if st == ArtifactStatus.EXISTE:
                return "✓ Encontrado"
            elif st == ArtifactStatus.NAO_EXISTE:
                return "— Não gerado"
            return "○ Não aplicável"

        ordem_exibicao = [
            ("DWG", "Desenho DWG Principal"),
            ("CROQUI", "Pasta de Croqui de Campo"),
            ("DOCUMENTOS", "Documentos e Anexos"),
            ("CHECKLIST_AMBIENTAL", "Checklist Ambiental (.xlsx)"),
            ("MEMORIAL_AMBIENTAL", "Memorial Ambiental (.docx)"),
            ("CROQUI_AMBIENTAL", "Croqui Ambiental Satélite (.png)"),
            ("CQT", "Queda de Tensão BT (CQT)"),
            ("ORCAMENTO", "Orçamento de Materiais (.xlsx)"),
            ("CPFC", "Participação Financeira CPFC (.xlsx)"),
            ("UNIFILAR", "Diagrama Unifilar / Proteção"),
        ]

        for chave, desc in ordem_exibicao:
            art = self.artefatos.get(chave)
            st = art.status if art else ArtifactStatus.NAO_EXISTE
            rotulo = _icone(st)
            detalhe = ""
            if art and art.caminho and st == ArtifactStatus.EXISTE:
                detalhe = f" ({art.caminho.name})"
            linhas.append(f"  {desc:<34} : {rotulo}{detalhe}")

        linhas.append(f"=======================================================")
        return "\n".join(linhas)
