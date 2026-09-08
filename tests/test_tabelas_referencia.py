import json
from pathlib import Path
import sqlite3
import pytest

from dados_tecnicos.tabelas_referencia import (
    CONDUTORES_BT_DADOS,
    ESTRUTURAS_BT_DADOS,
    buscar_condutor,
    obter_tracao_condutor,
    buscar_estrutura,
    consultar_resistencia_poste,
    exportar_para_json,
    inicializar_sqlite,
)


def test_tabela_9_condutores_valores_exatos():
    """Valida se os dados de condutores batem exatamente com a Tabela 9 oficial."""
    c150 = buscar_condutor("3x150+1x80")
    assert c150 is not None
    assert c150.corrente_a == 326.0
    assert c150.tracao_dan == 554.0
    assert c150.diametro_total_mm == 51.0
    assert c150.massa_total_kg_km == 1878.0
    assert c150.resistencia_r_ohm_km == 0.2775
    assert c150.reatancia_x_ohm_km == 0.0867

    c95 = buscar_condutor("95")
    assert c95 is not None
    assert c95.tracao_dan == 393.0
    assert c95.corrente_a == 244.0

    c50 = buscar_condutor("3x50")
    assert c50 is not None
    assert c50.tracao_dan == 260.0
    assert c50.diametro_total_mm == 37.0

    c35 = buscar_condutor("35")
    assert c35 is not None
    assert c35.tracao_dan == 235.0
    assert c35.massa_total_kg_km == 700.0


def test_obter_tracao_condutor():
    """Testa recuperação direta do float de tração mecânica."""
    assert obter_tracao_condutor("3x150+1x80") == 554.0
    assert obter_tracao_condutor("95") == 393.0
    assert obter_tracao_condutor("inexistente") == 0.0


def test_tabela_7_estruturas_valores_exatos():
    """Valida estruturas da Tabela 7 oficial."""
    # Tangente SI1
    si1 = buscar_estrutura("SI1")
    assert len(si1) == 5
    assert all(e.resistencia_min_poste_dan == 300 for e in si1)
    assert si1[0].angulo_utilizacao == "0° a 30°"
    assert "suspensão" in si1[0].fixacao_rede

    # Tangente Afastamento SI1.AF (300 daN para <=50mm², 600 daN para >=95mm²)
    si1_af = buscar_estrutura("SI1.AF")
    assert len(si1_af) == 5
    res_map = {e.cabo_fase: e.resistencia_min_poste_dan for e in si1_af}
    assert res_map["1x35 ou 2x25"] == 300
    assert res_map["3X35"] == 300
    assert res_map["3X50"] == 300
    assert res_map["3X95"] == 600
    assert res_map["3X150"] == 600

    # Ancoragem SI3 (Ângulo 30° a 90°)
    si3 = buscar_estrutura("SI3")
    assert si3[0].angulo_utilizacao == "30° a 90°"

    # Ancoragem Dupla Angular SI3.SI3 (Ângulo 60° a 90°)
    si3_si3 = buscar_estrutura("SI3.SI3")
    assert si3_si3[0].angulo_utilizacao == "60° a 90°"


def test_consultar_resistencia_poste():
    """Testa consulta rápida da resistência de poste exigida."""
    assert consultar_resistencia_poste("SI1", "3X150") == 300
    assert consultar_resistencia_poste("SI1.AF", "3X50") == 300
    assert consultar_resistencia_poste("SI1.AF", "3X95") == 600
    assert consultar_resistencia_poste("DERIV_VAO", "3X35") is None


def test_exportacao_json(tmp_path: Path):
    """Testa exportação para JSON e integridade das chaves."""
    json_file = tmp_path / "teste_tabelas.json"
    exportar_para_json(json_file)
    assert json_file.exists()

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "_metadados" in data
    assert "condutores_bt" in data
    assert "estruturas_bt" in data
    assert len(data["condutores_bt"]) == 4
    assert len(data["estruturas_bt"]) == len(ESTRUTURAS_BT_DADOS)


def test_inicializar_sqlite(tmp_path: Path):
    """Testa criação e consulta no banco SQLite3."""
    db_file = tmp_path / "teste.sqlite3"
    conn = inicializar_sqlite(db_file)
    cursor = conn.cursor()

    # Checa tabela de condutores
    cursor.execute("SELECT condutor, tracao_dan FROM condutores_bt WHERE condutor = '3x150+1x80';")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "3x150+1x80"
    assert row[1] == 554.0

    # Checa tabela de estruturas
    cursor.execute("SELECT codigo, resistencia_min_poste_dan FROM estruturas_bt WHERE codigo = 'SI1.AF' AND cabo_fase = '3X95';")
    row_est = cursor.fetchone()
    assert row_est is not None
    assert row_est[0] == "SI1.AF"
    assert row_est[1] == 600

    conn.close()
