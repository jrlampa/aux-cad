# -*- coding: utf-8 -*-
"""
Interface e Ponto de Entrada do Workspace da SOB (aux cad).
Permite consulta via linha de comando (CLI) ou interface gráfica desktop simples (Tkinter).
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _d in [_curr_dir, _root_dir]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

from workspace.workspace_core import ArtifactStatus, ProjectWorkspace
from workspace.workspace_scanner import WorkspaceScanner


class WorkspaceGUI(tk.Tk):
    """Interface visual simples e ergonômica para inspeção do Workspace da SOB."""

    def __init__(self, root_dir: Optional[str] = None, sob_id: Optional[str] = None):
        super().__init__()
        self.title("AUX CAD — Workspace da SOB / Projeto")
        self.geometry("780x640")
        self.minsize(700, 520)
        self.configure(bg="#F8FAFC")

        self.current_dir = Path(root_dir).resolve() if root_dir else Path.cwd()
        self.sob_id_inicial = sob_id

        self._configurar_estilos()
        self._construir_interface()
        self._executar_varredura()

    def _configurar_estilos(self):
        style = ttk.Style(self)
        style.theme_use("clam")

    def _construir_interface(self):
        # 1. Cabeçalho Executivo
        header = tk.Frame(self, bg="#1B365D", height=64, padx=16)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        lbl_tit = tk.Label(
            header,
            text="WORKSPACE DA SOB / PROJETO",
            font=("Segoe UI", 12, "bold"),
            fg="#FFFFFF",
            bg="#1B365D"
        )
        lbl_tit.pack(side="left", pady=16)

        lbl_sub = tk.Label(
            header,
            text="Coordenação Central de Contexto e Artefatos",
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#1B365D"
        )
        lbl_sub.pack(side="right", pady=18)

        # 2. Barra de Seleção de Pasta / SOB
        top_bar = tk.Frame(self, bg="#FFFFFF", bd=1, relief="solid", padx=12, pady=10)
        top_bar.pack(fill="x", padx=12, pady=8)

        tk.Label(top_bar, text="Pasta da SOB:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#1E293B").pack(side="left", padx=(0, 6))

        self.ent_dir = ttk.Entry(top_bar, font=("Segoe UI", 9))
        self.ent_dir.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.ent_dir.insert(0, str(self.current_dir))

        btn_browse = tk.Button(
            top_bar,
            text="Selecionar Pasta...",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#1E293B",
            relief="flat",
            padx=10,
            command=self._on_browse_dir
        )
        btn_browse.pack(side="left", padx=(0, 6))

        btn_refresh = tk.Button(
            top_bar,
            text="🔄 Atualizar",
            font=("Segoe UI", 9, "bold"),
            bg="#2563EB",
            fg="#FFFFFF",
            relief="flat",
            padx=12,
            command=self._executar_varredura
        )
        btn_refresh.pack(side="left")

        # 3. Card de Informações da SOB
        self.card_info = tk.Frame(self, bg="#FFFFFF", bd=1, relief="solid", padx=12, pady=8)
        self.card_info.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_sob_status = tk.Label(
            self.card_info,
            text="Carregando contexto...",
            font=("Segoe UI", 10, "bold"),
            bg="#FFFFFF",
            fg="#1E293B"
        )
        self.lbl_sob_status.pack(anchor="w")

        # 4. Tabela / Lista de Artefatos
        body_frame = tk.Frame(self, bg="#FFFFFF", bd=1, relief="solid", padx=8, pady=8)
        body_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        lbl_art_tit = tk.Label(body_frame, text="Artefatos de Engenharia Detectados:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#1E293B")
        lbl_art_tit.pack(anchor="w", pady=(0, 6))

        colunas = ("Artefato", "Status", "Arquivo / Detalhes")
        self.tree = ttk.Treeview(body_frame, columns=colunas, show="headings", height=10)
        self.tree.heading("Artefato", text="Artefato")
        self.tree.heading("Status", text="Status")
        self.tree.heading("Arquivo / Detalhes", text="Arquivo / Detalhes")

        self.tree.column("Artefato", width=220, anchor="w")
        self.tree.column("Status", width=110, anchor="center")
        self.tree.column("Arquivo / Detalhes", width=380, anchor="w")

        scroll = ttk.Scrollbar(body_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 5. Barra Inferior de Ações
        bot_bar = tk.Frame(self, bg="#F8FAFC", pady=4)
        bot_bar.pack(fill="x", padx=12, pady=(0, 8))

        btn_abrir_pasta = tk.Button(
            bot_bar,
            text="📂 Abrir Pasta no Explorer",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#1E293B",
            relief="flat",
            padx=12,
            pady=4,
            command=self._abrir_pasta_atual
        )
        btn_abrir_pasta.pack(side="left")

    def _on_browse_dir(self):
        escolhida = filedialog.askdirectory(parent=self, title="Selecionar Pasta da SOB / Projeto", initialdir=str(self.current_dir))
        if escolhida:
            self.current_dir = Path(escolhida).resolve()
            self.ent_dir.delete(0, tk.END)
            self.ent_dir.insert(0, str(self.current_dir))
            self._executar_varredura()

    def _executar_varredura(self):
        caminho_str = self.ent_dir.get().strip()
        p = Path(caminho_str).resolve()
        self.current_dir = p

        workspace = WorkspaceScanner.scan(p, sob_id=self.sob_id_inicial)
        self.workspace = workspace

        # Atualiza card de info
        if workspace.sob_id and workspace.sob_id != "DESCONHECIDO":
            self.lbl_sob_status.config(
                text=f"SOB: {workspace.sob_id}  |  Base: {workspace.base_sigla}  |  Pasta: {workspace.root_dir.name}",
                fg="#15803D"
            )
        else:
            self.lbl_sob_status.config(
                text=f"Pasta sem identificador explícito de SOB  |  Pasta: {workspace.root_dir.name}",
                fg="#B45309"
            )

        # Atualiza lista
        self.tree.delete(*self.tree.get_children())
        for art in workspace.artefatos.values():
            if art.status == ArtifactStatus.EXISTE:
                st_txt = "✔ EXISTE"
            elif art.status == ArtifactStatus.NAO_EXISTE:
                st_txt = "— NÃO GERADO"
            else:
                st_txt = "○ NÃO APLICÁVEL"

            detalhe = art.caminho.name if art.caminho else "—"
            if art.detalhes and "total_arquivos" in art.detalhes:
                detalhe += f" ({art.detalhes['total_arquivos']} arquivos)"

            self.tree.insert("", "end", values=(art.rotulo, st_txt, detalhe))

    def _abrir_pasta_atual(self):
        if self.current_dir.exists():
            if os.name == "nt":
                os.startfile(str(self.current_dir))
            else:
                subprocess.Popen(["xdg-open", str(self.current_dir)])


def main():
    parser = argparse.ArgumentParser(description="AUX CAD — Workspace da SOB/Projeto")
    parser.add_argument("--dir", type=str, help="Caminho do diretório da SOB")
    parser.add_argument("--sob", type=str, help="Identificador da SOB (ex: A057349839)")
    parser.add_argument("--gui", action="store_true", help="Abrir interface gráfica de visualização")
    parser.add_argument("--json", action="store_true", help="Exportar resumo em formato JSON")

    args = parser.parse_args()

    diretorio = Path(args.dir).resolve() if args.dir else Path.cwd()

    if args.gui or (len(sys.argv) == 1 and not args.json):
        app = WorkspaceGUI(root_dir=str(diretorio), sob_id=args.sob)
        app.mainloop()
        return

    # Execução CLI
    ws = WorkspaceScanner.scan(diretorio, sob_id=args.sob)
    if args.json:
        import json
        print(json.dumps(ws.obter_resumo(), indent=2, ensure_ascii=False))
    else:
        print(ws.formatar_relatorio_texto())


if __name__ == "__main__":
    main()
