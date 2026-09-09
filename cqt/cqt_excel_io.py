"""
Módulo de I/O e Persistência Excel para Queda de Tensão (CQT - BT).
Responsável por leitura de condutores homologados, extração de cenários pré-existentes
e gravação atômica da planilha multi-cenários (.xlsm) preservando o template intacto.
"""

import os
import shutil
import sys
from typing import Dict, List, Optional
import openpyxl

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

DEFAULT_TEMPLATE_PATH = r"G:\Meu Drive\1-HBT\HBT\SETEMBRO\CQT TRECHO.xlsm"


def load_cables_from_database(xlsm_path: str) -> List[str]:
    """Carrega a lista de condutores homologados da aba BASE DE DADOS."""
    default_cables = [
        "3x150+70 - Al - F.P 1",
        "3x150+1x80 - Al - F.P 1",
        "3x95+1x54,6 - Al - F.P 1",
        "3x70+1x70 - Al - F.P 1",
        "3x50+1x50 - Al - F.P 1",
        "3x50+1x54,6 - Al - F.P 1",
        "3x35+1x54,6 - Al - F.P 1",
        "3x35+1x35 - Al - F.P 1",
        "2x16+25 - Al - F.P 1"
    ]
    if not os.path.exists(xlsm_path):
        return default_cables

    try:
        wb = openpyxl.load_workbook(xlsm_path, data_only=True)
        if 'BASE DE DADOS' not in wb.sheetnames:
            return default_cables
        sheet = wb['BASE DE DADOS']
        cables = []
        for r in range(4, sheet.max_row + 1):
            val = sheet.cell(r, 1).value
            if val and str(val).strip():
                cables.append(str(val).strip())
        return cables if cables else default_cables
    except Exception:
        return default_cables


def load_scenario_from_excel(xlsm_path: str, cenario: str) -> Dict:
    """Lê os dados existentes de um cenário específico da planilha."""
    if not os.path.exists(xlsm_path):
        return {}

    try:
        wb = openpyxl.load_workbook(xlsm_path, data_only=True)
        sheet_cqt_name = f"CQT {cenario}"
        sheet_cargas_name = cenario

        if sheet_cqt_name not in wb.sheetnames or sheet_cargas_name not in wb.sheetnames:
            return {}

        s_cqt = wb[sheet_cqt_name]
        s_cargas = wb[sheet_cargas_name]

        projeto = str(s_cqt.cell(1, 2).value or "").strip()
        ponto_trafo = str(s_cqt.cell(4, 6).value or "").strip()
        classe = str(s_cargas.cell(3, 3).value or "CLASSE C").strip()
        potencia = str(s_cargas.cell(10, 3).value or "45").strip()

        trechos = []
        for idx in range(23):
            r_cqt = 11 + idx
            r_cargas = 3 + idx

            letra = s_cqt.cell(r_cqt, 1).value
            mont = s_cqt.cell(r_cqt, 2).value
            comp = s_cqt.cell(r_cqt, 3).value
            cabo = s_cqt.cell(r_cqt, 9).value

            mono = s_cargas.cell(r_cargas, 12).value
            bi = s_cargas.cell(r_cargas, 13).value
            tri = s_cargas.cell(r_cargas, 14).value
            esp_c = s_cargas.cell(r_cargas, 16).value
            ip70 = s_cargas.cell(r_cargas, 19).value
            ip125 = s_cargas.cell(r_cargas, 21).value
            ip250 = s_cargas.cell(r_cargas, 22).value

            if mont or comp or cabo or mono or bi or tri or ip70:
                try:
                    comp_m = float(comp or 0) * 100.0
                except ValueError:
                    comp_m = 0.0

                trechos.append({
                    "letra": str(letra or chr(ord('A') + idx)),
                    "montante": str(mont or ("TRAFO" if idx == 0 else "A")),
                    "comprimento_m": comp_m,
                    "condutor": str(cabo or ""),
                    "mono": str(mono if mono is not None else ""),
                    "bi": str(bi if bi is not None else ""),
                    "tri": str(tri if tri is not None else ""),
                    "esp_carga": str(esp_c if esp_c is not None else ""),
                    "ip70": str(ip70 if ip70 is not None else ""),
                    "ip125": str(ip125 if ip125 is not None else ""),
                    "ip250": str(ip250 if ip250 is not None else ""),
                })

        return {
            "projeto": projeto,
            "ponto_trafo": ponto_trafo,
            "classe": classe,
            "potencia_trafo": potencia,
            "trechos": trechos
        }
    except Exception:
        return {}


def load_all_scenarios_from_excel(xlsm_path: str) -> Dict:
    """
    Carrega todos os cenários disponíveis (ATUAL, ATUAL+NC, PROJETADO) e dados cadastrais
    de uma planilha Excel existente (.xlsx ou .xlsm).
    """
    if not os.path.exists(xlsm_path):
        return {}

    resultado = {
        "projeto": "",
        "ponto_trafo": "",
        "classe": "CLASSE C",
        "potencia_trafo": "45",
        "cenarios": {}
    }

    try:
        wb = openpyxl.load_workbook(xlsm_path, data_only=True)
        for cenario in ["ATUAL", "ATUAL+NC", "PROJETADO"]:
            data_cen = load_scenario_from_excel(xlsm_path, cenario)
            if data_cen and data_cen.get("trechos"):
                resultado["cenarios"][cenario] = data_cen["trechos"]
                if not resultado["projeto"] and data_cen.get("projeto"):
                    resultado["projeto"] = data_cen["projeto"]
                if not resultado["ponto_trafo"] and data_cen.get("ponto_trafo"):
                    resultado["ponto_trafo"] = data_cen["ponto_trafo"]
                if data_cen.get("classe"):
                    resultado["classe"] = data_cen["classe"]
                if data_cen.get("potencia_trafo"):
                    resultado["potencia_trafo"] = data_cen["potencia_trafo"]
        wb.close()
        return resultado
    except Exception:
        return {}


def update_cqt_excel(template_path: str, dest_path: str, data: Dict) -> List[str]:
    """
    Grava os dados preenchidos na planilha CQT de destino (preservando o template intacto).
    Suporta gravar múltiplos cenários (PROJETADO, ATUAL+NC, ATUAL) simultaneamente.
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template não encontrado: {template_path}")

    if os.path.abspath(dest_path) != os.path.abspath(template_path):
        dest_dir = os.path.dirname(dest_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(template_path, dest_path)

    wb = openpyxl.load_workbook(dest_path, keep_vba=True, data_only=False)

    scenarios_dict = {}
    if "scenarios" in data:
        scenarios_dict = data["scenarios"]
    elif "cenario" in data and "trechos" in data:
        scenarios_dict[data["cenario"]] = data["trechos"]

    projeto = data.get("projeto", "")
    ponto_trafo = data.get("ponto_trafo", "")
    classe = data.get("classe", "CLASSE C")
    try:
        potencia_val = float(data.get("potencia_trafo", 45))
    except ValueError:
        potencia_val = 45.0

    updated_scenarios = []

    for cenario, trechos in scenarios_dict.items():
        if not trechos:
            continue

        sheet_cargas_name = cenario
        sheet_cqt_name = f"CQT {cenario}"

        if sheet_cargas_name not in wb.sheetnames or sheet_cqt_name not in wb.sheetnames:
            continue

        sheet_cargas = wb[sheet_cargas_name]
        sheet_cqt = wb[sheet_cqt_name]

        # 1. Cabeçalho do Projeto e Trafo
        sheet_cqt.cell(1, 2).value = projeto
        sheet_cqt.cell(4, 6).value = ponto_trafo
        sheet_cargas.cell(3, 3).value = classe
        sheet_cargas.cell(10, 3).value = potencia_val

        # 2. Limpeza prévia de linhas residuais
        for r in range(11, 34):
            sheet_cqt.cell(r, 2).value = None  # Montante
            sheet_cqt.cell(r, 3).value = None  # Comprimento
            sheet_cqt.cell(r, 9).value = None  # Condutor

        for r in range(3, 26):
            sheet_cargas.cell(r, 12).value = None  # Mono
            sheet_cargas.cell(r, 13).value = None  # Bi
            sheet_cargas.cell(r, 14).value = None  # Tri
            sheet_cargas.cell(r, 15).value = None  # Tri Especial Quant
            sheet_cargas.cell(r, 16).value = None  # Tri Especial Carga
            sheet_cargas.cell(r, 19).value = None  # IP70W
            sheet_cargas.cell(r, 20).value = None  # IP80W
            sheet_cargas.cell(r, 21).value = None  # IP125W
            sheet_cargas.cell(r, 22).value = None  # IP250W
            sheet_cargas.cell(r, 23).value = None  # IP400W

        # 3. Gravação dos Trechos
        for idx, tr in enumerate(trechos):
            row_cqt = 11 + idx
            row_cargas = 3 + idx
            if row_cqt > 33 or row_cargas > 25:
                break

            sheet_cqt.cell(row_cqt, 2).value = tr.get("montante", "TRAFO" if idx == 0 else "A")

            try:
                comp_metros = float(tr.get("comprimento_m", 0))
                comp_hecto = comp_metros / 100.0
            except ValueError:
                comp_hecto = 0.0
            sheet_cqt.cell(row_cqt, 3).value = comp_hecto
            sheet_cqt.cell(row_cqt, 9).value = tr.get("condutor", "")

            mono = int(tr.get("mono", 0) or 0)
            bi = int(tr.get("bi", 0) or 0)
            tri = int(tr.get("tri", 0) or 0)
            esp_q = int(tr.get("esp_qtd", 0) or 0)
            try:
                esp_c = float(tr.get("esp_carga", 0) or 0)
            except ValueError:
                esp_c = 0.0

            if mono > 0: sheet_cargas.cell(row_cargas, 12).value = mono
            if bi > 0:   sheet_cargas.cell(row_cargas, 13).value = bi
            if tri > 0:  sheet_cargas.cell(row_cargas, 14).value = tri
            if esp_q > 0 or esp_c > 0:
                sheet_cargas.cell(row_cargas, 15).value = esp_q if esp_q > 0 else 1
                sheet_cargas.cell(row_cargas, 16).value = esp_c

            ip70 = int(tr.get("ip70", 0) or 0)
            ip80 = int(tr.get("ip80", 0) or 0)
            ip125 = int(tr.get("ip125", 0) or 0)
            ip250 = int(tr.get("ip250", 0) or 0)
            ip400 = int(tr.get("ip400", 0) or 0)

            if ip70 > 0:  sheet_cargas.cell(row_cargas, 19).value = ip70
            if ip80 > 0:  sheet_cargas.cell(row_cargas, 20).value = ip80
            if ip125 > 0: sheet_cargas.cell(row_cargas, 21).value = ip125
            if ip250 > 0: sheet_cargas.cell(row_cargas, 22).value = ip250
            if ip400 > 0: sheet_cargas.cell(row_cargas, 23).value = ip400

        updated_scenarios.append(cenario)

    wb.save(dest_path)
    return updated_scenarios
