# -*- coding: utf-8 -*-
"""
Módulo de Parsing da Árvore de Dispositivos e Caminho Elétrico.
Responsabilidade única: Interpretação analítica de caminhos elétricos,
localização de proteção a montante e formatação técnica para Diagrama Unifilar.
"""

from dataclasses import dataclass
import re
from typing import List, Optional, Tuple


@dataclass
class DispositivoNo:
    """Representa um nó individual no caminho elétrico da rede."""
    tipo: str
    codigo: str
    texto_original: str
    clientes_a: int = 0
    clientes_b: int = 0
    kva: float = 0.0


@dataclass
class ResultadoProtecao:
    """Resultado consolidado da busca de proteção a montante."""
    sucesso: bool
    ponto_alvo: str
    subestacao: str
    alimentador: str
    protecao_tipo: str
    protecao_codigo: str
    protecao_rotulo: str
    clientes_a: int = 0
    clientes_b: int = 0
    kva: float = 0.0
    mensagem: str = ""

    def gerar_linhas_diagrama(self) -> List[str]:
        """Gera as linhas textuais prontas para inserção no AutoCAD."""
        kva_str = f"{self.kva:g}" if self.kva else "0"
        return [
            "DIAGRAMA  UNIFILAR",
            f"SE.: {self.subestacao}",
            f"ALIM.: {self.alimentador}",
            "FONTE DE ALIMENTAÇÃO",
            f"DISPOSITIVO DE PROTEÇÃO: {self.protecao_rotulo}",
            f"Clientes Grupo A: {self.clientes_a} Clientes Grupo B: {self.clientes_b} - KVA: {kva_str}",
        ]


# Tipos de dispositivos válidos como proteção primária a montante (ordem de relevância)
TIPOS_PROTECAO_VALIDOS = (
    "chave fusivel",
    "chave fusível",
    "fusivel",
    "fusível",
    "religador",
    "saida do alimentador",
    "saída do alimentador",
    "disjuntor",
)

# Dispositivos que expressamente NÃO são de proteção (seccionamento/manobra ou cargas)
TIPOS_NAO_PROTECAO = (
    "chave faca",
    "chave na",
    "ctl",
    "centro de distribuic",
    "centro de distribui",
    "transformador",
)


def normalizar_texto(texto: str) -> str:
    """Normaliza texto removendo acentos e caracteres de interrogação/substituição de encoding."""
    if not texto:
        return ""
    t = texto.strip()
    t = t.replace("\ufffd", "")
    t = t.replace("Distribuic?o", "Distribuicao").replace("distribuic?o", "distribuicao")
    t = t.replace("Distribui?o", "Distribuicao").replace("distribui?o", "distribuicao")
    t = t.replace("Sa?da", "Saida").replace("sa?da", "saida")
    t = t.replace("Fus?vel", "Fusivel").replace("fus?vel", "fusivel")
    t = t.replace("Operac?o", "Operacao").replace("operac?o", "operacao")
    return t


def eh_dispositivo_protecao(tipo: str) -> bool:
    """Verifica se o tipo corresponde a Chave Fusível, Religador, Disjuntor ou Saída do Alimentador."""
    if not tipo:
        return False
    t = normalizar_texto(tipo).lower()
    if any(np in t for np in TIPOS_NAO_PROTECAO):
        return False
    return any(p in t for p in TIPOS_PROTECAO_VALIDOS)


def extrair_se_e_alimentador(cod_alim: str) -> Tuple[str, str]:
    """
    Separa o código do alimentador em Subestação (letras) e Alimentador (dígitos).
    Exemplos:
        'RBN02' -> ('RBN', '02')
        'ZSL10' -> ('ZSL', '10')
        'ABD01' -> ('ABD', '01')
        'VR04'  -> ('VR', '04')
        'SJR12' -> ('SJR', '12')
    """
    alim_limpo = cod_alim.strip().upper()
    # Se contiver ' - ', pega a parte final (ex: 'Saida do Alimentador - ZSL10' -> 'ZSL10')
    if " - " in alim_limpo:
        alim_limpo = alim_limpo.split(" - ")[-1].strip()
    m = re.match(r"^([A-Z]+)(\d+.*)$", alim_limpo)
    if m:
        return m.group(1), m.group(2)
    return alim_limpo, alim_limpo


def parse_no_string(no_str: str) -> DispositivoNo:
    """
    Faz o parse inteligente de uma string de nó individual da árvore.
    Suporta formatos:
        - 3 partes: 'ZSL10 - Saida do Alimentador - ZSL10 Clientes Grupo A: 13 Clientes Grupo B: 2752 - KVA: 12434'
        - 2 partes: 'Saida do Alimentador - ZSL10'
        - 2 partes: 'Chave Fusivel - SG59356 Clientes Grupo A: 0 Clientes Grupo B: 76 - KVA: 150'
        - Simples: 'Chave Faca - SG59034' ou '- SG37240'
    """
    texto = normalizar_texto(no_str)

    # Extração de Clientes Grupo A, B e KVA caso constem na string
    cli_a = 0
    cli_b = 0
    kva = 0.0

    mA = re.search(r"Clientes\s+Grupo\s+A:\s*(\d+)", texto, re.IGNORECASE)
    if mA:
        cli_a = int(mA.group(1))

    mB = re.search(r"Clientes\s+Grupo\s+B:\s*(\d+)", texto, re.IGNORECASE)
    if mB:
        cli_b = int(mB.group(1))

    mK = re.search(r"KVA:\s*([\d\.,]+)", texto, re.IGNORECASE)
    if mK:
        try:
            kva = float(mK.group(1).replace(",", "."))
        except ValueError:
            kva = 0.0

    # Limpa dados estatísticos para obter apenas as partes estruturais (Tipo / Código)
    trecho_principal = re.split(r"Clientes\s+Grupo", texto, flags=re.IGNORECASE)[0].strip()
    partes = [p.strip() for p in re.split(r"\s+-\s+|\s*-\s*", trecho_principal) if p.strip()]

    tipo = ""
    codigo = ""

    tipos_conhecidos = (
        "saida do alimentador",
        "chave fusivel",
        "chave fusível",
        "fusivel",
        "fusível",
        "religador",
        "chave faca",
        "chave na",
        "ctl",
        "centro de distribuic",
        "disjuntor",
        "chave de operac",
    )

    if len(partes) >= 3:
        # Formato Concessionária: ['ZSL10', 'Saida do Alimentador', 'ZSL10']
        if any(tk in normalizar_texto(partes[1]).lower() for tk in tipos_conhecidos):
            tipo = partes[1]
            codigo = partes[2]
        else:
            tipo = partes[0]
            codigo = partes[-1]
    elif len(partes) == 2:
        if any(tk in normalizar_texto(partes[0]).lower() for tk in tipos_conhecidos):
            tipo = partes[0]
            codigo = partes[1]
        elif any(tk in normalizar_texto(partes[1]).lower() for tk in tipos_conhecidos):
            tipo = partes[1]
            codigo = partes[0]
        else:
            tipo = partes[0]
            codigo = partes[1]
    elif len(partes) == 1:
        tipo = partes[0]
        codigo = partes[0]

    return DispositivoNo(
        tipo=tipo,
        codigo=codigo,
        texto_original=texto,
        clientes_a=cli_a,
        clientes_b=cli_b,
        kva=kva,
    )


def separar_caminho_em_nos(caminho_str: str) -> List[DispositivoNo]:
    """
    Recebe um caminho completo (separado por ' > ' ou '|') e divide em lista de nós.
    """
    if not caminho_str:
        return []

    # Se estiver delimitado por '|'
    if "|" in caminho_str:
        tokens = [t.strip() for t in caminho_str.split("|") if t.strip()]
    elif " > " in caminho_str:
        tokens = [t.strip() for t in caminho_str.split(" > ") if t.strip()]
    elif ">" in caminho_str:
        tokens = [t.strip() for t in caminho_str.split(">") if t.strip()]
    else:
        tokens = [caminho_str.strip()]

    return [parse_no_string(t) for t in tokens]


def localizar_protecao_a_montante(
    caminho_str: str,
    ponto_alvo: str,
    cod_alimentador_fallback: str = "",
    clientes_a_override: Optional[int] = None,
    clientes_b_override: Optional[int] = None,
    kva_override: Optional[float] = None,
) -> ResultadoProtecao:
    """
    Analisa a árvore/caminho elétrico do alimentador até o ponto alvo e identifica
    o primeiro dispositivo de proteção imediatamente a montante (Chave Fusível, Religador,
    Disjuntor ou a própria Saída do Alimentador).
    """
    nos = separar_caminho_em_nos(caminho_str)
    ponto_alvo_limpo = ponto_alvo.strip().upper()

    # Identifica o nó raiz (Saída do Alimentador) para extrair SE e Alimentador
    no_raiz = nos[0] if nos else None
    cod_alim_detectado = cod_alimentador_fallback
    if no_raiz and ("saida" in no_raiz.tipo.lower() or "saída" in no_raiz.tipo.lower()):
        cod_alim_detectado = no_raiz.codigo or cod_alim_detectado
    elif no_raiz and no_raiz.codigo and not cod_alim_detectado:
        cod_alim_detectado = no_raiz.codigo

    subestacao, alimentador = extrair_se_e_alimentador(cod_alim_detectado)

    if not nos:
        return ResultadoProtecao(
            sucesso=False,
            ponto_alvo=ponto_alvo,
            subestacao=subestacao,
            alimentador=alimentador,
            protecao_tipo="",
            protecao_codigo="",
            protecao_rotulo="",
            mensagem="Caminho elétrico vazio ou inválido.",
        )

    # Localiza o índice do nó alvo
    idx_alvo = -1
    for i in range(len(nos) - 1, -1, -1):
        if ponto_alvo_limpo in nos[i].codigo.upper() or ponto_alvo_limpo in nos[i].texto_original.upper():
            idx_alvo = i
            break

    # Se não achou pelo código exato, busca se o último nó é o próprio alvo
    if idx_alvo == -1:
        idx_alvo = len(nos) - 1

    no_protecao: Optional[DispositivoNo] = None

    # Se o próprio nó alvo já for um dispositivo de proteção (ex: Chave Fusível ou Religador)
    if idx_alvo >= 0 and eh_dispositivo_protecao(nos[idx_alvo].tipo) and not ("saida do alimentador" in nos[idx_alvo].tipo.lower()):
        no_protecao = nos[idx_alvo]
    else:
        # Varre a montante (da posição anterior ao alvo até o início)
        for i in range(idx_alvo - 1, -1, -1):
            candidato = nos[i]
            if eh_dispositivo_protecao(candidato.tipo):
                no_protecao = candidato
                break

    # Se não encontrou nenhuma proteção intermediária (ex: apenas chaves facas),
    # a proteção é a própria Saída do Alimentador
    if not no_protecao and nos:
        for candidato in nos:
            if "saida do alimentador" in candidato.tipo.lower() or "saída do alimentador" in candidato.tipo.lower():
                no_protecao = candidato
                break

    if not no_protecao:
        return ResultadoProtecao(
            sucesso=False,
            ponto_alvo=ponto_alvo,
            subestacao=subestacao,
            alimentador=alimentador,
            protecao_tipo="",
            protecao_codigo="",
            protecao_rotulo="",
            mensagem=f"Nenhum dispositivo de proteção a montante localizado para '{ponto_alvo}'.",
        )

    # Consolida os valores de Clientes e KVA
    cli_a = clientes_a_override if clientes_a_override is not None else no_protecao.clientes_a
    cli_b = clientes_b_override if clientes_b_override is not None else no_protecao.clientes_b
    kva_val = kva_override if kva_override is not None else no_protecao.kva

    # Formatação do rótulo oficial para Diagrama Unifilar da Concessionária
    if "saida do alimentador" in no_protecao.tipo.lower() or "saída do alimentador" in no_protecao.tipo.lower():
        rotulo = f"{no_protecao.codigo} - Saida do Alimentador - {no_protecao.codigo}"
    elif no_protecao.tipo and no_protecao.codigo:
        rotulo = f"{no_protecao.tipo} - {no_protecao.codigo}"
    else:
        rotulo = no_protecao.texto_original

    return ResultadoProtecao(
        sucesso=True,
        ponto_alvo=ponto_alvo,
        subestacao=subestacao,
        alimentador=alimentador,
        protecao_tipo=no_protecao.tipo,
        protecao_codigo=no_protecao.codigo,
        protecao_rotulo=rotulo,
        clientes_a=cli_a,
        clientes_b=cli_b,
        kva=kva_val,
        mensagem="Dispositivo de proteção localizado com sucesso.",
    )
