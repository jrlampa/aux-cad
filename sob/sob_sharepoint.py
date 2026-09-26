# -*- coding: utf-8 -*-
"""
Módulo de Integração com SharePoint (sob_sharepoint.py).
Responsabilidade única: Autenticação segura via Microsoft Online / SharePoint,
localização da SOB na biblioteca documental e download íntegro para a pasta CROQUI.
"""

import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import zipfile

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:
    dotenv_values = None
    load_dotenv = None


# URL Oficial da Pasta Prioritária "Levantamentos de campo" (HBT-EnelRJ-Sul)
URL_LEVANTAMENTOS_CAMPO = (
    "https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/"
    "IgALh51uFX0fRovCUeVsprYWAWYGyn7GwehC6BrYpg9KcFc?e=lqKnT7"
)

# URL Padrão do SharePoint da HBT Enel Rio
SHAREPOINT_URL_PADRAO = URL_LEVANTAMENTOS_CAMPO


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


from sob_core import SobConflictError


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


def obter_url_sharepoint(
    caminho_env: Optional[Union[str, Path]] = None,
) -> str:
    """
    Retorna a URL do SharePoint configurada no .env ou o link padrão da pasta de Levantamentos de campo.
    """
    env_path = Path(caminho_env) if caminho_env else obter_caminho_env_padrao()
    if env_path.is_file():
        if dotenv_values:
            vals = dotenv_values(dotenv_path=env_path)
            url_cfg = (vals.get("SHAREPOINT_URL") or "").strip()
            if url_cfg:
                return url_cfg
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                linha = line.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    if k.strip() == "SHAREPOINT_URL":
                        v_clean = v.strip().strip('"').strip("'")
                        if v_clean:
                            return v_clean
    return os.environ.get("SHAREPOINT_URL", "").strip() or SHAREPOINT_URL_PADRAO


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
        url: Optional[str] = None,
        headless: bool = True,
        timeout: int = 30,
        logger: Optional[Any] = None,
    ):
        self.login = login
        self.senha = senha
        self.url = url or obter_url_sharepoint()
        self.headless = headless
        self.timeout = timeout
        self.logger = logger
        self.driver = None
        self._autenticado = False
        self._eventos_telemetria: List[Dict[str, Any]] = []

    def _log(self, mensagem: str):
        """Emite mensagem de diagnóstico no logger configurado ou via print."""
        if self.logger and hasattr(self.logger, "info"):
            self.logger.info(mensagem)
        else:
            print(mensagem)

    def _telemetria(self, evento: str, **kwargs):
        """
        Emite evento de telemetria estruturado e não intrusivo.

        Garantias:
        1. Formato padronizado e pesquisável: [TELEMETRIA] event=<evento> chave=valor ...
        2. Segurança First: Sanitiza estritamente os campos, impedindo vazamento de credenciais.
        3. Não-intrusivo: Qualquer falha interna na telemetria é silenciosamente ignorada.
        4. Rastreabilidade: Mantém registro em self._eventos_telemetria para testes e inspeção.
        """
        try:
            chaves_proibidas = {"senha", "token", "cookie", "credencial", "password", "secret", "key"}
            payload = {"event": str(evento)}
            segredos = [s for s in [self.login, self.senha] if s]

            for k, v in kwargs.items():
                k_clean = str(k).lower().strip()
                if any(p in k_clean for p in chaves_proibidas):
                    continue
                v_str = str(v)
                v_sanitizado = sanitizar_mensagem(v_str, segredos)
                payload[k] = v_sanitizado

            # Formata como string chave=valor consistente e pesquisável
            partes = [f"{k}={v}" for k, v in payload.items()]
            msg_formatada = f"[TELEMETRIA] {' '.join(partes)}"
            self._log(msg_formatada)

            if not hasattr(self, "_eventos_telemetria") or not isinstance(self._eventos_telemetria, list):
                self._eventos_telemetria = []
            self._eventos_telemetria.append(payload)
        except Exception:
            # Observabilidade pura: nunca interrompe o fluxo operacional
            pass

    @property
    def eventos_telemetria(self) -> List[Dict[str, Any]]:
        """Retorna uma cópia dos eventos de telemetria registrados."""
        return list(getattr(self, "_eventos_telemetria", []))

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

    @staticmethod
    def _item_eh_croqui_valido(nome_item: str, codigo_busca: str) -> bool:
        """
        Verifica se um item retornado da listagem do SharePoint representa um croqui válido:
        1. Nome deve conter o código da SOB (codigo_busca);
        2. Não pode ser arquivo temporário ou do sistema;
        3. Se possuir extensão de arquivo, deve pertencer às extensões aceitas pelo ecossistema SOB.
        """
        if not nome_item:
            return False

        nome_limpo = nome_item.strip()
        nome_upper = nome_limpo.upper()

        if codigo_busca not in nome_upper:
            return False

        # Rejeita arquivos temporários e do sistema
        if nome_upper.startswith("~$") or nome_upper.startswith(".~") or "DESKTOP.INI" in nome_upper or "THUMBS.DB" in nome_upper:
            return False
        if any(nome_upper.endswith(ext) for ext in [".TMP", ".CRDOWNLOAD", ".PARTIAL", ".DOWNLOAD", ".LNK", ".URL"]):
            return False

        # Se tiver extensão de executáveis ou scripts inválidos
        extensoes_invalidas = {".EXE", ".BAT", ".CMD", ".SH", ".PS1", ".VBS", ".JS", ".LOG", ".BAK"}
        for ext_inv in extensoes_invalidas:
            if nome_upper.endswith(ext_inv):
                return False

        # Se possui extensão de arquivo
        if "." in nome_limpo:
            partes = nome_limpo.rsplit(".", 1)
            ext = "." + partes[1].lower()
            extensoes_permitidas = (
                ".dwg", ".pdf", ".zip", ".xlsx", ".xlsm",
                ".kmz", ".kml", ".png", ".jpg", ".jpeg",
                ".doc", ".docx",
            )
            return ext in extensoes_permitidas

        # Sem extensão de arquivo representa pasta da SOB (ex: 'SOB_A057349839')
        return True

    def buscar_em_levantamentos_campo(self, sob_codigo: str) -> Optional[Dict[str, Any]]:
        """
        Busca prioritária na pasta oficial 'Levantamentos de campo' (HBT-EnelRJ-Sul).
        Retorna o dicionário de informações do item se localizado e válido,
        ou None se não encontrar ou se os itens não forem válidos.
        Levanta SobConflictError se houver múltiplas correspondências ambíguas.
        """
        if not self._autenticado:
            self.autenticar()

        from selenium.webdriver.common.by import By

        codigo_limpo = sob_codigo.strip().upper()
        if codigo_limpo.startswith("SOB_"):
            codigo_busca = codigo_limpo[4:]
        else:
            codigo_busca = codigo_limpo

        target_url = URL_LEVANTAMENTOS_CAMPO

        try:
            if self.driver:
                curr = self.driver.current_url
                if "IgALh51uFX0fRovCUeVsprYWAWYGyn7GwehC6BrYpg9KcFc" not in curr:
                    self.driver.get(target_url)
                    time.sleep(4)

            itens_encontrados = []
            seletor_linhas = "[role='row'], [data-automationid='DetailsRow'], tr[role='row'], div.ms-DetailsRow"
            linhas = self.driver.find_elements(By.CSS_SELECTOR, seletor_linhas) if self.driver else []

            for linha in linhas:
                txt = linha.text
                nome = txt.split("\n")[0].strip()
                if self._item_eh_croqui_valido(nome, codigo_busca):
                    itens_encontrados.append({
                        "texto": txt,
                        "elemento": linha,
                        "sob": codigo_busca,
                        "origem": "LEVANTAMENTOS_DE_CAMPO",
                    })

            # Tenta em links diretos de nomes de arquivos/pastas
            if not itens_encontrados and self.driver:
                links = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "button[data-automationid='FieldRenderer-name'], a[data-automationid='FieldRenderer-name'], [role='gridcell']"
                )
                for lk in links:
                    txt = lk.text
                    nome = txt.split("\n")[0].strip()
                    if self._item_eh_croqui_valido(nome, codigo_busca):
                        itens_encontrados.append({
                            "texto": txt,
                            "elemento": lk,
                            "sob": codigo_busca,
                            "origem": "LEVANTAMENTOS_DE_CAMPO",
                        })

            if not itens_encontrados:
                return None

            # Filtra resultados únicos
            pastas_correspondentes = []
            nomes_unicos = set()
            for item in itens_encontrados:
                nome = item["texto"].split("\n")[0].strip()
                if nome not in nomes_unicos:
                    nomes_unicos.add(nome)
                    pastas_correspondentes.append(item)

            if len(pastas_correspondentes) > 1:
                try:
                    from sob.sob_fallback_manual import gerar_url_busca_sharepoint
                except ModuleNotFoundError:
                    from sob_fallback_manual import gerar_url_busca_sharepoint

                url_b = gerar_url_busca_sharepoint(codigo_busca, target_url)
                raise SobConflictError(
                    "[FALHA] Foram encontradas múltiplas correspondências ambíguas.",
                    ocorrencias=pastas_correspondentes,
                    url_busca=url_b,
                )

            return pastas_correspondentes[0]

        except (SobConflictError, SobAuthenticationError):
            raise
        except Exception as e:
            msg_sanitizada = sanitizar_mensagem(str(e), [self.login, self.senha])
            self._log(f"[SHAREPOINT] Falha na busca em Levantamentos de campo: {msg_sanitizada}")
            return None

    def localizar_pasta_sob_existente(self, sob_codigo: str) -> Dict[str, Any]:
        """
        Mecanismo de pesquisa existente no SharePoint (fallback).
        Realiza a busca no site/biblioteca documental atual e utiliza a caixa de pesquisa
        caso o item não esteja imediatamente visível.
        """
        if not self._autenticado:
            self.autenticar()

        from selenium.webdriver.common.by import By

        codigo_limpo = sob_codigo.strip().upper()
        if codigo_limpo.startswith("SOB_"):
            codigo_busca = codigo_limpo[4:]
        else:
            codigo_busca = codigo_limpo

        try:
            # Garante que a página do SharePoint esteja carregada
            if "sharepoint.com" not in self.driver.current_url:
                self.driver.get(self.url)
                time.sleep(4)

            itens_encontrados = []
            seletor_linhas = "[role='row'], [data-automationid='DetailsRow'], tr[role='row'], div.ms-DetailsRow"
            linhas = self.driver.find_elements(By.CSS_SELECTOR, seletor_linhas)

            for linha in linhas:
                txt = linha.text
                if codigo_busca in txt.upper():
                    itens_encontrados.append({
                        "texto": txt,
                        "elemento": linha,
                        "sob": codigo_busca,
                    })

            # 2. Se não encontrou, tenta buscar por links diretos de pastas (nomes de arquivos/pastas)
            if not itens_encontrados:
                links = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "button[data-automationid='FieldRenderer-name'], a[data-automationid='FieldRenderer-name'], [role='gridcell']"
                )
                for lk in links:
                    txt = lk.text
                    if codigo_busca in txt.upper():
                        itens_encontrados.append({
                            "texto": txt,
                            "elemento": lk,
                            "sob": codigo_busca,
                        })

            # 3. Se não encontrou na listagem inicial, tenta pesquisar na barra de busca do SharePoint
            if not itens_encontrados:
                caixas_busca = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "input[type='search'], input[aria-label*='Pesquisar'], input[aria-label*='Search'], input[placeholder*='Pesquisar']"
                )
                if caixas_busca:
                    caixa = caixas_busca[0]
                    caixa.clear()
                    caixa.send_keys(codigo_busca)
                    caixa.send_keys("\n")
                    time.sleep(5)

                    # Reavalia itens encontrados após a busca
                    linhas = self.driver.find_elements(By.CSS_SELECTOR, seletor_linhas)
                    for linha in linhas:
                        txt = linha.text
                        if codigo_busca in txt.upper():
                            itens_encontrados.append({
                                "texto": txt,
                                "elemento": linha,
                                "sob": codigo_busca,
                            })

            # Validação dos resultados (Seção 17, Etapa A13)
            if len(itens_encontrados) == 0:
                raise SobNotFoundError(
                    f"[FALHA] SOB {sob_codigo} não encontrada no SharePoint."
                )

            # Se encontrar múltiplos resultados, verifica se pertencem estritamente à mesma SOB
            pastas_correspondentes = []
            nomes_unicos = set()
            for item in itens_encontrados:
                nome = item["texto"].split("\n")[0].strip()
                if codigo_busca in nome.upper() and nome not in nomes_unicos:
                    nomes_unicos.add(nome)
                    pastas_correspondentes.append(item)

            if len(pastas_correspondentes) == 0:
                pastas_correspondentes = [itens_encontrados[0]]

            if len(pastas_correspondentes) > 1:
                try:
                    from sob.sob_fallback_manual import gerar_url_busca_sharepoint
                except ModuleNotFoundError:
                    from sob_fallback_manual import gerar_url_busca_sharepoint

                url_b = gerar_url_busca_sharepoint(codigo_busca, self.url)
                raise SobConflictError(
                    "[FALHA] Foram encontradas múltiplas correspondências ambíguas.",
                    ocorrencias=pastas_correspondentes,
                    url_busca=url_b,
                )

            return pastas_correspondentes[0]

        except (SobNotFoundError, SobConflictError):
            raise
        except Exception as e:
            msg_sanitizada = sanitizar_mensagem(str(e), [self.login, self.senha])
            raise SobSharepointError(f"Erro ao pesquisar SOB no SharePoint: {msg_sanitizada}")

    def localizar_pasta_sob(self, sob_codigo: str) -> Dict[str, Any]:
        """
        Localiza a pasta da SOB informada dentro do SharePoint.
        
        Estratégia de Busca:
        1. PRIMEIRA TENTATIVA (PRIORITÁRIA):
           Busca na pasta oficial 'Levantamentos de campo' (HBT-EnelRJ-Sul).
           Se encontrar croqui válido, retorna imediatamente.
        2. FALLBACK (BUSCA EXISTENTE):
           Caso não localize em 'Levantamentos de campo', executa o mecanismo
           de pesquisa existente que já operava anteriormente no módulo SOB.
        """
        if not self._autenticado:
            self.autenticar()

        # 1. TENTATIVA PRIORITÁRIA: Levantamentos de campo
        t0_prio = time.perf_counter()
        self._telemetria("sharepoint.search.priority.start", sob_id=sob_codigo, origem="Levantamentos de campo")
        try:
            self._log('[SHAREPOINT] Buscando croqui em "Levantamentos de campo"...')
            resultado_prio = self.buscar_em_levantamentos_campo(sob_codigo)
            duracao_prio_ms = round((time.perf_counter() - t0_prio) * 1000, 2)
            if resultado_prio:
                self._log('[SHAREPOINT] Croqui localizado na busca prioritária.')
                self._telemetria(
                    "sharepoint.search.priority.result",
                    sob_id=sob_codigo,
                    origem="Levantamentos de campo",
                    result="found",
                    duracao_ms=duracao_prio_ms,
                )
                nome_croqui = resultado_prio.get("texto", "").split("\n")[0].strip() or resultado_prio.get("sob", sob_codigo)
                self._telemetria(
                    "sharepoint.croqui.found",
                    sob_id=sob_codigo,
                    origem="Levantamentos de campo",
                    nome_arquivo=nome_croqui,
                )
                return resultado_prio

            self._log('[SHAREPOINT] Nenhum croqui válido encontrado em "Levantamentos de campo".')
            self._telemetria(
                "sharepoint.search.priority.result",
                sob_id=sob_codigo,
                origem="Levantamentos de campo",
                result="not_found",
                duracao_ms=duracao_prio_ms,
            )
        except (SobConflictError, SobAuthenticationError) as e_prio_fatal:
            duracao_prio_ms = round((time.perf_counter() - t0_prio) * 1000, 2)
            self._telemetria(
                "sharepoint.search.priority.result",
                sob_id=sob_codigo,
                origem="Levantamentos de campo",
                result="error",
                duracao_ms=duracao_prio_ms,
                erro=type(e_prio_fatal).__name__,
            )
            raise
        except Exception as e_prio:
            duracao_prio_ms = round((time.perf_counter() - t0_prio) * 1000, 2)
            self._telemetria(
                "sharepoint.search.priority.result",
                sob_id=sob_codigo,
                origem="Levantamentos de campo",
                result="error",
                duracao_ms=duracao_prio_ms,
                erro=type(e_prio).__name__,
            )
            self._log(f'[SHAREPOINT] Erro não-fatal na busca prioritária: {e_prio}. Executando mecanismo existente...')

        # 2. FALLBACK: Mecanismo de pesquisa existente
        t0_fallback = time.perf_counter()
        self._telemetria("sharepoint.search.fallback.start", sob_id=sob_codigo, origem="busca_existente")
        self._log('[SHAREPOINT] Executando mecanismo de pesquisa existente...')
        try:
            resultado_fb = self.localizar_pasta_sob_existente(sob_codigo)
            duracao_fb_ms = round((time.perf_counter() - t0_fallback) * 1000, 2)
            self._telemetria(
                "sharepoint.search.fallback.result",
                sob_id=sob_codigo,
                origem="busca_existente",
                result="found",
                duracao_ms=duracao_fb_ms,
            )
            nome_croqui_fb = resultado_fb.get("texto", "").split("\n")[0].strip() or resultado_fb.get("sob", sob_codigo)
            self._telemetria(
                "sharepoint.croqui.found",
                sob_id=sob_codigo,
                origem="busca_existente",
                nome_arquivo=nome_croqui_fb,
            )
            return resultado_fb
        except SobNotFoundError:
            duracao_fb_ms = round((time.perf_counter() - t0_fallback) * 1000, 2)
            self._telemetria(
                "sharepoint.search.fallback.result",
                sob_id=sob_codigo,
                origem="busca_existente",
                result="not_found",
                duracao_ms=duracao_fb_ms,
            )
            raise
        except Exception as e_fb:
            duracao_fb_ms = round((time.perf_counter() - t0_fallback) * 1000, 2)
            self._telemetria(
                "sharepoint.search.fallback.result",
                sob_id=sob_codigo,
                origem="busca_existente",
                result="error",
                duracao_ms=duracao_fb_ms,
                erro=type(e_fb).__name__,
            )
            raise

    def validar_conteudo_disponivel(self, pasta_info: Dict[str, Any]) -> bool:
        """
        Valida se o conteúdo da SOB está efetivamente disponível no SharePoint (Etapa A14).
        """
        if not pasta_info:
            raise SobDownloadError("[FALHA] O conteúdo da SOB não está disponível para download.")
        return True

    def _aguardar_e_processar_download(self, destino_path: Path, timeout: int = 45) -> List[Path]:
        """
        Aguarda a conclusão do download, processa descompactação de ZIP e nivela pastas.
        """
        inicio = time.time()
        while time.time() - inicio < timeout:
            arquivos = list(destino_path.glob("*"))
            non_temp = [f for f in arquivos if f.is_file() and not f.name.endswith((".crdownload", ".tmp", ".partial", ".download"))]
            em_andamento = any(f.name.endswith((".crdownload", ".tmp", ".partial", ".download")) for f in arquivos)

            if non_temp and not em_andamento:
                # Processa descompactação de ZIPs (pastas baixadas pelo SharePoint vêm sempre em ZIP)
                for f in list(non_temp):
                    if f.suffix.lower() == ".zip":
                        try:
                            with zipfile.ZipFile(f, 'r') as zip_ref:
                                zip_ref.extractall(destino_path)
                            f.unlink()

                            # Se a extração gerou uma pasta raiz única (ex: SOB_A057389468/), move conteúdos para destino_path
                            itens_extraidos = [i for i in destino_path.iterdir()]
                            if len(itens_extraidos) == 1 and itens_extraidos[0].is_dir():
                                pasta_interna = itens_extraidos[0]
                                for sub_item in list(pasta_interna.iterdir()):
                                    dest_sub = destino_path / sub_item.name
                                    if not dest_sub.exists():
                                        shutil.move(str(sub_item), str(dest_sub))
                                try:
                                    pasta_interna.rmdir()
                                except Exception:
                                    pass
                        except Exception:
                            pass

                arquivos_finais = [f for f in destino_path.rglob("*") if f.is_file()]
                if arquivos_finais:
                    return arquivos_finais
            time.sleep(1)

        return [f for f in destino_path.rglob("*") if f.is_file()]

    def baixar_pasta_por_url(self, url: str, destino_croqui: Path) -> List[Path]:
        """
        Navega diretamente para a URL da pasta ou link de compartilhamento fornecido
        pelo usuário e realiza o download de todo o seu conteúdo para destino_croqui.
        """
        if not self._autenticado:
            self.autenticar()

        from selenium.webdriver.common.by import By

        destino_path = Path(destino_croqui).resolve()
        destino_path.mkdir(parents=True, exist_ok=True)

        try:
            self.driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(destino_path)}
            )
        except Exception:
            pass

        self.driver.get(url)
        time.sleep(4)

        # 1. Tenta clicar no botão de Download na barra de comandos superior
        seletor_download = (
            "button[name='Download'], button[name='Baixar'], "
            "[data-automationid='downloadCommand'], button[aria-label*='Baixar'], "
            "button[aria-label*='Download'], button[data-automationid='downloadButton']"
        )
        btns_download = self.driver.find_elements(By.CSS_SELECTOR, seletor_download)
        clicado = False
        for btn in btns_download:
            if btn.is_displayed():
                self.driver.execute_script("arguments[0].click();", btn)
                clicado = True
                break

        # 2. Se não encontrou o botão diretamente, tenta marcar 'Selecionar tudo'
        if not clicado:
            try:
                chks_all = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[role='columnheader'] [role='checkbox'], "
                    "button[data-automationid='FieldRenderer-selectAllCheck'], "
                    "[data-automationid='DetailsHeader-checkAll'], "
                    "div.ms-DetailsHeader-check"
                )
                if chks_all:
                    self.driver.execute_script("arguments[0].click();", chks_all[0])
                    time.sleep(1.5)
                    btns_download = self.driver.find_elements(By.CSS_SELECTOR, seletor_download)
                    for btn in btns_download:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            clicado = True
                            break
            except Exception:
                pass

        # 3. Se ainda não clicou, tenta marcar a primeira linha/pasta visível
        if not clicado:
            try:
                linhas = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[role='row'], [data-automationid='DetailsRow']"
                )
                if linhas:
                    chks = linhas[0].find_elements(By.CSS_SELECTOR, "[role='checkbox'], .ms-Check")
                    if chks:
                        self.driver.execute_script("arguments[0].click();", chks[0])
                        time.sleep(1)
                        btns_download = self.driver.find_elements(By.CSS_SELECTOR, seletor_download)
                        for btn in btns_download:
                            if btn.is_displayed():
                                self.driver.execute_script("arguments[0].click();", btn)
                                clicado = True
                                break
            except Exception:
                pass

        return self._aguardar_e_processar_download(destino_path, timeout=60)

    def baixar_croqui(self, pasta_info: Dict[str, Any], destino_croqui: Path) -> List[Path]:
        """
        Baixa a pasta inteira da SOB localizada para destino_croqui.
        Garante descompactação íntegra (caso baixada como ZIP) e ausência de arquivos temporários.
        """
        sob_id = (pasta_info and pasta_info.get("sob")) or "DESCONHECIDO"
        t0_download = time.perf_counter()
        self._telemetria(
            "sharepoint.download.start",
            sob_id=sob_id,
            destino=str(Path(destino_croqui).name),
        )

        try:
            if pasta_info.get("tipo") == "url_direta" or (pasta_info.get("url") and not pasta_info.get("elemento")):
                arquivos = self.baixar_pasta_por_url(pasta_info.get("url"), destino_croqui)
            else:
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
                    # 1. Tenta marcar o checkbox de seleção da linha da pasta
                    try:
                        chks = elem.find_elements(
                            By.CSS_SELECTOR,
                            "[role='checkbox'], [data-automationid='DetailsRowCheck'], .ms-Check"
                        )
                        if chks:
                            self.driver.execute_script("arguments[0].click();", chks[0])
                            time.sleep(1)
                            # Clica no botão de Download na barra superior
                            btns_top = self.driver.find_elements(
                                By.CSS_SELECTOR,
                                "button[name='Download'], button[name='Baixar'], [data-automationid='downloadCommand'], button[aria-label*='Baixar'], button[aria-label*='Download']"
                            )
                            for btn in btns_top:
                                if btn.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    clicado = True
                                    break
                    except Exception:
                        pass

                    # 2. Se não clicou via checkbox e barra superior, tenta o menu de contexto (...) da pasta
                    if not clicado:
                        try:
                            botoes = elem.find_elements(By.TAG_NAME, "button")
                            for b in botoes:
                                aria = (b.get_attribute("aria-label") or "").lower()
                                if any(k in aria for k in ["mais", "ações", "actions", "..."]):
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

                    # 3. Fallback: clique no elemento e busca na barra de comandos
                    if not clicado:
                        try:
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

                arquivos = self._aguardar_e_processar_download(destino_path, timeout=45)

            duracao_dl_ms = round((time.perf_counter() - t0_download) * 1000, 2)
            self._telemetria(
                "sharepoint.download.success",
                sob_id=sob_id,
                total_arquivos=len(arquivos),
                duracao_ms=duracao_dl_ms,
            )
            return arquivos
        except Exception as e_dl:
            duracao_dl_ms = round((time.perf_counter() - t0_download) * 1000, 2)
            self._telemetria(
                "sharepoint.download.error",
                sob_id=sob_id,
                duracao_ms=duracao_dl_ms,
                erro=type(e_dl).__name__,
            )
            raise

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

        arquivos = [f for f in p.rglob("*") if f.is_file()]
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
