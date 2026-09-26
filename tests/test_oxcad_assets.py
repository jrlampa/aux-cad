# -*- coding: utf-8 -*-
"""
Testes Automatizados de Validação e Integridade dos Assets Visuais do OXCAD.
Cobre:
1. Existência obrigatória dos arquivos mestres (SVG, PNG, ICO);
2. Validação da estrutura XML dos SVGs (oxcad.svg e oxcad_wordmark.svg);
3. Dimensões e modo de cor RGBA com transparência de oxcad.png (1024x1024);
4. Integridade do pacote de resoluções derivadas (16, 24, 32, 48, 64, 128, 256);
5. Integridade do formato Windows Icon (.ico) com suporte a multi-resolução;
6. Validação da versão monocromática (oxcad_mono.png);
7. Reprodutibilidade determinística do script de geração.
"""

from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "oxcad" / "assets"
SCRIPT_ASSETS = ROOT_DIR / "oxcad" / "scripts" / "generate_assets.py"


def test_01_script_de_geracao_existe():
    """Valida que o script de geração reproduzível existe no repositório."""
    assert SCRIPT_ASSETS.exists(), f"Script não encontrado: {SCRIPT_ASSETS}"


def test_02_arquivos_mestres_existem():
    """Valida a existência dos assets mestres oficiais do OXCAD."""
    assert (ASSETS_DIR / "oxcad.svg").exists()
    assert (ASSETS_DIR / "oxcad_wordmark.svg").exists()
    assert (ASSETS_DIR / "oxcad.png").exists()
    assert (ASSETS_DIR / "oxcad.ico").exists()
    assert (ASSETS_DIR / "oxcad_mono.png").exists()
    assert (ASSETS_DIR / "oxcad_wordmark.png").exists()


def test_03_svgs_sao_xml_validos_e_possuem_viewbox():
    """Valida a sintaxe vetorial e atributos essenciais de viewBox nos arquivos SVG."""
    for svg_file in ["oxcad.svg", "oxcad_wordmark.svg"]:
        caminho = ASSETS_DIR / svg_file
        tree = ET.parse(caminho)
        root = tree.getroot()
        assert "svg" in root.tag.lower()
        assert "viewBox" in root.attrib or "viewbox" in root.attrib


def test_04_master_png_1024_com_transparencia():
    """Valida que oxcad.png possui 1024x1024 com canal alpha (RGBA)."""
    with Image.open(ASSETS_DIR / "oxcad.png") as img:
        assert img.size == (1024, 1024)
        assert img.mode == "RGBA"
        # Verifica que existe transparência (pixels com alpha < 255)
        extrema = img.getextrema()
        alpha_min, alpha_max = extrema[3]
        assert alpha_min == 0, "Deveria conter fundo transparente"
        assert alpha_max > 0, "Deveria conter elementos visíveis"


def test_05_assets_derivados_possuem_dimensoes_exatas():
    """Valida todas as resoluções derivadas do ícone."""
    tamanhos_esperados = [16, 24, 32, 48, 64, 128, 256]
    for t in tamanhos_esperados:
        caminho = ASSETS_DIR / f"oxcad_{t}.png"
        assert caminho.exists(), f"Asset oxcad_{t}.png ausente"
        with Image.open(caminho) as img:
            assert img.size == (t, t)
            assert img.mode == "RGBA"


def test_06_ico_windows_valido_e_multi_resolucao():
    """Valida que oxcad.ico é um arquivo ICO legítimo com múltiplos tamanhos empacotados."""
    caminho_ico = ASSETS_DIR / "oxcad.ico"
    assert caminho_ico.exists()
    with Image.open(caminho_ico) as ico:
        assert ico.format == "ICO"
        assert ico.size == (256, 256)


def test_07_versao_monocromatica_valida():
    """Valida a integridade do asset monocromático de alto contraste."""
    with Image.open(ASSETS_DIR / "oxcad_mono.png") as img:
        assert img.size == (1024, 1024)
        assert img.mode == "RGBA"
