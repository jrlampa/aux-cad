"""
Motor de Mapeamento e Explosão de Kits de Redes Aéreas (IM3 Brasil / Concessionária).
Converte anotações, blocos e estruturas do projeto (N1, M1, B1, Trafo, Aterramento, Estai)
nos seus respectivos kits oficiais e desdobra nos materiais componentes individuais com códigos SAP/E4E.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import orcamento_database as db


@dataclass
class MaterialComponente:
    codigo_kit: str
    nome_kit: str
    codigo_material: str
    descricao: str
    quantidade: float
    unidade: str = "UN"
    preco_unitario: float = 0.0
    ambiente: str = "NA"
    operacao: str = "INSTALA"  # "INSTALA", "RETIRA", "REUSE"

    @property
    def preco_total(self) -> float:
        return round(self.quantidade * self.preco_unitario, 2)


def normalizar_codigo_kit(nome_ou_cod: str, ambiente: str = "NA", esforco_poste: int = 300) -> str:
    """
    Normaliza a chave de uma estrutura para o código oficial do kit cadastrado.
    Exemplos:
      'M1' -> 'EST.M1.300-POL' ou 'EST.M1.600-POL'
      'B1' -> 'EST.B1.300-POL'
      'N1' -> 'EST.M1.300-POL' (ou kit N1)
      'TRAFO 10KVA' -> 'TR-MONO-10KVA_E' / 'AA-MONO-10KVA_E'
    """
    s = str(nome_ou_cod).upper().strip()
    esf = 600 if esforco_poste >= 600 else 300
    is_agressivo = (ambiente.upper() == "AA" or "AGRESSIVO" in s or "SALINIDADE" in s)

    # 1. Transformadores (Taqueamento)
    if "TRAFO" in s or "TRANSF" in s or "KVA" in s:
        pot = 15
        for p in [150, 112, 75, 45, 30, 15, 10]:
            if str(p) in s:
                pot = p
                break
        tipo_fase = "TRI" if pot >= 30 else ("BI" if ("BI" in s or "2F" in s) else "MONO")
        # Se for 112kVA, o mais próximo tabelado é 75 ou 150, ajusta para kit correspondente
        if pot == 112:
            pot = 75
        return f"TR-{tipo_fase}-{pot}KVA"

    # 2. Aterramentos
    if "ATERRA" in s or "ATER" in s or "HASTE" in s:
        return "ATER_EQUIP"

    # 3. Estais
    if "ESTAI" in s or "ANCORA" in s:
        return "ESTAI-7,9"

    # 4. Caixas de Derivação (DAE)
    if "DAE" in s or "CXDER" in s or "DERIV" in s:
        return "CXDERDAT"

    # 5. Estruturas MT (M1, M2, B1, B2, N1, N2, etc.)
    # Meio de rua
    if re.search(r'\bM1\b', s):
        return f"EST.M1.{esf}-POL"
    if re.search(r'\bB1\b', s):
        return f"EST.B1.{esf}-POL"
    if re.search(r'\bN1\b', s):
        return f"EST.M1.{esf}-POL"  # Concessionária unificou N1 polimérico em M1.CC
    if re.search(r'\bN2\b', s):
        return f"EST.M2.{esf}-POL"
    if re.search(r'\bM2\b', s):
        return f"EST.M2.{esf}-POL"
    if re.search(r'\bB2\b', s):
        return f"EST.B2.{esf}-POL"

    # Chave Fusível / Seccionadora
    if "CHAVE" in s or "FUSIVEL" in s or "SECC" in s:
        return "CH-FUS-15KV_E"

    return s


def explodir_kit(
    codigo_kit: str,
    ambiente: str = "NA",
    esforco_poste: int = 300,
    operacao: str = "INSTALA"
) -> List[MaterialComponente]:
    """
    Explode um kit em sua lista de materiais componentes com códigos e preços reais.
    """
    cod_norm = normalizar_codigo_kit(codigo_kit, ambiente, esforco_poste)
    itens_brutos = db.obter_itens_kit(cod_norm, ambiente)

    # Se não encontrou pelo normalizado, tenta o código original
    if not itens_brutos and cod_norm != codigo_kit:
        itens_brutos = db.obter_itens_kit(codigo_kit, ambiente)

    componentes: List[MaterialComponente] = []

    if itens_brutos:
        for r in itens_brutos:
            c_mat = str(r.get("codigo_material") or "")
            desc = r.get("descricao_final") or f"Material {c_mat}"
            un = r.get("unidade_final") or "UN"
            qtd = float(r.get("qtd_material", 1.0))
            preco_un = float(r.get("preco_unitario", 0.0))

            # Se o preço for zero, tenta buscar pelo código E4E ou SIE no banco
            if preco_un <= 0.0:
                mat_info = db.obter_material(c_mat)
                if mat_info and mat_info.get("preco_unitario"):
                    preco_un = float(mat_info["preco_unitario"])
                    if not desc or desc.startswith("Material "):
                        desc = mat_info["descricao"]
                    un = mat_info.get("unidade", un)

            componentes.append(MaterialComponente(
                codigo_kit=cod_norm,
                nome_kit=r.get("nome_kit") or cod_norm,
                codigo_material=c_mat,
                descricao=desc,
                quantidade=qtd,
                unidade=un,
                preco_unitario=preco_un,
                ambiente=ambiente,
                operacao=operacao
            ))
    else:
        # Fallback se o kit for um item direto (ex: chave individual ou transformador)
        mat_direto = db.obter_material(codigo_kit)
        if mat_direto:
            componentes.append(MaterialComponente(
                codigo_kit=codigo_kit,
                nome_kit=mat_direto.get("descricao", codigo_kit),
                codigo_material=str(mat_direto.get("codigo_e4e") or mat_direto.get("codigo_sie") or ""),
                descricao=mat_direto.get("descricao", codigo_kit),
                quantidade=1.0,
                unidade=mat_direto.get("unidade", "UN"),
                preco_unitario=float(mat_direto.get("preco_unitario", 0.0)),
                ambiente=ambiente,
                operacao=operacao
            ))

    return componentes


def explodir_poste_completo(
    estruturas: List[str],
    equipamentos: List[str],
    ambiente: str = "NA",
    esforco_poste: int = 300
) -> List[MaterialComponente]:
    """
    Desdobra todas as estruturas e equipamentos associados a um poste em materiais reais consolidados.
    """
    todos_componentes: List[MaterialComponente] = []

    for est in estruturas:
        if est:
            itens = explodir_kit(est, ambiente=ambiente, esforco_poste=esforco_poste, operacao="INSTALA")
            todos_componentes.extend(itens)

    for eq in equipamentos:
        if eq:
            itens = explodir_kit(eq, ambiente=ambiente, esforco_poste=esforco_poste, operacao="INSTALA")
            todos_componentes.extend(itens)

    return todos_componentes
