#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aux_cad_hub.py - Central de Automação & Launcher Unificado AUX CAD
Painel executivo moderno para inicialização de módulos de engenharia,
diagnóstico de ambiente em tempo real e orquestração de rotinas CAD.
"""

import os
import sys
import platform
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

APP_TITLE = "AUX CAD 2026 - Central de Automação de Projetos"
APP_VERSION = "v2.5.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def verificar_processo_autocad() -> bool:
    """Verifica se o processo do AutoCAD (acad.exe) está em execução."""
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq acad.exe"],
                text=True, stderr=subprocess.DEVNULL
            )
            return "acad.exe" in output.lower()
        except Exception:
            return False
    return False


def obter_branch_git() -> str:
    """Retorna a branch atual do git ou 'dev' como fallback."""
    try:
        res = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=BASE_DIR, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return res or "dev"
    except Exception:
        return "dev"


class AuxCadHubApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_TITLE} ({APP_VERSION})")
        self.root.geometry("900x780")
        self.root.minsize(840, 700)
        self.root.configure(bg="#0F172A")

        self.branch_git = obter_branch_git()
        self.acad_rodando = verificar_processo_autocad()

        self._criar_estilos()
        self._construir_interface()

    def _criar_estilos(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Configurações de cores executivas
        style.configure("TFrame", background="#0F172A")
        style.configure("Card.TFrame", background="#1E293B", relief="ridge")
        style.configure("Header.TLabel", background="#0F172A", foreground="#F8FAFC", font=("Segoe UI", 16, "bold"))
        style.configure("SubHeader.TLabel", background="#0F172A", foreground="#94A3B8", font=("Segoe UI", 10))
        style.configure("Diag.TLabel", background="#1E293B", foreground="#38BDF8", font=("Segoe UI", 9, "bold"))

    def _construir_interface(self):
        # 1. Cabeçalho Principal
        header_frame = tk.Frame(self.root, bg="#0F172A", padx=20, pady=12)
        header_frame.pack(fill="x")

        title_box = tk.Frame(header_frame, bg="#0F172A")
        title_box.pack(side="left")

        lbl_title = tk.Label(
            title_box,
            text="⚡ AUX CAD — CENTRAL DE ENGENHARIA",
            font=("Segoe UI", 15, "bold"),
            bg="#0F172A",
            fg="#F8FAFC"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            title_box,
            text="Painel Unificado de Automação, Geoprocessamento e Cálculos Elétricos",
            font=("Segoe UI", 9),
            bg="#0F172A",
            fg="#94A3B8"
        )
        lbl_sub.pack(anchor="w")

        lbl_ver = tk.Label(
            header_frame,
            text=f"Versão {APP_VERSION}\nBranch: [{self.branch_git}]",
            font=("Segoe UI", 9, "bold"),
            bg="#0F172A",
            fg="#F59E0B",
            justify="right"
        )
        lbl_ver.pack(side="right")

        # 2. Barra de Diagnóstico do Sistema
        diag_frame = tk.Frame(self.root, bg="#1E293B", padx=16, pady=8, highlightbackground="#334155", highlightthickness=1)
        diag_frame.pack(fill="x", padx=20, pady=(0, 12))

        # Status Python
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        tk.Label(
            diag_frame,
            text=f"🐍 Python: v{py_ver}",
            font=("Segoe UI", 9, "bold"),
            bg="#1E293B",
            fg="#38BDF8"
        ).pack(side="left", padx=(0, 16))

        # Status AutoCAD
        acad_cor = "#10B981" if self.acad_rodando else "#94A3B8"
        acad_txt = "🟢 AutoCAD: Detectado (Ativo)" if self.acad_rodando else "⚪ AutoCAD: Standby (Não detectado)"
        tk.Label(
            diag_frame,
            text=acad_txt,
            font=("Segoe UI", 9, "bold"),
            bg="#1E293B",
            fg=acad_cor
        ).pack(side="left", padx=16)

        # Status Paleta .NET
        dll_path = os.path.join(BASE_DIR, "mapa_cad_paleta", "bin", "Release", "net8.0-windows", "MapaCadPaleta.dll")
        dll_ok = os.path.exists(dll_path)
        tk.Label(
            diag_frame,
            text=f"📐 Paleta .NET: {'✓ Compilada' if dll_ok else '⚠️ Requer Build'}",
            font=("Segoe UI", 9, "bold"),
            bg="#1E293B",
            fg="#10B981" if dll_ok else "#F59E0B"
        ).pack(side="left", padx=16)

        # Botão Atualizar Diagnóstico
        btn_refresh = tk.Button(
            diag_frame,
            text="🔄 Atualizar",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#F8FAFC",
            activebackground="#475569",
            activeforeground="#FFFFFF",
            relief="flat",
            command=self._atualizar_diagnostico
        )
        btn_refresh.pack(side="right")

        # 3. Grade de Módulos (Cards de Ação)
        cards_container = tk.Frame(self.root, bg="#0F172A", padx=20)
        cards_container.pack(fill="both", expand=True)

        cards = [
            {
                "icone": "📁",
                "titulo": "Preparação de Projeto SOB",
                "descricao": "Criação de pastas, download automático de croquis do SharePoint/GOMNET e cópia para {BASE}_{SOB}_DESENHO.dwg.",
                "acao_texto": "Abrir SOB",
                "comando": self._abrir_guia_sob,
                "cor_borda": "#3B82F6"
            },
            {
                "icone": "⚡",
                "titulo": "Diagrama Unifilar & Proteção",
                "descricao": "Localização da proteção a montante (SG/CF/REL), árvore de dispositivos e inserção do unifilar 2.5D no DWG.",
                "acao_texto": "Guia / Unifilar",
                "comando": self._abrir_unifilar,
                "cor_borda": "#0284C7"
            },
            {
                "icone": "📐",
                "titulo": "AutoPrancha (Enel / HBT)",
                "descricao": "Enquadramento automático da rede no ModelSpace 1:1, seleção ótima de folha A0..A4 e escala 1:500..1:2000.",
                "acao_texto": "Guia / Prancha",
                "comando": self._abrir_autoprancha,
                "cor_borda": "#0D9488"
            },
            {
                "icone": "⚡",
                "titulo": "Queda de Tensão (CQT)",
                "descricao": "Cálculo analítico BT, Live Preview de QT, carregamento do trafo e desenho dos Quadros Verdes/Vermelhos no CAD.",
                "acao_texto": "Abrir CQT",
                "comando": self._abrir_cqt,
                "cor_borda": "#0284C7"
            },
            {
                "icone": "💰",
                "titulo": "Orçamento & Materiais",
                "descricao": "Levantamento de quantitativos do DWG (postes, cabos com flecha técnica e equipamentos) com exportação Excel.",
                "acao_texto": "Abrir Orçamento",
                "comando": self._abrir_orcamento,
                "cor_borda": "#059669"
            },
            {
                "icone": "📑",
                "titulo": "Participação Financeira (CPFC)",
                "descricao": "Cálculo analítico da REN 1.059 ANEEL (ERD, COP, Fator Prop.) com emissão da planilha oficial para a distribuidora.",
                "acao_texto": "Abrir CPFC",
                "comando": self._abrir_cpfc,
                "cor_borda": "#D97706"
            },
            {
                "icone": "🌳",
                "titulo": "Estudo & Memorial Ambiental",
                "descricao": "Auditoria de restrições em KMZ/KML (APPs e UCs), checklist automatizado e geração de croqui de satélite Snyder.",
                "acao_texto": "Abrir Ambiental",
                "comando": self._abrir_ambiental,
                "cor_borda": "#16A34A"
            },
            {
                "icone": "🗺️",
                "titulo": "Estúdio Web de Satélite & Postes",
                "descricao": "Servidor HTTP local integrado com mapa Leaflet, satélite ESRI/Google e injeção direta de blocos no AutoCAD.",
                "acao_texto": "Iniciar Estúdio Web",
                "comando": self._abrir_mapa_web,
                "cor_borda": "#7C3AED"
            },
            {
                "icone": "📐",
                "titulo": "Paleta Cartográfica OSM (.NET)",
                "descricao": "Paleta docked nativa no AutoCAD com Overpass, vias, calçadas, snap magnético e traçado contínuo.",
                "acao_texto": "Guia / Comandos CAD",
                "comando": self._abrir_guia_paleta,
                "cor_borda": "#06B6D4"
            },
            {
                "icone": "📊",
                "titulo": "Tabelas de Referência Normativas",
                "descricao": "Consulta de cabos BT (Tab. 9), estruturas (Tab. 7), cabos MT e interpolação contínua de trações em daN.",
                "acao_texto": "Consultar Tabelas",
                "comando": self._abrir_tabelas,
                "cor_borda": "#EA580C"
            },
            {
                "icone": "🧪",
                "titulo": "Suíte de Testes & QA",
                "descricao": "Executa a suíte completa de testes unitários (275 testes) e verifica a integridade de todos os módulos.",
                "acao_texto": "Executar Testes",
                "comando": self._executar_testes,
                "cor_borda": "#DC2626"
            }
        ]

        # Layout em grade 2x5
        for idx, c in enumerate(cards):
            r = idx // 2
            col = idx % 2
            self._criar_card(cards_container, c, r, col)

        cards_container.columnconfigure(0, weight=1)
        cards_container.columnconfigure(1, weight=1)

        # 4. Rodapé Informativo e Atalhos Rápidos
        footer_frame = tk.Frame(self.root, bg="#0F172A", padx=20, pady=12)
        footer_frame.pack(fill="x")

        lbl_copy = tk.Label(
            footer_frame,
            text="IM3 Brasil • Engenharia & Projetos de Distribuição",
            font=("Segoe UI", 8),
            bg="#0F172A",
            fg="#64748B"
        )
        lbl_copy.pack(side="left")

        btn_pasta = tk.Button(
            footer_frame,
            text="📁 Abrir Pasta Raiz",
            font=("Segoe UI", 8),
            bg="#1E293B",
            fg="#94A3B8",
            relief="flat",
            command=self._abrir_pasta_raiz
        )
        btn_pasta.pack(side="right", padx=(6, 0))

        btn_limpeza = tk.Button(
            footer_frame,
            text="🧹 Limpar Temporários",
            font=("Segoe UI", 8),
            bg="#1E293B",
            fg="#94A3B8",
            relief="flat",
            command=self._executar_limpeza
        )
        btn_limpeza.pack(side="right", padx=6)

    def _criar_card(self, parent: tk.Widget, card_data: dict, row: int, col: int):
        card = tk.Frame(
            parent,
            bg="#1E293B",
            padx=12,
            pady=10,
            highlightbackground="#334155",
            highlightthickness=1
        )
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        # Cabeçalho do Card
        top_box = tk.Frame(card, bg="#1E293B")
        top_box.pack(fill="x", anchor="w")

        lbl_ico = tk.Label(top_box, text=card_data["icone"], font=("Segoe UI", 13), bg="#1E293B", fg="#F8FAFC")
        lbl_ico.pack(side="left", padx=(0, 6))

        lbl_tit = tk.Label(top_box, text=card_data["titulo"], font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#F8FAFC")
        lbl_tit.pack(side="left")

        # Descrição
        lbl_desc = tk.Label(
            card,
            text=card_data["descricao"],
            font=("Segoe UI", 8),
            bg="#1E293B",
            fg="#94A3B8",
            justify="left",
            wraplength=340
        )
        lbl_desc.pack(anchor="w", pady=(4, 8), fill="x")

        # Botão de Ação do Card
        btn_acao = tk.Button(
            card,
            text=f"🚀 {card_data['acao_texto']}",
            font=("Segoe UI", 9, "bold"),
            bg=card_data["cor_borda"],
            fg="#FFFFFF",
            activebackground="#F8FAFC",
            activeforeground="#0F172A",
            relief="flat",
            cursor="hand2",
            command=card_data["comando"]
        )
        btn_acao.pack(anchor="e")

    # --- Comandos de Ação dos Módulos ---
    def _abrir_unifilar(self):
        bat = os.path.join(BASE_DIR, "Abrir_Unifilar.bat")
        if os.path.exists(bat):
            self._lancar_subprocesso([bat], shell=True)
        else:
            msg = (
                "⚡ DIAGRAMA UNIFILAR & PROTEÇÃO (KMZ / SGT)\n\n"
                "Comandos no AutoCAD:\n"
                "  • UNIFILAR ou PROTECAO: Localiza proteção a montante (SG/CF/REL)\n"
                "  • ARVORE: Consulta caminho elétrico a montante\n\n"
                "Blocos oficiais suportados:\n"
                "  ✓ Chaves Fusíveis: bloco 'chaves_'\n"
                "  ✓ Religadores: bloco 'REL.' (com fallback bidirecional 'REL')\n"
                "  ✓ Transformadores: bloco 'TRAFO1'"
            )
            messagebox.showinfo("Diagrama Unifilar", msg)

    def _abrir_guia_sob(self):
        bat = os.path.join(BASE_DIR, "Abrir_SOB.bat")
        if os.path.exists(bat):
            self._lancar_subprocesso([bat], shell=True)
        else:
            try:
                from sob.sob_launcher_gui import lancar_dialogo_sob
                lancar_dialogo_sob(self.root)
            except Exception:
                msg = (
                    "📁 PREPARAÇÃO AUTOMÁTICA DE PROJETO SOB\n\n"
                    "Fluxo integrado diretamente ao AutoCAD:\n"
                    "  1. Digite SOB (ou NOVASOB / PREPARAR_SOB) no console do AutoCAD\n"
                    "  2. Informe o número da SOB (ex: A057349839)\n"
                    "  3. Escolha a Base técnica (ex: PE, CF, AN, RE, NI, MA, SG, TE)\n"
                    "  4. Escolha a pasta de destino no diálogo nativo do Windows\n"
                    "  5. O sistema cria SOB_... e subpasta CROQUI com proteção contra sobrescrita\n"
                    "  6. Conecta ao SharePoint/GOMNET e baixa croquis e anexos\n"
                    "  7. Copia o modelo para {BASE}_{SOB}_DESENHO.dwg\n"
                    "  8. Abre o desenho automaticamente no AutoCAD!"
                )
                messagebox.showinfo("Preparação de Projeto SOB", msg)

    def _abrir_autoprancha(self):
        bat = os.path.join(BASE_DIR, "Abrir_AutoPrancha.bat")
        if os.path.exists(bat):
            self._lancar_subprocesso([bat], shell=True)
        else:
            msg = (
                "📐 AUTOPRANCHA ENEL / HBT (MODELSPACE 1:1)\n\n"
                "Comandos no AutoCAD:\n"
                "  • AUTOPRANCHA (ou PRANCHA / ENQUADRAR / FOLHA)\n"
                "  • RECARREGAR_PRANCHA\n\n"
                "Funcionalidades:\n"
                "  ✓ Seleção ótima de folha A0..A4 e escala 1:500..1:2000\n"
                "  ✓ Desconto de margens e reserva técnica de carimbo\n"
                "  ✓ Camadas técnicas A-PRANCHA, A-PRANCHA-MARGEM, A-PRANCHA-DOBRA"
            )
            messagebox.showinfo("AutoPrancha Enel/HBT", msg)

    def _abrir_cqt(self):
        script = os.path.join(BASE_DIR, "cqt", "cqt_excel_manager.py")
        self._lancar_subprocesso([sys.executable, script])

    def _abrir_orcamento(self):
        script = os.path.join(BASE_DIR, "orcamento", "orcamento_manager.py")
        self._lancar_subprocesso([sys.executable, script])

    def _abrir_cpfc(self):
        script = os.path.join(BASE_DIR, "cpfc", "cpfc_gui.py")
        self._lancar_subprocesso([sys.executable, script])

    def _abrir_ambiental(self):
        script = os.path.join(BASE_DIR, "ambiental", "memorial_ambiental_generator.py")
        self._lancar_subprocesso([sys.executable, script])

    def _abrir_mapa_web(self):
        bat = os.path.join(BASE_DIR, "Abrir_Mapa_Postes.bat")
        if os.path.exists(bat):
            self._lancar_subprocesso([bat], shell=True)
        else:
            script = os.path.join(BASE_DIR, "mapa_postes", "mapa_servidor.py")
            self._lancar_subprocesso([sys.executable, script])

    def _abrir_guia_paleta(self):
        msg = (
            "📌 PALETA CARTOGRÁFICA OSM NO AUTOCAD\n\n"
            "A paleta roda acoplada dentro da tela do AutoCAD via C# .NET + WebView2.\n\n"
            "Comandos no console do AutoCAD:\n"
            "  • OSMPALETA (ou MAPAPALETA): Abre a paleta acoplada à direita\n"
            "  • FECHAR_MAPAPALETA: Fecha a paleta\n"
            "  • RECARREGAR_MAPAPALETA: Recarrega as rotinas e a DLL\n\n"
            "Recursos integrados na Paleta:\n"
            "  ✓ Vias e calçadas urbanas (Overpass API)\n"
            "  ✓ Régua com azimute e distância métrica\n"
            "  ✓ Snap magnético aos postes e nós da rede\n"
            "  ✓ Traçado contínuo com exportação direta para CQT"
        )
        messagebox.showinfo("Paleta OSM AutoCAD", msg)

    def _abrir_tabelas(self):
        script = os.path.join(BASE_DIR, "dados_tecnicos", "tabelas_referencia.py")
        self._lancar_subprocesso([sys.executable, script, "--json"])

    def _executar_testes(self):
        def _run():
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "pytest", "tests/", "-q"],
                    cwd=BASE_DIR,
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0:
                    messagebox.showinfo("Sucesso nos Testes (QA)", f"✓ Todos os testes passaram com sucesso!\n\n{res.stdout.strip()}")
                else:
                    messagebox.showwarning("Aviso nos Testes", f"Alguns testes falharam:\n\n{res.stdout or res.stderr}")
            except Exception as ex:
                messagebox.showerror("Erro ao Executar Testes", f"Falha ao rodar pytest: {ex}")

        threading.Thread(target=_run, daemon=True).start()
        messagebox.showinfo("Executando Testes", "A suíte de testes está sendo executada em segundo plano...\nO resultado será exibido em instantes.")

    def _abrir_pasta_raiz(self):
        if platform.system() == "Windows":
            os.startfile(BASE_DIR)

    def _executar_limpeza(self):
        clean_bat = os.path.join(BASE_DIR, "clean.bat")
        if os.path.exists(clean_bat):
            self._lancar_subprocesso([clean_bat], shell=True)
            messagebox.showinfo("Limpeza Concluída", "Script clean.bat executado para limpeza de temporários.")

    def _atualizar_diagnostico(self):
        self.acad_rodando = verificar_processo_autocad()
        self.branch_git = obter_branch_git()
        messagebox.showinfo("Diagnóstico Atualizado", f"AutoCAD em execução: {'Sim' if self.acad_rodando else 'Não'}\nBranch Git: {self.branch_git}")

    def _lancar_subprocesso(self, cmd, shell=False):
        try:
            if platform.system() == "Windows" and not shell:
                subprocess.Popen(cmd, cwd=BASE_DIR, creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen(cmd, cwd=BASE_DIR, shell=shell)
        except Exception as ex:
            messagebox.showerror("Erro de Execução", f"Não foi possível iniciar o módulo:\n{ex}")


def main():
    root = tk.Tk()
    app = AuxCadHubApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
