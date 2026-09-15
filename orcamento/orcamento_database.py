"""
Camada de Acesso a Dados (DAO / Repositório) para o Módulo de Orçamento.
Gerencia consultas de alto desempenho (<15ms) ao banco orcamento_dados.sqlite3,
com suporte a busca de materiais precificados, explosão de kits e tabelas de mão de obra.
"""

import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional

_curr_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(_curr_dir, "orcamento_dados.sqlite3")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Retorna conexão ativa com o banco de dados de orçamento com row_factory configurado."""
    path = db_path or DEFAULT_DB_PATH
    if not os.path.exists(path):
        # Se não existir, tenta compilar dinamicamente
        try:
            from orcamento_builder import compilar_base_dados
            compilar_base_dados(db_saida=path)
        except Exception as e:
            print(f"[AVISO] Não foi possível compilar base de orçamento: {e}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def obter_material(termo_ou_codigo: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Busca um material por código SAP/E4E, código SIE, código curto ou descrição aproximada.
    """
    if not termo_ou_codigo:
        return None

    termo = str(termo_ou_codigo).strip()
    termo_limpo = termo.upper().replace("-", "").replace("/", "").replace(" ", "")

    conn = get_connection(db_path)
    cur = conn.cursor()

    # 1. Busca exata por código E4E ou SIE ou CURTO
    cur.execute("""
        SELECT codigo_sie, codigo_e4e, codigo_curto, descricao, unidade, preco_unitario, categoria, tipo
        FROM materiais
        WHERE codigo_e4e = ? OR codigo_sie = ? OR codigo_curto = ?
        LIMIT 1;
    """, (termo, termo, termo))
    row = cur.fetchone()

    # 2. Busca por código curto normalizado (ex: DT11600, CC121000)
    if not row:
        cur.execute("""
            SELECT codigo_sie, codigo_e4e, codigo_curto, descricao, unidade, preco_unitario, categoria, tipo
            FROM materiais
            WHERE UPPER(REPLACE(REPLACE(codigo_curto, '-', ''), ' ', '')) = ?
            LIMIT 1;
        """, (termo_limpo,))
        row = cur.fetchone()

    # 3. Busca por correspondência no código técnico do poste (ex: PST_CONC_11_600 -> DT11600)
    if not row and "PST_CONC_" in termo:
        partes = termo.replace("PST_CONC_", "").split("_")
        if len(partes) >= 2:
            alt, esf = partes[0], partes[1]
            padroes_busca = [f"DT{alt}{esf}", f"DT-{alt}-{esf}", f"CC{alt}{esf}", f"CC-{alt}-{esf}"]
            for pad in padroes_busca:
                cur.execute("""
                    SELECT codigo_sie, codigo_e4e, codigo_curto, descricao, unidade, preco_unitario, categoria, tipo
                    FROM materiais
                    WHERE codigo_curto = ?
                    LIMIT 1;
                """, (pad,))
                row = cur.fetchone()
                if row:
                    break

    conn.close()
    if row:
        return dict(row)
    return None


def buscar_materiais(termo: str, limite: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Busca textual de materiais por descrição ou código."""
    if not termo:
        return []

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT codigo_sie, codigo_e4e, codigo_curto, descricao, unidade, preco_unitario, categoria, tipo
        FROM materiais
        WHERE descricao LIKE ? OR codigo_e4e LIKE ? OR codigo_sie LIKE ? OR codigo_curto LIKE ?
        ORDER BY (preco_unitario > 0) DESC, descricao ASC
        LIMIT ?;
    """, (f"%{termo}%", f"%{termo}%", f"%{termo}%", f"%{termo}%", limite))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obter_itens_kit(codigo_kit: str, ambiente: str = "NA", db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna os materiais componentes do kit com quantidades, unindo com os preços unitários.
    ambiente: 'NA' (Normal) ou 'AA' (Ambiente Agressivo / Salinidade).
    """
    if not codigo_kit:
        return []

    conn = get_connection(db_path)
    cur = conn.cursor()

    # Prioriza o ambiente selecionado; se não encontrar, tenta qualquer ambiente
    cur.execute("""
        SELECT k.codigo_kit, k.nome_kit, k.codigo_material, k.nome_material, k.qtd_material, k.ambiente,
               m.descricao AS mat_descricao, m.unidade AS mat_unidade, m.preco_unitario, m.codigo_sie
        FROM kits k
        LEFT JOIN materiais m ON (m.codigo_e4e = k.codigo_material OR m.codigo_sie = k.codigo_material)
        WHERE k.codigo_kit = ? AND (k.ambiente = ? OR ? = '')
        ORDER BY k.id ASC;
    """, (codigo_kit, ambiente, ambiente))
    rows = cur.fetchall()

    if not rows:
        # Fallback sem restrição de ambiente
        cur.execute("""
            SELECT k.codigo_kit, k.nome_kit, k.codigo_material, k.nome_material, k.qtd_material, k.ambiente,
                   m.descricao AS mat_descricao, m.unidade AS mat_unidade, m.preco_unitario, m.codigo_sie
            FROM kits k
            LEFT JOIN materiais m ON (m.codigo_e4e = k.codigo_material OR m.codigo_sie = k.codigo_material)
            WHERE k.codigo_kit = ?
            ORDER BY k.id ASC;
        """, (codigo_kit,))
        rows = cur.fetchall()

    conn.close()
    resultado = []
    for r in rows:
        d = dict(r)
        d["descricao_final"] = d.get("mat_descricao") or d.get("nome_material") or f"Material {d.get('codigo_material')}"
        d["unidade_final"] = d.get("mat_unidade") or "UN"
        d["preco_unitario"] = float(d.get("preco_unitario") or 0.0)
        d["preco_total"] = round(d["preco_unitario"] * float(d.get("qtd_material", 1.0)), 2)
        resultado.append(d)
    return resultado


def obter_servico_mo(
    voz_ou_baremo: str,
    empreiteira: str = "ENGELMIG",
    territorio: str = "A",
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Obtém a taxa contratual de mão de obra para uma voz/baremo específica.
    """
    if not voz_ou_baremo:
        return None

    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT contrato, empreiteira, baremo, voz, texto_breve, territorio, unidade, custo_unitario, grupo, descricao_completa
        FROM mao_de_obra
        WHERE (voz = ? OR baremo = ?) AND empreiteira = ? AND territorio = ?
        LIMIT 1;
    """, (voz_ou_baremo, voz_ou_baremo, empreiteira.upper(), territorio.upper()))
    row = cur.fetchone()

    # Fallback para qualquer território se não achou específico
    if not row:
        cur.execute("""
            SELECT contrato, empreiteira, baremo, voz, texto_breve, territorio, unidade, custo_unitario, grupo, descricao_completa
            FROM mao_de_obra
            WHERE (voz = ? OR baremo = ?) AND empreiteira = ?
            ORDER BY territorio ASC
            LIMIT 1;
        """, (voz_ou_baremo, voz_ou_baremo, empreiteira.upper()))
        row = cur.fetchone()

    conn.close()
    if row:
        return dict(row)
    return None


def listar_contratos(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna os contratos oficiais cadastrados."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT contrato, empreiteira, regiao, unidade_base FROM contratos ORDER BY empreiteira ASC;")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
