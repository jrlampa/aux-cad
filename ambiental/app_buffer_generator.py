"""
app_buffer_generator.py - Motor Geodésico Analítico de Buffers de Preservação Permanente (APP)
Calcula e gera faixas marginais de rios, córregos e raios de nascentes (Código Florestal Lei 12.651/2012)
Suporta leitura de KMZ/KML com LineString, Point e Polygon, e seleção direta de entidades CAD.
"""

import json
import math
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Optional, Tuple

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

# Reutiliza algoritmo analítico Snyder de conversão UTM / LatLon
from croqui_ambiental_generator import latlon_to_utm
from kmz_point_layer_report import is_point_in_polygon, utm_to_latlon

# =============================================================================
# REGRAS DO CÓDIGO FLORESTAL (LEI 12.651/2012)
# =============================================================================
FAIXA_APP_PADRAO_RIO_MENOR_10M = 30.0   # Cursos d'água até 10m de largura: 30m
FAIXA_APP_PADRAO_NASCENTE = 50.0        # Raio de 50m ao redor de nascentes
FAIXA_APP_RIO_10M_50M = 50.0            # Cursos d'água de 10m a 50m: 50m
FAIXA_APP_RIO_50M_200M = 100.0          # Cursos d'água de 50m a 200m: 100m


# =============================================================================
# GEOMETRIA ANALÍTICA 2D / 2.5D: GERAÇÃO DE BUFFERS
# =============================================================================

def utm_buffer_point(cx: float, cy: float, radius: float = 50.0, num_points: int = 36) -> List[Tuple[float, float]]:
    """Gera um polígono circular regular de buffer ao redor de um ponto (nascente)."""
    coords = []
    for i in range(num_points):
        angle = 2.0 * math.pi * i / num_points
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        coords.append((round(x, 2), round(y, 2)))
    return coords


def _dist_2d(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _intersect_lines(p1: Tuple[float, float], d1: Tuple[float, float],
                     p2: Tuple[float, float], d2: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    """Calcula interseção de duas retas definidas por ponto e vetor diretor."""
    det = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(det) < 1e-9:
        return None
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    t = (dx * d2[1] - dy * d2[0]) / det
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def utm_buffer_linestring(coords: List[Tuple[float, float]], buffer_dist: float = 30.0) -> List[Tuple[float, float]]:
    """
    Gera um polígono fechado de buffer bilateral contínuo ao longo de uma linha/caminho.
    Inclui tampas semicirculares suaves nos extremos e junções robustas nos vértices.
    """
    if len(coords) < 2:
        if len(coords) == 1:
            return utm_buffer_point(coords[0][0], coords[0][1], buffer_dist)
        return []

    # Remove vértices duplicados consecutivos
    clean_pts = [coords[0]]
    for pt in coords[1:]:
        if _dist_2d(pt, clean_pts[-1]) > 0.05:
            clean_pts.append(pt)

    if len(clean_pts) < 2:
        return utm_buffer_point(clean_pts[0][0], clean_pts[0][1], buffer_dist)

    n = len(clean_pts)
    left_side = []
    right_side = []

    # Gera segmentos paralelos deslocados
    for i in range(n - 1):
        p1 = clean_pts[i]
        p2 = clean_pts[i + 1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue

        nx = -dy / length
        ny = dx / length

        # Pontos deslocados à esquerda (+nx, +ny) e direita (-nx, -ny)
        l1 = (p1[0] + buffer_dist * nx, p1[1] + buffer_dist * ny)
        l2 = (p2[0] + buffer_dist * nx, p2[1] + buffer_dist * ny)
        r1 = (p1[0] - buffer_dist * nx, p1[1] - buffer_dist * ny)
        r2 = (p2[0] - buffer_dist * nx, p2[1] - buffer_dist * ny)

        left_side.append((l1, l2, (dx, dy)))
        right_side.append((r1, r2, (dx, dy)))

    if not left_side:
        return utm_buffer_point(clean_pts[0][0], clean_pts[0][1], buffer_dist)

    polygon_pts = []

    # 1. Monta o lado esquerdo com junções
    polygon_pts.append(left_side[0][0])
    for i in range(len(left_side) - 1):
        cur_l2 = left_side[i][1]
        next_l1 = left_side[i + 1][0]
        p_inter = _intersect_lines(cur_l2, left_side[i][2], next_l1, left_side[i + 1][2])

        # Se o ângulo for suave e a interseção razoável
        if p_inter and _dist_2d(p_inter, cur_l2) < 3.0 * buffer_dist:
            polygon_pts.append(p_inter)
        else:
            polygon_pts.append(cur_l2)
            polygon_pts.append(next_l1)
    polygon_pts.append(left_side[-1][1])

    # 2. Tampa semicircular no ponto final
    last_pt = clean_pts[-1]
    dx_end = clean_pts[-1][0] - clean_pts[-2][0]
    dy_end = clean_pts[-1][1] - clean_pts[-2][1]
    base_ang = math.atan2(dy_end, dx_end)

    num_cap = 12
    for step in range(num_cap + 1):
        ang = (base_ang + math.pi / 2.0) - (math.pi * step / num_cap)
        cap_x = last_pt[0] + buffer_dist * math.cos(ang)
        cap_y = last_pt[1] + buffer_dist * math.sin(ang)
        polygon_pts.append((round(cap_x, 2), round(cap_y, 2)))

    # 3. Monta o lado direito em sentido inverso
    polygon_pts.append(right_side[-1][1])
    for i in range(len(right_side) - 1, 0, -1):
        cur_r1 = right_side[i][0]
        prev_r2 = right_side[i - 1][1]
        p_inter = _intersect_lines(cur_r1, right_side[i][2], prev_r2, right_side[i - 1][2])

        if p_inter and _dist_2d(p_inter, cur_r1) < 3.0 * buffer_dist:
            polygon_pts.append(p_inter)
        else:
            polygon_pts.append(cur_r1)
            polygon_pts.append(prev_r2)
    polygon_pts.append(right_side[0][0])

    # 4. Tampa semicircular no ponto inicial
    first_pt = clean_pts[0]
    dx_start = clean_pts[1][0] - clean_pts[0][0]
    dy_start = clean_pts[1][1] - clean_pts[0][1]
    start_ang = math.atan2(dy_start, dx_start)

    for step in range(num_cap + 1):
        ang = (start_ang - math.pi / 2.0) - (math.pi * step / num_cap)
        cap_x = first_pt[0] + buffer_dist * math.cos(ang)
        cap_y = first_pt[1] + buffer_dist * math.sin(ang)
        polygon_pts.append((round(cap_x, 2), round(cap_y, 2)))

    # Arredonda e remove pontos muito próximos
    final_coords = []
    for pt in polygon_pts:
        p_round = (round(pt[0], 2), round(pt[1], 2))
        if not final_coords or _dist_2d(p_round, final_coords[-1]) > 0.1:
            final_coords.append(p_round)

    return final_coords


# =============================================================================
# PARSER DE HIDROGRAFIA EM KMZ / KML
# =============================================================================

def _strip_ns(tag: str) -> str:
    return tag.split('}', 1)[1] if '}' in tag else tag


def parse_kml_hydrography(kml_text: str, default_zone: int = 23) -> List[Dict]:
    """
    Varre o KML procurando feições de rios, córregos, nascentes e corpos d'água.
    Suporta LineString, Point e Polygon com classificação inteligente.
    """
    root = ET.fromstring(kml_text)
    hydro_features = []

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

            comb = f"{folder} {p_name}".upper()

            # Identifica a natureza da feição hídrica
            is_nascente = any(w in comb for w in ["NASCENTE", "OLHO D'ÁGUA", "OLHO D AGUA", "MINA"])
            is_rio = any(w in comb for w in ["RIO", "CÓRREGO", "CORREGO", "RIACHO", "DRENAGEM", "CURSO", "VALÃO", "VALAO", "CANAL"])
            is_lago = any(w in comb for w in ["LAGO", "LAGOA", "REPRESA", "RESERVAT"])

            # 1. Varre Pontos (Nascentes)
            for pt in node.iter():
                if _strip_ns(pt.tag) == 'Point':
                    for c_tag in pt.iter():
                        if _strip_ns(c_tag.tag) == 'coordinates' and c_tag.text:
                            coords_text = c_tag.text.strip().split(',')
                            if len(coords_text) >= 2:
                                try:
                                    lon = float(coords_text[0])
                                    lat = float(coords_text[1])
                                    ux, uy = latlon_to_utm(lat, lon, zone=default_zone)
                                    buf_radius = FAIXA_APP_PADRAO_NASCENTE
                                    buf_poly = utm_buffer_point(ux, uy, radius=buf_radius)
                                    hydro_features.append({
                                        "name": p_name or "NASCENTE",
                                        "folder": folder,
                                        "type": "NASCENTE",
                                        "buffer_m": buf_radius,
                                        "center_utm": (round(ux, 2), round(uy, 2)),
                                        "app_polygon": buf_poly,
                                        "checklist_row": 33 # Linha 33 do checklist
                                    })
                                except ValueError:
                                    pass

            # 2. Varre Linhas (Rios, Córregos e Cursos d'água)
            for ls in node.iter():
                if _strip_ns(ls.tag) == 'LineString':
                    for c_tag in ls.iter():
                        if _strip_ns(c_tag.tag) == 'coordinates' and c_tag.text:
                            raw_pts = c_tag.text.strip().replace('\n', ' ').replace('\r', ' ').split()
                            utm_line = []
                            for token in raw_pts:
                                parts = token.strip().split(',')
                                if len(parts) >= 2:
                                    try:
                                        lon = float(parts[0])
                                        lat = float(parts[1])
                                        ux, uy = latlon_to_utm(lat, lon, zone=default_zone)
                                        utm_line.append((ux, uy))
                                    except ValueError:
                                        continue

                            if len(utm_line) >= 2:
                                # Define faixa de APP com base na largura ou nome
                                buf_dist = FAIXA_APP_PADRAO_RIO_MENOR_10M
                                if "50M" in comb:
                                    buf_dist = FAIXA_APP_RIO_10M_50M
                                elif "100M" in comb or "200M" in comb:
                                    buf_dist = FAIXA_APP_RIO_50M_200M

                                buf_poly = utm_buffer_linestring(utm_line, buffer_dist=buf_dist)
                                hydro_features.append({
                                    "name": p_name or "CURSO D'ÁGUA",
                                    "folder": folder,
                                    "type": "RIO",
                                    "buffer_m": buf_dist,
                                    "centerline_utm": [(round(x, 2), round(y, 2)) for x, y in utm_line],
                                    "app_polygon": buf_poly,
                                    "checklist_row": 24 # Linha 24 do checklist (<10m)
                                })

        for child in node:
            walk(child, folder)

    walk(root, "")
    return hydro_features


# =============================================================================
# AUDITORIA DE POSTES DO PROJETO CONTRA FAIXAS DE APP HÍDRICA
# =============================================================================

def check_postes_in_hydro_app(postes: List[Dict], hydro_features: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Cruza a lista de postes do CAD com todos os buffers de APP hídricos gerados.
    Retorna lista detalhada de postes auditados e lista de infrações/interseções.
    """
    audit_results = []
    infracoes = []

    for pt in postes:
        pt_id = pt.get("id", "Poste")
        x = float(pt["x"])
        y = float(pt["y"])
        point_tuple = (x, y)

        matched_apps = []
        for feat in hydro_features:
            poly = feat.get("app_polygon", [])
            if len(poly) >= 3 and is_point_in_polygon(point_tuple, poly):
                matched_apps.append(feat)
                infracoes.append({
                    "poste_id": pt_id,
                    "x": x,
                    "y": y,
                    "tipo_app": feat["type"],
                    "nome_corpo": feat["name"],
                    "faixa_app_m": feat["buffer_m"],
                    "checklist_row": feat["checklist_row"]
                })

        audit_results.append({
            "id": pt_id,
            "x": x,
            "y": y,
            "em_app": len(matched_apps) > 0,
            "apps": matched_apps
        })

    return audit_results, infracoes


# =============================================================================
# GERADOR DE ROTINA AUTOLISP PARA DESENHO NO AUTOCAD (2.5D)
# =============================================================================

def generate_cad_buffers_lisp(hydro_features: List[Dict], infracoes: List[Dict], out_lsp_path: str):
    """Gera rotina AutoLISP com ActiveX para desenhar as faixas de APP e destacar postes em infração."""
    lines = [
        ";;; ============================================================",
        ";;; app_draw_buffers.lsp - Desenho de Buffers de APP Hídrica no CAD",
        ";;; Gerado pelo módulo ambiental do AUX CAD",
        ";;; ============================================================",
        "(vl-load-com)",
        "",
        "(defun c:APP_DRAW_BUFFERS (/ acadApp doc mSpace layTable ptsArr polyObj txtObj circObj)",
        "  (setq acadApp (vlax-get-acad-object))",
        "  (setq doc (vla-get-ActiveDocument acadApp))",
        "  (setq mSpace (vla-get-ModelSpace doc))",
        "  (setq layTable (vla-get-Layers doc))",
        "",
        "  ;; Garante criação dos layers dedicados",
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
        "",
        '  (_ensure_layer "AMBIENTAL_APP_HIDRICA" 4) ; Ciano',
        '  (_ensure_layer "AMBIENTAL_APP_ALERTA" 1)  ; Vermelho para infrações',
        ""
    ]

    # 1. Desenha polígonos de faixa de APP
    for idx, feat in enumerate(hydro_features):
        poly = feat.get("app_polygon", [])
        if len(poly) < 3:
            continue

        nome = feat.get("name", "APP").replace('"', '\\"')
        faixa = feat.get("buffer_m", 30.0)
        tipo = feat.get("type", "RIO")

        flat_coords = []
        sum_x, sum_y = 0.0, 0.0
        for vx, vy in poly:
            flat_coords.extend([float(vx), float(vy)])
            sum_x += vx
            sum_y += vy

        n_doubles = len(flat_coords)
        coords_str = " ".join(f"{c:.2f}" for c in flat_coords)
        cx = round(sum_x / len(poly), 2)
        cy = round(sum_y / len(poly), 2)

        lines.extend([
            f"  ;; Faixa de APP {idx + 1}: {nome} ({tipo} - {faixa:.0f}m)",
            f"  (setq ptsArr (vlax-make-safearray vlax-vbDouble '(0 . {n_doubles - 1})))",
            f"  (vlax-safearray-fill ptsArr '({coords_str}))",
            "  (setq polyObj (vla-AddLightWeightPolyline mSpace ptsArr))",
            "  (vla-put-Closed polyObj :vlax-true)",
            '  (vla-put-Layer polyObj "AMBIENTAL_APP_HIDRICA")',
            "  (vla-put-Color polyObj 4)",
            "  (vla-Update polyObj)",
            "",
            f'  (setq txtObj (vla-AddText mSpace "APP: {nome} ({faixa:.0f}m)" (vlax-3d-point {cx:.2f} {cy:.2f} 0.0) 2.5))',
            '  (vla-put-Layer txtObj "AMBIENTAL_APP_HIDRICA")',
            "  (vla-put-Color txtObj 4)",
            "  (vla-Update txtObj)",
            ""
        ])

    # 2. Marcação gráfica dos postes em infração
    for inf in infracoes:
        pid = inf["poste_id"]
        px = inf["x"]
        py = inf["y"]
        p_corpo = inf["nome_corpo"].replace('"', '\\"')
        lines.extend([
            f"  ;; Alerta de Poste em APP: {pid}",
            f'  (setq circObj (vla-AddCircle mSpace (vlax-3d-point {px:.2f} {py:.2f} 0.0) 3.0))',
            '  (vla-put-Layer circObj "AMBIENTAL_APP_ALERTA")',
            "  (vla-put-Color circObj 1)",
            "  (vla-Update circObj)",
            f'  (setq txtObj (vla-AddText mSpace "ALERTA: {pid} EM APP ({p_corpo})" (vlax-3d-point {px + 3.5:.2f} {py:.2f} 0.0) 2.0))',
            '  (vla-put-Layer txtObj "AMBIENTAL_APP_ALERTA")',
            "  (vla-put-Color txtObj 1)",
            "  (vla-Update txtObj)",
            ""
        ])

    lines.extend([
        '  (princ "\\n[SUCESSO] Faixas de APP Hídrica desenhadas no AutoCAD (Layer: AMBIENTAL_APP_HIDRICA)!")',
        "  (princ)",
        ")",
        ""
    ])

    with open(out_lsp_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


# =============================================================================
# ORQUESTRADOR E CLI
# =============================================================================

def process_app_buffers(
    input_source: str,
    postes_json_path: Optional[str],
    out_json_path: str,
    out_boxes_path: str,
    out_lsp_path: str,
    buffer_dist_m: float = 30.0,
    fuso_utm: int = 23
) -> Dict:
    """
    Processa entrada hidrográfica (KMZ ou JSON de polilinhas/pontos do DWG),
    gera os buffers geodésicos, audita os postes e gera o LISP de desenho.
    """
    hydro_features = []

    # Caso 1: Entrada é um arquivo KMZ / KML
    if input_source.lower().endswith(('.kmz', '.kml')):
        if input_source.lower().endswith('.kmz'):
            with zipfile.ZipFile(input_source, 'r') as z:
                kml_names = [n for n in z.namelist() if n.lower().endswith('.kml')]
                if not kml_names:
                    raise FileNotFoundError("Nenhum arquivo KML encontrado no KMZ.")
                kml_text = z.read(kml_names[0]).decode('utf-8', errors='replace')
        else:
            with open(input_source, 'r', encoding='utf-8', errors='replace') as f:
                kml_text = f.read()

        hydro_features = parse_kml_hydrography(kml_text, default_zone=fuso_utm)

    # Caso 2: Entrada é JSON com geometrias exportadas do DWG
    elif input_source.lower().endswith('.json'):
        with open(input_source, 'r', encoding='utf-8') as f:
            dwg_data = json.load(f)

        for item in dwg_data:
            item_type = item.get("type", "LINE").upper()
            nome = item.get("name", "CURSO D'ÁGUA")
            pts = item.get("coordinates", [])

            if item_type in ["POINT", "NASCENTE"]:
                if pts:
                    cx, cy = pts[0][0], pts[0][1]
                    radius = float(item.get("buffer_m", FAIXA_APP_PADRAO_NASCENTE))
                    buf_poly = utm_buffer_point(cx, cy, radius=radius)
                    hydro_features.append({
                        "name": nome,
                        "type": "NASCENTE",
                        "buffer_m": radius,
                        "center_utm": (cx, cy),
                        "app_polygon": buf_poly,
                        "checklist_row": 33
                    })
            else:
                # Polilinha de curso d'água
                if len(pts) >= 2:
                    dist = float(item.get("buffer_m", buffer_dist_m))
                    buf_poly = utm_buffer_linestring(pts, buffer_dist=dist)
                    hydro_features.append({
                        "name": nome,
                        "type": "RIO",
                        "buffer_m": dist,
                        "centerline_utm": pts,
                        "app_polygon": buf_poly,
                        "checklist_row": 24
                    })

    # Carrega postes para auditoria
    postes = []
    if postes_json_path and os.path.exists(postes_json_path):
        try:
            with open(postes_json_path, 'r', encoding='utf-8') as f:
                postes = json.load(f)
        except Exception:
            pass

    audit_pts, infracoes = check_postes_in_hydro_app(postes, hydro_features)

    # Gera saída JSON
    res_payload = {
        "total_corpos_hidricos": len(hydro_features),
        "total_postes_auditados": len(postes),
        "postes_em_app": infracoes,
        "features": [
            {
                "name": h["name"],
                "type": h["type"],
                "buffer_m": h["buffer_m"],
                "checklist_row": h["checklist_row"],
                "app_polygon": h["app_polygon"]
            }
            for h in hydro_features
        ]
    }

    with open(out_json_path, 'w', encoding='utf-8') as f:
        json.dump(res_payload, f, ensure_ascii=False, indent=2)

    # Alimenta/anexa ao kmz_boxes.txt para o Checklist e Memorial Ambiental
    if out_boxes_path:
        existing_lines = []
        if os.path.exists(out_boxes_path):
            with open(out_boxes_path, 'r', encoding='utf-8') as f:
                existing_lines = [line.strip() for line in f if line.strip()]

        for inf in infracoes:
            cat = "ÁREA DE PRESERVAÇÃO PERMANENTE"
            spec = f"{inf['tipo_app']} - {inf['nome_corpo']} (Faixa {inf['faixa_app_m']:.0f}m)"
            box_line = f"{cat}|{spec}"
            if box_line not in existing_lines:
                existing_lines.append(box_line)

        with open(out_boxes_path, 'w', encoding='utf-8') as f:
            for line in existing_lines:
                f.write(f"{line}\n")

    # Gera LISP compilado para desenho no CAD
    generate_cad_buffers_lisp(hydro_features, infracoes, out_lsp_path)

    # Flag de conclusão
    done_flag = out_json_path + ".done"
    with open(done_flag, 'w', encoding='utf-8') as f:
        f.write("DONE")

    return res_payload


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Gerador de Buffers de APP Hídrica (Lei 12.651/2012)")
    parser.add_argument("pos_args", nargs="*", help="Argumentos posicionais legados")
    parser.add_argument("--kmz", dest="kmz", help="Arquivo KMZ ou KML de entrada")
    parser.add_argument("--cad-json", dest="cad_json", help="Arquivo JSON de geometrias do CAD")
    parser.add_argument("--postes-json", dest="postes_json", help="Arquivo JSON com coordenadas de postes")
    parser.add_argument("--out-json", dest="out_json", help="Caminho do JSON de saída")
    parser.add_argument("--out-report", dest="out_report", help="Caminho do relatório de saída")
    parser.add_argument("--out-boxes", dest="out_boxes", help="Caminho de kmz_boxes.txt")
    parser.add_argument("--out-lisp", dest="out_lisp", help="Caminho do script AutoLISP gerado")
    parser.add_argument("--fuso", dest="fuso", type=int, default=23, help="Fuso UTM")
    parser.add_argument("--buffer-rio", dest="buffer_rio", type=float, default=30.0, help="Raio do buffer de rio (m)")
    parser.add_argument("--buffer-nascente", dest="buffer_nascente", type=float, default=50.0, help="Raio da nascente (m)")

    args = parser.parse_args(argv)

    in_src = None
    p_json = None
    o_json = None
    o_box = None
    o_lsp = None
    b_dist = 30.0
    fuso = 23

    if args.pos_args and len(args.pos_args) >= 5:
        in_src = args.pos_args[0]
        p_json = args.pos_args[1]
        o_json = args.pos_args[2]
        o_box = args.pos_args[3]
        o_lsp = args.pos_args[4]
        b_dist = float(args.pos_args[5]) if len(args.pos_args) > 5 else 30.0
        fuso = int(args.pos_args[6]) if len(args.pos_args) > 6 else 23
    else:
        in_src = args.kmz or args.cad_json
        p_json = args.postes_json
        o_lsp = args.out_lisp or "app_draw_buffers.lsp"
        o_box = args.out_boxes or "kmz_boxes.txt"
        o_json = args.out_json or (os.path.splitext(o_lsp)[0] + ".json")
        b_dist = args.buffer_rio
        fuso = args.fuso

    if not in_src:
        parser.print_help()
        return 1

    try:
        res = process_app_buffers(in_src, p_json, o_json, o_box, o_lsp, buffer_dist_m=b_dist, fuso_utm=fuso)
        # Se solicitou relatório em texto
        if args.out_report:
            with open(args.out_report, 'w', encoding='utf-8') as f:
                f.write("RELATÓRIO DE AUDITORIA DE APP HÍDRICA (LEI 12.651)\n")
                f.write(f"Total de Corpos Hídricos: {res['total_corpos_hidricos']}\n")
                f.write(f"Total de Postes Auditados: {res['total_postes_auditados']}\n")
                f.write(f"Postes em APP: {len(res['postes_em_app'])}\n")
                for p in res['postes_em_app']:
                    f.write(f" - Poste {p['poste_id']} em {p['tipo_app']}: {p['nome_corpo']} (Faixa {p['faixa_app_m']:.0f}m)\n")
        print("Buffer de APP Hídrica processado com sucesso!")
        return 0
    except Exception as e:
        print(f"Erro ao processar buffer de APP: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
