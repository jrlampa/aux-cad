# -*- coding: utf-8 -*-
"""
AUX CAD / OXCAD — Qualidade, Histórico e Comparabilidade de Indicadores (P2.3).
Responsabilidade única: Determinação da qualidade da cobertura histórica,
rastreamento estrito de proveniência das métricas, auditoria de descarte de registros
e avaliação metodológica de comparabilidade entre períodos.

Diretrizes:
- Totalmente read-only, determinístico e auditável;
- Sem banco de dados, sem cache persistente, sem serviços residentes;
- Zero conclusões subjetivas ou avaliativas ('melhorou', 'piorou', 'produtividade');
- Zero ranking de pessoas, scores ou mensuração de desempenho individual;
- Apenas fatos observados, diferenças analíticas e explicitação de limitações.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union


# Classificações oficiais de cobertura histórica
COBERTURA_COMPLETA = "COMPLETA"
COBERTURA_PARCIAL = "PARCIAL"
COBERTURA_LIMITADA_POR_ROTACAO = "LIMITADA_POR_ROTACAO"
COBERTURA_SEM_DADOS = "SEM_DADOS"
COBERTURA_IDENTIDADE_NAO_VERIFICAVEL = "IDENTIDADE_NAO_VERIFICAVEL"
COBERTURA_FONTE_INDISPONIVEL = "FONTE_INDISPONIVEL"

# Mapeamento canônico de proveniência
PROVENIENCIA_FONTES: Dict[str, str] = {
    "execucoes": "logs/application.jsonl",
    "sob_manifesto": ".sob_state.json",
    "pendencias": ".oxcad/pending.json",
    "entregas": ".oxcad/deliveries/",
    "tempo_operacional": ".oxcad/time.json",
    "versoes": ".auxcad_versions/",
    "revisoes": ".oxcad/reviews.json",
}


@dataclass
class QualityMetricsCollector:
    """Coletor defensivo de métricas de qualidade, descarte e fontes."""
    linhas_totais: int = 0
    linhas_validas: int = 0
    linhas_invalidas: int = 0
    registros_considerados: int = 0
    descartes_por_motivo: Dict[str, int] = field(default_factory=lambda: {
        "FILTRO_PERIODO": 0,
        "FILTRO_SOB": 0,
        "FILTRO_ACAO": 0,
        "FILTRO_ESTADO": 0,
        "LINHA_CORROMPIDA": 0,
        "SEM_EXECUTION_ID": 0,
    })
    fontes_utilizadas: List[str] = field(default_factory=list)
    fontes_ausentes: List[str] = field(default_factory=list)
    fontes_invalidas: List[str] = field(default_factory=list)
    limitacoes_cobertura: List[str] = field(default_factory=list)
    log_rotacionado_detectado: bool = False
    solicitou_periodo_anterior_ao_log: bool = False

    def registrar_descarte(self, motivo: str, quantidade: int = 1) -> None:
        self.descartes_por_motivo[motivo] = self.descartes_por_motivo.get(motivo, 0) + quantidade

    def registrar_fonte_utilizada(self, fonte: str) -> None:
        if fonte not in self.fontes_utilizadas:
            self.fontes_utilizadas.append(fonte)

    def registrar_fonte_ausente(self, fonte: str) -> None:
        if fonte not in self.fontes_ausentes:
            self.fontes_ausentes.append(fonte)

    def registrar_fonte_invalida(self, fonte: str) -> None:
        if fonte not in self.fontes_invalidas:
            self.fontes_invalidas.append(fonte)

    def registrar_limitacao(self, limitacao: str) -> None:
        if limitacao not in self.limitacoes_cobertura:
            self.limitacoes_cobertura.append(limitacao)

    @property
    def total_descartes(self) -> int:
        return sum(self.descartes_por_motivo.values())


def classificar_cobertura_historica(
    status_identidade: str,
    collector: QualityMetricsCollector,
    total_execucoes: int,
    tem_fontes_duraveis_ok: bool,
    tem_fontes_duraveis_ausentes: bool,
    log_presente: bool,
) -> str:
    """
    Classifica a cobertura dos indicadores estritamente pelas fontes reais:
    - IDENTIDADE_NAO_VERIFICAVEL
    - FONTE_INDISPONIVEL
    - SEM_DADOS
    - LIMITADA_POR_ROTACAO
    - PARCIAL
    - COMPLETA
    """
    if status_identidade == "IDENTITY_UNVERIFIABLE":
        return COBERTURA_IDENTIDADE_NAO_VERIFICAVEL

    # Se nenhuma fonte válida foi utilizada
    if not collector.fontes_utilizadas:
        return COBERTURA_FONTE_INDISPONIVEL

    # Se log rotacionado limitou o período observado ou solicitado
    if collector.log_rotacionado_detectado or collector.solicitou_periodo_anterior_ao_log:
        return COBERTURA_LIMITADA_POR_ROTACAO

    # Se fontes existem mas não há dados nenhum
    if total_execucoes == 0 and not tem_fontes_duraveis_ok:
        return COBERTURA_SEM_DADOS

    # Se algumas fontes estão ausentes, inválidas ou linhas do log foram corrompidas
    if (
        tem_fontes_duraveis_ausentes
        or collector.fontes_invalidas
        or collector.linhas_invalidas > 0
        or (not log_presente and tem_fontes_duraveis_ok)
    ):
        return COBERTURA_PARCIAL

    return COBERTURA_COMPLETA


def _calcular_delta(base_val: Optional[Union[int, float]], comp_val: Optional[Union[int, float]]) -> Dict[str, Optional[float]]:
    if base_val is None or comp_val is None:
        return {
            "base": base_val,
            "comparado": comp_val,
            "delta_absoluto": None,
            "delta_pct": None,
        }

    delta_abs = round(float(comp_val - base_val), 2)
    delta_pct = None
    if base_val > 0:
        delta_pct = round(((comp_val - base_val) / float(base_val)) * 100.0, 2)

    return {
        "base": base_val,
        "comparado": comp_val,
        "delta_absoluto": delta_abs,
        "delta_pct": delta_pct,
    }


def comparar_indicadores(relatorio_base: Dict[str, Any], relatorio_comp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avalia a comparabilidade metodológica entre dois relatórios analíticos e,
    se válida, calcula as diferenças puramente descritivas.
    """
    escopo_base = relatorio_base.get("escopo", {})
    escopo_comp = relatorio_comp.get("escopo", {})

    status_id_base = escopo_base.get("status_identidade", "VALIDA")
    status_id_comp = escopo_comp.get("status_identidade", "VALIDA")

    sob_base = escopo_base.get("sob_id")
    sob_comp = escopo_comp.get("sob_id")

    tipo_base = escopo_base.get("tipo", "PROJETO")
    tipo_comp = escopo_comp.get("tipo", "PROJETO")

    qualidade_base = relatorio_base.get("qualidade_dados", {})
    qualidade_comp = relatorio_comp.get("qualidade_dados", {})

    cob_base = qualidade_base.get("cobertura", COBERTURA_PARCIAL)
    cob_comp = qualidade_comp.get("cobertura", COBERTURA_PARCIAL)

    fontes_base = set(qualidade_base.get("fontes_utilizadas", []))
    fontes_comp = set(qualidade_comp.get("fontes_utilizadas", []))

    periodo_base = relatorio_base.get("periodo_observado", {})
    periodo_comp = relatorio_comp.get("periodo_observado", {})

    # 1. Validação de Identidade
    if status_id_base == "IDENTITY_UNVERIFIABLE" or status_id_comp == "IDENTITY_UNVERIFIABLE":
        return {
            "status": "NAO_DETERMINADA",
            "comparavel": False,
            "motivo": "IDENTIDADE_INVERIFICAVEL",
            "detalhe": "Um ou ambos os relatórios apresentam identidade inverificável.",
            "periodo_base": periodo_base,
            "periodo_comparado": periodo_comp,
            "deltas": {},
        }

    # 2. Validação de Escopo e SOB
    if tipo_base != tipo_comp or (sob_base and sob_comp and sob_base != sob_comp):
        return {
            "status": "NAO_DETERMINADA",
            "comparavel": False,
            "motivo": "ESCOPO_OU_IDENTIDADE_DIVERGENTE",
            "detalhe": f"Escopos incompatíveis: ({tipo_base}, SOB: {sob_base}) vs ({tipo_comp}, SOB: {sob_comp}).",
            "periodo_base": periodo_base,
            "periodo_comparado": periodo_comp,
            "deltas": {},
        }

    # 3. Validação de Cobertura e Fontes
    if cob_base == COBERTURA_FONTE_INDISPONIVEL or cob_comp == COBERTURA_FONTE_INDISPONIVEL:
        return {
            "status": "NAO_DETERMINADA",
            "comparavel": False,
            "motivo": "FONTE_INDISPONIVEL",
            "detalhe": "Fontes primárias indisponíveis em um dos períodos comparados.",
            "periodo_base": periodo_base,
            "periodo_comparado": periodo_comp,
            "deltas": {},
        }

    if cob_base == COBERTURA_LIMITADA_POR_ROTACAO or cob_comp == COBERTURA_LIMITADA_POR_ROTACAO:
        return {
            "status": "NAO_DETERMINADA",
            "comparavel": False,
            "motivo": "LIMITADA_POR_ROTACAO",
            "detalhe": "Histórico truncado pela rotação de log de 5 MB impossibilita comparação íntegra.",
            "periodo_base": periodo_base,
            "periodo_comparado": periodo_comp,
            "deltas": {},
        }

    if fontes_base != fontes_comp and bool(fontes_base) and bool(fontes_comp):
        return {
            "status": "NAO_DETERMINADA",
            "comparavel": False,
            "motivo": "FONTES_DIVERGENTES",
            "detalhe": f"Fontes utilizadas divergem entre períodos: {sorted(fontes_base)} vs {sorted(fontes_comp)}.",
            "periodo_base": periodo_base,
            "periodo_comparado": periodo_comp,
            "deltas": {},
        }

    # 4. Cálculo de Deltas Observados (Puramente descritivos)
    exec_base = relatorio_base.get("execucoes", {})
    exec_comp = relatorio_comp.get("execucoes", {})

    dur_base = exec_base.get("duracao_ms", {}) if isinstance(exec_base.get("duracao_ms"), dict) else {}
    dur_comp = exec_comp.get("duracao_ms", {}) if isinstance(exec_comp.get("duracao_ms"), dict) else {}

    pend_base = relatorio_base.get("pendencias", {})
    pend_comp = relatorio_comp.get("pendencias", {})

    deliv_base = relatorio_base.get("entregas", {})
    deliv_comp = relatorio_comp.get("entregas", {})

    time_base = relatorio_base.get("tempo_operacional", {})
    time_comp = relatorio_comp.get("tempo_operacional", {})

    deltas = {
        "total_execucoes": _calcular_delta(exec_base.get("total_execucoes"), exec_comp.get("total_execucoes")),
        "concluidas": _calcular_delta(exec_base.get("concluidas"), exec_comp.get("concluidas")),
        "falhas": _calcular_delta(exec_base.get("falhas"), exec_comp.get("falhas")),
        "canceladas": _calcular_delta(exec_base.get("canceladas"), exec_comp.get("canceladas")),
        "taxa_conclusao_pct": _calcular_delta(exec_base.get("taxa_conclusao_pct"), exec_comp.get("taxa_conclusao_pct")),
        "duracao_mediana_ms": _calcular_delta(dur_base.get("mediana_ms"), dur_comp.get("mediana_ms")),
        "duracao_p95_ms": _calcular_delta(dur_base.get("p95_ms"), dur_comp.get("p95_ms")),
        "pendencias_abertas": _calcular_delta(pend_base.get("abertas"), pend_comp.get("abertas")),
        "pendencias_resolvidas": _calcular_delta(pend_base.get("resolvidas"), pend_comp.get("resolvidas")),
        "entregas_total": _calcular_delta(deliv_base.get("total_pacotes"), deliv_comp.get("total_pacotes")),
        "entregas_aprovadas": _calcular_delta(deliv_base.get("aprovados"), deliv_comp.get("aprovados")),
        "tempo_operacional_segundos": _calcular_delta(time_base.get("tempo_acumulado_segundos"), time_comp.get("tempo_acumulado_segundos")),
    }

    return {
        "status": "VALIDA",
        "comparavel": True,
        "motivo": None,
        "detalhe": "Comparação metodologicamente consistente entre períodos.",
        "periodo_base": periodo_base,
        "periodo_comparado": periodo_comp,
        "deltas": deltas,
    }
