"""
Exportador de Geometrias do AutoCAD para Google Earth (KMZ).
Converte postes (pontos/blocos) e redes elétricas (linhas/polilinhas) em UTM
para coordenadas geodésicas WGS84, estruturando KML com estilos visuais e empacotando em .kmz.
"""

import json
import math
import os
import sys

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

import zipfile
from datetime import datetime
from typing import Dict, List, Tuple


def utm_to_latlon(easting: float, northing: float, zone: int, northern_hemisphere: bool = False) -> Tuple[float, float]:
    """Converte UTM (SIRGAS 2000 / WGS84) para Latitude e Longitude em graus decimais."""
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


def gerar_kml_content(postes: List[Dict], linhas: List[Dict], fuso_utm: int = 23, titulo: str = "Projeto de Rede Elétrica") -> str:
    """Gera o código XML KML completo com pastas organizadas e estilização de engenharia."""
    kml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '  <Document>',
        f'    <name>{titulo}</name>',
        '    <description>Exportado automaticamente do AutoCAD pelo AUX CAD</description>',
        '    <!-- Estilo para Postes -->',
        '    <Style id="estilo_poste">',
        '      <IconStyle>',
        '        <color>ff00ffff</color>',  # Amarelo
        '        <scale>1.1</scale>',
        '        <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>',
        '      </IconStyle>',
        '      <LabelStyle><scale>0.85</scale></LabelStyle>',
        '    </Style>',
        '    <!-- Estilo para Redes Elétricas (Linha Ciano) -->',
        '    <Style id="estilo_rede">',
        '      <LineStyle>',
        '        <color>ffffff00</color>',  # Ciano/Azul claro (AABBGGRR)
        '        <width>3.5</width>',
        '      </LineStyle>',
        '    </Style>',
        '    <!-- Pasta de Postes e Estruturas -->',
        '    <Folder>',
        '      <name>Postes e Estruturas</name>'
    ]

    for p in postes:
        pid = str(p.get("id", "Poste"))
        blk = str(p.get("block", "Estrutura"))
        x = float(p.get("x", 0))
        y = float(p.get("y", 0))
        lat, lon = utm_to_latlon(x, y, fuso_utm)

        desc_html = (
            f"<![CDATA["
            f"<b>Poste/Nó:</b> {pid}<br/>"
            f"<b>Tipo/Bloco:</b> {blk}<br/>"
            f"<b>UTM X:</b> {x:.2f}<br/>"
            f"<b>UTM Y:</b> {y:.2f}<br/>"
            f"<b>Fuso:</b> {fuso_utm}S<br/>"
            f"<b>Lat/Lon:</b> {lat:.6f}, {lon:.6f}<br/>"
            f"]]>"
        )

        kml_parts.append('      <Placemark>')
        kml_parts.append(f'        <name>{pid}</name>')
        kml_parts.append(f'        <description>{desc_html}</description>')
        kml_parts.append('        <styleUrl>#estilo_poste</styleUrl>')
        kml_parts.append('        <Point>')
        kml_parts.append(f'          <coordinates>{lon:.7f},{lat:.7f},0</coordinates>')
        kml_parts.append('        </Point>')
        kml_parts.append('      </Placemark>')

    kml_parts.append('    </Folder>')

    # Pasta de Linhas e Redes
    kml_parts.append('    <Folder>')
    kml_parts.append('      <name>Redes e Condutores</name>')

    for idx, l in enumerate(linhas):
        layer = str(l.get("layer", "Rede"))
        coords_utm = l.get("coords", [])
        if len(coords_utm) < 2:
            continue

        coords_kml_str = []
        for pt in coords_utm:
            px = float(pt[0])
            py = float(pt[1])
            plat, plon = utm_to_latlon(px, py, fuso_utm)
            coords_kml_str.append(f"{plon:.7f},{plat:.7f},0")

        kml_parts.append('      <Placemark>')
        kml_parts.append(f'        <name>{layer} - Trecho {idx+1}</name>')
        kml_parts.append('        <styleUrl>#estilo_rede</styleUrl>')
        kml_parts.append('        <LineString>')
        kml_parts.append('          <tessellate>1</tessellate>')
        kml_parts.append(f'          <coordinates>{" ".join(coords_kml_str)}</coordinates>')
        kml_parts.append('        </LineString>')
        kml_parts.append('      </Placemark>')

    kml_parts.append('    </Folder>')
    kml_parts.append('  </Document>')
    kml_parts.append('</kml>')

    return "\n".join(kml_parts)


def exportar_para_kmz(input_json_path: str, output_kmz_path: str, fuso_utm: int = 23) -> str:
    """Lê o JSON gerado pelo AutoCAD e empacota o arquivo KMZ georreferenciado."""
    if not os.path.exists(input_json_path):
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_json_path}")

    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    postes = data.get("postes", [])
    linhas = data.get("linhas", [])
    titulo = data.get("titulo", "Projeto de Rede Elétrica")
    fuso = int(data.get("fuso", fuso_utm))

    kml_text = gerar_kml_content(postes, linhas, fuso_utm=fuso, titulo=titulo)

    # Criação do arquivo KMZ (KML compactado)
    os.makedirs(os.path.dirname(os.path.abspath(output_kmz_path)), exist_ok=True)
    with zipfile.ZipFile(output_kmz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('doc.kml', kml_text.encode('utf-8'))

    return output_kmz_path


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python cad_to_kmz_exporter.py <input_json> <output_kmz> [fuso]")
        sys.exit(1)

    in_json = sys.argv[1]
    out_kmz = sys.argv[2]
    fuso_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 23

    res_path = exportar_para_kmz(in_json, out_kmz, fuso_utm=fuso_arg)
    print(f"[SUCESSO] KMZ gerado em: {res_path}")

    # Abre o Google Earth se solicitado
    try:
        os.startfile(res_path)
    except Exception:
        pass
