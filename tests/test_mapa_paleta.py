"""
Testes Unitários para o Módulo Paleta Cartográfica OSM C# (.NET) e Assets Web.
"""

import json
import os
import subprocess
import pytest
from topografia.kmz_pontos_importer import latlon_to_utm
from mapa_postes.mapa_servidor import utm_to_latlon


def test_binarios_compilados_existem():
    """Valida se as DLLs para AutoCAD 2025/2026 (net8.0) e AutoCAD 2018-2024 (net48) foram geradas."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    dll_net8 = os.path.join(raiz, "mapa_cad_paleta", "bin", "Release", "net8.0-windows", "MapaCadPaleta.dll")
    dll_net48 = os.path.join(raiz, "mapa_cad_paleta", "bin", "Release", "net48", "MapaCadPaleta.dll")
    
    assert os.path.exists(dll_net8), f"DLL .NET 8 não encontrada: {dll_net8}"
    assert os.path.exists(dll_net48), f"DLL .NET Framework 4.8 não encontrada: {dll_net48}"


def test_assets_web_existem():
    """Valida presença dos arquivos HTML/JS/CSS da Paleta OSM."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    web_dir = os.path.join(raiz, "mapa_cad_paleta", "web")
    
    html = os.path.join(web_dir, "index.html")
    css = os.path.join(web_dir, "style.css")
    js = os.path.join(web_dir, "app.js")
    
    assert os.path.exists(html)
    assert os.path.exists(css)
    assert os.path.exists(js)
    
    with open(html, "r", encoding="utf-8") as f:
        conteudo_html = f.read()
        assert "Paleta Cartográfica OSM" in conteudo_html
        assert "btnInserirCad" in conteudo_html
        assert "btnLerCadTop" in conteudo_html

    with open(js, "r", encoding="utf-8") as f:
        conteudo_js = f.read()
        assert "Snyder" in conteudo_js
        assert "inserir_poste" in conteudo_js
        assert "capturar_ponto" in conteudo_js


def test_snyder_geodesia_consistencia():
    """Valida consistência matemática das coordenadas geodésicas Snyder."""
    # Teste de ida e volta para ponto no Rio de Janeiro (Fuso 23S)
    lat_orig = -22.9068
    lon_orig = -43.1729
    
    x, y = latlon_to_utm(lat_orig, lon_orig, zone=23, northern_hemisphere=False)
    assert 680000.0 < x < 700000.0
    assert 7460000.0 < y < 7480000.0
    
    lat_calc, lon_calc = utm_to_latlon(x, y, zone=23, northern_hemisphere=False)
    assert abs(lat_calc - lat_orig) < 1e-4
    assert abs(lon_calc - lon_orig) < 1e-4


def test_sintaxe_lisp_paleta_loader():
    """Valida balanceamento estrito de parênteses e strings no carregador LISP."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    lisp_file = os.path.join(raiz, "mapa_cad_paleta", "mapa_paleta_loader.lsp")
    assert os.path.exists(lisp_file)

    with open(lisp_file, "r", encoding="utf-8", errors="ignore") as f:
        conteudo = f.read()

    # Balanceamento de parênteses ignorando comentários e strings
    parenteses = 0
    em_string = False
    em_comentario = False

    for i, ch in enumerate(conteudo):
        if em_comentario:
            if ch == '\n':
                em_comentario = False
            continue

        if ch == ';' and not em_string:
            em_comentario = True
            continue

        if ch == '"':
            if i > 0 and conteudo[i - 1] == '\\':
                pass
            else:
                em_string = not em_string
            continue

        if not em_string:
            if ch == '(':
                parenteses += 1
            elif ch == ')':
                parenteses -= 1
                assert parenteses >= 0, f"Parêntese fechado sem abertura correspondente no char {i}"

    assert parenteses == 0, f"Parênteses desbalanceados: saldo de {parenteses}"
    assert not em_string, "String não fechada no arquivo LISP"


def test_multi_estruturas_e_trafo_no_frontend():
    """Valida a presença de seletores multi-estruturas MT/BT, tags e seletor de trafo no HTML/JS/CSS."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    web_dir = os.path.join(raiz, "mapa_cad_paleta", "web")

    with open(os.path.join(web_dir, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()

    # Multi-estruturas MT e BT
    assert 'id="selectEstruturaMt"' in html
    assert 'id="btnAddMt"' in html
    assert 'id="tagsEstruturasMt"' in html
    assert 'id="selectEstruturaBt"' in html
    assert 'id="btnAddBt"' in html
    assert 'id="tagsEstruturasBt"' in html
    assert 'chip-quick-add' in html

    # Configuração de Trafo
    assert 'id="chipTrafo"' in html
    assert 'id="painelTrafo"' in html
    assert 'id="selectPotenciaTrafo"' in html
    assert 'id="lblTrafoKva"' in html

    with open(os.path.join(web_dir, "app.js"), "r", encoding="utf-8") as f:
        js = f.read()

    assert "adicionarEstruturaMt" in js
    assert "removerEstruturaMt" in js
    assert "adicionarEstruturaBt" in js
    assert "removerEstruturaBt" in js
    assert "setTrafoAtivo" in js
    assert "potenciaTrafo" in js
    assert "temTrafo" in js
    assert "estruturasMt" in js
    assert "estruturasBt" in js


def test_cad_bridge_codigo_bloco_t_e_anti_sobreposicao():
    """Valida no código C# de CadBridge a inserção do bloco T e offsets anti-sobreposição de PONTO."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cs_file = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")
    assert os.path.exists(cs_file)

    with open(cs_file, "r", encoding="utf-8") as f:
        cs = f.read()

    # Payload
    assert "EstruturasMt" in cs
    assert "EstruturasBt" in cs
    assert "TemTrafo" in cs
    assert "PotenciaTrafo" in cs

    # Inserção do bloco 'T'
    assert 'InserirBlocoTrafo' in cs
    assert 'bt.Has("T")' in cs
    assert 'PossuiTrafo' in cs

    # Anti-sobreposição de PONTO e MText
    # PONTO afastado lateralmente (ex: X - 2.8, Y + 1.8) e MText à direita (ex: X + 1.8)
    assert "payload.X - 2.8" in cs or "payload.X -" in cs
    assert "payload.X + 1.8" in cs or "payload.X +" in cs

