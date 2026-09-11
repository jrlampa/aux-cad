import json
import os
import sys

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

from typing import Dict, List, Optional
import openpyxl
from cqt_excel_io import load_scenario_from_excel
from cqt_live_calc import calcular_cqt_topologia, calcular_dmdi

try:
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False


def format_num(val, decimals=2, is_pct=False, is_int=False, is_kva=False, is_dmdi=False) -> str:
    """Formata valores numéricos para padrão brasileiro com hífen único '-' para vazios/nulos."""
    if val is None or val == "" or str(val).strip() in ["-", "None", "#N/A", "#VALOR!", "", "0.0", "0,00"]:
        return "-"
    try:
        f = float(val)
        if abs(f) < 1e-6:
            return "-"
        if is_pct:
            if f <= 1.0 and f > 0.0:
                f *= 100.0
            return f"{f:.2f}%".replace(".", ",")
        if is_kva:
            return f"{f:.2f}kVA".replace(".", ",")
        if is_dmdi:
            return f"{f:.2f}".replace(".", ",")
        if is_int:
            return str(int(round(f)))
        return f"{f:.{decimals}f}".replace(".", ",")
    except (ValueError, TypeError):
        s = str(val).strip()
        return "-" if s in ["", "None", "0"] else s


def extract_from_reference_sheets(wb: openpyxl.Workbook, custom_ponto_trafo: Optional[str] = None) -> Dict:
    """
    Extrai os dados de resumo do trafo diretamente das abas de referência de cada cenário:
    Cargas/Demanda: 'ATUAL', 'ATUAL+NC', 'PROJETADO'
    Rede/CQT: 'CQT ATUAL', 'CQT ATUAL+NC', 'CQT PROJETADO'
    """
    resumos = {}
    scens_data = {}
    cenarios = ["ATUAL", "ATUAL+NC", "PROJETADO"]

    ponto_fallback = custom_ponto_trafo
    if ponto_fallback and str(ponto_fallback).lower() in ["auto", "none", "null", "0", ""]:
        ponto_fallback = None

    if not ponto_fallback:
        for cen in cenarios:
            s_cqt_name = f"CQT {cen}"
            if s_cqt_name in wb.sheetnames:
                val = str(wb[s_cqt_name].cell(4, 6).value or "").strip()
                if val and val.lower() not in ["none", "0", ""]:
                    ponto_fallback = val
                    break
    if not ponto_fallback:
        ponto_fallback = "77245"

    for cen in cenarios:
        s_car = None
        for name in [cen, f"{cen}_CARGAS", f"CARGAS_{cen}"]:
            if name in wb.sheetnames:
                s_car = wb[name]
                break

        if not s_car:
            continue

        s_cqt = None
        for name in [f"CQT {cen}", f"CQT_{cen}", f"CQT-{cen}"]:
            if name in wb.sheetnames:
                s_cqt = wb[name]
                break

        pt = custom_ponto_trafo
        if not pt or str(pt).lower() in ["auto", "none", "null", "0", ""]:
            pt = str(s_cqt.cell(4, 6).value or "").strip() if s_cqt else ""
            if not pt or pt.lower() in ["none", "0", ""]:
                pt = ponto_fallback if cen != "PROJETADO" else "ANXXXX"

        pot = None
        if s_car.cell(10, 3).value is not None:
            pot = s_car.cell(10, 3).value
        elif s_cqt and s_cqt.cell(3, 6).value is not None:
            pot = s_cqt.cell(3, 6).value
        if pot is None or str(pot).strip() in ["", "0", "None"]:
            pot = 75
        try:
            pot_f = float(pot)
            pot_str = f"{int(pot_f)}" if pot_f.is_integer() else f"{pot_f}".replace(".", ",")
        except Exception:
            pot_str = str(pot).strip()

        prefix_trafo = "TRAFO PROJ.:" if cen == "PROJETADO" else "TRAFO EXIST.:"
        trafo_desc = f"{prefix_trafo} {pt}-3-{pot_str}kVA"

        tot_cli_val = s_car.cell(4, 3).value
        tot_cli = int(float(tot_cli_val)) if tot_cli_val not in [None, "", "None"] else 0

        dmdi_val = s_car.cell(5, 3).value
        try:
            dmdi_f = float(dmdi_val) if dmdi_val not in [None, "", "None"] else 0.0
        except Exception:
            dmdi_f = 0.0

        dem_res_val = s_car.cell(6, 4).value
        dem_ip_val = s_car.cell(7, 4).value
        dem_esp_val = s_car.cell(8, 4).value
        dem_tot_val = s_car.cell(10, 4).value
        if (dem_tot_val is None or dem_tot_val == "") and s_cqt:
            dem_tot_val = s_cqt.cell(5, 6).value

        carg_val = s_car.cell(10, 2).value
        if (carg_val is None or carg_val == "") and s_cqt:
            carg_val = s_cqt.cell(3, 7).value
        try:
            if carg_val is not None and str(carg_val).strip() not in ["", "None"]:
                carg_f = float(carg_val)
                if carg_f <= 15.0:
                    carg_val = carg_f * 100.0
        except Exception:
            pass

        esp_count = sum(int(float(s_car.cell(r, 15).value or 0)) for r in range(3, 58) if s_car.cell(r, 15).value not in [None, "", "None"])

        res_count_cell = s_car.cell(6, 2).value
        if res_count_cell is not None and str(res_count_cell).strip() not in ["", "None"]:
            try:
                res_count = int(float(res_count_cell))
            except Exception:
                res_count = max(0, tot_cli - esp_count)
        else:
            res_count = max(0, tot_cli - esp_count)

        if res_count == 0 and tot_cli > 0 and esp_count == 0:
            res_count = tot_cli

        ip_count = sum(int(float(s_car.cell(r, 7).value or 0)) for r in range(3, 8) if s_car.cell(r, 7).value not in [None, "", "None"])
        if ip_count == 0:
            ip_count = sum(int(float(s_car.cell(r, c).value or 0)) for r in range(3, 58) for c in range(19, 24) if s_car.cell(r, c).value not in [None, "", "None"])

        scens_data[cen] = {
            "ponto": pt,
            "pot": pot,
            "trafo_desc": trafo_desc,
            "tot_cli": tot_cli,
            "res_count": res_count,
            "esp_count": esp_count,
            "dmdi_f": dmdi_f,
            "dem_res": dem_res_val,
            "ip_count": ip_count,
            "dem_ip": dem_ip_val,
            "dem_esp": dem_esp_val,
            "dem_tot": dem_tot_val,
            "carg": carg_val,
        }

    for cen, d in scens_data.items():
        if d["tot_cli"] == 0 and (d["dem_tot"] in [None, 0, "0", "-"]):
            continue

        rq = format_num(d["res_count"], is_int=True) if d["res_count"] > 0 else "-"
        rd = format_num(d["dmdi_f"], is_dmdi=True) if d["dmdi_f"] > 0 else "-"
        rt = format_num(d["dem_res"], decimals=2)
        if rt == "-" and d["res_count"] > 0 and d["dmdi_f"] > 0:
            rt = format_num(d["res_count"] * d["dmdi_f"], decimals=2)

        nrq = format_num(d["esp_count"], is_int=True) if d["esp_count"] > 0 else "-"
        nrd = "-"
        nrt = format_num(d["dem_esp"], decimals=2)

        rq_rq, rq_rd, rq_rt = "-", "-", "-"
        rq_nrq, rq_nrd, rq_nrt = "-", "-", "-"

        if cen == "ATUAL+NC" and "ATUAL" in scens_data:
            at = scens_data["ATUAL"]
            if d["res_count"] > at["res_count"]:
                delta_res = d["res_count"] - at["res_count"]
                rq_rq = str(delta_res)
                rq_rd = format_num(d["dmdi_f"], is_dmdi=True)
                rq_rt = format_num(delta_res * d["dmdi_f"], decimals=2)

            try:
                esp_now = float(d["dem_esp"] or 0)
                esp_at = float(at["dem_esp"] or 0)
            except Exception:
                esp_now, esp_at = 0.0, 0.0

            if esp_now > esp_at or d["esp_count"] > at["esp_count"]:
                delta_esp_q = max(0, d["esp_count"] - at["esp_count"])
                delta_esp_t = esp_now - esp_at
                rq_nrq = str(delta_esp_q) if delta_esp_q > 0 else "1"
                rq_nrt = format_num(delta_esp_t, decimals=2)

        ip_q = format_num(d["ip_count"], is_int=True) if d["ip_count"] > 0 else "-"
        ip_d = "-"
        ip_t = format_num(d["dem_ip"], decimals=2)

        tot_cli_str = format_num(d["tot_cli"], is_int=True)
        max_p_str = format_num(d["dem_tot"], is_kva=True)
        carg_str = format_num(d["carg"], is_pct=True)

        resumos[cen] = {
            "cenario": cen,
            "ponto_trafo": d["ponto"],
            "trafo_desc": d["trafo_desc"],
            "residencial": {"qtde": rq, "dmdi": rd, "total": rt},
            "n_residencial": {"qtde": nrq, "dmdi": nrd, "total": nrt},
            "req_resid": {"qtde": rq_rq, "dmdi": rq_rd, "total": rq_rt},
            "req_n_resid": {"qtde": rq_nrq, "dmdi": rq_nrd, "total": rq_nrt},
            "ilum_publica": {"qtde": ip_q, "dmdi": ip_d, "total": ip_t},
            "total_clientes": tot_cli_str,
            "max_prev": max_p_str,
            "carregamento": carg_str,
        }

    return resumos


def extract_trechos_from_sheets(wb: openpyxl.Workbook) -> List[Dict]:
    """Extrai as quedas de tensão acumuladas diretamente das abas CQT da planilha."""
    trechos_map = {}
    cenarios = ["ATUAL", "ATUAL+NC", "PROJETADO"]
    found_any = False

    for cen in cenarios:
        s = None
        for s_name in [f"CQT {cen}", f"CQT_{cen}", f"CQT-{cen}", cen]:
            if s_name in wb.sheetnames:
                s = wb[s_name]
                break
        if not s:
            continue

        for r in range(11, 35):
            letra = s.cell(r, 1).value
            comp = s.cell(r, 3).value
            qt_acum = s.cell(r, 12).value if s.max_column >= 12 else None
            if qt_acum is None or str(qt_acum).strip() in ["", " "]:
                qt_acum = s.cell(r, 11).value

            if letra and str(letra).strip() and comp is not None and str(comp).strip() not in ["", "0", "None"]:
                l_str = str(letra).strip()
                if l_str not in trechos_map:
                    trechos_map[l_str] = {
                        "trecho": l_str,
                        "qt_atual": "-",
                        "qt_atual_nc": "-",
                        "qt_projetado": "-",
                        "ativo": True,
                    }
                fmt_qt = format_num(qt_acum, is_pct=True)
                if fmt_qt != "-":
                    found_any = True
                if cen == "ATUAL":
                    trechos_map[l_str]["qt_atual"] = fmt_qt
                elif cen == "ATUAL+NC":
                    trechos_map[l_str]["qt_atual_nc"] = fmt_qt
                elif cen == "PROJETADO":
                    trechos_map[l_str]["qt_projetado"] = fmt_qt

    if found_any:
        return [trechos_map[k] for k in sorted(trechos_map.keys())]
    return []


def extract_quadros_data(xlsm_path: str, active_scenarios: Optional[List[str]] = None, custom_ponto_trafo: Optional[str] = None) -> Dict:
    """
    Extrai os dados de carga e queda de tensão de todos os cenários da planilha CQT (.xlsx ou .xlsm).
    Prioriza a leitura direta das abas de referência (ATUAL, CQT ATUAL, etc.); se incompletas, calcula analiticamente.
    """
    if not os.path.exists(xlsm_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {xlsm_path}")

    wb = openpyxl.load_workbook(xlsm_path, data_only=True)

    # 1. Tenta extração direta das abas de referência (ATUAL, ATUAL+NC, PROJETADO e CQT)
    resumo_scenarios = extract_from_reference_sheets(wb, custom_ponto_trafo)

    # 2. Tenta extração direta dos trechos das abas CQT
    active_trechos_list = extract_trechos_from_sheets(wb)

    # 3. Fallback de cálculo se abas de referência ou Trechos estiverem ausentes/incompletos
    if not resumo_scenarios or not active_trechos_list:
        cenarios_data = {}
        cenarios_calc = {}
        for cenario_name in ["ATUAL", "ATUAL+NC", "PROJETADO"]:
            scen_info = load_scenario_from_excel(xlsm_path, cenario_name)
            if scen_info and scen_info.get("trechos"):
                cenarios_data[cenario_name] = scen_info
                try:
                    pot = float(scen_info.get("potencia_trafo") or 75.0)
                except Exception:
                    pot = 75.0
                cenarios_calc[cenario_name] = calcular_cqt_topologia(scen_info["trechos"], potencia_trafo=pot)

        ponto_trafo_base = custom_ponto_trafo
        if ponto_trafo_base and str(ponto_trafo_base).lower() in ["auto", "none", "null", "0", ""]:
            ponto_trafo_base = None

        if not ponto_trafo_base:
            for c in ["ATUAL", "ATUAL+NC", "PROJETADO"]:
                if c in cenarios_data and cenarios_data[c].get("ponto_trafo"):
                    ponto_trafo_base = cenarios_data[c]["ponto_trafo"]
                    break
        if not ponto_trafo_base or ponto_trafo_base == "0":
            ponto_trafo_base = "77245"

        pot_base = 75
        for c in ["ATUAL", "ATUAL+NC", "PROJETADO"]:
            if c in cenarios_data and cenarios_data[c].get("potencia_trafo"):
                try:
                    pot_base = int(float(cenarios_data[c]["potencia_trafo"]))
                    break
                except Exception:
                    pass

        trafo_desc_base = f"TRAFO EXIST.: {ponto_trafo_base}-3-{pot_base}kVA"

        if not active_scenarios:
            active_scenarios_calc = [c for c in ["PROJETADO", "ATUAL+NC", "ATUAL"] if c in cenarios_data]
            if not active_scenarios_calc:
                active_scenarios_calc = ["ATUAL+NC", "ATUAL"]
        else:
            active_scenarios_calc = active_scenarios

        if not resumo_scenarios:
            tot_cli_atual = cenarios_calc.get("ATUAL", {}).get("total_clientes", 0)
            for cenario_name in active_scenarios_calc:
                calc_res = cenarios_calc.get(cenario_name, {})
                tot_cli = calc_res.get("total_clientes", 0)
                dmdi_float = calcular_dmdi(tot_cli)
                dmdi_str = format_num(dmdi_float, 2)
                dem_res_val = tot_cli * dmdi_float

                ip_qtd = 0
                ip_dem_val = 0.0
                if cenario_name in cenarios_data:
                    for t in cenarios_data[cenario_name]["trechos"]:
                        try:
                            ip_qtd += int(t.get("ip70", 0) or 0)
                        except Exception:
                            pass
                    ip_dem_val = ip_qtd * 0.07

                dem_tot_val = calc_res.get("demanda_total_kva", dem_res_val + ip_dem_val)
                carg_val = calc_res.get("carregamento_trafo", 0.0)

                req_res_q, req_res_d, req_res_t = "-", "-", "-"
                if cenario_name == "ATUAL+NC":
                    if tot_cli_atual > 0 and tot_cli > tot_cli_atual:
                        delta = tot_cli - tot_cli_atual
                        req_res_q = f"{delta:02d}"
                        req_res_d = dmdi_str
                        req_res_t = format_num(delta * dmdi_float, 2)
                    else:
                        esp_tot = sum(float(t.get("esp_carga", 0) or 0) for t in cenarios_data.get(cenario_name, {}).get("trechos", []))
                        if esp_tot > 0:
                            req_res_t = format_num(esp_tot, 2)

                pt_cen = ponto_trafo_base
                if cenario_name == "PROJETADO" and not custom_ponto_trafo:
                    pt_cen = "ANXXXX"

                resumo_scenarios[cenario_name] = {
                    "cenario": cenario_name,
                    "ponto_trafo": pt_cen,
                    "trafo_desc": trafo_desc_base,
                    "residencial": {
                        "qtde": str(tot_cli) if tot_cli > 0 else "-",
                        "dmdi": dmdi_str if tot_cli > 0 else "-",
                        "total": format_num(dem_res_val, 2) if tot_cli > 0 else "-",
                    },
                    "n_residencial": {"qtde": "-", "dmdi": "-", "total": "-"},
                    "req_resid": {"qtde": req_res_q, "dmdi": req_res_d, "total": req_res_t},
                    "req_n_resid": {"qtde": "-", "dmdi": "-", "total": "-"},
                    "ilum_publica": {
                        "qtde": str(ip_qtd) if ip_qtd > 0 else "-",
                        "dmdi": "-",
                        "total": format_num(ip_dem_val, 2) if ip_dem_val > 0 else "-",
                    },
                    "total_clientes": str(tot_cli),
                    "max_prev": f"{format_num(dem_tot_val, 2)}kVA",
                    "carregamento": format_num(carg_val, is_pct=True),
                }

        if not active_trechos_list:
            letras_ativas = set()
            qt_por_cenario = {}
            for cenario_name in ["ATUAL", "ATUAL+NC", "PROJETADO"]:
                qt_por_cenario[cenario_name] = {}
                if cenario_name in cenarios_calc:
                    for tr_res in cenarios_calc[cenario_name].get("trechos_resultado", []):
                        l = tr_res["letra"]
                        letras_ativas.add(l)
                        qt_por_cenario[cenario_name][l] = tr_res["qt_acumulada"]

            def _fmt_qt(v):
                if v is None or v == "" or v == "-":
                    return "-"
                try:
                    fv = float(v)
                    if abs(fv) < 1e-6:
                        return "-"
                    return f"{fv:.2f}%".replace(".", ",")
                except Exception:
                    return "-"

            for l in sorted(list(letras_ativas)):
                active_trechos_list.append({
                    "trecho": l,
                    "qt_atual": _fmt_qt(qt_por_cenario["ATUAL"].get(l)),
                    "qt_atual_nc": _fmt_qt(qt_por_cenario["ATUAL+NC"].get(l)),
                    "qt_projetado": _fmt_qt(qt_por_cenario["PROJETADO"].get(l)),
                    "ativo": True,
                })

    if not active_trechos_list:
        active_trechos_list = [{"trecho": "A", "qt_atual": "-", "qt_atual_nc": "-", "qt_projetado": "-", "ativo": True}]

    # Se foram passados active_scenarios explícitos, filtra os resumos
    if active_scenarios:
        resumo_scenarios = {k: v for k, v in resumo_scenarios.items() if k in active_scenarios}

    wb.close()
    return {
        "arquivo": xlsm_path,
        "resumo_trafo": resumo_scenarios,
        "trechos_cqt": active_trechos_list,
    }


def generate_cad_lisp(data: Dict, lsp_out_path: str = r"C:\Temp\cqt_draw_quadros.lsp") -> str:
    """
    Gera rotina AutoLISP com geometria e alinhamento idênticos aos quadros editados pelo usuário:
    - Quadro Trafo: 47.03 x 47.10 (Verde 3 / Textos Amarelo 2 e Título Verde 3)
    - Linha divisória vertical que desce até a base em X+20.0
    - Células inferiores da direita unificadas com valores centralizados
    """
    os.makedirs(os.path.dirname(lsp_out_path), exist_ok=True)

    lines = []
    lines.append(";; ============================================================")
    lines.append(";;  cqt_draw_quadros.lsp")
    lines.append(";;  Rotinas de desenho dos Quadros de CQT no AutoCAD")
    lines.append(";;  Dimensões exatas: Trafo 47.03x47.10 | CQT Trecho 33.21x13.64")
    lines.append(";; ============================================================")
    lines.append("")
    lines.append("(defun cqt-line (p1 p2 col)")
    lines.append("  (entmake (list '(0 . \"LINE\") (cons 10 p1) (cons 11 p2) (cons 62 col)))")
    lines.append(")")
    lines.append("")
    lines.append("(defun cqt-rect (p1 p2 col / x1 y1 x2 y2)")
    lines.append("  (setq x1 (car p1) y1 (cadr p1) x2 (car p2) y2 (cadr p2))")
    lines.append("  (entmake (list '(0 . \"LWPOLYLINE\") '(100 . \"AcDbEntity\") '(100 . \"AcDbPolyline\")")
    lines.append("                '(90 . 4) '(70 . 1) (cons 62 col)")
    lines.append("                (cons 10 (list x1 y1)) (cons 10 (list x2 y1))")
    lines.append("                (cons 10 (list x2 y2)) (cons 10 (list x1 y2))))")
    lines.append(")")
    lines.append("")
    lines.append("(defun cqt-text (pt txt h align col / d72 d73)")
    lines.append("  (setq d72 0 d73 0)")
    lines.append("  (cond ((= align \"MC\") (setq d72 1 d73 2))")
    lines.append("        ((= align \"ML\") (setq d72 0 d73 2))")
    lines.append("        ((= align \"MR\") (setq d72 2 d73 2)))")
    lines.append("  (entmake (list '(0 . \"TEXT\") (cons 1 txt) (cons 10 pt) (cons 11 pt)")
    lines.append("                (cons 40 h) (cons 62 col) (cons 72 d72) (cons 73 d73)))")
    lines.append(")")
    lines.append("")

    # Função do Quadro do Trafo (Verde 47.03 x 47.10)
    lines.append(";; Desenha 1 Quadro de Resumo do Trafo (47.03 x 47.10)")
    lines.append("(defun cqt-draw-trafo-box (x y titulo trafo_desc r_q r_d r_t nr_q nr_d nr_t rq_r_q rq_r_d rq_r_t rq_nr_q rq_nr_d rq_nr_t ip_q ip_d ip_t tot_cli max_prev carreg / colV colA x_dir_mid)")
    lines.append("  (setq colV 3 colA 2)")  # Verde e Amarelo
    lines.append("  (setq x_dir_mid (+ x 33.515))")  # Centro da célula da direita (20.0 + 27.03 / 2)
    lines.append("")
    lines.append("  ;; 1. Retângulo Externo (47.03 x 47.10)")
    lines.append("  (cqt-rect (list x y) (list (+ x 47.03) (+ y 47.10)) colV)")
    lines.append("")
    lines.append("  ;; 2. Título Superior (Verde, 2.4 de altura, perfeitamente centralizado)")
    lines.append("  (cqt-text (list (+ x 23.515) (+ y 49.30)) titulo 2.4 \"MC\" colV)")
    lines.append("")
    lines.append("  ;; 3. Linhas Horizontais Internas (Verdes)")
    lines.append("  (cqt-line (list x (+ y 42.60)) (list (+ x 47.03) (+ y 42.60)) colV)")
    lines.append("  (cqt-line (list x (+ y 38.10)) (list (+ x 47.03) (+ y 38.10)) colV)")
    lines.append("  (cqt-line (list x (+ y 33.60)) (list (+ x 47.03) (+ y 33.60)) colV)")
    lines.append("  (cqt-line (list x (+ y 29.10)) (list (+ x 47.03) (+ y 29.10)) colV)")
    lines.append("  (cqt-line (list (+ x 8.0) (+ y 24.60)) (list (+ x 47.03) (+ y 24.60)) colV)")
    lines.append("  (cqt-line (list x (+ y 20.10)) (list (+ x 47.03) (+ y 20.10)) colV)")
    lines.append("  (cqt-line (list x (+ y 15.60)) (list (+ x 47.03) (+ y 15.60)) colV)")
    lines.append("  (cqt-line (list x (+ y 10.40)) (list (+ x 47.03) (+ y 10.40)) colV)")
    lines.append("  (cqt-line (list x (+ y 5.20)) (list (+ x 47.03) (+ y 5.20)) colV)")
    lines.append("")
    lines.append("  ;; 4. Linhas Verticais Internas (Verdes)")
    lines.append("  ;; Divisória em X+20.0 desce até a base (Y) para separar rótulo e valor das 3 últimas linhas")
    lines.append("  (cqt-line (list (+ x 20.0) y) (list (+ x 20.0) (+ y 42.60)) colV)")
    lines.append("  ;; Divisórias de QTDE e DMDI terminam na linha de ILUM. PÚBLICA (Y+15.60)")
    lines.append("  (cqt-line (list (+ x 28.5) (+ y 15.60)) (list (+ x 28.5) (+ y 42.60)) colV)")
    lines.append("  (cqt-line (list (+ x 37.0) (+ y 15.60)) (list (+ x 37.0) (+ y 42.60)) colV)")
    lines.append("  ;; Divisória do bloco REQ. (entre REQ. e RESID./N.RESID.)")
    lines.append("  (cqt-line (list (+ x 8.0) (+ y 20.10)) (list (+ x 8.0) (+ y 29.10)) colV)")
    lines.append("")
    lines.append("  ;; 5. Textos da Tabela (Amarelo 2)")
    lines.append("  ;; Linha Trafo")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 44.85)) trafo_desc 1.4 \"ML\" colA)")
    lines.append("  ;; Cabeçalho")
    lines.append("  (cqt-text (list (+ x 10.0) (+ y 40.35)) \"CONS.\" 1.3 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 24.25) (+ y 40.35)) \"QTDE\" 1.3 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 32.75) (+ y 40.35)) \"DMDI\" 1.3 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 42.01) (+ y 40.35)) \"TOTAL\" 1.3 \"MC\" colA)")
    lines.append("  ;; Residencial")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 35.85)) \"RESIDENCIAL\" 1.2 \"ML\" colA)")
    lines.append("  (cqt-text (list (+ x 24.25) (+ y 35.85)) r_q 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 32.75) (+ y 35.85)) r_d 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 42.01) (+ y 35.85)) r_t 1.2 \"MC\" colA)")
    lines.append("  ;; N. Residencial")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 31.35)) \"N. RESIDENCIAL\" 1.2 \"ML\" colA)")
    lines.append("  (cqt-text (list (+ x 24.25) (+ y 31.35)) nr_q 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 32.75) (+ y 31.35)) nr_d 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 42.01) (+ y 31.35)) nr_t 1.2 \"MC\" colA)")
    lines.append("  ;; REQ.")
    lines.append("  (cqt-text (list (+ x 4.0) (+ y 24.60)) \"REQ.\" 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 9.2) (+ y 26.85)) \"RESID.\" 1.2 \"ML\" colA)")
    lines.append("  (cqt-text (list (+ x 24.25) (+ y 26.85)) rq_r_q 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 32.75) (+ y 26.85)) rq_r_d 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 42.01) (+ y 26.85)) rq_r_t 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 9.2) (+ y 22.35)) \"N. RESID.\" 1.2 \"ML\" colA)")
    lines.append("  (cqt-text (list (+ x 24.25) (+ y 22.35)) rq_nr_q 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 32.75) (+ y 22.35)) rq_nr_d 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 42.01) (+ y 22.35)) rq_nr_t 1.2 \"MC\" colA)")
    lines.append("  ;; Ilum. Pública")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 17.85)) \"ILUM. PÚBLICA\" 1.2 \"ML\" colA)")
    lines.append("  (cqt-text (list (+ x 24.25) (+ y 17.85)) ip_q 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 32.75) (+ y 17.85)) ip_d 1.2 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 42.01) (+ y 17.85)) ip_t 1.2 \"MC\" colA)")
    lines.append("  ;; Três Linhas Inferiores (Célula direita unificada e perfeitamente centralizada)")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 13.00)) \"TOTAL CLIENTES:\" 1.3 \"ML\" colA)")
    lines.append("  (cqt-text (list x_dir_mid (+ y 13.00)) tot_cli 1.3 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 7.80)) \"MÁX. PREV.\" 1.3 \"ML\" colA)")
    lines.append("  (cqt-text (list x_dir_mid (+ y 7.80)) max_prev 1.3 \"MC\" colA)")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 2.60)) \"CARREGAMENTO\" 1.3 \"ML\" colA)")
    lines.append("  (cqt-text (list x_dir_mid (+ y 2.60)) carreg 1.3 \"MC\" colA)")
    lines.append(")")
    lines.append("")

    # Função do Quadro de Queda de Tensão por Trecho (Vermelho 33.21 x 13.64)
    lines.append(";; Desenha 1 Quadro de Queda de Tensão por Trecho (33.21 x 13.64)")
    lines.append("(defun cqt-draw-cqt-box (x y tr_letra qt_at qt_anc qt_proj / colR colT)")
    lines.append("  (setq colR 1 colT 7)")  # Vermelho e Branco
    lines.append("  ;; Retângulo Externo (33.21 x 13.64)")
    lines.append("  (cqt-rect (list x y) (list (+ x 33.21) (+ y 13.64)) colR)")
    lines.append("  ;; Linhas Horizontais")
    lines.append("  (cqt-line (list x (+ y 9.84)) (list (+ x 33.21) (+ y 9.84)) colR)")
    lines.append("  (cqt-line (list x (+ y 6.56)) (list (+ x 33.21) (+ y 6.56)) colR)")
    lines.append("  (cqt-line (list x (+ y 3.28)) (list (+ x 33.21) (+ y 3.28)) colR)")
    lines.append("  ;; Linha Vertical Divisória")
    lines.append("  (cqt-line (list (+ x 18.50) y) (list (+ x 18.50) (+ y 9.84)) colR)")
    lines.append("  ;; Textos")
    lines.append("  (cqt-text (list (+ x 16.605) (+ y 11.74)) (strcat \"QUEDA DE TENSÃO - TRECHO \" tr_letra) 1.6 \"MC\" colT)")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 8.20)) \"QT ATUAL\" 1.4 \"ML\" colT)")
    lines.append("  (cqt-text (list (+ x 25.85) (+ y 8.20)) qt_at 1.4 \"MC\" colT)")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 4.92)) \"QT ATUAL+NC\" 1.4 \"ML\" colT)")
    lines.append("  (cqt-text (list (+ x 25.85) (+ y 4.92)) qt_anc 1.4 \"MC\" colT)")
    lines.append("  (cqt-text (list (+ x 1.2) (+ y 1.64)) \"QT PROJETADO\" 1.4 \"ML\" colT)")
    lines.append("  (cqt-text (list (+ x 25.85) (+ y 1.64)) qt_proj 1.4 \"MC\" colT)")
    lines.append(")")
    lines.append("")

    # Função Principal de Inserção de Todos os Quadros
    lines.append(";; Comando Principal para Inserir Quadros no Desenho")
    lines.append("(defun c:CQTQUADROS (/ pt_base x_base y_base offset_x pt_tr i tr)")
    lines.append("  (princ \"\\n=======================================================\")")
    lines.append("  (princ \"\\n   INSERÇÃO DE QUADROS DE CQT E RESUMO DO TRAFO        \")")
    lines.append("  (princ \"\\n=======================================================\")")
    lines.append("  (setq pt_base (getpoint \"\\nClique o ponto de inserção para os Quadros de Resumo do Trafo <0,0>: \"))")
    lines.append("  (if (null pt_base) (setq pt_base '(0.0 0.0 0.0)))")
    lines.append("  (setq x_base (car pt_base) y_base (cadr pt_base))")
    lines.append("  (setq offset_x 0.0)")
    lines.append("")

    # Chamadas dos Quadros de Trafo disponíveis: ATUAL+NC na esquerda, ATUAL na direita (e PROJETADO se houver)
    resumos = data.get("resumo_trafo", {})
    cen_ordem = ["PROJETADO", "ATUAL+NC", "ATUAL"]
    cen_presentes = [c for c in cen_ordem if c in resumos]
    if not cen_presentes:
        cen_presentes = list(resumos.keys())

    for cen in cen_presentes:
        info = resumos[cen]
        tit = f"{info['ponto_trafo']} - {cen}"
        tr_desc = info['trafo_desc'].replace('"', '\\"')
        rq = info['residencial']['qtde']
        rd = info['residencial']['dmdi']
        rt = info['residencial']['total']
        nrq = info['n_residencial']['qtde']
        nrd = info['n_residencial']['dmdi']
        nrt = info['n_residencial']['total']
        rqrq = info['req_resid']['qtde']
        rqrd = info['req_resid']['dmdi']
        rqrt = info['req_resid']['total']
        rqnrq = info['req_n_resid']['qtde']
        rqnrd = info['req_n_resid']['dmdi']
        rqnrt = info['req_n_resid']['total']
        ipq = info['ilum_publica']['qtde']
        ipd = info['ilum_publica']['dmdi']
        ipt = info['ilum_publica']['total']
        tot = info['total_clientes']
        max_p = info['max_prev']
        carg = info['carregamento']

        lines.append(f"  ;; Quadro: {cen}")
        lines.append(
            f'  (cqt-draw-trafo-box (+ x_base offset_x) y_base "{tit}" "{tr_desc}" '
            f'"{rq}" "{rd}" "{rt}" "{nrq}" "{nrd}" "{nrt}" '
            f'"{rqrq}" "{rqrd}" "{rqrt}" "{rqnrq}" "{rqnrd}" "{rqnrt}" '
            f'"{ipq}" "{ipd}" "{ipt}" "{tot}" "{max_p}" "{carg}")'
        )
        lines.append("  (setq offset_x (+ offset_x 57.03))")  # 47.03 + 10 de espaçamento

    lines.append("")
    lines.append("  (princ \"\\nQuadros de Resumo do Trafo inseridos com sucesso!\")")
    lines.append("")

    # Quadros de Queda de Tensão por Trecho
    trechos = data.get("trechos_cqt", [])
    lines.append("  ;; Quadros de CQT por Trecho (1 em cada ponto ou enfileirados)")
    lines.append("  (initget \"Ponto Enfileirar P E\")")
    lines.append('  (setq opt_pos (getkword "\\nPosicionamento dos Quadros de CQT: [P]onto individual / [E]nfileirar abaixo <Enfileirar>: "))')
    lines.append('  (if (or (null opt_pos) (= opt_pos "")) (setq opt_pos "Enfileirar"))')
    lines.append("  (setq cur_y (- y_base 25.0) cur_x x_base)")
    lines.append("")

    for tr in trechos:
        t_letra = tr["trecho"]
        q_at = tr["qt_atual"]
        q_anc = tr["qt_atual_nc"]
        q_pj = tr["qt_projetado"]

        lines.append(f'  ;; Trecho {t_letra}')
        lines.append('  (if (or (= opt_pos "Ponto") (= opt_pos "P"))')
        lines.append('    (progn')
        lines.append(f'      (setq pt_tr (getpoint "\\nClique o ponto para o Quadro CQT do Trecho {t_letra}: "))')
        lines.append('      (if pt_tr')
        lines.append(f'        (cqt-draw-cqt-box (car pt_tr) (cadr pt_tr) "{t_letra}" "{q_at}" "{q_anc}" "{q_pj}")')
        lines.append(f'        (cqt-draw-cqt-box cur_x cur_y "{t_letra}" "{q_at}" "{q_anc}" "{q_pj}")')
        lines.append('      )')
        lines.append('    )')
        lines.append('    (progn')
        lines.append(f'      (cqt-draw-cqt-box cur_x cur_y "{t_letra}" "{q_at}" "{q_anc}" "{q_pj}")')
        lines.append('      (setq cur_x (+ cur_x 40.0))')
        lines.append('    )')
        lines.append('  )')

    lines.append("")
    lines.append('  (setvar "QTEXTMODE" 0)')
    lines.append('  (princ "\\nQuadros de Queda de Tensão por Trecho gerados com sucesso!")')
    lines.append("  (princ)")
    lines.append(")")
    lines.append("")
    lines.append("(defun cqt-exec-draw-quadros () (c:CQTQUADROS))")
    lines.append("(defun c:CQTQUADROS_DESENHAR () (c:CQTQUADROS))")
    lines.append('(princ "\\nComando CQTQUADROS carregado com sucesso! Digite CQTQUADROS para desenhar os quadros.")')
    lines.append("(princ)")

    with open(lsp_out_path, "w", encoding="windows-1252", errors="replace") as f:
        f.write("\n".join(lines))

    return lsp_out_path


def save_quadros_json(xlsm_path: str, json_out_path: str = r"C:\Temp\cqt_quadros_cad.json", active_scenarios: Optional[List[str]] = None, custom_ponto_trafo: Optional[str] = None) -> str:
    """Gera o JSON e também o arquivo LISP C:\\Temp\\cqt_draw_quadros.lsp para inserção direta no CAD."""
    os.makedirs(os.path.dirname(json_out_path), exist_ok=True)
    dados = extract_quadros_data(xlsm_path, active_scenarios, custom_ponto_trafo)
    with open(json_out_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    lsp_path = r"C:\Temp\cqt_draw_quadros.lsp"
    generate_cad_lisp(dados, lsp_path)
    return json_out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gera quadros CQT a partir de planilha Excel existente.")
    parser.add_argument("excel", nargs="?", default="", help="Caminho da planilha (.xlsx/.xlsm)")
    parser.add_argument("trafo", nargs="?", default="", help="Ponto do trafo (opcional)")
    parser.add_argument("--excel", dest="opt_excel", default="", help="Caminho da planilha")
    parser.add_argument("--trafo", dest="opt_trafo", default="", help="Ponto do trafo")
    parser.add_argument("--out", dest="opt_out", default=r"C:\Temp\cqt_quadros_cad.json", help="JSON de saída")
    args = parser.parse_args()

    caminho = args.opt_excel or args.excel
    pt = args.opt_trafo or args.trafo
    if not caminho:
        caminho = r"G:\Meu Drive\1-HBT\HBT\SETEMBRO\05\A057146257\AN_A057146257_CQT.xlsm"

    if pt and pt.lower() in ["auto", "none", "null", "0", ""]:
        pt = None

    if not os.path.exists(caminho):
        cand = os.path.abspath(caminho)
        if os.path.exists(cand):
            caminho = cand
        else:
            print(f"[ERRO] Planilha Excel não encontrada: {caminho}", file=sys.stderr)
            sys.exit(1)

    out = save_quadros_json(caminho, json_out_path=args.opt_out, custom_ponto_trafo=pt)
    print(f"[SUCESSO] Quadros gerados em: C:\\Temp\\cqt_draw_quadros.lsp a partir de {caminho}")
