# -*- coding: utf-8 -*-
"""
unifilar_diagrama_builder.py - Construtor de Geometria 2.5D do Diagrama Unifilar
Responsabilidade: Geração de entidades gráficas (linhas, barramentos, blocos 'chaves_' / 'REL',
rotulação técnica e nós de projeto) para representação esquemática sem escala e traçado no CAD.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def determinar_bloco_protecao(tipo_protecao: str, rotulo: str = "") -> str:
    """
    Retorna o nome do bloco oficial do AutoCAD correspondente ao tipo de proteção.
    - Chave Fusível: 'chaves_'
    - Religador: 'REL'
    - Disjuntor/Outro: 'chaves_' (fallback padrão)
    """
    t = (tipo_protecao or "").lower()
    r = (rotulo or "").lower()

    if "religador" in t or "rel" in t or r.startswith("rl") or "rel" in r:
        return "REL"
    if "fusivel" in t or "fusível" in t or "chave" in t or r.startswith("cf"):
        return "chaves_"
    return "chaves_"


@dataclass
class EntidadeLinha:
    x1: float
    y1: float
    x2: float
    y2: float
    layer: str = "UNIFILAR"
    cor: int = 7


@dataclass
class EntidadeTexto:
    x: float
    y: float
    texto: str
    altura: float = 2.5
    layer: str = "UNIFILAR"
    cor: int = 7
    alinhamento: str = "LEFT"  # "LEFT", "CENTER", "RIGHT"


@dataclass
class EntidadeBloco:
    nome_bloco: str  # "chaves_", "REL", "PONTO"
    x: float
    y: float
    rotacao: float = 0.0
    escala: float = 1.0
    layer: str = "UNIFILAR"
    atributos: Dict[str, str] = field(default_factory=dict)
    fallback_tipo: str = "CHAVE"  # "CHAVE", "REL", "PONTO"


@dataclass
class EsquemaUnifilar:
    """Estrutura consolidada do Diagrama Unifilar Esquemático sem escala."""
    largura_total: float
    altura_total: float
    linhas: List[EntidadeLinha] = field(default_factory=list)
    textos: List[EntidadeTexto] = field(default_factory=list)
    blocos: List[EntidadeBloco] = field(default_factory=list)


def construir_esquema_unifilar(
    subestacao: str,
    alimentador: str,
    protecao_rotulo: str,
    protecao_tipo: str,
    ponto_alvo: str = "P01",
    clientes_a: int = 0,
    clientes_b: int = 0,
    kva: float = 0.0,
    pt_base: Tuple[float, float] = (0.0, 0.0),
    escala_h: float = 2.5
) -> EsquemaUnifilar:
    """
    Constrói a geometria esquemática vetorial 2.5D padronizada do Unifilar.
    - Barramento SE (linha dupla/grossa no topo)
    - Linha tronco MT descendo
    - Dispositivo de proteção a montante (bloco 'chaves_' ou 'REL')
    - Ramal MT até o Ponto do Projeto
    """
    bx, by = pt_base
    h = escala_h
    sp = h * 1.6

    linhas: List[EntidadeLinha] = []
    textos: List[EntidadeTexto] = []
    blocos: List[EntidadeBloco] = []

    # 1. BLOCO DE TEXTOS TÉCNICOS (À ESQUERDA)
    # Título Verde Sublinhado
    textos.append(EntidadeTexto(bx, by, "DIAGRAMA  UNIFILAR", altura=h * 1.2, layer="UNIFILAR", cor=3, alinhamento="LEFT"))
    linhas.append(EntidadeLinha(bx, by - h * 0.3, bx + h * 14.0, by - h * 0.3, layer="UNIFILAR", cor=3))

    x_al = bx + h * 14.0
    y_cur = by - sp * 1.5

    textos.append(EntidadeTexto(x_al, y_cur, f"SE.: {subestacao}", altura=h, layer="UNIFILAR", cor=7, alinhamento="RIGHT"))
    y_cur -= sp
    textos.append(EntidadeTexto(x_al, y_cur, f"ALIM.: {alimentador}", altura=h, layer="UNIFILAR", cor=7, alinhamento="RIGHT"))
    y_cur -= sp
    textos.append(EntidadeTexto(x_al, y_cur, "FONTE DE ALIMENTAÇÃO", altura=h, layer="UNIFILAR", cor=7, alinhamento="RIGHT"))
    y_cur -= sp
    textos.append(EntidadeTexto(x_al, y_cur, f"DISPOSITIVO DE PROTEÇÃO: {protecao_rotulo}", altura=h, layer="UNIFILAR", cor=7, alinhamento="RIGHT"))
    y_cur -= sp
    kva_txt = f"{kva:g}" if kva else "0"
    textos.append(EntidadeTexto(x_al, y_cur, f"Clientes Grupo A: {clientes_a} Clientes Grupo B: {clientes_b} - KVA: {kva_txt}", altura=h, layer="UNIFILAR", cor=7, alinhamento="RIGHT"))

    # 2. ESQUEMA GRÁFICO UNIFILAR SEM ESCALA (À DIREITA DOS TEXTOS)
    x_diag_offset = bx + h * 18.0
    largura_barramento = h * 12.0
    x_se_ini = x_diag_offset
    x_se_fim = x_diag_offset + largura_barramento
    x_tronco = x_diag_offset + (largura_barramento / 2.0)
    y_barramento = by - h * 1.0

    # 2.1 Barramento da SE
    linhas.append(EntidadeLinha(x_se_ini, y_barramento, x_se_fim, y_barramento, layer="UNIFILAR_SE", cor=3))
    linhas.append(EntidadeLinha(x_se_ini, y_barramento - h * 0.2, x_se_fim, y_barramento - h * 0.2, layer="UNIFILAR_SE", cor=3))
    textos.append(EntidadeTexto(x_tronco, y_barramento + h * 0.8, f"BARRAMENTO SE {subestacao} - ALIM {alimentador}", altura=h * 0.8, layer="UNIFILAR_SE", cor=3, alinhamento="CENTER"))

    # 2.2 Tronco MT descendo até a proteção
    y_chave = y_barramento - h * 6.0
    linhas.append(EntidadeLinha(x_tronco, y_barramento - h * 0.2, x_tronco, y_chave + h * 1.2, layer="UNIFILAR_LINHA", cor=7))
    textos.append(EntidadeTexto(x_tronco + h * 0.6, y_barramento - h * 3.0, "TRONCO MT", altura=h * 0.7, layer="UNIFILAR_LINHA", cor=8, alinhamento="LEFT"))

    # 2.3 Bloco do Dispositivo de Proteção
    nome_bloco = determinar_bloco_protecao(protecao_tipo, protecao_rotulo)
    blocos.append(EntidadeBloco(
        nome_bloco=nome_bloco,
        x=x_tronco,
        y=y_chave,
        rotacao=0.0,
        escala=1.0,
        layer="UNIFILAR_PROTECAO",
        atributos={"TAG": protecao_rotulo, "TIPO": protecao_tipo},
        fallback_tipo="REL" if nome_bloco == "REL" else "CHAVE"
    ))
    textos.append(EntidadeTexto(x_tronco + h * 2.0, y_chave, protecao_rotulo, altura=h * 0.9, layer="UNIFILAR_PROTECAO", cor=1, alinhamento="LEFT"))

    # 2.4 Ramal MT descendo até o Ponto do Projeto
    y_ponto = y_chave - h * 6.0
    linhas.append(EntidadeLinha(x_tronco, y_chave - h * 1.2, x_tronco, y_ponto + h * 1.0, layer="UNIFILAR_LINHA", cor=7))
    textos.append(EntidadeTexto(x_tronco + h * 0.6, y_chave - h * 3.0, "RAMAL PROJETO", altura=h * 0.7, layer="UNIFILAR_LINHA", cor=8, alinhamento="LEFT"))

    # 2.5 Ponto do Projeto (Bloco PONTO ou círculo)
    blocos.append(EntidadeBloco(
        nome_bloco="PONTO",
        x=x_tronco,
        y=y_ponto,
        rotacao=0.0,
        escala=1.0,
        layer="UNIFILAR_PONTO",
        atributos={"NUM": ponto_alvo},
        fallback_tipo="PONTO"
    ))
    textos.append(EntidadeTexto(x_tronco + h * 2.0, y_ponto, f"{ponto_alvo} ({kva_txt} kVA)", altura=h * 0.9, layer="UNIFILAR_PONTO", cor=2, alinhamento="LEFT"))

    return EsquemaUnifilar(
        largura_total=x_se_fim - bx + h * 4.0,
        altura_total=by - y_ponto + h * 4.0,
        linhas=linhas,
        textos=textos,
        blocos=blocos
    )


def gerar_dicionario_esquema(esquema: EsquemaUnifilar) -> Dict:
    """Converte a estrutura do esquema para dicionário serializável em JSON."""
    return {
        "largura_total": round(esquema.largura_total, 2),
        "altura_total": round(esquema.altura_total, 2),
        "linhas": [
            {"x1": round(l.x1, 2), "y1": round(l.y1, 2), "x2": round(l.x2, 2), "y2": round(l.y2, 2), "layer": l.layer, "cor": l.cor}
            for l in esquema.linhas
        ],
        "textos": [
            {"x": round(t.x, 2), "y": round(t.y, 2), "texto": t.texto, "altura": round(t.altura, 2), "layer": t.layer, "cor": t.cor, "alinhamento": t.alinhamento}
            for t in esquema.textos
        ],
        "blocos": [
            {
                "nome_bloco": b.nome_bloco,
                "x": round(b.x, 2),
                "y": round(b.y, 2),
                "rotacao": round(b.rotacao, 2),
                "escala": round(b.escala, 2),
                "layer": b.layer,
                "atributos": b.atributos,
                "fallback_tipo": b.fallback_tipo
            }
            for b in esquema.blocos
        ]
    }
