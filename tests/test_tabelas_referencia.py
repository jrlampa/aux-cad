import json
from pathlib import Path
import sqlite3
import pytest

from dados_tecnicos.tabelas_referencia import (
    CONDUTORES_BT_DADOS,
    ESTRUTURAS_BT_DADOS,
    CABOS_MT_DADOS,
    buscar_condutor,
    obter_tracao_condutor,
    buscar_estrutura,
    consultar_resistencia_poste,
    buscar_tracao_mt,
    calcular_esforco_linha,
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

    # Checa tabela de esforços MT
    cursor.execute("SELECT tipo_cabo, fase_3_dan FROM cabos_mt_esforcos WHERE tipo_cabo = '1/0 CAA' AND vao_m = 40;")
    row_mt = cursor.fetchone()
    assert row_mt is not None
    assert row_mt[0] == "1/0 CAA"
    assert row_mt[1] == 480.0

    conn.close()


def test_buscar_tracao_mt():
    """Valida consultas de esforços nominais em daN para cabos de Média Tensão (MT)."""
    # 1/0 CAA em vão tabelado de 40m e 150m
    assert buscar_tracao_mt("1/0 CAA", vao_m=40, condutores=3) == 480.0
    assert buscar_tracao_mt("1/0 CAA", vao_m=150, condutores=3) == 1200.0
    assert buscar_tracao_mt("1/0 CAA", vao_m=40, condutores=1) == 160.0
    assert buscar_tracao_mt("1/0 CAA", vao_m=40, condutores="neutro") == 128.0

    # 4/0 CAA
    assert buscar_tracao_mt("4/0 CAA", vao_m=40, condutores=3) == 960.0
    assert buscar_tracao_mt("4/0 CAA", vao_m=20, condutores=3) == 540.0

    # 336,4 CAA
    assert buscar_tracao_mt("336,4 CAA", vao_m=40, condutores=3) == 1767.0

    # 185 XLPE
    assert buscar_tracao_mt("185 XLPE", vao_m=40, condutores=3) == 1008.0

    # Interpolação linear contínua para vão intermediário:
    # 1/0 CAA em vão de 35m: entre 30m (420 daN) e 40m (480 daN) -> 450.0 daN
    assert buscar_tracao_mt("1/0 CAA", vao_m=35, condutores=3) == 450.0

    # Regra de 3 para vão curto (< 20m):
    # 1/0 CAA em vão de 10m: base 20m é 375 daN -> (375 * 10 / 20) = 187.5 daN
    assert buscar_tracao_mt("1/0 CAA", vao_m=10, condutores=3) == 187.5

    # Extrapolação linear para vão longo (> 200m):
    # 1/0 CAA em 220m: último intervalo 150m-200m (1200 -> 1395, taxa = 3.9 daN/m) -> 1395 + 3.9 * 20 = 1473.0 daN
    assert buscar_tracao_mt("1/0 CAA", vao_m=220, condutores=3) == 1473.0

    # Cabo inexistente
    assert buscar_tracao_mt("CABO_FANTASMA", vao_m=40) == 0.0


def test_calcular_esforco_linha_cenarios():
    """Valida a resolução integrada de esforços por linha: manual, BT, MT interpolado e MT + BT colinear."""
    # 1. Entrada manual pura
    res_man1 = calcular_esforco_linha("350")
    assert res_man1["total_dan"] == 350.0
    assert res_man1["modo"] == "manual"

    res_man2 = calcular_esforco_linha("150d")
    assert res_man2["total_dan"] == 150.0
    assert res_man2["modo"] == "manual"

    res_man3 = calcular_esforco_linha("=400")
    assert res_man3["total_dan"] == 400.0

    # 2. Cabo de BT isolado
    res_bt = calcular_esforco_linha("150")
    assert res_bt["total_dan"] == 554.0
    assert res_bt["bt_dan"] == 554.0
    assert res_bt["modo"] == "bt"

    res_bt_pr = calcular_esforco_linha("PR95")
    assert res_bt_pr["total_dan"] == 393.0
    assert res_bt_pr["modo"] == "bt"

    # 3. Cabo de MT isolado com vão interpolado (35m) e tabelado (150m)
    res_mt_35 = calcular_esforco_linha("1/0 CAA", vao_m=35.0)
    assert res_mt_35["total_dan"] == 450.0
    assert res_mt_35["mt_dan"] == 450.0
    assert res_mt_35["modo"] == "mt"

    res_mt_150 = calcular_esforco_linha("1/0 CAA", vao_m=150.0)
    assert res_mt_150["total_dan"] == 1200.0
    assert res_mt_150["mt_dan"] == 1200.0

    # 4. Combinação MT + BT colineares (mesma linha física no DWG)
    # 1/0 CAA (vão 35m = 450 daN) + PR150 (554 daN) -> soma = 1004 daN
    res_paralelo = calcular_esforco_linha("1/0 + 150", vao_m=35.0)
    assert res_paralelo["total_dan"] == 1004.0
    assert res_paralelo["mt_dan"] == 450.0
    assert res_paralelo["bt_dan"] == 554.0
    assert res_paralelo["modo"] == "combinado"
    assert "SOMA = 1004 daN" in res_paralelo["descricao"]

    # 4/0 CAA (vão 40m = 960 daN) + PR95 (393 daN) -> soma = 1353 daN
    res_paralelo_2 = calcular_esforco_linha("4/0 CAA + PR95", vao_m=40.0)
    assert res_paralelo_2["total_dan"] == 1353.0
    assert res_paralelo_2["mt_dan"] == 960.0
    assert res_paralelo_2["bt_dan"] == 393.0

    # 5. Validação de match estrito de 4 CAA (não confundir com 336.4 CAA)
    res_4caa = calcular_esforco_linha("4CAA", vao_m=40.0)
    assert res_4caa["total_dan"] == 225.0

    # 6. Prefixos de quantidade de condutores (1#, 2#, 3#, 1N)
    # 1 condutor de 1/0 a 40m = 160 daN (vs 480 daN para 3 fases)
    res_1_10 = calcular_esforco_linha("1#1/0", vao_m=40.0)
    assert res_1_10["total_dan"] == 160.0

    # 1 condutor neutro de 1/0 a 40m = 128 daN
    res_neutro = calcular_esforco_linha("1N1/0", vao_m=40.0)
    assert res_neutro["total_dan"] == 128.0

    # Circuito em paralelo: MT 3#4CAA + 3#4/0 + 1#1/0
    # 4CAA (3 fases = 225 daN) + 4/0 (3 fases = 960 daN) + 1#1/0 (1 fase = 160 daN) = 1345 daN
    res_paralelo_duplo = calcular_esforco_linha("4CAA + 4/0 + 1#1/0", vao_m=40.0)
    assert res_paralelo_duplo["total_dan"] == 1345.0
    assert res_paralelo_duplo["mt_dan"] == 1345.0

    res_paralelo_completo = calcular_esforco_linha("3#4CAA + 3#4/0 + 1#1/0", vao_m=40.0)
    assert res_paralelo_completo["total_dan"] == 1345.0


