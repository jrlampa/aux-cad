"""
Módulo de Exportação e Formatação da Planilha de Orçamento e Levantamento de Materiais.
Gera planilha Excel (.xlsx) profissional com 4 abas estruturadas, fórmulas atômicas e estilos de engenharia.
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from orcamento_core import CaboItem, MaterialResumo, PosteItem, carregar_catalogo


def exportar_planilha_orcamento(
    dados_processados: Dict[str, Any],
    caminho_saida: str,
    num_projeto: str = "PROJETO PADRÃO",
    municipio: str = "RIO DE JANEIRO - RJ",
    projetista: str = "ENG. PROJETISTA"
) -> str:
    """
    Gera pasta de trabalho Excel completa (.xlsx) a partir dos dados consolidados de materiais.
    """
    wb = openpyxl.Workbook()

    # Cores e Estilos Padrão
    cor_azul_escuro = "1B365D"
    cor_azul_medio = "2C5E8A"
    cor_cinza_claro = "F4F6F9"
    cor_borda = "D0D5DD"

    fill_header = PatternFill(start_color=cor_azul_escuro, end_color=cor_azul_escuro, fill_type="solid")
    fill_sub = PatternFill(start_color=cor_azul_medio, end_color=cor_azul_medio, fill_type="solid")
    fill_zebra = PatternFill(start_color=cor_cinza_claro, end_color=cor_cinza_claro, fill_type="solid")

    font_title = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Segoe UI", size=10, bold=True)
    font_body = Font(name="Segoe UI", size=10)

    thin_border = Border(
        left=Side(style='thin', color=cor_borda),
        right=Side(style='thin', color=cor_borda),
        top=Side(style='thin', color=cor_borda),
        bottom=Side(style='thin', color=cor_borda)
    )

    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    # =========================================================
    # ABA 1: RESUMO ORÇAMENTO
    # =========================================================
    ws_resumo = wb.active
    ws_resumo.title = "RESUMO ORÇAMENTO"
    ws_resumo.views.sheetView[0].showGridLines = True

    # Cabeçalho da Obra
    ws_resumo.merge_cells("A1:G1")
    ws_resumo["A1"] = "LEVANTAMENTO QUANTITATIVO E ORÇAMENTO DE MATERIAIS"
    ws_resumo["A1"].font = font_title
    ws_resumo["A1"].fill = fill_header
    ws_resumo["A1"].alignment = align_center
    ws_resumo.row_dimensions[1].height = 32

    meta_info = [
        ("Número do Projeto / Ordem:", num_projeto, "Data de Emissão:", datetime.now().strftime("%d/%m/%Y")),
        ("Município / Estado:", municipio, "Responsável Técnico:", projetista)
    ]

    for idx_row, row_data in enumerate(meta_info, start=2):
        ws_resumo.cell(row=idx_row, column=1, value=row_data[0]).font = font_bold
        ws_resumo.cell(row=idx_row, column=2, value=row_data[1]).font = font_body
        ws_resumo.cell(row=idx_row, column=4, value=row_data[2]).font = font_bold
        ws_resumo.cell(row=idx_row, column=5, value=row_data[3]).font = font_body
        ws_resumo.row_dimensions[idx_row].height = 20

    # Tabela de Materiais
    headers_resumo = ["Item", "Código", "Descrição do Material / Equipamento", "Unid.", "Qtd. Total", "Preço Unit. (R$)", "Total (R$)"]
    header_row = 5
    ws_resumo.row_dimensions[header_row].height = 25

    for col_idx, h in enumerate(headers_resumo, start=1):
        c = ws_resumo.cell(row=header_row, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_sub
        c.alignment = align_center
        c.border = thin_border

    linha_atual = header_row + 1
    materiais = dados_processados.get("materiais", [])

    for idx, mat in enumerate(materiais, start=1):
        ws_resumo.cell(row=linha_atual, column=1, value=idx).alignment = align_center
        ws_resumo.cell(row=linha_atual, column=2, value=mat.codigo).alignment = align_center
        ws_resumo.cell(row=linha_atual, column=3, value=mat.descricao).alignment = align_left
        ws_resumo.cell(row=linha_atual, column=4, value=mat.unidade).alignment = align_center
        
        # Quantidade formatada
        c_qtd = ws_resumo.cell(row=linha_atual, column=5, value=mat.quantidade)
        c_qtd.alignment = align_right
        c_qtd.number_format = '#,##0.00' if mat.unidade == 'M' else '#,##0'

        # Preço Unitário
        c_un = ws_resumo.cell(row=linha_atual, column=6, value=mat.preco_unitario)
        c_un.alignment = align_right
        c_un.number_format = 'R$ #,##0.00'

        # Total calculado por fórmula do Excel
        c_tot = ws_resumo.cell(row=linha_atual, column=7, value=f"=E{linha_atual}*F{linha_atual}")
        c_tot.alignment = align_right
        c_tot.font = font_bold
        c_tot.number_format = 'R$ #,##0.00'

        # Zebra striping
        if idx % 2 == 0:
            for c_idx in range(1, 8):
                ws_resumo.cell(row=linha_atual, column=c_idx).fill = fill_zebra

        for c_idx in range(1, 8):
            ws_resumo.cell(row=linha_atual, column=c_idx).border = thin_border
            if c_idx not in (1, 7):
                ws_resumo.cell(row=linha_atual, column=c_idx).font = font_body

        ws_resumo.row_dimensions[linha_atual].height = 20
        linha_atual += 1

    # Linha de Total Geral
    ws_resumo.merge_cells(start_row=linha_atual, start_column=1, end_row=linha_atual, end_column=6)
    c_tot_label = ws_resumo.cell(row=linha_atual, column=1, value="VALOR TOTAL ORÇADO DOS MATERIAIS:")
    c_tot_label.font = font_bold
    c_tot_label.alignment = align_right
    c_tot_label.fill = fill_zebra

    c_tot_val = ws_resumo.cell(row=linha_atual, column=7, value=f"=SUM(G6:G{linha_atual-1})")
    c_tot_val.font = Font(name="Segoe UI", size=11, bold=True, color="1B365D")
    c_tot_val.alignment = align_right
    c_tot_val.number_format = 'R$ #,##0.00'
    c_tot_val.fill = fill_zebra

    for c_idx in range(1, 8):
        ws_resumo.cell(row=linha_atual, column=c_idx).border = thin_border

    ws_resumo.row_dimensions[linha_atual].height = 25

    # =========================================================
    # ABA 2: DETALHAMENTO POSTES
    # =========================================================
    ws_postes = wb.create_sheet(title="DETALHAMENTO POSTES")
    ws_postes.views.sheetView[0].showGridLines = True
    headers_postes = ["ID Poste", "Nome do Bloco", "Altura (m)", "Esforço (daN)", "Layer CAD", "Coord. X (UTM)", "Coord. Y (UTM)", "Classificação Material"]
    
    ws_postes.row_dimensions[1].height = 25
    for col_idx, h in enumerate(headers_postes, start=1):
        c = ws_postes.cell(row=1, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_sub
        c.alignment = align_center
        c.border = thin_border

    postes: list[PosteItem] = dados_processados.get("postes", [])
    for row_idx, p in enumerate(postes, start=2):
        ws_postes.cell(row=row_idx, column=1, value=p.id_poste).alignment = align_center
        ws_postes.cell(row=row_idx, column=2, value=p.nome_bloco).alignment = align_left
        ws_postes.cell(row=row_idx, column=3, value=p.altura).alignment = align_center
        ws_postes.cell(row=row_idx, column=4, value=p.esforco).alignment = align_center
        ws_postes.cell(row=row_idx, column=5, value=p.layer).alignment = align_left
        
        cX = ws_postes.cell(row=row_idx, column=6, value=p.x)
        cX.alignment = align_right
        cX.number_format = '#,##0.00'
        
        cY = ws_postes.cell(row=row_idx, column=7, value=p.y)
        cY.alignment = align_right
        cY.number_format = '#,##0.00'
        
        ws_postes.cell(row=row_idx, column=8, value=p.material_chave).alignment = align_left

        for c_idx in range(1, 9):
            ws_postes.cell(row=row_idx, column=c_idx).border = thin_border
            ws_postes.cell(row=row_idx, column=c_idx).font = font_body
            if row_idx % 2 == 1:
                ws_postes.cell(row=row_idx, column=c_idx).fill = fill_zebra
        ws_postes.row_dimensions[row_idx].height = 19

    # =========================================================
    # ABA 3: DETALHAMENTO CABOS
    # =========================================================
    ws_cabos = wb.create_sheet(title="DETALHAMENTO CABOS")
    ws_cabos.views.sheetView[0].showGridLines = True
    headers_cabos = ["ID Trecho", "Layer CAD", "Tensão", "Qtd. Vãos", "Comp. CAD (m)", "Margem Flecha (%)", "Comp. Orçado (m)", "Material Atribuído"]

    ws_cabos.row_dimensions[1].height = 25
    for col_idx, h in enumerate(headers_cabos, start=1):
        c = ws_cabos.cell(row=1, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_sub
        c.alignment = align_center
        c.border = thin_border

    cabos: list[CaboItem] = dados_processados.get("cabos", [])
    for row_idx, cab in enumerate(cabos, start=2):
        ws_cabos.cell(row=row_idx, column=1, value=cab.id_cabo).alignment = align_center
        ws_cabos.cell(row=row_idx, column=2, value=cab.layer).alignment = align_left
        ws_cabos.cell(row=row_idx, column=3, value=cab.tensao).alignment = align_center
        ws_cabos.cell(row=row_idx, column=4, value=cab.vaos).alignment = align_center
        
        cCad = ws_cabos.cell(row=row_idx, column=5, value=cab.comprimento_cad)
        cCad.alignment = align_right
        cCad.number_format = '#,##0.00'

        cMarg = ws_cabos.cell(row=row_idx, column=6, value=f"{cab.margem_pct:.1f}%")
        cMarg.alignment = align_center

        cOrc = ws_cabos.cell(row=row_idx, column=7, value=cab.comprimento_orcado)
        cOrc.alignment = align_right
        cOrc.number_format = '#,##0.00'
        cOrc.font = font_bold

        ws_cabos.cell(row=row_idx, column=8, value=cab.descricao).alignment = align_left

        for c_idx in range(1, 9):
            ws_cabos.cell(row=row_idx, column=c_idx).border = thin_border
            ws_cabos.cell(row=row_idx, column=c_idx).font = font_body
            if row_idx % 2 == 1:
                ws_cabos.cell(row=row_idx, column=c_idx).fill = fill_zebra
        ws_cabos.row_dimensions[row_idx].height = 19

    # =========================================================
    # ABA 4: BANCO DE PREÇOS
    # =========================================================
    ws_banco = wb.create_sheet(title="BANCO DE PREÇOS")
    ws_banco.views.sheetView[0].showGridLines = True
    headers_banco = ["Chave Interna", "Código", "Descrição Técnica", "Unidade", "Preço Unitário (R$)", "Categoria"]

    ws_banco.row_dimensions[1].height = 25
    for col_idx, h in enumerate(headers_banco, start=1):
        c = ws_banco.cell(row=1, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_sub
        c.alignment = align_center
        c.border = thin_border

    catalogo = carregar_catalogo()
    for row_idx, (k, item) in enumerate(catalogo.items(), start=2):
        ws_banco.cell(row=row_idx, column=1, value=k).alignment = align_left
        ws_banco.cell(row=row_idx, column=2, value=item.get("codigo", "")).alignment = align_center
        ws_banco.cell(row=row_idx, column=3, value=item.get("descricao", "")).alignment = align_left
        ws_banco.cell(row=row_idx, column=4, value=item.get("unidade", "")).alignment = align_center
        
        cPreco = ws_banco.cell(row=row_idx, column=5, value=float(item.get("preco_unitario", 0.0)))
        cPreco.alignment = align_right
        cPreco.number_format = 'R$ #,##0.00'

        ws_banco.cell(row=row_idx, column=6, value=item.get("categoria", "")).alignment = align_left

        for c_idx in range(1, 7):
            ws_banco.cell(row=row_idx, column=c_idx).border = thin_border
            ws_banco.cell(row=row_idx, column=c_idx).font = font_body
            if row_idx % 2 == 1:
                ws_banco.cell(row=row_idx, column=c_idx).fill = fill_zebra
        ws_banco.row_dimensions[row_idx].height = 19

    # Auto-ajuste de largura de colunas em todas as abas
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if val_str.startswith("="):
                    val_str = "R$ 999.999,99"
                max_len = max(max_len, len(val_str))
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Cria diretório de destino se não existir
    os.makedirs(os.path.dirname(os.path.abspath(caminho_saida)), exist_ok=True)
    wb.save(caminho_saida)
    return caminho_saida
