"""Módulo: autoprancha_core.py
Responsabilidade Única: Motor analítico para cálculo de enquadramento de pranchas
no ModelSpace para projetos de rede de distribuição no padrão Enel / HBT.

Permite selecionar a melhor combinação de formato de papel (A0, A1, A2, A3, A4)
e escala normativa de distribuição (1:500, 1:750, 1:1000, 1:1250, 1:1500, 1:2000).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Dimensões nominais dos formatos de papel em milímetros (largura x altura)
# Padrão ABNT NBR 10068 / Padrão Enel & HBT
FORMATOS_PAPEL_MM: Dict[str, Tuple[float, float]] = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),  # A4 paisagem (horizontal)
}

# Margens padrão da prancha em milímetros (esquerda, direita, superior, inferior)
MARGENS_PADRAO_MM: Dict[str, Tuple[float, float, float, float]] = {
    "A0": (25.0, 10.0, 10.0, 10.0),
    "A1": (25.0, 10.0, 10.0, 10.0),
    "A2": (25.0, 10.0, 10.0, 10.0),
    "A3": (25.0, 10.0, 10.0, 10.0),
    "A4": (25.0, 10.0, 10.0, 10.0),
}

# Dimensões da reserva de Carimbo + Legenda Enel/HBT no canto inferior direito (mm)
LARGURA_CARIMBO_MM: float = 185.0
ALTURA_CARIMBO_MM: float = 60.0

# Escalas normativas recomendadas em projetos de distribuição aérea (1:N)
ESCALAS_NORMATIVAS: List[int] = [500, 750, 1000, 1250, 1500, 2000]


@dataclass
class EnquadramentoResultado:
    """Resultado do cálculo de enquadramento da prancha no ModelSpace."""
    formato: str
    escala: int
    fator_escala: float  # escala / 1000.0 (onde 1 unidade CAD = 1 metro)
    largura_folha_m: float
    altura_folha_m: float
    largura_util_m: float
    altura_util_m: float
    dx_projeto_m: float
    dy_projeto_m: float
    folga_x_perc: float
    folga_y_perc: float
    reserva_carimbo_largura_m: float
    reserva_carimbo_altura_m: float
    # Ponto de inserção (canto inferior esquerdo da folha no ModelSpace)
    x_folha_min: float
    y_folha_min: float
    x_folha_max: float
    y_folha_max: float
    centro_projeto_x: float
    centro_projeto_y: float


def obter_area_util_mm(formato: str) -> Tuple[float, float]:
    """Retorna a largura e altura útil da folha em mm (descontadas as margens)."""
    fmt = formato.upper()
    if fmt not in FORMATOS_PAPEL_MM:
        raise ValueError(f"Formato desconhecido: {formato}")
    largura, altura = FORMATOS_PAPEL_MM[fmt]
    m_esq, m_dir, m_sup, m_inf = MARGENS_PADRAO_MM[fmt]
    largura_util = largura - (m_esq + m_dir)
    altura_util = altura - (m_sup + m_inf)
    return largura_util, altura_util


def calcular_dimensoes_model(formato: str, escala: int) -> Tuple[float, float, float, float]:
    """Calcula as dimensões da folha e da área útil no ModelSpace em metros."""
    fmt = formato.upper()
    if fmt not in FORMATOS_PAPEL_MM:
        raise ValueError(f"Formato desconhecido: {formato}")
    largura_mm, altura_mm = FORMATOS_PAPEL_MM[fmt]
    larg_util_mm, alt_util_mm = obter_area_util_mm(fmt)
    fator = escala / 1000.0

    largura_folha_m = largura_mm * fator
    altura_folha_m = altura_mm * fator
    largura_util_m = larg_util_mm * fator
    altura_util_m = alt_util_mm * fator

    return largura_folha_m, altura_folha_m, largura_util_m, altura_util_m


def calcular_enquadramento(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    escala_fixa: Optional[int] = None,
    formato_fixo: Optional[str] = None,
    margem_seguranca_perc: float = 0.10,
    preferencia_formato: str = "A1",
) -> EnquadramentoResultado:
    """Calcula o melhor formato e escala de prancha para enquadrar a área selecionada.

    Args:
        x1, y1: Primeiro canto da caixa delimitadora do projeto (metros).
        x2, y2: Canto oposto da caixa delimitadora (metros).
        escala_fixa: Se fornecida, força o uso dessa escala (ex: 1000).
        formato_fixo: Se fornecido, força o uso desse formato (ex: 'A1').
        margem_seguranca_perc: Folga de respiro mínima recomendada (padrão 10%).
        preferencia_formato: Formato preferencial em caso de empate (padrão 'A1').

    Returns:
        EnquadramentoResultado com todas as informações geométricas e de escala.
    """
    xmin = min(x1, x2)
    xmax = max(x1, x2)
    ymin = min(y1, y2)
    ymax = max(y1, y2)

    dx = max(0.01, xmax - xmin)
    dy = max(0.01, ymax - ymin)
    centro_x = (xmin + xmax) / 2.0
    centro_y = (ymin + ymax) / 2.0

    # Adicionar margem de segurança desejada
    dx_necessario = dx * (1.0 + margem_seguranca_perc)
    dy_necessario = dy * (1.0 + margem_seguranca_perc)

    formatos_a_testar = [formato_fixo.upper()] if formato_fixo else ["A3", "A2", "A1", "A0"]
    escalas_a_testar = [escala_fixa] if escala_fixa else ESCALAS_NORMATIVAS

    melhor_opcao: Optional[Tuple[str, int, float, float, float, float]] = None
    menor_desperdicio = float("inf")

    for fmt in formatos_a_testar:
        if fmt not in FORMATOS_PAPEL_MM:
            continue
        for esc in escalas_a_testar:
            larg_folha_m, alt_folha_m, larg_util_m, alt_util_m = calcular_dimensoes_model(fmt, esc)

            # Verificar se a área útil comporta o projeto com folga
            if larg_util_m >= dx_necessario and alt_util_m >= dy_necessario:
                # Calcular desperdício de papel / área livre
                area_util = larg_util_m * alt_util_m
                area_proj = dx * dy
                desperdicio = area_util - area_proj

                # Dar leve prioridade à escala 1:1000 (escala mãe da Enel)
                # e ao formato preferencial A1
                bonus_prioridade = 0.0
                if esc == 1000:
                    bonus_prioridade -= area_proj * 0.15
                if fmt == preferencia_formato.upper():
                    bonus_prioridade -= area_proj * 0.20

                custo_total = desperdicio + bonus_prioridade
                if custo_total < menor_desperdicio:
                    menor_desperdicio = custo_total
                    melhor_opcao = (fmt, esc, larg_folha_m, alt_folha_m, larg_util_m, alt_util_m)

    # Fallback se nenhum couber perfeitamente com a margem desejada:
    # Escolher o maior formato (A0) na maior escala (2000)
    if melhor_opcao is None:
        fmt_fallback = formato_fixo.upper() if formato_fixo else "A0"
        esc_fallback = escala_fixa if escala_fixa else ESCALAS_NORMATIVAS[-1]
        larg_folha_m, alt_folha_m, larg_util_m, alt_util_m = calcular_dimensoes_model(fmt_fallback, esc_fallback)
        melhor_opcao = (fmt_fallback, esc_fallback, larg_folha_m, alt_folha_m, larg_util_m, alt_util_m)

    fmt_escolhido, esc_escolhido, lf_m, af_m, lu_m, au_m = melhor_opcao
    fator = esc_escolhido / 1000.0

    # Margens no ModelSpace
    m_esq, m_dir, m_sup, m_inf = MARGENS_PADRAO_MM[fmt_escolhido]
    m_esq_m = m_esq * fator
    m_inf_m = m_inf * fator

    # Centralizar a folha de modo que a área útil fique centrada sobre o centro do projeto
    # Centro da área útil relativo ao canto inferior esquerdo da folha:
    centro_util_rel_x = m_esq_m + (lu_m / 2.0)
    centro_util_rel_y = m_inf_m + (au_m / 2.0)

    # Coordenadas mínimas e máximas da folha no ModelSpace
    x_folha_min = centro_x - centro_util_rel_x
    y_folha_min = centro_y - centro_util_rel_y
    x_folha_max = x_folha_min + lf_m
    y_folha_max = y_folha_min + af_m

    folga_x = ((lu_m - dx) / dx) * 100.0 if dx > 0 else 0.0
    folga_y = ((au_m - dy) / dy) * 100.0 if dy > 0 else 0.0

    return EnquadramentoResultado(
        formato=fmt_escolhido,
        escala=esc_escolhido,
        fator_escala=fator,
        largura_folha_m=round(lf_m, 3),
        altura_folha_m=round(af_m, 3),
        largura_util_m=round(lu_m, 3),
        altura_util_m=round(au_m, 3),
        dx_projeto_m=round(dx, 3),
        dy_projeto_m=round(dy, 3),
        folga_x_perc=round(folga_x, 1),
        folga_y_perc=round(folga_y, 1),
        reserva_carimbo_largura_m=round(LARGURA_CARIMBO_MM * fator, 3),
        reserva_carimbo_altura_m=round(ALTURA_CARIMBO_MM * fator, 3),
        x_folha_min=round(x_folha_min, 3),
        y_folha_min=round(y_folha_min, 3),
        x_folha_max=round(x_folha_max, 3),
        y_folha_max=round(y_folha_max, 3),
        centro_projeto_x=round(centro_x, 3),
        centro_projeto_y=round(centro_y, 3),
    )
