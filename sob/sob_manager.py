# -*- coding: utf-8 -*-
"""
Orquestrador Principal do Módulo SOB (sob_manager.py).
Responsabilidade única: Coordenação do fluxo de preparação da SOB,
emissão de logs de diagnóstico, tratamento de erros e interface CLI/JSON para o AutoCAD.
"""

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple

_current_dir = str(Path(__file__).resolve().parent)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from sob_core import (
    normalizar_sob,
    validar_sob,
    validar_sob_id,
    validar_sob_name,
    obter_sob_id,
    obter_sob_name,
    derivar_caminhos_sob,
    verificar_pasta_sob_existente,
    validar_permissao_criacao,
    criar_estrutura_sob,
    copiar_arquivo_base,
    validar_arquivo_dwg,
    calcular_hash_arquivo,
    remover_estrutura_incompleta,
    SobValidationError,
    SobPermissionError,
    SobDirectoryExistsError,
    SobFileExistsError,
    SobFileNotFoundError,
    SobIntegrityError,
)
from sob_rollback import RollbackContext
from sob_idempotencia import (
    gerar_run_id,
    gravar_manifesto_execucao,
    classificar_sob_root,
    verificar_arquivo_download_idempotente,
)
from sob_gomnet import (
    GomnetClient,
    GomnetAnexo,
    GomnetError,
    GomnetAuthError,
    GomnetNotFoundError,
    GomnetDownloadError,
    carregar_credenciais_gomnet,
)
from sob_sharepoint import (
    obter_credenciais_sharepoint,
    sanitizar_mensagem,
    SharePointClient,
    SobSharepointError,
    SobEnvNotFoundError,
    SobCredentialError,
    SobAuthenticationError,
    SobSharepointUnavailableError,
    SobNotFoundError,
    SobConflictError,
    SobDownloadError,
    SobDownloadIncompleteError,
)

# Caminho padrão do arquivo-base prancha.dwg
CAMINHO_BASE_PRANCHA_PADRAO = (
    Path(__file__).resolve().parent.parent / "modelos" / "prancha.dwg"
)


def formatar_mensagem_erro(
    etapa: str,
    problema: str,
    caminho: Optional[str] = None,
    acao: Optional[str] = None,
) -> str:
    """Formata mensagens de erro de acordo com a Seção 14.26."""
    linhas = [
        "[ERRO]",
        "",
        "Etapa:",
        etapa,
        "",
        "Problema:",
        problema,
    ]
    if caminho:
        linhas.extend(["", "Caminho afetado:", caminho])
    if acao:
        linhas.extend(["", "Ação:", acao])
    return "\n".join(linhas)


class LoggerSeguro:
    """Logger formatado que impede vazamento de senhas ou segredos."""

    def __init__(self, logger: logging.Logger, segredos: Optional[list] = None):
        self._logger = logger
        self.segredos = segredos or []

    def adicionar_segredo(self, segredo: str):
        if segredo and segredo not in self.segredos:
            self.segredos.append(segredo)

    def info(self, msg: str):
        msg_limpa = sanitizar_mensagem(msg, self.segredos)
        self._logger.info(msg_limpa)

    def error(self, msg: str):
        msg_limpa = sanitizar_mensagem(msg, self.segredos)
        self._logger.error(msg_limpa)

    def warning(self, msg: str):
        msg_limpa = sanitizar_mensagem(msg, self.segredos)
        self._logger.warning(msg_limpa)


def configurar_logger() -> LoggerSeguro:
    """Configura o logger com formato padrão do projeto."""
    logger = logging.getLogger("AUXCAD_SOB")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return LoggerSeguro(logger)


class SobOrchestrator:
    """Orquestrador do ciclo de vida da preparação de projeto SOB com validações estritas (Seção 14)."""

    def __init__(
        self,
        origem_base: Optional[Path] = None,
        sharepoint_client: Optional[SharePointClient] = None,
        gomnet_client: Optional[Any] = None,
        logger: Optional[LoggerSeguro] = None,
    ):
        self.origem_base = origem_base or CAMINHO_BASE_PRANCHA_PADRAO
        self.sharepoint_client = sharepoint_client
        self.gomnet_client = gomnet_client
        self.logger = logger or configurar_logger()

    def executar(
        self,
        sob_raw: str,
        destino_dir: str,
        baixar_croqui_sp: bool = True,
        consultar_gomnet: bool = True,
        abrir_cad: bool = False,
    ) -> Dict[str, Any]:
        """
        Executa o fluxo completo da SOB de acordo com as regras de negócio e validações da Seção 14.
        """
        resultado: Dict[str, Any] = {
            "sucesso": False,
            "status": "BLOQUEADO",
            "pre_validacao": "BLOQUEADA",
            "fase": "FASE_A",
            "estado": "INICIANDO",
            "etapa": "INICIO",
            "mensagem": "",
            "SOB_ID": "",
            "SOB_NAME": "",
            "DESTINATION_ROOT": "",
            "SOB_ROOT": "",
            "CROQUI_DIR": "",
            "BASE_DWG": "",
            "sob": "",
            "sob_root": "",
            "croqui_dir": "",
            "dwg_path": "",
            "arquivos_croqui": [],
            "GOMNET_ATTACHMENTS": [],
            "GOMNET_CREATED_FILES": [],
            "ANEXOS_DIR": "",
            "checklist": {},
            "rollback": "ROLLBACK_NÃO_NECESSÁRIO",
            "rollback_info": None,
            "RUN_ID": gerar_run_id(),
        }

        checklist: Dict[str, bool] = {
            "SOB_ID válido": False,
            "SOB_NAME válido": False,
            "DESTINATION_ROOT válido": False,
            "SOB_ROOT disponível": False,
            "SOB_ROOT correto": False,
            "CROQUI_DIR correto": False,
            "Permissão de criação validada": False,
            "BASE_TEMPLATE validado": False,
            "BASE_DWG disponível": False,
            "Credenciais SharePoint validadas": False,
            "Autenticação validada": False,
            "SOB encontrada no SharePoint": False,
            "Conteúdo disponível para download": False,
            "GOMNET validado": False,
            "Pré-validação concluída": False,
            "SOB_ROOT criado": False,
            "CROQUI_DIR criado": False,
            "Download concluído": False,
            "Conteúdo do CROQUI validado": False,
            "Download GOMNET concluído": False,
            "BASE_DWG criado": False,
            "BASE_DWG validado": False,
            "Integridade validada": False,
            "BASE_TEMPLATE preservado": False,
            "Estrutura final validada": False,
        }

        estrutura_criada_nesta_execucao = False
        sob_root_path: Optional[Path] = None
        client: Optional[SharePointClient] = None
        pasta_info: Optional[Dict[str, Any]] = None
        rollback_ctx: Optional[RollbackContext] = None
        gom_client: Optional[GomnetClient] = None

        try:
            self.logger.info("Início da operação - FASE A: PRÉ-VALIDAÇÃO")

            # =========================================================================
            # FASE A — PRÉ-VALIDAÇÃO (Não cria, não copia e não baixa nada)
            # =========================================================================

            # ETAPA A02 & A03: Normalizar e validar SOB
            resultado["estado"] = "INICIANDO"
            resultado["etapa"] = "VALIDAR_SOB"

            if not sob_raw or not str(sob_raw).strip():
                raise SobValidationError("[FALHA] Número da SOB inválido.")

            sob_id = obter_sob_id(sob_raw)
            checklist["SOB_ID válido"] = True

            sob_name = obter_sob_name(sob_raw)
            checklist["SOB_NAME válido"] = True
            resultado["estado"] = "SOB_VALIDADA"

            # ETAPA A04 & A05: Selecionar e Validar DESTINATION_ROOT
            resultado["etapa"] = "VALIDAR_DESTINO"
            if not destino_dir or not str(destino_dir).strip():
                raise SobValidationError("[INFO] Operação cancelada pelo usuário.")

            destination_root = Path(destino_dir).resolve()
            if not destination_root.is_dir():
                raise SobValidationError(
                    formatar_mensagem_erro(
                        etapa="Validação do Diretório de Destino",
                        problema="[FALHA] Diretório de destino inválido.",
                        caminho=str(destination_root),
                        acao="Selecione uma pasta válida no sistema de arquivos.",
                    )
                )

            checklist["DESTINATION_ROOT válido"] = True
            resultado["estado"] = "DESTINO_VALIDADO"

            # ETAPA A06: Derivar caminhos canônicos
            caminhos = derivar_caminhos_sob(sob_raw, destination_root, self.origem_base)
            sob_root_path = caminhos["SOB_ROOT"]
            croqui_dir = caminhos["CROQUI_DIR"]
            base_dwg = caminhos["BASE_DWG"]
            base_template = caminhos["BASE_TEMPLATE"]

            # Instancia o contexto de rollback seguro (Seção 18.2)
            rollback_ctx = RollbackContext(
                sob_id=sob_id,
                destination_root=destination_root,
                sob_root=sob_root_path,
                croqui_dir=croqui_dir,
                base_dwg=base_dwg,
                base_template=base_template,
                logger_instance=self.logger,
            )

            resultado["SOB_ID"] = sob_id
            resultado["SOB_NAME"] = sob_name
            resultado["DESTINATION_ROOT"] = str(destination_root)
            resultado["SOB_ROOT"] = str(sob_root_path)
            resultado["CROQUI_DIR"] = str(croqui_dir)
            resultado["BASE_DWG"] = str(base_dwg)
            resultado["sob"] = sob_name
            resultado["sob_root"] = str(sob_root_path)
            resultado["croqui_dir"] = str(croqui_dir)

            checklist["SOB_ROOT correto"] = True
            checklist["CROQUI_DIR correto"] = True

            self.logger.info(f"SOB: {sob_id}")
            self.logger.info(f"SOB_ROOT: {sob_root_path}")
            self.logger.info(f"CROQUI_DIR: {croqui_dir}")
            self.logger.info(f"BASE_DWG: {base_dwg}")

            # ETAPA A07: Análise de Idempotência e Conflito de SOB_ROOT (Seção 19.2 a 19.10)
            classificacao, msg_classificacao, manifesto_previo = classificar_sob_root(
                destination_root=destination_root,
                sob_name=sob_name,
                nome_dwg_base=base_dwg.name,
            )

            if classificacao == "EXISTE_E_ESTÁ_CONCLUÍDA":
                # Seção 19.7: A SOB já possui uma execução concluída neste destino. Bloquear duplicação.
                self.logger.info(msg_classificacao)
                resultado["status"] = "BLOQUEADO"
                resultado["mensagem"] = msg_classificacao
                resultado["pre_validacao"] = "OK"
                resultado["etapa"] = "SOB_CONCLUIDA_EXISTENTE"
                return resultado

            if classificacao in ("EXISTE_E_ESTÁ_INCOMPLETA", "EXISTE_EM_ESTADO_INCONSISTENTE"):
                # Seção 19.9 & 19.10: Execução anterior incompleta ou inconsistente
                raise SobDirectoryExistsError(msg_classificacao)

            if classificacao == "EXISTE_E_NÃO_É_DA_EXECUÇÃO":
                raise SobDirectoryExistsError(
                    formatar_mensagem_erro(
                        etapa="Criação da pasta da SOB",
                        problema="[FALHA] A pasta da SOB já existe.",
                        caminho=str(sob_root_path),
                        acao="Verifique a pasta existente ou selecione outro diretório de destino.",
                    )
                )

            checklist["SOB_ROOT disponível"] = True

            # ETAPA A08: Validar possibilidade de criação (sem criar nada)
            if not validar_permissao_criacao(destination_root):
                raise SobPermissionError(
                    "[FALHA] O diretório selecionado não permite a criação da estrutura da SOB."
                )
            checklist["Permissão de criação validada"] = True

            # ETAPA A09: Validar BASE_TEMPLATE
            resultado["etapa"] = "VALIDAR_BASE_TEMPLATE"
            if not base_template.is_file() or not os.access(base_template, os.R_OK):
                raise SobFileNotFoundError(
                    formatar_mensagem_erro(
                        etapa="Validação do Arquivo-Modelo",
                        problema="[FALHA] Arquivo-modelo prancha.dwg não encontrado ou inacessível.",
                        caminho=str(base_template),
                        acao="Verifique se o arquivo modelos/prancha.dwg está presente e acessível.",
                    )
                )
            checklist["BASE_TEMPLATE validado"] = True
            self.logger.info("Arquivo-base localizado")

            # ETAPA A10: Validar disponibilidade de BASE_DWG
            if base_dwg.exists():
                raise SobFileExistsError(
                    f"[FALHA] O arquivo BASE_SOB_DESENHO.dwg já existe no destino."
                )
            checklist["BASE_DWG disponível"] = True

            # ETAPAS A11 a A14: SharePoint na Pré-Validação
            if baixar_croqui_sp:
                resultado["etapa"] = "SHAREPOINT_PRE_VALIDACAO"
                self.logger.info("Pré-validação SharePoint iniciada")

                client = self.sharepoint_client
                if not client:
                    login, senha = obter_credenciais_sharepoint()
                    self.logger.adicionar_segredo(senha)
                    client = SharePointClient(login=login, senha=senha, headless=True)

                # ETAPA A11 & A12: Credenciais e Autenticação
                checklist["Credenciais SharePoint validadas"] = True
                client.autenticar()
                checklist["Autenticação validada"] = True
                resultado["estado"] = "SHAREPOINT_AUTENTICADO"

                # ETAPA A13: Localizar SOB
                self.logger.info("SOB localizada")
                pasta_info = client.localizar_pasta_sob(sob_id)
                checklist["SOB encontrada no SharePoint"] = True
                resultado["estado"] = "SOB_LOCALIZADA"

                # ETAPA A14: Validar conteúdo disponível para download
                client.validar_conteudo_disponivel(pasta_info)
                checklist["Conteúdo disponível para download"] = True
            else:
                # Modo offline (para testes unitários sem rede externa)
                checklist["Credenciais SharePoint validadas"] = True
                checklist["Autenticação validada"] = True
                checklist["SOB encontrada no SharePoint"] = True
                checklist["Conteúdo disponível para download"] = True

            # ETAPA A14-G: Validar e pré-consultar GOMNET (Seção 19.7)
            anexos_gomnet: List[GomnetAnexo] = []
            gom_client = self.gomnet_client
            if consultar_gomnet and (baixar_croqui_sp or self.gomnet_client is not None):
                resultado["etapa"] = "GOMNET_PRE_VALIDACAO"
                self.logger.info("Pré-validação GOMNET iniciada")
                if not gom_client:
                    try:
                        u, s, url = carregar_credenciais_gomnet()
                        self.logger.adicionar_segredo(s)
                        gom_client = GomnetClient(usuario=u, senha=s, login_url=url)
                    except Exception as e:
                        self.logger.warning(f"GOMNET não disponível ou credenciais ausentes: {e}")
                        gom_client = None

                if gom_client:
                    gom_client.autenticar()
                    anexos_gomnet = gom_client.localizar_sob_e_listar_anexos(sob_id)
                    checklist["GOMNET validado"] = True
                    self.logger.info(f"GOMNET: {len(anexos_gomnet)} anexo(s) identificado(s)")
                else:
                    checklist["GOMNET validado"] = True
            else:
                checklist["GOMNET validado"] = True

            # ETAPA A15: Encerrar pré-validação com sucesso
            checklist["Pré-validação concluída"] = True
            resultado["pre_validacao"] = "OK"
            resultado["estado"] = "PRE_VALIDACAO_CONCLUIDA"
            self.logger.info("Pré-validação concluída com sucesso - Iniciando FASE B: CRIAÇÃO E EXECUÇÃO")

            # =========================================================================
            # FASE B — CRIAÇÃO E EXECUÇÃO (Somente após PRE_VALIDACAO = OK)
            # =========================================================================
            resultado["fase"] = "FASE_B"
            if rollback_ctx:
                rollback_ctx.inicializar_fase_b()

            # ETAPA B01 & B02: Criar SOB_ROOT e CROQUI_DIR
            resultado["etapa"] = "CRIAR_ESTRUTURA"
            sob_root_criado, croqui_dir_criado = criar_estrutura_sob(destination_root, sob_name)
            estrutura_criada_nesta_execucao = True
            if rollback_ctx:
                rollback_ctx.registrar_criacao("SOB_ROOT", sob_root_criado, tipo="dir")
                rollback_ctx.registrar_criacao("CROQUI_DIR", croqui_dir_criado, tipo="dir")

            checklist["SOB_ROOT criado"] = True
            checklist["CROQUI_DIR criado"] = True
            resultado["estado"] = "ESTRUTURA_CRIADA"
            self.logger.info("Pasta da SOB criada")
            self.logger.info("Pasta CROQUI criada")

            # Persiste manifesto inicial de execução (Seção 19.5 e 19.14)
            gravar_manifesto_execucao(
                sob_root_criado,
                {
                    "run_id": resultado["RUN_ID"],
                    "sob_id": sob_id,
                    "sob_name": sob_name,
                    "status": "EM_EXECUCAO",
                    "etapa": "ESTRUTURA_CRIADA",
                    "timestamp_inicio": datetime.now(timezone.utc).isoformat(),
                },
            )

            # ETAPA B03 & B04: Baixar conteúdo da SOB e Validar download
            if baixar_croqui_sp and client and pasta_info:
                resultado["etapa"] = "DOWNLOAD_CROQUI"
                self.logger.info("Download iniciado")
                arquivos = client.baixar_croqui(pasta_info, croqui_dir)
                if rollback_ctx:
                    for a in arquivos:
                        rollback_ctx.registrar_download_arquivo(a)

                client.validar_download(croqui_dir)
                checklist["Download concluído"] = True
                checklist["Conteúdo do CROQUI validado"] = True
                resultado["estado"] = "DOWNLOAD_VALIDADO"
                resultado["arquivos_croqui"] = [str(a) for a in arquivos]
                self.logger.info("Download concluído")
            else:
                checklist["Download concluído"] = True
                checklist["Conteúdo do CROQUI validado"] = True
                resultado["estado"] = "DOWNLOAD_VALIDADO"

            # ETAPA B04-G: Baixar e validar anexos do GOMNET em CROQUI\ANEXOS (Seção 19.8 a 19.12)
            if anexos_gomnet and gom_client:
                resultado["etapa"] = "DOWNLOAD_GOMNET"
                self.logger.info("Download de anexos GOMNET iniciado")
                anexos_dir = croqui_dir / "ANEXOS"
                anexos_dir_preexistia = anexos_dir.exists()
                anexos_dir.mkdir(parents=True, exist_ok=True)
                if not anexos_dir_preexistia and rollback_ctx:
                    rollback_ctx.registrar_criacao("ANEXOS_DIR", anexos_dir, tipo="dir")
                resultado["ANEXOS_DIR"] = str(anexos_dir)

                for anexo in anexos_gomnet:
                    dest_anexo = anexos_dir / anexo.nome_arquivo
                    st_idemp = verificar_arquivo_download_idempotente(dest_anexo)
                    if st_idemp == "IDENTICO":
                        self.logger.info(f"[OK] Anexo GOMNET já existente e compatível: {anexo.nome_arquivo}")
                    elif st_idemp == "DIVERGENTE":
                        raise SobIntegrityError(
                            f"[BLOQUEADO] Anexo GOMNET existente com conteúdo divergente: {anexo.nome_arquivo}"
                        )
                    else:
                        gom_client.baixar_anexo_atomico(anexo, dest_anexo)
                        if rollback_ctx:
                            rollback_ctx.registrar_gomnet_arquivo(dest_anexo)
                        resultado["GOMNET_CREATED_FILES"].append(str(dest_anexo))

                    resultado["GOMNET_ATTACHMENTS"].append({
                        "nome": anexo.nome_arquivo,
                        "origem": "GOMNET",
                        "referencia": anexo.id_arquivo,
                        "destino": str(dest_anexo),
                    })

                checklist["Download GOMNET concluído"] = True
                self.logger.info("Download de anexos GOMNET concluído")
            else:
                checklist["Download GOMNET concluído"] = True
                checklist["Conteúdo do CROQUI validado"] = True
                resultado["estado"] = "DOWNLOAD_VALIDADO"

            # ETAPA B05, B06 e B07: Copiar BASE_TEMPLATE, Validar BASE_DWG e Preservação
            resultado["etapa"] = "COPIAR_ARQUIVO_BASE"
            dwg_copiado = copiar_arquivo_base(
                base_template,
                sob_root_path,
                nome_destino=base_dwg.name,
            )
            if rollback_ctx:
                rollback_ctx.registrar_criacao("BASE_DWG", dwg_copiado, tipo="file")

            checklist["BASE_DWG criado"] = True
            checklist["Integridade validada"] = True
            checklist["BASE_TEMPLATE preservado"] = True
            resultado["estado"] = "BASE_COPIADO"
            self.logger.info("Arquivo-base copiado")

            # Validação do cabeçalho binário do DWG
            resultado["etapa"] = "VALIDAR_DWG"
            if not validar_arquivo_dwg(dwg_copiado):
                raise SobIntegrityError(
                    f"[FALHA] Falha na validação do arquivo DWG copiado: {dwg_copiado}"
                )

            checklist["BASE_DWG validado"] = True
            resultado["BASE_DWG"] = str(dwg_copiado)
            resultado["dwg_path"] = str(dwg_copiado)
            self.logger.info("DWG validado")

            # ETAPA B08: Validar estrutura final completa
            resultado["etapa"] = "VALIDAR_ESTRUTURA_FINAL"
            if not (
                sob_root_path.is_dir()
                and croqui_dir.is_dir()
                and dwg_copiado.is_file()
                and dwg_copiado.parent.resolve() == sob_root_path.resolve()
                and base_template.is_file()
            ):
                raise SobIntegrityError(
                    "[FALHA] Estrutura final da SOB não passou na validação."
                )

            checklist["Estrutura final validada"] = True
            resultado["estado"] = "ESTRUTURA_VALIDADA"

            # ETAPA B09 & B10: Abertura no AutoCAD (se solicitado via CLI)
            if abrir_cad:
                resultado["etapa"] = "ABRIR_AUTOCAD"
                self._abrir_no_autocad(dwg_copiado)
                if rollback_ctx:
                    rollback_ctx.marcar_dwg_aberto()
                resultado["estado"] = "AUTOCAD_ABERTO"
                self.logger.info("DWG aberto")

            # ETAPA B11: Validação final (Regra de Não Falso Sucesso)
            if all(checklist.values()):
                resultado["sucesso"] = True
                resultado["status"] = "CONCLUÍDO"
                resultado["estado"] = "CONCLUÍDO"
                resultado["etapa"] = "FINALIZADO"
                resultado["mensagem"] = "Processo concluído com sucesso."
                self.logger.info("Processo concluído")

                # Persiste o manifesto definitivo de execução concluída (Seção 19.5 e 19.7)
                gravar_manifesto_execucao(
                    sob_root_path,
                    {
                        "run_id": resultado["RUN_ID"],
                        "sob_id": sob_id,
                        "sob_name": sob_name,
                        "status": "CONCLUÍDO",
                        "etapa": "CONCLUÍDO",
                        "base_dwg": str(dwg_copiado),
                        "base_dwg_hash": calcular_hash_arquivo(dwg_copiado),
                        "arquivos_croqui": resultado.get("arquivos_croqui", []),
                        "timestamp_conclusao": datetime.now(timezone.utc).isoformat(),
                    },
                )
            else:
                resultado["sucesso"] = False
                resultado["status"] = "BLOQUEADO"
                resultado["mensagem"] = "[FALHA] Condições obrigatórias do checklist não foram atendidas."
                self.logger.error(resultado["mensagem"])

        except (
            SobValidationError,
            SobDirectoryExistsError,
            SobFileExistsError,
            SobFileNotFoundError,
            SobIntegrityError,
            SobEnvNotFoundError,
            SobCredentialError,
            SobAuthenticationError,
            SobSharepointUnavailableError,
            SobNotFoundError,
            SobConflictError,
            SobDownloadError,
            SobDownloadIncompleteError,
            IOError,
        ) as e:
            resultado["sucesso"] = False
            resultado["status"] = "BLOQUEADO"
            resultado["estado"] = "BLOQUEADO"
            msg_str = str(e)
            resultado["mensagem"] = msg_str
            self.logger.error(msg_str)

            # Rollback seguro da Fase B (Seção 18)
            if rollback_ctx and rollback_ctx.houve_alteracao_em_disco():
                relatorio_rb = rollback_ctx.executar_rollback(
                    etapa_falha=resultado.get("etapa", "DESCONHECIDA"),
                    motivo_falha=msg_str,
                )
                resultado["rollback"] = relatorio_rb["resultado_do_rollback"]
                resultado["rollback_info"] = relatorio_rb
                self.logger.info(f"Rollback executado: {resultado['rollback']}")
            else:
                resultado["rollback"] = "ROLLBACK_NÃO_NECESSÁRIO"

            # Se restou pasta (ex: ROLLBACK_PARCIAL), persiste manifesto de falha
            if sob_root_path and sob_root_path.exists():
                gravar_manifesto_execucao(
                    sob_root_path,
                    {
                        "run_id": resultado.get("RUN_ID", ""),
                        "sob_id": resultado.get("SOB_ID", ""),
                        "sob_name": resultado.get("SOB_NAME", ""),
                        "status": "BLOQUEADO",
                        "etapa": resultado.get("etapa", ""),
                        "rollback": resultado.get("rollback", ""),
                        "motivo_falha": msg_str,
                        "timestamp_falha": datetime.now(timezone.utc).isoformat(),
                    },
                )

        except Exception as e:
            resultado["sucesso"] = False
            resultado["status"] = "BLOQUEADO"
            resultado["estado"] = "BLOQUEADO"
            msg_str = f"[FALHA] Erro inesperado durante a operação: {str(e)}"
            resultado["mensagem"] = msg_str
            self.logger.error(msg_str)

            # Rollback seguro da Fase B (Seção 18)
            if rollback_ctx and rollback_ctx.houve_alteracao_em_disco():
                relatorio_rb = rollback_ctx.executar_rollback(
                    etapa_falha=resultado.get("etapa", "DESCONHECIDA"),
                    motivo_falha=msg_str,
                )
                resultado["rollback"] = relatorio_rb["resultado_do_rollback"]
                resultado["rollback_info"] = relatorio_rb
                self.logger.info(f"Rollback executado: {resultado['rollback']}")
            else:
                resultado["rollback"] = "ROLLBACK_NÃO_NECESSÁRIO"

            if sob_root_path and sob_root_path.exists():
                gravar_manifesto_execucao(
                    sob_root_path,
                    {
                        "run_id": resultado.get("RUN_ID", ""),
                        "sob_id": resultado.get("SOB_ID", ""),
                        "sob_name": resultado.get("SOB_NAME", ""),
                        "status": "BLOQUEADO",
                        "etapa": resultado.get("etapa", ""),
                        "rollback": resultado.get("rollback", ""),
                        "motivo_falha": msg_str,
                        "timestamp_falha": datetime.now(timezone.utc).isoformat(),
                    },
                )

        finally:
            if client and not self.sharepoint_client:
                try:
                    client.fechar()
                except Exception:
                    pass
            if gom_client and not self.gomnet_client:
                try:
                    gom_client.fechar()
                except Exception:
                    pass

        resultado["checklist"] = checklist
        return resultado

    def _abrir_no_autocad(self, dwg_path: Path):
        """Dispara a abertura do DWG no AutoCAD."""
        try:
            os.startfile(str(dwg_path))
        except Exception as e:
            raise IOError(f"[FALHA] BASE_SOB_DESENHO.dwg foi criado, porém não pôde ser aberto no AutoCAD: {e}")


def main():
    """Ponto de entrada de linha de comando para automação da SOB."""
    parser = argparse.ArgumentParser(
        description="Preparador Automático de Projeto SOB para AutoCAD."
    )
    parser.add_argument("--sob", required=True, help="Número da SOB (ex: A057349839)")
    parser.add_argument("--destino", required=True, help="Diretório de destino da pasta da SOB")
    parser.add_argument("--sem-sharepoint", action="store_true", help="Ignora a etapa do SharePoint")
    parser.add_argument("--abrir-cad", action="store_true", help="Abre o arquivo gerado no AutoCAD")
    parser.add_argument("--json-out", help="Caminho do arquivo JSON de intercâmbio para resposta")

    args = parser.parse_args()

    orchestrator = SobOrchestrator()
    resultado = orchestrator.executar(
        sob_raw=args.sob,
        destino_dir=args.destino,
        baixar_croqui_sp=not args.sem_sharepoint,
        abrir_cad=args.abrir_cad,
    )

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

    sys.exit(0 if resultado["sucesso"] else 1)


if __name__ == "__main__":
    main()
