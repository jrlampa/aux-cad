import os
import json
import pytest
from PIL import Image
from croqui_ambiental_generator import latlon_to_utm, utm_to_latlon, download_tile
from kmz_point_layer_report import generate_cad_polygons_lisp


def test_latlon_to_utm_and_back():
    # Coordenadas reais de Angra dos Reis (Fuso 23S)
    orig_x = 560234.50
    orig_y = 7441567.80
    zone = 23

    lat, lon = utm_to_latlon(orig_x, orig_y, zone)
    recalc_x, recalc_y = latlon_to_utm(lat, lon, zone)

    # Erro de reversibilidade deve ser estritamente submétrico (< 0.05m)
    assert abs(orig_x - recalc_x) < 0.05
    assert abs(orig_y - recalc_y) < 0.05


def test_tile_cache_mechanism(tmp_path):
    cache_dir = str(tmp_path / "test_cache")
    x, y, zoom = 32800, 35700, 16

    # 1. Simula um tile em cache
    os.makedirs(cache_dir, exist_ok=True)
    fake_tile_path = os.path.join(cache_dir, f"{zoom}_{x}_{y}.png")
    test_img = Image.new("RGBA", (256, 256), (100, 150, 200, 255))
    test_img.save(fake_tile_path, "PNG")

    # 2. Chama download_tile que deve ler direto do cache
    loaded_img = download_tile(x, y, zoom, cache_dir=cache_dir)
    assert loaded_img is not None
    assert loaded_img.size == (256, 256)
    # Verifica que a cor do pixel corresponde ao tile do cache
    assert loaded_img.getpixel((10, 10)) == (100, 150, 200, 255)


def test_generate_cad_polygons_lisp(tmp_path):
    polygons = [
        {
            "name": "APP - RIO MAIOR QUE 10M",
            "category": "ÁREA DE PRESERVAÇÃO PERMANENTE (APP)",
            "layer": "AMBIENTAL_APP",
            "color": 1,
            "centroid": [560250.0, 7441580.0],
            "vertices": [
                [560200.0, 7441500.0],
                [560300.0, 7441500.0],
                [560250.0, 7441600.0]
            ]
        }
    ]

    out_lsp = str(tmp_path / "kmz_draw_polygons.lsp")
    generate_cad_polygons_lisp(polygons, out_lsp)

    assert os.path.exists(out_lsp)
    with open(out_lsp, "r", encoding="utf-8") as f:
        content = f.read()

    assert "c:KMZ_DRAW_POLYGONS" in content
    assert "AMBIENTAL_APP" in content
    assert "APP - RIO MAIOR QUE 10M" in content
    assert "vla-AddLightWeightPolyline" in content
    assert "vla-put-Closed" in content


def test_parse_kml_multigeometry_multiple_polygons():
    from kmz_point_layer_report import parse_kml_polygons_with_hierarchy

    kml_sample = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Folder>
          <name>UNIDADES DE CONSERVACAO</name>
          <Placemark>
            <name>ZONA DE AMORTECIMENTO DO PARQUE</name>
            <MultiGeometry>
              <Polygon>
                <outerBoundaryIs>
                  <LinearRing>
                    <coordinates>
                      -43.10,-22.10,0 -43.10,-22.20,0 -43.20,-22.20,0 -43.10,-22.10,0
                    </coordinates>
                  </LinearRing>
                </outerBoundaryIs>
              </Polygon>
              <Polygon>
                <outerBoundaryIs>
                  <LinearRing>
                    <coordinates>
                      -42.70,-22.30,0 -42.70,-22.35,0 -42.75,-22.35,0 -42.70,-22.30,0
                    </coordinates>
                  </LinearRing>
                </outerBoundaryIs>
              </Polygon>
            </MultiGeometry>
          </Placemark>
        </Folder>
      </Document>
    </kml>
    """

    polys = parse_kml_polygons_with_hierarchy(kml_sample)
    # Deve ler AMBOS os polígonos do MultiGeometry, sem descartar nenhum
    assert len(polys) == 2
    assert polys[0]["name"] == "ZONA DE AMORTECIMENTO DO PARQUE"
    assert polys[1]["name"] == "ZONA DE AMORTECIMENTO DO PARQUE"
    assert "bbox" in polys[0]
    assert "bbox" in polys[1]
    assert polys[0]["bbox"][0] < polys[0]["bbox"][1]

