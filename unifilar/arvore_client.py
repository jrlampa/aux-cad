# -*- coding: utf-8 -*-
"""
Módulo de Cliente de Consulta da Árvore de Dispositivos.
Responsabilidade única: Orquestração de chamadas web à intranet da concessionária,
autenticação com credenciais corporativas e fallback resiliente para banco local.
"""

import os
from pathlib import Path
import re
from typing import Optional

from dotenv import load_dotenv
import requests

from arvore_database import ArvoreDatabase, get_base_dir
from arvore_parser import (
    ResultadoProtecao,
    localizar_protecao_a_montante,
)

# Carrega variáveis do arquivo .env
env_file = get_base_dir() / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)


def get_url_arvore() -> str:
    return os.getenv(
        "URL_ARVORE_DISPOSITIVOS",
        "http://sgt.rio.e-corpnet.org/caminhoeletrico/Arvore.aspx",
    )


def get_login() -> str:
    return os.getenv("GOMNET_LOGIN", "")


def get_senha() -> str:
    return os.getenv("GOMNET_SENHA", "")


class ArvoreClient:
    """Cliente para consulta da árvore via web ou fallback de banco local."""

    def __init__(self, database: Optional[ArvoreDatabase] = None):
        self.db = database or ArvoreDatabase()
        self.url = get_url_arvore()
        self.login = get_login()
        self.senha = get_senha()

    def extrair_resumo_de_html(self, html_content: str, ponto_alvo: str) -> Optional[str]:
        """
        Extrai o caminho elétrico em formato resumo do HTML retornado pelo sistema.
        Exemplo: 'Saida do Alimentador - RBN02 > ... > Centro de Distribuic?o - SG40995'
        """
        if not html_content:
            return None

        import html
        conteudo = html.unescape(html_content)

        # Procura linhas com o separador ' > '
        linhas = conteudo.splitlines()
        for linha in linhas:
            if " > " in linha and ("Saida do Alimentador" in linha or "Saída do Alimentador" in linha or "Chave" in linha):
                # Limpa tags HTML
                limpa = re.sub(r"<[^>]+>", "", linha).strip()
                if ponto_alvo.upper() in limpa.upper():
                    return limpa

        # Procura por regex genérico de breadcrumb
        padrao = r"((?:Saida do Alimentador|Saída do Alimentador)[^<]+>[^<]+)"
        match = re.search(padrao, conteudo, re.IGNORECASE)
        if match:
            return re.sub(r"<[^>]+>", "", match.group(1)).strip()

        return None

    def consultar_web(self, ponto: str, timeout: int = 4) -> Optional[ResultadoProtecao]:
        """
        Tenta realizar consulta HTTP à intranet ASP.NET.
        Retorna ResultadoProtecao caso obtenha resposta com sucesso, ou None se falhar.
        """
        try:
            # Tenta autenticação NTLM caso disponível
            from requests_ntlm import HttpNtlmAuth

            auth = HttpNtlmAuth(self.login, self.senha) if self.login and self.senha else None
            session = requests.Session()
            if auth:
                session.auth = auth

            # 1. Faz GET para capturar ViewState
            r_get = session.get(self.url, timeout=timeout)
            if r_get.status_code != 200:
                return None

            # 2. Faz POST com o ponto elétrico
            vs_match = re.search(r'id="__VIEWSTATE"\s+value="([^"]+)"', r_get.text)
            ev_match = re.search(r'id="__EVENTVALIDATION"\s+value="([^"]+)"', r_get.text)

            vs = vs_match.group(1) if vs_match else ""
            ev = ev_match.group(1) if ev_match else ""

            payload = {
                "__VIEWSTATE": vs,
                "__EVENTVALIDATION": ev,
                "txtPontoEletrico": ponto,
                "btnBuscar": "Buscar",
            }
            # Mapeia inputs extras
            for m in re.finditer(r'<input[^>]+name="([^"]+)"(?:\s+value="([^"]*)")?', r_get.text):
                name = m.group(1)
                val = m.group(2) or ""
                if name not in payload and not name.startswith("btn"):
                    payload[name] = val

            r_post = session.post(self.url, data=payload, timeout=timeout)
            if r_post.status_code == 200:
                caminho = self.extrair_resumo_de_html(r_post.text, ponto)
                if caminho:
                    return localizar_protecao_a_montante(caminho, ponto)

        except Exception:
            # Em caso de timeout ou indisponibilidade da intranet, prossegue para fallback
            pass

        return None

    def consultar(self, ponto: str) -> ResultadoProtecao:
        """
        Método principal unificado:
        1. Tenta consulta web em tempo real se a rede permitir.
        2. Faz fallback transparente para o banco SQLite indexado da planilha oficial.
        """
        ponto_limpo = ponto.strip().upper()

        # Tentativa Web
        res_web = self.consultar_web(ponto_limpo)
        if res_web and res_web.sucesso:
            return res_web

        # Fallback Local (SQLite ultrarrápido)
        res_local = self.db.consultar_protecao_dispositivo(ponto_limpo)
        if res_local and res_local.sucesso:
            return res_local

        return ResultadoProtecao(
            sucesso=False,
            ponto_alvo=ponto_limpo,
            subestacao="",
            alimentador="",
            protecao_tipo="",
            protecao_codigo="",
            protecao_rotulo="",
            mensagem=f"Ponto elétrico '{ponto_limpo}' não localizado nem online nem na base local.",
        )

    def consultar_resumo_manual(self, texto_resumo: str, ponto: str) -> ResultadoProtecao:
        """Processa um texto de resumo colado manualmente pelo usuário."""
        return localizar_protecao_a_montante(texto_resumo, ponto)
