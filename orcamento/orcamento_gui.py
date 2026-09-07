"""
Interface Gráfica Interativa para o Módulo de Orçamento e Levantamento de Materiais.
Permite visualização em tempo real, ajuste de margem de flechas, edição de custos unitários e exportação Excel.
100% em pt-BR.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.abspath(os.path.join(_curr_dir, ".."))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from orcamento_core import processar_dados_orcamento
from orcamento_excel import exportar_planilha_orcamento


class OrcamentoGUI(tk.Tk):
    """Interface principal para conferência e emissão do orçamento de materiais."""

    def __init__(self, dados_cad_iniciais: Optional[Dict[str, Any]] = None, caminho_arquivo_cad: Optional[str] = None):
        super().__init__()

        self.title("AUX CAD - Orçamento e Levantamento Automático de Materiais")
        self.geometry("980x680")
        self.minsize(850, 550)

        self.dados_cad = dados_cad_iniciais or {"postes": [], "cabos": [], "estruturas": [], "equipamentos": []}
        self.caminho_arquivo_cad = caminho_arquivo_cad
        self.margem_cabo_var = tk.DoubleVar(value=5.0)
        self.num_projeto_var = tk.StringVar(value="PROJ-001/2026")
        self.municipio_var = tk.StringVar(value="RIO DE JANEIRO - RJ")
        self.projetista_var = tk.StringVar(value="ENG. PROJETISTA")
        self.filtro_categoria_var = tk.StringVar(value="Todos")
        self.caminho_excel_gerado = ""

        self.dados_processados: Dict[str, Any] = {}

        self._configurar_estilos()
        self._criar_widgets()
        self.recalcular()

    def _configurar_estilos(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#E2E8F0")
        self.style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        self.style.map("Treeview", background=[("selected", "#2C5E8A")])

    def _criar_widgets(self):
        # 1. Painel Superior: Dados do Projeto e Indicadores
        top_frame = ttk.LabelFrame(self, text=" Dados do Projeto & Parâmetros ", padding=10)
        top_frame.pack(fill="x", padx=12, pady=6)

        # Linha 1 de metadados
        ttk.Label(top_frame, text="Nº Projeto / OS:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(top_frame, textvariable=self.num_projeto_var, width=18).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(top_frame, text="Município / UF:").grid(row=0, column=2, sticky="w", padx=8, pady=2)
        ttk.Entry(top_frame, textvariable=self.municipio_var, width=22).grid(row=0, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(top_frame, text="Responsável Técnico:").grid(row=0, column=4, sticky="w", padx=8, pady=2)
        ttk.Entry(top_frame, textvariable=self.projetista_var, width=22).grid(row=0, column=5, sticky="w", padx=4, pady=2)

        # Linha 2 de controles: Margem de Cabos
        ttk.Label(top_frame, text="Margem Flecha Cabos:").grid(row=1, column=0, sticky="w", padx=4, pady=6)
        scale_frame = ttk.Frame(top_frame)
        scale_frame.grid(row=1, column=1, columnspan=3, sticky="w", padx=4, pady=6)

        self.scale_margem = ttk.Scale(
            scale_frame, from_=0.0, to=15.0, variable=self.margem_cabo_var,
            orient="horizontal", length=180, command=lambda v: self.recalcular()
        )
        self.scale_margem.pack(side="left", padx=4)
        self.lbl_margem = ttk.Label(scale_frame, text="5.0%", width=6)
        self.lbl_margem.pack(side="left")

        # 2. Painel de Indicadores Principais (KPIs)
        kpi_frame = ttk.Frame(self, padding=4)
        kpi_frame.pack(fill="x", padx=12, pady=4)

        self.card_postes = self._criar_card_kpi(kpi_frame, "POSTES", "0 un", "#2C5E8A")
        self.card_cabos = self._criar_card_kpi(kpi_frame, "EXTENSÃO CABOS", "0.0 m", "#1E824C")
        self.card_itens = self._criar_card_kpi(kpi_frame, "ITENS DISTINTOS", "0", "#6C7A89")
        self.card_total = self._criar_card_kpi(kpi_frame, "VALOR ESTIMADO", "R$ 0,00", "#96281B")

        self.card_postes.pack(side="left", fill="both", expand=True, padx=4)
        self.card_cabos.pack(side="left", fill="both", expand=True, padx=4)
        self.card_itens.pack(side="left", fill="both", expand=True, padx=4)
        self.card_total.pack(side="left", fill="both", expand=True, padx=4)

        # 3. Painel de Filtro e Ações na Tabela
        filter_frame = ttk.Frame(self, padding=4)
        filter_frame.pack(fill="x", padx=12, pady=2)

        ttk.Label(filter_frame, text="Filtrar por Categoria:").pack(side="left", padx=4)
        categorias = ["Todos", "Postes", "Condutores", "Estruturas", "Equipamentos", "Acessórios"]
        cb_cat = ttk.Combobox(filter_frame, values=categorias, textvariable=self.filtro_categoria_var, state="readonly", width=16)
        cb_cat.pack(side="left", padx=4)
        cb_cat.bind("<<ComboboxSelected>>", lambda e: self._atualizar_tabela())

        btn_add = ttk.Button(filter_frame, text="+ Inserir Item Manual", command=self._adicionar_item_manual)
        btn_add.pack(side="right", padx=4)

        # 4. Tabela de Materiais (Treeview)
        table_frame = ttk.Frame(self, padding=2)
        table_frame.pack(fill="both", expand=True, padx=12, pady=4)

        colunas = ("codigo", "descricao", "categoria", "unidade", "quantidade", "preco_un", "total")
        self.tree = ttk.Treeview(table_frame, columns=colunas, show="headings", selectmode="browse")

        self.tree.heading("codigo", text="Código")
        self.tree.heading("descricao", text="Descrição do Material / Equipamento")
        self.tree.heading("categoria", text="Categoria")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("quantidade", text="Qtd.")
        self.tree.heading("preco_un", text="Preço Unit. (R$)")
        self.tree.heading("total", text="Total (R$)")

        self.tree.column("codigo", width=85, anchor="center")
        self.tree.column("descricao", width=380, anchor="w")
        self.tree.column("categoria", width=100, anchor="center")
        self.tree.column("unidade", width=50, anchor="center")
        self.tree.column("quantidade", width=80, anchor="e")
        self.tree.column("preco_un", width=100, anchor="e")
        self.tree.column("total", width=110, anchor="e")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 5. Barra Inferior com Botões de Ação
        bottom_frame = ttk.Frame(self, padding=8)
        bottom_frame.pack(fill="x", padx=12, pady=6)

        btn_exportar = tk.Button(
            bottom_frame, text="📊 Gerar Planilha Orçamentária (.xlsx)",
            bg="#1B365D", fg="white", font=("Segoe UI", 10, "bold"),
            padx=14, pady=6, cursor="hand2", command=self.gerar_planilha
        )
        btn_exportar.pack(side="right", padx=6)

        self.btn_abrir = tk.Button(
            bottom_frame, text="Abrir no Excel",
            bg="#E2E8F0", fg="#1E293B", font=("Segoe UI", 9),
            padx=10, pady=6, state="disabled", cursor="hand2", command=self.abrir_no_excel
        )
        self.btn_abrir.pack(side="right", padx=6)

        btn_fechar = ttk.Button(bottom_frame, text="Fechar", command=self.destroy)
        btn_fechar.pack(side="left", padx=4)

    def _criar_card_kpi(self, parent: ttk.Frame, titulo: str, valor_padrao: str, cor_destaque: str) -> tk.Frame:
        card = tk.Frame(parent, bg="#FFFFFF", relief="solid", bd=1, padx=8, pady=6)
        lbl_tit = tk.Label(card, text=titulo, font=("Segoe UI", 8, "bold"), fg="#64748B", bg="#FFFFFF")
        lbl_tit.pack(anchor="w")
        lbl_val = tk.Label(card, text=valor_padrao, font=("Segoe UI", 13, "bold"), fg=cor_destaque, bg="#FFFFFF")
        lbl_val.pack(anchor="w", pady=2)
        card.lbl_val = lbl_val  # type: ignore
        return card

    def recalcular(self):
        """Recalcula todos os materiais analiticamente com a margem atual."""
        margem = self.margem_cabo_var.get()
        self.lbl_margem.config(text=f"{margem:.1f}%")
        self.dados_processados = processar_dados_orcamento(self.dados_cad, margem_cabos_pct=margem)

        # Atualiza KPIs
        qtd_postes = self.dados_processados.get("qtd_postes", 0)
        extensao = self.dados_processados.get("extensao_total_m", 0.0)
        materiais = self.dados_processados.get("materiais", [])
        total = self.dados_processados.get("total_geral", 0.0)

        self.card_postes.lbl_val.config(text=f"{qtd_postes} un")  # type: ignore
        self.card_cabos.lbl_val.config(text=f"{extensao:,.1f} m".replace(",", "X").replace(".", ",").replace("X", "."))  # type: ignore
        self.card_itens.lbl_val.config(text=str(len(materiais)))  # type: ignore
        self.card_total.lbl_val.config(text=f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))  # type: ignore

        self._atualizar_tabela()

    def _atualizar_tabela(self):
        self.tree.delete(*self.tree.get_children())
        filtro = self.filtro_categoria_var.get()
        materiais = self.dados_processados.get("materiais", [])

        for mat in materiais:
            if filtro != "Todos" and mat.categoria != filtro:
                continue

            qtd_fmt = f"{mat.quantidade:,.2f}" if mat.unidade == 'M' else f"{int(mat.quantidade)}"
            preco_fmt = f"R$ {mat.preco_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            total_fmt = f"R$ {mat.preco_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            self.tree.insert("", "end", values=(
                mat.codigo,
                mat.descricao,
                mat.categoria,
                mat.unidade,
                qtd_fmt,
                preco_fmt,
                total_fmt
            ))

    def _adicionar_item_manual(self):
        """Janela modal para inserção manual de um item fora do DWG."""
        dlg = tk.Toplevel(self)
        dlg.title("Inserir Item Manual")
        dlg.geometry("380x280")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text="Descrição do Item:").pack(anchor="w", padx=16, pady=4)
        e_desc = ttk.Entry(dlg, width=38)
        e_desc.pack(padx=16, pady=2)

        ttk.Label(dlg, text="Unidade (UN, M, CJ):").pack(anchor="w", padx=16, pady=4)
        e_un = ttk.Entry(dlg, width=12)
        e_un.insert(0, "UN")
        e_un.pack(anchor="w", padx=16, pady=2)

        ttk.Label(dlg, text="Quantidade:").pack(anchor="w", padx=16, pady=4)
        e_qtd = ttk.Entry(dlg, width=12)
        e_qtd.insert(0, "1")
        e_qtd.pack(anchor="w", padx=16, pady=2)

        ttk.Label(dlg, text="Preço Unitário (R$):").pack(anchor="w", padx=16, pady=4)
        e_pr = ttk.Entry(dlg, width=12)
        e_pr.insert(0, "0.00")
        e_pr.pack(anchor="w", padx=16, pady=2)

        def salvar():
            desc = e_desc.get().strip()
            if not desc:
                return
            try:
                qtd = float(e_qtd.get().replace(",", "."))
                pr = float(e_pr.get().replace(",", "."))
            except ValueError:
                messagebox.showerror("Valor Inválido", "Quantidade e Preço devem ser números válidos.")
                return

            self.dados_cad.setdefault("equipamentos", []).append({
                "id": "MANUAL",
                "tipo": desc,
                "preco": pr,
                "qtd": qtd
            })
            dlg.destroy()
            self.recalcular()

        ttk.Button(dlg, text="Adicionar", command=salvar).pack(pady=12)

    def gerar_planilha(self):
        """Exporta os dados consolidados para o arquivo Excel .xlsx."""
        padrao_nome = f"ORCAMENTO_{self.num_projeto_var.get().replace('/', '_')}.xlsx"
        caminho_salvar = filedialog.asksaveasfilename(
            title="Salvar Planilha de Orçamento",
            initialfile=padrao_nome,
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel", "*.xlsx")]
        )
        if not caminho_salvar:
            return

        try:
            exportar_planilha_orcamento(
                dados_processados=self.dados_processados,
                caminho_saida=caminho_salvar,
                num_projeto=self.num_projeto_var.get(),
                municipio=self.municipio_var.get(),
                projetista=self.projetista_var.get()
            )
            self.caminho_excel_gerado = caminho_salvar
            self.btn_abrir.config(state="normal", bg="#1E824C", fg="white")
            messagebox.showinfo("Sucesso", f"Planilha gerada com sucesso!\n\nArquivo:\n{caminho_salvar}")
        except Exception as e:
            messagebox.showerror("Erro ao Exportar", f"Não foi possível gerar a planilha:\n{e}")

    def abrir_no_excel(self):
        if self.caminho_excel_gerado and os.path.exists(self.caminho_excel_gerado):
            if os.name == "nt":
                os.startfile(self.caminho_excel_gerado)
            else:
                subprocess.Popen(["xdg-open", self.caminho_excel_gerado])
