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

try:
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False


def format_num(val, decimals=2, is_pct=False, is_int=False) -> str:
    """Formata valores numéricos para padrão brasileiro com hífen único '-' para vazios/nulos."""
    if val is None or val == "" or str(val).strip() in ["-", "None", "#N/A", "#VALOR!", "", "0.0", "0,00", "0"]:
        return "-"
    try:
        f = float(val)
        if abs(f) < 1e-6:
            return "-"
        if is_pct:
            if f <= 1.0 and f > 0.0:
                f *= 100.0
            return f"{f:.2f}%".replace(".", ",")
        if is_int:
            return str(int(round(f)))
        return f"{f:.{decimals}f}".replace(".", ",")
    except (ValueError, TypeError):
        s = str(val).strip()
        return "-" if s in ["", "None", "0"] else s


def extract_quadros_data(xlsm_path: str, active_scenarios: Optional[List[str]] = None, custom_ponto_trafo: Optional[str] = None) -> Dict:
    """
    Extrai os valores calculados diretamente das abas de carga (ATUAL, ATUAL+NC, PROJETADO)
    e das abas de queda de tensão (CQT ...) com máxima precisão.
    """
    if not os.path.exists(xlsm_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {xlsm_path}")

    # Abre via openpyxl data_only para leitura ultrarrápida dos valores calculados
    wb = openpyxl.load_workbook(xlsm_path, data_only=True)

    # Identifica o ponto do trafo e a descrição do trafo
    ponto_trafo_base = custom_ponto_trafo
    if not ponto_trafo_base:
        if "CQT ATUAL" in wb.sheetnames:
            ponto_trafo_base = str(wb["CQT ATUAL"]["F4"].value or "").strip()
        elif "CQT ATUAL+NC" in wb.sheetnames:
            ponto_trafo_base = str(wb["CQT ATUAL+NC"]["F4"].value or "").strip()
    if not ponto_trafo_base or ponto_trafo_base == "0":
        ponto_trafo_base = "77245"

    trafo_desc_base = "TRAFO EXIST.: 176262-3-150kVA"
    if "CAPA-RESUMO" in wb.sheetnames:
        t_exist = str(wb["CAPA-RESUMO"]["A14"].value or "").strip()
        t_val = str(wb["CAPA-RESUMO"]["B14"].value or "").strip()
        if t_exist and t_val and t_val != "None":
            trafo_desc_base = f"{t_exist} {t_val}".strip()

    if not active_scenarios:
        # Detecta automaticamente quais abas têm dados preenchidos
        active_scenarios = []
        for c in ["PROJETADO", "ATUAL+NC", "ATUAL"]:
            if c in wb.sheetnames:
                tot = wb[c]["C4"].value
                if tot and float(tot) > 0:
                    active_scenarios.append(c)
        if not active_scenarios:
            active_scenarios = ["ATUAL+NC", "ATUAL"]

    resumo_scenarios = {}

    # Dados base do ATUAL para calcular o delta de novas cargas do ATUAL+NC
    tot_cli_atual = 0
    if "ATUAL" in wb.sheetnames:
        try: tot_cli_atual = int(wb["ATUAL"]["C4"].value or 0)
        except Exception: tot_cli_atual = 0

    for cenario_name in ["PROJETADO", "ATUAL+NC", "ATUAL"]:
        if cenario_name not in active_scenarios or cenario_name not in wb.sheetnames:
            continue

        ws_c = wb[cenario_name]
        try:
            tot_cli = int(ws_c["C4"].value or 0)
        except Exception:
            tot_cli = 0

        dmdi_val = ws_c["C5"].value or 1.30
        try: dmdi_float = float(dmdi_val)
        except Exception: dmdi_float = 1.30
        dmdi_str = format_num(dmdi_float, 2)

        # Demanda residencial
        try:
            dem_res_val = float(ws_c["D6"].value or (tot_cli * dmdi_float))
        except Exception:
            dem_res_val = tot_cli * dmdi_float
        dem_res_str = format_num(dem_res_val, 2)

        # Iluminação pública
        ip_qtd = 0
        for r in range(3, 8):
            try:
                ip_qtd += int(float(ws_c[f"G{r}"].value or 0))
            except Exception:
                pass
        try:
            ip_dem_val = float(ws_c["D7"].value or 0)
        except Exception:
            ip_dem_val = 0.0

        # Demanda Total e Carregamento
        try:
            dem_tot_val = float(ws_c["D10"].value or (dem_res_val + ip_dem_val))
        except Exception:
            dem_tot_val = dem_res_val + ip_dem_val

        try:
            carg_val = float(ws_c["B10"].value or 0)
        except Exception:
            carg_val = 0.0

        # Bloco REQ (Novas Cargas)
        req_res_q = "-"
        req_res_d = "-"
        req_res_t = "-"

        if cenario_name == "ATUAL+NC" and tot_cli_atual > 0 and tot_cli > tot_cli_atual:
            delta = tot_cli - tot_cli_atual
            req_res_q = f"{delta:02d}"
            req_res_d = dmdi_str
            req_res_t = format_num(delta * dmdi_float, 2)

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
                "total": dem_res_str if tot_cli > 0 else "-"
            },
            "n_residencial": {"qtde": "-", "dmdi": "-", "total": "-"},
            "req_resid": {"qtde": req_res_q, "dmdi": req_res_d, "total": req_res_t},
            "req_n_resid": {"qtde": "-", "dmdi": "-", "total": "-"},
            "ilum_publica": {
                "qtde": str(ip_qtd) if ip_qtd > 0 else "-",
                "dmdi": "-",
                "total": format_num(ip_dem_val, 2) if ip_dem_val > 0 else "-"
            },
            "total_clientes": str(tot_cli),
            "max_prev": f"{format_num(dem_tot_val, 2)}kVA",
            "carregamento": format_num(carg_val, is_pct=True)
        }

    # Queda de Tensão por Trecho
    trechos_cqt = {}
    letras = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
    for tr_letra in letras:
        trechos_cqt[tr_letra] = {
            "trecho": tr_letra,
            "qt_atual": "-",
            "qt_atual_nc": "-",
            "qt_projetado": "-",
            "ativo": False
        }

    for cenario_name in ["ATUAL", "ATUAL+NC", "PROJETADO"]:
        sheet_cqt_name = f"CQT {cenario_name}"
        if sheet_cqt_name in wb.sheetnames:
            ws_cqt = wb[sheet_cqt_name]
            for r in range(11, 34):
                tr_nome = str(ws_cqt.cell(r, 1).value or "").strip()
                comp = ws_cqt.cell(r, 3).value
                qt_tot = ws_cqt.cell(r, 12).value  # Coluna L

                if tr_nome and tr_nome in trechos_cqt:
                    if comp is not None and str(comp).strip() not in ["", "0", "None"]:
                        trechos_cqt[tr_nome]["ativo"] = True
                    val_fmt = format_num(qt_tot, is_pct=True)
                    if cenario_name == "ATUAL":
                        trechos_cqt[tr_nome]["qt_atual"] = val_fmt
                    elif cenario_name == "ATUAL+NC":
                        trechos_cqt[tr_nome]["qt_atual_nc"] = val_fmt
                    elif cenario_name == "PROJETADO":
                        trechos_cqt[tr_nome]["qt_projetado"] = val_fmt

    active_trechos_list = [tr for tr in trechos_cqt.values() if tr["ativo"] or tr["qt_atual"] != "-" or tr["qt_atual_nc"] != "-" or tr["qt_projetado"] != "-"]
    if not active_trechos_list and "A" in trechos_cqt:
        active_trechos_list = [trechos_cqt["A"]]

    return {
        "arquivo": xlsm_path,
        "resumo_trafo": resumo_scenarios,
        "trechos_cqt": active_trechos_list
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
    lines.append("  (princ \"\\nQuadros de Queda de Tensão por Trecho gerados com sucesso!\")")
    lines.append("  (princ)")
    lines.append(")")
    lines.append("")
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
    caminho = sys.argv[1] if len(sys.argv) > 1 else r"G:\Meu Drive\1-HBT\HBT\SETEMBRO\05\A057146257\AN_A057146257_CQT.xlsm"
    pt = sys.argv[2] if len(sys.argv) > 2 else "77245"
    out = save_quadros_json(caminho, custom_ponto_trafo=pt)
    print(f"Dados e LISP dos quadros exportados com sucesso para: {out} e C:\\Temp\\cqt_draw_quadros.lsp")
