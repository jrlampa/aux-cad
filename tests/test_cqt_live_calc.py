import pytest
from cqt_live_calc import calcular_cqt_topologia, get_fator_condutor, LIMITE_NORMATIVO_QT

def test_fator_condutor():
    assert get_fator_condutor("3x150+70 - Al - F.P 1") == 0.0508
    assert get_fator_condutor("PR3#150(70)AL") == 0.0508
    assert get_fator_condutor("3x50+1x54,6 - Al - F.P 1") == 0.1784
    assert get_fator_condutor("PR3#35(54,6)AL") == 0.2416
    assert get_fator_condutor("Subterrâneo 150 - Al - F.P 1") == 0.0573
    assert get_fator_condutor("3# 25 - Cu - F.P 1") == 0.2200
    assert get_fator_condutor("3x150+1x80 - Al - F.P 0,8") == 0.0566
    assert get_fator_condutor("3x35+35 (nú) - Al - F.P 1") == 0.1793
    assert get_fator_condutor("3x35+35 (nó) - Al - F.P 1") == 0.1793

def test_calcular_cqt_topologia_normal():
    # Simula 2 trechos normais
    trechos = [
        {"letra": "A", "montante": "TRAFO", "comprimento_m": 85.0, "condutor": "PR3#150(70)AL", "mono": 0, "bi": 42, "tri": 1, "ip125": 10},
        {"letra": "B", "montante": "A", "comprimento_m": 110.0, "condutor": "PR3#50(50)AL", "mono": 0, "bi": 6, "tri": 0, "ip125": 0}
    ]
    res = calcular_cqt_topologia(trechos, potencia_trafo=150.0, dmdi=1.30)
    assert res["total_clientes"] == 49
    assert res["carregamento_trafo"] > 0.0
    assert res["pior_qt"] < LIMITE_NORMATIVO_QT  # Deve ser menor que 6.00%
    assert res["tem_alerta_normativo"] is False

def test_calcular_cqt_alerta_normativo():
    # Simula trecho muito longo com cabo fino ultrapassando 6.00%
    trechos = [
        {"letra": "A", "montante": "TRAFO", "comprimento_m": 500.0, "condutor": "PR3#35(54,6)AL", "mono": 0, "bi": 30, "tri": 0, "ip125": 10}
    ]
    res = calcular_cqt_topologia(trechos, potencia_trafo=45.0, dmdi=1.30)
    assert res["pior_qt"] > LIMITE_NORMATIVO_QT
    assert res["tem_alerta_normativo"] is True
    assert "A" in res["trechos_em_alerta"]

def test_calcular_dmdi():
    from cqt_live_calc import calcular_dmdi
    assert calcular_dmdi(0) == 1.30
    assert calcular_dmdi(3) == 2.60
    assert calcular_dmdi(8) == 2.20
    assert calcular_dmdi(14) == 1.90
    assert calcular_dmdi(18) == 1.70
    assert calcular_dmdi(24) == 1.50
    assert calcular_dmdi(28) == 1.40
    assert calcular_dmdi(50) == 1.30

def test_mais_cabos():
    assert get_fator_condutor("") == 0.1784
    assert get_fator_condutor("CABO_120") == 0.0523
    assert get_fator_condutor("CABO_95") == 0.0850
    assert get_fator_condutor("CABO_70") == 0.1175
    assert get_fator_condutor("CABO_16") == 0.8400
    assert get_fator_condutor("DESCONHECIDO") == 0.1784

def test_cqt_lista_vazia():
    res = calcular_cqt_topologia([], potencia_trafo=150.0)
    assert res["total_clientes"] == 0
    assert res["pior_qt"] == 0.0

