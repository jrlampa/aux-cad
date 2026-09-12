"""
Módulo de Tabelas Técnicas de Referência para Redes de Distribuição (BT)
Baseado nas Tabelas Oficiais de Projetos (Tabela 7 e Tabela 9).
Fonte: OneNote de Referência Técnica (BASE.one / INFO DE PROJETO IMPORTANTE).

Gera e gerencia consultas rápidas via SQLite3 e JSON, além de exportar dados para LISPs e CLI.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional


@dataclass
class CondutorBT:
    condutor: str
    fase: str
    neutro: str
    corrente_a: float
    tracao_dan: float
    diametro_total_mm: float
    massa_total_kg_km: float
    resistencia_r_ohm_km: float
    reatancia_x_ohm_km: float


@dataclass
class EstruturaBT:
    estrutura: str
    codigo: str
    cabo_neutro_mm2: str
    cabo_fase: str
    resistencia_min_poste_dan: Optional[int]
    angulo_utilizacao: str
    fixacao_rede: str


@dataclass
class CaboMTEsforco:
    tipo_cabo: str
    vao_m: int
    fase_1_dan: float
    fase_2_dan: float
    fase_3_dan: float
    neutro_dan: float


# ==============================================================================
# DADOS REAIS - TABELA 9: CONDUTORES DE BAIXA TENSÃO
# ==============================================================================
CONDUTORES_BT_DADOS: List[CondutorBT] = [
    CondutorBT(
        condutor="3x150+1x80",
        fase="3x150",
        neutro="1x80",
        corrente_a=326.0,
        tracao_dan=554.0,
        diametro_total_mm=51.0,
        massa_total_kg_km=1878.0,
        resistencia_r_ohm_km=0.2775,
        reatancia_x_ohm_km=0.0867,
    ),
    CondutorBT(
        condutor="3x95+1x54,6",
        fase="3x95",
        neutro="1x54,6",
        corrente_a=244.0,
        tracao_dan=393.0,
        diametro_total_mm=43.0,
        massa_total_kg_km=1270.0,
        resistencia_r_ohm_km=0.4311,
        reatancia_x_ohm_km=0.0902,
    ),
    CondutorBT(
        condutor="3x50+1x54,6",
        fase="3x50",
        neutro="1x54,6",
        corrente_a=169.0,
        tracao_dan=260.0,
        diametro_total_mm=37.0,
        massa_total_kg_km=765.0,
        resistencia_r_ohm_km=0.8634,
        reatancia_x_ohm_km=0.0943,
    ),
    CondutorBT(
        condutor="3x35+1x54,6",
        fase="3x35",
        neutro="1x54,6",
        corrente_a=136.0,
        tracao_dan=235.0,
        diametro_total_mm=37.0,
        massa_total_kg_km=700.0,
        resistencia_r_ohm_km=1.1694,
        reatancia_x_ohm_km=0.0974,
    ),
]


# ==============================================================================
# DADOS REAIS - TABELA 7: ESTRUTURAS DE BAIXA TENSÃO
# ==============================================================================
def _gerar_dados_estrutura(
    nome: str,
    codigo: str,
    res_list: List[Optional[int]],
    angulo: str,
    fixacao: str,
) -> List[EstruturaBT]:
    fases_neutros = [
        ("54,5", "1x35 ou 2x25"),
        ("54,6", "3X35"),
        ("54,6", "3X50"),
        ("54,6", "3X95"),
        ("80", "3X150"),
    ]
    itens = []
    for (neutro, fase), res in zip(fases_neutros, res_list):
        itens.append(
            EstruturaBT(
                estrutura=nome,
                codigo=codigo,
                cabo_neutro_mm2=neutro,
                cabo_fase=fase,
                resistencia_min_poste_dan=res,
                angulo_utilizacao=angulo,
                fixacao_rede=fixacao,
            )
        )
    return itens


ESTRUTURAS_BT_DADOS: List[EstruturaBT] = []
# 1. Tangente (SI1)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Tangente", "SI1", [300, 300, 300, 300, 300], "0° a 30°", "Conjunto de suspensão"
    )
)
# 2. Tangente Afastamento (SI1.AF)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Tangente Afastamento", "SI1.AF", [300, 300, 300, 600, 600], "0° a 30°", "Conjunto de suspensão"
    )
)
# 3. Tangente Afastamento Duplo (SI1.2AF)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Tangente Afastamento Duplo", "SI1.2AF", [300, 300, 300, 600, 600], "0° a 30°", "Conjunto de suspensão"
    )
)
# 4. Tangente com Derivação Oposta (SI1B.SI3)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Tangente com Derivação Oposta", "SI1B.SI3", [300, 300, 300, 600, 600], "0°", "Conjunto de suspensão / Suporte de ancoragem"
    )
)
# 5. Tangente com Derivação do mesmo Lado (SI1A.SI3)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Tangente com Derivação do mesmo Lado", "SI1A.SI3", [300, 300, 300, 600, 600], "0° a 30°", "Conjunto de suspensão / Suporte de ancoragem"
    )
)
# 6. Tangente com duas derivações (SI1.SI4)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Tangente com duas derivações", "SI1.SI4", [300, 300, 300, 600, 600], "0°", "Conjunto de suspensão / Suporte de ancoragem"
    )
)
# 7. Derivação em alinhamento com a Rede Aérea Nua (SI3.S3)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Derivação em alinhamento com a Rede Aérea Nua", "SI3.S3", [300, 300, 300, 600, 600], "0°", "Suporte de ancoragem / isolador roldana"
    )
)
# 8. Ancoragem Dupla com derivação (SI4.SI3)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Ancoragem Dupla com derivação", "SI4.SI3", [300, 300, 300, 600, 600], "0°", "Suporte de ancoragem / Isolador castanha"
    )
)
# 9. Ancoragem Dupla (SI4)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Ancoragem Dupla", "SI4", [300, 300, 300, 600, 600], "0°", "Suporte de ancoragem"
    )
)
# 10. Ancoragem (SI3)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Ancoragem", "SI3", [300, 300, 300, 600, 600], "30° a 90°", "Suporte de ancoragem"
    )
)
# 11. Ancoragem dupla (SI3.SI3)
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Ancoragem dupla", "SI3.SI3", [300, 300, 300, 600, 600], "60° a 90°", "Suporte de ancoragem / isolador castanha"
    )
)
# 12. Derivação no Vão da Rede Secundária
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Derivação no Vão da Rede Secundária", "DERIV_VAO", [None, None, None, None, None], "-", "-"
    )
)
# 13. Cruzamento (flytap) - com Conexão
ESTRUTURAS_BT_DADOS.extend(
    _gerar_dados_estrutura(
        "Cruzamento (flytap) - com Conexão", "FLYTAP", [None, None, None, None, None], "-", "-"
    )
)


# ==============================================================================
# DADOS REAIS - ESFORÇOS CABOS MÉDIA TENSÃO (MT) POR VÃO (daN)
# Fonte: Diretório "CALC_ESF" (Cálculo de Esforço / IM3 Brasil)
# ==============================================================================
_MT_TABELAS_RAW: Dict[str, Dict[int, tuple]] = {
    "1/0 CAA": {
        20: (125, 250, 375, 100), 30: (140, 280, 420, 112), 40: (160, 320, 480, 128),
        50: (189, 378, 566, 151), 60: (218, 435, 653, 174), 70: (246, 493, 739, 197),
        80: (275, 550, 825, 220), 100: (315, 630, 945, 252), 120: (355, 710, 1065, 284),
        150: (400, 800, 1200, 320), 200: (465, 930, 1395, 372),
    },
    "4/0 CAA": {
        20: (180, 360, 540, 144), 30: (250, 500, 750, 200), 40: (320, 640, 960, 256),
        50: (378, 756, 1133, 302), 60: (436, 871, 1307, 348), 70: (493, 987, 1480, 395),
        80: (551, 1102, 1653, 441), 100: (602, 1203, 1805, 481), 120: (652, 1304, 1956, 522),
        150: (706, 1412, 2118, 565), 200: (784, 1568, 2352, 627),
    },
    "336,4 CAA": {
        20: (389, 778, 1167, 311), 30: (489, 978, 1467, 391), 40: (589, 1178, 1767, 471),
        50: (661, 1322, 1982, 529), 60: (733, 1465, 2198, 586), 70: (804, 1609, 2413, 643),
        80: (876, 1752, 2628, 701), 100: (956, 1911, 2867, 764), 120: (1035, 2070, 3105, 828),
        150: (1140, 2280, 3420, 912), 200: (1295, 2590, 3885, 1036),
    },
    "4 CAA": {
        20: (60, 120, 180, 48), 30: (68, 135, 203, 54), 40: (75, 150, 225, 60),
        50: (90, 180, 270, 72), 60: (105, 210, 315, 84), 70: (120, 240, 360, 96),
        80: (135, 270, 405, 108), 100: (155, 310, 465, 124), 120: (175, 350, 525, 140),
        150: (204, 407, 611, 163), 200: (249, 498, 747, 199),
    },
    "1/0 CA": {
        20: (110, 220, 330, 88), 30: (120, 240, 360, 96), 40: (125, 250, 375, 100),
        50: (140, 281, 421, 112), 60: (156, 311, 467, 124), 70: (171, 342, 512, 137),
        80: (186, 372, 558, 149),
    },
    "4/0 CA": {
        20: (155, 310, 465, 124), 30: (170, 340, 510, 136), 40: (190, 380, 570, 152),
        50: (221, 443, 664, 177), 60: (253, 505, 758, 202), 70: (284, 568, 851, 227),
        80: (315, 630, 945, 252), 100: (375, 750, 1125, 300),
    },
    "336,4 CA": {
        20: (246, 492, 738, 197), 30: (286, 571, 857, 228), 40: (325, 650, 975, 260),
        50: (365, 729, 1094, 292), 60: (404, 808, 1212, 323), 70: (444, 887, 1331, 355),
        80: (483, 966, 1449, 386), 100: (561, 1122, 1683, 449), 120: (639, 1278, 1917, 511),
    },
    "2 CA": {
        20: (76, 152, 228, 61), 30: (91, 182, 273, 73), 40: (96, 192, 288, 77),
        50: (105, 211, 316, 84), 60: (115, 229, 344, 92), 70: (124, 248, 371, 99),
        80: (133, 266, 399, 106), 100: (152, 303, 455, 121),
    },
    "35/50 XLPE": {
        10: (154, 307, 461, 42), 20: (188, 375, 563, 48), 30: (226, 453, 679, 54),
        40: (259, 517, 776, 60), 50: (286, 571, 857, 72), 60: (309, 617, 926, 84),
        70: (328, 656, 984, 96), 80: (345, 690, 1035, 108),
    },
    "185 XLPE": {
        10: (171, 343, 514, 82), 20: (235, 471, 706, 88), 30: (280, 561, 841, 96),
        40: (336, 672, 1008, 100), 50: (375, 751, 1126, 112), 60: (410, 819, 1229, 124),
        70: (440, 880, 1320, 137), 80: (466, 933, 1399, 149),
    },
}

CABOS_MT_DADOS: List[CaboMTEsforco] = []
for cabo_nome, vaos in _MT_TABELAS_RAW.items():
    for vao, (f1, f2, f3, neu) in vaos.items():
        CABOS_MT_DADOS.append(
            CaboMTEsforco(
                tipo_cabo=cabo_nome,
                vao_m=vao,
                fase_1_dan=float(f1),
                fase_2_dan=float(f2),
                fase_3_dan=float(f3),
                neutro_dan=float(neu),
            )
        )


# ==============================================================================
# PERSISTÊNCIA: SQLITE3 E JSON
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tabelas_referencia.sqlite3"
JSON_PATH = BASE_DIR / "tabelas_referencia.json"


def exportar_para_json(caminho: Path = JSON_PATH) -> Path:
    """Exporta as tabelas para formato JSON estruturado."""
    payload = {
        "_metadados": {
            "titulo": "Tabelas Técnicas de Referência - Redes BT e MT",
            "fonte": "OneNote BASE.one e Diretório CALC_ESF (IM3 Brasil)",
            "tabelas": [
                "Tabela 7 - Estruturas de Baixa Tensão",
                "Tabela 9 - Condutores de Baixa Tensão",
                "Tabelas MT - Esforços de Cabos CA, CAA e XLPE por Vão (daN)",
            ],
            "versao": "2.0.0",
        },
        "condutores_bt": [asdict(c) for c in CONDUTORES_BT_DADOS],
        "estruturas_bt": [asdict(e) for e in ESTRUTURAS_BT_DADOS],
        "cabos_mt_esforcos": [asdict(m) for m in CABOS_MT_DADOS],
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return caminho


def inicializar_sqlite(caminho_db: Path = DB_PATH) -> sqlite3.Connection:
    """Cria e popula o banco SQLite3 com dados indexados."""
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS condutores_bt;")
    cursor.execute("""
        CREATE TABLE condutores_bt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condutor TEXT UNIQUE NOT NULL,
            fase TEXT NOT NULL,
            neutro TEXT NOT NULL,
            corrente_a REAL NOT NULL,
            tracao_dan REAL NOT NULL,
            diametro_total_mm REAL NOT NULL,
            massa_total_kg_km REAL NOT NULL,
            resistencia_r_ohm_km REAL NOT NULL,
            reatancia_x_ohm_km REAL NOT NULL
        );
    """)

    cursor.execute("DROP TABLE IF EXISTS estruturas_bt;")
    cursor.execute("""
        CREATE TABLE estruturas_bt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estrutura TEXT NOT NULL,
            codigo TEXT NOT NULL,
            cabo_neutro_mm2 TEXT NOT NULL,
            cabo_fase TEXT NOT NULL,
            resistencia_min_poste_dan INTEGER,
            angulo_utilizacao TEXT,
            fixacao_rede TEXT
        );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cond_nome ON condutores_bt (condutor);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_est_cod ON estruturas_bt (codigo);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_est_fase ON estruturas_bt (cabo_fase);")

    # Inserção de dados dos condutores
    for c in CONDUTORES_BT_DADOS:
        cursor.execute("""
            INSERT INTO condutores_bt (
                condutor, fase, neutro, corrente_a, tracao_dan,
                diametro_total_mm, massa_total_kg_km, resistencia_r_ohm_km, reatancia_x_ohm_km
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            c.condutor, c.fase, c.neutro, c.corrente_a, c.tracao_dan,
            c.diametro_total_mm, c.massa_total_kg_km, c.resistencia_r_ohm_km, c.reatancia_x_ohm_km
        ))

    # Inserção de dados das estruturas
    for e in ESTRUTURAS_BT_DADOS:
        cursor.execute("""
            INSERT INTO estruturas_bt (
                estrutura, codigo, cabo_neutro_mm2, cabo_fase,
                resistencia_min_poste_dan, angulo_utilizacao, fixacao_rede
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            e.estrutura, e.codigo, e.cabo_neutro_mm2, e.cabo_fase,
            e.resistencia_min_poste_dan, e.angulo_utilizacao, e.fixacao_rede
        ))

    # Tabela de Esforços MT
    cursor.execute("DROP TABLE IF EXISTS cabos_mt_esforcos;")
    cursor.execute("""
        CREATE TABLE cabos_mt_esforcos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_cabo TEXT NOT NULL,
            vao_m INTEGER NOT NULL,
            fase_1_dan REAL NOT NULL,
            fase_2_dan REAL NOT NULL,
            fase_3_dan REAL NOT NULL,
            neutro_dan REAL NOT NULL
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mt_cabo ON cabos_mt_esforcos (tipo_cabo);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mt_vao ON cabos_mt_esforcos (vao_m);")

    for m in CABOS_MT_DADOS:
        cursor.execute("""
            INSERT INTO cabos_mt_esforcos (
                tipo_cabo, vao_m, fase_1_dan, fase_2_dan, fase_3_dan, neutro_dan
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, (
            m.tipo_cabo, m.vao_m, m.fase_1_dan, m.fase_2_dan, m.fase_3_dan, m.neutro_dan
        ))

    conn.commit()
    return conn


# ==============================================================================
# API DE CONSULTA EM MEMÓRIA / SQLITE
# ==============================================================================
def buscar_condutor(termo: str) -> Optional[CondutorBT]:
    """Busca condutor por nome exato ou aproximação (ex: '150', '3x150+1x80', '95', 'PR95', 'PR150')."""
    termo_limpo = termo.strip().lower().replace(".", ",").replace("-", "")
    for prefixo in ("pr", "bt", "cabo"):
        if termo_limpo.startswith(prefixo) and len(termo_limpo) > len(prefixo):
            termo_limpo = termo_limpo[len(prefixo):].strip()

    # 1. Match exato
    for c in CONDUTORES_BT_DADOS:
        if c.condutor.lower() == termo_limpo:
            return c
    # 2. Match por bitola de fase
    for c in CONDUTORES_BT_DADOS:
        if termo_limpo in c.condutor.lower() or termo_limpo in c.fase.lower():
            return c
    return None


def obter_tracao_condutor(condutor: str) -> float:
    """Retorna o valor da tração nominal em daN do condutor ou 0.0 se não encontrado."""
    c = buscar_condutor(condutor)
    return c.tracao_dan if c else 0.0


def buscar_tracao_mt(tipo_cabo: str, vao_m: float = 40.0, condutores: Any = 3) -> float:
    """Retorna a tração em daN do cabo de MT para o vão especificado, com interpolação e extrapolação contínua."""
    cabo_norm = tipo_cabo.strip().upper().replace(" ", "").replace(",", ".")
    chave_encontrada = None
    # 1. Busca exata prioritária (ex: '4CAA' == '4CAA', evitando falso positivo com '336.4CAA')
    for k in _MT_TABELAS_RAW:
        k_norm = k.upper().replace(" ", "").replace(",", ".")
        if cabo_norm == k_norm:
            chave_encontrada = k
            break
    # 2. Busca parcial se não achou exato
    if not chave_encontrada:
        for k in _MT_TABELAS_RAW:
            k_norm = k.upper().replace(" ", "").replace(",", ".")
            if cabo_norm in k_norm or k_norm in cabo_norm:
                chave_encontrada = k
                break
    if not chave_encontrada:
        return 0.0

    vaos_map = _MT_TABELAS_RAW[chave_encontrada]
    vaos_ordenados = sorted(vaos_map.keys())
    col_idx = 0 if condutores == 1 else (1 if condutores == 2 else (3 if condutores in (4, "neutro", "N") else 2))

    if int(vao_m) in vaos_map and vao_m == int(vao_m):
        return float(vaos_map[int(vao_m)][col_idx])

    # Abaixo do menor vão tabelado: regra de 3 proporcional ao menor vão
    v_min = vaos_ordenados[0]
    if vao_m < v_min:
        f_min = float(vaos_map[v_min][col_idx])
        return round(f_min * (max(vao_m, 1.0) / v_min), 1)

    # Acima do maior vão tabelado: extrapolação linear baseada no último intervalo
    v_max = vaos_ordenados[-1]
    if vao_m > v_max:
        v_prev = vaos_ordenados[-2]
        f_prev = float(vaos_map[v_prev][col_idx])
        f_max = float(vaos_map[v_max][col_idx])
        taxa = (f_max - f_prev) / (v_max - v_prev)
        return round(f_max + taxa * (vao_m - v_max), 1)

    # Interpolação linear entre os dois vãos adjacentes
    v1, v2 = v_min, v_max
    for i in range(len(vaos_ordenados) - 1):
        if vaos_ordenados[i] <= vao_m <= vaos_ordenados[i + 1]:
            v1, v2 = vaos_ordenados[i], vaos_ordenados[i + 1]
            break

    f1 = float(vaos_map[v1][col_idx])
    f2 = float(vaos_map[v2][col_idx])
    f_interp = f1 + ((vao_m - v1) / (v2 - v1)) * (f2 - f1)
    return round(f_interp, 1)


def calcular_esforco_linha(expressao: str, vao_m: float = 40.0) -> Dict[str, Any]:
    """Calcula a tração total da linha em daN, suportando valor manual, cabo BT, cabo MT, prefixos (1#, 3#) ou combinação MT + BT."""
    expr = expressao.strip()
    if not expr:
        return {"total_dan": 0.0, "mt_dan": 0.0, "bt_dan": 0.0, "descricao": "0 daN", "modo": "vazio"}

    # Combinação MT + BT colineares (ex: '1/0 + 150' ou '4/0CAA + PR95' ou '4CAA + 4/0 + 1#1/0')
    if "+" in expr and not expr.startswith("+"):
        partes = [p.strip() for p in expr.split("+") if p.strip()]
        resultados = [calcular_esforco_linha(p, vao_m) for p in partes]
        total = sum(r["total_dan"] for r in resultados)
        mt_total = sum(r["mt_dan"] for r in resultados)
        bt_total = sum(r["bt_dan"] for r in resultados)
        desc = " + ".join(r["descricao"] for r in resultados)
        return {
            "total_dan": round(total, 1),
            "mt_dan": round(mt_total, 1),
            "bt_dan": round(bt_total, 1),
            "descricao": f"{desc} -> SOMA = {total:.0f} daN",
            "modo": "combinado",
        }

    # Detecta prefixo de quantidade de condutores (ex: '3#4CAA', '1#1/0', '1X1/0', '1N1/0', 'N#1/0')
    num_cond = 3
    is_neutro = False
    cabo_limpo = expr
    m_neutro = re.match(r"^(?:1N|N#|NEUTRO\s*)[-\s]*(.+)$", expr, re.IGNORECASE)
    if m_neutro:
        is_neutro = True
        num_cond = 1
        cabo_limpo = m_neutro.group(1).strip()
    else:
        m_qtd = re.match(r"^(\d+)[#X\*][-\s]*(.+)$", expr, re.IGNORECASE)
        if m_qtd:
            num_cond = int(m_qtd.group(1))
            cabo_limpo = m_qtd.group(2).strip()

    s_upper = cabo_limpo.upper()
    # Valor manual forçado com sufixo 'd', 'dan' ou '='
    if s_upper.endswith("DAN") or s_upper.endswith("D") or s_upper.startswith("="):
        num_str = s_upper.replace("DAN", "").replace("D", "").replace("=", "").strip()
        try:
            val = float(num_str.replace(",", "."))
            return {"total_dan": val, "mt_dan": 0.0, "bt_dan": 0.0, "descricao": f"Manual {val:.0f} daN", "modo": "manual"}
        except ValueError:
            pass

    # Identifica se é cabo de MT
    eh_mt = any(t in s_upper for t in ["CAA", "XLPE", "MCM", "1/0", "4/0", "336", "2CA", "4CA"])
    if eh_mt:
        cond_param = "neutro" if is_neutro else num_cond
        tracao_mt = buscar_tracao_mt(cabo_limpo, vao_m=vao_m, condutores=cond_param)
        if tracao_mt > 0.0:
            qtd_desc = "neutro " if is_neutro else (f"{num_cond}#" if num_cond != 3 else "")
            return {
                "total_dan": tracao_mt,
                "mt_dan": tracao_mt,
                "bt_dan": 0.0,
                "descricao": f"MT {qtd_desc}{cabo_limpo} ({vao_m:.0f}m: {tracao_mt:.0f} daN)",
                "modo": "mt",
            }

    # Identifica se é cabo de BT (PR150, PR95, PR50, PR35, 150, 95, etc.)
    c_bt = buscar_condutor(cabo_limpo)
    if c_bt and (s_upper.startswith("PR") or cabo_limpo in ["150", "95", "50", "35"] or "3X" in s_upper):
        return {
            "total_dan": c_bt.tracao_dan,
            "mt_dan": 0.0,
            "bt_dan": c_bt.tracao_dan,
            "descricao": f"BT {c_bt.condutor} ({c_bt.tracao_dan:.0f} daN)",
            "modo": "bt",
        }

    # Valor numérico puro digitado diretamente em daN
    try:
        val = float(expr.replace(",", "."))
        return {"total_dan": val, "mt_dan": 0.0, "bt_dan": 0.0, "descricao": f"Manual {val:.0f} daN", "modo": "manual"}
    except ValueError:
        return {"total_dan": 0.0, "mt_dan": 0.0, "bt_dan": 0.0, "descricao": "Não identificado (0 daN)", "modo": "erro"}


def buscar_estrutura(codigo_ou_nome: str, fase: Optional[str] = None) -> List[EstruturaBT]:
    """Busca estruturas pelo código (ex: SI1, SI3) ou nome, opcionalmente filtrando por cabo fase."""
    termo = codigo_ou_nome.strip().upper()
    fase_filtro = fase.strip().upper() if fase else None
    resultados = []

    for e in ESTRUTURAS_BT_DADOS:
        match_cod = termo == e.codigo.upper() or termo in e.estrutura.upper()
        if match_cod:
            if not fase_filtro or fase_filtro in e.cabo_fase.upper():
                resultados.append(e)

    return resultados


def consultar_resistencia_poste(codigo_est: str, fase: str) -> Optional[int]:
    """Retorna a resistência mínima do poste (300 ou 600 daN) para a combinação."""
    ests = buscar_estrutura(codigo_est, fase)
    if ests and ests[0].resistencia_min_poste_dan is not None:
        return ests[0].resistencia_min_poste_dan
    return None


if __name__ == "__main__":
    print(f"Gerando JSON em: {JSON_PATH}")
    exportar_para_json()
    print(f"Gerando SQLite3 em: {DB_PATH}")
    conn = inicializar_sqlite()
    conn.close()
    print("Sucesso! Bases de dados técnicas geradas com sucesso.")
