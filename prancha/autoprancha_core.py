"""Módulo: autoprancha_core.py
Responsabilidade Única: Motor analítico para cálculo de enquadramento de pranchas
no ModelSpace para projetos de rede de distribuição no padrão Enel / HBT.

Permite selecionar a melhor combinação de formato de papel (A0, A1, A2, A3, A4)
e escala normativa de distribuição (1:500, 1:750, 1:1000, 1:1250, 1:1500, 1:2000).
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

# Modelo corporativo imutável
PROJETISTA_OFICIAL_IM3: str = "JONATAS LAMPA"


@dataclass
class MetadadosPranchaV1:
    """Metadados cadastrais normativos da Prancha V1 (IM3 / Enel)."""
    sob_id: str
    titulo: str
    municipio: str
    bairro: str = "-"
    endereco: str = "-"
    folha: str = "1 de 1"
    data: str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y"))
    projetista: str = PROJETISTA_OFICIAL_IM3

    def para_dicionario(self) -> Dict[str, str]:
        """Exporta os campos do carimbo V1 estruturados."""
        return {
            "SOB": self.sob_id,
            "TITULO": self.titulo,
            "MUNICIPIO": self.municipio,
            "BAIRRO": self.bairro,
            "ENDERECO": self.endereco,
            "FOLHA": self.folha,
            "DATA": self.data,
            "PROJETISTA": self.projetista,
        }

    def gravar_json(self, destino: Path) -> Path:
        """Salva os metadados em arquivo JSON e LSP para intercâmbio com AutoLISP."""
        p = Path(destino)
        d = self.para_dicionario()
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

        # Gera simultaneamente o contexto .lsp correspondente
        p_lsp = p.with_suffix(".lsp")
        linhas_lsp = [
            ";;; Contexto da Prancha gerado pelo Workspace / AutoPranche",
            f'(setq *prancha-sob* "{d["SOB"]}")',
            f'(setq *prancha-titulo* "{d["TITULO"]}")',
            f'(setq *prancha-municipio* "{d["MUNICIPIO"]}")',
            f'(setq *prancha-bairro* "{d["BAIRRO"]}")',
            f'(setq *prancha-endereco* "{d["ENDERECO"]}")',
            f'(setq *prancha-folha* "{d["FOLHA"]}")',
            f'(setq *prancha-data* "{d["DATA"]}")',
            f'(setq *prancha-projetista* "{d["PROJETISTA"]}")',
        ]
        p_lsp.write_text("\n".join(linhas_lsp), encoding="utf-8")
        return p



# Assinatura de entidades mínimas e coordenadas relativas para validação de compatibilidade
MARCADORES_COMPATIBILIDADE_BLOCO: Dict[str, list] = {
    "PRANCHA": [
        {"texto": "Folha", "x": -35.89, "y": 30.24, "tol": 4.0},
        {"texto": "Escala", "x": -35.91, "y": 25.46, "tol": 4.0},
        {"texto": "DATA", "x": -86.58, "y": 15.76, "tol": 4.0},
        {"texto": "BAIRRO", "x": -117.78, "y": 15.73, "tol": 4.0},
        {"texto": "HBT", "x": -138.45, "y": 24.87, "tol": 4.0},
    ],
    "PRANCHA_A4": [
        {"texto": "Folha", "x": 261.11, "y": 30.24, "tol": 4.0},
        {"texto": "Escala", "x": 261.09, "y": 25.46, "tol": 4.0},
        {"texto": "DATA", "x": 210.42, "y": 15.76, "tol": 4.0},
        {"texto": "BAIRRO", "x": 179.22, "y": 15.73, "tol": 4.0},
        {"texto": "JONATAS LAMPA", "x": 160.03, "y": 10.55, "tol": 4.0},
    ],
}


def validar_assinatura_bloco(nome_bloco: str, entidades: list) -> str:
    """Valida a compatibilidade da definição do bloco com base nos marcadores oficiais IM3.

    Retorna 'COMPATIVEL' se todos os marcadores estiverem presentes nas coordenadas locais,
    ou 'INCOMPATIVEL' caso contrário.
    """
    nome_norm = nome_bloco.strip().upper()
    marcadores = MARCADORES_COMPATIBILIDADE_BLOCO.get(nome_norm)
    if not marcadores:
        return "INCOMPATIVEL"

    for m in marcadores:
        encontrado = False
        for ent in entidades:
            txt = ent.get("texto", "")
            if m["texto"].upper() in txt.upper():
                x = ent.get("x", 0.0)
                y = ent.get("y", 0.0)
                dist = ((x - m["x"]) ** 2 + (y - m["y"]) ** 2) ** 0.5
                if dist <= m["tol"]:
                    encontrado = True
                    break
        if not encontrado:
            return "INCOMPATIVEL"

    return "COMPATIVEL"


def resolver_metadados_prancha(workspace: Any) -> MetadadosPranchaV1:
    """Resolve os metadados cadastrais V1 a partir do ProjectWorkspace de forma controlada.

    Regras V1 (Contrato Estrito):
    - sob_id: obrigatório (workspace.sob_id). Erro controlado se ausente ou inválido.
    - titulo: metadados do workspace ou fallback determinístico '-'.
    - municipio: metadados do workspace ou fallback '-'.
    - bairro: metadados do workspace ou fallback '-'.
    - endereco: metadados do workspace ou fallback '-'.
    - folha: '1 de 1'.
    - data: data local DD/MM/AAAA.
    - projetista: 'JONATAS LAMPA' (inalterado).
    """
    if not workspace or not getattr(workspace, "sob_id", None):
        raise ValueError("Contexto de Workspace inválido: sob_id obrigatório ausente.")

    sob_id = str(workspace.sob_id).strip().upper()
    if not sob_id or sob_id in ("DESCONHECIDO", "SOB-DESCONHECIDA"):
        raise ValueError("Contexto de Workspace inválido: sob_id obrigatório ausente.")

    meta = getattr(workspace, "metadados", {}) or {}

    # 1. Título: Sem fallback arbitrário de 'REDE DE DISTRIBUICAO - {sob_id}'
    titulo_raw = meta.get("titulo") or meta.get("TITULO")
    if not titulo_raw or not str(titulo_raw).strip():
        titulo = "-"
    else:
        titulo = str(titulo_raw).strip().upper()

    # 2. Município
    mun_raw = meta.get("municipio") or meta.get("MUNICIPIO") or meta.get("cidade") or meta.get("CIDADE")
    if not mun_raw or not str(mun_raw).strip():
        municipio = "-"
    else:
        municipio = str(mun_raw).strip().upper()

    # 3. Bairro
    bairro_raw = meta.get("bairro") or meta.get("BAIRRO")
    if not bairro_raw or not str(bairro_raw).strip():
        bairro = "-"
    else:
        bairro = str(bairro_raw).strip().upper()

    # 4. Endereço
    end_raw = meta.get("endereco") or meta.get("ENDERECO") or meta.get("logradouro")
    if not end_raw or not str(end_raw).strip():
        endereco = "-"
    else:
        endereco = str(end_raw).strip().upper()

    # Fallback estruturado adicional em arquivos JSON se disponíveis no root_dir
    root_dir = getattr(workspace, "root_dir", None)
    if root_dir and Path(root_dir).exists():
        p_root = Path(root_dir)
        info_json = p_root / "prancha_dados.json"
        if info_json.exists():
            try:
                dados_extras = json.loads(info_json.read_text(encoding="utf-8"))
                if titulo == "-" and dados_extras.get("titulo"):
                    titulo = str(dados_extras["titulo"]).strip().upper()
                if municipio == "-" and dados_extras.get("municipio"):
                    municipio = str(dados_extras["municipio"]).strip().upper()
                if bairro == "-" and dados_extras.get("bairro"):
                    bairro = str(dados_extras["bairro"]).strip().upper()
                if endereco == "-" and dados_extras.get("endereco"):
                    endereco = str(dados_extras["endereco"]).strip().upper()
            except Exception:
                pass

    return MetadadosPranchaV1(
        sob_id=sob_id,
        titulo=titulo,
        municipio=municipio,
        bairro=bairro,
        endereco=endereco,
        folha="1 de 1",
        data=datetime.now().strftime("%d/%m/%Y"),
        projetista=PROJETISTA_OFICIAL_IM3,
    )



# Dimensões nominais dos formatos de papel em milímetros (largura x altura)
# Padrão ABNT NBR 10068 / Padrão Enel & HBT
FORMATOS_PAPEL_MM: Dict[str, Tuple[float, float]] = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),  # A4 paisagem (horizontal)
}

# Margens padrão da prancha em milímetros (esquerda, direita, superior, inferior)
MARGENS_PADRAO_MM: Dict[str, Tuple[float, float, float, float]] = {
    "A0": (25.0, 10.0, 10.0, 10.0),
    "A1": (25.0, 10.0, 10.0, 10.0),
    "A2": (25.0, 10.0, 10.0, 10.0),
    "A3": (25.0, 10.0, 10.0, 10.0),
    "A4": (25.0, 10.0, 10.0, 10.0),
}

# Dimensões da reserva de Carimbo oficial IM3 no canto inferior direito (mm)
# Medição física no modelo oficial prancha.dwg
LARGURA_CARIMBO_MM: float = 297.0
ALTURA_CARIMBO_MM: float = 64.27

# Escalas normativas recomendadas em projetos de distribuição aérea (1:N)
ESCALAS_NORMATIVAS: List[int] = [500, 750, 1000, 1250, 1500, 2000]

# Mapeamento do bloco oficial por formato de folha
BLOCO_POR_FORMATO: Dict[str, str] = {
    "A1": "PRANCHA",
    "A2": "PRANCHA",
    "A3": "PRANCHA",
    "A4": "PRANCHA_A4",
    "A0": "PRANCHA",  # Fallback
}


@dataclass
class EnquadramentoResultado:
    """Resultado do cálculo de enquadramento da prancha no ModelSpace."""
    formato: str
    escala: int
    fator_escala: float  # escala / 1000.0 (onde 1 unidade CAD = 1 metro)
    largura_folha_m: float
    altura_folha_m: float
    largura_util_m: float
    altura_util_m: float
    dx_projeto_m: float
    dy_projeto_m: float
    folga_x_perc: float
    folga_y_perc: float
    reserva_carimbo_largura_m: float
    reserva_carimbo_altura_m: float
    # Limites da folha no ModelSpace
    x_folha_min: float
    y_folha_min: float
    x_folha_max: float
    y_folha_max: float
    centro_projeto_x: float
    centro_projeto_y: float
    # Ponto de inserção CAD oficial conforme ancoragem do bloco
    bloco_nome: str = "PRANCHA"
    x_insercao: float = 0.0
    y_insercao: float = 0.0



def obter_area_util_mm(formato: str) -> Tuple[float, float]:
    """Retorna a largura e altura útil da folha em mm (descontadas as margens)."""
    fmt = formato.upper()
    if fmt not in FORMATOS_PAPEL_MM:
        raise ValueError(f"Formato desconhecido: {formato}")
    largura, altura = FORMATOS_PAPEL_MM[fmt]
    m_esq, m_dir, m_sup, m_inf = MARGENS_PADRAO_MM[fmt]
    largura_util = largura - (m_esq + m_dir)
    altura_util = altura - (m_sup + m_inf)
    return largura_util, altura_util


def calcular_dimensoes_model(formato: str, escala: int) -> Tuple[float, float, float, float]:
    """Calcula as dimensões da folha e da área útil no ModelSpace em metros."""
    fmt = formato.upper()
    if fmt not in FORMATOS_PAPEL_MM:
        raise ValueError(f"Formato desconhecido: {formato}")
    largura_mm, altura_mm = FORMATOS_PAPEL_MM[fmt]
    larg_util_mm, alt_util_mm = obter_area_util_mm(fmt)
    fator = escala / 1000.0

    largura_folha_m = largura_mm * fator
    altura_folha_m = altura_mm * fator
    largura_util_m = larg_util_mm * fator
    altura_util_m = alt_util_mm * fator

    return largura_folha_m, altura_folha_m, largura_util_m, altura_util_m


def calcular_enquadramento(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    escala_fixa: Optional[int] = None,
    formato_fixo: Optional[str] = None,
    margem_seguranca_perc: float = 0.10,
    preferencia_formato: str = "A1",
) -> EnquadramentoResultado:
    """Calcula o melhor formato e escala de prancha para enquadrar a área selecionada.

    Args:
        x1, y1: Primeiro canto da caixa delimitadora do projeto (metros).
        x2, y2: Canto oposto da caixa delimitadora (metros).
        escala_fixa: Se fornecida, força o uso dessa escala (ex: 1000).
        formato_fixo: Se fornecido, força o uso desse formato (ex: 'A1').
        margem_seguranca_perc: Folga de respiro mínima recomendada (padrão 10%).
        preferencia_formato: Formato preferencial em caso de empate (padrão 'A1').

    Returns:
        EnquadramentoResultado com todas as informações geométricas e de escala.
    """
    xmin = min(x1, x2)
    xmax = max(x1, x2)
    ymin = min(y1, y2)
    ymax = max(y1, y2)

    dx = max(0.01, xmax - xmin)
    dy = max(0.01, ymax - ymin)
    centro_x = (xmin + xmax) / 2.0
    centro_y = (ymin + ymax) / 2.0

    # Adicionar margem de segurança desejada
    dx_necessario = dx * (1.0 + margem_seguranca_perc)
    dy_necessario = dy * (1.0 + margem_seguranca_perc)

    formatos_a_testar = [formato_fixo.upper()] if formato_fixo else ["A3", "A2", "A1", "A0"]
    escalas_a_testar = [escala_fixa] if escala_fixa else ESCALAS_NORMATIVAS

    melhor_opcao: Optional[Tuple[str, int, float, float, float, float]] = None
    menor_desperdicio = float("inf")

    for fmt in formatos_a_testar:
        if fmt not in FORMATOS_PAPEL_MM:
            continue
        for esc in escalas_a_testar:
            larg_folha_m, alt_folha_m, larg_util_m, alt_util_m = calcular_dimensoes_model(fmt, esc)

            # Verificar se a área útil comporta o projeto com folga
            if larg_util_m >= dx_necessario and alt_util_m >= dy_necessario:
                # Calcular desperdício de papel / área livre
                area_util = larg_util_m * alt_util_m
                area_proj = dx * dy
                desperdicio = area_util - area_proj

                # Dar leve prioridade à escala 1:1000 (escala mãe da Enel)
                # e ao formato preferencial A1
                bonus_prioridade = 0.0
                if esc == 1000:
                    bonus_prioridade -= area_proj * 0.15
                if fmt == preferencia_formato.upper():
                    bonus_prioridade -= area_proj * 0.20

                custo_total = desperdicio + bonus_prioridade
                if custo_total < menor_desperdicio:
                    menor_desperdicio = custo_total
                    melhor_opcao = (fmt, esc, larg_folha_m, alt_folha_m, larg_util_m, alt_util_m)

    # Fallback se nenhum couber perfeitamente com a margem desejada:
    # Escolher o maior formato (A0) na maior escala (2000)
    if melhor_opcao is None:
        fmt_fallback = formato_fixo.upper() if formato_fixo else "A0"
        esc_fallback = escala_fixa if escala_fixa else ESCALAS_NORMATIVAS[-1]
        larg_folha_m, alt_folha_m, larg_util_m, alt_util_m = calcular_dimensoes_model(fmt_fallback, esc_fallback)
        melhor_opcao = (fmt_fallback, esc_fallback, larg_folha_m, alt_folha_m, larg_util_m, alt_util_m)

    fmt_escolhido, esc_escolhido, lf_m, af_m, lu_m, au_m = melhor_opcao
    fator = esc_escolhido / 1000.0

    # Margens no ModelSpace
    m_esq, m_dir, m_sup, m_inf = MARGENS_PADRAO_MM[fmt_escolhido]
    m_esq_m = m_esq * fator
    m_inf_m = m_inf * fator

    # Centralizar a folha de modo que a área útil fique centrada sobre o centro do projeto
    # Centro da área útil relativo ao canto inferior esquerdo da folha:
    centro_util_rel_x = m_esq_m + (lu_m / 2.0)
    centro_util_rel_y = m_inf_m + (au_m / 2.0)

    # Coordenadas mínimas e máximas da folha no ModelSpace
    x_folha_min = centro_x - centro_util_rel_x
    y_folha_min = centro_y - centro_util_rel_y
    x_folha_max = x_folha_min + lf_m
    y_folha_max = y_folha_min + af_m

    folga_x = ((lu_m - dx) / dx) * 100.0 if dx > 0 else 0.0
    folga_y = ((au_m - dy) / dy) * 100.0 if dy > 0 else 0.0

    # Determinar bloco oficial e coordenadas de inserção baseadas na ancoragem do bloco:
    # PRANCHA (A1, A2, A3): Ancorado no Canto Inferior Direito (0, 0)
    # PRANCHA_A4 (A4): Ancorado no Canto Inferior Esquerdo (0, 0)
    bloco_nome = BLOCO_POR_FORMATO.get(fmt_escolhido, "PRANCHA")
    if bloco_nome == "PRANCHA":
        x_insercao = x_folha_max
        y_insercao = y_folha_min
    else:
        x_insercao = x_folha_min
        y_insercao = y_folha_min

    return EnquadramentoResultado(
        formato=fmt_escolhido,
        escala=esc_escolhido,
        fator_escala=fator,
        largura_folha_m=round(lf_m, 3),
        altura_folha_m=round(af_m, 3),
        largura_util_m=round(lu_m, 3),
        altura_util_m=round(au_m, 3),
        dx_projeto_m=round(dx, 3),
        dy_projeto_m=round(dy, 3),
        folga_x_perc=round(folga_x, 1),
        folga_y_perc=round(folga_y, 1),
        reserva_carimbo_largura_m=round(LARGURA_CARIMBO_MM * fator, 3),
        reserva_carimbo_altura_m=round(ALTURA_CARIMBO_MM * fator, 3),
        x_folha_min=round(x_folha_min, 3),
        y_folha_min=round(y_folha_min, 3),
        x_folha_max=round(x_folha_max, 3),
        y_folha_max=round(y_folha_max, 3),
        centro_projeto_x=round(centro_x, 3),
        centro_projeto_y=round(centro_y, 3),
        bloco_nome=bloco_nome,
        x_insercao=round(x_insercao, 3),
        y_insercao=round(y_insercao, 3),
    )



def main():
    """Ponto de entrada CLI do AutoPranche."""
    parser = argparse.ArgumentParser(description="AUX CAD — AutoPranche V1 (ModelSpace)")
    parser.add_argument("--sob", type=str, help="Identificador da SOB (ex: A057349839)")
    parser.add_argument("--root", type=str, help="Diretório raiz da SOB no disco")
    parser.add_argument("--dwg", type=str, help="Caminho do DWG principal da SOB")
    parser.add_argument("--json", type=str, help="Arquivo JSON de saída/entrada de metadados")
    parser.add_argument("--exportar-contexto", action="store_true", help="Exporta prancha_contexto.json na pasta da SOB")

    args = parser.parse_args()

    sob_id = args.sob or "PROJETO_TESTE"
    root_path = Path(args.root).resolve() if args.root else Path.cwd()

    class _MockWorkspace:
        def __init__(self, s_id: str, r_path: Path):
            self.sob_id = s_id
            self.root_dir = r_path
            self.metadados = {}

    ws = _MockWorkspace(sob_id, root_path)
    meta = resolver_metadados_prancha(ws)

    if args.json:
        out_p = Path(args.json)
        meta.gravar_json(out_p)
        print(f"[AutoPranche] Metadados gravados com sucesso em: {out_p}")
    elif args.exportar_contexto and root_path.exists():
        out_p = root_path / "prancha_contexto.json"
        meta.gravar_json(out_p)
        print(f"[AutoPranche] Contexto exportado em: {out_p}")
    else:
        print("=== AUTOPRANCHE V1 — METADADOS CADASTRADOS ===")
        for k, v in meta.para_dicionario().items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    import argparse
    main()

