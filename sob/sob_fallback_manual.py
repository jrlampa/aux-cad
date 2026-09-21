# -*- coding: utf-8 -*-
"""
sob_fallback_manual.py - Módulo de Fallback para Múltiplas Ocorrências da SOB no SharePoint.
Responsabilidade única: Geração de URLs de pesquisa contextualizada, abertura de navegador,
cópia de identificador para área de transferência e validação rigorosa de arquivos baixados manualmente.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.parse
import webbrowser
from typing import Any, Dict, List, Optional, Tuple


def gerar_url_busca_sharepoint(sob_id: str, base_url: str = "") -> str:
    """
    Gera a URL oficial do SharePoint contextualizada com a busca pelo SOB_ID.
    """
    codigo_limpo = sob_id.strip().upper()
    if codigo_limpo.startswith("SOB_"):
        codigo_limpo = codigo_limpo[4:]

    encoded_id = urllib.parse.quote(codigo_limpo)

    if not base_url:
        try:
            from sob_sharepoint import SHAREPOINT_URL_PADRAO
            base_url = SHAREPOINT_URL_PADRAO
        except ImportError:
            try:
                from sob.sob_sharepoint import SHAREPOINT_URL_PADRAO
                base_url = SHAREPOINT_URL_PADRAO
            except ImportError:
                base_url = (
                    "https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/"
                    "IgALh51uFX0fRovCUeVsprYWAWYGyn7GwehC6BrYpg9KcFc?e=ltJeMr"
                )

    # Extrai o site base para a URL de busca padrão do SharePoint Modern
    match_site = re.search(r"https://([^/]+)/(?:sites|:f:/s|s)/([^/?#]+)", base_url)
    if match_site:
        host = match_site.group(1)
        site_name = match_site.group(2)
        return f"https://{host}/sites/{site_name}/_layouts/15/search.aspx/siteall?q={encoded_id}"

    # Fallback seguro adicionando o parâmetro de query
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}q={encoded_id}"


def copiar_para_clipboard(texto: str) -> bool:
    """Copia uma string para a área de transferência do Windows de forma segura."""
    try:
        process = subprocess.Popen(
            ["clip"],
            stdin=subprocess.PIPE,
            close_fds=True,
            shell=True,
        )
        process.communicate(input=texto.encode("utf-8"))
        return True
    except Exception:
        return False


def abrir_busca_sharepoint_navegador(sob_id: str, base_url: str = "") -> str:
    """
    Abre o navegador na URL de busca contextualizada do SharePoint e copia o SOB_ID
    para a área de transferência. Retorna a URL aberta.
    """
    url_busca = gerar_url_busca_sharepoint(sob_id, base_url)
    copiar_para_clipboard(sob_id)

    try:
        webbrowser.open(url_busca, new=2)
    except Exception:
        pass

    return url_busca


def validar_arquivos_manuais(
    origem_dir: Path,
    sob_id: str,
    extensoes_permitidas: Optional[Tuple[str, ...]] = None,
) -> List[Path]:
    """
    Valida rigorosamente os arquivos baixados manualmente pelo usuário.

    Critérios:
    - O diretório deve existir e ser acessível.
    - Deve conter ao menos um arquivo real relevante (.dwg, .pdf, .zip, .xlsx, .kmz).
    - Arquivos devem possuir tamanho > 0 bytes e não ser páginas HTML de erro.
    - Se houver múltiplos arquivos, filtra arquivos que contenham o SOB_ID ou pertençam ao lote.
    """
    if not extensoes_permitidas:
        extensoes_permitidas = (
            ".dwg",
            ".pdf",
            ".zip",
            ".xlsx",
            ".xlsm",
            ".kmz",
            ".kml",
            ".png",
            ".jpg",
            ".jpeg",
            ".doc",
            ".docx",
        )

    origem = Path(origem_dir).resolve()
    if not origem.is_dir():
        return []

    codigo_limpo = sob_id.strip().upper()
    if codigo_limpo.startswith("SOB_"):
        codigo_limpo = codigo_limpo[4:]

    candidatos: List[Path] = []

    # Procura arquivos no diretório especificado
    for item in origem.iterdir():
        if not item.is_file():
            continue

        ext = item.suffix.lower()
        if ext not in extensoes_permitidas:
            continue

        # Ignora arquivos temporários
        if item.name.startswith("~$") or item.name.endswith(".download") or item.name.endswith(".tmp"):
            continue

        # Validação física de tamanho
        try:
            tam = item.stat().st_size
            if tam <= 0:
                continue
        except OSError:
            continue

        # Rejeita páginas de erro HTML salvas com extensão incorreta
        try:
            with open(item, "rb") as f:
                header = f.read(512).lower()
                if b"<!doctype html" in header or b"<html" in header:
                    continue
        except Exception:
            continue

        candidatos.append(item)

    # Se houver candidatos, prioriza os que possuem menção explícita à SOB
    candidatos_especificos = [c for c in candidatos if codigo_limpo in c.name.upper()]
    if candidatos_especificos:
        return candidatos_especificos

    return candidatos


def copiar_arquivos_manuais_para_croqui(arquivos: List[Path], croqui_dir: Path) -> List[Path]:
    """
    Copia os arquivos manuais validados para a pasta CROQUI de destino.
    Garante integridade e retorna a lista de arquivos criados no destino.
    """
    croqui = Path(croqui_dir).resolve()
    croqui.mkdir(parents=True, exist_ok=True)

    criados: List[Path] = []

    for arq in arquivos:
        dest = croqui / arq.name
        temp_dest = croqui / f"{arq.name}.download"

        try:
            shutil.copy2(arq, temp_dest)
            # Validação física pós-cópia
            if temp_dest.stat().st_size != arq.stat().st_size:
                if temp_dest.exists():
                    temp_dest.unlink()
                raise IOError(f"Cópia parcial ou inconsistente para {arq.name}")

            # Renomeação atômica
            temp_dest.replace(dest)
            criados.append(dest)
        except Exception:
            if temp_dest.exists():
                try:
                    temp_dest.unlink()
                except Exception:
                    pass
            raise

    return criados


def executar_fallback_intervencao_manual(
    sob_id: str,
    ocorrencias: List[Any],
    url_busca: str,
    callback_progresso: Optional[Any] = None,
    logger: Optional[Any] = None,
    abrir_navegador: bool = True,
    pasta_padrao_downloads: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Orquestra o fallback manual quando múltiplas ocorrências forem detectadas no SharePoint.

    Segue as regras não negociáveis:
    - Registra log padronizado com STATUS = INTERVENÇÃO_USUÁRIO e MOTIVO = MÚLTIPLAS_OCORRÊNCIAS_SHAREPOINT.
    - Abre a busca no SharePoint contextualizada e copia SOB_ID para o clipboard.
    - Interage com a UI para aguardar download e indicação de pasta.
    - Suporta 'sem_croqui' (CROQUI = SEM_ARQUIVOS).
    - Valida arquivos baixados com rigor (rejeita 0 bytes, HTMLs de erro, temporários).
    """
    from sob_core import SobCancellationRequestedError, SobConflictError

    log_prefix = (
        f"SOB: {sob_id} | STATUS = INTERVENÇÃO_USUÁRIO | "
        f"MOTIVO = MÚLTIPLAS_OCORRÊNCIAS_SHAREPOINT | "
        f"QUANTIDADE_OCORRÊNCIAS = {len(ocorrencias)} | "
        f"AÇÃO = ABERTURA_BUSCA_SHAREPOINT"
    )
    if logger:
        logger.warning(log_prefix)

    url_real = url_busca or gerar_url_busca_sharepoint(sob_id)
    if abrir_navegador:
        abrir_busca_sharepoint_navegador(sob_id, url_real)

    if not callback_progresso or not hasattr(callback_progresso, "aguardar_intervencao"):
        # Modo não interativo (headless/CLI sem UI)
        raise SobConflictError(
            f"[BLOQUEADO] Múltiplas ocorrências ({len(ocorrencias)}) encontradas para SOB {sob_id}. "
            f"Intervenção do usuário necessária no SharePoint: {url_real}",
            ocorrencias=ocorrencias,
            url_busca=url_real,
        )

    # Loop de intervenção interativa
    pasta_busca = pasta_padrao_downloads or (Path.home() / "Downloads")
    max_tentativas = 5
    tentativa = 0

    while tentativa < max_tentativas:
        tentativa += 1
        dados_intervencao = {
            "sob_id": sob_id,
            "url_busca": url_real,
            "ocorrencias": ocorrencias,
            "pasta_sugerida": str(pasta_busca),
            "tentativa": tentativa,
        }

        resposta = callback_progresso.aguardar_intervencao(dados_intervencao)

        if not resposta or (isinstance(resposta, dict) and resposta.get("cancelar")):
            if logger:
                logger.info(f"SOB: {sob_id} | RESULTADO_DA_INTERVENÇÃO = CANCELADO")
            raise SobCancellationRequestedError("[CANCELADO] Operação cancelada pelo usuário durante intervenção.")

        # Opção: Continuar sem arquivos de croqui
        if isinstance(resposta, dict) and resposta.get("sem_croqui"):
            if logger:
                logger.info(f"SOB: {sob_id} | CROQUI = SEM_ARQUIVOS | RESULTADO_DA_INTERVENÇÃO = SUCESSO")
            return {
                "sucesso": True,
                "sem_croqui": True,
                "arquivos": [],
                "status_croqui": "SEM_ARQUIVOS",
            }

        # Caminho especificado pelo usuário
        caminho_informado = resposta.get("caminho") if isinstance(resposta, dict) else resposta
        pasta_alvo = Path(caminho_informado).resolve() if caminho_informado else pasta_busca

        arquivos_encontrados = validar_arquivos_manuais(pasta_alvo, sob_id)

        if arquivos_encontrados:
            if logger:
                logger.info(
                    f"SOB: {sob_id} | RESULTADO_DA_INTERVENÇÃO = SUCESSO | "
                    f"ARQUIVOS_OBTIDOS = {len(arquivos_encontrados)}"
                )
            return {
                "sucesso": True,
                "sem_croqui": False,
                "arquivos": arquivos_encontrados,
                "pasta_origem": str(pasta_alvo),
                "status_croqui": "DOWNLOAD_MANUAL_VALIDADO",
            }

        # Falha de validação: notifica a UI
        if hasattr(callback_progresso, "notificar"):
            callback_progresso.notificar(
                etapa="FALHA_VALIDACAO_MANUAL",
                descricao="Nenhum arquivo válido encontrado na pasta indicada.",
                estado="FALHA_VALIDACAO_MANUAL",
                detalhes={"pasta": str(pasta_alvo), "sob_id": sob_id},
            )

    raise SobConflictError(
        f"[BLOQUEADO] Número máximo de tentativas de validação manual excedido para SOB {sob_id}.",
        ocorrencias=ocorrencias,
        url_busca=url_real,
    )
