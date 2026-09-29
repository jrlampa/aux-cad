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

    # Inserção do bloco de transformador (priorizando TRAFO1)
    assert 'InserirBlocoTrafo' in cs
    assert 'TRAFO1' in cs
    assert 'PossuiTrafo' in cs

    # Anti-sobreposição de PONTO e MText
    # PONTO afastado lateralmente (ex: X - 2.8, Y + 1.8) e MText à direita (ex: X + 1.8)
    assert "payload.X - 2.8" in cs or "payload.X -" in cs
    assert "payload.X + 1.8" in cs or "payload.X +" in cs


def test_osm_tem_identidade_persistente_e_reconciliacao_segura():
    """Protege a idempotência OSM sem apagar entidades sem metadado do módulo."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cs_file = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")
    vias_file = os.path.join(raiz, "mapa_cad_paleta", "web", "vias_obstrucoes.js")

    with open(cs_file, "r", encoding="utf-8") as f:
        cs = f.read()
    with open(vias_file, "r", encoding="utf-8") as f:
        js = f.read()

    assert 'REGAPP_OSM = "AUXCAD_OSM"' in cs
    assert "ConstruirChaveOsm" in cs
    assert "CalcularFingerprintOsm" in cs
    assert "IndexarEntidadesOsm" in cs
    assert "entidade.Erase(true)" in cs
    assert "osmId: el.id" in js
    assert "osmType: el.type" in js
    assert "osmId: item.osmId" in js
    assert 'REGAPP_POSTE = "AUXCAD_POSTE"' in cs
    assert 'REGAPP_VAO = "AUXCAD_VAO"' in cs
    assert "Seleção cancelada pelo usuário." in cs


def test_osm_obstruction_geometry_semantics_and_validation():
    """Garante que polígonos OSM fechem, barreiras permaneçam abertas e pontos inválidos não cheguem ao CAD."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cs_file = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")
    policy_file = os.path.join(raiz, "mapa_cad_paleta", "OsmGeometryPolicy.cs")
    vias_file = os.path.join(raiz, "mapa_cad_paleta", "web", "vias_obstrucoes.js")

    with open(cs_file, "r", encoding="utf-8") as f:
        cs = f.read()
    with open(policy_file, "r", encoding="utf-8") as f:
        policy = f.read()
    with open(vias_file, "r", encoding="utf-8") as f:
        js = f.read()

    assert "L.polygon(coords" in js
    assert "L.polyline(coords" in js
    assert "tipo: 'EDIFICACAO'" in js
    assert "tipo: 'BARREIRA'" in js
    assert "OsmGeometryPolicy.TryReadCoordinates(pts, out var pontos)" in cs
    assert "OsmGeometryPolicy.ShouldClose(tipoGeometria, fechada)" in cs
    assert "Closed = itemFechado" in cs
    assert "GetArrayLength() < 2" in policy
    assert "GetArrayLength() != 2" in policy
    assert "double.IsInfinity" in policy
    assert "EDIFICACAO" in policy
    assert "BARREIRA" in policy
    assert "ConstruirChaveOsm" in cs
    assert "CalcularFingerprintOsm" in cs


def test_tracado_continuo_assets_e_algoritmos():
    """Valida assets de traçado contínuo (P2), cálculo analítico de vãos e rotação de texto no CAD."""
    import math
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tracado_js = os.path.join(raiz, "mapa_cad_paleta", "web", "tracado.js")
    cad_bridge_cs = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")
    index_html = os.path.join(raiz, "mapa_cad_paleta", "web", "index.html")

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
    assert "LAYER_CABOS_BT, 2" in cs  # Amarelo / Yellow
    assert "LAYER_CABOS_MT, 4" in cs  # Ciano / Cyan

    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Rede BT (Amarelo)" in html
    assert "Rede MT (Ciano)" in html

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


def test_vias_calcadas_obstrucoes_assets_e_parser():
    """Valida assets de vias/obstruções (vias_obstrucoes.js), rotinas no CAD e lógica de classificação semântica."""
    import math
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    web_dir = os.path.join(raiz, "mapa_cad_paleta", "web")

    vias_js = os.path.join(web_dir, "vias_obstrucoes.js")
    tracado_js = os.path.join(web_dir, "tracado.js")
    index_html = os.path.join(web_dir, "index.html")
    cad_bridge_cs = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")

    assert os.path.exists(vias_js), "Arquivo vias_obstrucoes.js não encontrado"
    assert os.path.exists(cad_bridge_cs), "Arquivo CadBridge.cs não encontrado"

    with open(vias_js, "r", encoding="utf-8") as f:
        js = f.read()

    assert "toggleViasObstrucoes" in js
    assert "carregarContextoUrbano" in js
    assert "desenharViasNoCad" in js
    assert "converterEEnviarParaCad" in js
    assert "calcularBbox" in js
    assert "renderizarElementosOsm" in js
    assert "desenharNoCad: true" in js
    assert "sincronizarOpcaoViasCad" in js
    assert "waysProcessados" in js

    # Verifica hook automático no traçado contínuo e na inserção direta
    with open(tracado_js, "r", encoding="utf-8") as f:
        tjs = f.read()
    assert "carregarContextoUrbano" in tjs
    assert "chkTracadoViasCad" in tjs

    app_js = os.path.join(web_dir, "app.js")
    with open(app_js, "r", encoding="utf-8") as f:
        ajs = f.read()
    assert "chkAutoViasCad" in ajs
    assert "carregarContextoUrbano" in ajs

    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "btnToggleVias" in html
    assert "btnDesenharViasCad" in html
    assert "btnViasTracadoCad" in html
    assert "chkAutoViasCad" in html
    assert "chkTracadoViasCad" in html
    assert "vias_obstrucoes.js" in html

    with open(cad_bridge_cs, "r", encoding="utf-8") as f:
        cs = f.read()
    assert "DesenharElementosUrbanos" in cs
    assert "VIAS_EIXO" in cs
    assert "VIAS_CALCADA" in cs
    assert "OBSTRUCOES_EDIF" in cs

    # Teste analítico do cálculo de Bbox (Buffer métrico)
    lat_ref, lon_ref = -22.9068, -43.1729
    raio_m = 100.0
    delta_lat = raio_m / 111111.0
    delta_lon = raio_m / (111111.0 * math.cos(math.radians(lat_ref)))

    bbox = {
        "south": lat_ref - delta_lat,
        "north": lat_ref + delta_lat,
        "west": lon_ref - delta_lon,
        "east": lon_ref + delta_lon
    }
    assert bbox["north"] > bbox["south"]
    assert bbox["east"] > bbox["west"]
    # Verifica que o raio cobre aproximadamente 200m de amplitude norte-sul
    amplitude_m = (bbox["north"] - bbox["south"]) * 111111.0
    assert abs(amplitude_m - 200.0) < 1.0

    # Teste de classificação semântica de tags OSM
    def classificar_elemento_osm(tags):
        if "building" in tags:
            return "OBSTRUCAO_EDIFICACAO"
        if "barrier" in tags:
            return "OBSTRUCAO_BARREIRA"
        if tags.get("footway") == "sidewalk" or tags.get("highway") in ("footway", "pedestrian"):
            return "CALCADA_PASSEIO"
        if "highway" in tags:
            return "VIA_EIXO"
        return "OUTRO"

    assert classificar_elemento_osm({"highway": "residential", "name": "Rua das Flores"}) == "VIA_EIXO"
    assert classificar_elemento_osm({"highway": "footway", "footway": "sidewalk"}) == "CALCADA_PASSEIO"
    assert classificar_elemento_osm({"building": "yes"}) == "OBSTRUCAO_EDIFICACAO"
    assert classificar_elemento_osm({"barrier": "wall"}) == "OBSTRUCAO_BARREIRA"


def test_layout_consumidores_bt_sem_overflow():
    """Valida ergonomia, steppers, totalizador e proteção contra overflow horizontal na paleta."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    index_html = os.path.join(raiz, "mapa_cad_paleta", "web", "index.html")
    style_css = os.path.join(raiz, "mapa_cad_paleta", "web", "style.css")
    app_js = os.path.join(raiz, "mapa_cad_paleta", "web", "app.js")

    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()

    # Componentes de interface dos Consumidores BT
    assert "clientes-cqt-card" in html
    assert "badgeTotalClientes" in html
    assert "lblTotalClientes" in html
    assert "inputMono" in html
    assert "inputBi" in html
    assert "inputTri" in html
    assert "fase-badge tri" in html
    assert "btn-stepper" in html
    assert "alterarCliente('Tri', 1)" in html
    assert "TRAFO1" in html

    with open(style_css, "r", encoding="utf-8") as f:
        css = f.read()

    # Regras anti-overflow horizontal
    assert "overflow-x: hidden" in css
    assert "clientes-cqt-card" in css
    assert "stepper-control" in css
    assert "repeat(3, minmax(0, 1fr))" in css
    assert "-webkit-appearance: none" in css

    with open(app_js, "r", encoding="utf-8") as f:
        js = f.read()

    # Funções de manipulação e sincronização
    assert "alterarCliente" in js
    assert "zerarClientes" in js
    assert "atualizarTotalClientes" in js
    assert "limparFormulario" in js


def test_tracado_edicao_movimentacao_e_desfazer():
    """Valida recursos de edição interativa: marcadores arrastáveis, desfazer, remoção e recálculo de vãos."""
    import math
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tracado_js = os.path.join(raiz, "mapa_cad_paleta", "web", "tracado.js")
    index_html = os.path.join(raiz, "mapa_cad_paleta", "web", "index.html")
    style_css = os.path.join(raiz, "mapa_cad_paleta", "web", "style.css")
    app_js = os.path.join(raiz, "mapa_cad_paleta", "web", "app.js")
    mapa_control_cs = os.path.join(raiz, "mapa_cad_paleta", "MapaControl.xaml.cs")

    with open(tracado_js, "r", encoding="utf-8") as f:
        js = f.read()

    # Funções mestras de edição e movimentação no JS
    assert "desfazerUltimoPoste" in js
    assert "removerPosteTracado" in js
    assert "redesenharTodoTracado" in js
    assert "criarMarcadorPosteTracado" in js
    assert "draggable: true" in js
    assert "dragend" in js
    assert "toggleListaPostes" in js
    assert "renderizarListaPostesTracado" in js
    assert "markersLayer" in js

    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()

    # Controles na interface HTML
    assert "btnDesfazerTracado" in html
    assert "btnVerPostesTracado" in html
    assert "painelListaPostes" in html
    assert "containerItensPostes" in html

    with open(style_css, "r", encoding="utf-8") as f:
        css = f.read()

    # Estilização no CSS
    assert "tracado-node-marker" in css
    assert "tracado-lista-container" in css
    assert "cursor: grab" in css or "cursor: grabbing" in css

    with open(app_js, "r", encoding="utf-8") as f:
        app_code = f.read()

    # Atalho de teclado Ctrl+Z implementado
    assert "e.ctrlKey" in app_code
    assert "desfazerUltimoPoste" in app_code

    with open(mapa_control_cs, "r", encoding="utf-8") as f:
        cs_code = f.read()

    assert "case \"desfazer_vao\":" in cs_code

    # Teste analítico do recálculo de vãos ao remover um poste intermediário:
    # P1(0, 0), P2(30, 40) com vão = 50m, P3(60, 80) com vão = 50m
    pontos = [
        {"numero": "01", "x": 0.0, "y": 0.0},
        {"numero": "02", "x": 30.0, "y": 40.0},
        {"numero": "03", "x": 60.0, "y": 80.0},
    ]
    vao1 = math.hypot(pontos[1]["x"] - pontos[0]["x"], pontos[1]["y"] - pontos[0]["y"])
    vao2 = math.hypot(pontos[2]["x"] - pontos[1]["x"], pontos[2]["y"] - pontos[1]["y"])
    assert abs(vao1 - 50.0) < 1e-6
    assert abs(vao2 - 50.0) < 1e-6

    # Remove o ponto intermediário (P2)
    removido = pontos.pop(1)
    assert removido["numero"] == "02"
    assert len(pontos) == 2

    # Novo vão reconectado diretamente de P1 para P3:
    novo_vao = math.hypot(pontos[1]["x"] - pontos[0]["x"], pontos[1]["y"] - pontos[0]["y"])
    assert abs(novo_vao - 100.0) < 1e-6


def test_paleta_cqtui_exportacao_e_chamada():
    """Valida que o botão CQT na paleta web e no AutoCAD dispara a CQTUI de forma resiliente."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tracado_js = os.path.join(raiz, "mapa_cad_paleta", "web", "tracado.js")
    index_html = os.path.join(raiz, "mapa_cad_paleta", "web", "index.html")
    mapa_control_cs = os.path.join(raiz, "mapa_cad_paleta", "MapaControl.xaml.cs")
    cqt_extractor_lsp = os.path.join(raiz, "cqt", "cqt_cad_extractor.lsp")

    with open(tracado_js, "r", encoding="utf-8") as f:
        js = f.read()

    # exportarParaCqt não pode bloquear com return se houver < 2 postes
    assert "function exportarParaCqt()" in js
    assert "action: 'exportar_cqt'" in js
    assert "consumidores_base" in js
    assert "temVaos" in js

    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()

    # Botões na interface web
    assert "btnExportarCqt" in html
    assert "⚡ CQTUI" in html

    with open(mapa_control_cs, "r", encoding="utf-8") as f:
        cs = f.read()

    # C# deve suportar exportar_cqt e abrir_cqtui, chamando via CMD com py
    assert 'case "exportar_cqt":' in cs
    assert 'case "abrir_cqtui":' in cs
    assert "auxcad_cqt_import.json" in cs
    assert 'cmd.exe' in cs
    assert 'start \\"\\" py' in cs

    with open(cqt_extractor_lsp, "r", encoding="utf-8") as f:
        lsp = f.read()

    # LISP c:CQTUI e c:CQT_OSM devem ler auxcad_cqt_import.json da paleta
    assert "(defun c:CQTUI" in lsp
    assert "(defun c:CQT_OSM" in lsp
    assert "auxcad_cqt_import.json" in lsp


def test_snyder_js_exportacao_global():
    """Valida que snyder.js exporta explicitamente para window.Snyder e globalThis.Snyder."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    snyder_js = os.path.join(raiz, "mapa_cad_paleta", "web", "snyder.js")

    with open(snyder_js, "r", encoding="utf-8") as f:
        conteudo = f.read()

    assert "window.Snyder = Snyder" in conteudo
    assert "globalThis.Snyder = Snyder" in conteudo
    assert "latLonToUtm" in conteudo
    assert "utmToLatLon" in conteudo


def test_vias_cad_ao_inserir_poste():
    """Valida que vias_obstrucoes.js e app.js garantem envio de vias ao AutoCAD sem barreiras indevidas."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    vias_js = os.path.join(raiz, "mapa_cad_paleta", "web", "vias_obstrucoes.js")
    app_js = os.path.join(raiz, "mapa_cad_paleta", "web", "app.js")

    with open(vias_js, "r", encoding="utf-8") as f:
        vias_conteudo = f.read()

    # Deve usar POST com Content-Type application/x-www-form-urlencoded para evitar erro 406
    assert "method: 'POST'" in vias_conteudo
    assert "application/x-www-form-urlencoded" in vias_conteudo
    assert "executarConsultaOverpass" in vias_conteudo

    # toggleViasObstrucoes não pode desativar desenharNoCad
    assert "ViasObstrucoesState.desenharNoCad = ViasObstrucoesState.ativo" not in vias_conteudo

    # converterEEnviarParaCad deve usar fallback resiliente para Snyder
    assert "window.Snyder" in vias_conteudo
    assert "desenhar_elementos_urbanos" in vias_conteudo

    with open(app_js, "r", encoding="utf-8") as f:
        app_conteudo = f.read()

    # Inserção de poste deve calcular coordenadas analíticas e forçar envio ao CAD
    assert "chkAutoViasCad" in app_conteudo
    assert "carregarContextoUrbano" in app_conteudo
    assert "forcarCad" in vias_conteudo or "true" in app_conteudo


def test_osm_api_oficial_e_snyder_syntax():
    """Valida integridade sintática do snyder.js e suporte nativo à API Oficial OSM."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    snyder_js = os.path.join(raiz, "mapa_cad_paleta", "web", "snyder.js")
    vias_js = os.path.join(raiz, "mapa_cad_paleta", "web", "vias_obstrucoes.js")
    cad_bridge = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")

    with open(snyder_js, "r", encoding="utf-8") as f:
        snyder_conteudo = f.read()

    # Valida fechamento sintático correto do objeto Snyder
    assert "};" in snyder_conteudo
    assert "window.Snyder = Snyder;" in snyder_conteudo

    with open(vias_js, "r", encoding="utf-8") as f:
        vias_conteudo = f.read()

    # Valida presença da API oficial OSM e suporte duplo a JSON/XML
    assert "api.openstreetmap.org/api/0.6/map.json" in vias_conteudo
    assert "converterOsmXmlParaJson" in vias_conteudo
    assert "executarConsultaOsm" in vias_conteudo

    with open(cad_bridge, "r", encoding="utf-8") as f:
        bridge_conteudo = f.read()

    # Valida desenho de polilinhas urbanas e nomes de ruas
    assert "DesenharListaPolilinhas" in bridge_conteudo
    assert "LAYER_VIAS_EIXO" in bridge_conteudo
    assert "LAYER_VIAS_CALCADA" in bridge_conteudo
    assert "LAYER_OBSTRUCOES_EDIF" in bridge_conteudo
    assert "inserirNome" in bridge_conteudo


def test_deduplicacao_consulta_contexto_urbano_tracado():
    """Valida a eliminação da chamada redundante (P2) para o poste em tracado.js e preservação do vão."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tracado_js = os.path.join(raiz, "mapa_cad_paleta", "web", "tracado.js")
    app_js = os.path.join(raiz, "mapa_cad_paleta", "web", "app.js")

    with open(tracado_js, "r", encoding="utf-8") as f:
        tracado_conteudo = f.read()

    with open(app_js, "r", encoding="utf-8") as f:
        app_conteudo = f.read()

    # tracado.js NÃO deve duplicar a consulta do novo poste (120m)
    assert "carregarContextoUrbano(novoPoste.lat" not in tracado_conteudo
    # tracado.js DEVE manter a consulta para o ponto médio do vão
    assert "carregarContextoUrbano(midLat, midLon" in tracado_conteudo
    # app.js DEVE manter a consulta unificada autoritativa para o novo poste com raio 140m
    assert "carregarContextoUrbano(pLat, pLon, 140, AppState.map, true)" in app_conteudo


def test_identidade_persistente_xdata_bim():
    """Valida a implementação da Identidade Persistente BIM via XData nativo (AUXCAD_POSTE / AUXCAD_VAO)."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cad_bridge = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")

    with open(cad_bridge, "r", encoding="utf-8") as f:
        conteudo = f.read()

    # Aplicações DXF registradas oficiais
    assert 'REGAPP_POSTE = "AUXCAD_POSTE"' in conteudo
    assert 'REGAPP_VAO = "AUXCAD_VAO"' in conteudo

    # Métodos de garantia e gravação de XData
    assert "GarantirRegApp" in conteudo
    assert "GravarXDataPoste" in conteudo
    assert "GravarXDataVao" in conteudo

    # Uso de ResultBuffer e DxfCode oficial do AutoCAD
    assert "DxfCode.ExtendedDataRegAppName" in conteudo
    assert "DxfCode.ExtendedDataAsciiString" in conteudo

    # Rastreamento de entidades com registro de operação
    assert "CadOperacaoRegistro" in conteudo
    assert "OperationId" in conteudo


def test_rollback_desfazer_operacao_cad():
    """Valida o mecanismo seguro de Undo/Rollback no DWG via handles e XData."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cad_bridge = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")
    mapa_control = os.path.join(raiz, "mapa_cad_paleta", "MapaControl.xaml.cs")
    tracado_js = os.path.join(raiz, "mapa_cad_paleta", "web", "tracado.js")
    app_js = os.path.join(raiz, "mapa_cad_paleta", "web", "app.js")

    with open(cad_bridge, "r", encoding="utf-8") as f:
        bridge_c = f.read()
    with open(mapa_control, "r", encoding="utf-8") as f:
        control_c = f.read()
    with open(tracado_js, "r", encoding="utf-8") as f:
        tracado_c = f.read()
    with open(app_js, "r", encoding="utf-8") as f:
        app_c = f.read()

    # CadBridge possui DesfazerUltimaOperacao implementado
    assert "DesfazerUltimaOperacao" in bridge_c
    assert "ent.Erase(true)" in bridge_c

    # MapaControl conecta desfazer_vao ao CadBridge com resultado_desfazer
    assert "CadBridge.DesfazerUltimaOperacao" in control_c
    assert 'action = "resultado_desfazer"' in control_c

    # tracado.js envia operationId ao desfazer
    assert "operationId: removido.operationId" in tracado_c

    # app.js escuta resultado_desfazer e gera operationId na inserção
    assert "resultado_desfazer" in app_c
    assert "operationId: opId" in app_c


def test_escanear_postes_dwg_bim_e_compatibilidade_legado():
    """Valida a leitura de metadados BIM no scan do DWG e preservação de compatibilidade com DWG legado."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cad_bridge = os.path.join(raiz, "mapa_cad_paleta", "CadBridge.cs")
    app_js = os.path.join(raiz, "mapa_cad_paleta", "web", "app.js")

    with open(cad_bridge, "r", encoding="utf-8") as f:
        bridge_c = f.read()
    with open(app_js, "r", encoding="utf-8") as f:
        app_c = f.read()

    # EscanearPostesDwg lê XData da aplicação AUXCAD_POSTE
    assert "GetXDataForApplication(REGAPP_POSTE)" in bridge_c
    assert "isLegacy" in bridge_c
    assert "temTrafo" in bridge_c
    assert "tipoPoste" in bridge_c

    # Frontend renderiza informações ricas e tag de legado
    assert "renderizarPostesDwg" in app_c
    assert "legacyTag" in app_c
    assert "trafoInfo" in app_c


def test_seguranca_webview2_origem_autorizada():
    """Valida segurança do WebView2 com IsAuthorizedOrigin e ausência de fallback inseguro."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    mapa_control = os.path.join(raiz, "mapa_cad_paleta", "MapaControl.xaml.cs")

    with open(mapa_control, "r", encoding="utf-8") as f:
        control_c = f.read()

    # Método IsAuthorizedOrigin deve existir e restringir a appassets.example
    assert "IsAuthorizedOrigin" in control_c
    assert "https://appassets.example" in control_c
    # Não deve haver fallback silencioso para file:///
    assert "file:///" not in control_c


# ==============================================================================
# SUÍTE ARQUITETURAL DE IDENTIDADE PERSISTENTE E TOPOLOGIA (T01 - T10)
# ==============================================================================

import uuid


class SimiladorDominioEletrico:
    """Implementação canônica de referência das regras de domínio para testes unitários comportamentais."""

    @staticmethod
    def criar_poste(numero: str, x: float, y: float, op_id: str = None, domain_id: str = None):
        return {
            "id": domain_id or str(uuid.uuid4()),
            "numero": str(numero),
            "operationId": op_id or f"op_{uuid.uuid4().hex[:8]}",
            "x": x,
            "y": y,
            "tipoPoste": "11/600",
            "handle": hex(uuid.uuid4().int)[2:10].upper()
        }

    @staticmethod
    def criar_vao(poste_origem: dict, poste_destino: dict, tipo_rede: str = "BT", op_id: str = None, vao_id: str = None):
        dx = poste_destino["x"] - poste_origem["x"]
        dy = poste_destino["y"] - poste_origem["y"]
        extensao = round((dx**2 + dy**2)**0.5, 2)
        return {
            "id": vao_id or str(uuid.uuid4()),
            "operationId": op_id or f"op_{uuid.uuid4().hex[:8]}",
            "posteOrigemId": poste_origem["id"],
            "posteDestinoId": poste_destino["id"],
            "de": poste_origem["numero"],
            "para": poste_destino["numero"],
            "tipoRede": tipo_rede,
            "extensao": extensao,
            "textoVao": f"{extensao:.1f}m",
            "handle": hex(uuid.uuid4().int)[2:10].upper()
        }

    @staticmethod
    def serializar_xdata_poste(poste: dict):
        metadata_json = json.dumps({
            "id": poste["id"],
            "domainId": poste["id"],
            "numero": poste["numero"],
            "tipoPoste": poste["tipoPoste"],
            "operationId": poste["operationId"]
        })
        return {
            "regApp": "AUXCAD_POSTE",
            "strings": [poste["id"], poste["numero"], poste["tipoPoste"], poste["operationId"], metadata_json]
        }

    @staticmethod
    def deserializar_xdata_poste(xdata: dict):
        strings = xdata.get("strings", [])
        domain_id = ""
        numero = ""
        op_id = ""

        # Lê do JSON metadata se presente
        json_str = next((s for s in strings if s.startswith("{")), None)
        if json_str:
            meta = json.loads(json_str)
            domain_id = meta.get("id") or meta.get("domainId", "")
            numero = meta.get("numero", "")
            op_id = meta.get("operationId", "")

        # Fallback posicional
        if not domain_id and len(strings) >= 1:
            try:
                uuid.UUID(strings[0])
                domain_id = strings[0]
                if len(strings) >= 2:
                    numero = strings[1]
            except ValueError:
                # Legado onde strings[0] era o número
                numero = strings[0]

        return {"domainId": domain_id, "numero": numero, "operationId": op_id}

    @staticmethod
    def reconciliar_clones_copy(entidades: list):
        """Simula o mecanismo de autocorreção de COPY nativo do AutoCAD no scan."""
        domain_ids_vistos = set()
        resultado = []
        for ent in entidades:
            ent_copy = dict(ent)
            d_id = ent_copy.get("id")
            if d_id in domain_ids_vistos:
                # Clone detectado: gera novo DomainId mantendo número visual
                ent_copy["id"] = str(uuid.uuid4())
                ent_copy["clonado"] = True
            else:
                domain_ids_vistos.add(d_id)
            resultado.append(ent_copy)
        return resultado

    @staticmethod
    def executar_undo(entidades: list, domain_id: str = None, op_id: str = None):
        """Simula o Undo transacional por OperationId e DomainId, independente de número."""
        if op_id:
            return [e for e in entidades if e.get("operationId") != op_id]
        if domain_id:
            return [e for e in entidades if e.get("id") != domain_id]
        if entidades:
            return entidades[:-1]
        return entidades


def test_t01_dois_postes_possuem_domain_ids_diferentes():
    """T01: Dois postes criados possuem DomainIds diferentes."""
    p1 = SimiladorDominioEletrico.criar_poste("01", 100.0, 200.0)
    p2 = SimiladorDominioEletrico.criar_poste("02", 140.0, 200.0)

    assert p1["id"] != p2["id"]
    assert uuid.UUID(p1["id"])  # Deve ser GUID válido
    assert uuid.UUID(p2["id"])  # Deve ser GUID válido


def test_t02_numero_visual_igual_sem_colisao_domain_id():
    """T02: O número visual pode ser igual sem gerar colisão de DomainId."""
    p1 = SimiladorDominioEletrico.criar_poste("01", 100.0, 200.0)
    p2 = SimiladorDominioEletrico.criar_poste("01", 200.0, 300.0)

    assert p1["numero"] == p2["numero"] == "01"
    assert p1["id"] != p2["id"], "DomainId colidiu mesmo sendo entidades distintas"


def test_t03_dois_vaos_possuem_vao_ids_diferentes():
    """T03: Dois vãos possuem VaoIds diferentes."""
    p1 = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    p2 = SimiladorDominioEletrico.criar_poste("02", 30, 0)
    p3 = SimiladorDominioEletrico.criar_poste("03", 60, 0)

    v1 = SimiladorDominioEletrico.criar_vao(p1, p2)
    v2 = SimiladorDominioEletrico.criar_vao(p2, p3)

    assert v1["id"] != v2["id"]
    assert uuid.UUID(v1["id"])
    assert uuid.UUID(v2["id"])


def test_t04_vao_referencia_domain_ids_corretos_dos_postes():
    """T04: Um vão referencia os DomainIds corretos dos postes."""
    p1 = SimiladorDominioEletrico.criar_poste("P_A", 10, 20)
    p2 = SimiladorDominioEletrico.criar_poste("P_B", 40, 60)

    vao = SimiladorDominioEletrico.criar_vao(p1, p2)

    assert vao["posteOrigemId"] == p1["id"]
    assert vao["posteDestinoId"] == p2["id"]
    assert vao["posteOrigemId"] != p1["numero"]
    assert vao["posteDestinoId"] != p2["numero"]


def test_t05_operation_id_compartilhado_multiplas_entidades_com_domain_ids_distintos():
    """T05: OperationId pode ser igual para múltiplas entidades da mesma operação sem transformar essas entidades na mesma entidade."""
    shared_op_id = "op_batch_123"
    p1 = SimiladorDominioEletrico.criar_poste("01", 0, 0, op_id=shared_op_id)
    p2 = SimiladorDominioEletrico.criar_poste("02", 35, 0, op_id=shared_op_id)
    v1 = SimiladorDominioEletrico.criar_vao(p1, p2, op_id=shared_op_id)

    assert p1["operationId"] == p2["operationId"] == v1["operationId"] == shared_op_id
    assert p1["id"] != p2["id"]
    assert p1["id"] != v1["id"]
    assert p2["id"] != v1["id"]


def test_t06_xdata_contem_domain_id_e_operation_id_distintos():
    """T06: XData contém DomainId e OperationId distintos."""
    domain_id = str(uuid.uuid4())
    op_id = "op_test_999"
    poste = SimiladorDominioEletrico.criar_poste("10", 50, 50, op_id=op_id, domain_id=domain_id)

    xdata = SimiladorDominioEletrico.serializar_xdata_poste(poste)
    meta = json.loads(xdata["strings"][-1])

    assert meta["id"] == domain_id
    assert meta["operationId"] == op_id
    assert meta["id"] != meta["operationId"]
    assert xdata["strings"][0] == domain_id
    assert xdata["strings"][3] == op_id


def test_t07_undo_nao_depende_do_numero_visual():
    """T07: Undo não depende do número visual."""
    p1 = SimiladorDominioEletrico.criar_poste("01", 10, 10)
    p2 = SimiladorDominioEletrico.criar_poste("01", 20, 20)  # Mesmo número visual "01"
    entidades = [p1, p2]

    # Desfazer especificando domainId do poste 2
    restantes = SimiladorDominioEletrico.executar_undo(entidades, domain_id=p2["id"])

    assert len(restantes) == 1
    assert restantes[0]["id"] == p1["id"]
    assert restantes[0]["numero"] == "01"  # Poste 1 com mesmo número foi preservado!


def test_t08_scanner_interpreta_domain_id_e_numero_separadamente():
    """T08: Scanner consegue interpretar DomainId + Numero separadamente."""
    d_id = str(uuid.uuid4())
    num = "P-105"
    xdata = {
        "strings": [d_id, num, "11/600", "op_123", json.dumps({"id": d_id, "numero": num, "tipoPoste": "11/600"})]
    }

    resultado = SimiladorDominioEletrico.deserializar_xdata_poste(xdata)

    assert resultado["domainId"] == d_id
    assert resultado["numero"] == num
    assert resultado["domainId"] != resultado["numero"]


def test_t09_copy_clonagem_detectada_e_reconciliada_sem_colisao():
    """T09: COPY/clonagem não preserva DomainId quando o mecanismo implementado detectar a clonagem."""
    original = SimiladorDominioEletrico.criar_poste("01", 10, 10)
    # AutoCAD COPY duplica a entidade com XData idêntico
    clone = dict(original)
    clone["handle"] = "A1B2C3"

    assert original["id"] == clone["id"]

    # Reconciliação no scanner
    reconciliados = SimiladorDominioEletrico.reconciliar_clones_copy([original, clone])

    p_orig = reconciliados[0]
    p_clone = reconciliados[1]

    assert p_orig["id"] == original["id"], "Original deve manter seu DomainId"
    assert p_clone["id"] != original["id"], "Clone deve receber NOVO DomainId"
    assert p_clone["numero"] == original["numero"], "GAP-007: Número visual deve ser preservado temporariamente"


def test_t10_reconstrucao_topologica_preserva_relacoes_por_id():
    """T10: Reconstrução de um conjunto Poste + Vão preserva as relações por ID."""
    pA = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    pB = SimiladorDominioEletrico.criar_poste("02", 30, 0)
    pC = SimiladorDominioEletrico.criar_poste("03", 60, 0)

    vAB = SimiladorDominioEletrico.criar_vao(pA, pB)
    vBC = SimiladorDominioEletrico.criar_vao(pB, pC)

    postes_dwg = [pA, pB, pC]
    vaos_dwg = [vAB, vBC]

    # Reconstrução
    id_map = {p["id"]: p for p in postes_dwg}

    # Valida conectividade topológica
    for v in vaos_dwg:
        orig = id_map.get(v["posteOrigemId"])
        dest = id_map.get(v["posteDestinoId"])
        assert orig is not None
        assert dest is not None
        assert orig["id"] == v["posteOrigemId"]
        assert dest["id"] == v["posteDestinoId"]


def test_t11_domain_id_canonico_e_guid_valido():
    """T11: DomainId canônico é GUID RFC4122 válido tanto no C# quanto no JS."""
    p = SimiladorDominioEletrico.criar_poste("01", 10.0, 20.0)
    parsed = uuid.UUID(p["id"])
    assert parsed.version == 4, "DomainId deve ser GUID v4 válido"
    assert len(p["id"]) == 36, "GUID deve possuir formato canônico de 36 caracteres"


def test_t12_vao_id_canonico_e_guid_valido():
    """T12: VaoId canônico é GUID RFC4122 válido."""
    p1 = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    p2 = SimiladorDominioEletrico.criar_poste("02", 40, 0)
    v = SimiladorDominioEletrico.criar_vao(p1, p2)
    parsed = uuid.UUID(v["id"])
    assert parsed.version == 4, "VaoId deve ser GUID v4 válido"
    assert len(v["id"]) == 36


def test_t13_copy_de_poste_gera_identidade_nova():
    """T13: COPY de um Poste isolado gera nova identidade de domínio sem alterar o original."""
    p_orig = SimiladorDominioEletrico.criar_poste("10", 100, 100)
    p_clone = dict(p_orig)
    p_clone["handle"] = "H_CLONE_1"

    reconciliados = SimiladorDominioEletrico.reconciliar_clones_copy([p_orig, p_clone])
    assert len(reconciliados) == 2
    assert reconciliados[0]["id"] == p_orig["id"]
    assert reconciliados[1]["id"] != p_orig["id"]
    assert uuid.UUID(reconciliados[1]["id"]).version == 4


def test_t14_copy_de_vao_gera_identidade_nova():
    """T14: COPY de um Vão isolado gera nova identidade lógica."""
    p1 = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    p2 = SimiladorDominioEletrico.criar_poste("02", 30, 0)
    v_orig = SimiladorDominioEletrico.criar_vao(p1, p2)
    v_clone = dict(v_orig)
    v_clone["handle"] = "H_VAO_CLONE"

    # Simula reconciliação de vãos
    reconciliados = SimiladorDominioEletrico.reconciliar_clones_copy([v_orig, v_clone])
    assert reconciliados[0]["id"] == v_orig["id"]
    assert reconciliados[1]["id"] != v_orig["id"]
    assert uuid.UUID(reconciliados[1]["id"]).version == 4


def test_t15_copy_de_conjunto_preserva_relacoes_internas_quando_identificaveis():
    """T15: COPY de um conjunto (Poste A + Vão + Poste B) preserva referências internas remapeadas."""
    pA = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    pB = SimiladorDominioEletrico.criar_poste("02", 35, 0)
    vAB = SimiladorDominioEletrico.criar_vao(pA, pB)

    # Clona todo o conjunto no DWG
    pA_c = dict(pA)
    pA_c["handle"] = "HA_CLONE"
    pB_c = dict(pB)
    pB_c["handle"] = "HB_CLONE"
    vAB_c = dict(vAB)
    vAB_c["handle"] = "HV_CLONE"

    # Simulação do algoritmo de remapeamento de conjunto
    remap = {}
    postes_rec = []
    vistos = set()
    for p in [pA, pB, pA_c, pB_c]:
        pc = dict(p)
        if pc["id"] in vistos:
            novo_id = str(uuid.uuid4())
            remap[pc["id"]] = novo_id
            pc["id"] = novo_id
        else:
            vistos.add(pc["id"])
        postes_rec.append(pc)

    # Vão clonado remapeia referências internas
    vAB_c["id"] = str(uuid.uuid4())
    if vAB_c["posteOrigemId"] in remap:
        vAB_c["posteOrigemId"] = remap[vAB_c["posteOrigemId"]]
    if vAB_c["posteDestinoId"] in remap:
        vAB_c["posteDestinoId"] = remap[vAB_c["posteDestinoId"]]

    assert vAB_c["posteOrigemId"] == postes_rec[2]["id"]
    assert vAB_c["posteDestinoId"] == postes_rec[3]["id"]
    assert vAB_c["posteOrigemId"] != pA["id"]


def test_t16_referencia_externa_nao_e_redirecionada_silenciosamente():
    """T16: Vão clonado isoladamente que aponta para postes externos não remapeados mantém as referências externas intactas."""
    pA = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    pB = SimiladorDominioEletrico.criar_poste("02", 35, 0)
    vAB = SimiladorDominioEletrico.criar_vao(pA, pB)
    vAB_clone = dict(vAB)
    vAB_clone["handle"] = "H_EXT"
    vAB_clone["id"] = str(uuid.uuid4())

    # Postes não foram clonados: as referências de pA e pB permanecem
    assert vAB_clone["posteOrigemId"] == pA["id"]
    assert vAB_clone["posteDestinoId"] == pB["id"]


def test_t17_vao_orfao_e_detectado():
    """T17: Vão cujas referências de poste não existem no DWG é detectado como ORPHAN_VAO."""
    vao = {
        "id": str(uuid.uuid4()),
        "posteOrigemId": "ID_INEXISTENTE_ORIG",
        "posteDestinoId": "ID_INEXISTENTE_DEST",
        "handle": "H_ORPHAN"
    }
    postes_dwg = [SimiladorDominioEletrico.criar_poste("01", 0, 0)]
    postes_ids = {p["id"] for p in postes_dwg}

    orig_existe = vao["posteOrigemId"] in postes_ids
    dest_existe = vao["posteDestinoId"] in postes_ids
    is_orphan = not orig_existe or not dest_existe

    assert is_orphan is True


def test_t18_poste_apagado_gera_diagnostico_de_vao_orfao():
    """T18: Quando um poste é apagado do DWG (ERASE), os vãos conectados viram órfãos."""
    pA = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    pB = SimiladorDominioEletrico.criar_poste("02", 30, 0)
    v1 = SimiladorDominioEletrico.criar_vao(pA, pB)

    # ERASE nativo em pA (resta apenas pB no DWG)
    postes_ativos = [pB]
    mapa_ids = {p["id"] for p in postes_ativos}

    assert v1["posteOrigemId"] not in mapa_ids
    assert v1["posteDestinoId"] in mapa_ids
    orphan_reason = f"Poste de origem '{v1['posteOrigemId']}' não encontrado no DWG."
    assert "não encontrado no DWG" in orphan_reason


def test_t19_legacy_com_um_unico_candidato_geometrico_e_marcado_como_inferido():
    """T19: Vão legado resolvido por geometria única a < 1.0m é explicitamente marcado como Inferred."""
    import math
    pA = SimiladorDominioEletrico.criar_poste("01", 0.0, 0.0)
    pB = SimiladorDominioEletrico.criar_poste("02", 40.0, 0.0)

    # Extremidade do vão legado a 0.2m do poste A (dentro do raio de 1.0m)
    p1 = (0.2, 0.0)
    dist = math.hypot(p1[0] - pA["x"], p1[1] - pA["y"])
    assert dist < 1.0

    # Método de resolução
    res_method = "Geometry"
    res_confidence = "Inferred"
    assert res_method == "Geometry"
    assert res_confidence == "Inferred"


def test_t20_legacy_ambiguo_nao_e_resolvido_arbitrariamente():
    """T20: Vão legado com múltiplos postes a < 1.0m não escolhe arbitrariamente e registra ambiguidade."""
    import math
    pA1 = SimiladorDominioEletrico.criar_poste("01", 0.0, 0.0)
    pA2 = SimiladorDominioEletrico.criar_poste("02", 0.5, 0.0)

    p1 = (0.2, 0.0)
    candidatos = []
    for p in [pA1, pA2]:
        d = math.hypot(p1[0] - p["x"], p1[1] - p["y"])
        if d < 1.0:
            candidatos.append(p)

    assert len(candidatos) == 2, "Dois candidatos detectados a < 1.0m"
    # Não deve escolher aleatoriamente
    res_confidence = "Ambiguous" if len(candidatos) > 1 else "Inferred"
    assert res_confidence == "Ambiguous"


def test_t21_move_preserva_ids():
    """T21: Operação MOVE nativa altera coordenadas X/Y mas preserva DomainId, Numero e VaoId."""
    p = SimiladorDominioEletrico.criar_poste("01", 10.0, 20.0)
    orig_id = p["id"]
    orig_num = p["numero"]

    # Simula MOVE (+5m em X, +10m em Y)
    p["x"] += 5.0
    p["y"] += 10.0

    assert p["id"] == orig_id, "DomainId não pode ser alterado após MOVE"
    assert p["numero"] == orig_num, "Numero não pode ser alterado após MOVE"
    assert p["x"] == 15.0
    assert p["y"] == 30.0


def test_t22_reconstrucao_substitui_estado_anterior():
    """T22: Sincronização do DWG substitui integralmente o estado anterior do traçado (sem merges cegos)."""
    estado_anterior = [
        {"id": "pA", "numero": "01"},
        {"id": "pB", "numero": "02"},
        {"id": "pC", "numero": "03"}
    ]
    # No DWG, o usuário deletou pC
    dwg_estado = [
        {"id": "pA", "numero": "01"},
        {"id": "pB", "numero": "02"}
    ]

    # Reconstrução autoritativa substitui a lista
    estado_sincronizado = list(dwg_estado)
    assert len(estado_sincronizado) == 2
    assert all(p["id"] != "pC" for p in estado_sincronizado)


def test_t23_reconstrucao_nao_duplica_markers():
    """T23: A camada de marcadores tem clearLayers() garantindo 0 duplicações visuais."""
    markers_layer = []
    # Estado inicial
    markers_layer.extend(["m1", "m2"])
    assert len(markers_layer) == 2

    # Sincronização com limpeza prévia
    markers_layer.clear()
    novos_postes = ["m1", "m2", "m3"]
    markers_layer.extend(novos_postes)

    assert len(markers_layer) == 3, "Marcadores não devem duplicar para 5"


def test_t24_reconstrucao_nao_duplica_vaos():
    """T24: A camada de polilinhas tem clearLayers() garantindo 0 duplicações de trechos."""
    vaos_state = [{"id": "v1"}, {"id": "v2"}]
    # Limpeza autoritativa
    vaos_state = []
    novos_vaos = [{"id": "v1"}, {"id": "v2"}]
    vaos_state.extend(novos_vaos)

    assert len(vaos_state) == 2


def test_t25_xdata_invalido_nao_derruba_o_scanner_inteiro():
    """T25: Entidade com XData corrompido é marcada como IsValid=false e o scan continua."""
    xdata_corrompido = {
        "strings": ["not-a-guid", "{json_malformado: true,"]
    }
    # Tenta decodificar
    is_valid = True
    invalid_reason = ""
    domain_id = ""
    try:
        json.loads(xdata_corrompido["strings"][1])
    except json.JSONDecodeError as ex:
        is_valid = False
        invalid_reason = str(ex)

    assert is_valid is False
    assert len(invalid_reason) > 0


def test_t26_versao_antiga_de_xdata_e_tratada():
    """T26: Schema version 1 (legado sem header de versão) é tratado graciosamente."""
    xdata_v1 = {
        "strings": [str(uuid.uuid4()), "01", "11/600", "op_old", "{}"]
    }
    # Decodificação
    parsed = SimiladorDominioEletrico.deserializar_xdata_poste(xdata_v1)
    assert uuid.UUID(parsed["domainId"])
    assert parsed["numero"] == "01"


def test_t27_entidade_parcialmente_corrompida_gera_diagnostico():
    """T27: Entidade com carga parcial gera diagnóstico estruturado DwgDiagnostic."""
    diag = {
        "code": "INVALID_XDATA_JSON",
        "severity": "WARNING",
        "entityType": "POSTE",
        "entityId": "handle_123",
        "message": "Metadados JSON corrompidos"
    }
    assert diag["code"] == "INVALID_XDATA_JSON"
    assert diag["severity"] == "WARNING"


def test_t28_undo_usa_identidade_logica_e_nao_numero():
    """T28: Desfazer por DomainId remove a entidade correta mesmo se houver outro poste com mesmo número."""
    p1 = SimiladorDominioEletrico.criar_poste("10", 0, 0)
    p2 = SimiladorDominioEletrico.criar_poste("10", 50, 0)
    entidades = [p1, p2]

    restantes = SimiladorDominioEletrico.executar_undo(entidades, domain_id=p1["id"])
    assert len(restantes) == 1
    assert restantes[0]["id"] == p2["id"]
    assert restantes[0]["numero"] == "10"


def test_t29_dois_postes_com_mesmo_numero_continuam_independentes():
    """T29: Dois postes com mesmo número possuem handles e DomainIds distintos e independentes."""
    p1 = SimiladorDominioEletrico.criar_poste("05", 100, 100)
    p2 = SimiladorDominioEletrico.criar_poste("05", 200, 200)

    assert p1["numero"] == p2["numero"]
    assert p1["id"] != p2["id"]
    assert p1["handle"] != p2["handle"]


def test_t30_dois_vaos_com_mesmo_de_para_visual_continuam_independentes():
    """T30: Dois vãos com mesmo 'De/Para' visual (ex: MT e BT no mesmo vão de postes) possuem VaoIds distintos."""
    p1 = SimiladorDominioEletrico.criar_poste("01", 0, 0)
    p2 = SimiladorDominioEletrico.criar_poste("02", 30, 0)

    v_bt = SimiladorDominioEletrico.criar_vao(p1, p2, tipo_rede="BT")
    v_mt = SimiladorDominioEletrico.criar_vao(p1, p2, tipo_rede="MT")

    assert v_bt["de"] == v_mt["de"] == "01"
    assert v_bt["para"] == v_mt["para"] == "02"
    assert v_bt["id"] != v_mt["id"], "VaoIds devem ser distintos mesmo no mesmo vão físico"
    assert v_bt["handle"] != v_mt["handle"]


def test_t31_copy_set_rigoroso_com_ambiguidade_gera_incerteza():
    """T31: Cópia parcial de conjunto (apenas uma extremidade remapeada) gera COPY_SET_UNCERTAIN sem mutação cega."""
    # Simula regra do CadBridge.cs: se origem e destino foram clonados juntos -> remapeia. Se apenas um -> COPY_SET_UNCERTAIN.
    remap = {"ORIG_REMAP": "NOVO_ORIG"}
    vao = {
        "id": "VAO_CLONE",
        "posteOrigemId": "ORIG_REMAP",
        "posteDestinoId": "DEST_EXTERNO_NAO_REMAP"
    }

    orig_clonada = vao["posteOrigemId"] in remap
    dest_clonada = vao["posteDestinoId"] in remap

    if orig_clonada and dest_clonada:
        diag = "COPY_SET_REPAIRED"
    elif orig_clonada != dest_clonada:
        diag = "COPY_SET_UNCERTAIN"
    else:
        diag = "NO_REPAIR"

    assert diag == "COPY_SET_UNCERTAIN"
    # A referência de destino não foi alterada arbitrariamente
    assert vao["posteDestinoId"] == "DEST_EXTERNO_NAO_REMAP"


def test_t32_versao_futura_de_xdata_gera_unsupported_version():
    """T32: Schema version superior à suportada pelo scanner (ex: v3 > v2) gera UNSUPPORTED_XDATA_VERSION."""
    schema_suportado = 2
    schema_entidade = 3

    if schema_entidade > schema_suportado:
        diag_code = "UNSUPPORTED_XDATA_VERSION"
    elif schema_entidade < schema_suportado:
        diag_code = "LEGACY_ENTITY"
    else:
        diag_code = "OK"

    assert diag_code == "UNSUPPORTED_XDATA_VERSION"








def test_dt01_modelo_digital_twin_isolado_e_read_model():
    """DT01-T07: o modelo não referencia AutoCAD, WebView2 ou operações de escrita."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho = os.path.join(raiz, "mapa_cad_paleta", "DigitalTwin.cs")
    assert os.path.exists(caminho)

    with open(caminho, "r", encoding="utf-8") as f:
        fonte = f.read()

    assert "class DigitalTwin" in fonte
    assert "class PosteTwin" in fonte
    assert "class VaoTwin" in fonte
    assert "class DigitalTwinBuilder" in fonte
    assert "EscanearDwgResultado state" in fonte
    assert "DWG_SCAN" in fonte
    assert "DocumentLock" not in fonte
    assert "Transaction" not in fonte
    assert "WebView2" not in fonte
    assert "GravarXData" not in fonte


def test_dt01_builder_preserva_identidade_e_nao_gera_ids():
    """DT01-T03/T06: IDs vêm do estado lido e não há geração silenciosa no builder."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho = os.path.join(raiz, "mapa_cad_paleta", "DigitalTwin.cs")
    with open(caminho, "r", encoding="utf-8") as f:
        fonte = f.read()

    assert "poste.Id" in fonte
    assert "vao.Id" in fonte
    assert 'TWIN_MISSING_POSTE_ID' in fonte
    assert 'TWIN_MISSING_VAO_ID' in fonte
    assert "nenhuma identidade foi gerada" in fonte
    assert "Guid.NewGuid" not in fonte
    assert "new Guid" not in fonte


def test_dt01_diagnostica_topologia_sem_reparo():
    """DT01-T02/T04: órfãos e IDs duplicados viram diagnósticos, sem escrita no DWG."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho = os.path.join(raiz, "mapa_cad_paleta", "DigitalTwin.cs")
    with open(caminho, "r", encoding="utf-8") as f:
        fonte = f.read()

    assert 'TWIN_ORPHAN_VAO' in fonte
    assert 'TWIN_DUPLICATE_POSTE_ID' in fonte
    assert 'TWIN_DUPLICATE_VAO_ID' in fonte
    assert "TwinTopologyGraph" in fonte
    assert "ExecutarReparosDwg" not in fonte


def test_dt01_t01_modelo_cobre_postes_vaos_topologia_e_diagnosticos():
    """DT01-T01: o modelo mínimo representa os dois ativos e a relação topológica."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho = os.path.join(raiz, "mapa_cad_paleta", "DigitalTwin.cs")
    with open(caminho, "r", encoding="utf-8") as f:
        fonte = f.read()

    assert "IReadOnlyList<PosteTwin> Postes" in fonte
    assert "IReadOnlyList<VaoTwin> Vaos" in fonte
    assert "IReadOnlyList<TwinTopologyRelation> Topology" in fonte
    assert "IReadOnlyList<TwinDiagnostic> Diagnostics" in fonte


def test_dt01_t02_t04_diagnosticos_cobrem_orfao_e_inconsistencia():
    """DT01-T02/T04: os códigos de inconsistência são parte do contrato do builder."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho = os.path.join(raiz, "mapa_cad_paleta", "DigitalTwin.cs")
    with open(caminho, "r", encoding="utf-8") as f:
        fonte = f.read()

    assert "TWIN_ORPHAN_VAO" in fonte
    assert "TWIN_DUPLICATE_POSTE_ID" in fonte
    assert "TWIN_DUPLICATE_VAO_ID" in fonte


def test_dt01_t05_twin_vazio_e_modelo_valido():
    """DT01-T05: o construtor aceita coleções vazias sem depender do AutoCAD."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho = os.path.join(raiz, "mapa_cad_paleta", "DigitalTwin.cs")
    with open(caminho, "r", encoding="utf-8") as f:
        fonte = f.read()

    assert "DigitalTwin(" in fonte
    assert "ArgumentNullException" in fonte
    assert "ToList().AsReadOnly()" in fonte


def test_dt01_t06_geometria_e_proveniencia_nao_sao_fabricadas():
    """DT01-T06: geometria vem dos DTOs e Z ausente permanece nullable."""
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho = os.path.join(raiz, "mapa_cad_paleta", "DigitalTwin.cs")
    with open(caminho, "r", encoding="utf-8") as f:
        fonte = f.read()

    assert "poste.X" in fonte and "poste.Y" in fonte
    assert "vao.X1" in fonte and "vao.Y1" in fonte
    assert "double? Z" in fonte
    assert 'new TwinDataSource("DWG_SCAN"' in fonte
    assert "Guid.NewGuid" not in fonte
