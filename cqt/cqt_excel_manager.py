"""
Módulo Principal do Gerenciador de Queda de Tensão (CQT - BT).
Interface Gráfica multi-cenários (ATUAL, ATUAL+NC, PROJETADO) com Live Preview,
alerta normativo rígido (QT <= 6,00%) e integração com AutoCAD e Excel.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

# Importa a camada de I/O e persistência Excel
from cqt_excel_io import (
    DEFAULT_TEMPLATE_PATH,
    get_default_template_path,
    load_cables_from_database,
    load_scenario_from_excel,
    load_all_scenarios_from_excel,
    update_cqt_excel,
)

# Importa o componente visual de abas de cenário
from cqt_scenario_tab import ScenarioTab


class CQTManagerGUI:
    """Janela Principal e Orquestradora da Ferramenta CQT."""
    def __init__(self, template_path: Optional[str] = None, cad_input_json: Optional[str] = None, initial_dest_path: Optional[str] = None):
        if not template_path:
            template_path = get_default_template_path()
        self.template_path = template_path
        self.cad_input_json = cad_input_json
        self.initial_dest_path = initial_dest_path
        self.cables_list = load_cables_from_database(template_path)

        self.root = tk.Tk()
        self.root.title("Gerenciador CQT - Cálculo de Queda de Tensão BT (ENEL)")
        self.root.geometry("1160x800")
        self.root.minsize(1020, 660)

        style = ttk.Style()
        style.theme_use('clam')

        self.tabs: Dict[str, ScenarioTab] = {}
        self._build_ui()
        self._load_initial_data()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        lbl_titulo = tk.Label(
            main_frame,
            text="AUTOMAÇÃO DE QUEDA DE TENSÃO (CQT - BT) - MULTI-CENÁRIOS",
            font=("Segoe UI", 12, "bold"),
            fg="#1A365D"
        )
        lbl_titulo.pack(pady=(0, 6))

        # --- 1. IDENTIFICAÇÃO DO PROJETO E DESTINO ---
        grp_cab = ttk.LabelFrame(main_frame, text=" 1. Identificação do Projeto, Transformador e Destino ", padding=8)
        grp_cab.pack(fill="x", pady=2)

        f1 = ttk.Frame(grp_cab)
        f1.pack(fill="x", pady=2)

        ttk.Label(f1, text="Nº Projeto:").grid(row=0, column=0, padx=4, sticky="w")
        self.ent_proj = ttk.Entry(f1, width=15)
        self.ent_proj.grid(row=0, column=1, padx=4, sticky="w")
        self.ent_proj.insert(0, "A057100646")

        ttk.Label(f1, text="Ponto Trafo:").grid(row=0, column=2, padx=4, sticky="w")
        self.ent_ponto = ttk.Entry(f1, width=12)
        self.ent_ponto.grid(row=0, column=3, padx=4, sticky="w")
        self.ent_ponto.insert(0, "A55323")

        ttk.Label(f1, text="Potência Trafo (kVA):").grid(row=0, column=4, padx=4, sticky="w")
        self.cb_potencia = ttk.Combobox(f1, values=["10", "15", "30", "45", "75", "112.5", "150"], width=8)
        self.cb_potencia.grid(row=0, column=5, padx=4, sticky="w")
        self.cb_potencia.set("45")

        ttk.Label(f1, text="Classe:").grid(row=0, column=6, padx=4, sticky="w")
        self.cb_classe = ttk.Combobox(f1, values=["CLASSE A", "CLASSE B", "CLASSE C", "CLASSE D"], width=12)
        self.cb_classe.grid(row=0, column=7, padx=4, sticky="w")
        self.cb_classe.set("CLASSE C")

        btn_import = ttk.Button(f1, text="📥 Importar Planilha Existente", command=self._on_importar_planilha_existente)
        btn_import.grid(row=0, column=8, padx=(12, 4), sticky="e")

        self.cb_potencia.bind("<<ComboboxSelected>>", lambda e: self._recalcular_todas_abas())
        self.cb_classe.bind("<<ComboboxSelected>>", lambda e: self._recalcular_todas_abas())

        # Linha de Destino do Arquivo
        f2 = ttk.Frame(grp_cab)
        f2.pack(fill="x", pady=(4, 2))

        ttk.Label(f2, text="Salvar Planilha em:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 5))
        self.ent_dest_path = ttk.Entry(f2)
        self.ent_dest_path.pack(side="left", fill="x", expand=True, padx=5)

        default_dest = self.initial_dest_path
        if not default_dest:
            base_dir = os.path.dirname(self.template_path)
            default_dest = os.path.join(base_dir, "CQT_PREENCHIDO.xlsm")
        self.ent_dest_path.insert(0, default_dest)

        btn_browse = ttk.Button(f2, text="📁 Salvar Como...", command=self._on_browse_dest)
        btn_browse.pack(side="left", padx=5)

        # --- 2. NOTEBOOK COM AS ABAS DE CADA CENÁRIO ---
        grp_notebook = ttk.LabelFrame(main_frame, text=" 2. Edição de Trechos por Cenário (Selecione a Aba para Editar) ", padding=6)
        grp_notebook.pack(fill="both", expand=True, pady=4)

        self.notebook = ttk.Notebook(grp_notebook)
        self.notebook.pack(fill="both", expand=True)

        cenarios = [
            ("ATUAL", "🔍 1. ATUAL (Rede Existente)"),
            ("ATUAL+NC", "⚡ 2. ATUAL + NC (Novas Cargas)"),
            ("PROJETADO", "📐 3. PROJETADO (Reforma/Opcional)")
        ]
        for cenario_id, cenario_label in cenarios:
            tab = ScenarioTab(
                self.notebook,
                cenario=cenario_id,
                cables_list=self.cables_list,
                get_template_path_fn=lambda: self.template_path,
                get_source_scenario_data_fn=self._get_scenario_trechos,
                parent_app=self
            )
            self.tabs[cenario_id] = tab
            self.notebook.add(tab, text=f"  {cenario_label}  ")

        # --- 3. RODAPÉ DE AÇÃO ---
        btn_frame = ttk.Frame(main_frame, padding=(0, 8, 0, 0))
        btn_frame.pack(fill="x")

        lbl_dica = ttk.Label(
            btn_frame,
            text="* Fluxo: 1. Preencha a rede ATUAL -> 2. No ATUAL+NC copie do ATUAL e lance as Novas Cargas -> 3. No PROJETADO (se houver reforma) copie e altere os cabos.",
            font=("Segoe UI", 8, "italic"),
            foreground="#2B6CB0"
        )
        lbl_dica.pack(side="left", padx=5)

        btn_gravar = tk.Button(
            btn_frame,
            text="✔ GRAVAR E ABRIR PLANILHA CQT (.XLSM)",
            font=("Segoe UI", 10, "bold"),
            bg="#2B6CB0",
            fg="white",
            padx=18,
            pady=8,
            cursor="hand2",
            command=self._on_gravar
        )
        btn_gravar.pack(side="right", padx=5)

        btn_cancelar = tk.Button(
            btn_frame,
            text="Fechar",
            font=("Segoe UI", 9),
            padx=10,
            pady=6,
            command=self.root.destroy
        )
        btn_cancelar.pack(side="right", padx=5)

    def _get_scenario_trechos(self, cenario: str) -> List[Dict]:
        if cenario in self.tabs:
            return self.tabs[cenario].get_trechos_data()
        return []

    def _on_browse_dest(self):
        cur = self.ent_dest_path.get().strip()
        init_dir = os.path.dirname(cur) if cur and os.path.exists(os.path.dirname(cur)) else os.getcwd()
        init_file = os.path.basename(cur) if cur else "CQT_PREENCHIDO.xlsm"

        chosen = filedialog.asksaveasfilename(
            initialdir=init_dir,
            initialfile=init_file,
            defaultextension=".xlsm",
            filetypes=[("Planilha com Macros do Excel", "*.xlsm"), ("Todos os Arquivos", "*.*")]
        )
        if chosen:
            self.ent_dest_path.delete(0, tk.END)
            self.ent_dest_path.insert(0, chosen)

    def _on_importar_planilha_existente(self, file_path: Optional[str] = None):
        """Importa os dados cadastrais e trechos de todos os cenários de uma planilha existente."""
        if not file_path:
            file_path = filedialog.askopenfilename(
                title="Selecionar Planilha CQT Preenchida",
                filetypes=[("Planilhas Excel", "*.xlsx;*.xlsm"), ("Todos os Arquivos", "*.*")]
            )
        if not file_path or not os.path.exists(file_path):
            return

        dados = load_all_scenarios_from_excel(file_path)
        cenarios = dados.get("cenarios", {})
        if not cenarios:
            messagebox.showwarning(
                "Aviso de Importação",
                f"Nenhum trecho de cenário (ATUAL, ATUAL+NC ou PROJETADO) foi localizado na planilha:\n{os.path.basename(file_path)}"
            )
            return

        # Atualiza campos cadastrais
        if dados.get("projeto"):
            self.ent_proj.delete(0, tk.END)
            self.ent_proj.insert(0, dados["projeto"])

        if dados.get("ponto_trafo"):
            self.ent_ponto.delete(0, tk.END)
            self.ent_ponto.insert(0, dados["ponto_trafo"])

        if dados.get("potencia_trafo"):
            self.cb_potencia.set(str(dados["potencia_trafo"]))

        if dados.get("classe"):
            self.cb_classe.set(str(dados["classe"]))

        # Atualiza caminho de destino sugerindo salvar na própria planilha
        self.ent_dest_path.delete(0, tk.END)
        self.ent_dest_path.insert(0, file_path)

        # Preenche as abas de cada cenário existente
        resumo_cenarios = []
        for cid in ["ATUAL", "ATUAL+NC", "PROJETADO"]:
            if cid in cenarios and cid in self.tabs:
                tr_list = cenarios[cid]
                self.tabs[cid].set_trechos_data(tr_list)
                resumo_cenarios.append(f"• {cid}: {len(tr_list)} trechos carregados")

        # Recarrega e mescla cabos homologados a partir da planilha importada
        novos_cabos = load_cables_from_database(file_path)
        if novos_cabos:
            for c in novos_cabos:
                if c not in self.cables_list:
                    self.cables_list.append(c)
            for tab in self.tabs.values():
                tab.update_cables_list(self.cables_list)

        self._recalcular_todas_abas()

        msg = f"Planilha importada com sucesso!\n\nArquivo: {os.path.basename(file_path)}\n\n" + "\n".join(resumo_cenarios)
        messagebox.showinfo("Importação Concluída", msg)

    def _recalcular_todas_abas(self):
        for tab in self.tabs.values():
            tab.recalcular_live()

    def _load_initial_data(self):
        target_scenario = "ATUAL"
        if self.cad_input_json and os.path.exists(self.cad_input_json):
            try:
                with open(self.cad_input_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "projeto" in data:
                        self.ent_proj.delete(0, tk.END)
                        self.ent_proj.insert(0, data["projeto"])
                        cur_dest = self.ent_dest_path.get().strip()
                        if cur_dest and ("CQT_PREENCHIDO" in cur_dest or "CQT_" in cur_dest):
                            d_dir = os.path.dirname(cur_dest)
                            self.ent_dest_path.delete(0, tk.END)
                            self.ent_dest_path.insert(0, os.path.join(d_dir, f"CQT_{data['projeto']}.xlsm"))
                    if "ponto_trafo" in data:
                        self.ent_ponto.delete(0, tk.END)
                        self.ent_ponto.insert(0, data["ponto_trafo"])
                    if "potencia_trafo" in data:
                        self.cb_potencia.set(str(data["potencia_trafo"]))
                    if "salvar_em" in data and data["salvar_em"]:
                        self.ent_dest_path.delete(0, tk.END)
                        self.ent_dest_path.insert(0, data["salvar_em"])
                    if "cenario" in data and data["cenario"]:
                        target_scenario = data["cenario"]

                    trechos_cad = data.get("trechos", [])
                    if trechos_cad:
                        if target_scenario in self.tabs:
                            self.tabs[target_scenario].set_trechos_data(trechos_cad)
                            for idx, (cid, _) in enumerate([("ATUAL", ""), ("ATUAL+NC", ""), ("PROJETADO", "")]):
                                if cid == target_scenario:
                                    self.notebook.select(idx)
                        return
            except Exception:
                pass

        # Se foi fornecido um arquivo Excel existente que possui dados, carrega-o
        if self.initial_dest_path and os.path.exists(self.initial_dest_path):
            ext = os.path.splitext(self.initial_dest_path)[1].lower()
            if ext in [".xlsm", ".xlsx"]:
                dados_auto = load_all_scenarios_from_excel(self.initial_dest_path)
                if dados_auto and dados_auto.get("cenarios"):
                    for cid, tr_list in dados_auto["cenarios"].items():
                        if cid in self.tabs and tr_list:
                            self.tabs[cid].set_trechos_data(tr_list)
                    if dados_auto.get("projeto"):
                        self.ent_proj.delete(0, tk.END)
                        self.ent_proj.insert(0, dados_auto["projeto"])
                    if dados_auto.get("ponto_trafo"):
                        self.ent_ponto.delete(0, tk.END)
                        self.ent_ponto.insert(0, dados_auto["ponto_trafo"])
                    if dados_auto.get("potencia_trafo"):
                        self.cb_potencia.set(str(dados_auto["potencia_trafo"]))
                    if dados_auto.get("classe"):
                        self.cb_classe.set(str(dados_auto["classe"]))
                    self._recalcular_todas_abas()
                    return

        default_trechos = [
            {"montante": "TRAFO", "vaos": 2, "comprimento_m": 75.0, "condutor": "3x150+70 - Al - F.P 1", "tri": 1, "ip70": 2},
            {"montante": "A", "vaos": 3, "comprimento_m": 110.0, "condutor": "3x50+1x50 - Al - F.P 1", "mono": 2, "ip70": 1},
            {"montante": "A", "vaos": 5, "comprimento_m": 180.0, "condutor": "3x35+1x54,6 - Al - F.P 1", "mono": 1, "tri": 1}
        ]
        self.tabs["ATUAL"].set_trechos_data(default_trechos)

    def _on_gravar(self):
        dest = self.ent_dest_path.get().strip()
        if not dest:
            messagebox.showwarning("Aviso", "Por favor, indique onde deseja salvar o arquivo Excel.")
            return

        scenarios_payload = {}
        for cenario_id, tab in self.tabs.items():
            t_data = tab.get_trechos_data()
            if t_data:
                scenarios_payload[cenario_id] = t_data

        if not scenarios_payload:
            messagebox.showwarning("Aviso", "Nenhum trecho adicionado em nenhum cenário.")
            return

        payload = {
            "projeto": self.ent_proj.get().strip(),
            "ponto_trafo": self.ent_ponto.get().strip(),
            "potencia_trafo": self.cb_potencia.get().strip(),
            "classe": self.cb_classe.get().strip(),
            "scenarios": scenarios_payload
        }

        try:
            gravados = update_cqt_excel(self.template_path, dest, payload)
            cenarios_str = ", ".join(gravados)

            # Gera automaticamente os dados e a rotina AutoLISP para os Quadros do CAD
            try:
                import cqt_quadros_generator
                cqt_quadros_generator.save_quadros_json(
                    xlsm_path=dest,
                    active_scenarios=list(scenarios_payload.keys()),
                    custom_ponto_trafo=self.ent_ponto.get().strip()
                )
                quadros_prontos = True
            except Exception as e_q:
                print(f"Aviso ao gerar quadros CAD: {e_q}")
                quadros_prontos = False

            msg_sucesso = (
                f"Planilha CQT gravada com sucesso!\n\n"
                f"Cenários atualizados: {cenarios_str}\n"
                f"Salvo em:\n{dest}\n\n"
            )
            if quadros_prontos:
                msg_sucesso += (
                    "📐 QUADROS DO CAD PRONTOS!\n"
                    "- No AutoCAD, digite o comando: CQTQUADROS\n"
                    "- Ou clique 'Sim' se chamado pelo CQTCAD para desenhar os quadros de Trafo e Queda de Tensão."
                )

            messagebox.showinfo("Sucesso", msg_sucesso)
            self.root.destroy()
            os.startfile(dest)
        except Exception as e:
            messagebox.showerror("Erro ao Gravar", f"Falha ao atualizar a planilha: {e}")

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    template = DEFAULT_TEMPLATE_PATH
    cad_json = None
    dest_file = None

    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        if arg1.lower().endswith(".json"):
            cad_json = arg1
        elif arg1 == "--json" and len(sys.argv) > 2:
            cad_json = sys.argv[2]
        else:
            template = arg1

    if len(sys.argv) > 2 and not cad_json:
        cad_json = sys.argv[2]
    if len(sys.argv) > 3:
        dest_file = sys.argv[3]

    app = CQTManagerGUI(template, cad_json, dest_file)
    app.run()
