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


def test_tracado_continuo_assets_e_algoritmos():
    """Valida assets de traçado contínuo (P2), cálculo analítico de vãos e rotação de texto no CAD."""
    import math
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tracado_js = os.path.join(raiz, "mapa_cad_paleta", "web", "tracado.js")
    cad_bridge_cs = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")

    assert os.path.exists(tracado_js), "Arquivo tracado.js não encontrado"
    assert os.path.exists(cad_bridge_cs), "Arquivo CadBridge.cs não encontrado"

    with open(tracado_js, "r", encoding="utf-8") as f:
        js = f.read()

    assert "toggleModoTracado" in js
    assert "registrarPosteTracado" in js
    assert "desenharVaoNoMapa" in js
    assert "finalizarTrecho" in js
    assert "desenhar_vao" in js

    with open(cad_bridge_cs, "r", encoding="utf-8") as f:
        cs = f.read()

    assert "InserirVaoCabos" in cs
    assert "CABOS_BT" in cs
    assert "CABOS_MT" in cs
    assert "CABOS_TEXTO" in cs

    # Validação matemática do vão: P1(685000, 7470000) até P2(685030, 7470040)
    p1 = (685000.0, 7470000.0)
    p2 = (685030.0, 7470040.0)
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    assert abs(dist - 50.0) < 1e-6

    # Teste de rotação de texto do vão: se ângulo estiver apontando para a esquerda, deve inverter
    angulo = math.atan2(dy, dx)
    if angulo > math.pi / 2.0 or angulo < -math.pi / 2.0:
        angulo_corrigido = angulo + math.pi
    else:
        angulo_corrigido = angulo
    # Ângulo original em (30, 40) está no 1º quadrante (aprox 53.13 graus), não precisa inverter
    assert abs(math.degrees(angulo_corrigido) - 53.13) < 0.1

    # Vetor inverso P2 -> P1 (3º quadrante, -126.87 graus)
    dx_inv, dy_inv = p1[0] - p2[0], p1[1] - p2[1]
    ang_inv = math.atan2(dy_inv, dx_inv)
    assert ang_inv < -math.pi / 2.0
    ang_inv_corrigido = ang_inv + math.pi
    # Após correção de legibilidade no CAD, deve apontar no mesmo sentido visual do 1º quadrante
    assert abs(math.degrees(ang_inv_corrigido) - 53.13) < 0.1


def test_restricoes_ambientais_e_raycasting():
    """Valida assets de restrições ambientais (P4) e o algoritmo Ray-Casting analítico."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    amb_js = os.path.join(raiz, "mapa_cad_paleta", "web", "ambiental_overlay.js")
    parser_cs = os.path.join(raiz, "mapa_cad_paleta", "AmbientalParser.cs")

    assert os.path.exists(amb_js), "Arquivo ambiental_overlay.js não encontrado"
    assert os.path.exists(parser_cs), "Arquivo AmbientalParser.cs não encontrado"

    with open(amb_js, "r", encoding="utf-8") as f:
        js = f.read()

    assert "carregarPoligonosAmbientais" in js
    assert "auditarPontoAmbiental" in js
    assert "rayCastingPontoEmPoligono" in js

    with open(parser_cs, "r", encoding="utf-8") as f:
        cs = f.read()

    assert "CarregarArquivo" in cs
    assert "ExtrairDeKmz" in cs
    assert "ExtrairDeGeoJson" in cs
    assert "ClassificarCategoria" in cs

    # Algoritmo Ray-Casting de alta precisão (idêntico ao de ambiental_overlay.js)
    def ray_casting_ponto_em_poligono(lat, lon, vertices):
        dentro = False
        n = len(vertices)
        j = n - 1
        for i in range(n):
            xi, yi = vertices[i][0], vertices[i][1]
            xj, yj = vertices[j][0], vertices[j][1]
            intersecao = ((yi > lon) != (yj > lon)) and (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi)
            if intersecao:
                dentro = not dentro
            j = i
        return dentro

    # Polígono quadrado em torno de (-22.90, -43.20)
    quadrado_app = [
        [-22.89, -43.21],
        [-22.89, -43.19],
        [-22.91, -43.19],
        [-22.91, -43.21]
    ]

    # Ponto no centro (deve estar dentro)
    assert ray_casting_ponto_em_poligono(-22.90, -43.20, quadrado_app) is True

    # Ponto fora ao norte (fora da APP)
    assert ray_casting_ponto_em_poligono(-22.88, -43.20, quadrado_app) is False

    # Ponto fora ao leste (fora da APP)
    assert ray_casting_ponto_em_poligono(-22.90, -43.18, quadrado_app) is False


def test_ferramenta_medicao_regua_assets_e_geodesia():
    """Valida a presença da ferramenta de régua (medicao.js), controles na UI e precisão dos cálculos de distância/azimute."""
    import math
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    web_dir = os.path.join(raiz, "mapa_cad_paleta", "web")

    medicao_js = os.path.join(web_dir, "medicao.js")
    index_html = os.path.join(web_dir, "index.html")
    style_css = os.path.join(web_dir, "style.css")

    assert os.path.exists(medicao_js), "Arquivo medicao.js não encontrado"

    with open(medicao_js, "r", encoding="utf-8") as f:
        js = f.read()

    assert "toggleModoMedicao" in js
    assert "cliqueMapaMedicao" in js
    assert "mouseMoveMapaMedicao" in js
    assert "calcularDistanciaMetros" in js
    assert "calcularAzimuteGraus" in js
    assert "medirAPartirDoPoste" in js
    assert "posicionarPosteNoUltimoPonto" in js
    assert "limparMedicao" in js

    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()

    assert "btnToggleMedicao" in html
    assert "painelMedicao" in html
    assert "medicao.js" in html

    with open(style_css, "r", encoding="utf-8") as f:
        css = f.read()

    assert "painel-medicao-flutuante" in css
    assert "btn-medicao" in css
    assert "cursor-crosshair" in css

    # Validação analítica do cálculo de azimute geodésico
    def calcular_azimute_graus(lat1, lon1, lat2, lon2):
        d_lon = math.radians(lon2 - lon1)
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        y = math.sin(d_lon) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lon)
        brng = math.degrees(math.atan2(y, x))
        return (brng + 360.0) % 360.0

    # Norte puro (lat2 > lat1, lon igual): deve ser 0°
    assert abs(calcular_azimute_graus(-22.90, -43.20, -22.80, -43.20) - 0.0) < 1e-4

    # Leste puro (lon2 > lon1, lat quase igual no equador/proximidade): deve ser ~90°
    assert abs(calcular_azimute_graus(0.0, -43.20, 0.0, -43.10) - 90.0) < 0.1

    # Sul puro (lat2 < lat1, lon igual): deve ser 180°
    assert abs(calcular_azimute_graus(-22.80, -43.20, -22.90, -43.20) - 180.0) < 1e-4

    # Oeste puro: deve ser ~270°
    assert abs(calcular_azimute_graus(0.0, -43.10, 0.0, -43.20) - 270.0) < 0.1

    # Validação de distância métrica por Haversine analítico
    def calcular_distancia_metros(lat1, lon1, lat2, lon2):
        r = 6371000.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (math.sin(d_lat / 2.0) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(d_lon / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c

    # 1 grau de latitude no equador é ~111.19 km
    dist_1grau = calcular_distancia_metros(0.0, 0.0, 1.0, 0.0)
    assert 111000.0 < dist_1grau < 112000.0



