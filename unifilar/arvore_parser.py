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
            f"DISPOSITIVO DE PROTEÇÃO:{self.protecao_rotulo}",
            f"Clientes Grupo A: {self.clientes_a} Clientes Grupo B: {self.clientes_b} - KVA: {kva_str}",
        ]


# Tipos de dispositivos válidos como proteção primária a montante (ordem de relevância)
TIPOS_PROTECAO_VALIDOS = (
    "chave fusivel",
    "chave fusível",
    "religador",
    "saida do alimentador",
    "saída do alimentador",
)


def normalizar_texto(texto: str) -> str:
    """Normaliza texto removendo acentos e caracteres de interrogação de encoding."""
    if not texto:
        return ""
    t = texto.strip()
    t = t.replace("Distribuic?o", "Distribuicao").replace("distribuic?o", "distribuicao")
    return t


def extrair_se_e_alimentador(cod_alim: str) -> Tuple[str, str]:
    """
    Separa o código do alimentador em Subestação (letras) e Alimentador (dígitos).
    Exemplos:
        'RBN02' -> ('RBN', '02')
        'ABD01' -> ('ABD', '01')
        'VR04'  -> ('VR', '04')
        'SJR12' -> ('SJR', '12')
    """
    alim_limpo = cod_alim.strip().upper()
    # Casamento de letras iniciais seguidas de dígitos/sufixo
    m = re.match(r"^([A-Z]+)(\d+.*)$", alim_limpo)
    if m:
        return m.group(1), m.group(2)
    # Se não separar de forma padrão por regex, divide ao meio ou retorna o próprio
    return alim_limpo, alim_limpo


def parse_no_string(no_str: str) -> DispositivoNo:
    """
    Faz o parse de uma string de nó individual da árvore.
    Exemplos:
        'Chave Fusivel - SG59356 Clientes Grupo A: 0 Clientes Grupo B: 76 - KVA: 150'
        'Saida do Alimentador - RBN02'
        'Chave Faca - SG59034'
        '- SG37240'
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

    # Limpa dados estatísticos para obter apenas Tipo - Código
    trecho_principal = re.split(r"Clientes\s+Grupo", texto, flags=re.IGNORECASE)[0].strip()

    tipo = ""
    codigo = ""
    if " - " in trecho_principal:
        partes = trecho_principal.split(" - ", 1)
        tipo = partes[0].strip()
        codigo = partes[1].strip()
    elif "-" in trecho_principal:
        partes = trecho_principal.split("-", 1)
        tipo = partes[0].strip()
        codigo = partes[1].strip()
    else:
        tipo = trecho_principal
        codigo = trecho_principal

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

    return [parse_no_string(tok) for tok in tokens if tok]


def eh_dispositivo_protecao(tipo: str) -> bool:
    """Verifica se o tipo corresponde a Chave Fusível, Religador ou Saída do Alimentador."""
    t = tipo.strip().lower()
    return any(p in t for p in TIPOS_PROTECAO_VALIDOS)


def localizar_protecao_a_montante(
    caminho_str: str,
    ponto_alvo: str,
    clientes_a_override: Optional[int] = None,
    clientes_b_override: Optional[int] = None,
    kva_override: Optional[float] = None,
) -> ResultadoProtecao:
    """
    Localiza a primeira proteção a montante do ponto alvo no caminho elétrico.

    Varre da direita para a esquerda (a montante do alvo).
    O primeiro nó que corresponder a Chave Fusível, Religador ou Saída do Alimentador
    é eleito como dispositivo de proteção.
    """
    ponto_alvo_limpo = ponto_alvo.strip().upper()
    nos = separar_caminho_em_nos(caminho_str)

    if not nos:
        return ResultadoProtecao(
            sucesso=False,
            ponto_alvo=ponto_alvo,
            subestacao="",
            alimentador="",
            protecao_tipo="",
            protecao_codigo="",
            protecao_rotulo="",
            mensagem="Caminho elétrico vazio ou inválido.",
        )

    # Identifica a Saída do Alimentador (geralmente o nó 0 ou que contém 'Saida do Alimentador')
    subestacao = ""
    alimentador = ""
    for no in nos:
        if "saida do alimentador" in no.tipo.lower() or "saída do alimentador" in no.tipo.lower():
            se, alim = extrair_se_e_alimentador(no.codigo)
            subestacao = se
            alimentador = alim
            break

    # Se não achou nó explícito de saída, tenta extrair do primeiro nó
    if not subestacao and nos:
        if any(char.isdigit() for char in nos[0].codigo):
            subestacao, alimentador = extrair_se_e_alimentador(nos[0].codigo)

    # Localiza o índice do nó alvo
    idx_alvo = -1
    for i in range(len(nos) - 1, -1, -1):
        if ponto_alvo_limpo in nos[i].codigo.upper() or ponto_alvo_limpo in nos[i].texto_original.upper():
            idx_alvo = i
            break

    # Se não achou pelo código exato, busca se o último nó é o próprio alvo
    if idx_alvo == -1:
        idx_alvo = len(nos) - 1

    # Varre a montante (da posição anterior ao alvo até o início)
    no_protecao: Optional[DispositivoNo] = None
    for i in range(idx_alvo - 1, -1, -1):
        candidato = nos[i]
        if eh_dispositivo_protecao(candidato.tipo):
            no_protecao = candidato
            break

    # Se não encontrou nenhuma proteção intermediária, a proteção é a própria Saída do Alimentador
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

    rotulo = f"{no_protecao.tipo} - {no_protecao.codigo}" if no_protecao.tipo and no_protecao.codigo else no_protecao.texto_original

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
