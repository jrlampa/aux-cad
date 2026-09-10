"""cpfc_gui.py - Interface Gráfica Interativa para Preenchimento de CPFC (REN 1.059 ANEEL).
Design executivo #1B365D, Live Preview de ERD/COP/PF, salvamento interativo de planilha."""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Dict, Any

from cpfc.cpfc_core import (
    DadosCadastrais,
    OrcamentoObra,
    ParametrosDemanda,
    ResultadoCPFC,
    calcular_cpfc,
    SUBGRUPOS_LOOKUP,
    TIPOS_LIGACAO_PADRAO,
    ORIGENS_ORCAMENTO_PADRAO,
)
from cpfc.cpfc_excel import preencher_e_salvar_cpfc
from cpfc.cpfc_guia_ren1059 import exibir_modal_guia_ren1059
from cpfc.cpfc_notas import exibir_modal_notas_cpfc


class CPFCManagerGUI(tk.Tk):
    """Janela principal para preenchimento e cálculo do CPFC."""

    def __init__(
        self,
        projeto_inicial: str = "A057032667",
        pasta_padrao: Optional[str] = None,
        dados_iniciais: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.title("AUX CAD - Cálculo de Participação Financeira (REN 1.059 ANEEL)")
        self.geometry("960x780")
        self.minsize(880, 680)
        self.configure(bg="#F1F5F9")

        self.pasta_destino_sugerida = pasta_padrao or os.getcwd()
        self.ultimo_arquivo_salvo: Optional[str] = None
        self._custom_dem_erd: bool = False

        # Estilos TTK
        self._configurar_estilos()

        # Construção da interface
        self._criar_cabecalho()
        self._criar_corpo_com_rolagem()
        self._criar_rodape_acoes()

        # Inicialização dos dados
        self._preencher_dados_iniciais(projeto_inicial, dados_iniciais)
        self._calcular_em_tempo_real()

    def _configurar_estilos(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # Configurações de fontes e cores
        self.style.configure(".", font=("Segoe UI", 9), background="#F1F5F9")
        self.style.configure("TLabel", background="#FFFFFF", foreground="#1E293B")
        self.style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#1B365D", background="#FFFFFF")
        self.style.configure("Card.TFrame", background="#FFFFFF", relief="solid", borderwidth=1)
        self.style.configure("TCombobox", padding=4)
        self.style.configure("TEntry", padding=4)

    def _criar_cabecalho(self):
        header_frame = tk.Frame(self, bg="#1B365D", height=70, padx=20, pady=12)
        header_frame.pack(fill=tk.X, side=tk.TOP)

        left_box = tk.Frame(header_frame, bg="#1B365D")
        left_box.pack(side=tk.LEFT, fill=tk.Y)

        lbl_titulo = tk.Label(
            left_box,
            text="💰 Participação Financeira do Consumidor (CPFC)",
            font=("Segoe UI", 14, "bold"),
            bg="#1B365D",
            fg="#FFFFFF",
        )
        lbl_titulo.pack(anchor="w")

        lbl_sub = tk.Label(
            left_box,
            text="Resolução Normativa ANEEL Nº 1.059 | Preenchimento Oficial de Planilha de Distribuição",
            font=("Segoe UI", 9),
            bg="#1B365D",
            fg="#94A3B8",
        )
        lbl_sub.pack(anchor="w")

        btn_guia = tk.Button(
            header_frame,
            text="📘 Regras REN 1.059",
            font=("Segoe UI", 9, "bold"),
            bg="#0D8269",
            fg="#FFFFFF",
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
            command=lambda: exibir_modal_guia_ren1059(self),
        )
        btn_guia.pack(side=tk.RIGHT, pady=4)

        btn_notas = tk.Button(
            header_frame,
            text="📋 Notas p/ Desenho (CPFC)",
            font=("Segoe UI", 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
            command=self._abrir_notas_desenho,
        )
        btn_notas.pack(side=tk.RIGHT, padx=(0, 8), pady=4)

    def _abrir_notas_desenho(self):
        num_proj = self.ent_projeto.get().strip() if hasattr(self, "ent_projeto") else ""
        exibir_modal_notas_cpfc(self, self.pasta_destino_sugerida, num_proj)

    def _criar_corpo_com_rolagem(self):
        container = tk.Frame(self, bg="#F1F5F9")
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        canvas = tk.Canvas(container, bg="#F1F5F9", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg="#F1F5F9")

        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas_window = canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        def _on_canvas_resize(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Suporte a mousewheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 1. Card Dados do Projeto
        self._criar_card_projeto(self.scrollable_frame)

        # 2. Card Orçamento da Obra
        self._criar_card_orcamento(self.scrollable_frame)

        # 3. Card Demandas Elétricas
        self._criar_card_demandas(self.scrollable_frame)

        # 4. Card Live Preview de Resultados
        self._criar_card_resultados(self.scrollable_frame)

    def _criar_card_projeto(self, parent):
        card = tk.Frame(parent, bg="#FFFFFF", padx=16, pady=12, highlightbackground="#CBD5E1", highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card, text="1. Dados Cadastrais do Projeto", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#1B365D").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        # Projeto Nº e Município
        tk.Label(card, text="Número do Projeto/Ordem:", bg="#FFFFFF").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.ent_projeto = ttk.Entry(card, width=22)
        self.ent_projeto.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.ent_projeto.bind("<KeyRelease>", lambda e: self._calcular_em_tempo_real())

        tk.Label(card, text="Município:", bg="#FFFFFF").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.ent_municipio = ttk.Entry(card, width=24)
        self.ent_municipio.grid(row=1, column=3, sticky="ew", padx=4, pady=4)

        # Endereço
        tk.Label(card, text="Endereço da Obra:", bg="#FFFFFF").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.ent_endereco = ttk.Entry(card)
        self.ent_endereco.grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=4)

        # Tipo de Ligação e Subgrupo
        tk.Label(card, text="Tipo de Ligação:", bg="#FFFFFF").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.cb_tipo_ligacao = ttk.Combobox(card, values=TIPOS_LIGACAO_PADRAO, state="readonly")
        self.cb_tipo_ligacao.grid(row=3, column=1, sticky="ew", padx=4, pady=4)

        tk.Label(card, text="Subgrupo Tarifário:", bg="#FFFFFF").grid(row=3, column=2, sticky="w", padx=4, pady=4)
        self.cb_subgrupo = ttk.Combobox(card, values=list(SUBGRUPOS_LOOKUP.keys()), state="readonly", width=28)
        self.cb_subgrupo.grid(row=3, column=3, sticky="ew", padx=4, pady=4)
        self.cb_subgrupo.bind("<<ComboboxSelected>>", lambda e: self._calcular_em_tempo_real())

        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

    def _criar_card_orcamento(self, parent):
        card = tk.Frame(parent, bg="#FFFFFF", padx=16, pady=12, highlightbackground="#CBD5E1", highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card, text="2. Orçamento e Custos da Obra (R$)", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#1B365D").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(card, text="Origem do Orçamento:", bg="#FFFFFF").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.cb_origem = ttk.Combobox(card, values=ORIGENS_ORCAMENTO_PADRAO, state="readonly", width=18)
        self.cb_origem.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        tk.Label(card, text="Serviço de Terceiros (R$):", bg="#FFFFFF").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.ent_terceiros = ttk.Entry(card, width=20)
        self.ent_terceiros.grid(row=1, column=3, sticky="w", padx=4, pady=4)
        self.ent_terceiros.bind("<KeyRelease>", lambda e: self._calcular_em_tempo_real())

        tk.Label(card, text="Material da Obra (R$):", bg="#FFFFFF").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.ent_material = ttk.Entry(card, width=20)
        self.ent_material.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.ent_material.bind("<KeyRelease>", lambda e: self._calcular_em_tempo_real())

        tk.Label(card, text="Custo Total da Obra:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF").grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.lbl_total_obra = tk.Label(card, text="R$ 0,00", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#0284C7")
        self.lbl_total_obra.grid(row=2, column=3, sticky="w", padx=4, pady=4)

        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

    def _criar_card_demandas(self, parent):
        card = tk.Frame(parent, bg="#FFFFFF", padx=16, pady=12, highlightbackground="#CBD5E1", highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card, text="3. Demandas Elétricas - REN 1.059 (kW)", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#1B365D").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(card, text="Demanda de Carga (kW):", bg="#FFFFFF").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.ent_dem_carga = ttk.Entry(card, width=18)
        self.ent_dem_carga.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.ent_dem_carga.bind("<KeyRelease>", lambda e: self._on_dem_carga_change())

        tk.Label(card, text="Demanda de Geração (kW):", bg="#FFFFFF").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.ent_dem_geracao = ttk.Entry(card, width=18)
        self.ent_dem_geracao.grid(row=1, column=3, sticky="w", padx=4, pady=4)
        self.ent_dem_geracao.bind("<KeyRelease>", lambda e: self._calcular_em_tempo_real())

        tk.Label(card, text="Demanda Cliente p/ ERD (kW):", bg="#FFFFFF").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.ent_dem_erd = ttk.Entry(card, width=18)
        self.ent_dem_erd.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.ent_dem_erd.bind("<KeyRelease>", lambda e: self._on_dem_erd_change())

        tk.Label(card, text="Demanda Disp. Orçamento (kW):", bg="#FFFFFF").grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.ent_dem_disp = ttk.Entry(card, width=18)
        self.ent_dem_disp.grid(row=2, column=3, sticky="w", padx=4, pady=4)
        self.ent_dem_disp.bind("<KeyRelease>", lambda e: self._calcular_em_tempo_real())
        self.ent_dem_disp.bind("<KeyRelease>", lambda e: self._calcular_em_tempo_real())

        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)

    def _criar_card_resultados(self, parent):
        card = tk.Frame(parent, bg="#FFFFFF", padx=16, pady=14, highlightbackground="#CBD5E1", highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card, text="4. Live Preview - Resultados e Participação Financeira", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#1B365D").pack(anchor="w", pady=(0, 10))

        # Grade de Indicadores (KPIs)
        grid_kpi = tk.Frame(card, bg="#FFFFFF")
        grid_kpi.pack(fill=tk.X, pady=(0, 12))

        # Coluna 1: ERD
        f_erd = tk.Frame(grid_kpi, bg="#F8FAFC", padx=12, pady=8, relief="solid", borderwidth=1)
        f_erd.grid(row=0, column=0, sticky="nsew", padx=4)
        tk.Label(f_erd, text="ERD (Distribuidora)", font=("Segoe UI", 8, "bold"), bg="#F8FAFC", fg="#64748B").pack(anchor="w")
        self.lbl_kpi_erd = tk.Label(f_erd, text="R$ 0,00", font=("Segoe UI", 11, "bold"), bg="#F8FAFC", fg="#1E293B")
        self.lbl_kpi_erd.pack(anchor="w")

        # Coluna 2: Fator Proporc.
        f_prop = tk.Frame(grid_kpi, bg="#F8FAFC", padx=12, pady=8, relief="solid", borderwidth=1)
        f_prop.grid(row=0, column=1, sticky="nsew", padx=4)
        tk.Label(f_prop, text="Fator Proporc.", font=("Segoe UI", 8, "bold"), bg="#F8FAFC", fg="#64748B").pack(anchor="w")
        self.lbl_kpi_prop = tk.Label(f_prop, text="0,00%", font=("Segoe UI", 11, "bold"), bg="#F8FAFC", fg="#1E293B")
        self.lbl_kpi_prop.pack(anchor="w")

        # Coluna 3: COP
        f_cop = tk.Frame(grid_kpi, bg="#F8FAFC", padx=12, pady=8, relief="solid", borderwidth=1)
        f_cop.grid(row=0, column=2, sticky="nsew", padx=4)
        tk.Label(f_cop, text="COP (Proporcionalizado)", font=("Segoe UI", 8, "bold"), bg="#F8FAFC", fg="#64748B").pack(anchor="w")
        self.lbl_kpi_cop = tk.Label(f_cop, text="R$ 0,00", font=("Segoe UI", 11, "bold"), bg="#F8FAFC", fg="#1E293B")
        self.lbl_kpi_cop.pack(anchor="w")

        grid_kpi.columnconfigure(0, weight=1)
        grid_kpi.columnconfigure(1, weight=1)
        grid_kpi.columnconfigure(2, weight=1)

        # Banner Destaque Participação Financeira
        self.f_banner_pf = tk.Frame(card, bg="#DCFCE7", padx=14, pady=12, relief="solid", borderwidth=1)
        self.f_banner_pf.pack(fill=tk.X)

        self.lbl_status_pf = tk.Label(
            self.f_banner_pf,
            text="SEM PARTICIPAÇÃO FINANCEIRA",
            font=("Segoe UI", 12, "bold"),
            bg="#DCFCE7",
            fg="#166534",
        )
        self.lbl_status_pf.pack(anchor="w")

        self.lbl_detalhe_pf = tk.Label(
            self.f_banner_pf,
            text="O encargo da distribuidora (ERD) absorve integralmente o custo proporcionalizado da obra (COP <= ERD).",
            font=("Segoe UI", 9),
            bg="#DCFCE7",
            fg="#15803D",
        )
        self.lbl_detalhe_pf.pack(anchor="w")

    def _criar_rodape_acoes(self):
        rodape = tk.Frame(self, bg="#FFFFFF", padx=16, pady=12, relief="groove", borderwidth=1)
        rodape.pack(fill=tk.X, side=tk.BOTTOM)

        btn_salvar = tk.Button(
            rodape,
            text="💾 Preencher e Salvar Planilha CPFC (.xlsx)",
            font=("Segoe UI", 10, "bold"),
            bg="#1B365D",
            fg="#FFFFFF",
            padx=18,
            pady=8,
            relief="raised",
            cursor="hand2",
            command=self._salvar_planilha_dialogo,
        )
        btn_salvar.pack(side=tk.RIGHT, padx=6)

        btn_fechar = tk.Button(
            rodape,
            text="Fechar",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#334155",
            padx=14,
            pady=8,
            relief="flat",
            command=self.destroy,
        )
        btn_fechar.pack(side=tk.RIGHT, padx=6)

    def _on_dem_erd_change(self):
        """Marca que o usuário customizou manualmente a demanda de ERD."""
        self._custom_dem_erd = True
        self._calcular_em_tempo_real()

    def _on_dem_carga_change(self):
        """Sincroniza a demanda de carga com a demanda de ERD se o usuário não alterou manualmente."""
        if not self._custom_dem_erd:
            val_carga = self.ent_dem_carga.get().strip()
            self.ent_dem_erd.delete(0, tk.END)
            self.ent_dem_erd.insert(0, val_carga)
        self._calcular_em_tempo_real()

    def _obter_dados_formulario(self):
        def _parse_float(val_str: str) -> float:
            try:
                s = str(val_str).replace(".", "").replace(",", ".").strip()
                return float(s) if s else 0.0
            except ValueError:
                return 0.0

        cad = DadosCadastrais(
            projeto=self.ent_projeto.get(),
            tipo_ligacao=self.cb_tipo_ligacao.get(),
            subgrupo=self.cb_subgrupo.get(),
            endereco=self.ent_endereco.get(),
            municipio=self.ent_municipio.get(),
        )

        orc = OrcamentoObra(
            origem=self.cb_origem.get(),
            servico_terceiros=_parse_float(self.ent_terceiros.get()),
            material=_parse_float(self.ent_material.get()),
        )

        d_carga = _parse_float(self.ent_dem_carga.get())
        d_ger = _parse_float(self.ent_dem_geracao.get())
        d_erd_str = self.ent_dem_erd.get().strip()
        d_erd = _parse_float(d_erd_str) if d_erd_str else d_carga
        d_disp = _parse_float(self.ent_dem_disp.get())

        dem = ParametrosDemanda(
            demanda_carga=d_carga,
            demanda_geracao=d_ger,
            demanda_cliente_erd=d_erd,
            demanda_disponibilizada=d_disp,
        )

        return cad, orc, dem

    def _calcular_em_tempo_real(self):
        cad, orc, dem = self._obter_dados_formulario()
        resultado: ResultadoCPFC = calcular_cpfc(cad, orc, dem)

        # Atualiza Total da Obra
        self.lbl_total_obra.config(text=f"R$ {orc.custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # Atualiza KPIs
        self.lbl_kpi_erd.config(text=f"R$ {resultado.erd:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_kpi_prop.config(text=f"{resultado.fator_proporcionalizacao * 100:.2f}%")
        self.lbl_kpi_cop.config(text=f"R$ {resultado.cop:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # Atualiza Banner de Status
        if resultado.alerta and "MENOR" in resultado.alerta:
            self.f_banner_pf.config(bg="#FEE2E2")
            self.lbl_status_pf.config(text="ALERTA: DEMANDA DISP. INSUFICIENTE", bg="#FEE2E2", fg="#991B1B")
            self.lbl_detalhe_pf.config(text=resultado.alerta, bg="#FEE2E2", fg="#B91C1C")
        elif resultado.possui_participacao:
            self.f_banner_pf.config(bg="#FEF3C7")
            self.lbl_status_pf.config(
                text=f"PARTICIPAÇÃO FINANCEIRA: R$ {resultado.pf:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                bg="#FEF3C7",
                fg="#92400E",
            )
            self.lbl_detalhe_pf.config(
                text=f"Custo proporcionalizado (R$ {resultado.cop:,.2f}) excede o ERD (R$ {resultado.erd:,.2f}). Consumidor arca com a diferença.",
                bg="#FEF3C7",
                fg="#B45309",
            )
        else:
            self.f_banner_pf.config(bg="#DCFCE7")
            self.lbl_status_pf.config(text="SEM PARTICIPAÇÃO FINANCEIRA (ISENTO)", bg="#DCFCE7", fg="#166534")
            self.lbl_detalhe_pf.config(
                text="O encargo da distribuidora (ERD) absorve integralmente os custos da obra para este consumidor.",
                bg="#DCFCE7",
                fg="#15803D",
            )

    def _salvar_planilha_dialogo(self):
        cad, orc, dem = self._obter_dados_formulario()

        projeto_slug = cad.projeto if cad.projeto else "NOVO"
        nome_sugerido = f"PE_{projeto_slug}_CPFC_REN1.059.xlsx"

        caminho_escolhido = filedialog.asksaveasfilename(
            parent=self,
            title="Salvar Planilha CPFC Preenchida",
            initialdir=self.pasta_destino_sugerida,
            initialfile=nome_sugerido,
            defaultextension=".xlsx",
            filetypes=[("Planilhas Excel", "*.xlsx"), ("Todos os Arquivos", "*.*")],
        )

        if not caminho_escolhido:
            return  # Usuário cancelou

        try:
            arquivo_salvo = preencher_e_salvar_cpfc(cad, orc, dem, caminho_escolhido)
            self.ultimo_arquivo_salvo = arquivo_salvo
            self.pasta_destino_sugerida = os.path.dirname(arquivo_salvo)

            # Notificação de sucesso com opções
            self._exibir_dialogo_sucesso(arquivo_salvo)

        except Exception as err:
            messagebox.showerror("Erro ao Salvar", f"Falha ao gerar planilha CPFC:\n{str(err)}", parent=self)

    def _exibir_dialogo_sucesso(self, arquivo_salvo: str):
        msg_box = tk.Toplevel(self)
        msg_box.title("Sucesso!")
        msg_box.geometry("520x220")
        msg_box.configure(bg="#FFFFFF")
        msg_box.transient(self)
        msg_box.grab_set()

        tk.Label(msg_box, text="✔ Planilha CPFC Gerada com Sucesso!", font=("Segoe UI", 12, "bold"), bg="#FFFFFF", fg="#15803D").pack(pady=(16, 8))
        tk.Label(msg_box, text=f"Arquivo salvo em:\n{arquivo_salvo}", font=("Segoe UI", 8), bg="#FFFFFF", fg="#475569", wraplength=480).pack(pady=4)

        btn_box = tk.Frame(msg_box, bg="#FFFFFF")
        btn_box.pack(pady=16)

        def _abrir_excel():
            try:
                os.startfile(arquivo_salvo)
            except Exception:
                subprocess.Popen(["excel", arquivo_salvo], shell=True)
            msg_box.destroy()

        def _abrir_pasta():
            pasta = os.path.dirname(arquivo_salvo)
            try:
                os.startfile(pasta)
            except Exception:
                subprocess.Popen(["explorer", pasta], shell=True)
            msg_box.destroy()

        tk.Button(btn_box, text="📊 Abrir no Excel", font=("Segoe UI", 9, "bold"), bg="#1B365D", fg="#FFFFFF", padx=12, pady=6, command=_abrir_excel).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_box, text="📁 Abrir Pasta", font=("Segoe UI", 9), bg="#E2E8F0", fg="#1E293B", padx=12, pady=6, command=_abrir_pasta).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_box, text="OK", font=("Segoe UI", 9), bg="#E2E8F0", fg="#1E293B", padx=12, pady=6, command=msg_box.destroy).pack(side=tk.LEFT, padx=6)

    def _preencher_dados_iniciais(self, projeto: str, dados: Optional[Dict[str, Any]]):
        self.ent_projeto.insert(0, projeto)
        self.cb_tipo_ligacao.set((dados and dados.get("tipo_ligacao")) or "Acréscimo de carga")
        self.cb_subgrupo.set((dados and dados.get("subgrupo")) or "Subgrupo B1")
        self.cb_origem.set("GOM")
        val = dados or {
            "endereco": "Rua Jose Timoteo Caldara 834",
            "municipio": "PETRÓPOLIS",
            "servico_terceiros": "17172.51",
            "material": "29988.28",
            "demanda_carga": "40",
            "demanda_erd": "39.52",
            "demanda_disponibilizada": "69",
        }
        for campo, widget in [
            ("municipio", self.ent_municipio), ("endereco", self.ent_endereco),
            ("servico_terceiros", self.ent_terceiros), ("material", self.ent_material),
            ("demanda_carga", self.ent_dem_carga), ("demanda_geracao", self.ent_dem_geracao),
            ("demanda_erd", self.ent_dem_erd), ("demanda_disponibilizada", self.ent_dem_disp),
        ]:
            if campo in val and val[campo] is not None:
                widget.delete(0, tk.END)
                widget.insert(0, str(val[campo]))
