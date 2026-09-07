import json
import math
import os
import sys

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Optional, Tuple

# ============================================================
# Conversão UTM (SIRGAS 2000 / WGS84) para Latitude / Longitude
# ============================================================

def utm_to_latlon(easting: float, northing: float, zone: int, northern_hemisphere: bool = False) -> Tuple[float, float]:
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

    return lon, lat


# ============================================================
# Leitura e Parse de KMZ / KML com Hierarquia de Pastas
# ============================================================

def extract_kml_from_kmz(kmz_path: str) -> str:
    with zipfile.ZipFile(kmz_path, 'r') as z:
        names = [n for n in z.namelist() if n.lower().endswith('.kml')]
        if not names:
            raise FileNotFoundError('Nenhum KML encontrado dentro do arquivo KMZ.')
        return z.read(names[0]).decode('utf-8', errors='replace')


def _strip_ns(tag: str) -> str:
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def parse_kml_polygons_with_hierarchy(kml_text: str) -> List[Dict]:
    root = ET.fromstring(kml_text)
    polygons = []

    def walk(node, current_folder=""):
        tag = _strip_ns(node.tag)
        folder = current_folder

        if tag == 'Folder':
            for child in node:
                if _strip_ns(child.tag) == 'name' and child.text:
                    folder = child.text.strip()
                    break

        elif tag == 'Placemark':
            p_name = ""
            for child in node:
                if _strip_ns(child.tag) == 'name' and child.text:
                    p_name = child.text.strip()
                    break

            # Varre TODOS os Polygons do Placemark (suporte total a MultiGeometry)
            for poly in node.iter():
                if _strip_ns(poly.tag) == 'Polygon':
                    outer_ring = None
                    # Prioriza outerBoundaryIs para fronteira externa
                    for outer in poly.iter():
                        if _strip_ns(outer.tag) == 'outerBoundaryIs':
                            for ring in outer.iter():
                                if _strip_ns(ring.tag) == 'coordinates' and ring.text:
                                    outer_ring = ring.text.strip()
                                    break
                            if outer_ring:
                                break

                    # Fallback caso não haja outerBoundaryIs explícito
                    if not outer_ring:
                        for ring in poly.iter():
                            if _strip_ns(ring.tag) == 'coordinates' and ring.text:
                                outer_ring = ring.text.strip()
                                break

                    if outer_ring:
                        coords = []
                        for token in outer_ring.replace('\n', ' ').replace('\r', ' ').split():
                            parts = token.strip().split(',')
                            if len(parts) >= 2:
                                try:
                                    lon = float(parts[0])
                                    lat = float(parts[1])
                                    coords.append((lon, lat))
                                except ValueError:
                                    continue
                        if len(coords) >= 3:
                            polygons.append({
                                'folder': folder,
                                'name': p_name,
                                'coordinates': coords,
                                'bbox': (
                                    min(c[0] for c in coords),
                                    max(c[0] for c in coords),
                                    min(c[1] for c in coords),
                                    max(c[1] for c in coords)
                                )
                            })

        for child in node:
            walk(child, folder)

    walk(root, "")
    return polygons


# ============================================================
# Algoritmo de Ponto em Polígono
# ============================================================

def is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    n = len(polygon)

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        if ((y1 > y) != (y2 > y)):
            xinters = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xinters:
                inside = not inside

    return inside


# ============================================================
# Classificação Técnica das Camadas
# ============================================================

def classify_environmental_layer(folder: str, name: str) -> Tuple[str, str]:
    comb = f"{folder} {name}".upper()
    name_clean = name.strip().upper()
    folder_clean = folder.strip().upper()

    category = "ÁREA AMBIENTAL PROTEGIDA"
    specific = name_clean

    if "ZONA DE AMORTECIMENTO" in comb:
        category = "ZONA DE AMORTECIMENTO DE UNIDADE DE CONSERVAÇÃO"
        for prefix in ["ZONA DE AMORTECIMENTO DO ", "ZONA DE AMORTECIMENTO DA ", "ZONA DE AMORTECIMENTO DE ", "ZONA DE AMORTECIMENTO "]:
            if specific.startswith(prefix):
                specific = specific[len(prefix):].strip()
    elif "USO SUSTENTÁVEL" in comb or "USO SUSTENTAVEL" in comb:
        category = "UNIDADE DE CONSERVAÇÃO DE USO SUSTENTÁVEL"
    elif "PROTEÇÃO INTEGRAL" in comb or "PROTECAO INTEGRAL" in comb:
        category = "UNIDADE DE CONSERVAÇÃO DE PROTEÇÃO INTEGRAL"
    elif any(term in comb for term in ["PARQUE ESTADUAL", "PARQUE NACIONAL", "PARNA", "REBIO", "ESTAÇÃO ECOLÓGICA", "ESTACAO ECOLOGICA"]):
        category = "UNIDADE DE CONSERVAÇÃO DE PROTEÇÃO INTEGRAL"
    elif any(term in comb for term in ["APA ", "ÁREA DE PROTEÇÃO AMBIENTAL", "AREA DE PROTECAO AMBIENTAL", "ARIE", "RESEX", "FLONA"]):
        category = "UNIDADE DE CONSERVAÇÃO DE USO SUSTENTÁVEL"
    elif "PRESERVAÇÃO PERMANENTE" in comb or "PRESERVACAO PERMANENTE" in comb or "APP" in comb.split():
        category = "ÁREA DE PRESERVAÇÃO PERMANENTE"
    elif "RESERVA LEGAL" in comb:
        category = "ÁREA DE RESERVA LEGAL"
    elif "INDÍGENA" in comb or "INDIGENA" in comb:
        category = "TERRA INDÍGENA"
    elif "QUILOMBOLA" in comb:
        category = "TERRITÓRIO QUILOMBOLA"
    elif folder_clean:
        category = folder_clean
    elif name_clean:
        category = name_clean

    if specific == category or specific in ["SEM NOME", "POLÍGONO", "POLYGON", "CAMADA 1", "LAYER 1", ""]:
        specific = ""

    return category, specific


# ============================================================
# Processador Principal
# ============================================================

def process_points_against_kmz(
    kmz_path: str,
    points_json_path: str,
    out_txt_path: str,
    out_json_path: str,
    out_boxes_path: str,
    default_zone: int = 23,
    northern_hemisphere: bool = False
):
    kml_text = extract_kml_from_kmz(kmz_path)
    kmz_polygons = parse_kml_polygons_with_hierarchy(kml_text)

    with open(points_json_path, 'r', encoding='utf-8') as f:
        points_data = json.load(f)

    results = []
    unique_intersections = set()
    intercepted_polygons = {}

    report_lines = [
        "============================================================",
        "  RELATÓRIO DE INTERSEÇÃO DE PONTOS COM KMZ AMBIENTAL",
        "============================================================",
        f"Arquivo KMZ: {kmz_path}",
        f"Polígonos Lidos: {len(kmz_polygons)}",
        f"Pontos Testados: {len(points_data)}",
        "------------------------------------------------------------\n"
    ]

    for pt in points_data:
        pt_id = pt.get("id", "Ponto")
        utm_x = float(pt["x"])
        utm_y = float(pt["y"])
        zone = pt.get("zone", default_zone)

        lon, lat = utm_to_latlon(utm_x, utm_y, zone=zone, northern_hemisphere=northern_hemisphere)

        matching_layers = []
        for poly in kmz_polygons:
            min_lon, max_lon, min_lat, max_lat = poly.get('bbox', (-180.0, 180.0, -90.0, 90.0))
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                continue

            if is_point_in_polygon((lon, lat), poly['coordinates']):
                cat, spec = classify_environmental_layer(poly['folder'], poly['name'])
                label = f"{cat} - {spec}" if spec else cat
                matching_layers.append(label)
                unique_intersections.add((cat, spec))

                # Registra o polígono interceptado para marcação gráfica no CAD
                poly_key = (poly.get('folder', ''), poly.get('name', ''), tuple(poly['coordinates'][:3]))
                if poly_key not in intercepted_polygons:
                    intercepted_polygons[poly_key] = {
                        "folder": poly.get('folder', ''),
                        "name": poly.get('name', ''),
                        "category": cat,
                        "specific": spec,
                        "coordinates": poly['coordinates']
                    }

        results.append({
            "id": pt_id,
            "x": utm_x,
            "y": utm_y,
            "lon": lon,
            "lat": lat,
            "layers": matching_layers,
            "has_intersection": len(matching_layers) > 0
        })

        if matching_layers:
            report_lines.append(f"[INCIDÊNCIA DETECTADA] {pt_id} (X: {utm_x:.3f}, Y: {utm_y:.3f})")
            report_lines.append(f"  -> Camadas: {', '.join(matching_layers)}\n")
        else:
            report_lines.append(f"[OK - Fora de Áreas Restritas] {pt_id} (X: {utm_x:.3f}, Y: {utm_y:.3f})\n")

    # Importa conversor analítico latlon_to_utm
    from croqui_ambiental_generator import latlon_to_utm

    cad_polygons = []
    for p_info in intercepted_polygons.values():
        utm_coords = []
        sum_x, sum_y = 0.0, 0.0
        for p_lon, p_lat in p_info["coordinates"]:
            ux, uy = latlon_to_utm(p_lat, p_lon, zone=default_zone, northern_hemisphere=northern_hemisphere)
            utm_coords.append([round(ux, 2), round(uy, 2)])
            sum_x += ux
            sum_y += uy

        n_pts = len(utm_coords)
        cx = round(sum_x / n_pts, 2) if n_pts > 0 else 0.0
        cy = round(sum_y / n_pts, 2) if n_pts > 0 else 0.0

        cat_upper = p_info["category"].upper()
        if "APP" in cat_upper:
            layer_name = "AMBIENTAL_APP"
            color_code = 1  # Vermelho
        elif "CONSERVAÇÃO" in cat_upper or "AMORTECIMENTO" in cat_upper:
            layer_name = "AMBIENTAL_UC"
            color_code = 4  # Ciano
        elif "EXCLUSÃO" in cat_upper:
            layer_name = "AMBIENTAL_EXCLUSAO"
            color_code = 1  # Vermelho
        else:
            layer_name = "AMBIENTAL_RESTRICAO"
            color_code = 3  # Verde

        display_name = p_info["specific"] if p_info["specific"] else p_info["name"]
        if not display_name:
            display_name = p_info["category"]

        cad_polygons.append({
            "name": display_name,
            "category": p_info["category"],
            "layer": layer_name,
            "color": color_code,
            "centroid": [cx, cy],
            "vertices": utm_coords
        })

    # Salva relatório TXT
    with open(out_txt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))

    # Salva JSON de retorno com polígonos inclusos
    with open(out_json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "project_intersections": [{"category": c, "specific": s} for (c, s) in sorted(unique_intersections)],
            "points": results,
            "polygons": cad_polygons
        }, f, ensure_ascii=False, indent=2)

    # Salva arquivo formatado kmz_boxes.txt
    with open(out_boxes_path, 'w', encoding='utf-8') as f:
        for cat, spec in sorted(unique_intersections):
            f.write(f"{cat}|{spec}\n")

    # Salva kmz_polygons.json no mesmo diretório temporário
    out_dir = os.path.dirname(out_boxes_path)
    poly_json_path = os.path.join(out_dir, "kmz_polygons.json")
    with open(poly_json_path, 'w', encoding='utf-8') as f:
        json.dump(cad_polygons, f, ensure_ascii=False, indent=2)

    # Gera também rotina AutoLISP compilada para desenhar os polígonos no CAD
    poly_lsp_path = os.path.join(out_dir, "kmz_draw_polygons.lsp")
    generate_cad_polygons_lisp(cad_polygons, poly_lsp_path)

    # Sinalizador de conclusão para o AutoLISP
    flag_file = out_boxes_path + ".done"
    with open(flag_file, 'w', encoding='utf-8') as f:
        f.write("DONE")

    print(f"Processamento concluído.")
    print(f"Total de incidências únicas no projeto: {len(unique_intersections)}")


def generate_cad_polygons_lisp(cad_polygons: List[Dict], out_lsp_path: str):
    """Gera rotina AutoLISP compilada com primitivas ActiveX para desenhar os polígonos e rótulos no CAD."""
    lines = [
        ";;; ============================================================",
        ";;; kmz_draw_polygons.lsp - Desenho de Polígonos Ambientais",
        ";;; Gerado automaticamente pelo aux cad",
        ";;; ============================================================",
        "(vl-load-com)",
        "",
        "(defun c:KMZ_DRAW_POLYGONS (/ acadApp doc mSpace layTable ptsArr polyObj txtObj)",
        "  (setq acadApp (vlax-get-acad-object))",
        "  (setq doc (vla-get-ActiveDocument acadApp))",
        "  (setq mSpace (vla-get-ModelSpace doc))",
        "  (setq layTable (vla-get-Layers doc))",
        "",
        "  ;; Função auxiliar para criar/garantir layer",
        "  (defun _ensure_layer (name col / l)",
        "    (setq l (vl-catch-all-apply 'vla-Item (list layTable name)))",
        "    (if (vl-catch-all-error-p l)",
        "      (progn",
        "        (setq l (vla-Add layTable name))",
        "        (vla-put-Color l col)",
        "      )",
        "    )",
        "    l",
        "  )",
        ""
    ]

    for idx, poly in enumerate(cad_polygons):
        layer = poly.get("layer", "AMBIENTAL_RESTRICAO")
        color = poly.get("color", 3)
        name = poly.get("name", "RESTRICAO AMBIENTAL").replace('"', '\\"')
        vertices = poly.get("vertices", [])
        centroid = poly.get("centroid", [0.0, 0.0])

        if len(vertices) < 3:
            continue

        flat_coords = []
        for vx, vy in vertices:
            flat_coords.extend([float(vx), float(vy)])

        coords_str = " ".join(f"{c:.2f}" for c in flat_coords)
        n_doubles = len(flat_coords)

        lines.extend([
            f"  ;; Polígono {idx + 1}: {name}",
            f'  (_ensure_layer "{layer}" {color})',
            f"  (setq ptsArr (vlax-make-safearray vlax-vbDouble '(0 . {n_doubles - 1})))",
            f"  (vlax-safearray-fill ptsArr '({coords_str}))",
            "  (setq polyObj (vla-AddLightWeightPolyline mSpace ptsArr))",
            "  (vla-put-Closed polyObj :vlax-true)",
            f'  (vla-put-Layer polyObj "{layer}")',
            f"  (vla-put-Color polyObj {color})",
            "  (vla-Update polyObj)",
            "",
            f"  ;; Rótulo descritivo no centróide",
            f'  (setq txtObj (vla-AddText mSpace "{name}" (vlax-3d-point {centroid[0]:.2f} {centroid[1]:.2f} 0.0) 3.5))',
            f'  (vla-put-Layer txtObj "{layer}")',
            f"  (vla-put-Color txtObj {color})",
            "  (vla-Update txtObj)",
            ""
        ])

    lines.extend([
        '  (princ "\\n[SUCESSO] Polígonos de restrição ambiental desenhados com sucesso no ModelSpace!")',
        "  (princ)",
        ")",
        ""
    ])

    with open(out_lsp_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


if __name__ == '__main__':
    if len(sys.argv) < 6:
        print("Uso: kmz_point_layer_report.py <kmz> <pontos.json> <relatorio.txt> <resultado.json> <boxes.txt> [fuso_utm]")
        sys.exit(1)

    kmz_file = sys.argv[1]
    pts_file = sys.argv[2]
    out_txt = sys.argv[3]
    out_json = sys.argv[4]
    out_boxes = sys.argv[5]
    zone_utm = int(sys.argv[6]) if len(sys.argv) > 6 else 23

    try:
        process_points_against_kmz(kmz_file, pts_file, out_txt, out_json, out_boxes, default_zone=zone_utm)
        sys.exit(0)
    except Exception as e:
        print(f"Erro ao processar: {e}")
        sys.exit(1)
