"""
Módulo de Contagem e Detalhamento Inteligente de Postes para o Memorial Ambiental.
Analisa nomes de blocos e atributos extraídos do AutoCAD (ex: 12/300, 12/600, 10/300)
e formata o texto padronizado exigido pelas concessionárias de energia.
"""

import re
from typing import Dict, List, Tuple


def extrair_altura_esforco(texto: str) -> Tuple[int, int]:
    """
    Extrai a altura (metros) e o esforço nominal (daN) a partir de um nome de bloco ou string.
    Exemplos aceitos:
      - '12/300', '12/600', '10/300', '11/600', '9/150', '14/1000'
      - 'POSTE_12_300', 'Bloco_12/300_1', 'DT-12-600', 'CIRC-10/300'
      - '12M 300DAN', 'POSTE 12M 300 DAN'
    Retorna (altura, esforço) ou (0, 0) se não reconhecido.
    """
    if not texto:
        return 0, 0

    s = str(texto).upper().strip()

    # Padrão 1: Notação clássica de distribuição: XX/YYY ou XX-YYY ou XX_YYY
    # onde XX é a altura (9 a 18 metros) e YYY é o esforço (150 a 3000 daN)
    padrao_dist = re.search(r'(?:^|[^\d])(9|10|11|12|13|14|15|16|17|18)[\s/\-_]+(150|200|300|400|600|800|1000|1200|1500|2000|2500|3000)(?:$|[^\d])', s)
    if padrao_dist:
        alt = int(padrao_dist.group(1))
        esf = int(padrao_dist.group(2))
        return alt, esf

    # Padrão 2: Procura altura explícita com 'M' e esforço com 'DAN' ou 'KGF'
    padrao_alt = re.search(r'(?:^|[^\d])(9|10|11|12|13|14|15|16|17|18)\s*(?:M|METROS?)\b', s)
    padrao_esf = re.search(r'(?:^|[^\d])(150|200|300|400|600|800|1000|1200|1500|2000|2500|3000)\s*(?:DAN|KGF)\b', s)
    if padrao_alt and padrao_esf:
        alt = int(padrao_alt.group(1))
        esf = int(padrao_esf.group(1))
        return alt, esf

    return 0, 0


def formatar_descricao_postes(contagem_postes: Dict[Tuple[int, int], int], total_generico: int = 0) -> str:
    """
    Gera o texto padronizado de descrição dos postes para o Memorial Descritivo.
    Exemplo:
      '04 de 12 metros de altura e 300 daN de esforço, 03 de 12 metros de altura e 600 daN de esforço e 03 de 10 metros de altura e 300 daN de esforço'
    """
    if not contagem_postes:
        if total_generico > 0:
            qtd_str = f"{total_generico:02d}" if total_generico < 10 else str(total_generico)
            return f"{qtd_str} postes de concreto armado de distribuição"
        return "Nenhum poste cadastrado"

    # Ordena: maior altura primeiro, depois maior esforço
    itens_ordenados = sorted(contagem_postes.items(), key=lambda x: (x[0][0], x[0][1]), reverse=True)

    frases = []
    for (alt, esf), qtd in itens_ordenados:
        qtd_fmt = f"{qtd:02d}" if qtd < 10 else str(qtd)
        frases.append(f"{qtd_fmt} de {alt} metros de altura e {esf} daN de esforço")

    if len(frases) == 1:
        return frases[0]
    elif len(frases) == 2:
        return f"{frases[0]} e {frases[1]}"
    else:
        return ", ".join(frases[:-1]) + f" e {frases[-1]}"


def analisar_postes_projeto(pontos_lista: List[Dict]) -> Dict:
    """
    Analisa a lista de pontos georreferenciados (extraídos do CAD).
    Cada ponto pode conter: 'id', 'block_name', 'attrs', 'x', 'y', 'layer'.
    Retorna resumo com total de postes, contagem por tipo e frase técnica gerada.
    """
    contagem: Dict[Tuple[int, int], int] = {}
    nao_identificados = 0
    total_pontos = len(pontos_lista) if pontos_lista else 0

    for pt in pontos_lista:
        texto_busca = " ".join([
            str(pt.get("block_name", "")),
            str(pt.get("id", "")),
            str(pt.get("layer", "")),
            str(pt.get("attrs", ""))
        ])

        alt, esf = extrair_altura_esforco(texto_busca)
        if alt > 0 and esf > 0:
            chave = (alt, esf)
            contagem[chave] = contagem.get(chave, 0) + 1
        else:
            nao_identificados += 1

    total_identificados = sum(contagem.values())
    total_final = total_identificados + nao_identificados

    # Se não identificou nenhum tipo específico mas há pontos, formata genérico
    texto_detalhe = formatar_descricao_postes(contagem, total_generico=total_final)

    return {
        "total_postes": total_final,
        "total_identificados": total_identificados,
        "nao_identificados": nao_identificados,
        "contagem_detalhada": contagem,
        "texto_formatado": texto_detalhe
    }
