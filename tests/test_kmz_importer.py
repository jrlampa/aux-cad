"""
Testes Unitários para o Módulo de Importação de Postes KMZ/KML (topografia/kmz_pontos_importer.py).
"""

import os
import tempfile
import zipfile
import pytest

from topografia.kmz_pontos_importer import (
    PosteKMZ,
    latlon_to_utm,
    detectar_fuso_utm,
    sanitizar_descricao,
    extrair_postes_kml,
    ler_arquivo_kmz_ou_kml,
    gerar_script_lisp_postes
)


def test_latlon_to_utm_conversao_precisa():
    """Testa a conversão analítica de lat/lon WGS84 para coordenadas UTM Fuso 23S."""
    # Coordenada no Rio de Janeiro
    lat = -22.9068
    lon = -43.1729
    zone = 23

    x, y = latlon_to_utm(lat, lon, zone, northern_hemisphere=False)

    # Verificações de ordem de grandeza e precisão
    assert 687000 < x < 688000
    assert 7465000 < y < 7466000
    assert detectar_fuso_utm(lon) == 23


def test_sanitizar_descricao_html_e_quebras():
    """Testa a limpeza de tags HTML do Google Earth e extração das linhas técnicas."""
    desc_html = (
        "11/M<br>"
        "<div>N1</div>"
        "<p>S1</p>"
        "<span>ESF. RESULTANTE 450 daN</span>&nbsp;"
    )
    linhas = sanitizar_descricao(desc_html)

    assert len(linhas) == 4
    assert linhas[0] == "11/M"
    assert linhas[1] == "N1"
    assert linhas[2] == "S1"
    assert "ESF. RESULTANTE" in linhas[3]


def test_extrair_postes_kml_multiplos_placemarks():
    """Testa o parsing de arquivo KML com múltiplos marcadores."""
    kml_conteudo = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <name>05</name>
          <description>11/M\nN1\nS1\nESF. RESULTANTE</description>
          <Point>
            <coordinates>-43.1729,-22.9068,0</coordinates>
          </Point>
        </Placemark>
        <Placemark>
          <name>06</name>
          <description>12/300&lt;br&gt;CE1&lt;br&gt;B1</description>
          <Point>
            <coordinates>-43.1735,-22.9075,0</coordinates>
          </Point>
        </Placemark>
      </Document>
    </kml>
    """
    postes = extrair_postes_kml(kml_conteudo, fuso_padrao=23)

    assert len(postes) == 2

    p1 = postes[0]
    assert p1.nome == "05"
    assert p1.descricao_linhas == ["11/M", "N1", "S1", "ESF. RESULTANTE"]
    assert p1.fuso == 23
    assert p1.x_utm > 600000
    assert p1.y_utm > 7000000

    p2 = postes[1]
    assert p2.nome == "06"
    assert p2.descricao_linhas == ["12/300", "CE1", "B1"]


def test_ler_arquivo_kmz_comprimido():
    """Testa a leitura direta de arquivo .kmz (zip) em disco."""
    kml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <name>10</name>
          <description>11/600\nN3</description>
          <Point>
            <coordinates>-43.2000,-22.9000,0</coordinates>
          </Point>
        </Placemark>
      </Document>
    </kml>
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        kmz_path = os.path.join(tmpdir, "rede_teste.kmz")
        with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("doc.kml", kml_data)

        postes = ler_arquivo_kmz_ou_kml(kmz_path, fuso_padrao=23)
        assert len(postes) == 1
        assert postes[0].nome == "10"
        assert postes[0].descricao_linhas == ["11/600", "N3"]


def test_gerar_script_lisp_postes_conteudo():
    """Testa a geração da rotina AutoLISP garantindo presença de blocos e layers."""
    postes = [
        PosteKMZ(
            nome="05",
            descricao_linhas=["11/M", "N1", "S1", "ESF. RESULTANTE"],
            lon=-43.1729,
            lat=-22.9068,
            x_utm=687483.123,
            y_utm=7465384.456,
            fuso=23
        )
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_lsp = os.path.join(tmpdir, "teste_postes.lsp")
        gerar_script_lisp_postes(postes, out_lsp)

        assert os.path.exists(out_lsp)
        with open(out_lsp, "r", encoding="utf-8") as f:
            conteudo = f.read()

        # Verifica layers criados
        assert "POSTES_SIMBOLO" in conteudo
        assert "POSTES_NUMERO" in conteudo
        assert "POSTES_DESCRICAO" in conteudo

        # Verifica referências aos blocos solicitados
        assert '"POSTE_"' in conteudo
        assert '"PONTO"' in conteudo

        # Verifica nome e descrição no script LISP
        assert '"05"' in conteudo
        assert "11/M\\PN1\\PS1\\PESF. RESULTANTE" in conteudo
        assert "c:EXEC_IMPORT_KMZ_POSTES" in conteudo


def test_ler_arquivo_kml_direto_em_disco():
    """Testa leitura de arquivo .kml direto no sistema de arquivos."""
    kml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <Point>
            <coordinates>-43.2000,-22.9000,0</coordinates>
          </Point>
        </Placemark>
      </Document>
    </kml>
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        kml_path = os.path.join(tmpdir, "pontos.kml")
        with open(kml_path, "w", encoding="utf-8") as f:
            f.write(kml_data)

        postes = ler_arquivo_kmz_ou_kml(kml_path)
        assert len(postes) == 1
        assert postes[0].nome == "01"  # Nome gerado automaticamente


def test_ler_arquivo_inexistente_ou_invalido():
    """Testa lançamento de exceção para arquivo inexistente ou sem KML."""
    with pytest.raises(FileNotFoundError):
        ler_arquivo_kmz_ou_kml("caminho_inexistente_123.kmz")

    with tempfile.TemporaryDirectory() as tmpdir:
        kmz_vazio = os.path.join(tmpdir, "vazio.kmz")
        with zipfile.ZipFile(kmz_vazio, "w") as z:
            z.writestr("outro.txt", "conteudo")

        with pytest.raises(ValueError):
            ler_arquivo_kmz_ou_kml(kmz_vazio)


def test_cli_main_execucao(monkeypatch, capsys):
    """Testa a execução CLI main() do módulo."""
    from topografia.kmz_pontos_importer import main

    kml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <name>P01</name>
          <description>11/300</description>
          <Point>
            <coordinates>-43.1729,-22.9068,0</coordinates>
          </Point>
        </Placemark>
      </Document>
    </kml>
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        kml_path = os.path.join(tmpdir, "cli_teste.kml")
        out_lsp = os.path.join(tmpdir, "cli_saida.lsp")
        with open(kml_path, "w", encoding="utf-8") as f:
            f.write(kml_data)

        monkeypatch.setattr(
            "sys.argv",
            ["kmz_pontos_importer.py", kml_path, "--fuso", "23", "--saida", out_lsp, "--json"]
        )

        main()
        captured = capsys.readouterr()
        assert "[OK] 1 marcadores lidos com sucesso" in captured.out
        assert "[OK] Rotina AutoLISP gerada com sucesso" in captured.out
        assert os.path.exists(out_lsp)

