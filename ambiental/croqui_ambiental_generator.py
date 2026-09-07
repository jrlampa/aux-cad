"""
Módulo de Geração Automática de Ortofoto / Croqui Ambiental Georreferenciado.
Baixa tiles de satélite de alta resolução (zero custo, ESRI World Imagery / OSM),
costura em uma imagem georreferenciada e plota a rede elétrica, postes numerados,
mancha da área de preservação ambiental do KMZ, escala gráfica e rosa dos ventos.
"""

import io
import math
import os
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont


def utm_to_latlon(easting: float, northing: float, zone: int, northern_hemisphere: bool = False) -> Tuple[float, float]:
    """Converte coordenadas UTM (SIRGAS 2000 / WGS84) para Latitude / Longitude (graus decimais)."""
    a = 6378137.0
    f = 1 / 298.257223563
    b = a * (1 - f)
    e_sq = (a**2 - b**2) / (a**2)
    e_prime_sq = (a**2 - b**2) / (b**2)
    k0 = 0.9996

    x = easting - 500000.0
    y = northing
    if not northern_hemisphere:
        y -= 10000000.0

    long_origin = (zone - 1) * 6 - 180 + 3
    m = y / k0
    mu = m / (a * (1 - e_sq / 4 - 3 * e_sq**2 / 64 - 5 * e_sq**3 / 256))
    e1 = (1 - math.sqrt(1 - e_sq)) / (1 + math.sqrt(1 - e_sq))

    phi1_rad = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    n1 = a / math.sqrt(1 - e_sq * math.sin(phi1_rad) ** 2)
    t1 = math.tan(phi1_rad) ** 2
    c1 = e_prime_sq * math.cos(phi1_rad) ** 2
    r1 = a * (1 - e_sq) / ((1 - e_sq * math.sin(phi1_rad) ** 2) ** 1.5)
    d = x / (n1 * k0)

    lat_rad = phi1_rad - (n1 * math.tan(phi1_rad) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e_prime_sq) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e_prime_sq - 3 * c1**2) * d**6 / 720
    )
    lat = math.degrees(lat_rad)

    lon_rad = (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e_prime_sq + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1_rad)
    lon = long_origin + math.degrees(lon_rad)

    return lat, lon


def latlon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[float, float]:
    """Converte lat/lon para coordenadas fracionárias de tile em Web Mercator (EPSG:3857)."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x_tile = (lon + 180.0) / 360.0 * n
    y_tile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x_tile, y_tile


def tile_to_latlon(x: int, y: int, zoom: int) -> Tuple[float, float]:
    """Converte índice do tile de volta para latitude e longitude do canto superior esquerdo."""
    n = 2.0 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tile_cache")


def latlon_to_utm(lat: float, lon: float, zone: int, northern_hemisphere: bool = False) -> Tuple[float, float]:
    """
    Converte coordenadas Latitude / Longitude (WGS84 / SIRGAS 2000)
    para UTM Easting (X) e Northing (Y) em metros com precisão analítica Snyder.
    """
    a = 6378137.0
    f = 1 / 298.257223563
    e_sq = (2 * f) - (f ** 2)
    e_prime_sq = e_sq / (1 - e_sq)
    k0 = 0.9996

    lat_rad = math.radians(lat)
    lon_origin = (zone - 1) * 6 - 180 + 3
    lon_origin_rad = math.radians(lon_origin)
    lon_rad = math.radians(lon)

    delta_lon = lon_rad - lon_origin_rad

    sin_phi = math.sin(lat_rad)
    cos_phi = math.cos(lat_rad)
    tan_phi = math.tan(lat_rad)

    n = a / math.sqrt(1 - e_sq * (sin_phi ** 2))
    t = tan_phi ** 2
    c = e_prime_sq * (cos_phi ** 2)
    a_val = cos_phi * delta_lon

    m = a * (
        (1 - e_sq / 4 - 3 * (e_sq ** 2) / 64 - 5 * (e_sq ** 3) / 256) * lat_rad
        - (3 * e_sq / 8 + 3 * (e_sq ** 2) / 32 + 45 * (e_sq ** 3) / 1024) * math.sin(2 * lat_rad)
        + (15 * (e_sq ** 2) / 256 + 45 * (e_sq ** 3) / 1024) * math.sin(4 * lat_rad)
        - (35 * (e_sq ** 3) / 3072) * math.sin(6 * lat_rad)
    )

    x = 500000.0 + k0 * n * (
        a_val
        + (1 - t + c) * (a_val ** 3) / 6
        + (5 - 18 * t + (t ** 2) + 72 * c - 58 * e_prime_sq) * (a_val ** 5) / 120
    )

    y = k0 * (
        m
        + n * tan_phi * (
            (a_val ** 2) / 2
            + (5 - t + 9 * c + 4 * (c ** 2)) * (a_val ** 4) / 24
            + (61 - 58 * t + (t ** 2) + 600 * c - 330 * e_prime_sq) * (a_val ** 6) / 720
        )
    )

    if not northern_hemisphere:
        y += 10000000.0

    return x, y


def download_tile(x: int, y: int, zoom: int, cache_dir: Optional[str] = DEFAULT_CACHE_DIR) -> Optional[Image.Image]:
    """
    Baixa um tile de satélite público da ESRI (World Imagery) ou fallback OSM,
    utilizando cache em disco local para respostas em <10ms e redução de tráfego.
    """
    # 1. Checa cache em disco
    if cache_dir:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"{zoom}_{x}_{y}.png")
            if os.path.exists(cache_file):
                return Image.open(cache_file).convert("RGBA")
        except Exception:
            pass

    # 2. Requisição remota (ESRI / OSM)
    urls = [
        f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}",
        f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DistribuidoraAutoCAD/1.0"}

    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                img_data = response.read()
                img = Image.open(io.BytesIO(img_data)).convert("RGBA")
                # Salva no cache local em disco
                if cache_dir:
                    try:
                        cache_file = os.path.join(cache_dir, f"{zoom}_{x}_{y}.png")
                        img.save(cache_file, "PNG")
                    except Exception:
                        pass
                return img
        except Exception:
            continue

    # 3. Fallback visual neutro caso esteja totalmente sem conexão
    fallback_tile = Image.new("RGBA", (256, 256), (240, 243, 246, 255))
    draw_f = ImageDraw.Draw(fallback_tile)
    draw_f.rectangle([0, 0, 255, 255], outline=(203, 213, 224, 255), width=1)
    return fallback_tile


def escolher_zoom_otimo(lat_min: float, lat_max: float, lon_min: float, lon_max: float, max_tiles: int = 16) -> int:
    """Calcula o melhor nível de zoom para cobrir o Bounding Box sem exceder o limite seguro de tiles."""
    for z in range(18, 13, -1):
        x1, y1 = latlon_to_tile(lat_max, lon_min, z)
        x2, y2 = latlon_to_tile(lat_min, lon_max, z)
        dx = abs(int(x2) - int(x1)) + 1
        dy = abs(int(y2) - int(y1)) + 1
        if (dx * dy) <= max_tiles:
            return z
    return 14


def gerar_croqui_satelite(
    pontos_utm: List[Dict],
    fuso_utm: int = 23,
    output_path: str = "CROQUI_AMBIENTAL.png",
    poligonos_amb: Optional[List[List[Tuple[float, float]]]] = None,
    dados_projeto: Optional[Dict] = None,
    cache_dir: Optional[str] = DEFAULT_CACHE_DIR
) -> str:
    """
    Gera a Ortofoto / Croqui de Satélite georreferenciado e salva em disco.
    - pontos_utm: Lista de dicts com 'x', 'y', 'id' (postes)
    - poligonos_amb: Lista de polígonos em Lat/Lon [(lat, lon), ...]
    - dados_projeto: Dict com 'SOB', 'MUNICIPIO', 'PROJETISTA'
    """
    if not pontos_utm:
        raise ValueError("Nenhum ponto fornecido para gerar o croqui.")

    # 1. Converte pontos para Lat/Lon e calcula Bounding Box
    pts_geo = []
    lats, lons = [], []
    for pt in pontos_utm:
        x = float(pt.get("x", 0))
        y = float(pt.get("y", 0))
        pid = str(pt.get("id", "P"))
        lat, lon = utm_to_latlon(x, y, fuso_utm)
        pts_geo.append({"lat": lat, "lon": lon, "id": pid, "x": x, "y": y})
        lats.append(lat)
        lons.append(lon)

    # Margem de conforto (padding de aprox. 150m)
    d_lat = 0.0015
    d_lon = 0.0015
    lat_min = min(lats) - d_lat
    lat_max = max(lats) + d_lat
    lon_min = min(lons) - d_lon
    lon_max = max(lons) + d_lon

    # 2. Escolhe Zoom e calcula tiles necessários
    zoom = escolher_zoom_otimo(lat_min, lat_max, lon_min, lon_max)
    x_tile_min, y_tile_min = latlon_to_tile(lat_max, lon_min, zoom)
    x_tile_max, y_tile_max = latlon_to_tile(lat_min, lon_max, zoom)

    xt_start, xt_end = int(x_tile_min), int(x_tile_max)
    yt_start, yt_end = int(y_tile_min), int(y_tile_max)

    cols = xt_end - xt_start + 1
    rows = yt_end - yt_start + 1

    tile_size = 256
    largura_px = cols * tile_size
    altura_px = rows * tile_size

    # 3. Baixa e monta a imagem base
    canvas = Image.new("RGBA", (largura_px, altura_px), (230, 235, 240, 255))
    draw_canvas = ImageDraw.Draw(canvas)

    satelite_disponivel = False
    for c, tx in enumerate(range(xt_start, xt_end + 1)):
        for r, ty in enumerate(range(yt_start, yt_end + 1)):
            tile_img = download_tile(tx, ty, zoom, cache_dir=cache_dir)
            pos_x = c * tile_size
            pos_y = r * tile_size
            if tile_img:
                canvas.paste(tile_img, (pos_x, pos_y))
                satelite_disponivel = True
            else:
                # Grade cartográfica de fundo caso offline
                draw_canvas.rectangle([pos_x, pos_y, pos_x + tile_size, pos_y + tile_size], outline="#CBD5E0", width=1)

    # 4. Função auxiliar de projeção de Lat/Lon para Pixels do Canvas
    def geo_to_px(lat: float, lon: float) -> Tuple[int, int]:
        xt, yt = latlon_to_tile(lat, lon, zoom)
        px = int((xt - xt_start) * tile_size)
        py = int((yt - yt_start) * tile_size)
        return px, py

    # 5. Desenha Polígonos Ambientais (se houver)
    overlay = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    if poligonos_amb:
        for poly in poligonos_amb:
            pts_poly_px = [geo_to_px(plat, plon) for plat, plon in poly]
            if len(pts_poly_px) >= 3:
                # Preenchimento semitransparente vermelho/laranja (área de restrição)
                overlay_draw.polygon(pts_poly_px, fill=(229, 62, 62, 75), outline=(197, 48, 48, 220))

    # 6. Desenha o Traçado da Rede Elétrica (linhas conectando os postes)
    px_coords = [geo_to_px(p["lat"], p["lon"]) for p in pts_geo]
    if len(px_coords) >= 2:
        for i in range(len(px_coords) - 1):
            p1 = px_coords[i]
            p2 = px_coords[i + 1]
            # Linha dupla de alto contraste (fundo escuro + linha ciano brilhante)
            overlay_draw.line([p1, p2], fill=(26, 32, 44, 240), width=6)
            overlay_draw.line([p1, p2], fill=(0, 245, 255, 255), width=3)

    # 7. Desenha Marcadores dos Postes com rótulos legíveis
    for i, pt in enumerate(pts_geo):
        px, py = px_coords[i]
        r = 8
        # Círculo externo escuro
        overlay_draw.ellipse([px - r - 1, py - r - 1, px + r + 1, py + r + 1], fill=(0, 0, 0, 220))
        # Círculo interno amarelo vivo
        overlay_draw.ellipse([px - r, py - r, px + r, py + r], fill=(255, 215, 0, 255), outline=(255, 255, 255, 255), width=2)

        # Rótulo do poste com caixa de fundo branca
        lbl_text = f"P{i+1:02d}" if "Bloco" in pt["id"] or "Ponto" in pt["id"] else pt["id"][:6]
        tx, ty = px + 12, py - 8
        overlay_draw.rectangle([tx - 2, ty - 2, tx + 28, ty + 14], fill=(255, 255, 255, 230), outline=(45, 55, 72, 220))
        overlay_draw.text((tx + 2, ty), lbl_text, fill=(26, 32, 44, 255))

    # Mescla overlay com o canvas principal
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    # 8. Rosa dos Ventos (Norte) no canto superior direito
    norte_x = largura_px - 55
    norte_y = 65
    draw.rectangle([norte_x - 20, norte_y - 35, norte_x + 20, norte_y + 35], fill=(255, 255, 255, 220), outline="#718096", width=1)
    # Seta Norte
    draw.polygon([(norte_x, norte_y - 30), (norte_x - 8, norte_y + 10), (norte_x, norte_y + 4)], fill=(197, 48, 48, 255))
    draw.polygon([(norte_x, norte_y - 30), (norte_x + 8, norte_y + 10), (norte_x, norte_y + 4)], fill=(74, 85, 104, 255))
    draw.text((norte_x - 4, norte_y + 12), "N", fill=(26, 32, 44, 255))

    # 9. Barra de Escala Métrica no canto inferior esquerdo
    # Metros por pixel: s = 156543.03392 * cos(lat) / (2 ^ zoom)
    lat_cen = (lat_min + lat_max) / 2.0
    m_per_px = 156543.03392 * math.cos(math.radians(lat_cen)) / (2.0 ** zoom)

    comp_alvo_m = 100.0 if m_per_px < 1.0 else 200.0
    bar_px = int(comp_alvo_m / m_per_px) if m_per_px > 0 else 100

    bx = 30
    by = altura_px - 40
    draw.rectangle([bx - 10, by - 22, bx + bar_px + 25, by + 18], fill=(255, 255, 255, 230), outline="#718096", width=1)
    draw.line([(bx, by), (bx + bar_px, by)], fill=(26, 32, 44, 255), width=4)
    draw.line([(bx, by - 5), (bx, by + 5)], fill=(26, 32, 44, 255), width=2)
    draw.line([(bx + bar_px, by - 5), (bx + bar_px, by + 5)], fill=(26, 32, 44, 255), width=2)
    draw.text((bx - 2, by - 18), "0", fill=(26, 32, 44, 255))
    draw.text((bx + bar_px - 15, by - 18), f"{int(comp_alvo_m)}m", fill=(26, 32, 44, 255))

    # 10. Carimbo do Projeto no topo
    dados = dados_projeto or {}
    sob_val = dados.get("SOB", "PROJETO AMBIENTAL")
    mun_val = dados.get("MUNICIPIO", "MUNICÍPIO NÃO INFORMADO")
    cen_x = pts_geo[0]["x"]
    cen_y = pts_geo[0]["y"]

    carimbo_h = 42
    draw.rectangle([0, 0, largura_px, carimbo_h], fill=(26, 32, 44, 235))
    tit_text = f"ORTOFOTO / CROQUI DE SITUAÇÃO AMBIENTAL - ORDEM/SOB: {sob_val}"
    sub_text = f"MUNICÍPIO: {mun_val.upper()} | COORDENADAS UTM: X={cen_x:.1f} Y={cen_y:.1f} (FUSO {fuso_utm}S) | DATA: {datetime.now().strftime('%d/%m/%Y')}"

    draw.text((15, 6), tit_text, fill=(255, 255, 255, 255))
    draw.text((15, 23), sub_text, fill=(226, 232, 240, 255))

    # Salva imagem final em PNG de alta resolução
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path
