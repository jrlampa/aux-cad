"""
Interface Gráfica Interativa para o Módulo de Orçamento e Levantamento de Materiais.
Visualização em tempo real com suporte a seleção de Empreiteira (Indica, Engelmig, Dínamo, Progen),
Classe de Território (A, B, C), Ambiente Agressivo (Salinidade), explosão de kits e exportação Excel.
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
    """Interface principal para conferência e emissão do orçamento oficial de engenharia."""

    def __init__(self, dados_cad_iniciais: Optional[Dict[str, Any]] = None, caminho_arquivo_cad: Optional[str] = None):
        super().__init__()

        self.title("AUX CAD - Orçamento Executivo de Materiais & Mão de Obra")
        self.geometry("1020x720")
        self.minsize(900, 600)

        self.dados_cad = dados_cad_iniciais or {"postes": [], "cabos": [], "estruturas": [], "equipamentos": []}
        self.caminho_arquivo_cad = caminho_arquivo_cad

        # Variáveis de Controle
        self.margem_cabo_var = tk.DoubleVar(value=5.0)
        self.num_projeto_var = tk.StringVar(value="PE_001/2026")
        self.municipio_var = tk.StringVar(value="CAMPOS DOS GOYTACAZES - RJ")
        self.projetista_var = tk.StringVar(value="ENG. PROJETISTA")
        self.empreiteira_var = tk.StringVar(value="ENGELMIG")
        self.territorio_var = tk.StringVar(value="A")
        self.salinidade_var = tk.BooleanVar(value=False)
        self.visao_tabela_var = tk.StringVar(value="Materiais")
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
        # 1. Painel Superior: Metadados e Contrato
        top_frame = ttk.LabelFrame(self, text=" Dados do Projeto, Contrato & Território ", padding=8)
        top_frame.pack(fill="x", padx=12, pady=4)

        # Linha 1: Metadados do Projeto
        ttk.Label(top_frame, text="Nº Projeto:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(top_frame, textvariable=self.num_projeto_var, width=16).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(top_frame, text="Município / UF:").grid(row=0, column=2, sticky="w", padx=6, pady=2)
        ttk.Entry(top_frame, textvariable=self.municipio_var, width=24).grid(row=0, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(top_frame, text="Projetista:").grid(row=0, column=4, sticky="w", padx=6, pady=2)
        ttk.Entry(top_frame, textvariable=self.projetista_var, width=20).grid(row=0, column=5, sticky="w", padx=4, pady=2)

        # Linha 2: Empreiteira, Território e Salinidade
        ttk.Label(top_frame, text="Empreiteira / Região:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        emps = [("ENGELMIG (Itaperuna/Campos)", "ENGELMIG"), ("INDICA (Cantagalo/Pádua)", "INDICA"),
                ("DÍNAMO (Lagos)", "DÍNAMO"), ("PROGEN (Macaé)", "PROGEN")]
        self.cb_emp = ttk.Combobox(top_frame, values=[e[0] for e in emps], state="readonly", width=24)
        self.cb_emp.current(0)
        self.cb_emp.grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=4)
        self.cb_emp.bind("<<ComboboxSelected>>", self._on_emp_changed)

        ttk.Label(top_frame, text="Território:").grid(row=1, column=3, sticky="w", padx=6, pady=4)
        terrs = ["Classe A (Normal)", "Classe B (Intermediário)", "Classe C (Dificultoso)"]
        self.cb_terr = ttk.Combobox(top_frame, values=terrs, state="readonly", width=18)
        self.cb_terr.current(0)
        self.cb_terr.grid(row=1, column=4, sticky="w", padx=4, pady=4)
        self.cb_terr.bind("<<ComboboxSelected>>", self._on_terr_changed)

        chk_sal = ttk.Checkbutton(top_frame, text="Ambiente Salino (Salinidade)", variable=self.salinidade_var, command=self.recalcular)
        chk_sal.grid(row=1, column=5, sticky="w", padx=6, pady=4)

        # Linha 3: Margem de Flecha de Cabos
        ttk.Label(top_frame, text="Margem Flecha Cabos:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        scale_frame = ttk.Frame(top_frame)
        scale_frame.grid(row=2, column=1, columnspan=3, sticky="w", padx=4, pady=2)

        self.scale_margem = ttk.Scale(
            scale_frame, from_=0.0, to=15.0, variable=self.margem_cabo_var,
            orient="horizontal", length=160, command=lambda v: self.recalcular()
        )
        self.scale_margem.pack(side="left", padx=4)
        self.lbl_margem = ttk.Label(scale_frame, text="5.0%", width=6)
        self.lbl_margem.pack(side="left")

        # 2. Painel de Indicadores Principais (KPIs)
        kpi_frame = ttk.Frame(self, padding=4)
        kpi_frame.pack(fill="x", padx=12, pady=4)

        self.card_mat = self._criar_card_kpi(kpi_frame, "📦 MATERIAIS (R$)", "R$ 0,00", "#1E824C")
        self.card_mo = self._criar_card_kpi(kpi_frame, "👷 MÃO DE OBRA (R$)", "R$ 0,00", "#8A532C")
        self.card_total = self._criar_card_kpi(kpi_frame, "💰 TOTAL DA OBRA (R$)", "R$ 0,00", "#1B365D")
        self.card_rede = self._criar_card_kpi(kpi_frame, "📍 POSTES / REDE DWG", "0 un / 0 m", "#475569")

        self.card_mat.pack(side="left", fill="both", expand=True, padx=4)
        self.card_mo.pack(side="left", fill="both", expand=True, padx=4)
        self.card_total.pack(side="left", fill="both", expand=True, padx=4)
        self.card_rede.pack(side="left", fill="both", expand=True, padx=4)

        # 3. Painel de Visão da Tabela (Materiais vs Mão de Obra)
        action_frame = ttk.Frame(self, padding=4)
        action_frame.pack(fill="x", padx=12, pady=2)

        ttk.Label(action_frame, text="Visualização:").pack(side="left", padx=4)
        self.btn_vis_mat = tk.Button(
            action_frame, text="📦 Materiais Orçados", bg="#1B365D", fg="white",
            font=("Segoe UI", 9, "bold"), padx=10, pady=2, command=lambda: self._set_visao("Materiais")
        )
        self.btn_vis_mat.pack(side="left", padx=2)

        self.btn_vis_mo = tk.Button(
            action_frame, text="👷 Mão de Obra Contratual", bg="#E2E8F0", fg="#1E293B",
            font=("Segoe UI", 9), padx=10, pady=2, command=lambda: self._set_visao("MaoDeObra")
        )
        self.btn_vis_mo.pack(side="left", padx=2)

        ttk.Label(action_frame, text="  |  Filtrar:").pack(side="left", padx=4)
        categorias = ["Todos", "Postes", "Condutores", "Estruturas", "Equipamentos"]
        self.cb_cat = ttk.Combobox(action_frame, values=categorias, textvariable=self.filtro_categoria_var, state="readonly", width=14)
        self.cb_cat.pack(side="left", padx=2)
        self.cb_cat.bind("<<ComboboxSelected>>", lambda e: self._atualizar_tabela())

        btn_add = ttk.Button(action_frame, text="+ Inserir Manual", command=self._adicionar_item_manual)
        btn_add.pack(side="right", padx=4)

        # 4. Tabela Principal (Treeview)
        table_frame = ttk.Frame(self, padding=2)
        table_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self.tree = ttk.Treeview(table_frame, show="headings", selectmode="browse")
        self.scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 5. Barra Inferior com Botões de Ação
        bottom_frame = ttk.Frame(self, padding=8)
        bottom_frame.pack(fill="x", padx=12, pady=4)

        btn_exportar = tk.Button(
            bottom_frame, text="📊 Gerar Planilha Oficial (.xlsx)",
            bg="#107C41", fg="white", font=("Segoe UI", 10, "bold"),
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
        lbl_val = tk.Label(card, text=valor_padrao, font=("Segoe UI", 12, "bold"), fg=cor_destaque, bg="#FFFFFF")
        lbl_val.pack(anchor="w", pady=2)
        card.lbl_val = lbl_val  # type: ignore
        return card

    def _on_emp_changed(self, event=None):
        val = self.cb_emp.get()
        emp_nome = "ENGELMIG"
        for prefix, key in [("ENGELMIG", "ENGELMIG"), ("INDICA", "INDICA"), ("DÍNAMO", "DÍNAMO"), ("PROGEN", "PROGEN")]:
            if prefix in val:
                emp_nome = key
                break
        self.empreiteira_var.set(emp_nome)
        self.recalcular()

    def _on_terr_changed(self, event=None):
        val = self.cb_terr.get()
        terr = "A" if "Classe A" in val else ("B" if "Classe B" in val else "C")
        self.territorio_var.set(terr)
        self.recalcular()

    def _set_visao(self, modo: str):
        self.visao_tabela_var.set(modo)
        if modo == "Materiais":
            self.btn_vis_mat.config(bg="#1B365D", fg="white", font=("Segoe UI", 9, "bold"))
            self.btn_vis_mo.config(bg="#E2E8F0", fg="#1E293B", font=("Segoe UI", 9))
            self.cb_cat.config(state="readonly")
        else:
            self.btn_vis_mo.config(bg="#8A532C", fg="white", font=("Segoe UI", 9, "bold"))
            self.btn_vis_mat.config(bg="#E2E8F0", fg="#1E293B", font=("Segoe UI", 9))
            self.cb_cat.config(state="disabled")
        self._atualizar_tabela()

    def recalcular(self):
        """Recalcula materiais e mão de obra com os parâmetros selecionados."""
        margem = self.margem_cabo_var.get()
        self.lbl_margem.config(text=f"{margem:.1f}%")
        amb = "AA" if self.salinidade_var.get() else "NA"

        self.dados_processados = processar_dados_orcamento(
            self.dados_cad,
            margem_cabos_pct=margem,
            empreiteira=self.empreiteira_var.get(),
            territorio=self.territorio_var.get(),
            ambiente=amb
        )

        total_mat = self.dados_processados.get("total_materiais", 0.0)
        total_mo = self.dados_processados.get("total_mao_de_obra", 0.0)
        total_geral = self.dados_processados.get("total_geral", 0.0)
        qtd_p = self.dados_processados.get("qtd_postes", 0)
        ext_m = self.dados_processados.get("extensao_total_m", 0.0)

        def fmt_br(v):
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        self.card_mat.lbl_val.config(text=fmt_br(total_mat))  # type: ignore
        self.card_mo.lbl_val.config(text=fmt_br(total_mo))  # type: ignore
        self.card_total.lbl_val.config(text=fmt_br(total_geral))  # type: ignore
        self.card_rede.lbl_val.config(text=f"{qtd_p} un / {ext_m:,.1f} m".replace(".", ","))  # type: ignore

        self._atualizar_tabela()

    def _atualizar_tabela(self):
        self.tree.delete(*self.tree.get_children())
        modo = self.visao_tabela_var.get()

        if modo == "Materiais":
            colunas = ("codigo", "descricao", "origem", "unidade", "quantidade", "preco_un", "total")
            self.tree["columns"] = colunas
            self.tree.heading("codigo", text="Código")
            self.tree.heading("descricao", text="Descrição do Material")
            self.tree.heading("origem", text="Origem / Kit")
            self.tree.heading("unidade", text="Unid.")
            self.tree.heading("quantidade", text="Qtd.")
            self.tree.heading("preco_un", text="Preço Unit. (R$)")
            self.tree.heading("total", text="Total (R$)")

            self.tree.column("codigo", width=85, anchor="center")
            self.tree.column("descricao", width=340, anchor="w")
            self.tree.column("origem", width=120, anchor="w")
            self.tree.column("unidade", width=50, anchor="center")
            self.tree.column("quantidade", width=70, anchor="e")
            self.tree.column("preco_un", width=95, anchor="e")
            self.tree.column("total", width=105, anchor="e")

            filtro = self.filtro_categoria_var.get()
            for mat in self.dados_processados.get("materiais", []):
                if filtro != "Todos" and mat.categoria != filtro:
                    continue
                qtd_fmt = f"{mat.quantidade:,.2f}" if mat.unidade == 'M' else f"{int(mat.quantidade)}"
                pr_fmt = f"R$ {mat.preco_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                tot_fmt = f"R$ {mat.preco_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self.tree.insert("", "end", values=(
                    mat.codigo, mat.descricao, mat.origem_kit or mat.categoria,
                    mat.unidade, qtd_fmt, pr_fmt, tot_fmt
                ))
        else:
            colunas = ("voz", "baremo", "descricao", "unidade", "quantidade", "custo_un", "total")
            self.tree["columns"] = colunas
            self.tree.heading("voz", text="Voz Contratual")
            self.tree.heading("baremo", text="Baremo SAP")
            self.tree.heading("descricao", text="Descrição do Serviço")
            self.tree.heading("unidade", text="Unid.")
            self.tree.heading("quantidade", text="Qtd.")
            self.tree.heading("custo_un", text="Custo Unit. (R$)")
            self.tree.heading("total", text="Total (R$)")

            self.tree.column("voz", width=90, anchor="center")
            self.tree.column("baremo", width=95, anchor="center")
            self.tree.column("descricao", width=380, anchor="w")
            self.tree.column("unidade", width=50, anchor="center")
            self.tree.column("quantidade", width=70, anchor="e")
            self.tree.column("custo_un", width=95, anchor="e")
            self.tree.column("total", width=110, anchor="e")

            for mo in self.dados_processados.get("mao_de_obra", []):
                qtd_fmt = f"{int(mo.quantidade)}" if mo.unidade == 'UN' else f"{mo.quantidade:,.2f}"
                c_fmt = f"R$ {mo.custo_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                tot_fmt = f"R$ {mo.custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self.tree.insert("", "end", values=(
                    mo.voz, mo.baremo, mo.descricao, mo.unidade, qtd_fmt, c_fmt, tot_fmt
                ))

    def _adicionar_item_manual(self):
        """Janela modal para inserção manual de material."""
        dlg = tk.Toplevel(self)
        dlg.title("Inserir Material Manual")
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
                "id": "MANUAL", "tipo": desc, "preco": pr, "qtd": qtd
            })
            dlg.destroy()
            self.recalcular()

        ttk.Button(dlg, text="Adicionar", command=salvar).pack(pady=12)

    def gerar_planilha(self):
        padrao_nome = f"ORCAMENTO_{self.num_projeto_var.get().replace('/', '_')}.xlsx"
        caminho_salvar = filedialog.asksaveasfilename(
            title="Salvar Planilha de Orçamento Oficial",
            initialfile=padrao_nome, defaultextension=".xlsx",
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
            self.btn_abrir.config(state="normal", bg="#107C41", fg="white")
            messagebox.showinfo("Sucesso", f"Planilha oficial gerada com sucesso!\n\nArquivo:\n{caminho_salvar}")
        except Exception as e:
            messagebox.showerror("Erro ao Exportar", f"Não foi possível gerar a planilha:\n{e}")

    def abrir_no_excel(self):
        if self.caminho_excel_gerado and os.path.exists(self.caminho_excel_gerado):
            if os.name == "nt":
                os.startfile(self.caminho_excel_gerado)
            else:
                subprocess.Popen(["xdg-open", self.caminho_excel_gerado])


if __name__ == "__main__":
    app = OrcamentoGUI()
    app.mainloop()
