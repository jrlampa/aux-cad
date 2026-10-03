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
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import quote, urljoin, urlsplit

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
STATUS_CONSULTA_PATH = "EstudoTecnico.aspx"
STATUS_GRID_ID = re.compile(r"Gridview_GomNet1", re.IGNORECASE)
STATUS_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "DNT": "1",
    "Sec-GPC": "1",
    "Upgrade-Insecure-Requests": "1",
}


def _normalizar_chave_sob(valor: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (valor or "").upper().replace("SOB_", ""))


def _extrair_status_sob_html(html: str, sob_id: str) -> Optional[str]:
    """Localiza o status visível na linha da SOB no grid principal do GOMNET."""
    soup = BeautifulSoup(html or "", "html.parser")
    sob_chave = _normalizar_chave_sob(sob_id)

    for grid in soup.find_all("table", id=STATUS_GRID_ID):
        rows = grid.find_all("tr")
        if not rows:
            continue

        cabecalhos = [
            re.sub(r"[^a-z0-9]", "", cell.get_text(" ", strip=True).casefold())
            for cell in rows[0].find_all(["th", "td"], recursive=False)
        ]
        idx_estado = next(
            (i for i, texto in enumerate(cabecalhos) if texto in {"estado", "status"}),
            None,
        )

        for row in rows[1:]:
            celulas = row.find_all(["th", "td"], recursive=False)
            sob_na_linha = any(
                _normalizar_chave_sob(cell.get_text(" ", strip=True)) == sob_chave
                for cell in celulas
            )
            if not sob_na_linha:
                continue

            if idx_estado is not None and idx_estado < len(celulas):
                return celulas[idx_estado].get_text(" ", strip=True)

            hidden_estado = row.find(
                "input",
                {"type": "hidden", "id": re.compile(r"HiddenField_EstadoSolic", re.IGNORECASE)},
            )
            if hidden_estado:
                celula_estado = hidden_estado.find_parent("td")
                if celula_estado:
                    return celula_estado.get_text(" ", strip=True)
            return ""

    return None


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
        self._pagina_pos_login = ""
        self._url_pos_login = self.login_url

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

            resposta_login = BeautifulSoup(r_post.text, "html.parser")
            texto_login = resposta_login.get_text(" ", strip=True).casefold()
            mensagens_credencial_invalida = (
                "usuário ou senha incorretos",
                "usuario ou senha incorretos",
                "senha incorreta",
                "senha inválida",
                "senha invalida",
                "usuário inválido",
                "usuario invalido",
            )
            credencial_invalida = any(msg in texto_login for msg in mensagens_credencial_invalida)
            formulario_login_presente = bool(
                resposta_login.find(id="txtBoxLogin") and resposta_login.find(id="txtBoxSenha")
            )
            titulo_login = resposta_login.title.get_text(" ", strip=True).casefold() if resposta_login.title else ""
            if credencial_invalida:
                raise GomnetAuthError("Falha de autenticação no GOMNET: usuário ou senha incorretos.")
            if formulario_login_presente and "gom.net - login" in titulo_login:
                raise GomnetAuthError(
                    "O GOMNET manteve a tela de login; verifique usuário, senha e perfil de acesso."
                )

            self.autenticado = True
            self._pagina_pos_login = r_post.text
            self._url_pos_login = r_post.url
            logger.info("Autenticação no GOMNET realizada com sucesso.")
            return True

        except requests.RequestException as e:
            raise GomnetAuthError(f"Erro de comunicação com o GOMNET: {e}")

    def obter_status_sob(self, sob_id: str) -> Optional[str]:
        """Consulta EstudoTecnico.aspx e lê a linha da SOB no grid principal."""
        if not self.autenticado:
            self.autenticar()

        status = _extrair_status_sob_html(self._pagina_pos_login, sob_id)
        if status is not None:
            return status
        if BeautifulSoup(self._pagina_pos_login, "html.parser").find("table", id=STATUS_GRID_ID):
            return None

        base_url = self.login_url.rsplit("/", 1)[0] + "/"
        home_url = urljoin(base_url, "PaginaPrincipal.aspx")
        consulta_url = urljoin(base_url, STATUS_CONSULTA_PATH)
        try:
            home = self.session.get(
                home_url,
                headers={**STATUS_BROWSER_HEADERS, "Referer": self._url_pos_login},
                timeout=self.timeout,
            )
            if home.status_code != 200:
                raise GomnetError(
                    f"Falha ao carregar o menu principal do GOMNET. HTTP {home.status_code}"
                )

            home_soup = BeautifulSoup(home.text, "html.parser")
            if home_soup.find(id="txtBoxLogin") and home_soup.find(id="txtBoxSenha"):
                self.autenticado = False
                raise GomnetAuthError("A sessão do GOMNET expirou antes da consulta de status.")

            pagina = self.session.get(
                consulta_url,
                headers={**STATUS_BROWSER_HEADERS, "Referer": home_url},
                timeout=self.timeout,
            )
            if pagina.status_code != 200:
                raise GomnetError(
                    f"Falha ao abrir a consulta de status do GOMNET. HTTP {pagina.status_code}"
                )

            soup = BeautifulSoup(pagina.text, "html.parser")
            if soup.find(id="txtBoxLogin") and soup.find(id="txtBoxSenha"):
                self.autenticado = False
                raise GomnetAuthError("A sessão do GOMNET expirou durante a consulta de status.")

            form = soup.find("form")
            if not form:
                raise GomnetError("A tela de status do GOMNET não contém o formulário ASP.NET esperado.")

            payload: Dict[str, str] = {}
            for campo in form.find_all("input"):
                nome = campo.get("name")
                tipo = (campo.get("type") or "").lower()
                if not nome:
                    continue
                if tipo in {"hidden", "text", "password"}:
                    payload[nome] = campo.get("value", "")
                elif tipo in {"checkbox", "radio"} and campo.has_attr("checked"):
                    payload[nome] = campo.get("value", "on")

            for campo in form.find_all("select"):
                nome = campo.get("name")
                selecionado = campo.find("option", selected=True) or campo.find("option")
                if nome and selecionado:
                    payload[nome] = selecionado.get("value", "")

            for campo in form.find_all("textarea"):
                if campo.get("name"):
                    payload[campo["name"]] = campo.get_text()

            filtro_sob = next(
                (
                    campo
                    for campo in form.find_all("input")
                    if re.search(r"(?:txtBox|TextBox)_?NumSOB", campo.get("id", "") + campo.get("name", ""), re.I)
                ),
                None,
            )
            botao_busca = next(
                (
                    campo
                    for campo in form.find_all("input", type="image")
                    if "ImageButton_Enviar" in (campo.get("id", "") + campo.get("name", ""))
                ),
                None,
            )
            if not filtro_sob or not filtro_sob.get("name") or not botao_busca or not botao_busca.get("name"):
                raise GomnetError(
                    "A tela EstudoTecnico.aspx mudou: filtro da SOB ou botão de consulta não encontrado."
                )

            sob_limpa = re.sub(r"^SOB_", "", sob_id, flags=re.IGNORECASE).strip()
            payload[filtro_sob["name"]] = sob_limpa
            payload["__EVENTTARGET"] = ""
            payload["__EVENTARGUMENT"] = ""
            payload[f"{botao_busca['name']}.x"] = "1"
            payload[f"{botao_busca['name']}.y"] = "10"

            resposta = self.session.post(
                consulta_url,
                data=payload,
                headers={
                    **STATUS_BROWSER_HEADERS,
                    "Origin": f"{urlsplit(consulta_url).scheme}://{urlsplit(consulta_url).netloc}",
                    "Referer": consulta_url,
                },
                timeout=self.timeout,
            )
            if resposta.status_code != 200:
                raise GomnetError(
                    f"Falha ao consultar status da SOB {sob_limpa} no GOMNET. HTTP {resposta.status_code}"
                )

            resultado = BeautifulSoup(resposta.text, "html.parser")
            if resultado.find(id="txtBoxLogin") and resultado.find(id="txtBoxSenha"):
                self.autenticado = False
                raise GomnetAuthError("A sessão do GOMNET expirou durante a consulta de status.")

            self._pagina_status = resposta.text
            return _extrair_status_sob_html(resposta.text, sob_limpa)
        except requests.RequestException as e:
            raise GomnetError(f"Erro de comunicação ao consultar status da SOB no GOMNET: {e}")

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
            html_lower = html.casefold()
            if any(
                marker in html_lower
                for marker in (
                    "sob não encontrada",
                    "sob nao encontrada",
                    "sob inexistente",
                    "número da sob não existe",
                    "numero da sob nao existe",
                )
            ):
                raise GomnetNotFoundError(f"SOB {sob_limpa} não encontrada no GOMNET.")

            if "Não existem dados para serem exibidos" in html:
                logger.info(f"A SOB {sob_limpa} foi localizada no GOMNET mas não possui anexos cadastrados.")
                return []

            soup = BeautifulSoup(html, "html.parser")
            grid = soup.find("table", {"id": re.compile(r"gridviewUploads", re.IGNORECASE)})
            if not grid:
                raise GomnetError(
                    f"O GOMNET não confirmou a consulta da SOB {sob_limpa}; "
                    "a resposta não contém a tabela de anexos esperada."
                )

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


def baixar_anexos_gomnet_fase_b(
    anexos_gomnet: List[GomnetAnexo],
    gom_client: GomnetClient,
    croqui_dir: Path,
    rollback_ctx: Optional[Any] = None,
    callback_progresso: Optional[Any] = None,
    checar_cancelamento_fn: Optional[Any] = None,
    logger: Optional[Any] = None,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Realiza o download idempotente e atômico dos anexos identificados no GOMNET para CROQUI\\ANEXOS.
    """
    from sob_idempotencia import verificar_arquivo_download_idempotente
    from sob_core import SobIntegrityError

    anexos_dir = croqui_dir / "ANEXOS"
    anexos_dir_preexistia = anexos_dir.exists()
    anexos_dir.mkdir(parents=True, exist_ok=True)
    if not anexos_dir_preexistia and rollback_ctx:
        rollback_ctx.registrar_criacao("ANEXOS_DIR", anexos_dir, tipo="dir")

    created_files: List[str] = []
    attachments_info: List[Dict[str, Any]] = []

    for idx, anexo in enumerate(anexos_gomnet):
        if checar_cancelamento_fn:
            checar_cancelamento_fn()

        dest_anexo = anexos_dir / anexo.nome_arquivo
        st_idemp = verificar_arquivo_download_idempotente(dest_anexo)
        if st_idemp == "IDENTICO":
            if logger:
                logger.info(f"[OK] Anexo GOMNET já existente e compatível: {anexo.nome_arquivo}")
        elif st_idemp == "DIVERGENTE":
            raise SobIntegrityError(
                f"[BLOQUEADO] Anexo GOMNET existente com conteúdo divergente: {anexo.nome_arquivo}"
            )
        else:
            gom_client.baixar_anexo_atomico(anexo, dest_anexo)
            if rollback_ctx:
                rollback_ctx.registrar_gomnet_arquivo(dest_anexo)
            created_files.append(str(dest_anexo))

        attachments_info.append({
            "nome": anexo.nome_arquivo,
            "origem": "GOMNET",
            "referencia": anexo.id_arquivo,
            "destino": str(dest_anexo),
        })

        if callback_progresso and hasattr(callback_progresso, "notificar"):
            perc_g = ((idx + 1) / len(anexos_gomnet)) * 100
            callback_progresso.notificar(
                etapa="DOWNLOAD_GOMNET",
                descricao=f"Anexo GOMNET: {anexo.nome_arquivo}",
                etapa_num=10,
                percentual=perc_g,
            )

    return created_files, attachments_info
