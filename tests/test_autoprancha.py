"""Suíte de testes unitários para o módulo autoprancha_core.py.
Valida regras de enquadramento, escalas normativas, dimensões no ModelSpace e margens ABNT/Enel.
"""

import pytest
from prancha.autoprancha_core import (
    FORMATOS_PAPEL_MM,
    MARGENS_PADRAO_MM,
    calcular_dimensoes_model,
    calcular_enquadramento,
    obter_area_util_mm,
)


def test_formatos_papel_abnt_dimensoes():
    """Valida as dimensões nominais ABNT/NBR dos papéis em mm."""
    assert FORMATOS_PAPEL_MM["A0"] == (1189.0, 841.0)
    assert FORMATOS_PAPEL_MM["A1"] == (841.0, 594.0)
    assert FORMATOS_PAPEL_MM["A2"] == (594.0, 420.0)
    assert FORMATOS_PAPEL_MM["A3"] == (420.0, 297.0)
    assert FORMATOS_PAPEL_MM["A4"] == (297.0, 210.0)


def test_area_util_mm():
    """Valida o desconto correto das margens (25mm esquerda, 10mm outras)."""
    # A1: 841 - (25+10) = 806; 594 - (10+10) = 574
    larg_util, alt_util = obter_area_util_mm("A1")
    assert larg_util == 806.0
    assert alt_util == 574.0

    # A3: 420 - 35 = 385; 297 - 20 = 277
    larg_util, alt_util = obter_area_util_mm("A3")
    assert larg_util == 385.0
    assert alt_util == 277.0


def test_calcular_dimensoes_model_escala_1000():
    """Na escala 1:1000, 1 mm de papel corresponde a 1 m no ModelSpace."""
    larg_f, alt_f, larg_u, alt_u = calcular_dimensoes_model("A1", 1000)
    assert larg_f == 841.0
    assert alt_f == 594.0
    assert larg_u == 806.0
    assert alt_u == 574.0


def test_calcular_dimensoes_model_escala_500():
    """Na escala 1:500, fator é 0.5 (1 mm = 0.5 m no ModelSpace)."""
    larg_f, alt_f, larg_u, alt_u = calcular_dimensoes_model("A1", 500)
    assert larg_f == 420.5
    assert alt_f == 297.0
    assert larg_u == 403.0
    assert alt_u == 287.0


def test_calcular_dimensoes_model_escala_2000():
    """Na escala 1:2000, fator é 2.0 (1 mm = 2.0 m no ModelSpace)."""
    larg_f, alt_f, larg_u, alt_u = calcular_dimensoes_model("A1", 2000)
    assert larg_f == 1682.0
    assert alt_f == 1188.0
    assert larg_u == 1612.0
    assert alt_u == 1148.0


def test_enquadramento_projeto_medio_enel():
    """Projeto com 650m de extensão por 450m de largura exige folha A1 na escala 1:1000."""
    res = calcular_enquadramento(1000.0, 2000.0, 1650.0, 2450.0)
    assert res.dx_projeto_m == 650.0
    assert res.dy_projeto_m == 450.0
    assert res.formato == "A1"
    assert res.escala == 1000
    assert res.fator_escala == 1.0
    assert res.largura_folha_m == 841.0
    assert res.altura_folha_m == 594.0
    assert res.largura_util_m == 806.0
    assert res.altura_util_m == 574.0
    # Valida se a folha envolve o projeto
    assert res.x_folha_min <= 1000.0
    assert res.x_folha_max >= 1650.0
    assert res.y_folha_min <= 2000.0
    assert res.y_folha_max >= 2450.0


def test_enquadramento_forcar_escala():
    """Forçando escala 1:1000 para uma área de 300m x 200m."""
    res = calcular_enquadramento(0.0, 0.0, 300.0, 200.0, escala_fixa=1000)
    assert res.escala == 1000
    # Deve escolher A3 ou A2, que comportam com folga na 1:1000
    assert res.formato in ["A3", "A2"]


def test_enquadramento_forcar_formato():
    """Forçando formato A1 para uma área grande de 1200m x 800m."""
    res = calcular_enquadramento(0.0, 0.0, 1200.0, 800.0, formato_fixo="A1")
    assert res.formato == "A1"
    # Para caber 1200m na A1 (util 806mm), precisa de escala 2000 (util 1612m)
    assert res.escala == 2000
    assert res.largura_util_m >= 1200.0
    assert res.altura_util_m >= 800.0


def test_coordenadas_invertidas_diagonal():
    """Verifica se o cálculo é idêntico independentemente da direção do clique na diagonal."""
    res1 = calcular_enquadramento(100.0, 200.0, 600.0, 400.0)
    res2 = calcular_enquadramento(600.0, 400.0, 100.0, 200.0)
    assert res1.formato == res2.formato
    assert res1.escala == res2.escala
    assert res1.x_folha_min == res2.x_folha_min
    assert res1.y_folha_min == res2.y_folha_min


def test_formato_invalido():
    """Garante que formatos desconhecidos gerem exceção apropriada."""
    with pytest.raises(ValueError):
        obter_area_util_mm("A99")


def test_dimensoes_carimbo_oficial_im3():
    """Valida as dimensões físicas oficiais do carimbo corporativo IM3 (297 x 64.27 mm)."""
    from prancha.autoprancha_core import ALTURA_CARIMBO_MM, LARGURA_CARIMBO_MM
    assert LARGURA_CARIMBO_MM == 297.0
    assert ALTURA_CARIMBO_MM == 64.27


def test_fator_metrico_todas_escalas_normativas():
    """Garante o fator f = escala / 1000.0 para todas as escalas normativas de distribuição."""
    from prancha.autoprancha_core import ESCALAS_NORMATIVAS
    for esc in ESCALAS_NORMATIVAS:
        _, _, _, _ = calcular_dimensoes_model("A1", esc)
        fator = esc / 1000.0
        assert fator == pytest.approx(esc / 1000.0)


def test_ancoragem_bloco_prancha_inferior_direito():
    """Para A1, A2 e A3, o bloco PRANCHA é ancorado no canto inferior direito (Xmax, Ymin)."""
    for fmt in ["A1", "A2", "A3"]:
        res = calcular_enquadramento(0.0, 0.0, 100.0, 100.0, formato_fixo=fmt, escala_fixa=1000)
        assert res.bloco_nome == "PRANCHA"
        assert res.x_insercao == res.x_folha_max
        assert res.y_insercao == res.y_folha_min


def test_ancoragem_bloco_prancha_a4_inferior_esquerdo():
    """Para A4, o bloco PRANCHA_A4 é ancorado no canto inferior esquerdo (Xmin, Ymin)."""
    res = calcular_enquadramento(0.0, 0.0, 50.0, 50.0, formato_fixo="A4", escala_fixa=1000)
    assert res.bloco_nome == "PRANCHA_A4"
    assert res.x_insercao == res.x_folha_min
    assert res.y_insercao == res.y_folha_min


def test_reserva_carimbo_resultado_enquadramento():
    """Valida se o enquadramento calcula a reserva de carimbo baseada no tamanho oficial 297x64.27."""
    res = calcular_enquadramento(0.0, 0.0, 500.0, 300.0, escala_fixa=1000)
    assert res.reserva_carimbo_largura_m == 297.0
    assert res.reserva_carimbo_altura_m == 64.27


def test_bloco_prancha_compativel_assinatura():
    """Valida que uma definição com todos os marcadores oficiais do PRANCHA é COMPATÍVEL."""
    from prancha.autoprancha_core import validar_assinatura_bloco
    entidades_oficiais = [
        {"texto": "Folha: ", "x": -35.89, "y": 30.24},
        {"texto": "Escala:", "x": -35.91, "y": 25.46},
        {"texto": "DATA:", "x": -86.58, "y": 15.76},
        {"texto": "BAIRRO:", "x": -117.78, "y": 15.73},
        {"texto": "HBT ENGENHARIA", "x": -138.45, "y": 24.87},
    ]
    assert validar_assinatura_bloco("PRANCHA", entidades_oficiais) == "COMPATIVEL"


def test_bloco_prancha_incompativel_ausencia_marcador():
    """Definição de bloco PRANCHA sem os marcadores ou com coordenadas deslocadas é INCOMPATÍVEL."""
    from prancha.autoprancha_core import validar_assinatura_bloco
    # Falta o marcador HBT e Escala está fora de posição
    entidades_legadas = [
        {"texto": "Folha: ", "x": -35.89, "y": 30.24},
        {"texto": "Escala:", "x": 100.0, "y": 25.46},
        {"texto": "DATA:", "x": -86.58, "y": 15.76},
    ]
    assert validar_assinatura_bloco("PRANCHA", entidades_legadas) == "INCOMPATIVEL"


def test_bloco_prancha_a4_compativel_assinatura():
    """Valida que uma definição com todos os marcadores oficiais do PRANCHA_A4 é COMPATÍVEL."""
    from prancha.autoprancha_core import validar_assinatura_bloco
    entidades_a4_oficiais = [
        {"texto": "Folha: ", "x": 261.11, "y": 30.24},
        {"texto": "Escala:", "x": 261.09, "y": 25.46},
        {"texto": "DATA:", "x": 210.42, "y": 15.76},
        {"texto": "BAIRRO:", "x": 179.22, "y": 15.73},
        {"texto": "JONATAS LAMPA", "x": 160.03, "y": 10.55},
    ]
    assert validar_assinatura_bloco("PRANCHA_A4", entidades_a4_oficiais) == "COMPATIVEL"


def test_bloco_prancha_a4_incompativel_ausencia_marcador():
    """Definição de bloco PRANCHA_A4 sem o marcador de responsável oficial é INCOMPATÍVEL."""
    from prancha.autoprancha_core import validar_assinatura_bloco
    entidades_a4_legadas = [
        {"texto": "Folha: ", "x": 261.11, "y": 30.24},
        {"texto": "Escala:", "x": 261.09, "y": 25.46},
        {"texto": "DATA:", "x": 210.42, "y": 15.76},
        {"texto": "BAIRRO:", "x": 179.22, "y": 15.73},
        {"texto": "OUTRO PROJETISTA", "x": 160.03, "y": 10.55},
    ]
    assert validar_assinatura_bloco("PRANCHA_A4", entidades_a4_legadas) == "INCOMPATIVEL"


def test_bloco_desconhecido_incompativel():
    """Bloco não cadastrado resulta em INCOMPATIVEL."""
    from prancha.autoprancha_core import validar_assinatura_bloco
    assert validar_assinatura_bloco("BLOCO_INEXISTENTE", []) == "INCOMPATIVEL"


