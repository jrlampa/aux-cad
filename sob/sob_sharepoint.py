# -*- coding: utf-8 -*-
"""
Módulo de Integração com SharePoint (sob_sharepoint.py).
Responsabilidade única: Autenticação segura via Microsoft Online / SharePoint,
localização da SOB na biblioteca documental e download íntegro para a pasta CROQUI.
"""

import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:
    dotenv_values = None
    load_dotenv = None


# URL Padrão do SharePoint da HBT Enel Rio
SHAREPOINT_URL_PADRAO = (
    "https://hbtengenharia1.sharepoint.com/sites/HBT-EnelRJ-Sul/"
    "Documentos%20Compartilhados/Forms/AllItems.aspx"
)


class SobSharepointError(Exception):
    """Classe base para exceções do SharePoint."""
    pass


class SobEnvNotFoundError(SobSharepointError):
    """Arquivo .env não localizado."""
    pass


class SobCredentialError(SobSharepointError):
    """Credencial SHAREPOINT_ID ou SHAREPOINT_SENHA ausente."""
    pass


class SobAuthenticationError(SobSharepointError):
    """Falha na autenticação do SharePoint (Credencial inválida ou bloqueada)."""
    pass


class SobSharepointUnavailableError(SobSharepointError):
    """SharePoint ou serviço de login indisponível."""
    pass


class SobNotFoundError(SobSharepointError):
    """SOB informada não foi localizada no SharePoint."""
    pass


class SobConflictError(SobSharepointError):
    """Múltiplas pastas encontradas para a mesma SOB sem critério de desempate."""
    pass


class SobDownloadError(SobSharepointError):
    """Erro durante a transferência de arquivos do SharePoint."""
    pass


class SobDownloadIncompleteError(SobSharepointError):
    """Download incompleto ou arquivos corrompidos/parciais."""
    pass


def obter_caminho_env_padrao() -> Path:
    """Retorna o caminho padrão do arquivo .env na raiz do projeto."""
    return Path(__file__).resolve().parent.parent / ".env"


def obter_credenciais_sharepoint(
    caminho_env: Optional[Union[str, Path]] = None,
) -> Tuple[str, str]:
    """
    Carrega e valida as credenciais do SharePoint a partir do arquivo .env.
    Retorna uma tupla (SHAREPOINT_ID, SHAREPOINT_SENHA).
    
    Regras de Segurança:
    - O .env é a única fonte das credenciais.
    - Nunca utiliza fallback hardcoded.
    """
    env_path = Path(caminho_env) if caminho_env else obter_caminho_env_padrao()

    if not env_path.is_file():
        raise SobEnvNotFoundError(
            f"Arquivo de configuração .env não encontrado em: {env_path}\n"
            "Crie o arquivo .env a partir do .env.example com suas credenciais."
        )

    login = ""
    senha = ""

    # Lê estritamente as chaves do arquivo indicado para evitar poluição de os.environ
    if dotenv_values:
        vals = dotenv_values(dotenv_path=env_path)
        login = (vals.get("SHAREPOINT_ID") or "").strip()
        senha = (vals.get("SHAREPOINT_SENHA") or "").strip()

    if not login or not senha:
        # Parser robusto linha a linha
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                linha = line.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "SHAREPOINT_ID" and not login:
                        login = v
                    elif k == "SHAREPOINT_SENHA" and not senha:
                        senha = v

    if not login or not senha:
        raise SobCredentialError(
            "[FALHA] Credenciais do SharePoint não configuradas."
        )

    return login, senha


def sanitizar_mensagem(texto: str, segredos: Optional[List[str]] = None) -> str:
    """
    Remove segredos e credenciais de mensagens ou logs.
    Garante que senhas nunca apareçam em logs ou telas.
    """
    if not texto:
        return ""

    resultado = texto
    if segredos:
        for s in segredos:
            if s and len(s) >= 3:
                resultado = resultado.replace(s, "******")

    # Sanitização extra de padrões comuns
    resultado = re.sub(r'(password|senha|passwd|pwd)\s*=\s*([^\s&]+)', r'\1=******', resultado, flags=re.IGNORECASE)
    return resultado


class SharePointClient:
    """
    Cliente para autenticação, busca e download de arquivos da SOB no SharePoint.
    Utiliza navegador automatizado Edge/Chrome com Selenium e download nativo.
    """

    def __init__(
        self,
        login: str,
        senha: str,
        url: str = SHAREPOINT_URL_PADRAO,
        headless: bool = True,
        timeout: int = 30,
    ):
        self.login = login
        self.senha = senha
        self.url = url
        self.headless = headless
        self.timeout = timeout
        self.driver = None
        self._autenticado = False

    def _criar_driver(self, pasta_download: Optional[Path] = None):
        """Inicializa o WebDriver do Edge (ou fallback Chrome) configurado."""
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options as EdgeOptions

        opts = EdgeOptions()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")

        # Preferências de download
        if pasta_download:
            download_dir = str(pasta_download.resolve())
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            opts.add_experimental_option("prefs", prefs)

        try:
            self.driver = webdriver.Edge(options=opts)
            self.driver.set_page_load_timeout(self.timeout)
        except Exception as e:
            # Tenta fallback para Chrome
            try:
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                copts = ChromeOptions()
                if self.headless:
                    copts.add_argument("--headless=new")
                copts.add_argument("--disable-gpu")
                copts.add_argument("--no-sandbox")
                if pasta_download:
                    copts.add_experimental_option("prefs", {
                        "download.default_directory": str(pasta_download.resolve()),
                        "download.prompt_for_download": False,
                    })
                self.driver = webdriver.Chrome(options=copts)
                self.driver.set_page_load_timeout(self.timeout)
            except Exception as e2:
                raise SobSharepointUnavailableError(
                    f"Não foi possível inicializar o navegador automatizado: {e}; {e2}"
                )

    @staticmethod
    def _verificar_erro_login(body_text: str):
        """Verifica mensagens de erro conhecidas na página de login da Microsoft."""
        if any(msg in body_text for msg in [
            "Sua conta ou senha está incorreta",
            "Sua conta ou senha est",
            "Insira uma senha válida",
            "passwordError",
            "AADSTS50126",
        ]):
            raise SobAuthenticationError(
                "[FALHA] Não foi possível autenticar no SharePoint."
            )

    def autenticar(self):
        """
        Realiza a autenticação no Microsoft Online para acesso ao SharePoint.
        Lança SobAuthenticationError caso as credenciais sejam inválidas.
        """
        if not self.driver:
            self._criar_driver()

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            self.driver.get(self.url)
            time.sleep(2)

            curr_url = self.driver.current_url
            if "login.microsoftonline.com" in curr_url or "login.live.com" in curr_url:
                # 1. Digita o e-mail / ID
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "loginfmt"))
                )
                email_input.clear()
                email_input.send_keys(self.login)

                # Clica em Avançar
                btn_next = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "idSIButton9"))
                )
                btn_next.click()
                time.sleep(2)

                # Verifica se houve erro de usuário inexistente
                err_user = self.driver.find_elements(By.ID, "usernameError")
                if err_user and err_user[0].is_displayed():
                    raise SobAuthenticationError(
                        "[FALHA] Não foi possível autenticar no SharePoint."
                    )

                # 2. Digita a senha
                pwd_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "passwd"))
                )
                pwd_input.clear()
                pwd_input.send_keys(self.senha)

                # Clica em Entrar
                btn_sign = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "idSIButton9"))
                )
                btn_sign.click()
                time.sleep(3)

                # 3. Verifica resposta após submissão de senha
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                body_text = body_elem.text if body_elem else ""

                self._verificar_erro_login(body_text)

                if self.driver.find_elements(By.ID, "passwordError"):
                    raise SobAuthenticationError(
                        "[FALHA] Não foi possível autenticar no SharePoint."
                    )

                # Trata tela de "Permanecer conectado?" (KMSI)
                kmsi_btns = self.driver.find_elements(By.ID, "idSIButton9")
                if kmsi_btns:
                    try:
                        kmsi_btns[0].click()
                        time.sleep(3)
                    except Exception:
                        pass

            # Verifica se chegamos ao SharePoint
            time.sleep(2)
            curr_url = self.driver.current_url
            if "sharepoint.com" in curr_url:
                self._autenticado = True
            elif "login.microsoftonline.com" in curr_url:
                # Permaneceu na página de login (ex: exigência de MFA ou erro não capturado)
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                self._verificar_erro_login(body_elem.text if body_elem else "")

                raise SobAuthenticationError(
                    "[FALHA] Não foi possível autenticar no SharePoint."
                )

        except SobAuthenticationError:
            raise
        except Exception as e:
            msg_sanitizada = sanitizar_mensagem(str(e), [self.login, self.senha])
            raise SobSharepointUnavailableError(
                f"Erro durante a conexão com o SharePoint: {msg_sanitizada}"
            )

    def localizar_pasta_sob(self, sob_codigo: str) -> Dict[str, Any]:
        """
        Localiza a pasta da SOB informada dentro da biblioteca documental do SharePoint.
        
        Regras:
        - Não assumir cegamente um único diretório fixo.
        - Se não encontrar: levanta SobNotFoundError("SOB NÃO ENCONTRADA NO SHAREPOINT.").
        - Se encontrar múltiplos resultados ambíguos: levanta SobConflictError.
        """
        if not self._autenticado:
            self.autenticar()

        from selenium.webdriver.common.by import By

        codigo_limpo = sob_codigo.strip().upper()
        if codigo_limpo.startswith("SOB_"):
            codigo_busca = codigo_limpo[4:]
        else:
            codigo_busca = codigo_limpo

        # Executa busca no SharePoint via DOM / API interna
        try:
            # Navega para a raiz da biblioteca caso necessário
            if "sharepoint.com" not in self.driver.current_url:
                self.driver.get(self.url)
                time.sleep(4)

            # Busca por elementos de pasta ou itens contendo o código da SOB
            # Avalia linhas de arquivo/pasta na visualização do SharePoint
            itens_encontrados = []
            linhas = self.driver.find_elements(By.CSS_SELECTOR, "[role='row'], [data-automationid='DetailsRow']")

            for linha in linhas:
                txt = linha.text
                if codigo_busca in txt.upper():
                    itens_encontrados.append({
                        "texto": txt,
                        "elemento": linha,
                        "sob": codigo_busca,
                    })

            # Se não encontrou na listagem inicial, tenta pesquisar na barra de busca do SharePoint
            if not itens_encontrados:
                caixas_busca = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "input[type='search'], input[aria-label*='Pesquisar'], input[aria-label*='Search']"
                )
                if caixas_busca:
                    caixa = caixas_busca[0]
                    caixa.clear()
                    caixa.send_keys(codigo_busca)
                    caixa.send_keys("\n")
                    time.sleep(5)

                    # Reavalia itens encontrados após a busca
                    linhas = self.driver.find_elements(By.CSS_SELECTOR, "[role='row'], [data-automationid='DetailsRow']")
                    for linha in linhas:
                        txt = linha.text
                        if codigo_busca in txt.upper():
                            itens_encontrados.append({
                                "texto": txt,
                                "elemento": linha,
                                "sob": codigo_busca,
                            })

            # Validação dos resultados (Seção 14.16)
            if len(itens_encontrados) == 0:
                raise SobNotFoundError(
                    f"[FALHA] SOB {sob_codigo} não encontrada no SharePoint."
                )

            # Se encontrar múltiplos resultados, verifica se pertencem estritamente à mesma SOB
            pastas_correspondentes = []
            for item in itens_encontrados:
                # Extrai nome
                nome = item["texto"].split("\n")[0]
                if codigo_busca in nome.upper():
                    pastas_correspondentes.append(item)

            if len(pastas_correspondentes) > 1:
                # Compara se há ambiguidades de diferentes SOBs
                nomes = {p["texto"].split("\n")[0] for p in pastas_correspondentes}
                if len(nomes) > 1:
                    raise SobConflictError(
                        "[FALHA] Foram encontradas múltiplas correspondências para a SOB."
                    )

            return pastas_correspondentes[0]

        except (SobNotFoundError, SobConflictError):
            raise
        except Exception as e:
            msg_sanitizada = sanitizar_mensagem(str(e), [self.login, self.senha])
            raise SobSharepointError(f"Erro ao pesquisar SOB no SharePoint: {msg_sanitizada}")

    def baixar_croqui(self, pasta_info: Dict[str, Any], destino_croqui: Path) -> List[Path]:
        """
        Baixa os arquivos contidos na pasta da SOB localizada para destino_croqui.
        Garante integridade e ausência de arquivos temporários parciais.
        """
        from selenium.webdriver.common.by import By

        destino_path = Path(destino_croqui).resolve()
        destino_path.mkdir(parents=True, exist_ok=True)

        # Habilita download via CDP para o destino configurado
        try:
            self.driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(destino_path)}
            )
        except Exception:
            pass

        elem = pasta_info.get("elemento")
        if elem:
            clicado = False
            try:
                botoes = elem.find_elements(By.TAG_NAME, "button")
                for b in botoes:
                    aria = (b.get_attribute("aria-label") or "").lower()
                    if any(k in aria for k in ["mais", "ações", "actions"]):
                        self.driver.execute_script("arguments[0].click();", b)
                        time.sleep(1.5)
                        menu_items = self.driver.find_elements(By.CSS_SELECTOR, "[role='menuitem'], button")
                        for mi in menu_items:
                            txt = (mi.text or mi.get_attribute("name") or "").strip().lower()
                            if "baixar" in txt or "download" in txt:
                                self.driver.execute_script("arguments[0].click();", mi)
                                clicado = True
                                break
                        if clicado:
                            break
            except Exception:
                pass

            if not clicado:
                try:
                    chks = elem.find_elements(By.CSS_SELECTOR, "[role='checkbox'], [data-automationid='DetailsRowCheck']")
                    if chks:
                        self.driver.execute_script("arguments[0].click();", chks[0])
                    else:
                        elem.click()
                    time.sleep(1)
                    btns_top = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "button[name='Download'], button[name='Baixar'], [data-automationid='downloadCommand']"
                    )
                    for btn in btns_top:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            break
                except Exception:
                    pass

        # Aguarda a conclusão do download (até 30 segundos)
        inicio = time.time()
        while time.time() - inicio < 30:
            arquivos = list(destino_path.glob("*"))
            non_temp = [f for f in arquivos if f.is_file() and not f.name.endswith((".crdownload", ".tmp", ".partial"))]
            if non_temp:
                for f in list(non_temp):
                    if f.suffix.lower() == ".zip":
                        try:
                            import zipfile
                            with zipfile.ZipFile(f, 'r') as zip_ref:
                                zip_ref.extractall(destino_path)
                            f.unlink()
                        except Exception:
                            pass
                return [f for f in destino_path.glob("*") if f.is_file()]
            time.sleep(1)

        return [f for f in destino_path.glob("*") if f.is_file()]

    def validar_download(self, destino_croqui: Path) -> bool:
        """
        Valida que o download foi concluído com sucesso (Seção 14.17 & 14.18):
        1. Diretório existe e não está vazio.
        2. Não existem arquivos parciais (.crdownload, .tmp, .partial).
        3. Todos os arquivos possuem tamanho > 0 bytes.
        """
        p = Path(destino_croqui).resolve()
        if not p.is_dir():
            raise SobDownloadIncompleteError(
                "[FALHA] Download reportado como concluído, porém o conteúdo não foi encontrado em CROQUI_DIR."
            )

        arquivos = [f for f in p.iterdir() if f.is_file()]
        if not arquivos:
            raise SobDownloadIncompleteError(
                "[FALHA] Download reportado como concluído, porém o conteúdo não foi encontrado em CROQUI_DIR."
            )

        for f in arquivos:
            ext = f.suffix.lower()
            if ext in [".crdownload", ".tmp", ".partial", ".download"]:
                raise SobDownloadIncompleteError(
                    f"[FALHA] Download incompleto: arquivo temporário '{f.name}' presente."
                )
            if f.stat().st_size == 0:
                raise SobDownloadIncompleteError(
                    f"[FALHA] Download incompleto: arquivo com zero bytes detectado '{f.name}'."
                )

        return True

    def fechar(self):
        """Fecha o navegador com segurança."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
                self._autenticado = False
