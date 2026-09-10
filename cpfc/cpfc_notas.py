"""
cpfc_notas.py - Gerador de Notas Técnicas e Regulatórias de CPFC para o AutoCAD
Módulo CPFC - Cálculo de Participação Financeira do Consumidor (REN 1.000 / REN 1.059 ANEEL)
IM3 Brasil / Concessionária
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple


# Catálogo das 4 Notas Regulatórias Oficiais para Projetos com CPFC
NOTAS_REGULATORIAS: Dict[str, Dict[str, str]] = {
    "1": {
        "id": "1",
        "codigo": "CARGA_DISJUNTOR",
        "titulo": "1. Fora da relação Carga Instalada (kW) x Disjuntor (Arts. 98 e 99)",
        "artigos": "Arts. 98 e 99 da REN ANEEL nº 1.000/2021",
        "texto_cad": (
            "NOTA TÉCNICA - PARTICIPAÇÃO FINANCEIRA (ARTS. 98 E 99 DA REN ANEEL 1.000/2021):\n"
            "A PRESENTE SOLICITAÇÃO ENQUADRA-SE NOS TERMOS DO ART. 98 (INCISOS I A IV E § 3º) E "
            "ART. 99 (INCISOS I E II) DA RESOLUÇÃO NORMATIVA ANEEL Nº 1.000/2021. HAVENDO DISCREPÂNCIA "
            "ENTRE A CARGA INSTALADA DECLARADA (kW) E A PROTEÇÃO GERAL REQUERIDA (DISJUNTOR) OU "
            "OPÇÃO POR CONEXÃO POLIFÁSICA FORA DO PADRÃO TÉCNICO REGULAMENTAR, CABE AO SOLICITANTE "
            "O CUSTEIO DAS INSTALAÇÕES INTERNAS, SISTEMA DE MEDIÇÃO DIFERENCIADO, ADAPTAÇÕES DE REDE "
            "E A PARTICIPAÇÃO FINANCEIRA CALCULADA CONFORME REGULAÇÃO VIGENTE."
        ),
        "detalhe_legal": (
            "Art. 98: Responsabilidade do consumidor por instalações internas, interesse restrito, "
            "ponto de conexão e participação financeira (arts. 108 e seguintes). § 3º: Custo integral "
            "para mudança de nível de tensão ou local sem aumento de demanda.\n"
            "Art. 99: Pagamento da diferença de medição e custos de adaptação da rede quando a opção "
            "bifásica/trifásica < 2,3 kV for menor que a norma técnica da distribuidora."
        ),
    },
    "2": {
        "id": "2",
        "codigo": "LIGACAO_NOVA_50KW",
        "titulo": "2. Pedidos de Ligação Nova Acima de 50 kW / Sem Gratuidade (Arts. 104 e 106)",
        "artigos": "Arts. 104 e 106 da REN ANEEL nº 1.000/2021 / REN 1.059/2023",
        "texto_cad": (
            "NOTA TÉCNICA - PARTICIPAÇÃO FINANCEIRA (ARTS. 104 E 106 DA REN ANEEL 1.000/2021 / REN 1.059/2023):\n"
            "A UNIDADE CONSUMIDORA NÃO ATENDE INTEGRALMENTE AOS REQUISITOS CUMULATIVOS DE GRATUIDADE DO "
            "ART. 104 DA REN Nº 1.000/2021 (CARGA INSTALADA SUPERIOR A 50 kW, EXISTÊNCIA DE OUTRA UC NA "
            "PROPRIEDADE OU ENQUADRAMENTO NO § 2º). APLICAM-SE O ART. 106 E ART. 108, SENDO CALCULADOS "
            "O ENCARGO DE RESPONSABILIDADE DA DISTRIBUIDORA (ERD) E A PARTICIPAÇÃO FINANCEIRA DO "
            "CONSUMIDOR (PF) PELO CUSTO PROPORCIONALIZADO DA OBRA (COP)."
        ),
        "detalhe_legal": (
            "Art. 104: Conexão gratuita restrita a Grupo B <= 50 kW sem outra UC na propriedade. "
            "§ 2º: Não se aplica gratuidade à Iluminação Pública e múltiplas UCs.\n"
            "Art. 106: Obrigatoriedade de cálculo de ERD e PF para solicitações fora da gratuidade "
            "ou com micro/minigeração distribuída."
        ),
    },
    "3": {
        "id": "3",
        "codigo": "ACRESCIMO_CARGA_50KW_FASE",
        "titulo": "3. Acréscimo de Carga Acima de 50 kW ou Complementação de Fase MT (Arts. 105 e 106)",
        "artigos": "Arts. 105 e 106 da REN ANEEL nº 1.000/2021 / REN 1.059/2023",
        "texto_cad": (
            "NOTA TÉCNICA - PARTICIPAÇÃO FINANCEIRA (ARTS. 105 E 106 DA REN ANEEL 1.000/2021 / REN 1.059/2023):\n"
            "SOLICITAÇÃO DE AUMENTO DE CARGA NÃO ENQUADRADA NA GRATUIDADE DO ART. 105 DA REN Nº 1.000/2021 "
            "POR RESULTAR EM CARGA INSTALADA TOTAL SUPERIOR A 50 kW E/OU EXIGIR COMPLEMENTAÇÃO DE FASE(S) "
            "EM REDE DE TENSÃO MAIOR OU IGUAL A 2,3 kV (MÉDIA TENSÃO). CONFORME ART. 106, PROCEDEU-SE AO "
            "CÁLCULO DO ENCARGO REGULATÓRIO (ERD) E DA PARTICIPAÇÃO FINANCEIRA DO CONSUMIDOR (PF) "
            "CONFORME MEMÓRIA DE CÁLCULO CPFC EM ANEXO."
        ),
        "detalhe_legal": (
            "Art. 105: Gratuidade de aumento de carga somente se pós-aumento <= 50 kW e sem complementação de fase em MT (>= 2,3 kV).\n"
            "Art. 106: Cálculo do encargo da distribuidora e participação financeira do consumidor."
        ),
    },
    "4": {
        "id": "4",
        "codigo": "RELOCACAO_TERCEIROS",
        "titulo": "4. Relocação de Poste / Afastamento de Rede / Interesse de Terceiros (Art. 110)",
        "artigos": "Art. 110 da REN ANEEL nº 1.000/2021",
        "texto_cad": (
            "NOTA TÉCNICA - OBRAS A PEDIDO DE TERCEIROS (ART. 110 DA REN ANEEL 1.000/2021):\n"
            "OBRA EXECUTADA A PEDIDO DO CONSUMIDOR / INTERESSADO PARA DESLOCAMENTO/REMOÇÃO DE POSTE E REDE "
            "OU MELHORIA DE ASPECTOS ESTÉTICOS/INTERESSE RESTRITO, NOS TERMOS DO ART. 110 (INCISOS I A VIII "
            "E § 1º) DA REN ANEEL Nº 1.000/2021. OS CUSTOS INTEGRAIS DA OBRA, INCLUINDO EVENTUAIS REFORMAS "
            "DE CAPACIDADE OU ADEQUAÇÕES NECESSÁRIAS NA REDE, SÃO DE RESPONSABILIDADE EXCLUSIVA DO SOLICITANTE."
        ),
        "detalhe_legal": (
            "Art. 110: Custeio integral pelo solicitante para deslocamento/remoção de poste e rede, "
            "redes subterrâneas opcionais, extensão de rede de reserva e alterações estéticas.\n"
            "§ 1º: Devem ser incluídos custos de ampliação de capacidade ou reforma de SE e alimentadores."
        ),
    },
}


def obter_nota(chave: str) -> Optional[Dict[str, str]]:
    """Retorna o registro completo de uma nota pela chave (1 a 4 ou código)."""
    if chave in NOTAS_REGULATORIAS:
        return NOTAS_REGULATORIAS[chave]
    for n in NOTAS_REGULATORIAS.values():
        if n["codigo"].upper() == str(chave).upper():
            return n
    return None


def formatar_notas_cad(chaves_selecionadas: List[str], num_projeto: str = "") -> str:
    """Gera bloco consolidado de texto técnico formatado para MText no CAD."""
    blocos = []
    cabecalho = "=================================================================\n"
    cabecalho += "NOTAS TÉCNICAS DE PROJETO - PARTICIPAÇÃO FINANCEIRA (CPFC)\n"
    if num_projeto:
        cabecalho += f"PROJETO / ORDEM: {num_projeto.strip().upper()}\n"
    cabecalho += "REGULAMENTAÇÃO: RESOLUÇÃO NORMATIVA ANEEL Nº 1.000/2021 E Nº 1.059/2023\n"
    cabecalho += "================================================================="
    blocos.append(cabecalho)

    for chave in chaves_selecionadas:
        nota = obter_nota(chave)
        if nota:
            blocos.append(nota["texto_cad"])

    blocos.append(
        "OBSERVAÇÃO GERAL:\n"
        "O CÁLCULO DETALHADO DO ENCARGO DE RESPONSABILIDADE DA DISTRIBUIDORA (ERD), "
        "CUSTO PROPORCIONALIZADO (COP) E PARTICIPAÇÃO FINANCEIRA (PF) CONSTA NA "
        "PLANILHA PADRÃO CPFC VINCULADA A ESTE PROJETO."
    )

    return "\n\n".join(blocos)


def salvar_arquivo_notas(pasta_destino: str, num_projeto: str, texto_notas: str) -> str:
    """Salva as notas geradas em um arquivo de texto (.txt) na pasta do projeto."""
    os.makedirs(pasta_destino, exist_ok=True)
    nome_proj = num_projeto.strip().upper() or "PROJETO"
    nome_arquivo = f"NOTAS_CPFC_{nome_proj}.txt"
    caminho = os.path.join(pasta_destino, nome_arquivo)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto_notas)
    return caminho


def exibir_modal_notas_cpfc(parent: tk.Tk, pasta_projeto: Optional[str] = None, num_projeto: str = ""):
    """Abre janela interativa para seleção, cópia e exportação de Notas de CPFC para o CAD."""
    modal = tk.Toplevel(parent)
    modal.title("Notas Técnicas de Participação Financeira para o Desenho (CPFC)")
    modal.geometry("820x660")
    modal.minsize(740, 540)
    modal.configure(bg="#FFFFFF")
    modal.transient(parent)
    modal.grab_set()

    pasta_dest = pasta_projeto or os.getcwd()
    var_proj = tk.StringVar(value=num_projeto or "")

    # Cabeçalho
    h_frame = tk.Frame(modal, bg="#1B365D", padx=16, pady=10)
    h_frame.pack(fill=tk.X, side=tk.TOP)

    tk.Label(
        h_frame,
        text="📋 Notas Técnicas para o Desenho - CPFC (REN 1.000 / 1.059)",
        font=("Segoe UI", 12, "bold"),
        bg="#1B365D",
        fg="#FFFFFF",
    ).pack(anchor="w")

    tk.Label(
        h_frame,
        text="Selecione as situações aplicáveis à obra para gerar as notas de carimbo/prancha no CAD",
        font=("Segoe UI", 8),
        bg="#1B365D",
        fg="#94A3B8",
    ).pack(anchor="w")

    # Área de Seleção
    sel_frame = tk.LabelFrame(
        modal,
        text=" Enquadramentos Regulatórios da Obra ",
        font=("Segoe UI", 9, "bold"),
        bg="#FFFFFF",
        fg="#1B365D",
        padx=12,
        pady=8,
    )
    sel_frame.pack(fill=tk.X, padx=12, pady=(8, 4))

    check_vars: Dict[str, tk.BooleanVar] = {}

    for k, info in NOTAS_REGULATORIAS.items():
        var = tk.BooleanVar(value=(k == "1"))  # 1 selecionado por padrão
        check_vars[k] = var
        chk = tk.Checkbutton(
            sel_frame,
            text=info["titulo"],
            variable=var,
            font=("Segoe UI", 9),
            bg="#FFFFFF",
            activebackground="#FFFFFF",
            anchor="w",
            command=lambda: atualizar_previa(),
        )
        chk.pack(fill=tk.X, pady=2)

    # Campo de Projeto e Botões de Ação Rápida
    top_bar = tk.Frame(modal, bg="#FFFFFF", padx=12, pady=4)
    top_bar.pack(fill=tk.X)

    tk.Label(top_bar, text="Nº Projeto / Ordem:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF").pack(side=tk.LEFT)
    ent_proj = tk.Entry(top_bar, textvariable=var_proj, width=16, font=("Segoe UI", 9))
    ent_proj.pack(side=tk.LEFT, padx=6)
    var_proj.trace_add("write", lambda *args: atualizar_previa())

    # Área de Pré-visualização do Texto
    txt_frame = tk.Frame(modal, bg="#FFFFFF", padx=12, pady=4)
    txt_frame.pack(fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(txt_frame, orient="vertical")
    txt_preview = tk.Text(
        txt_frame,
        wrap="word",
        font=("Consolas", 9),
        bg="#F8FAFC",
        fg="#0F172A",
        padx=8,
        pady=8,
        relief="solid",
        borderwidth=1,
        yscrollcommand=scrollbar.set,
    )
    scrollbar.config(command=txt_preview.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    txt_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def obter_selecionados() -> List[str]:
        return [k for k, v in check_vars.items() if v.get()]

    def atualizar_previa():
        sel = obter_selecionados()
        if not sel:
            txt_preview.delete("1.0", tk.END)
            txt_preview.insert(tk.END, "[Selecione ao menos um enquadramento acima para gerar as notas.]")
            return
        texto = formatar_notas_cad(sel, var_proj.get())
        txt_preview.delete("1.0", tk.END)
        txt_preview.insert(tk.END, texto)

    def copiar_area_transferencia():
        txt = txt_preview.get("1.0", tk.END).strip()
        if not txt:
            return
        modal.clipboard_clear()
        modal.clipboard_append(txt)
        messagebox.showinfo("Copiado!", "Texto das notas copiado para a área de transferência!\nPronto para colar no CAD.", parent=modal)

    def salvar_arquivo():
        sel = obter_selecionados()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione ao menos um enquadramento.", parent=modal)
            return
        texto = formatar_notas_cad(sel, var_proj.get())
        caminho = salvar_arquivo_notas(pasta_dest, var_proj.get(), texto)
        messagebox.showinfo("Arquivo Salvo", f"Notas salvas com sucesso em:\n{caminho}", parent=modal)

    # Rodapé com Ações
    b_frame = tk.Frame(modal, bg="#F1F5F9", padx=14, pady=10)
    b_frame.pack(fill=tk.X, side=tk.BOTTOM)

    btn_copiar = tk.Button(
        b_frame,
        text="📋 Copiar Notas (MText)",
        font=("Segoe UI", 9, "bold"),
        bg="#0284C7",
        fg="#FFFFFF",
        padx=14,
        pady=6,
        relief="flat",
        cursor="hand2",
        command=copiar_area_transferencia,
    )
    btn_copiar.pack(side=tk.LEFT, padx=(0, 6))

    btn_salvar = tk.Button(
        b_frame,
        text="💾 Salvar Arquivo (.txt)",
        font=("Segoe UI", 9),
        bg="#10B981",
        fg="#FFFFFF",
        padx=12,
        pady=6,
        relief="flat",
        cursor="hand2",
        command=salvar_arquivo,
    )
    btn_salvar.pack(side=tk.LEFT, padx=6)

    btn_fechar = tk.Button(
        b_frame,
        text="Fechar",
        font=("Segoe UI", 9),
        bg="#E2E8F0",
        fg="#1E293B",
        padx=14,
        pady=6,
        relief="flat",
        cursor="hand2",
        command=modal.destroy,
    )
    btn_fechar.pack(side=tk.RIGHT)

    atualizar_previa()
