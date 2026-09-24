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

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_scanner import WorkspaceScanner
from workspace.workspace_actions import WorkspaceActionDispatcher


class WorkspaceGUI(tk.Tk):
    """Interface visual simples e ergonômica para inspeção e ações do Workspace da SOB."""

    def __init__(self, root_dir: Optional[str] = None, sob_id: Optional[str] = None):
        super().__init__()
        self.title("AUX CAD — Workspace da SOB / Projeto")
        self.geometry("860x640")
        self.minsize(780, 520)
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
        self.tree.bind("<Double-1>", lambda event: self._on_abrir_artefato())

        # 5. Barra Inferior de Ações
        bot_bar = tk.Frame(self, bg="#F8FAFC", pady=6)
        bot_bar.pack(fill="x", padx=12, pady=(0, 8))

        # Ações do Item Selecionado
        lbl_acoes_item = tk.Label(bot_bar, text="Item Selecionado:", font=("Segoe UI", 9, "bold"), bg="#F8FAFC", fg="#334155")
        lbl_acoes_item.pack(side="left", padx=(0, 6))

        btn_abrir = tk.Button(
            bot_bar,
            text="📂 Abrir",
            font=("Segoe UI", 9, "bold"),
            bg="#2563EB",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_abrir_artefato
        )
        btn_abrir.pack(side="left", padx=(0, 4))

        btn_localizar = tk.Button(
            bot_bar,
            text="🔍 Localizar",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#1E293B",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_localizar_artefato
        )
        btn_localizar.pack(side="left", padx=(0, 16))

        # Lançadores de Módulos Especialistas
        lbl_modulos = tk.Label(bot_bar, text="Executar Módulo:", font=("Segoe UI", 9, "bold"), bg="#F8FAFC", fg="#334155")
        lbl_modulos.pack(side="left", padx=(0, 6))

        btn_sob = tk.Button(
            bot_bar,
            text="📁 Preparar SOB",
            font=("Segoe UI", 9, "bold"),
            bg="#0D9488",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_executar_sob
        )
        btn_sob.pack(side="left", padx=(0, 4))

        btn_cqt = tk.Button(
            bot_bar,
            text="⚡ CQT",
            font=("Segoe UI", 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_executar_cqt
        )
        btn_cqt.pack(side="left", padx=(0, 4))

        btn_orc = tk.Button(
            bot_bar,
            text="📊 Orçamento",
            font=("Segoe UI", 9, "bold"),
            bg="#059669",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_executar_orcamento
        )
        btn_orc.pack(side="left", padx=(0, 4))

        btn_cpfc = tk.Button(
            bot_bar,
            text="📐 CPFC",
            font=("Segoe UI", 9, "bold"),
            bg="#7C3AED",
            fg="#FFFFFF",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_executar_cpfc
        )
        btn_cpfc.pack(side="left", padx=(0, 16))

        btn_abrir_pasta = tk.Button(
            bot_bar,
            text="📁 Pasta SOB",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#1E293B",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._abrir_pasta_atual
        )
        btn_abrir_pasta.pack(side="right")

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

        # Atualiza lista mantendo a chave como iid
        self.tree.delete(*self.tree.get_children())
        for chave, art in workspace.artefatos.items():
            if art.status == ArtifactStatus.EXISTE:
                st_txt = "✔ EXISTE"
            elif art.status == ArtifactStatus.NAO_EXISTE:
                st_txt = "— NÃO GERADO"
            else:
                st_txt = "○ NÃO APLICÁVEL"

            detalhe = art.caminho.name if art.caminho else "—"
            if art.detalhes and "total_arquivos" in art.detalhes:
                detalhe += f" ({art.detalhes['total_arquivos']} arquivos)"

            self.tree.insert("", "end", iid=chave, values=(art.rotulo, st_txt, detalhe))

    def _get_selected_artifact(self) -> Optional[ProjectArtifact]:
        """Recupera o objeto ProjectArtifact correspondente à linha selecionada na Treeview."""
        sel = self.tree.selection()
        if not sel:
            return None
        chave = sel[0]
        if hasattr(self, "workspace") and self.workspace:
            return self.workspace.obter_artefato(chave)
        return None

    def _on_abrir_artefato(self):
        """Abre o artefato selecionado no aplicativo padrão do Windows."""
        art = self._get_selected_artifact()
        if not art:
            messagebox.showinfo("Aviso", "Nenhum artefato selecionado na lista.")
            return

        if not art.existe or not art.caminho or not art.caminho.exists():
            messagebox.showwarning("Artefato Inexistente", f"O artefato '{art.rotulo}' ainda não foi gerado ou não existe no disco.")
            return

        sucesso = WorkspaceActionDispatcher.abrir_artefato(art)
        if not sucesso:
            messagebox.showerror("Erro ao Abrir", f"Não foi possível abrir o artefato '{art.rotulo}'.")

    def _on_localizar_artefato(self):
        """Evidencia e seleciona o artefato no Windows Explorer."""
        art = self._get_selected_artifact()
        if not art:
            messagebox.showinfo("Aviso", "Nenhum artefato selecionado na lista.")
            return

        if not art.existe or not art.caminho or not art.caminho.exists():
            messagebox.showwarning("Artefato Inexistente", f"O artefato '{art.rotulo}' ainda não foi gerado ou não existe no disco.")
            return

        sucesso = WorkspaceActionDispatcher.localizar_artefato(art)
        if not sucesso:
            messagebox.showerror("Erro ao Localizar", f"Não foi possível localizar o artefato '{art.rotulo}' no Explorer.")

    def _on_executar_cqt(self):
        """Dispara a interface do módulo CQT contextualizada para a SOB atual."""
        if not hasattr(self, "workspace") or not self.workspace:
            messagebox.showwarning("Aviso", "Contexto de Workspace não disponível.")
            return

        try:
            proc = WorkspaceActionDispatcher.executar_cqt(self.workspace)
            if proc:
                messagebox.showinfo("Módulo CQT", f"Módulo de Queda de Tensão (CQT) iniciado para a SOB {self.workspace.sob_id}.")
        except Exception as ex:
            messagebox.showerror("Erro ao Iniciar CQT", f"Não foi possível iniciar o módulo CQT:\n{ex}")

    def _on_executar_orcamento(self):
        """Dispara a interface do módulo de Orçamento contextualizada para a SOB atual."""
        if not hasattr(self, "workspace") or not self.workspace:
            messagebox.showwarning("Aviso", "Contexto de Workspace não disponível.")
            return

        try:
            proc = WorkspaceActionDispatcher.executar_orcamento(self.workspace)
            if proc:
                messagebox.showinfo("Módulo Orçamento", f"Módulo de Orçamento e Materiais iniciado para a SOB {self.workspace.sob_id}.")
        except Exception as ex:
            messagebox.showerror("Erro ao Iniciar Orçamento", f"Não foi possível iniciar o módulo de Orçamento:\n{ex}")

    def _on_executar_cpfc(self):
        """Dispara a interface do módulo CPFC (REN 1.059) contextualizada para a SOB atual."""
        if not hasattr(self, "workspace") or not self.workspace:
            messagebox.showwarning("Aviso", "Contexto de Workspace não disponível.")
            return

        try:
            proc = WorkspaceActionDispatcher.executar_cpfc(self.workspace)
            if proc:
                messagebox.showinfo("Módulo CPFC", f"Módulo CPFC (REN 1.059) iniciado para a SOB {self.workspace.sob_id}.")
        except Exception as ex:
            messagebox.showerror("Erro ao Iniciar CPFC", f"Não foi possível iniciar o módulo CPFC:\n{ex}")

    def _on_executar_sob(self):
        """Dispara a interface oficial do Preparador de Projeto SOB."""
        try:
            ws = self.workspace if hasattr(self, "workspace") else None
            proc = WorkspaceActionDispatcher.executar_sob(workspace=ws)
            if proc:
                messagebox.showinfo("Preparador SOB", "Preparador de Projeto SOB iniciado.")
        except FileNotFoundError as fnf:
            messagebox.showerror("Launcher Não Encontrado", f"O launcher oficial da SOB não foi encontrado:\n{fnf}")
        except Exception as ex:
            messagebox.showerror("Erro ao Iniciar Preparador SOB", f"Não foi possível iniciar o preparador da SOB:\n{ex}")

    def _abrir_pasta_atual(self):
        """Abre a pasta raiz da SOB no Explorer via Dispatcher."""
        alvo = self.workspace.root_dir if (hasattr(self, "workspace") and self.workspace and self.workspace.root_dir) else self.current_dir
        if not WorkspaceActionDispatcher.localizar_artefato(alvo):
            messagebox.showwarning("Aviso", "A pasta selecionada não foi encontrada no disco.")


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
