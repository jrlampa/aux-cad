"""
Módulo de Importação Direta de Marcadores KMZ/KML do Google Earth para o AutoCAD.
Extrai pontos georreferenciados de campo (<Placemark>), converte para coordenadas
planas UTM SIRGAS 2000 / WGS84 analiticamente (Snyder) e gera comandos AutoCAD (LISP)
para inserção automática do bloco 'POSTE_', do bloco numerador 'PONTO' e do texto
técnico lateral descritivo (tipo, esforço, estruturas MT/BT).
"""

import argparse
import html
import json
import math
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET


@dataclass
class PosteKMZ:
    """Representa um poste/marcador importado do Google Earth."""
    nome: str
    descricao_linhas: List[str]
    lon: float
    lat: float
    x_utm: float
    y_utm: float
    fuso: int
    hemisferio_norte: bool = False
    metadados: Dict[str, str] = field(default_factory=dict)


def latlon_to_utm(lat: float, lon: float, zone: int, northern_hemisphere: bool = False) -> Tuple[float, float]:
    """
    Converte coordenadas Latitude / Longitude (WGS84 / SIRGAS 2000)
    para UTM Easting (X) e Northing (Y) em metros com precisão analítica Snyder.
    """
    a = 6378137.0
    f = 1 / 298.257223563
    e_sq = (2 * f) - (f ** 2)
    e_prime_sq = e_sq / (1 - e_sq)
    k0 = 0.9996

    lat_rad = math.radians(lat)
    lon_origin = (zone - 1) * 6 - 180 + 3
    lon_origin_rad = math.radians(lon_origin)
    lon_rad = math.radians(lon)

    delta_lon = lon_rad - lon_origin_rad

    sin_phi = math.sin(lat_rad)
    cos_phi = math.cos(lat_rad)
    tan_phi = math.tan(lat_rad)

    n = a / math.sqrt(1 - e_sq * (sin_phi ** 2))
    t = tan_phi ** 2
    c = e_prime_sq * (cos_phi ** 2)
    a_val = cos_phi * delta_lon

    m = a * (
        (1 - e_sq / 4 - 3 * (e_sq ** 2) / 64 - 5 * (e_sq ** 3) / 256) * lat_rad
        - (3 * e_sq / 8 + 3 * (e_sq ** 2) / 32 + 45 * (e_sq ** 3) / 1024) * math.sin(2 * lat_rad)
        + (15 * (e_sq ** 2) / 256 + 45 * (e_sq ** 3) / 1024) * math.sin(4 * lat_rad)
        - (35 * (e_sq ** 3) / 3072) * math.sin(6 * lat_rad)
    )

    x = 500000.0 + k0 * n * (
        a_val
        + (1 - t + c) * (a_val ** 3) / 6
        + (5 - 18 * t + (t ** 2) + 72 * c - 58 * e_prime_sq) * (a_val ** 5) / 120
    )

    y = k0 * (
        m
        + n * tan_phi * (
            (a_val ** 2) / 2
            + (5 - t + 9 * c + 4 * (c ** 2)) * (a_val ** 4) / 24
            + (61 - 58 * t + (t ** 2) + 600 * c - 330 * e_prime_sq) * (a_val ** 6) / 720
        )
    )

    if not northern_hemisphere:
        y += 10000000.0

    return x, y


def detectar_fuso_utm(lon: float) -> int:
    """Calcula o fuso UTM padrão (1 a 60) a partir da longitude."""
    return int((lon + 180.0) / 6.0) + 1


def sanitizar_descricao(descricao_bruta: Optional[str]) -> List[str]:
    """
    Limpa tags HTML do Google Earth (<br>, <div>, <p>, &nbsp;, etc.)
    e extrai linhas de texto técnico preservando a formatação.
    """
    if not descricao_bruta:
        return []

    # Decodifica entidades HTML primeiro
    txt = html.unescape(descricao_bruta)

    # Substitui quebras de linha HTML por quebras reais
    txt = re.sub(r"(?i)<br\s*/?>", "\n", txt)
    txt = re.sub(r"(?i)</(?:p|div|tr|li)>", "\n", txt)
    txt = re.sub(r"(?i)<(?:p|div|tr|li)[^>]*>", "", txt)

    # Remove qualquer outra tag HTML
    txt = re.sub(r"<[^>]+>", "", txt)

    # Divide em linhas e sanitiza espaços
    linhas_finais = []
    for linha in txt.splitlines():
        limpa = linha.strip()
        if limpa:
            linhas_finais.append(limpa)

    return linhas_finais


def _strip_ns(tag: str) -> str:
    """Remove o namespace de uma tag XML (ex: '{http://...}Placemark' -> 'Placemark')."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def extrair_postes_kml(conteudo_xml: bytes | str, fuso_padrao: int = 23, hemisferio_norte: bool = False) -> List[PosteKMZ]:
    """
    Lê o conteúdo XML de um KML e extrai os marcadores (<Placemark>) contendo <Point>.
    Suporta namespaces múltiplos (gx:, atom:, etc.) sem falhar.
    """
    postes: List[PosteKMZ] = []
    
    if isinstance(conteudo_xml, str):
        # Se for string com declaração de encoding <?xml encoding="..."?>, codifica para bytes para o ElementTree
        if conteudo_xml.startswith("<?xml") and "encoding=" in conteudo_xml[:100].lower():
            root = ET.fromstring(conteudo_xml.encode("utf-8"))
        else:
            root = ET.fromstring(conteudo_xml)
    else:
        root = ET.fromstring(conteudo_xml)

    idx_generico = 1
    for placemark in root.iter():
        if _strip_ns(placemark.tag) != "Placemark":
            continue

        point = None
        for elem in placemark.iter():
            if _strip_ns(elem.tag) == "Point":
                point = elem
                break

        if point is None:
            continue

        coord_elem = None
        for elem in point.iter():
            if _strip_ns(elem.tag) == "coordinates" and elem.text:
                coord_elem = elem
                break

        if coord_elem is None or not coord_elem.text:
            continue

        coords_str = coord_elem.text.strip()
        # Coordenadas no KML: lon,lat[,alt] (pode conter múltiplos tokens se houver quebra de linha)
        tokens = coords_str.replace("\n", " ").replace("\r", " ").split()
        if not tokens:
            continue

        partes = tokens[0].strip().split(",")
        if len(partes) < 2:
            continue

        try:
            lon = float(partes[0].strip())
            lat = float(partes[1].strip())
        except ValueError:
            continue

        # Extrai Nome
        nome = ""
        for elem in placemark:
            if _strip_ns(elem.tag) == "name" and elem.text:
                nome = elem.text.strip()
                break

        if not nome:
            nome = f"{idx_generico:02d}"
            idx_generico += 1

        # Extrai Descrição
        desc_bruta = ""
        for elem in placemark:
            if _strip_ns(elem.tag) == "description" and elem.text:
                desc_bruta = elem.text
                break

        linhas_desc = sanitizar_descricao(desc_bruta)

        # Fuso UTM
        fuso = fuso_padrao if fuso_padrao > 0 else detectar_fuso_utm(lon)
        x_utm, y_utm = latlon_to_utm(lat, lon, fuso, northern_hemisphere=hemisferio_norte)

        poste = PosteKMZ(
            nome=nome,
            descricao_linhas=linhas_desc,
            lon=lon,
            lat=lat,
            x_utm=round(x_utm, 3),
            y_utm=round(y_utm, 3),
            fuso=fuso,
            hemisferio_norte=hemisferio_norte
        )
        postes.append(poste)

    return postes


def ler_arquivo_kmz_ou_kml(caminho_arquivo: str, fuso_padrao: int = 23, hemisferio_norte: bool = False) -> List[PosteKMZ]:
    """Lê diretamente um arquivo .kmz ou .kml e retorna a lista de postes."""
    if not os.path.exists(caminho_arquivo):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")

    ext = os.path.splitext(caminho_arquivo)[1].lower()

    if ext == ".kmz":
        with zipfile.ZipFile(caminho_arquivo, "r") as z:
            kml_files = [f for f in z.namelist() if f.lower().endswith(".kml")]
            if not kml_files:
                raise ValueError("Nenhum arquivo .kml encontrado dentro do .kmz")
            with z.open(kml_files[0]) as kf:
                conteudo_bytes = kf.read()
                return extrair_postes_kml(conteudo_bytes, fuso_padrao, hemisferio_norte)
    else:
        with open(caminho_arquivo, "rb") as f:
            conteudo_bytes = f.read()
            return extrair_postes_kml(conteudo_bytes, fuso_padrao, hemisferio_norte)



def gerar_script_lisp_postes(
    postes: List[PosteKMZ],
    caminho_saida_lsp: str,
    offset_num_x: float = -3.0,
    offset_num_y: float = -3.0,
    offset_txt_x: float = 3.0,
    offset_txt_y: float = 0.8
) -> str:
    """
    Gera um script AutoLISP completo e autônomo para inserção dos blocos
    'POSTE_', 'PONTO' e textos descritivos no AutoCAD.
    """
    linhas_lsp = [
        ";;; =============================================================================",
        ";;; Script Gerado Automaticamente pelo Importador de Postes KMZ/KML",
        ";;; Insere bloco 'POSTE_', bloco 'PONTO' com atributos e texto técnico lateral.",
        ";;; =============================================================================",
        "(vl-load-com)",
        "",
        "(defun c:EXEC_IMPORT_KMZ_POSTES ( / acad doc space layers layObj c p blkName pBase pNum pTxt mTextObj atts tag )",
        "  (setq acad (vlax-get-acad-object))",
        "  (setq doc (vla-get-ActiveDocument acad))",
        "  (if (= (getvar \"CVPORT\") 1)",
        "    (setq space (vla-get-PaperSpace doc))",
        "    (setq space (vla-get-ModelSpace doc))",
        "  )",
        "  (setq layers (vla-get-Layers doc))",
        "",
        "  ;; Função interna para criar Layer com cor",
        "  (defun criar-camada (nome cor / l)",
        "    (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-Item (list layers nome)))",
        "      (progn",
        "        (setq l (vla-Add layers nome))",
        "        (vla-put-Color l cor)",
        "      )",
        "    )",
        "  )",
        "",
        "  ;; 1. Criação de Layers Padronizados (2.5D)",
        "  (criar-camada \"POSTES_SIMBOLO\" 3)    ; Verde",
        "  (criar-camada \"POSTES_NUMERO\" 3)     ; Verde",
        "  (criar-camada \"POSTES_DESCRICAO\" 7)  ; Branco / Padrão",
        "",
        "  (vla-StartUndoMark doc)",
        ""
    ]

    for p in postes:
        x = p.x_utm
        y = p.y_utm
        num_x = round(x + offset_num_x, 3)
        num_y = round(y + offset_num_y, 3)
        txt_x = round(num_x + offset_txt_x, 3)
        txt_y = round(num_y + offset_txt_y, 3)

        nome_escapado = p.nome.replace('"', '\\"')

        linhas_lsp.extend([
            f"  ;; --- Poste {nome_escapado} (UTM X: {x}, Y: {y}) ---",
            f"  (setq pBase (vlax-3d-point (list {x} {y} 0.0)))",
            f"  (setq pNum  (vlax-3d-point (list {num_x} {num_y} 0.0)))",
            "",
            "  ;; A) Inserção do Bloco 'POSTE_' (ou Fallback se não existir no DWG)",
            "  (if (tblsearch \"BLOCK\" \"POSTE_\")",
            "    (progn",
            f"      (setq blk (vla-InsertBlock space pBase \"POSTE_\" 1.0 1.0 1.0 0.0))",
            "      (vla-put-Layer blk \"POSTES_SIMBOLO\")",
            "    )",
            "    (progn",
            "      (setq c (vla-AddCircle space pBase 0.6))",
            "      (vla-put-Layer c \"POSTES_SIMBOLO\")",
            "      (setq ptObj (vla-AddPoint space pBase))",
            "      (vla-put-Layer ptObj \"POSTES_SIMBOLO\")",
            "    )",
            "  )",
            "",
            "  ;; B) Inserção do Bloco 'PONTO' com Atributo de Número",
            "  (if (tblsearch \"BLOCK\" \"PONTO\")",
            "    (progn",
            f"      (setq blk (vla-InsertBlock space pNum \"PONTO\" 1.0 1.0 1.0 0.0))",
            "      (vla-put-Layer blk \"POSTES_NUMERO\")",
            "      (if (= (vla-get-HasAttributes blk) :vlax-true)",
            "        (foreach att (vlax-safearray->list (vlax-variant-value (vla-GetAttributes blk)))",
            f"          (vla-put-TextString att \"{nome_escapado}\")",
            "        )",
            "      )",
            "    )",
            "    (progn",
            "      ;; Fallback para Bloco PONTO: Círculo verde + Texto centralizado",
            "      (setq c (vla-AddCircle space pNum 1.8))",
            "      (vla-put-Layer c \"POSTES_NUMERO\")",
            f"      (setq tObj (vla-AddText space \"{nome_escapado}\" pNum 1.8))",
            "      (vla-put-Alignment tObj 10) ; acAlignmentMiddleCenter",
            "      (vla-put-TextAlignmentPoint tObj pNum)",
            "      (vla-put-Layer tObj \"POSTES_NUMERO\")",
            "    )",
            "  )",
            ""
        ])

        if p.descricao_linhas:
            linhas_lsp.append("  ;; C) Descrição Técnica Lateral (Linhas Empilhadas)")
            altura_texto = 1.8
            espacamento_y = 2.60
            for idx_linha, linha in enumerate(p.descricao_linhas):
                cur_y = round(txt_y - (idx_linha * espacamento_y), 3)
                linha_escapada = linha.replace('"', '\\"')
                linhas_lsp.extend([
                    f"  (setq tObj (vla-AddText space \"{linha_escapada}\" (vlax-3d-point (list {txt_x} {cur_y} 0.0)) {altura_texto}))",
                    "  (vla-put-Layer tObj \"POSTES_DESCRICAO\")"
                ])
            linhas_lsp.append("")



    linhas_lsp.extend([
        "  (vla-EndUndoMark doc)",
        "  (vla-ZoomExtents acad)",
        f"  (princ \"\\n[Sucesso] {len(postes)} postes importados com simbologia, numeracao e descricao!\")",
        "  (princ)",
        ")",
        "",
        ";; Executa imediatamente ao carregar",
        "(c:EXEC_IMPORT_KMZ_POSTES)",
        "(princ)"
    ])

    codigo_lsp = "\n".join(linhas_lsp)
    os.makedirs(os.path.dirname(os.path.abspath(caminho_saida_lsp)), exist_ok=True)
    with open(caminho_saida_lsp, "w", encoding="utf-8") as f:
        f.write(codigo_lsp)

    return caminho_saida_lsp


def main():
    """Interface CLI do importador."""
    parser = argparse.ArgumentParser(description="Importador direto de KMZ/KML para o AutoCAD (POSTE_, PONTO e anotações)")
    parser.add_argument("arquivo", help="Caminho do arquivo .kmz ou .kml do Google Earth")
    parser.add_argument("--fuso", type=int, default=23, help="Fuso UTM (padrão: 23)")
    parser.add_argument("--norte", action="store_true", help="Hemisfério Norte (padrão: Sul/False)")
    parser.add_argument("--saida", default=None, help="Caminho do script .lsp de saída gerado")
    parser.add_argument("--json", action="store_true", help="Gera saída em JSON estruturado")

    args = parser.parse_args()

    try:
        postes = ler_arquivo_kmz_ou_kml(args.arquivo, fuso_padrao=args.fuso, hemisferio_norte=args.norte)
        print(f"[OK] {len(postes)} marcadores lidos com sucesso do arquivo: {args.arquivo}")

        if args.json:
            dados = [
                {
                    "nome": p.nome,
                    "descricao": p.descricao_linhas,
                    "lat": p.lat,
                    "lon": p.lon,
                    "x_utm": p.x_utm,
                    "y_utm": p.y_utm,
                    "fuso": p.fuso
                }
                for p in postes
            ]
            print(json.dumps(dados, indent=2, ensure_ascii=False))

        saida_lsp = args.saida
        if not saida_lsp:
            pasta = os.path.dirname(os.path.abspath(args.arquivo))
            saida_lsp = os.path.join(pasta, "kmz_import_postes_exec.lsp")

        gerar_script_lisp_postes(postes, saida_lsp)
        print(f"[OK] Rotina AutoLISP gerada com sucesso em: {saida_lsp}")

    except Exception as e:
        print(f"[ERRO] Falha ao processar arquivo KMZ/KML: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
