# -*- coding: utf-8 -*-
"""
sob_launcher_gui.py - Janela interativa para lançamento autônomo da SOB.
Permite ao projetista informar a SOB, selecionar a Base técnica Enel Rio/FABAO
e escolher a pasta de destino antes de acionar o fluxo do orquestrador.
"""

import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from sob.sob_bases import LISTA_BASES_PADRAO, normalizar_sigla_base
    from sob.sob_core import obter_sob_id, validar_sob
    from sob.sob_manager import SobOrchestrator
    from sob.sob_progress_gui import SobProgressGUI
except ImportError:
    from sob_bases import LISTA_BASES_PADRAO, normalizar_sigla_base
    from sob_core import obter_sob_id, validar_sob
    from sob_manager import SobOrchestrator
    from sob_progress_gui import SobProgressGUI


class SobLauncherDialog:
    """Janela moderna de diálogo para configuração prévia da SOB."""

    def __init__(self, root: Optional[tk.Tk] = None):
        self._proprio_root = root is None
        self.root = tk.Tk() if self._proprio_root else tk.Toplevel(root)
        self.root.title("AUX CAD — Preparação de Projeto SOB")
        self.root.geometry("540x440")
        self.root.resizable(False, False)
        self.root.configure(bg="#0F172A")

        self.sob_var = tk.StringVar(value="")
        self.base_var = tk.StringVar(value="PE")
        self.destino_var = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.sp_var = tk.BooleanVar(value=True)
        self.cad_var = tk.BooleanVar(value=True)

        self._construir_ui()

    def _construir_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg="#1E293B", padx=16, pady=12)
        hdr.pack(fill="x")

        tk.Label(
            hdr,
            text="📁 PREPARAÇÃO DE PROJETO SOB",
            font=("Segoe UI", 13, "bold"),
            bg="#1E293B",
            fg="#F8FAFC",
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Criação padronizada de diretórios, croquis e desenho canônico {BASE}_{SOB}_DESENHO.dwg",
            font=("Segoe UI", 8),
            bg="#1E293B",
            fg="#94A3B8",
        ).pack(anchor="w")

        # Corpo
        corpo = tk.Frame(self.root, bg="#0F172A", padx=20, pady=16)
        corpo.pack(fill="both", expand=True)

        # 1. Campo Número da SOB
        tk.Label(
            corpo,
            text="Número da SOB (ex: A057350816 ou 57350816):",
            font=("Segoe UI", 9, "bold"),
            bg="#0F172A",
            fg="#E2E8F0",
        ).pack(anchor="w", pady=(0, 4))

        self.ent_sob = tk.Entry(
            corpo,
            textvariable=self.sob_var,
            font=("Segoe UI", 11),
            bg="#1E293B",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#475569",
        )
        self.ent_sob.pack(fill="x", ipady=4, pady=(0, 12))
        self.ent_sob.focus_set()

        # 2. Seleção da Base Técnica
        tk.Label(
            corpo,
            text="Base Técnica Operacional (FABAO / Enel Rio):",
            font=("Segoe UI", 9, "bold"),
            bg="#0F172A",
            fg="#E2E8F0",
        ).pack(anchor="w", pady=(0, 4))

        bases_opcoes = [f"{sigla} - {nome}" for sigla, nome in LISTA_BASES_PADRAO]
        self.cb_base = ttk.Combobox(
            corpo,
            values=bases_opcoes,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self.cb_base.set("PE - Petrópolis")
        self.cb_base.pack(fill="x", pady=(0, 12))

        # 3. Diretório de Destino
        tk.Label(
            corpo,
            text="Diretório de Destino (onde será criada a pasta SOB_...):",
            font=("Segoe UI", 9, "bold"),
            bg="#0F172A",
            fg="#E2E8F0",
        ).pack(anchor="w", pady=(0, 4))

        dest_frame = tk.Frame(corpo, bg="#0F172A")
        dest_frame.pack(fill="x", pady=(0, 12))

        self.ent_dest = tk.Entry(
            dest_frame,
            textvariable=self.destino_var,
            font=("Segoe UI", 9),
            bg="#1E293B",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#475569",
        )
        self.ent_dest.pack(side="left", fill="x", expand=True, ipady=4)

        btn_browse = tk.Button(
            dest_frame,
            text="📁 Procurar...",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            relief="flat",
            command=self._procurar_pasta,
        )
        btn_browse.pack(side="left", padx=(6, 0))

        # 4. Opções de Execução
        chk_frame = tk.Frame(corpo, bg="#0F172A")
        chk_frame.pack(fill="x", pady=(0, 12))

        tk.Checkbutton(
            chk_frame,
            text="Baixar Croquis e Anexos (SharePoint & GOMNET)",
            variable=self.sp_var,
            font=("Segoe UI", 9),
            bg="#0F172A",
            fg="#94A3B8",
            selectcolor="#1E293B",
            activebackground="#0F172A",
            activeforeground="#FFFFFF",
        ).pack(anchor="w")

        tk.Checkbutton(
            chk_frame,
            text="Abrir DWG no AutoCAD ao concluir",
            variable=self.cad_var,
            font=("Segoe UI", 9),
            bg="#0F172A",
            fg="#94A3B8",
            selectcolor="#1E293B",
            activebackground="#0F172A",
            activeforeground="#FFFFFF",
        ).pack(anchor="w")

        # Rodapé / Botão de Ação
        rodape = tk.Frame(self.root, bg="#1E293B", padx=16, pady=10)
        rodape.pack(fill="x", side="bottom")

        btn_iniciar = tk.Button(
            rodape,
            text="🚀 Iniciar Preparação do Projeto",
            font=("Segoe UI", 10, "bold"),
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=6,
            command=self._iniciar_execucao,
        )
        btn_iniciar.pack(side="right")

        btn_canc = tk.Button(
            rodape,
            text="Fechar",
            font=("Segoe UI", 9),
            bg="#334155",
            fg="#E2E8F0",
            activebackground="#475569",
            relief="flat",
            command=self.root.destroy,
        )
        btn_canc.pack(side="left")

    def _procurar_pasta(self):
        escolha = filedialog.askdirectory(
            title="Selecione o diretório onde a SOB será criada",
            initialdir=self.destino_var.get(),
            parent=self.root,
        )
        if escolha:
            self.destino_var.set(escolha)

    def _iniciar_execucao(self):
        sob_txt = self.sob_var.get().strip()
        if not validar_sob(sob_txt):
            messagebox.showerror(
                "SOB Inválida",
                "Por favor, informe um número de SOB válido (ex: A057350816).",
                parent=self.root,
            )
            self.ent_sob.focus_set()
            return

        dest_txt = self.destino_var.get().strip()
        if not dest_txt or not Path(dest_txt).is_dir():
            messagebox.showerror(
                "Destino Inválido",
                "O diretório de destino selecionado não existe ou é inválido.",
                parent=self.root,
            )
            return

        base_val = self.cb_base.get()
        sigla_base = normalizar_sigla_base(base_val.split(" - ")[0] if " - " in base_val else base_val)

        # Fecha a janela de diálogo
        self.root.destroy()

        # Instancia o orquestrador e abre a barra de progresso oficial
        orchestrator = SobOrchestrator()

        def _tarefa(observer):
            base_usada = getattr(observer, "base_selecionada", None) or sigla_base
            return orchestrator.executar(
                sob_raw=sob_txt,
                destino_dir=dest_txt,
                base=base_usada,
                baixar_croqui_sp=self.sp_var.get(),
                abrir_cad=self.cad_var.get(),
                callback_progresso=observer,
                verificador_cancelamento=observer,
            )

        app_gui = SobProgressGUI(
            sob_id=obter_sob_id(sob_txt),
            tarefa_executora=_tarefa,
            base_inicial=sigla_base,
        )
        app_gui.iniciar()

    def run(self):
        self.root.mainloop()


def lancar_dialogo_sob(parent: Optional[tk.Tk] = None):
    dialog = SobLauncherDialog(parent)
    if parent is None:
        dialog.run()


if __name__ == "__main__":
    lancar_dialogo_sob()
