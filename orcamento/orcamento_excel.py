"""
Módulo de Exportação e Formatação da Planilha de Orçamento e Levantamento de Materiais.
Gera planilha Excel (.xlsx) profissional multi-abas:
1. RESUMO ORÇAMENTO (com KPIs de Materiais, Mão de Obra e Total Geral)
2. DETALHAMENTO MATERIAIS (incluindo materiais explodidos de kits)
3. DETALHAMENTO MÃO DE OBRA (baremos, vozes e custos contratuais da empreiteira)
4. DETALHAMENTO POSTES E CABOS (dados de engenharia do CAD)
5. FORMATO sisORÇA (colunas compatíveis para colagem na planilha oficial)
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from orcamento_core import CaboItem, MaoDeObraItem, MaterialResumo, PosteItem


def exportar_planilha_orcamento(
    dados_processados: Dict[str, Any],
    caminho_saida: str,
    num_projeto: str = "PROJETO PADRÃO",
    municipio: str = "CAMPOS DOS GOYTACAZES - RJ",
    projetista: str = "ENG. PROJETISTA"
) -> str:
    """
    Gera pasta de trabalho Excel completa (.xlsx) com 5 abas estruturadas.
    """
    wb = openpyxl.Workbook()

    # Estilos Corporativos IM3 / Concessionária
    cor_azul_escuro = "1B365D"
    cor_azul_medio = "2C5E8A"
    cor_azul_claro = "4A90E2"
    cor_cinza_claro = "F4F6F9"
    cor_verde_sucesso = "107C41"
    cor_borda = "D0D5DD"

    fill_header = PatternFill(start_color=cor_azul_escuro, end_color=cor_azul_escuro, fill_type="solid")
    fill_sub = PatternFill(start_color=cor_azul_medio, end_color=cor_azul_medio, fill_type="solid")
    fill_sub_mo = PatternFill(start_color="8A532C", end_color="8A532C", fill_type="solid")
    fill_zebra = PatternFill(start_color=cor_cinza_claro, end_color=cor_cinza_claro, fill_type="solid")
    fill_total = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")

    font_title = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    font_header = Font(name="Segoe UI", size=9, bold=True, color="FFFFFF")
    font_bold = Font(name="Segoe UI", size=9, bold=True)
    font_body = Font(name="Segoe UI", size=9)
    font_total = Font(name="Segoe UI", size=10, bold=True, color=cor_verde_sucesso)

    thin_border = Border(
        left=Side(style='thin', color=cor_borda),
        right=Side(style='thin', color=cor_borda),
        top=Side(style='thin', color=cor_borda),
        bottom=Side(style='thin', color=cor_borda)
    )

    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    # Dados processados
    materiais = dados_processados.get("materiais", [])
    mao_de_obra = dados_processados.get("mao_de_obra", [])
    postes = dados_processados.get("postes", [])
    cabos = dados_processados.get("cabos", [])
    total_mat = float(dados_processados.get("total_materiais", 0.0))
    total_mo = float(dados_processados.get("total_mao_de_obra", 0.0))
    total_bdi = float(dados_processados.get("total_bdi", 0.0))
    total_geral = float(dados_processados.get("total_geral", 0.0))
    empreiteira = str(dados_processados.get("empreiteira", "ENGELMIG"))
    territorio = str(dados_processados.get("territorio", "A"))
    ambiente = str(dados_processados.get("ambiente", "NA"))

    # =========================================================
    # ABA 1: RESUMO ORÇAMENTO
    # =========================================================
    ws_resumo = wb.active
    ws_resumo.title = "RESUMO ORÇAMENTO"
    ws_resumo.views.sheetView[0].showGridLines = True

    ws_resumo.merge_cells("A1:G1")
    ws_resumo["A1"] = "LEVANTAMENTO QUANTITATIVO E ORÇAMENTO DE MATERIAIS - REDE ELÉTRICA"
    ws_resumo["A1"].font = font_title
    ws_resumo["A1"].fill = fill_header
    ws_resumo["A1"].alignment = align_center
    ws_resumo.row_dimensions[1].height = 28

    meta_info = [
        ("Projeto / Ordem:", num_projeto, "Data:", datetime.now().strftime("%d/%m/%Y")),
        ("Município / UF:", municipio, "Projetista:", projetista),
        ("Empreiteira:", empreiteira, "Território / Classe:", f"Classe {territorio}"),
        ("Ambiente:", "Agressivo (Salinidade)" if ambiente == "AA" else "Normal", "Margem Cabos:", f"{dados_processados.get('margem_cabos_pct', 5.0)}%")
    ]

    for idx_row, row_data in enumerate(meta_info, start=2):
        ws_resumo.cell(row=idx_row, column=1, value=row_data[0]).font = font_bold
        ws_resumo.cell(row=idx_row, column=2, value=row_data[1]).font = font_body
        ws_resumo.cell(row=idx_row, column=4, value=row_data[2]).font = font_bold
        ws_resumo.cell(row=idx_row, column=5, value=row_data[3]).font = font_body
        ws_resumo.row_dimensions[idx_row].height = 18

    # Cards de Totais
    ws_resumo.cell(row=6, column=1, value="TOTAL MATERIAIS (R$)").font = font_bold
    ws_resumo.cell(row=6, column=2, value=total_mat).number_format = 'R$ #,##0.00'
    ws_resumo.cell(row=6, column=2).font = font_bold

    ws_resumo.cell(row=6, column=4, value="TOTAL MÃO DE OBRA (R$)").font = font_bold
    ws_resumo.cell(row=6, column=5, value=total_mo).number_format = 'R$ #,##0.00'
    ws_resumo.cell(row=6, column=5).font = font_bold

    ws_resumo.cell(row=7, column=1, value="TOTAL GERAL DA OBRA (R$)").font = font_total
    ws_resumo.cell(row=7, column=2, value=total_geral).number_format = 'R$ #,##0.00'
    ws_resumo.cell(row=7, column=2).font = font_total
    ws_resumo.cell(row=7, column=2).fill = fill_total

    # Tabela de Materiais Resumida
    headers_res = ["Item", "Código", "Descrição do Material / Equipamento", "Unid.", "Qtd.", "Preço Unit. (R$)", "Total (R$)"]
    row_h = 9
    ws_resumo.row_dimensions[row_h].height = 22
    for col_i, h in enumerate(headers_res, start=1):
        c = ws_resumo.cell(row=row_h, column=col_i, value=h)
        c.font = font_header
        c.fill = fill_sub
        c.alignment = align_center
        c.border = thin_border

    cur_row = row_h + 1
    for idx, mat in enumerate(materiais, start=1):
        ws_resumo.cell(row=cur_row, column=1, value=idx).alignment = align_center
        ws_resumo.cell(row=cur_row, column=2, value=mat.codigo).alignment = align_center
        ws_resumo.cell(row=cur_row, column=3, value=mat.descricao).alignment = align_left
        ws_resumo.cell(row=cur_row, column=4, value=mat.unidade).alignment = align_center
        ws_resumo.cell(row=cur_row, column=5, value=mat.quantidade).alignment = align_right
        ws_resumo.cell(row=cur_row, column=6, value=mat.preco_unitario).number_format = 'R$ #,##0.00'
        ws_resumo.cell(row=cur_row, column=7, value=f"=E{cur_row}*F{cur_row}").number_format = 'R$ #,##0.00'

        for col_i in range(1, 8):
            cell = ws_resumo.cell(row=cur_row, column=col_i)
            cell.font = font_body
            cell.border = thin_border
            if idx % 2 == 0:
                cell.fill = fill_zebra
        cur_row += 1

    # =========================================================
    # ABA 2: DETALHAMENTO MÃO DE OBRA
    # =========================================================
    ws_mo = wb.create_sheet(title="DETALHAMENTO MÃO DE OBRA")
    ws_mo.views.sheetView[0].showGridLines = True

    ws_mo.merge_cells("A1:I1")
    ws_mo["A1"] = f"CRONOGRAMA E DETALHAMENTO DE MÃO DE OBRA - {empreiteira} (CLASSE {territorio})"
    ws_mo["A1"].font = font_title
    ws_mo["A1"].fill = fill_sub_mo
    ws_mo["A1"].alignment = align_center
    ws_mo.row_dimensions[1].height = 28

    headers_mo = ["Item", "Voz", "Baremo SAP", "Descrição do Serviço Contratual", "Território", "Unid.", "Qtd.", "Custo Unit. (R$)", "Total (R$)"]
    row_h_mo = 3
    for col_i, h in enumerate(headers_mo, start=1):
        c = ws_mo.cell(row=row_h_mo, column=col_i, value=h)
        c.font = font_header
        c.fill = fill_sub_mo
        c.alignment = align_center
        c.border = thin_border

    cur_row_mo = row_h_mo + 1
    for idx, mo in enumerate(mao_de_obra, start=1):
        ws_mo.cell(row=cur_row_mo, column=1, value=idx).alignment = align_center
        ws_mo.cell(row=cur_row_mo, column=2, value=mo.voz).alignment = align_center
        ws_mo.cell(row=cur_row_mo, column=3, value=mo.baremo).alignment = align_center
        ws_mo.cell(row=cur_row_mo, column=4, value=mo.descricao).alignment = align_left
        ws_mo.cell(row=cur_row_mo, column=5, value=mo.territorio).alignment = align_center
        ws_mo.cell(row=cur_row_mo, column=6, value=mo.unidade).alignment = align_center
        ws_mo.cell(row=cur_row_mo, column=7, value=mo.quantidade).alignment = align_right
        ws_mo.cell(row=cur_row_mo, column=8, value=mo.custo_unitario).number_format = 'R$ #,##0.00'
        ws_mo.cell(row=cur_row_mo, column=9, value=f"=G{cur_row_mo}*H{cur_row_mo}").number_format = 'R$ #,##0.00'

        for col_i in range(1, 10):
            cell = ws_mo.cell(row=cur_row_mo, column=col_i)
            cell.font = font_body
            cell.border = thin_border
            if idx % 2 == 0:
                cell.fill = fill_zebra
        cur_row_mo += 1

    # Linha de Total Mão de Obra
    ws_mo.cell(row=cur_row_mo, column=8, value="TOTAL MÃO DE OBRA:").font = font_bold
    ws_mo.cell(row=cur_row_mo, column=9, value=f"=SUM(I4:I{cur_row_mo-1})").font = font_total
    ws_mo.cell(row=cur_row_mo, column=9).number_format = 'R$ #,##0.00'

    # =========================================================
    # ABA 3: DETALHAMENTO POSTES
    # =========================================================
    ws_postes = wb.create_sheet(title="DETALHAMENTO POSTES")
    ws_postes.views.sheetView[0].showGridLines = True

    ws_postes.cell(row=1, column=1, value="LEVANTAMENTO DE POSTES DO DWG").font = font_bold
    headers_p = ["ID", "Bloco CAD", "Altura (m)", "Esforço (daN)", "Estruturas", "Equipamentos", "Coord. X", "Coord. Y"]
    for col_i, h in enumerate(headers_p, start=1):
        c = ws_postes.cell(row=2, column=col_i, value=h)
        c.font = font_header
        c.fill = fill_sub
        c.border = thin_border

    row_p = 3
    for p in postes:
        ws_postes.cell(row=row_p, column=1, value=p.id_poste).alignment = align_center
        ws_postes.cell(row=row_p, column=2, value=p.nome_bloco).alignment = align_left
        ws_postes.cell(row=row_p, column=3, value=p.altura).alignment = align_center
        ws_postes.cell(row=row_p, column=4, value=p.esforco).alignment = align_center
        ws_postes.cell(row=row_p, column=5, value=", ".join(p.estruturas)).alignment = align_left
        ws_postes.cell(row=row_p, column=6, value=", ".join(p.equipamentos)).alignment = align_left
        ws_postes.cell(row=row_p, column=7, value=p.x).alignment = align_right
        ws_postes.cell(row=row_p, column=8, value=p.y).alignment = align_right
        for ci in range(1, 9):
            ws_postes.cell(row=row_p, column=ci).font = font_body
            ws_postes.cell(row=row_p, column=ci).border = thin_border
        row_p += 1

    # =========================================================
    # ABA 4: DETALHAMENTO CABOS
    # =========================================================
    ws_cabos = wb.create_sheet(title="DETALHAMENTO CABOS")
    ws_cabos.views.sheetView[0].showGridLines = True

    ws_cabos.cell(row=1, column=1, value="LEVANTAMENTO DE CONDUTORES DO DWG").font = font_bold
    headers_c = ["ID", "Layer CAD", "Tensão", "Extensão DWG (m)", "Margem (%)", "Extensão Orçada (m)", "Vãos"]
    for col_i, h in enumerate(headers_c, start=1):
        c = ws_cabos.cell(row=2, column=col_i, value=h)
        c.font = font_header
        c.fill = fill_sub
        c.border = thin_border

    row_c = 3
    for cb in cabos:
        ws_cabos.cell(row=row_c, column=1, value=cb.id_cabo).alignment = align_center
        ws_cabos.cell(row=row_c, column=2, value=cb.layer).alignment = align_left
        ws_cabos.cell(row=row_c, column=3, value=cb.tensao).alignment = align_center
        ws_cabos.cell(row=row_c, column=4, value=cb.comprimento_cad).alignment = align_right
        ws_cabos.cell(row=row_c, column=5, value=cb.margem_pct).alignment = align_center
        ws_cabos.cell(row=row_c, column=6, value=cb.comprimento_orcado).alignment = align_right
        ws_cabos.cell(row=row_c, column=7, value=cb.vaos).alignment = align_center
        for ci in range(1, 8):
            ws_cabos.cell(row=row_c, column=ci).font = font_body
            ws_cabos.cell(row=row_c, column=ci).border = thin_border
        row_c += 1

    # =========================================================
    # ABA 5: BANCO DE PREÇOS / FORMATO sisORÇA
    # =========================================================
    ws_sisorca = wb.create_sheet(title="FORMATO sisORÇA")
    ws_sisorca.views.sheetView[0].showGridLines = True

    headers_sisorca = ["PONTO", "POSTE NOVO", "POSTE RET", "EST 1", "EST 2", "EST 3", "EST 4", "EST 5", "EST RET", "AT", "DAE"]
    for col_i, h in enumerate(headers_sisorca, start=1):
        c = ws_sisorca.cell(row=1, column=col_i, value=h)
        c.font = font_header
        c.fill = fill_header
        c.alignment = align_center
        c.border = thin_border

    row_so = 2
    for p in postes:
        ws_sisorca.cell(row=row_so, column=1, value=p.id_poste).alignment = align_center
        cod_so_poste = f"DT{p.altura}{p.esforco}" if p.altura > 0 else ""
        ws_sisorca.cell(row=row_so, column=2, value=cod_so_poste).alignment = align_center
        ws_sisorca.cell(row=row_so, column=3, value="").alignment = align_center

        for idx_e in range(5):
            val_e = p.estruturas[idx_e] if idx_e < len(p.estruturas) else ""
            ws_sisorca.cell(row=row_so, column=4 + idx_e, value=val_e).alignment = align_center

        ws_sisorca.cell(row=row_so, column=9, value="").alignment = align_center

        tem_ater = any("ATER" in str(eq).upper() for eq in p.equipamentos)
        tem_dae = any("DAE" in str(eq).upper() for eq in p.equipamentos)
        ws_sisorca.cell(row=row_so, column=10, value="SIM" if tem_ater else "").alignment = align_center
        ws_sisorca.cell(row=row_so, column=11, value="SIM" if tem_dae else "").alignment = align_center

        for ci in range(1, 12):
            ws_sisorca.cell(row=row_so, column=ci).font = font_body
            ws_sisorca.cell(row=row_so, column=ci).border = thin_border
        row_so += 1

    # Aba legada de compatibilidade
    ws_banco = wb.create_sheet(title="BANCO DE PREÇOS")
    ws_banco.views.sheetView[0].showGridLines = True
    ws_banco.cell(row=1, column=1, value="Código").font = font_bold
    ws_banco.cell(row=1, column=2, value="Descrição").font = font_bold
    ws_banco.cell(row=1, column=3, value="Preço Unit. (R$)").font = font_bold
    for r_idx, mat in enumerate(materiais[:50], start=2):
        ws_banco.cell(row=r_idx, column=1, value=mat.codigo)
        ws_banco.cell(row=r_idx, column=2, value=mat.descricao)
        ws_banco.cell(row=r_idx, column=3, value=mat.preco_unitario).number_format = 'R$ #,##0.00'

    # Auto-ajuste de colunas para todas as abas
    for ws in [ws_resumo, ws_mo, ws_postes, ws_cabos, ws_sisorca, ws_banco]:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or '')
                if cell.row > 1 and len(val) > max_len and not cell.coordinate in ws.merged_cells:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    os.makedirs(os.path.dirname(os.path.abspath(caminho_saida)), exist_ok=True)
    wb.save(caminho_saida)
    wb.close()
    return caminho_saida
