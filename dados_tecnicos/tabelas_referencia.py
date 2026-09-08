"""
Módulo de Tabelas Técnicas de Referência para Redes de Distribuição (BT)
Baseado nas Tabelas Oficiais de Projetos (Tabela 7 e Tabela 9).
Fonte: OneNote de Referência Técnica (BASE.one / INFO DE PROJETO IMPORTANTE).

Gera e gerencia consultas rápidas via SQLite3 e JSON, além de exportar dados para LISPs e CLI.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
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
# PERSISTÊNCIA: SQLITE3 E JSON
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tabelas_referencia.sqlite3"
JSON_PATH = BASE_DIR / "tabelas_referencia.json"


def exportar_para_json(caminho: Path = JSON_PATH) -> Path:
    """Exporta as tabelas para formato JSON estruturado."""
    payload = {
        "_metadados": {
            "titulo": "Tabelas Técnicas de Referência - Baixa Tensão (BT)",
            "fonte": "OneNote BASE.one - INFO DE PROJETO IMPORTANTE",
            "tabelas": ["Tabela 7 - Estruturas de Baixa Tensão", "Tabela 9 - Condutores de Baixa Tensão"],
            "versao": "1.0.0",
        },
        "condutores_bt": [asdict(c) for c in CONDUTORES_BT_DADOS],
        "estruturas_bt": [asdict(e) for e in ESTRUTURAS_BT_DADOS],
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

    conn.commit()
    return conn


# ==============================================================================
# API DE CONSULTA EM MEMÓRIA / SQLITE
# ==============================================================================
def buscar_condutor(termo: str) -> Optional[CondutorBT]:
    """Busca condutor por nome exato ou aproximação (ex: '150', '3x150+1x80', '95')."""
    termo_limpo = termo.strip().lower().replace(".", ",")
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
