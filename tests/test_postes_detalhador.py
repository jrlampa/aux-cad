import pytest
from postes_detalhador import extrair_altura_esforco, formatar_descricao_postes, analisar_postes_projeto


def test_extrair_altura_esforco():
    assert extrair_altura_esforco("12/300") == (12, 300)
    assert extrair_altura_esforco("12-600") == (12, 600)
    assert extrair_altura_esforco("Bloco_10/300_1") == (10, 300)
    assert extrair_altura_esforco("DT-11_600") == (11, 600)
    assert extrair_altura_esforco("CIRC_12/1000") == (12, 1000)
    assert extrair_altura_esforco("POSTE 14M 1000DAN") == (14, 1000)
    assert extrair_altura_esforco("TEXTO_QUALQUER") == (0, 0)
    assert extrair_altura_esforco("") == (0, 0)


def test_formatar_descricao_postes():
    # Caso 1 tipo
    d1 = {(12, 300): 4}
    assert formatar_descricao_postes(d1) == "04 de 12 metros de altura e 300 daN de esforço"

    # Caso 2 tipos
    d2 = {(12, 300): 4, (10, 300): 2}
    assert formatar_descricao_postes(d2) == "04 de 12 metros de altura e 300 daN de esforço e 02 de 10 metros de altura e 300 daN de esforço"

    # Caso 3 tipos (como no memorial real do usuário)
    d3 = {(12, 300): 4, (12, 600): 3, (10, 300): 3}
    res3 = formatar_descricao_postes(d3)
    assert "04 de 12 metros de altura e 300 daN de esforço" in res3
    assert "03 de 12 metros de altura e 600 daN de esforço" in res3
    assert "03 de 10 metros de altura e 300 daN de esforço" in res3

    # Vazio com fallback
    assert formatar_descricao_postes({}, total_generico=8) == "08 postes de concreto armado de distribuição"
    assert formatar_descricao_postes({}, total_generico=0) == "Nenhum poste cadastrado"


def test_analisar_postes_projeto():
    pontos = [
        {"id": "P1", "block_name": "12/300"},
        {"id": "P2", "block_name": "12/300"},
        {"id": "P3", "block_name": "12/300"},
        {"id": "P4", "block_name": "12/300"},
        {"id": "P5", "block_name": "12/600"},
        {"id": "P6", "block_name": "12/600"},
        {"id": "P7", "block_name": "12/600"},
        {"id": "P8", "block_name": "10/300"},
        {"id": "P9", "block_name": "10/300"},
        {"id": "P10", "block_name": "10/300"},
    ]
    res = analisar_postes_projeto(pontos)
    assert res["total_postes"] == 10
    assert res["total_identificados"] == 10
    assert res["nao_identificados"] == 0
    assert (12, 300) in res["contagem_detalhada"]
    assert res["contagem_detalhada"][(12, 300)] == 4
    assert res["contagem_detalhada"][(12, 600)] == 3
    assert res["contagem_detalhada"][(10, 300)] == 3
    assert "04 de 12 metros de altura e 300 daN de esforço" in res["texto_formatado"]
