"""
cpfc_core.py - Motor de Cálculo e Regras de Negócio (REN 1.059 ANEEL)
Módulo CPFC - Cálculo de Participação Financeira do Consumidor (IM3 Brasil / Concessionária)

Implementa:
  - Resolução Normativa ANEEL Nº 1.059 (Válido até 10/03/2027 - Versão 03)
  - Mapeamento oficial de subgrupos tarifários e Fatores K (Kc e Kg)
  - Cálculo analítico do Encargo de Responsabilidade da Distribuidora (ERD)
  - Proporcionalização do Custo da Obra (COP)
  - Cálculo da Participação Financeira do Consumidor (PF)
  - Sanitização e validação de dados de entrada
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# Mapeamento Oficial de Subgrupos Tarifários e Códigos de Consulta (Tabela I11:J30)
SUBGRUPOS_LOOKUP: Dict[str, str] = {
    "Subgrupo B1": "B1",
    "Subgrupo B2 rural": "B2rur",
    "Subgrupo B2 irrigação": "B2irrig",
    "Subgrupo B3": "B3",
    "Subgrupo B4a": "B4a",
    "Iluminação Publica - Bulbo de lampada": "B4b",
    "Subgrupo A4": "A4",
    "Subgrupo A3a": "A3a",
    "Subgrupo A3": "A3",
    "Subgrupo A2": "A2",
    "Subgrupo AS": "AS",
    "Subgrupo - BT1 Geração": "BT1 Geração",
    "Subgrupo - BT2 Geração": "BT2 Geração",
}

# Tabela Oficial de Fatores K da ANEEL (Kc e Kg em R$/kW - Linhas E50:G62)
FATORES_K: Dict[str, Dict[str, float]] = {
    "B1": {"kc": 1711.94, "kg": 0.0},
    "B2rur": {"kc": 1711.94, "kg": 0.0},
    "B2irrig": {"kc": 1711.94, "kg": 0.0},
    "B3": {"kc": 1711.94, "kg": 0.0},
    "B4a": {"kc": 941.39, "kg": 0.0},
    "B4b": {"kc": 1027.16, "kg": 0.0},
    "A4": {"kc": 1668.09, "kg": 1176.18},
    "A3a": {"kc": 1668.09, "kg": 1176.18},
    "A3": {"kc": 360.09, "kg": 525.48},
    "A2": {"kc": 54.99, "kg": 153.72},
    "AS": {"kc": 1711.94, "kg": 0.0},  # Tensão inferior a 2,3 kV (equiparado BT)
    "BT1 Geração": {"kc": 0.0, "kg": 882.47},
    "BT2 Geração": {"kc": 0.0, "kg": 2315.87},
}

# Lista oficial de Tipos de Ligação aceitos na planilha (I21:I27)
TIPOS_LIGACAO_PADRAO: List[str] = [
    "Acréscimo de carga",
    "Extensão de Rede",
    "Acréscimo de carga c/ complementação de fases",
    "Iluminação pública",
    "Engenharia - Extensão de rede",
    "Engenharia - Acréscimo de carga",
]

# Lista de Origens de Orçamento aceitas (C24)
ORIGENS_ORCAMENTO_PADRAO: List[str] = [
    "GOM",
    "OPD",
    "Engenharia",
]


@dataclass
class DadosCadastrais:
    """Informações cadastrais da obra e do cliente."""
    projeto: str = ""
    tipo_ligacao: str = "Acréscimo de carga"
    subgrupo: str = "Subgrupo B1"
    endereco: str = ""
    municipio: str = "PETRÓPOLIS"

    def sanitizar(self) -> "DadosCadastrais":
        return DadosCadastrais(
            projeto=str(self.projeto).strip().upper(),
            tipo_ligacao=str(self.tipo_ligacao).strip(),
            subgrupo=str(self.subgrupo).strip(),
            endereco=str(self.endereco).strip(),
            municipio=str(self.municipio).strip().upper(),
        )


@dataclass
class OrcamentoObra:
    """Custos da obra elétrica."""
    origem: str = "GOM"
    servico_terceiros: float = 0.0
    material: float = 0.0
    trafos: float = 0.0
    mao_de_obra: float = 0.0

    @property
    def transporte(self) -> float:
        """Transporte = 11% da Mão de Obra (se preenchida)."""
        return round(self.mao_de_obra * 0.11, 2)

    @property
    def custo_total(self) -> float:
        """Custo Total da Obra = Terceiros + Material (referência célula F32)."""
        return round(self.servico_terceiros + self.material, 2)

    def sanitizar(self) -> "OrcamentoObra":
        return OrcamentoObra(
            origem=str(self.origem).strip().upper() if self.origem else "GOM",
            servico_terceiros=max(0.0, float(self.servico_terceiros or 0.0)),
            material=max(0.0, float(self.material or 0.0)),
            trafos=max(0.0, float(self.trafos or 0.0)),
            mao_de_obra=max(0.0, float(self.mao_de_obra or 0.0)),
        )


@dataclass
class ParametrosDemanda:
    """Demandas elétricas de carga, geração e capacidade disponibilizada em kW."""
    demanda_carga: float = 0.0
    demanda_geracao: float = 0.0
    demanda_cliente_erd: Optional[float] = None
    demanda_disponibilizada: float = 0.0

    def get_demanda_erd(self) -> float:
        """Retorna a demanda utilizada para cálculo do ERD (G66)."""
        if self.demanda_cliente_erd is not None and self.demanda_cliente_erd > 0:
            return float(self.demanda_cliente_erd)
        return float(self.demanda_carga)

    def sanitizar(self) -> "ParametrosDemanda":
        c_erd = float(self.demanda_cliente_erd) if self.demanda_cliente_erd is not None else None
        return ParametrosDemanda(
            demanda_carga=max(0.0, float(self.demanda_carga or 0.0)),
            demanda_geracao=max(0.0, float(self.demanda_geracao or 0.0)),
            demanda_cliente_erd=max(0.0, c_erd) if c_erd is not None else None,
            demanda_disponibilizada=max(0.0, float(self.demanda_disponibilizada or 0.0)),
        )


@dataclass
class ResultadoCPFC:
    """Consolidação dos cálculos analíticos da REN 1.059."""
    codigo_subgrupo: str
    fator_kc: float
    fator_kg: float
    erd: float
    demanda_cliente: float
    fator_proporcionalizacao: float
    custo_total_obra: float
    cop: float
    pf: float
    status_pf: str
    possui_participacao: bool
    alerta: Optional[str] = None


def obter_codigo_subgrupo(subgrupo_texto: str) -> str:
    """Obtém o código tarifário (ex: B1, A4) a partir do texto do subgrupo."""
    texto = subgrupo_texto.strip()
    if texto in SUBGRUPOS_LOOKUP:
        return SUBGRUPOS_LOOKUP[texto]
    # Busca por correspondência exata de código
    for code in FATORES_K:
        if texto.upper() == code.upper():
            return code
    # Fallback padrão
    return "B1"


def obter_fatores_k(codigo_subgrupo: str) -> Tuple[float, float]:
    """Retorna os fatores (Kc, Kg) para o código tarifário especificado."""
    dados = FATORES_K.get(codigo_subgrupo, {"kc": 1711.94, "kg": 0.0})
    return dados.get("kc", 0.0), dados.get("kg", 0.0)


def calcular_cpfc(
    cadastrais: DadosCadastrais,
    orcamento: OrcamentoObra,
    demanda: ParametrosDemanda,
) -> ResultadoCPFC:
    """
    Executa o cálculo rigoroso da Participação Financeira do Consumidor.

    Regras da REN 1.059:
      - ERD = Demanda_ERD * Kc + max(0, Demanda_Geração - Demanda_ERD) * Kg
      - Demanda_Cliente = max(Demanda_Carga, Demanda_Geração)
      - Fator_Proporc = Demanda_Cliente / Demanda_Disponibilizada
      - COP = Custo_Total_Obra * Fator_Proporc
      - PF = max(0, COP - ERD)
    """
    cad = cadastrais.sanitizar()
    orc = orcamento.sanitizar()
    dem = demanda.sanitizar()

    codigo = obter_codigo_subgrupo(cad.subgrupo)
    kc, kg = obter_fatores_k(codigo)

    d_erd = dem.get_demanda_erd()
    d_ger = dem.demanda_geracao
    d_carga = dem.demanda_carga
    d_disp = dem.demanda_disponibilizada

    # 1. Cálculo do Encargo de Responsabilidade da Distribuidora (ERD) - Célula G76
    # Se G68 <= G66: G66 * G72
    # Se G68 > G66: G66 * G72 + (G68 - G66) * G74
    if d_ger > d_erd:
        erd = (d_erd * kc) + ((d_ger - d_erd) * kg)
    else:
        erd = d_erd * kc
    erd = round(erd, 2)

    # 2. Demanda do Cliente - Célula G82
    demanda_cliente = max(d_carga, d_ger)

    # 3. Fator de Proporcionalização - Célula G84
    alerta: Optional[str] = None
    if d_disp <= 0:
        fator_proporc = 0.0
        alerta = "Demanda disponibilizada não informada ou zero."
    else:
        fator_proporc = demanda_cliente / d_disp

    # 4. Custo Total da Obra - Célula G86 / F32
    custo_total = orc.custo_total

    # 5. Custo Proporcionalizado da Obra (COP) - Célula G88
    if d_disp > 0 and d_disp < demanda_cliente:
        cop = 0.0
        alerta = "DEMANDA DISPONIBILIZADA MENOR QUE DEMANDA DO CLIENTE"
    else:
        cop = round(custo_total * fator_proporc, 2)

    # 6. Participação Financeira (PF) - Célula G93
    saldo = cop - erd
    if saldo <= 0.0 or cop <= 0.0:
        pf = 0.0
        status_pf = "SEM PARTICIPAÇÃO FINANCEIRA"
        possui_pf = False
    else:
        pf = round(saldo, 2)
        status_pf = f"COM PARTICIPAÇÃO FINANCEIRA (R$ {pf:,.2f})"
        possui_pf = True

    return ResultadoCPFC(
        codigo_subgrupo=codigo,
        fator_kc=kc,
        fator_kg=kg,
        erd=erd,
        demanda_cliente=round(demanda_cliente, 2),
        fator_proporcionalizacao=round(fator_proporc, 6),
        custo_total_obra=custo_total,
        cop=cop,
        pf=pf,
        status_pf=status_pf,
        possui_participacao=possui_pf,
        alerta=alerta,
    )
