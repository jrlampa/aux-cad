"""
Módulo Central de Regras de Negócio e Cálculo de Materiais e Mão de Obra para Orçamento.
Responsável por classificar entidades do CAD (postes, cabos, estruturas e equipamentos),
explodir kits padronizados em materiais oficiais e calcular custos de mão de obra contratual
por empreiteira (Indica, Engelmig, Dínamo, Progen) e classe de território (A, B, C).
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.abspath(os.path.join(_curr_dir, ".."))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import orcamento_database as db
import orcamento_kits as kits

DEFAULT_CATALOG_PATH = os.path.join(_curr_dir, "orcamento_catalogo.json")


@dataclass
class PosteItem:
    id_poste: str
    nome_bloco: str
    altura: int
    esforco: int
    x: float = 0.0
    y: float = 0.0
    layer: str = ""
    estruturas: List[str] = field(default_factory=list)
    equipamentos: List[str] = field(default_factory=list)
    material_chave: str = "PST_CONC_GENERICO"


@dataclass
class CaboItem:
    id_cabo: str
    layer: str
    tensao: str  # "MT" ou "BT"
    comprimento_cad: float
    vaos: int = 1
    margem_pct: float = 5.0
    material_chave: str = ""
    descricao: str = ""

    @property
    def comprimento_orcado(self) -> float:
        return round(self.comprimento_cad * (1.0 + self.margem_pct / 100.0), 2)


@dataclass
class MaterialResumo:
    chave: str
    codigo: str
    descricao: str
    unidade: str
    quantidade: float
    preco_unitario: float = 0.0
    categoria: str = "Geral"
    origem_kit: str = ""

    @property
    def preco_total(self) -> float:
        return round(self.quantidade * self.preco_unitario, 2)


@dataclass
class MaoDeObraItem:
    voz: str
    baremo: str
    descricao: str
    unidade: str
    quantidade: float
    custo_unitario: float
    empreiteira: str
    territorio: str
    grupo: str = "LINHAS AÉREAS"

    @property
    def custo_total(self) -> float:
        return round(self.quantidade * self.custo_unitario, 2)


def carregar_catalogo(caminho: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Carrega o catálogo de materiais padrão a partir de JSON (para compatibilidade)."""
    caminho_final = caminho or DEFAULT_CATALOG_PATH
    if not os.path.exists(caminho_final):
        return {}
    try:
        with open(caminho_final, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("materiais", {})
    except Exception as e:
        print(f"[ERRO] Falha ao ler catálogo de materiais: {e}")
        return {}


def classificar_poste(texto: str) -> Tuple[str, int, int]:
    """
    Identifica altura e esforço nominal do poste e retorna (chave_material, altura, esforco).
    """
    if not texto:
        return "PST_CONC_GENERICO", 0, 0

    s = str(texto).upper().strip()

    # Formato clássico: 10/300, 11/600, 12/300, 12/600, 12/1000
    padrao = re.search(
        r'(?:^|[^\d])(9|10|11|12|13|14|15|16|17|18)[\s/\-_]+(150|200|300|400|600|800|1000|1200|1500|2000)(?:$|[^\d])',
        s
    )
    if padrao:
        alt = int(padrao.group(1))
        esf = int(padrao.group(2))
        chave = f"PST_CONC_{alt}_{esf}"
        return chave, alt, esf

    # Formato com 'M' e 'DAN'
    p_alt = re.search(r'(?:^|[^\d])(9|10|11|12|13|14|15|16|17|18)\s*(?:M|METROS?)\b', s)
    p_esf = re.search(r'(?:^|[^\d])(150|200|300|400|600|800|1000|1200|1500|2000)\s*(?:DAN|KGF)\b', s)
    if p_alt and p_esf:
        alt = int(p_alt.group(1))
        esf = int(p_esf.group(1))
        chave = f"PST_CONC_{alt}_{esf}"
        return chave, alt, esf

    return "PST_CONC_GENERICO", 0, 0


def classificar_cabo(layer: str, texto_extra: str = "") -> Tuple[str, str, str]:
    """
    Classifica condutor com base no layer e atributos.
    Retorna: (chave_material, tensao ["MT"|"BT"], descricao_sugerida)
    """
    raw = f"{layer} {texto_extra}".upper()

    # BT Multiplexado
    if "1X35" in raw or "1+1X35" in raw:
        return "CABO_BT_1X35_35", "BT", "Cabo BT Multiplex 1x35+35 mm²"
    if "3X35" in raw or "3+1X35" in raw:
        return "CABO_BT_3X35_35", "BT", "Cabo BT Multiplex 3x35+35 mm²"
    if "3X70" in raw or "70+50" in raw or "3+1X70" in raw or "3X70+50" in raw:
        return "CABO_BT_3X70_50", "BT", "Cabo BT Multiplex 3x70+50 mm²"
    if "3X120" in raw or "120+70" in raw or "3+1X120" in raw:
        return "CABO_BT_3X120_70", "BT", "Cabo BT Multiplex 3x120+70 mm²"

    # MT Nua CAA
    if "1/0" in raw or "RAVEN" in raw:
        return "CABO_MT_3X1_0_CAA", "MT", "Cabo MT Nu 1/0 AWG CAA (Raven)"
    if "2AWG" in raw or "2 AWG" in raw or "SPARROW" in raw:
        return "CABO_MT_3X2_CAA", "MT", "Cabo MT Nu 2 AWG CAA (Sparrow)"
    if "4AWG" in raw or "4 AWG" in raw or "SWAN" in raw:
        return "CABO_MT_3X4_CAA", "MT", "Cabo MT Nu 4 AWG CAA (Swan)"
    if "336" in raw or "LINNET" in raw:
        return "CABO_MT_3X336_CA", "MT", "Cabo MT Nu 336,4 MCM CA (Linnet)"

    # MT Compacta / Protegida
    if "COMPACT" in raw or "ESPACADOR" in raw or "PROTEGIDO" in raw:
        if "150" in raw:
            return "CABO_MT_COMPACTO_150", "MT", "Cabo MT Protegido Compacto 150 mm²"
        return "CABO_MT_COMPACTO_50", "MT", "Cabo MT Protegido Compacto 50 mm²"

    if "MT" in raw or "MEDIA" in raw or "13.8" in raw or "13800" in raw:
        return "CABO_MT_3X1_0_CAA", "MT", "Cabo MT Nu 1/0 CAA (Detectado via layer)"

    return "CABO_BT_3X70_50", "BT", "Cabo BT Multiplex 3x70+50 mm² (Detectado via layer)"


def classificar_equipamento_ou_estrutura(texto: str) -> Optional[Tuple[str, str, str]]:
    """
    Identifica estruturas (N1, N2, B1...) ou equipamentos (TRAFO, CHAVE, PARA-RAIOS, ESTAI).
    Retorna: (chave_material, categoria, descricao) ou None.
    """
    if not texto:
        return None

    s = str(texto).upper().strip()

    # Transformadores
    if "TRAFO" in s or "TRANSFORMADOR" in s or "KVA" in s:
        for pot in [150, 112, 75, 45, 30, 15, 10]:
            if str(pot) in s:
                return f"TRAFO_{pot}_KVA", "Equipamentos", f"Transformador Trifásico {pot} kVA"
        return "TRAFO_45_KVA", "Equipamentos", "Transformador Trifásico 45 kVA (Padrão)"

    # Chaves e Proteções
    if "FUSIVEL" in s or "MATHEUS" in s or "CH-FUS" in s or "CHAVE" in s:
        return "CHAVE_FUSIVEL_15KV", "Equipamentos", "Chave Fusível 15kV 100A"
    if "PARA-RAIO" in s or "PARARAIOS" in s or "PR-12" in s or "DPS" in s:
        return "PARA_RAIOS_12KV", "Equipamentos", "Pára-Raios Polimérico 12kV 10kA"

    # Estais e Aterramentos
    if "ESTAI" in s or "ANCORA" in s or "CONTRAPOSTE" in s:
        if "CONTRA" in s:
            return "ESTAI_CONTRAPOSTE", "Acessórios", "Estai Contraposte"
        return "ESTAI_ANCORA", "Acessórios", "Estai de Âncora"
    if "ATERRA" in s or "HASTE" in s or "COPPERWELD" in s:
        return "ATERRAMENTO_COMPLETO", "Acessórios", "Aterramento de Proteção"

    # Estruturas MT
    p_mt = re.search(r'\b(N1|N2|N3|N4|CE1|CE2|M1|M2|M3)\b', s)
    if p_mt:
        tipo = p_mt.group(1)
        return f"ESTRUTURA_{tipo}", "Estruturas", f"Estrutura de Montagem MT Tipo {tipo}"

    # Estruturas BT
    p_bt = re.search(r'\b(B1|B2|RS1|RS2)\b', s)
    if p_bt:
        tipo = p_bt.group(1)
        return f"ESTRUTURA_{tipo}", "Estruturas", f"Estrutura de Montagem BT Tipo {tipo}"

    return None


def processar_dados_orcamento(
    dados_cad: Dict[str, Any],
    margem_cabos_pct: float = 5.0,
    empreiteira: str = "ENGELMIG",
    territorio: str = "A",
    ambiente: str = "NA",
    bdi_pct: float = 0.0
) -> Dict[str, Any]:
    """
    Processa dados do CAD com explosão de kits oficiais e cálculo de mão de obra contratual.
    """
    catalogo = carregar_catalogo()

    postes_processados: List[PosteItem] = []
    cabos_processados: List[CaboItem] = []
    itens_materiais: Dict[str, MaterialResumo] = {}
    itens_mo: Dict[str, MaoDeObraItem] = {}

    def registrar_material(
        chave: str,
        qtd: float,
        cat_padrao: str = "Geral",
        desc_padrao: str = "",
        un_padrao: str = "UN",
        origem: str = ""
    ):
        if qtd <= 0:
            return

        # 1. Tenta buscar no banco de dados oficial
        mat_db = db.obter_material(chave)
        if mat_db:
            codigo = str(mat_db.get("codigo_e4e") or mat_db.get("codigo_sie") or chave)
            descricao = mat_db.get("descricao") or desc_padrao or chave
            unidade = mat_db.get("unidade") or un_padrao
            preco_un = float(mat_db.get("preco_unitario", 0.0))
            categoria = mat_db.get("categoria") or cat_padrao
        else:
            # 2. Fallback no catálogo legado
            cat_info = catalogo.get(chave, {})
            codigo = cat_info.get("codigo", "00000000")
            descricao = cat_info.get("descricao", desc_padrao or chave)
            unidade = cat_info.get("unidade", un_padrao)
            preco_un = float(cat_info.get("preco_unitario", 0.0))
            categoria = cat_info.get("categoria", cat_padrao)

        if chave not in itens_materiais:
            itens_materiais[chave] = MaterialResumo(
                chave=chave,
                codigo=codigo,
                descricao=descricao,
                unidade=unidade,
                quantidade=0.0,
                preco_unitario=preco_un,
                categoria=categoria,
                origem_kit=origem
            )
        itens_materiais[chave].quantidade = round(itens_materiais[chave].quantidade + qtd, 2)

    def registrar_mo(voz: str, qtd: float, desc_sugerida: str = ""):
        if qtd <= 0:
            return
        mo_db = db.obter_servico_mo(voz, empreiteira=empreiteira, territorio=territorio)
        if mo_db:
            custo_un = float(mo_db.get("custo_unitario", 0.0))
            desc = mo_db.get("texto_breve") or desc_sugerida or voz
            un = mo_db.get("unidade") or "UN"
            bar = mo_db.get("baremo") or ""
        else:
            custo_un = 0.0
            desc = desc_sugerida or voz
            un = "UN"
            bar = ""

        chave_mo = f"{voz}_{empreiteira}_{territorio}"
        if chave_mo not in itens_mo:
            itens_mo[chave_mo] = MaoDeObraItem(
                voz=voz,
                baremo=bar,
                descricao=desc,
                unidade=un,
                quantidade=0.0,
                custo_unitario=custo_un,
                empreiteira=empreiteira,
                territorio=territorio
            )
        itens_mo[chave_mo].quantidade = round(itens_mo[chave_mo].quantidade + qtd, 2)

    # 1. Processa Postes
    for p_raw in dados_cad.get("postes", []):
        id_p = str(p_raw.get("id", "P"))
        bloco = str(p_raw.get("bloco", ""))
        attrs = str(p_raw.get("attrs", ""))
        layer = str(p_raw.get("layer", ""))
        x = float(p_raw.get("x", 0.0))
        y = float(p_raw.get("y", 0.0))
        ests = p_raw.get("estruturas", [])
        eqs = p_raw.get("equipamentos", [])

        texto_busca = f"{bloco} {attrs} {id_p} {layer}"
        chave_pst, alt, esf = classificar_poste(texto_busca)

        poste_obj = PosteItem(
            id_poste=id_p,
            nome_bloco=bloco,
            altura=alt,
            esforco=esf,
            x=x,
            y=y,
            layer=layer,
            estruturas=ests,
            equipamentos=eqs,
            material_chave=chave_pst
        )
        postes_processados.append(poste_obj)
        registrar_material(chave_pst, 1.0, "Postes", f"Poste {alt}m / {esf} daN", "UN")

        # Mão de obra para poste: AHO110 (Poste MT) ou AHO111 (Poste BT)
        voz_poste = "AHO110" if ("MT" in layer.upper() or alt >= 11) else "AHO111"
        registrar_mo(voz_poste, 1.0, f"Instalação de Poste {alt}m/{esf}daN")

        # Mão de obra de escavação/abertura de solo: ABR106
        registrar_mo("ABR106", 1.0, "Abertura Solo Base Poste")

        # 1.1 Explosão de kits associados diretamente ao poste
        if ests or eqs:
            componentes = kits.explodir_poste_completo(ests, eqs, ambiente=ambiente, esforco_poste=esf)
            for c in componentes:
                registrar_material(
                    c.codigo_material or c.descricao,
                    c.quantidade,
                    "Estruturas",
                    c.descricao,
                    c.unidade,
                    c.nome_kit
                )

    # 2. Processa Cabos
    for c_raw in dados_cad.get("cabos", []):
        id_c = str(c_raw.get("id", "C"))
        layer = str(c_raw.get("layer", ""))
        comp = float(c_raw.get("comprimento", 0.0))
        vaos = int(c_raw.get("vaos", 1))

        if comp <= 0.0:
            continue

        chave_cabo, tensao, desc_sug = classificar_cabo(layer)
        cabo_obj = CaboItem(
            id_cabo=id_c,
            layer=layer,
            tensao=tensao,
            comprimento_cad=comp,
            vaos=vaos,
            margem_pct=margem_cabos_pct,
            material_chave=chave_cabo,
            descricao=desc_sug
        )
        cabos_processados.append(cabo_obj)
        registrar_material(chave_cabo, cabo_obj.comprimento_orcado, "Condutores", desc_sug, "M")

        # Mão de obra de condutores: AHO212 (tensionamento por vão)
        registrar_mo("AHO212", float(vaos), "Tensionar ou Soltar Condutor")

    # 3. Processa Estruturas e Equipamentos explícitos da extração CAD
    for e_raw in dados_cad.get("estruturas", []):
        texto = f"{e_raw.get('tipo', '')} {e_raw.get('bloco', '')} {e_raw.get('attrs', '')}"
        res = classificar_equipamento_ou_estrutura(texto)
        if res:
            chave, cat, desc = res
            registrar_material(chave, 1.0, cat, desc, "CJ")
            # Explode kit em componentes reais
            itens_kit = kits.explodir_kit(e_raw.get('tipo') or chave, ambiente=ambiente)
            if itens_kit:
                for it in itens_kit:
                    registrar_material(it.codigo_material or it.descricao, it.quantidade, cat, it.descricao, it.unidade, it.nome_kit)

    for eq_raw in dados_cad.get("equipamentos", []):
        texto = f"{eq_raw.get('tipo', '')} {eq_raw.get('bloco', '')} {eq_raw.get('attrs', '')}"
        res = classificar_equipamento_ou_estrutura(texto)
        if res:
            chave, cat, desc = res
            registrar_material(chave, 1.0, cat, desc, "UN")
            itens_kit = kits.explodir_kit(eq_raw.get('tipo') or chave, ambiente=ambiente)
            if itens_kit:
                for it in itens_kit:
                    registrar_material(it.codigo_material or it.descricao, it.quantidade, cat, it.descricao, it.unidade, it.nome_kit)

            # Mão de obra para trafo se for transformador: FHO110
            if "TRAFO" in chave.upper():
                registrar_mo("FHO110", 1.0, "Instalação de Trafo sobre Poste")

    # Ordenação dos materiais
    ordem_cat = {"Postes": 1, "Condutores": 2, "Estruturas": 3, "Equipamentos": 4, "Acessórios": 5, "Geral": 6}
    materiais_ordenados = sorted(
        itens_materiais.values(),
        key=lambda item: (ordem_cat.get(item.categoria, 99), item.descricao)
    )

    mo_ordenada = sorted(itens_mo.values(), key=lambda m: m.voz)

    total_mat = round(sum(m.preco_total for m in materiais_ordenados), 2)
    total_mo = round(sum(mo.custo_total for mo in mo_ordenada), 2)
    total_bdi = round((total_mat + total_mo) * (bdi_pct / 100.0), 2) if bdi_pct > 0 else 0.0
    total_geral = round(total_mat + total_mo + total_bdi, 2)

    return {
        "postes": postes_processados,
        "cabos": cabos_processados,
        "materiais": materiais_ordenados,
        "mao_de_obra": mo_ordenada,
        "total_materiais": total_mat,
        "total_mao_de_obra": total_mo,
        "total_bdi": total_bdi,
        "total_geral": total_geral,
        "qtd_postes": len(postes_processados),
        "qtd_trechos_cabo": len(cabos_processados),
        "extensao_total_m": round(sum(c.comprimento_orcado for c in cabos_processados), 2),
        "empreiteira": empreiteira,
        "territorio": territorio,
        "ambiente": ambiente,
        "bdi_pct": bdi_pct
    }
