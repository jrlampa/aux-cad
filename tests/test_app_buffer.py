import os
import math
import zipfile
import pytest

from ambiental.app_buffer_generator import (
    utm_buffer_point,
    utm_buffer_linestring,
    is_point_in_polygon,
    parse_kml_hydrography,
    check_postes_in_hydro_app,
    generate_cad_buffers_lisp,
)


def test_utm_buffer_point_nascente():
    cx, cy = 560000.0, 7440000.0
    radius = 50.0  # Lei 12.651 raio de 50m para nascentes
    poly = utm_buffer_point(cx, cy, radius, num_points=36)

    assert poly is not None
    assert len(poly) == 36

    # Cada vértice deve estar à distância do raio (tolerância para arredondamento a 2 casas decimais)
    for x, y in poly:
        dist = math.hypot(x - cx, y - cy)
        assert abs(dist - radius) < 0.05

    # O centro deve estar dentro do polígono
    assert is_point_in_polygon((cx, cy), poly) is True
    # Ponto a 49m dentro
    assert is_point_in_polygon((cx + 49.0, cy), poly) is True
    # Ponto a 52m fora
    assert is_point_in_polygon((cx + 52.0, cy), poly) is False


def test_utm_buffer_linestring_straight():
    # Linha reta de 100m no eixo X
    coords = [(500000.0, 7000000.0), (500100.0, 7000000.0)]
    buf_dist = 30.0  # 30m Lei 12.651 para rios <10m
    poly = utm_buffer_linestring(coords, buf_dist)

    assert poly is not None
    assert len(poly) >= 4

    # Ponto no meio da linha deve estar dentro do buffer
    mid_x, mid_y = 500050.0, 7000000.0
    assert is_point_in_polygon((mid_x, mid_y), poly) is True

    # Ponto a 20m perpendicular deve estar dentro
    assert is_point_in_polygon((mid_x, mid_y + 20.0), poly) is True
    assert is_point_in_polygon((mid_x, mid_y - 20.0), poly) is True

    # Ponto a 35m perpendicular deve estar fora
    assert is_point_in_polygon((mid_x, mid_y + 35.0), poly) is False
    assert is_point_in_polygon((mid_x, mid_y - 35.0), poly) is False

    # Pontos além do início e fim (+ tampa)
    assert is_point_in_polygon((500000.0 - 20.0, 7000000.0), poly) is True
    assert is_point_in_polygon((500000.0 - 35.0, 7000000.0), poly) is False


def test_check_postes_in_hydro_app():
    # Cria feições hídricas com polígonos de APP (um rio e uma nascente)
    rio_poly = utm_buffer_linestring([(1000.0, 2000.0), (1200.0, 2000.0)], 30.0)
    nasc_poly = utm_buffer_point(1500.0, 2000.0, 50.0)

    hydro_features = [
        {
            "name": "Rio Guandu (Trecho 1)",
            "type": "RIO",
            "buffer_m": 30.0,
            "checklist_row": 24,
            "app_polygon": rio_poly,
        },
        {
            "name": "Nascente do Cedro",
            "type": "NASCENTE",
            "buffer_m": 50.0,
            "checklist_row": 33,
            "app_polygon": nasc_poly,
        },
    ]

    postes = [
        {"id": "P1", "x": 1100.0, "y": 2010.0},  # Dentro do rio
        {"id": "P2", "x": 1500.0, "y": 2020.0},  # Dentro da nascente
        {"id": "P3", "x": 1100.0, "y": 2060.0},  # Fora de ambos
    ]

    audit_results, infracoes = check_postes_in_hydro_app(postes, hydro_features)

    assert len(audit_results) == 3
    assert len(infracoes) == 2

    infracoes_postes = [inf["poste_id"] for inf in infracoes]
    assert "P1" in infracoes_postes
    assert "P2" in infracoes_postes
    assert "P3" not in infracoes_postes

    res_dict = {r["id"]: r for r in audit_results}
    assert res_dict["P1"]["em_app"] is True
    assert res_dict["P2"]["em_app"] is True
    assert res_dict["P3"]["em_app"] is False


def test_parse_kml_hydrography_kmz(tmp_path):
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Folder>
          <name>Hidrografia</name>
          <Placemark>
            <name>Córrego das Pedras</name>
            <LineString>
              <coordinates>
                -44.12345,-22.98765,0 -44.12456,-22.98876,0
              </coordinates>
            </LineString>
          </Placemark>
          <Placemark>
            <name>Nascente 01</name>
            <Point>
              <coordinates>-44.12500,-22.98900,0</coordinates>
            </Point>
          </Placemark>
        </Folder>
      </Document>
    </kml>
    """
    features = parse_kml_hydrography(kml_content, default_zone=23)
    assert len(features) == 2

    feicoes_dict = {f["name"]: f for f in features}
    assert "Córrego das Pedras" in feicoes_dict
    assert feicoes_dict["Córrego das Pedras"]["type"] == "RIO"
    assert feicoes_dict["Córrego das Pedras"]["checklist_row"] == 24

    assert "Nascente 01" in feicoes_dict
    assert feicoes_dict["Nascente 01"]["type"] == "NASCENTE"
    assert feicoes_dict["Nascente 01"]["checklist_row"] == 33


def test_generate_cad_buffers_lisp(tmp_path):
    poly_vertices = [
        [560000.0, 7440000.0],
        [560100.0, 7440000.0],
        [560100.0, 7440050.0],
        [560000.0, 7440050.0],
    ]
    features = [
        {
            "name": "APP - Córrego do Engenho",
            "type": "RIO",
            "buffer_m": 30.0,
            "checklist_row": 24,
            "app_polygon": poly_vertices,
        }
    ]
    infracoes = [
        {
            "poste_id": "P01",
            "x": 560050.0,
            "y": 7440020.0,
            "tipo_app": "RIO",
            "nome_corpo": "Córrego do Engenho",
            "faixa_app_m": 30.0,
            "checklist_row": 24,
        }
    ]

    out_lisp = str(tmp_path / "test_draw_buffers.lsp")
    generate_cad_buffers_lisp(features, infracoes, out_lisp)

    assert os.path.exists(out_lisp)
    with open(out_lisp, "r", encoding="utf-8") as f:
        content = f.read()

    assert "vla-AddLightWeightPolyline" in content
    assert "AMBIENTAL_APP_HIDRICA" in content
    assert "AMBIENTAL_APP_ALERTA" in content
    assert "ALERTA: P01 EM APP" in content
    assert "Córrego do Engenho" in content


def test_utm_buffer_linestring_corner():
    # Linha em 'L' (virada em 90 graus)
    coords = [(1000.0, 1000.0), (1050.0, 1000.0), (1050.0, 1050.0)]
    poly = utm_buffer_linestring(coords, buffer_dist=20.0)
    assert len(poly) > 6

    # Vértice de curva deve estar dentro do buffer
    assert is_point_in_polygon((1050.0, 1000.0), poly) is True
    # Ponto no meio do segundo trecho
    assert is_point_in_polygon((1050.0, 1025.0), poly) is True


def test_process_app_buffers_kmz_and_cad_json(tmp_path):
    from ambiental.app_buffer_generator import process_app_buffers, main

    # 1. KMZ
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Folder>
          <name>Hidrografia</name>
          <Placemark>
            <name>Rio Teste</name>
            <LineString>
              <coordinates>-44.12345,-22.98765,0 -44.12456,-22.98876,0</coordinates>
            </LineString>
          </Placemark>
        </Folder>
      </Document>
    </kml>"""
    kmz_file = str(tmp_path / "teste.kmz")
    with zipfile.ZipFile(kmz_file, "w") as z:
        z.writestr("doc.kml", kml_content.encode("utf-8"))

    # Postes JSON
    import json
    postes_json = str(tmp_path / "postes.json")
    with open(postes_json, "w", encoding="utf-8") as f:
        json.dump([{"id": "POSTE_1", "x": 589800.0, "y": 7457400.0}], f)

    out_json = str(tmp_path / "res.json")
    out_boxes = str(tmp_path / "kmz_boxes.txt")
    out_lsp = str(tmp_path / "draw.lsp")

    res = process_app_buffers(
        input_source=kmz_file,
        postes_json_path=postes_json,
        out_json_path=out_json,
        out_boxes_path=out_boxes,
        out_lsp_path=out_lsp,
        buffer_dist_m=30.0,
        fuso_utm=23
    )

    assert res["total_corpos_hidricos"] == 1
    assert os.path.exists(out_json)
    assert os.path.exists(out_lsp)

    # 2. CAD JSON
    cad_json = str(tmp_path / "cad_hydro.json")
    with open(cad_json, "w", encoding="utf-8") as f:
        json.dump([
            {
                "type": "POINT",
                "name": "Nascente DWG",
                "coordinates": [[589800.0, 7457400.0]],
                "buffer_m": 50.0
            },
            {
                "type": "LINE",
                "name": "Córrego DWG",
                "coordinates": [[589800.0, 7457400.0], [589900.0, 7457400.0]],
                "buffer_m": 30.0
            }
        ], f)

    cad_res = process_app_buffers(
        input_source=cad_json,
        postes_json_path=postes_json,
        out_json_path=out_json,
        out_boxes_path=out_boxes,
        out_lsp_path=out_lsp
    )
    assert cad_res["total_corpos_hidricos"] == 2
    assert len(cad_res["postes_em_app"]) >= 1

    # 3. Teste CLI main()
    ret = main([
        "--cad-json", cad_json,
        "--postes-json", postes_json,
        "--out-json", out_json,
        "--out-boxes", out_boxes,
        "--out-lisp", out_lsp,
        "--out-report", str(tmp_path / "rep.txt")
    ])
    assert ret == 0

