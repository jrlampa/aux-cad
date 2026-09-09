"""
cpfc_guia_ren1059.py - Guia Didático e Regulatório da REN 1.059 / REN 1.000 ANEEL
Módulo CPFC - Cálculo de Participação Financeira do Consumidor (IM3 Brasil / Concessionária)

Apresenta aos projetistas os casos objetivos que geram Participação Financeira (PF)
e as hipóteses regulatórias de gratuidade / isenção.
"""

import tkinter as tk
from tkinter import ttk


TEXTO_GUIA_REN1059 = """
REGRAS DE PARTICIPAÇÃO FINANCEIRA DO CONSUMIDOR (REN 1.059 / REN 1.000 ANEEL)
=============================================================================

A fórmula regulatória que determina se haverá custo para o consumidor é:
    Participação Financeira (PF) = max(0, COP - ERD)

Onde:
  • COP (Custo Proporcionalizado da Obra): Fração do custo total da obra correspondente
    à demanda solicitada pelo cliente dividida pela capacidade disponibilizada pela rede.
  • ERD (Encargo de Responsabilidade da Distribuidora): Limite máximo que a concessionária
    é obrigada a investir com base na receita tarifária futura gerada pela demanda do cliente.

-----------------------------------------------------------------------------
🚨 SITUAÇÕES EM QUE OCORRE PARTICIPAÇÃO FINANCEIRA (PF > 0):
-----------------------------------------------------------------------------

1. CUSTO PROPORCIONALIZADO MAIOR QUE O LIMITE REGULATÓRIO (COP > ERD):
   • Ocorre tipicamente em extensões de rede de médio/longo alcance (muitos vãos de MT/BT)
     ou locais de topografia complexa com alto custo de material e mão de obra, para atender
     uma demanda de carga moderada. O investimento por kW ultrapassa o teto do fator K.

2. GERAÇÃO DISTRIBUÍDA (MMGD - LEI 14.300 / REN 1.059):
   • Quando a potência de geração supera a demanda de carga contratada (Geração > Carga).
   • Pela regra da REN 1.059, sobre a parcela excedente de geração incide o Fator Kgeração (Kg),
     que no Grupo B é R$ 0,00 e no Grupo A é inferior ao Kcarga. Isso reduz drasticamente o ERD,
     fazendo com que eventuais obras de reforço para escoamento de potência sejam pagas pelo acessante.

3. OBRAS DE INTERESSE RESTRITO / TENSÃO DIFERENCIADA (ART. 109 DA REN 1.000):
   • Atendimento em nível de tensão diferente do padrão da distribuidora por conveniência
     do cliente, circuitos expressos ou exigência de maior confiabilidade/reserva de capacidade.
   • Nesses casos, o custo adicional das instalações dedicadas é 100% cobrado do consumidor.

4. TRANSFORMADOR OU ATENDIMENTO EXCLUSIVO (FATOR PROP. = 100%):
   • Obras que atendem exclusivamente a um consumidor sem perspectiva de compartilhamento
     futuro de carga com terceiros (onde Demanda Cliente = Demanda Disponibilizada).
   • Se o orçamento total da obra superar o ERD da carga, a diferença integral é devida como PF.

-----------------------------------------------------------------------------
✔ HIPÓTESES DE ISENÇÃO / GRATUIDADE TOTAL (PF = 0):
-----------------------------------------------------------------------------

• Quando COP <= ERD:
  A demanda declarada gera receita tarifária futura suficiente para cobrir integralmente
  o custo proporcionalizado da obra. A concessionária arca com 100% dos custos.

• Atendimento Gratuito do Grupo B (Art. 104 da REN 1.000):
  Conexões residenciais e rurais com carga instalada até 50 kW dentro dos critérios
  de universalização e gratuidade sem ônus da ANEEL.

• Obras com Alta Taxa de Compartilhamento:
  Quando a rede é dimensionada para atender a expansão do sistema (Demanda Disponibilizada alta),
  reduzindo a fração proporcional (COP) para um valor inferior ao ERD.
"""


def exibir_modal_guia_ren1059(parent: tk.Tk):
    """Exibe modal didático e executivo detalhando as regras de Participação Financeira da ANEEL."""
    modal = tk.Toplevel(parent)
    modal.title("Guia Regulatório - Casos que Geram Participação Financeira (REN 1.059)")
    modal.geometry("760x600")
    modal.minsize(680, 480)
    modal.configure(bg="#FFFFFF")
    modal.transient(parent)
    modal.grab_set()

    # Cabeçalho
    h_frame = tk.Frame(modal, bg="#1B365D", padx=16, pady=12)
    h_frame.pack(fill=tk.X, side=tk.TOP)

    tk.Label(
        h_frame,
        text="📘 Regras e Casos de Participação Financeira (REN 1.059 ANEEL)",
        font=("Segoe UI", 12, "bold"),
        bg="#1B365D",
        fg="#FFFFFF",
    ).pack(anchor="w")

    tk.Label(
        h_frame,
        text="Critérios Oficiais para Isenção e Cobrança de Participação Financeira do Consumidor",
        font=("Segoe UI", 8),
        bg="#1B365D",
        fg="#94A3B8",
    ).pack(anchor="w")

    # Área de Texto com Rolagem
    body_frame = tk.Frame(modal, bg="#FFFFFF", padx=12, pady=10)
    body_frame.pack(fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(body_frame, orient="vertical")
    txt = tk.Text(
        body_frame,
        wrap="word",
        font=("Consolas", 9),
        bg="#F8FAFC",
        fg="#1E293B",
        padx=10,
        pady=8,
        relief="solid",
        borderwidth=1,
        yscrollcommand=scrollbar.set,
    )
    scrollbar.config(command=txt.yview)

    txt.insert(tk.END, TEXTO_GUIA_REN1059.strip())
    txt.config(state="disabled")

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Rodapé
    f_btn = tk.Frame(modal, bg="#FFFFFF", padx=16, pady=10)
    f_btn.pack(fill=tk.X, side=tk.BOTTOM)

    btn_ok = tk.Button(
        f_btn,
        text="Entendido / Fechar",
        font=("Segoe UI", 9, "bold"),
        bg="#1B365D",
        fg="#FFFFFF",
        padx=16,
        pady=6,
        relief="flat",
        cursor="hand2",
        command=modal.destroy,
    )
    btn_ok.pack(side=tk.RIGHT)
