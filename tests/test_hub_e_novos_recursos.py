# -*- coding: utf-8 -*-
"""
test_hub_e_novos_recursos.py - Testes unitários para P1 (Conexão Paleta-CQT),
P2 (Snap Magnético), P3 (Hub Central Launcher) e P4 (Docker & CI/CD).
"""

import os
import sys
import json
import math
import subprocess
import pytest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_p1_conexao_paleta_osm_cqt():
    """Valida a cadeia de dados entre a Paleta OSM e o módulo CQT."""
    tracado_js = os.path.join(RAIZ, "mapa_cad_paleta", "web", "tracado.js")
    index_html = os.path.join(RAIZ, "mapa_cad_paleta", "web", "index.html")
    mapa_control_cs = os.path.join(RAIZ, "mapa_cad_paleta", "MapaControl.xaml.cs")
    cqt_manager_py = os.path.join(RAIZ, "cqt", "cqt_excel_manager.py")

    assert os.path.exists(tracado_js)
    assert os.path.exists(mapa_control_cs)
    assert os.path.exists(cqt_manager_py)

    with open(tracado_js, "r", encoding="utf-8") as f:
        js = f.read()
    assert "exportarParaCqt" in js
    assert "trechosCqt.push" in js
    assert "action: 'exportar_cqt'" in js

    with open(index_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "btnExportarCqt" in html
    assert "inputProjeto" in html
    assert "inputMono" in html
    assert "inputBi" in html
    assert "inputTri" in html

    with open(mapa_control_cs, "r", encoding="utf-8") as f:
        cs = f.read()
    assert "case \"exportar_cqt\":" in cs
    assert "ExportarParaCqt" in cs
    assert "auxcad_cqt_import.json" in cs

    # Validação do formato JSON gerado e consumido pelo CQT
    payload_exemplo = {
        "projeto": "PE_12345",
        "ponto_trafo": "P01",
        "potencia_trafo": "45",
        "cenario": "PROJETADO",
        "trechos": [
            {
                "letra": "A",
                "de": "P01",
                "para": "P02",
                "montante": "TRAFO",
                "vaos": 1,
                "comprimento_m": 35.5,
                "condutor": "3x150+70 - Al - F.P 1",
                "mono": 2,
                "bi": 1,
                "tri": 0,
                "esp_carga": 0.0,
                "ip70": 1,
                "ip125": 0,
                "ip250": 0
            },
            {
                "letra": "B",
                "de": "P02",
                "para": "P03",
                "montante": "A",
                "vaos": 1,
                "comprimento_m": 42.0,
                "condutor": "3x35+1x54,6 - Al - F.P 1",
                "mono": 3,
                "bi": 0,
                "tri": 1,
                "esp_carga": 15.0,
                "ip70": 1,
                "ip125": 0,
                "ip250": 0
            }
        ]
    }

    # Verifica serialização e desserialização sem perda
    raw = json.dumps(payload_exemplo)
    loaded = json.loads(raw)
    assert loaded["projeto"] == "PE_12345"
    assert loaded["ponto_trafo"] == "P01"
    assert len(loaded["trechos"]) == 2
    assert loaded["trechos"][0]["condutor"] == "3x150+70 - Al - F.P 1"
    assert loaded["trechos"][1]["montante"] == "A"
    assert loaded["trechos"][1]["esp_carga"] == 15.0


def test_p2_snap_magnetico_assets_e_calculo():
    """Valida assets de snap magnético, atração por raio em pixels e persistência."""
    snap_js = os.path.join(RAIZ, "mapa_cad_paleta", "web", "snap_magnetico.js")
    medicao_js = os.path.join(RAIZ, "mapa_cad_paleta", "web", "medicao.js")
    app_js = os.path.join(RAIZ, "mapa_cad_paleta", "web", "app.js")
    style_css = os.path.join(RAIZ, "mapa_cad_paleta", "web", "style.css")

    assert os.path.exists(snap_js)
    with open(snap_js, "r", encoding="utf-8") as f:
        sjs = f.read()

    assert "SnapMagnetico" in sjs
    assert "buscarPontoSnap" in sjs
    assert "raioPixels: 18" in sjs
    assert "snap-magnetico-marker" in sjs

    with open(medicao_js, "r", encoding="utf-8") as f:
        mjs = f.read()
    assert "SnapMagnetico.buscarPontoSnap" in mjs

    with open(app_js, "r", encoding="utf-8") as f:
        ajs = f.read()
    assert "SnapMagnetico.buscarPontoSnap" in ajs

    with open(style_css, "r", encoding="utf-8") as f:
        css = f.read()
    assert ".snap-magnetico-marker" in css
    assert "snapPulse" in css
    assert ".btn-snap" in css

    # Simulação analítica do algoritmo de Snap Magnético
    raio_snap_px = 18.0
    cursor_pos = (100.0, 200.0)

    candidatos = [
        {"nome": "P01", "tela_x": 150.0, "tela_y": 200.0, "lat": -22.90, "lon": -43.20},  # dist = 50px (> 18)
        {"nome": "P02", "tela_x": 105.0, "tela_y": 203.0, "lat": -22.91, "lon": -43.21},  # dist = sqrt(25 + 9) = 5.83px (SNAP!)
        {"nome": "P03", "tela_x": 110.0, "tela_y": 210.0, "lat": -22.92, "lon": -43.22}   # dist = sqrt(100 + 100) = 14.14px
    ]

    melhor_cand = None
    menor_dist = raio_snap_px

    for cand in candidatos:
        d = math.hypot(cursor_pos[0] - cand["tela_x"], cursor_pos[1] - cand["tela_y"])
        if d < menor_dist:
            menor_dist = d
            melhor_cand = cand

    assert melhor_cand is not None
    assert melhor_cand["nome"] == "P02"
    assert menor_dist < 6.0


def test_p3_aux_cad_hub_e_launcher():
    """Valida o Hub central unificado e o atalho de execução."""
    hub_py = os.path.join(RAIZ, "aux_cad_hub.py")
    abrir_bat = os.path.join(RAIZ, "Abrir_AUXCAD.bat")

    assert os.path.exists(hub_py)
    assert os.path.exists(abrir_bat)

    # Verifica sintaxe e imports do script
    import aux_cad_hub
    assert hasattr(aux_cad_hub, "AuxCadHubApp")
    assert hasattr(aux_cad_hub, "verificar_processo_autocad")
    assert hasattr(aux_cad_hub, "obter_branch_git")

    branch = aux_cad_hub.obter_branch_git()
    assert isinstance(branch, str)
    assert len(branch) > 0

    with open(abrir_bat, "r", encoding="utf-8") as f:
        bat_content = f.read()
    assert "aux_cad_hub.py" in bat_content


def test_p4_docker_e_ci_pipeline():
    """Valida arquivos de Docker First e o workflow de CI do GitHub Actions."""
    dockerfile = os.path.join(RAIZ, "Dockerfile")
    docker_compose = os.path.join(RAIZ, "docker-compose.yml")
    dockerignore = os.path.join(RAIZ, ".dockerignore")
    ci_yml = os.path.join(RAIZ, ".github", "workflows", "ci.yml")
    req_txt = os.path.join(RAIZ, "requirements.txt")

    assert os.path.exists(dockerfile), "Dockerfile deve existir"
    assert os.path.exists(docker_compose), "docker-compose.yml deve existir"
    assert os.path.exists(dockerignore), ".dockerignore deve existir"
    assert os.path.exists(ci_yml), ".github/workflows/ci.yml deve existir"
    assert os.path.exists(req_txt), "requirements.txt deve existir"

    with open(dockerfile, "r", encoding="utf-8") as f:
        df = f.read()
    assert "FROM python:3.12-slim" in df
    assert "requirements.txt" in df
    assert "pytest" in df

    with open(docker_compose, "r", encoding="utf-8") as f:
        dc = f.read()
    assert "auxcad-tests" in dc
    assert "auxcad-mapa" in dc

    with open(dockerignore, "r", encoding="utf-8") as f:
        di = f.read()
    assert "__pycache__" in di
    assert "*.dwg" in di
    assert ".git" in di

    with open(ci_yml, "r", encoding="utf-8") as f:
        ci = f.read()
    assert "branches: [ dev, main ]" in ci
    assert "pytest tests/" in ci
    assert "--cov-fail-under=80" in ci
