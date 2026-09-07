import os
import pytest
from croqui_ambiental_generator import (
    utm_to_latlon,
    latlon_to_tile,
    tile_to_latlon,
    escolher_zoom_otimo,
    gerar_croqui_satelite,
)


def test_utm_to_latlon():
    # Coordenadas UTM reais de Angra dos Reis / Ilha Grande (Fuso 23S)
    x = 560000.0
    y = 7440000.0
    lat, lon = utm_to_latlon(x, y, 23)
    assert -24.0 < lat < -22.0
    assert -45.0 < lon < -43.0


def test_latlon_to_tile_and_back():
    lat = -23.1234
    lon = -44.5678
    zoom = 16
    xt, yt = latlon_to_tile(lat, lon, zoom)
    assert xt > 0
    assert yt > 0

    lat_rec, lon_rec = tile_to_latlon(int(xt), int(yt), zoom)
    assert abs(lat - lat_rec) < 0.05
    assert abs(lon - lon_rec) < 0.05


def test_escolher_zoom_otimo():
    lat_min, lat_max = -23.10, -23.09
    lon_min, lon_max = -44.50, -44.49
    z = escolher_zoom_otimo(lat_min, lat_max, lon_min, lon_max, max_tiles=16)
    assert 13 <= z <= 18


def test_gerar_croqui_satelite(tmp_path):
    pontos = [
        {"id": "P01", "x": 560100.0, "y": 7440100.0},
        {"id": "P02", "x": 560150.0, "y": 7440140.0},
        {"id": "P03", "x": 560200.0, "y": 7440180.0},
    ]
    poligono = [
        (-23.140, -44.410),
        (-23.140, -44.405),
        (-23.145, -44.405),
        (-23.145, -44.410),
    ]
    dados = {
        "SOB": "A057100646",
        "MUNICIPIO": "Angra dos Reis",
        "PROJETISTA": "FABIO VARGAS"
    }

    out_file = str(tmp_path / "CROQUI_TESTE.png")
    result_path = gerar_croqui_satelite(
        pontos_utm=pontos,
        fuso_utm=23,
        output_path=out_file,
        poligonos_amb=[poligono],
        dados_projeto=dados
    )

    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 1000  # Imagem PNG gerada válida
