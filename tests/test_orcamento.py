"""
Testes Unitários para o Módulo de Orçamento e Levantamento de Materiais (orcamento/).
Valida classificação analítica de postes, condutores, equipamentos, estruturas e geração Excel.
"""

import os
import openpyxl
import pytest

from orcamento_core import (
    carregar_catalogo,
    classificar_cabo,
    classificar_equipamento_ou_estrutura,
    classificar_poste,
    processar_dados_orcamento
)
from orcamento_excel import exportar_planilha_orcamento


def test_catalogo_padrao_existente():
    catalogo = carregar_catalogo()
    assert isinstance(catalogo, dict)
    assert len(catalogo) >= 15
    assert "PST_CONC_12_300" in catalogo
    assert "CABO_BT_3X70_50" in catalogo
    assert "TRAFO_45_KVA" in catalogo


def test_classificacao_postes():
    # 1. Padrão barra: XX/YYY
    chave, alt, esf = classificar_poste("POSTE_12/300_NOVO")
    assert chave == "PST_CONC_12_300"
    assert alt == 12
    assert esf == 300

    # 2. Padrão hífen: DT-11-600
    chave, alt, esf = classificar_poste("DT-11-600")
    assert chave == "PST_CONC_11_600"
    assert alt == 11
    assert esf == 600

    # 3. Padrão por extenso: 10M 300DAN
    chave, alt, esf = classificar_poste("POSTE CONCRETO 10M 300DAN")
    assert chave == "PST_CONC_10_300"
    assert alt == 10
    assert esf == 300

    # 4. Caso não identificado: retorna genérico
    chave, alt, esf = classificar_poste("POSTE_DESCONHECIDO")
    assert chave == "PST_CONC_GENERICO"
    assert alt == 0
    assert esf == 0


def test_classificacao_cabos():
    # BT Multiplexado
    chave, tensao, _ = classificar_cabo("BT_CABO_3X70+50")
    assert chave == "CABO_BT_3X70_50"
    assert tensao == "BT"

    chave, tensao, _ = classificar_cabo("REDE_BT_1X35")
    assert chave == "CABO_BT_1X35_35"
    assert tensao == "BT"

    # MT Nu CAA
    chave, tensao, _ = classificar_cabo("MT_3X1/0_CAA_RAVEN")
    assert chave == "CABO_MT_3X1_0_CAA"
    assert tensao == "MT"

    # MT Compacto
    chave, tensao, _ = classificar_cabo("REDE_COMPACTA_50MM2")
    assert chave == "CABO_MT_COMPACTO_50"
    assert tensao == "MT"


def test_classificacao_equipamentos_e_estruturas():
    # Transformadores
    res = classificar_equipamento_ou_estrutura("TRAFO 45KVA 13.8KV")
    assert res is not None
    assert res[0] == "TRAFO_45_KVA"
    assert res[1] == "Equipamentos"

    # Chaves e Proteção
    res = classificar_equipamento_ou_estrutura("CHAVE FUSIVEL MATHEUS 15KV")
    assert res is not None
    assert res[0] == "CHAVE_FUSIVEL_15KV"

    # Estruturas de MT e BT
    res = classificar_equipamento_ou_estrutura("ESTRUTURA N1 TANGENCIA")
    assert res is not None
    assert res[0] == "ESTRUTURA_N1"

    res = classificar_equipamento_ou_estrutura("ARMACAO SECUNDARIA B1")
    assert res is not None
    assert res[0] == "ESTRUTURA_B1"

    # Estai e Aterramento
    res = classificar_equipamento_ou_estrutura("ESTAI DE ANCORA COMPLETO")
    assert res is not None
    assert res[0] == "ESTAI_ANCORA"


def test_processamento_dados_orcamento_completo():
    dados_cad = {
        "postes": [
            {"id": "P1", "bloco": "POSTE_12_300", "attrs": "NUM:1", "x": 600000.0, "y": 7500000.0, "layer": "POSTES"},
            {"id": "P2", "bloco": "POSTE_12_600", "attrs": "NUM:2", "x": 600040.0, "y": 7500000.0, "layer": "POSTES"}
        ],
        "cabos": [
            {"id": "C1", "layer": "BT_CABO_3X70+50", "comprimento": 40.0, "vaos": 1},
            {"id": "C2", "layer": "MT_CABO_3X1/0_CAA", "comprimento": 100.0, "vaos": 2}
        ],
        "estruturas": [
            {"id": "E1", "tipo": "N1", "bloco": "ESTR_N1"}
        ],
        "equipamentos": [
            {"id": "EQ1", "tipo": "TRAFO 45 KVA", "bloco": "TRAFO"}
        ]
    }

    # Margem padrão de 5%
    resultado = processar_dados_orcamento(dados_cad, margem_cabos_pct=5.0)

    assert resultado["qtd_postes"] == 2
    assert resultado["qtd_trechos_cabo"] == 2
    # Comprimento orçado = 40 * 1.05 (42.0) + 100 * 1.05 (105.0) = 147.0
    assert resultado["extensao_total_m"] == 147.0
    assert resultado["total_geral"] > 0.0

    chaves_geradas = [m.chave for m in resultado["materiais"]]
    assert "PST_CONC_12_300" in chaves_geradas
    assert "PST_CONC_12_600" in chaves_geradas
    assert "CABO_BT_3X70_50" in chaves_geradas
    assert "CABO_MT_3X1_0_CAA" in chaves_geradas
    assert "ESTRUTURA_N1" in chaves_geradas
    assert "TRAFO_45_KVA" in chaves_geradas


def test_exportacao_planilha_orcamento_excel(tmp_path):
    dados_cad = {
        "postes": [
            {"id": "P1", "bloco": "POSTE_12_300", "attrs": "NUM:1", "x": 600000.0, "y": 7500000.0, "layer": "POSTES"}
        ],
        "cabos": [
            {"id": "C1", "layer": "BT_CABO_3X70+50", "comprimento": 50.0, "vaos": 1}
        ]
    }
    processados = processar_dados_orcamento(dados_cad, margem_cabos_pct=5.0)
    arquivo_excel = os.path.join(tmp_path, "ORCAMENTO_TESTE.xlsx")

    caminho_gerado = exportar_planilha_orcamento(
        dados_processados=processados,
        caminho_saida=arquivo_excel,
        num_projeto="OS-2026-TESTE",
        municipio="NITEROI - RJ",
        projetista="ENG. TESTE"
    )

    assert os.path.exists(caminho_gerado)

    # Abre e valida as abas e estrutura
    wb = openpyxl.load_workbook(caminho_gerado)
    abas_esperadas = ["RESUMO ORÇAMENTO", "DETALHAMENTO POSTES", "DETALHAMENTO CABOS", "BANCO DE PREÇOS"]
    for aba in abas_esperadas:
        assert aba in wb.sheetnames

    ws_resumo = wb["RESUMO ORÇAMENTO"]
    assert "LEVANTAMENTO QUANTITATIVO E ORÇAMENTO DE MATERIAIS" in str(ws_resumo["A1"].value)
    assert ws_resumo["B2"].value == "OS-2026-TESTE"


def test_carregar_dados_json(tmp_path):
    import json
    from orcamento_manager import carregar_dados_json

    # Teste com arquivo inexistente
    dados_vazio = carregar_dados_json("caminho_inexistente.json")
    assert dados_vazio["postes"] == []

    # Teste com arquivo existente
    arq = tmp_path / "dados.json"
    conteudo = {"postes": [{"id": "P1"}], "cabos": [], "estruturas": [], "equipamentos": []}
    arq.write_text(json.dumps(conteudo), encoding="utf-8")

    dados = carregar_dados_json(str(arq))
    assert len(dados["postes"]) == 1
    assert dados["postes"][0]["id"] == "P1"

    # Teste com JSON corrompido / inválido
    arq_corrompido = tmp_path / "corrompido.json"
    arq_corrompido.write_text("{json invalido:", encoding="utf-8")
    dados_inv = carregar_dados_json(str(arq_corrompido))
    assert dados_inv == {"postes": [], "cabos": [], "estruturas": [], "equipamentos": []}



def test_orcamento_manager_cli(tmp_path, monkeypatch):
    import json
    import sys
    from orcamento_manager import main

    arq_json = tmp_path / "dados_cli.json"
    arq_xlsx = tmp_path / "saida_cli.xlsx"

    conteudo = {
        "postes": [{"id": "P1", "bloco": "12/300"}],
        "cabos": [{"id": "C1", "layer": "BT_CABO", "comprimento": 30.0}],
        "estruturas": [],
        "equipamentos": []
    }
    arq_json.write_text(json.dumps(conteudo), encoding="utf-8")

    test_args = [
        "orcamento_manager.py",
        "--json", str(arq_json),
        "--saida", str(arq_xlsx),
        "--no-gui",
        "--projeto", "CLI-TESTE-2026"
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    main()

    assert os.path.exists(str(arq_xlsx))

