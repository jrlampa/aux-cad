import os
import json
import zipfile
import pytest
from cad_to_kmz_exporter import utm_to_latlon, gerar_kml_content, exportar_para_kmz


def test_utm_to_latlon_kmz():
    lat, lon = utm_to_latlon(560000.0, 7440000.0, 23)
    assert -24.0 < lat < -22.0
    assert -45.0 < lon < -43.0


def test_gerar_kml_content():
    postes = [{"id": "P01", "block": "12/300", "x": 560100.0, "y": 7440100.0}]
    linhas = [{"layer": "BT_CONVENCIONAL", "coords": [[560100.0, 7440100.0], [560150.0, 7440140.0]]}]
    kml = gerar_kml_content(postes, linhas, fuso_utm=23, titulo="Teste Projeto")

    assert "<kml" in kml
    assert "P01" in kml
    assert "12/300" in kml
    assert "BT_CONVENCIONAL" in kml
    assert "<LineString>" in kml


def test_exportar_para_kmz(tmp_path):
    in_json = str(tmp_path / "cad_input.json")
    out_kmz = str(tmp_path / "PROJETO_TESTE.kmz")

    data = {
        "titulo": "SOB A057100646",
        "fuso": 23,
        "postes": [
            {"id": "P01", "block": "12/300", "x": 560100.0, "y": 7440100.0},
            {"id": "P02", "block": "12/600", "x": 560150.0, "y": 7440140.0}
        ],
        "linhas": [
            {"layer": "REDE_BT", "coords": [[560100.0, 7440100.0], [560150.0, 7440140.0]]}
        ]
    }

    with open(in_json, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    res = exportar_para_kmz(in_json, out_kmz, fuso_utm=23)
    assert os.path.exists(res)
    assert os.path.getsize(res) > 200

    # Verifica se é um arquivo ZIP válido com doc.kml dentro
    with zipfile.ZipFile(res, 'r') as zf:
        assert "doc.kml" in zf.namelist()
        kml_read = zf.read("doc.kml").decode('utf-8')
        assert "SOB A057100646" in kml_read
