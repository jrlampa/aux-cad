"""
Módulo de Cálculo em Tempo Real (Live Preview) para CQT e Carregamento de Transformador.
Permite cálculo instantâneo na interface gráfica sem depender da abertura do Excel.
Inclui verificação normativa com limite de Queda de Tensão máxima de 6,00%.
"""

from typing import Dict, List, Tuple

# Constantes de Queda de Tensão por tipo de condutor (VLOOKUP da BASE DE DADOS da planilha oficial)
CONDUTORES_K = {
    "3x150+70 - Al - F.P 1": 0.0508,
    "3x150+1x80 - Al - F.P 1": 0.0573,
    "3x120+70 (nó) - Al - F.P 1": 0.0523,
    "3x95+1x70 - Al - F.P 1": 0.0850,
    "3x95+1x50 - Al - F.P 1": 0.0850,
    "3x95+1x54,6 - Al - F.P 1": 0.0891,
    "3x70+70 (nó) - Al - F.P 1": 0.0915,
    "3x70+1x70 - Al - F.P 1": 0.1175,
    "3x50+50 (nó) - Al - F.P 1": 0.1324,
    "3x50+1x54,6 - Al - F.P 1": 0.1784,
    "3x50+1x50 - Al - F.P 1": 0.1784,
    "3x35+35 (nó) - Al - F.P 1": 0.1793,
    "3x35+1x35 - Al - F.P 1": 0.2300,
    "3x35+1x50 - Al - F.P 1": 0.2300,
    "3x35+1x54,6 - Al - F.P 1": 0.2416,
    "2x16+25 - Al - F.P 1": 0.8400,
    "Subterrâneo 150 - Al - F.P 1": 0.0573,
    "Subterrâneo 95 - Al - F.P 1": 0.0850,
    "Subterrâneo 50 - Al - F.P 1": 0.1699,
    "Subterrâneo 25 - Al - F.P 1": 0.3340,
    "Subterrâneo 16 - Al - F.P 1": 0.5060,
}

# Tabela 16: Demanda Diversificada (kVA por consumidor) - Classe C
TABELA_16_CLASSE_C = {
    1: 2.60,
    6: 2.20,
    11: 1.90,
    16: 1.70,
    21: 1.50,
    26: 1.40,
    31: 1.30,
    41: 1.30,
}

LIMITE_NORMATIVO_QT = 6.00  # Limite máximo admissível de Queda de Tensão


def get_fator_condutor(cabo_str: str) -> float:
    """Busca a constante de queda de tensão pelo nome do condutor ou código aproximado."""
    if not cabo_str:
        return 0.1784  # Default 3x50

    cabo_clean = cabo_str.strip()
    if cabo_clean in CONDUTORES_K:
        return CONDUTORES_K[cabo_clean]

    c = cabo_clean.upper()
    if "150" in c:
        return 0.0508
    elif "120" in c:
        return 0.0523
    elif "95" in c:
        return 0.0850
    elif "70" in c:
        return 0.1175
    elif "50" in c:
        return 0.1784
    elif "35" in c:
        return 0.2416
    elif "16" in c:
        return 0.8400

    return 0.1784


def calcular_dmdi(total_clientes: int, classe: str = "CLASSE C") -> float:
    """Calcula a Demanda Média Diversificada Individual (DMDI) com base na Tabela 16."""
    if total_clientes <= 0:
        return 1.30
    elif total_clientes < 6:
        return 2.60
    elif total_clientes < 11:
        return 2.20
    elif total_clientes < 16:
        return 1.90
    elif total_clientes < 21:
        return 1.70
    elif total_clientes < 26:
        return 1.50
    elif total_clientes < 31:
        return 1.40
    else:
        return 1.30


def calcular_cqt_topologia(trechos: List[Dict], potencia_trafo: float = 150.0, dmdi: float = 1.30) -> Dict:
    """
    Executa o cálculo topológico de Queda de Tensão para uma lista de trechos.
    Cada trecho contém:
      letra, montante, comprimento_m, condutor, mono, bi, tri, esp_carga, ip70, ip125, ip250
    Retorna resultados detalhados por trecho e resumo geral do circuito.
    """
    if not trechos:
        return {
            "trechos_resultado": [],
            "pior_qt": 0.0,
            "trecho_pior_qt": "-",
            "tem_alerta_normativo": False,
            "trechos_em_alerta": [],
            "demanda_total_kva": 0.0,
            "carregamento_trafo": 0.0,
            "total_clientes": 0,
        }

    # 1. Totaliza clientes e cargas próprias de cada trecho
    tot_clientes = 0
    tot_ip_demanda = 0.0
    trechos_calc = []

    for t in trechos:
        letra = str(t.get("letra", "")).strip().upper()
        montante = str(t.get("montante", "TRAFO")).strip().upper()
        try:
            comp_m = float(t.get("comprimento_m", 0) or 0)
        except ValueError:
            comp_m = 0.0
        comp_hm = comp_m / 100.0  # Hectômetros

        cabo = str(t.get("condutor", "")).strip()
        fator_k = get_fator_condutor(cabo)

        # Clientes
        try: mono = int(t.get("mono", 0) or 0)
        except ValueError: mono = 0
        try: bi = int(t.get("bi", 0) or 0)
        except ValueError: bi = 0
        try: tri = int(t.get("tri", 0) or 0)
        except ValueError: tri = 0
        try: esp = float(t.get("esp_carga", 0) or 0)
        except ValueError: esp = 0.0

        n_cli = mono + bi + tri
        tot_clientes += n_cli

        # Iluminação Pública (kVA)
        try: ip70 = int(t.get("ip70", 0) or 0)
        except ValueError: ip70 = 0
        try: ip125 = int(t.get("ip125", 0) or 0)
        except ValueError: ip125 = 0
        try: ip250 = int(t.get("ip250", 0) or 0)
        except ValueError: ip250 = 0

        dem_ip = (ip70 * 0.07) + (ip125 * 0.125) + (ip250 * 0.25)
        tot_ip_demanda += dem_ip

        trechos_calc.append({
            "letra": letra,
            "montante": montante,
            "comp_hm": comp_hm,
            "comp_m": comp_m,
            "cabo": cabo,
            "fator_k": fator_k,
            "n_cli": n_cli,
            "dem_ip": dem_ip,
            "esp": esp,
            "carga_clientes": 0.0,
            "carga_propria": 0.0,
            "carga_jusante": 0.0,
            "momento": 0.0,
            "qt_parcial": 0.0,
            "qt_acumulada": 0.0,
            "em_alerta": False,
        })

    # 2. Carga própria por trecho
    # Se dmdi não foi informado, calcula com base no total de clientes
    if dmdi <= 0:
        dmdi = calcular_dmdi(tot_clientes)

    for item in trechos_calc:
        item["carga_clientes"] = (item["n_cli"] * dmdi) + item["esp"]
        item["carga_propria"] = item["carga_clientes"] + item["dem_ip"]

    # 3. Propagação de jusante (de baixo para cima na árvore topológica)
    # Executa passadas reversas para somar cargas que dependem deste trecho
    for _ in range(len(trechos_calc)):
        for item in trechos_calc:
            l = item["letra"]
            # Soma carga própria + jusante dos filhos diretos
            soma_filhos = sum(
                f["carga_propria"] + f["carga_jusante"]
                for f in trechos_calc
                if f["montante"] == l
            )
            item["carga_jusante"] = soma_filhos

    # 4. Cálculo de Momento e Queda de Tensão
    for item in trechos_calc:
        c_hm = item["comp_hm"]
        d = item["carga_propria"]
        g = item["carga_jusante"]
        # Momento = ((D/2) + G) * Comprimento(hm)
        item["momento"] = ((d / 2.0) + g) * c_hm
        item["qt_parcial"] = item["momento"] * item["fator_k"]

    # 5. Queda de Tensão Acumulada (do Trafo até o final do trecho)
    qt_dict = {}
    pior_qt = 0.0
    trecho_pior = "-"
    trechos_em_alerta = []

    for item in trechos_calc:
        l = item["letra"]
        m = item["montante"]
        k_parcial = item["qt_parcial"]

        if m in ["TRAFO", "", "None"]:
            qt_tot = k_parcial
        else:
            qt_mont = qt_dict.get(m, 0.0)
            qt_tot = qt_mont + k_parcial

        qt_dict[l] = qt_tot
        item["qt_acumulada"] = qt_tot

        # Checagem normativa (não pode ser maior que 6.00%)
        if qt_tot > LIMITE_NORMATIVO_QT:
            item["em_alerta"] = True
            trechos_em_alerta.append(l)

        if qt_tot > pior_qt:
            pior_qt = qt_tot
            trecho_pior = l

    # 6. Totais e Carregamento do Trafo
    demanda_total = sum(t["carga_propria"] for t in trechos_calc)
    carregamento = (demanda_total / potencia_trafo * 100.0) if potencia_trafo > 0 else 0.0

    return {
        "trechos_resultado": trechos_calc,
        "pior_qt": pior_qt,
        "trecho_pior_qt": trecho_pior,
        "tem_alerta_normativo": len(trechos_em_alerta) > 0,
        "trechos_em_alerta": trechos_em_alerta,
        "demanda_total_kva": demanda_total,
        "carregamento_trafo": carregamento,
        "total_clientes": tot_clientes,
    }
