# -*- coding: utf-8 -*-
"""
Suíte de testes unitários do módulo unifilar (Árvore de Dispositivos e Diagrama Unifilar).
"""

import json
from pathlib import Path
import sqlite3
import pytest

from arvore_parser import (
    DispositivoNo,
    ResultadoProtecao,
    eh_dispositivo_protecao,
    extrair_se_e_alimentador,
    localizar_protecao_a_montante,
    normalizar_texto,
    parse_no_string,
    separar_caminho_em_nos,
)
from arvore_database import ArvoreDatabase
from arvore_client import ArvoreClient
from unifilar_manager import processar_ponto


# =============================================================================
# TESTES DO PARSER ANALÍTICO (arvore_parser.py)
# =============================================================================

def test_extrair_se_e_alimentador():
    assert extrair_se_e_alimentador("RBN02") == ("RBN", "02")
    assert extrair_se_e_alimentador("ABD01") == ("ABD", "01")
    assert extrair_se_e_alimentador("VR04") == ("VR", "04")
    assert extrair_se_e_alimentador("SJR12") == ("SJR", "12")
    assert extrair_se_e_alimentador("SE_CUSTOM") == ("SE_CUSTOM", "SE_CUSTOM")


def test_normalizar_texto():
    assert normalizar_texto("Centro de Distribuic?o") == "Centro de Distribuicao"
    assert normalizar_texto("") == ""
    assert normalizar_texto("  teste  ") == "teste"


def test_parse_no_string_completo():
    no_str = "Chave Fusivel - SG59356 Clientes Grupo A: 2 Clientes Grupo B: 76 - KVA: 150.5"
    no = parse_no_string(no_str)
    assert no.tipo == "Chave Fusivel"
    assert no.codigo == "SG59356"
    assert no.clientes_a == 2
    assert no.clientes_b == 76
    assert no.kva == 150.5


def test_parse_no_string_simples():
    no1 = parse_no_string("Saida do Alimentador - RBN02")
    assert no1.tipo == "Saida do Alimentador"
    assert no1.codigo == "RBN02"

    no2 = parse_no_string("- SG37240")
    assert no2.codigo == "SG37240"

    no3 = parse_no_string("Chave Faca-SG59034")
    assert no3.tipo == "Chave Faca"
    assert no3.codigo == "SG59034"


def test_separar_caminho_em_nos():
    caminho_pipe = "|Saida do Alimentador - RBN02|Chave Faca - SG59034|Chave Fusivel - SG59356"
    nos_pipe = separar_caminho_em_nos(caminho_pipe)
    assert len(nos_pipe) == 3
    assert nos_pipe[0].codigo == "RBN02"
    assert nos_pipe[2].codigo == "SG59356"

    caminho_arrow = "Saida do Alimentador - RBN02 > Chave Faca - SG59034 > Chave Fusivel - SG59356"
    nos_arrow = separar_caminho_em_nos(caminho_arrow)
    assert len(nos_arrow) == 3

    assert separar_caminho_em_nos("") == []


def test_eh_dispositivo_protecao():
    assert eh_dispositivo_protecao("Chave Fusivel") is True
    assert eh_dispositivo_protecao("Chave Fusível") is True
    assert eh_dispositivo_protecao("Religador") is True
    assert eh_dispositivo_protecao("Saida do Alimentador") is True
    assert eh_dispositivo_protecao("Chave Faca") is False
    assert eh_dispositivo_protecao("CTL") is False
    assert eh_dispositivo_protecao("Centro de Distribuicao") is False


def test_localizar_protecao_caso_real_chave_fusivel():
    # Caminho real fornecido pelo usuário nas imagens
    caminho = (
        "Saida do Alimentador - RBN02 > Chave Faca - SG59034 > Chave Faca - SG292230 > "
        "Chave Faca - SG292220 > - SG37240 > Chave Faca - UF03326 > Chave Faca - SG292215 > "
        "Religador - SG59205 > Chave Faca - UF02206 > Chave Faca - SG41133 > - SG35355 > "
        "Chave Faca - SG59320 > Chave Faca - UF07197 > Chave Faca - UF07198 > Chave Faca - UF03709 > "
        "Chave Faca - SG59052 > Chave Faca - SG38819 > Chave Fusivel - SG59356 > Centro de Distribuic?o - SG40995"
    )
    resultado = localizar_protecao_a_montante(
        caminho_str=caminho,
        ponto_alvo="SG40995",
        clientes_a_override=0,
        clientes_b_override=76,
        kva_override=150.0,
    )

    assert resultado.sucesso is True
    assert resultado.ponto_alvo == "SG40995"
    assert resultado.subestacao == "RBN"
    assert resultado.alimentador == "02"
    assert resultado.protecao_tipo == "Chave Fusivel"
    assert resultado.protecao_codigo == "SG59356"
    assert resultado.protecao_rotulo == "Chave Fusivel - SG59356"
    assert resultado.clientes_a == 0
    assert resultado.clientes_b == 76
    assert resultado.kva == 150.0

    linhas = resultado.gerar_linhas_diagrama()
    assert len(linhas) == 6
    assert linhas[0] == "DIAGRAMA  UNIFILAR"
    assert linhas[1] == "SE.: RBN"
    assert linhas[2] == "ALIM.: 02"
    assert linhas[3] == "FONTE DE ALIMENTAÇÃO"
    assert linhas[4] == "DISPOSITIVO DE PROTEÇÃO: Chave Fusivel - SG59356"
    assert linhas[5] == "Clientes Grupo A: 0 Clientes Grupo B: 76 - KVA: 150"


def test_localizar_protecao_caso_real_n760355_resumo():
    """Valida o caso exato informado pelo usuário para N760355 e o alimentador ZSL10."""
    resumo_str = "ZSL10 - Saida do Alimentador - ZSL10 Clientes Grupo A: 13 Clientes Grupo B: 2752 - KVA: 12434"
    client = ArvoreClient()
    res = client.consultar_resumo_manual(resumo_str, "N760355")

    assert res.sucesso is True
    assert res.ponto_alvo == "N760355"
    assert res.subestacao == "ZSL"
    assert res.alimentador == "10"
    assert res.protecao_codigo == "ZSL10"
    assert res.protecao_rotulo == "ZSL10 - Saida do Alimentador - ZSL10"
    assert res.clientes_a == 13
    assert res.clientes_b == 2752
    assert res.kva == 12434.0

    linhas = res.gerar_linhas_diagrama()
    assert "SE.: ZSL" in linhas
    assert "ALIM.: 10" in linhas
    assert "DISPOSITIVO DE PROTEÇÃO: ZSL10 - Saida do Alimentador - ZSL10" in linhas
    assert "Clientes Grupo A: 13 Clientes Grupo B: 2752 - KVA: 12434" in linhas


def test_localizar_protecao_caso_religador():
    # Caminho onde não há chave fusível entre o alvo e o religador
    caminho = (
        "|Saida do Alimentador - ABD01|Chave Faca - CP100|Religador - REL200|Chave Faca - CP300|Trafo - TR400"
    )
    res = localizar_protecao_a_montante(caminho, "TR400")
    assert res.sucesso is True
    assert res.subestacao == "ABD"
    assert res.alimentador == "01"
    assert res.protecao_tipo == "Religador"
    assert res.protecao_codigo == "REL200"


def test_localizar_protecao_caso_saida_alimentador_direta():
    # Caminho onde só existem chaves faca até a saída do alimentador
    caminho = "Saida do Alimentador - VR04 > Chave Faca - CF1 > Chave Faca - CF2 > Ponto - PT99"
    res = localizar_protecao_a_montante(caminho, "PT99")
    assert res.sucesso is True
    assert res.subestacao == "VR"
    assert res.alimentador == "04"
    assert "Saida do Alimentador" in res.protecao_tipo
    assert res.protecao_codigo == "VR04"


def test_localizar_protecao_caminho_invalido():
    res = localizar_protecao_a_montante("", "X1")
    assert res.sucesso is False
    assert "vazio ou inválido" in res.mensagem


# =============================================================================
# TESTES DO BANCO DE DADOS LOCAL (arvore_database.py)
# =============================================================================

def test_arvore_database_operacoes(tmp_path):
    db_file = tmp_path / "test_arvore.sqlite3"
    db = ArvoreDatabase(db_path=db_file)
    assert db.total_registros() == 0

    # Inserção manual no SQLite para teste isolado
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO arvore_dispositivos (
                indice, ingr_alim, cliente_vital, dispositivo,
                arvore, descricao_tipo, total_clientes, total_potencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                16,
                "RBN02",
                0,
                "SG59356",
                "|Saida do Alimentador - RBN02|Chave Fusivel - SG59356",
                "Chave Fusivel",
                80,
                150.0,
            ),
        )
        cursor.execute(
            """
            INSERT INTO arvore_dispositivos (
                indice, ingr_alim, cliente_vital, dispositivo,
                arvore, descricao_tipo, total_clientes, total_potencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                17,
                "RBN02",
                0,
                "SG40995",
                "|Saida do Alimentador - RBN02|Chave Fusivel - SG59356|Centro de Distribuic?o - SG40995",
                "Centro de Distribuic?o",
                80,
                150.0,
            ),
        )
        conn.commit()

    assert db.total_registros() == 2

    # Busca dispositivo
    disp = db.buscar_dispositivo("SG40995")
    assert disp is not None
    assert disp["dispositivo"] == "SG40995"
    assert disp["ingr_alim"] == "RBN02"

    # Consulta proteção
    res = db.consultar_protecao_dispositivo("SG40995")
    assert res.sucesso is True
    assert res.protecao_codigo == "SG59356"
    assert res.subestacao == "RBN"
    assert res.alimentador == "02"
    assert res.clientes_b == 80
    assert res.kva == 150.0

    # Ponto inexistente
    res_nao = db.consultar_protecao_dispositivo("INEXISTENTE99")
    assert res_nao.sucesso is False


# =============================================================================
# TESTES DO CLIENTE E ORQUESTRADOR (arvore_client.py & unifilar_manager.py)
# =============================================================================

def test_arvore_client_extrair_resumo_html():
    client = ArvoreClient()
    html = """
    <html>
    <body>
    <div id="form2">
    <span>Saida do Alimentador - RBN02 &gt; Chave Faca - SG1 &gt; Chave Fusivel - SG2 &gt; Ponto - SG40995</span>
    </div>
    </body>
    </html>
    """
    resumo = client.extrair_resumo_de_html(html, "SG40995")
    assert resumo is not None
    assert "RBN02" in resumo
    assert "SG40995" in resumo


def test_unifilar_manager_processar_ponto(tmp_path):
    out_json = tmp_path / "saida_teste.json"
    resumo_manual = "Saida do Alimentador - RBN02 > Chave Fusivel - SG59356 > Centro - SG40995"

    ret = processar_ponto(
        ponto="SG40995",
        resumo_manual=resumo_manual,
        arquivo_saida=str(out_json),
    )

    assert ret["sucesso"] is True
    assert ret["subestacao"] == "RBN"
    assert ret["alimentador"] == "02"
    assert ret["protecao_codigo"] == "SG59356"
    assert out_json.exists()

    with open(out_json, "r", encoding="utf-8") as f:
        carregado = json.load(f)
    assert carregado["sucesso"] is True
    assert carregado["protecao_codigo"] == "SG59356"


def test_arvore_database_sincronizar_planilha(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["INDICE", "INGR_ALIM", "CLIENTE_VITAL", "DISPOSITIVO", "ARVORE", "DESCRICAO_TIPO", "TOTAL_CLIENTES", "TOTAL_POTENCIA"])
    ws.append([1, "RBN02", 0, "SG59356", "|Saida do Alimentador - RBN02|Chave Fusivel - SG59356", "Chave Fusivel", 80, 150.0])
    ws.append([2, "RBN02", 0, "SG40995", "|Saida do Alimentador - RBN02|Chave Fusivel - SG59356|Centro de Distribuicao - SG40995", "Centro de Distribuicao", 80, 150.0])
    ws.append([3, "RBN02", 0, "", "", "", "", ""])  # Linha vazia
    xlsx_path = tmp_path / "planilha_teste.xlsx"
    wb.save(str(xlsx_path))
    wb.close()

    db_path = tmp_path / "db_sinc.sqlite3"
    db = ArvoreDatabase(db_path=db_path)
    total = db.sincronizar_de_planilha(excel_path=xlsx_path)
    assert total == 2
    assert db.total_registros() == 2

    # Busca por LIKE
    disp_like = db.buscar_dispositivo("40995")
    assert disp_like is not None
    assert disp_like["dispositivo"] == "SG40995"


def test_arvore_client_consultar_e_fallback(monkeypatch, tmp_path):
    db_file = tmp_path / "test_client_db.sqlite3"
    db = ArvoreDatabase(db_path=db_file)
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO arvore_dispositivos (indice, ingr_alim, cliente_vital, dispositivo, arvore, descricao_tipo, total_clientes, total_potencia) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "RBN02", 0, "SG40995", "|Saida do Alimentador - RBN02|Chave Fusivel - SG59356|Centro - SG40995", "Centro", 80, 150.0),
        )
        cursor.execute(
            "INSERT INTO arvore_dispositivos (indice, ingr_alim, cliente_vital, dispositivo, arvore, descricao_tipo, total_clientes, total_potencia) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (2, "RBN02", 0, "SG59356", "|Saida do Alimentador - RBN02|Chave Fusivel - SG59356", "Chave Fusivel", 80, 150.0),
        )
        conn.commit()

    client = ArvoreClient(database=db)

    # 1. Quando web falha/retorna None, deve recorrer ao banco local com sucesso
    monkeypatch.setattr(client, "consultar_web", lambda ponto: None)
    res = client.consultar("SG40995")
    assert res.sucesso is True
    assert res.protecao_codigo == "SG59356"

    # 2. Ponto inexistente em ambos
    res_nao = client.consultar("NAO_EXISTE_XYZ")
    assert res_nao.sucesso is False

    # 3. Quando web retorna com sucesso
    res_mock = ResultadoProtecao(
        sucesso=True,
        ponto_alvo="MOCK123",
        subestacao="VR",
        alimentador="04",
        protecao_tipo="Religador",
        protecao_codigo="REL99",
        protecao_rotulo="Religador - REL99",
        clientes_a=1,
        clientes_b=50,
        kva=200.0,
    )
    monkeypatch.setattr(client, "consultar_web", lambda ponto: res_mock)
    res_web = client.consultar("MOCK123")
    assert res_web.sucesso is True
    assert res_web.subestacao == "VR"


def test_unifilar_manager_cli_main(monkeypatch, tmp_path, capsys):
    import sys
    from unifilar_manager import main

    out_file = tmp_path / "cli_out.json"
    resumo = "Saida do Alimentador - RBN02 > Chave Fusivel - SG59356 > Centro - SG40995"
    test_args = ["unifilar_manager.py", "--ponto", "SG40995", "--resumo", resumo, "--out", str(out_file)]

    monkeypatch.setattr(sys, "argv", test_args)
    main()

    captured = capsys.readouterr()
    assert "SG59356" in captured.out
    assert out_file.exists()


def test_arvore_parser_casos_adicionais():
    # Nó sem traço
    no_simples = parse_no_string("DispositivoIsolado")
    assert no_simples.tipo == "DispositivoIsolado"

    # Caminho com separador '>' simples
    nos = separar_caminho_em_nos("Saida do Alimentador - RBN02>Chave Fusivel - SG59356")
    assert len(nos) == 2

    # Ponto alvo que não existe explicitamente (pega último nó)
    caminho = "Saida do Alimentador - RBN02 > Chave Fusivel - SG59356 > PontoFinal"
    res = localizar_protecao_a_montante(caminho, "ALVO_INEXISTENTE")
    assert res.sucesso is True
    assert res.protecao_codigo == "SG59356"


def test_arvore_client_consultar_web_mock(monkeypatch):
    client = ArvoreClient()

    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

    class MockSession:
        def __init__(self):
            self.auth = None

        def get(self, url, timeout=4):
            html_form = '<input id="__VIEWSTATE" value="VS123" /><input id="__EVENTVALIDATION" value="EV123" />'
            return MockResponse(html_form, 200)

        def post(self, url, data=None, timeout=4):
            html_resp = '<span>Saida do Alimentador - RBN02 > Chave Fusivel - SG59356 > Ponto - SG40995</span>'
            return MockResponse(html_resp, 200)

    import requests
    monkeypatch.setattr(requests, "Session", MockSession)

    res = client.consultar_web("SG40995")
    assert res is not None
    assert res.sucesso is True
    assert res.protecao_codigo == "SG59356"


def test_unifilar_lisp_suporte_bloco_trafo1():
    """Valida que unifilar_cad.lsp configura TRAFO1 como bloco padrão de transformador com suporte a lista e seleção."""
    import os
    lsp_path = os.path.join(os.path.dirname(__file__), "..", "unifilar", "unifilar_cad.lsp")
    assert os.path.exists(lsp_path)

    with open(lsp_path, "r", encoding="utf-8") as f:
        conteudo = f.read()

    assert '*UNIFILAR-BLOCO-TRAFO*' in conteudo
    assert '"TRAFO1"' in conteudo
    assert 'unifilar-obter-bloco-trafo' in conteudo
    assert 'unifilar-listar-blocos-trafo' in conteudo
    assert 'fallback-type "TRAFO1"' in conteudo or 'fallback-type "TRAFO"' in conteudo


