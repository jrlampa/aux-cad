# -*- coding: utf-8 -*-
"""
Módulo de Integração com o GOMNET (Seção 19).
Responsável pela autenticação, consulta de SOBs, inspeção de modais de anexos (Upload.aspx)
e download atômico e validado de todos os arquivos associados à SOB para CROQUI\\ANEXOS.

Regras de negócio:
- Não tratar o ícone/imagem anexarArquivo.gif como anexo (apenas referência de interface).
- Autenticação com manutenção de sessão HTTP (ASP.NET_SessionId).
- Download atômico utilizando extensão temporária .download antes da renomeação final.
- Validação estrita de cada arquivo (tamanho > 0, ausência de páginas de erro HTML).
- Zero exposição de senhas em logs ou exceções.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup
from dotenv import dotenv_values
import requests

try:
    from sob.sob_core import sanitizar_mensagem
except ModuleNotFoundError:
    from sob_core import sanitizar_mensagem

logger = logging.getLogger("aux_cad.sob.gomnet")

DEFAULT_GOMNET_URL = "http://gomnet-rj.enelint.global/login.aspx"
DEFAULT_TIMEOUT = 25


class GomnetError(Exception):
    """Exceção base para erros do conector GOMNET."""
    pass


class GomnetAuthError(GomnetError):
    """Falha de autenticação no GOMNET."""
    pass


class GomnetNotFoundError(GomnetError):
    """SOB não encontrada no GOMNET."""
    pass


class GomnetDownloadError(GomnetError):
    """Falha ao baixar anexo do GOMNET."""
    pass


@dataclass
class GomnetAnexo:
    """Metadados de um anexo registrado no GOMNET para uma SOB."""
    id_arquivo: str
    nome_arquivo: str
    tipo: str
    categoria: str
    descricao: str
    data_gravacao: str
    usuario: str
    url_download: str
    origem: str = "GOMNET"

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id_arquivo,
            "nome": self.nome_arquivo,
            "tipo": self.tipo,
            "categoria": self.categoria,
            "descricao": self.descricao,
            "data": self.data_gravacao,
            "usuario": self.usuario,
            "origem": self.origem,
            "url_download": self.url_download,
        }


def carregar_credenciais_gomnet(env_path: Optional[Union[str, Path]] = None) -> Tuple[str, str, str]:
    """
    Carrega com segurança as credenciais do GOMNET a partir do .env sem expor valores nos logs.
    Retorna (usuario, senha, url_login).
    """
    caminho_env = Path(env_path) if env_path else Path(__file__).resolve().parent.parent / ".env"
    if not caminho_env.is_file():
        raise GomnetAuthError(f"Arquivo de ambiente não encontrado: {caminho_env}")

    try:
        valores = dotenv_values(caminho_env)
    except Exception as e:
        raise GomnetAuthError(f"Erro ao ler arquivo .env: {e}")

    usuario = (valores.get("GOMNET_LOGIN") or valores.get("DISTRIBUIDORA_LOGIN") or "").strip()
    senha = (valores.get("GOMNET_SENHA") or valores.get("DISTRIBUIDORA_SENHA") or "").strip()
    url_login = (valores.get("GOMNET_URL") or DEFAULT_GOMNET_URL).strip()

    if not usuario or not senha:
        raise GomnetAuthError("Credenciais do GOMNET (GOMNET_LOGIN/GOMNET_SENHA) não preenchidas no .env.")

    return usuario, senha, url_login


class GomnetClient:
    """Cliente HTTP desacoplado e seguro para comunicação com o GOMNET."""

    def __init__(
        self,
        usuario: Optional[str] = None,
        senha: Optional[str] = None,
        login_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.timeout = timeout
        if not usuario or not senha:
            u, s, url = carregar_credenciais_gomnet()
            self.usuario = usuario or u
            self.senha = senha or s
            self.login_url = login_url or url
        else:
            self.usuario = usuario
            self.senha = senha
            self.login_url = login_url or DEFAULT_GOMNET_URL

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.autenticado = False

    def autenticar(self) -> bool:
        """Realiza autenticação segura via POST em login.aspx preservando ASP.NET_SessionId."""
        try:
            r_get = self.session.get(self.login_url, timeout=self.timeout)
            if r_get.status_code != 200:
                raise GomnetAuthError(f"Falha de acesso à tela de login do GOMNET. HTTP {r_get.status_code}")

            soup = BeautifulSoup(r_get.text, "html.parser")
            vs_input = soup.find("input", {"id": "__VIEWSTATE"})
            vsg_input = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})

            if not vs_input or not vs_input.get("value"):
                raise GomnetAuthError("Campos de estado ASP.NET (__VIEWSTATE) ausentes no formulário de login.")

            viewstate = vs_input.get("value", "")
            viewstategenerator = vsg_input.get("value", "") if vsg_input else ""

            payload = {
                "__VIEWSTATE": viewstate,
                "__VIEWSTATEGENERATOR": viewstategenerator,
                "txtBoxLogin": self.usuario,
                "txtBoxSenha": self.senha,
                "ImageButton_Login.x": "15",
                "ImageButton_Login.y": "15",
            }

            r_post = self.session.post(self.login_url, data=payload, timeout=self.timeout)
            if r_post.status_code != 200:
                raise GomnetAuthError(f"Resposta inesperada do login GOMNET. HTTP {r_post.status_code}")

            if "txtBoxLogin" in r_post.text and "txtBoxSenha" in r_post.text and ("Inválido" in r_post.text or "Incorret" in r_post.text or "Senha" in r_post.text):
                raise GomnetAuthError("Falha de autenticação no GOMNET: usuário ou senha incorretos.")

            self.autenticado = True
            logger.info("Autenticação no GOMNET realizada com sucesso.")
            return True

        except requests.RequestException as e:
            raise GomnetAuthError(f"Erro de comunicação com o GOMNET: {e}")

    def localizar_sob_e_listar_anexos(self, sob_id: str) -> List[GomnetAnexo]:
        """
        Acessa a interface modal de anexos (Upload.aspx) para a SOB informada
        e retorna todos os anexos legítimos identificados.
        """
        if not self.autenticado:
            self.autenticar()

        sob_limpa = re.sub(r"^SOB_", "", sob_id, flags=re.IGNORECASE).strip()
        base_url = self.login_url.rsplit("/", 1)[0]
        upload_url = f"{base_url}/Upload.aspx?numtrab=&numsob={sob_limpa}&Slns_Codigo={sob_limpa}"

        try:
            resp = self.session.get(upload_url, timeout=self.timeout)
            if resp.status_code != 200:
                raise GomnetError(f"Falha ao consultar anexos da SOB {sob_limpa} no GOMNET. HTTP {resp.status_code}")

            html = resp.text
            if "Não existem dados para serem exibidos" in html:
                logger.info(f"A SOB {sob_limpa} foi localizada no GOMNET mas não possui anexos cadastrados.")
                return []

            soup = BeautifulSoup(html, "html.parser")
            grid = soup.find("table", {"id": re.compile(r"gridviewUploads", re.IGNORECASE)})
            if not grid:
                logger.info(f"Nenhuma tabela de anexos encontrada para a SOB {sob_limpa}.")
                return []

            anexos: List[GomnetAnexo] = []
            for tr in grid.find_all("tr"):
                link = tr.find("a")
                hidden_id = tr.find("input", {"type": "hidden", "name": lambda x: x and "HiddenField3" in x})
                if not link or not hidden_id:
                    continue

                nome_arquivo = link.get_text(strip=True)
                id_arquivo = hidden_id.get("value", "").strip()
                if not nome_arquivo or not id_arquivo:
                    continue

                # Evita salvar referências visuais de botões ou ícones de interface
                if "anexararquivo.gif" in nome_arquivo.lower() or nome_arquivo.lower().endswith(".gif"):
                    continue

                cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                tipo = cols[0] if len(cols) > 0 else ""
                categoria = cols[1] if len(cols) > 1 else ""
                descricao = cols[3] if len(cols) > 3 else ""
                data_gravacao = cols[4] if len(cols) > 4 else ""
                usuario = cols[5] if len(cols) > 5 else ""

                download_url = f"{base_url}/DownloadArquivo.aspx?id={id_arquivo}&nomeArquivo={quote(nome_arquivo)}&sob={sob_limpa}"

                anexo = GomnetAnexo(
                    id_arquivo=id_arquivo,
                    nome_arquivo=nome_arquivo,
                    tipo=tipo,
                    categoria=categoria,
                    descricao=descricao,
                    data_gravacao=data_gravacao,
                    usuario=usuario,
                    url_download=download_url,
                )
                anexos.append(anexo)

            logger.info(f"Localizados {len(anexos)} anexo(s) no GOMNET para a SOB {sob_limpa}.")
            return anexos

        except requests.RequestException as e:
            raise GomnetError(f"Erro ao consultar modal de anexos no GOMNET: {e}")

    def baixar_anexo_atomico(self, anexo: GomnetAnexo, destino_final: Union[str, Path]) -> Path:
        """
        Baixa o anexo utilizando escrita temporária (.download), valida a integridade
        (tamanho > 0, ausência de HTML de erro) e renomeia atomicamente para o destino final.
        """
        if not self.autenticado:
            self.autenticar()

        destino = Path(destino_final).resolve()
        destino.parent.mkdir(parents=True, exist_ok=True)
        arquivo_temp = destino.with_name(f"{destino.name}.download")

        try:
            with self.session.get(anexo.url_download, stream=True, timeout=self.timeout) as r:
                if r.status_code != 200:
                    raise GomnetDownloadError(f"Servidor retornou HTTP {r.status_code} ao baixar {anexo.nome_arquivo}.")

                content_type = (r.headers.get("Content-Type") or "").lower()
                with open(arquivo_temp, "wb") as f_out:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f_out.write(chunk)

            # Validações de integridade física
            if not arquivo_temp.exists() or arquivo_temp.stat().st_size == 0:
                if arquivo_temp.exists():
                    arquivo_temp.unlink()
                raise GomnetDownloadError(f"Arquivo baixado vazio (0 bytes): {anexo.nome_arquivo}")

            # Rejeita respostas HTML de erro salvas como arquivo binário
            tamanho = arquivo_temp.stat().st_size
            eh_html_erro = False
            with open(arquivo_temp, "rb") as f_check:
                inicio = f_check.read(256)
                if inicio.strip().startswith(b"<!DOCTYPE") or inicio.strip().startswith(b"<html") or b"<title>Error" in inicio:
                    eh_html_erro = True

            if eh_html_erro:
                if arquivo_temp.exists():
                    arquivo_temp.unlink()
                raise GomnetDownloadError(f"O servidor retornou uma página HTML de erro em vez do anexo {anexo.nome_arquivo}.")

            # Renomeação atômica
            arquivo_temp.replace(destino)
            logger.info(f"Anexo GOMNET baixado com sucesso: {destino.name} ({tamanho} bytes)")
            return destino

        except Exception as e:
            if arquivo_temp.exists():
                try:
                    arquivo_temp.unlink()
                except Exception:
                    pass
            raise GomnetDownloadError(f"Falha ao baixar anexo {anexo.nome_arquivo}: {e}")

    def fechar(self):
        """Fecha a sessão HTTP."""
        try:
            self.session.close()
        except Exception:
            pass
