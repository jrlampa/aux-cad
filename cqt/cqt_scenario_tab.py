"""
Componente Visual de Aba de Cenário (ScenarioTab) para o Gerenciador CQT.
Responsável pela edição tabular de trechos, botões de cópia inteligente e painel
de Live Preview com indicação de conformidade normativa (QT <= 6,00%).
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

from cqt_live_calc import calcular_cqt_topologia, LIMITE_NORMATIVO_QT
from cqt_excel_io import load_scenario_from_excel


class ScenarioTab(ttk.Frame):
    """Gerencia a visualização e edição de trechos de um cenário específico."""
    def __init__(self, parent, cenario: str, cables_list: List[str], get_template_path_fn, get_source_scenario_data_fn=None, parent_app=None):
        super().__init__(parent, padding=8)
        self.cenario = cenario
        self.cables_list = cables_list
        self.get_template_path = get_template_path_fn
        self.get_source_scenario_data = get_source_scenario_data_fn
        self.parent_app = parent_app

        self.letras = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
        self.trechos_rows = []

        self._build_ui()

    def _build_ui(self):
        # Barra de ferramentas
        tb = ttk.Frame(self)
        tb.pack(fill="x", pady=(0, 6))

        ttk.Button(tb, text="+ Inserir Trecho", command=self.add_trecho_row).pack(side="left", padx=2)
        ttk.Button(tb, text="- Remover Último", command=self.remove_last_trecho).pack(side="left", padx=2)
        ttk.Button(tb, text="Limpar Tabela", command=self.clear_all_trechos).pack(side="left", padx=2)
        ttk.Button(tb, text="🔄 Carregar do Excel", command=self._on_load_from_excel).pack(side="left", padx=6)

        # Botões inteligentes de cópia conforme fluxo de engenharia
        if self.cenario == "ATUAL+NC" and self.get_source_scenario_data:
            btn_copy_atual = tk.Button(
                tb,
                text="📋 Copiar Trechos do ATUAL",
                bg="#2B6CB0",
                fg="white",
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda: self._on_copy_from("ATUAL")
            )
            btn_copy_atual.pack(side="left", padx=4)

        elif self.cenario == "PROJETADO" and self.get_source_scenario_data:
            btn_copy_anc = tk.Button(
                tb,
                text="📋 Copiar do ATUAL+NC",
                bg="#ED8936",
                fg="white",
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda: self._on_copy_from("ATUAL+NC")
            )
            btn_copy_anc.pack(side="left", padx=4)

            btn_copy_at = tk.Button(
                tb,
                text="📋 Copiar do ATUAL",
                bg="#4A5568",
                fg="white",
                font=("Segoe UI", 8),
                padx=5,
                pady=2,
                cursor="hand2",
                command=lambda: self._on_copy_from("ATUAL")
            )
            btn_copy_at.pack(side="left", padx=2)

        self.lbl_status = ttk.Label(tb, text=f"Cenário: {self.cenario} (0 trechos)", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(side="right", padx=5)

        # Canvas com Scrollbar
        canvas_wrap = ttk.Frame(self)
        canvas_wrap.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_wrap, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.canvas.yview)
        self.tbl_frame = ttk.Frame(self.canvas)

        self.tbl_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.tbl_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Painel de Live Preview e Alerta Normativo (QT <= 6.00%)
        self.pnl_preview = tk.Frame(self, bg="#EDF2F7", relief="ridge", bd=1, padx=8, pady=4)
        self.pnl_preview.pack(fill="x", side="bottom", pady=(4, 0))

        self.lbl_preview_info = tk.Label(
            self.pnl_preview,
            text="⚡ CÁLCULO EM TEMPO REAL: Demanda: 0,00 kVA | Trafo: 0,0% | Pior QT: 0,00% (Trecho -)",
            font=("Segoe UI", 9, "bold"),
            bg="#EDF2F7",
            fg="#2D3748"
        )
        self.lbl_preview_info.pack(side="left", padx=4)

        self.lbl_norma_badge = tk.Label(
            self.pnl_preview,
            text="✓ ATENDE À NORMA (QT <= 6,00%)",
            font=("Segoe UI", 9, "bold"),
            bg="#C6F6D5",
            fg="#22543D",
            padx=8,
            pady=2,
            relief="solid",
            bd=1
        )
        self.lbl_norma_badge.pack(side="right", padx=4)

        # Cabeçalho da Tabela
        headers = [
            ("Trecho", 6), ("Montante", 10), ("Vãos", 6), ("Compr. (m)", 11),
            ("Condutor", 24), ("Mono", 6), ("Bi", 6), ("Tri", 6), ("Esp. kVA", 8),
            ("IP 70W", 7), ("IP 100/125W", 9), ("IP 250W", 8)
        ]
        for col_idx, (h_text, width) in enumerate(headers):
            lbl = tk.Label(self.tbl_frame, text=h_text, font=("Segoe UI", 9, "bold"), bg="#E2E8F0", width=width, pady=4, relief="ridge")
            lbl.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)

    def _get_montante_options(self, current_idx: int) -> List[str]:
        opts = ["TRAFO"]
        for i in range(current_idx):
            opts.append(self.letras[i])
        return opts

    def add_trecho_row(self, initial_data: Optional[Dict] = None):
        idx = len(self.trechos_rows)
        row_num = idx + 1
        trecho_letra = self.letras[idx] if idx < len(self.letras) else f"T{idx+1}"

        lbl_tr = ttk.Label(self.tbl_frame, text=trecho_letra, font=("Segoe UI", 9, "bold"), anchor="center")
        lbl_tr.grid(row=row_num, column=0, padx=2, pady=2)

        montante_opts = self._get_montante_options(idx)
        cb_montante = ttk.Combobox(self.tbl_frame, values=montante_opts, width=8)
        cb_montante.grid(row=row_num, column=1, padx=2, pady=2)
        default_mont = "TRAFO" if idx == 0 else self.letras[idx - 1]
        cb_montante.set(initial_data.get("montante", default_mont) if initial_data else default_mont)

        ent_vaos = ttk.Entry(self.tbl_frame, width=5, justify="center")
        ent_vaos.grid(row=row_num, column=2, padx=2, pady=2)
        ent_vaos.insert(0, str(initial_data.get("vaos", 1) if initial_data else 1))

        ent_comp = ttk.Entry(self.tbl_frame, width=9, justify="right")
        ent_comp.grid(row=row_num, column=3, padx=2, pady=2)
        ent_comp.insert(0, f"{float(initial_data.get('comprimento_m', 35.0)):.1f}" if initial_data else "35.0")

        cb_cabo = ttk.Combobox(self.tbl_frame, values=self.cables_list, width=22)
        cb_cabo.grid(row=row_num, column=4, padx=2, pady=2)
        default_cabo = "3x35+1x54,6 - Al - F.P 1"
        if idx == 0 and "3x150+70 - Al - F.P 1" in self.cables_list:
            default_cabo = "3x150+70 - Al - F.P 1"
        cb_cabo.set(initial_data.get("condutor", default_cabo) if initial_data else default_cabo)

        ent_mono = ttk.Entry(self.tbl_frame, width=5, justify="center")
        ent_mono.grid(row=row_num, column=5, padx=2, pady=2)
        ent_mono.insert(0, str(initial_data.get("mono", "") if initial_data else ""))

        ent_bi = ttk.Entry(self.tbl_frame, width=5, justify="center")
        ent_bi.grid(row=row_num, column=6, padx=2, pady=2)
        ent_bi.insert(0, str(initial_data.get("bi", "") if initial_data else ""))

        ent_tri = ttk.Entry(self.tbl_frame, width=5, justify="center")
        ent_tri.grid(row=row_num, column=7, padx=2, pady=2)
        ent_tri.insert(0, str(initial_data.get("tri", "") if initial_data else ""))

        ent_esp = ttk.Entry(self.tbl_frame, width=7, justify="right")
        ent_esp.grid(row=row_num, column=8, padx=2, pady=2)
        ent_esp.insert(0, str(initial_data.get("esp_carga", "") if initial_data else ""))

        ent_ip70 = ttk.Entry(self.tbl_frame, width=6, justify="center")
        ent_ip70.grid(row=row_num, column=9, padx=2, pady=2)
        ent_ip70.insert(0, str(initial_data.get("ip70", "") if initial_data else ""))

        ent_ip125 = ttk.Entry(self.tbl_frame, width=7, justify="center")
        ent_ip125.grid(row=row_num, column=10, padx=2, pady=2)
        ent_ip125.insert(0, str(initial_data.get("ip125", "") if initial_data else ""))

        ent_ip250 = ttk.Entry(self.tbl_frame, width=6, justify="center")
        ent_ip250.grid(row=row_num, column=11, padx=2, pady=2)
        ent_ip250.insert(0, str(initial_data.get("ip250", "") if initial_data else ""))

        # Vincular eventos para recálculo instantâneo
        for ent in [ent_comp, ent_mono, ent_bi, ent_tri, ent_esp, ent_ip70, ent_ip125, ent_ip250]:
            ent.bind("<KeyRelease>", lambda e: self.recalcular_live())
        cb_montante.bind("<<ComboboxSelected>>", lambda e: self.recalcular_live())
        cb_cabo.bind("<<ComboboxSelected>>", lambda e: self.recalcular_live())

        self.trechos_rows.append({
            "widgets": [lbl_tr, cb_montante, ent_vaos, ent_comp, cb_cabo, ent_mono, ent_bi, ent_tri, ent_esp, ent_ip70, ent_ip125, ent_ip250],
            "letra": trecho_letra,
            "lbl_tr": lbl_tr,
            "cb_montante": cb_montante,
            "ent_vaos": ent_vaos,
            "ent_comp": ent_comp,
            "cb_cabo": cb_cabo,
            "ent_mono": ent_mono,
            "ent_bi": ent_bi,
            "ent_tri": ent_tri,
            "ent_esp": ent_esp,
            "ent_ip70": ent_ip70,
            "ent_ip125": ent_ip125,
            "ent_ip250": ent_ip250
        })
        self._update_status()
        self.recalcular_live()

    def recalcular_live(self):
        """Calcula em tempo real a topologia e atualiza o resumo e alertas normativos (QT <= 6,00%)."""
        trechos = self.get_trechos_data()
        if not trechos:
            self.lbl_preview_info.config(
                text="⚡ CÁLCULO EM TEMPO REAL: Demanda: 0,00 kVA | Trafo: 0,0% | Pior QT: 0,00% (Trecho -)"
            )
            self.lbl_norma_badge.config(
                text="✓ ATENDE À NORMA (QT <= 6,00%)",
                bg="#C6F6D5",
                fg="#22543D"
            )
            return

        potencia_trafo = 45.0
        if self.parent_app and hasattr(self.parent_app, "cb_potencia"):
            try:
                potencia_trafo = float(self.parent_app.cb_potencia.get())
            except ValueError:
                potencia_trafo = 45.0

        res = calcular_cqt_topologia(trechos, potencia_trafo=potencia_trafo)

        demanda = res["demanda_total_kva"]
        carreg = res["carregamento_trafo"]
        pior_qt = res["pior_qt"]
        trecho_crit = res["trecho_pior_qt"]
        tot_cli = res["total_clientes"]

        self.lbl_preview_info.config(
            text=f"⚡ CÁLCULO EM TEMPO REAL ({tot_cli} cli): Demanda: {demanda:.2f} kVA | Trafo: {carreg:.1f}% | Pior QT: {pior_qt:.2f}% (Trecho {trecho_crit})"
        )

        # Alerta normativo rígido de 6,00%
        if res["tem_alerta_normativo"]:
            self.lbl_norma_badge.config(
                text=f"⚠️ QT EXCESSIVA: {pior_qt:.2f}% no Trecho {trecho_crit} (> {LIMITE_NORMATIVO_QT:.2f}%)",
                bg="#FED7D7",
                fg="#9B2C2C"
            )
        else:
            self.lbl_norma_badge.config(
                text=f"✓ ATENDE À NORMA (Pior QT: {pior_qt:.2f}% <= {LIMITE_NORMATIVO_QT:.2f}%)",
                bg="#C6F6D5",
                fg="#22543D"
            )

        # Destaque visual dos trechos em desconformidade
        alertas = set(res["trechos_em_alerta"])
        for row in self.trechos_rows:
            letra = row["letra"]
            lbl_tr = row.get("lbl_tr")
            ent_comp = row.get("ent_comp")
            if lbl_tr:
                if letra in alertas:
                    lbl_tr.config(foreground="#C53030")
                    if ent_comp:
                        ent_comp.config(foreground="#C53030")
                else:
                    lbl_tr.config(foreground="#000000")
                    if ent_comp:
                        ent_comp.config(foreground="#000000")

    def remove_last_trecho(self):
        if not self.trechos_rows:
            return
        last_row = self.trechos_rows.pop()
        for w in last_row["widgets"]:
            w.destroy()
        self._update_status()

    def clear_all_trechos(self):
        while self.trechos_rows:
            self.remove_last_trecho()
        self._update_status()

    def _update_status(self):
        qtd = len(self.trechos_rows)
        self.lbl_status.config(text=f"Cenário: {self.cenario} ({qtd} trecho{'s' if qtd != 1 else ''})")
        self.recalcular_live()

    def get_trechos_data(self) -> List[Dict]:
        trechos = []
        for row in self.trechos_rows:
            trechos.append({
                "letra": row["letra"],
                "montante": row["cb_montante"].get().strip(),
                "vaos": row["ent_vaos"].get().strip(),
                "comprimento_m": row["ent_comp"].get().strip(),
                "condutor": row["cb_cabo"].get().strip(),
                "mono": row["ent_mono"].get().strip(),
                "bi": row["ent_bi"].get().strip(),
                "tri": row["ent_tri"].get().strip(),
                "esp_qtd": 1 if row["ent_esp"].get().strip() else 0,
                "esp_carga": row["ent_esp"].get().strip(),
                "ip70": row["ent_ip70"].get().strip(),
                "ip125": row["ent_ip125"].get().strip(),
                "ip250": row["ent_ip250"].get().strip(),
            })
        return trechos

    def set_trechos_data(self, trechos_list: List[Dict]):
        self.clear_all_trechos()
        for tr in trechos_list:
            self.add_trecho_row(tr)

    def _on_load_from_excel(self):
        path = self.get_template_path()
        data = load_scenario_from_excel(path, self.cenario)
        if not data or not data.get("trechos"):
            messagebox.showinfo("Informação", f"Nenhum trecho salvo encontrado no cenário '{self.cenario}' na planilha informada.")
            return

        if messagebox.askyesno("Confirmar", f"Carregar {len(data['trechos'])} trechos do cenário '{self.cenario}' da planilha? A tabela atual desta aba será substituída."):
            self.set_trechos_data(data["trechos"])

    def _on_copy_from(self, source_scenario: str):
        if not self.get_source_scenario_data:
            return
        src_trechos = self.get_source_scenario_data(source_scenario)
        if not src_trechos:
            messagebox.showwarning("Aviso", f"A aba '{source_scenario}' ainda não possui trechos para copiar.")
            return

        msg = (
            f"Deseja copiar os {len(src_trechos)} trechos da aba '{source_scenario}' para a aba '{self.cenario}'?\n\n"
            f"- Todos os comprimentos, montantes e cabos serão replicados.\n"
            f"- Você poderá ajustar cargas (NC) ou cabos recondutorados livremente."
        )
        if messagebox.askyesno("Confirmar Cópia de Trechos", msg):
            self.set_trechos_data(src_trechos)
