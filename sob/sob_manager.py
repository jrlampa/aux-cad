# -*- coding: utf-8 -*-
"""
Orquestrador Principal do Módulo SOB (sob_manager.py).
Responsabilidade única: Coordenação do fluxo de preparação da SOB,
emissão de logs de diagnóstico, tratamento de erros e interface CLI/JSON para o AutoCAD.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

_current_dir = str(Path(__file__).resolve().parent)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from sob_core import (
    obter_sob_id,
    obter_sob_name,
    derivar_caminhos_sob,
    validar_permissao_criacao,
    criar_estrutura_sob,
    copiar_arquivo_base,
    validar_arquivo_dwg,
    calcular_hash_arquivo,
    SobValidationError,
    SobCancellationRequestedError,
    SobPermissionError,
    SobDirectoryExistsError,
    SobFileExistsError,
    SobFileNotFoundError,
    SobIntegrityError,
    SobConflictError,
)
from sob_rollback import RollbackContext
from sob_idempotencia import (
    gerar_run_id,
    gravar_manifesto_execucao,
    classificar_sob_root,
)
from sob_gomnet import (
    GomnetClient,
    GomnetAnexo,
    carregar_credenciais_gomnet,
    baixar_anexos_gomnet_fase_b,
)
from sob_sharepoint import (
    obter_credenciais_sharepoint,
    SharePointClient,
    SobEnvNotFoundError,
    SobCredentialError,
    SobAuthenticationError,
    SobSharepointUnavailableError,
    SobNotFoundError,
    SobDownloadError,
    SobDownloadIncompleteError,
)

from sob_logger import (
    LoggerSeguro,
    configurar_logger,
    formatar_mensagem_erro,
)
from sob_fallback_manual import (
    executar_fallback_intervencao_manual,
    copiar_arquivos_manuais_para_croqui,
)

# Caminho padrão do arquivo-base prancha.dwg
CAMINHO_BASE_PRANCHA_PADRAO = (
    Path(__file__).resolve().parent.parent / "modelos" / "prancha.dwg"
)


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

    def _notificar_progresso(
        self,
        cb: Any,
        etapa: str,
        desc: str,
        num: int = 1,
        total: int = 12,
        perc: Optional[float] = None,
        estado: str = "EM_EXECUCAO",
    ):
        if not cb:
            return
        try:
            if hasattr(cb, "notificar"):
                cb.notificar(etapa=etapa, descricao=desc, etapa_num=num, total_etapas=total, percentual=perc, estado=estado)
            elif callable(cb):
                cb({"etapa": etapa, "descricao": desc, "etapa_num": num, "total_etapas": total, "percentual": perc, "estado": estado})
        except Exception:
            pass

    def _checar_cancelamento(self, verificador: Any):
        if not verificador:
            return
        cancelado = False
        try:
            if hasattr(verificador, "cancelamento_solicitado"):
                cancelado = verificador.cancelamento_solicitado()
            elif callable(verificador):
                cancelado = verificador()
        except Exception:
            pass
        if cancelado:
            raise SobCancellationRequestedError("[CANCELADO] Operação cancelada pelo usuário.")

    def _perguntar_decisao_sharepoint(
        self,
        erro: Exception,
        callback_progresso: Optional[Any],
        etapa: str,
        continuar_em_falha: Optional[bool] = None,
    ) -> bool:
        """
        Pergunta ao usuário se deseja ignorar a falha do SharePoint e continuar
        (uma vez que a preparação local já foi realizada com sucesso) ou cancelar e fazer rollback.
        Retorna True para IGNORAR E CONTINUAR, ou False para CANCELAR E FAZER ROLLBACK.
        """
        if continuar_em_falha is not None:
            return bool(continuar_em_falha)

        dados = {
            "tipo": "ERRO_SHAREPOINT",
            "motivo": "ERRO_ACESSO_SHAREPOINT",
            "erro": str(erro),
            "etapa": etapa,
            "mensagem": (
                f"Erro na consulta ao SharePoint ({etapa}): {erro}\n"
                "A preparação local (pastas e modelo DWG) já foi realizada com sucesso."
            ),
        }

        # 1. Callback com método dedicado perguntar_continuar_sem_sharepoint
        if callback_progresso and hasattr(callback_progresso, "perguntar_continuar_sem_sharepoint"):
            return bool(callback_progresso.perguntar_continuar_sem_sharepoint(dados))

        # 2. Callback com aguardar_intervencao genérico
        if callback_progresso and hasattr(callback_progresso, "aguardar_intervencao"):
            res = callback_progresso.aguardar_intervencao(dados)
            if isinstance(res, bool):
                return res
            if isinstance(res, dict):
                return bool(res.get("continuar_sem_sharepoint", res.get("ignorar", False)))
            if isinstance(res, str):
                return res.strip().lower() in ("sim", "s", "true", "continuar", "ignorar")
            return False

        # 3. Terminal interativo (CLI)
        if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            try:
                print(f"\n[SHAREPOINT] Falha na consulta ({etapa}): {erro}")
                print("A preparação local já foi realizada com sucesso.")
                resp = input("Deseja IGNORAR e continuar? (S/N) [N]: ")
                return resp.strip().lower() in ("s", "sim", "y", "yes", "ignorar")
            except Exception:
                return False

        return False

    def _perguntar_decisao_gomnet(
        self,
        erro: Exception,
        callback_progresso: Optional[Any],
        etapa: str,
        continuar_em_falha: Optional[bool] = None,
    ) -> bool:
        """
        Pergunta ao usuário se deseja continuar a preparação da SOB sem o fluxo do GOMNET ou fazer rollback.
        Retorna True para continuar sem GOMNET, ou False para realizar rollback.
        """
        if continuar_em_falha is not None:
            return bool(continuar_em_falha)

        dados = {
            "tipo": "ERRO_GOMNET",
            "motivo": "ERRO_ACESSO_GOMNET",
            "erro": str(erro),
            "etapa": etapa,
            "mensagem": f"Erro ao acessar o GOMNET ({etapa}): {erro}",
        }

        # 1. Callback com método dedicado perguntar_continuar_sem_gomnet
        if callback_progresso and hasattr(callback_progresso, "perguntar_continuar_sem_gomnet"):
            return bool(callback_progresso.perguntar_continuar_sem_gomnet(dados))

        # 2. Callback com aguardar_intervencao genérico
        if callback_progresso and hasattr(callback_progresso, "aguardar_intervencao"):
            res = callback_progresso.aguardar_intervencao(dados)
            if isinstance(res, bool):
                return res
            if isinstance(res, dict):
                return bool(res.get("continuar_sem_gomnet", False))
            if isinstance(res, str):
                return res.strip().lower() in ("sim", "s", "true", "continuar")
            return False

        # 3. Terminal interativo (CLI)
        if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            try:
                print(f"\n[GOMNET] Erro ao acessar o GOMNET ({etapa}): {erro}")
                resp = input("Deseja continuar a preparação da SOB sem o fluxo do GOMNET? (S/N) [S]: ")
                return resp.strip().lower() in ("", "s", "sim", "y", "yes")
            except Exception:
                return False

        return False

    def _tratar_falha(
        self,
        e: Exception,
        msg_str: str,
        rollback_ctx: Optional[RollbackContext],
        sob_root_path: Optional[Path],
        resultado: Dict[str, Any],
        callback_progresso: Optional[Any],
    ):
        resultado["sucesso"] = False
        resultado["status"] = "BLOQUEADO"
        resultado["estado"] = "BLOQUEADO"
        resultado["mensagem"] = msg_str
        self.logger.error(msg_str)

        if rollback_ctx and rollback_ctx.houve_alteracao_em_disco():
            resultado["dwg_path"] = ""
            resultado["estado"] = "ROLLBACK_EM_EXECUCAO"
            self._notificar_progresso(
                callback_progresso,
                "ROLLBACK_EM_EXECUCAO",
                "Executando reversão dos recursos criados...",
                12,
                estado="ROLLBACK_EM_EXECUCAO",
            )
            relatorio_rb = rollback_ctx.executar_rollback(
                etapa_falha=resultado.get("etapa", "DESCONHECIDA"),
                motivo_falha=msg_str,
            )
            resultado["rollback"] = relatorio_rb["resultado_do_rollback"]
            resultado["rollback_info"] = relatorio_rb
            self.logger.info(f"Rollback executado: {resultado['rollback']}")
            st_rb = "ROLLBACK_CONCLUIDO" if resultado["rollback"] == "ROLLBACK_CONCLUÍDO" else "ROLLBACK_PARCIAL"
            resultado["estado"] = st_rb
            self._notificar_progresso(
                callback_progresso,
                st_rb,
                f"Reversão finalizada: {resultado['rollback']}",
                12,
                estado=st_rb,
            )
        else:
            resultado["rollback"] = "ROLLBACK_NÃO_NECESSÁRIO"
            st_blq = "CANCELAMENTO" if isinstance(e, SobCancellationRequestedError) else "BLOQUEADO"
            self._notificar_progresso(
                callback_progresso,
                st_blq,
                msg_str,
                12,
                estado=st_blq,
            )

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

    def executar(
        self,
        sob_raw: str,
        destino_dir: str,
        base: Optional[str] = "PE",
        baixar_croqui_sp: bool = True,
        consultar_gomnet: bool = True,
        abrir_cad: bool = False,
        callback_progresso: Optional[Any] = None,
        verificador_cancelamento: Optional[Any] = None,
        continuar_sem_gomnet_em_falha: Optional[bool] = None,
        continuar_sem_sharepoint_em_falha: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Executa o fluxo completo da SOB de acordo com as regras de negócio e validações da Seção 14.
        Garante a ordem estrita: Preparação Local -> SharePoint -> GOMNET.
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
        arquivos_manuais_validados: List[Path] = []

        try:
            self.logger.info("Início da operação - FASE A: PRÉ-VALIDAÇÃO")
            self._notificar_progresso(callback_progresso, "INICIANDO", "Iniciando preparação do projeto...", 1)
            self._checar_cancelamento(verificador_cancelamento or callback_progresso)

            # =========================================================================
            # FASE A — PRÉ-VALIDAÇÃO (Não cria, não copia e não baixa nada)
            # =========================================================================

            # ETAPA A02 & A03: Normalizar e validar SOB
            resultado["estado"] = "INICIANDO"
            resultado["etapa"] = "VALIDAR_SOB"
            self._notificar_progresso(callback_progresso, "VALIDAR_SOB", "Validando formato e identificador da SOB...", 2)
            self._checar_cancelamento(verificador_cancelamento or callback_progresso)

            if not sob_raw or not str(sob_raw).strip():
                raise SobValidationError("[FALHA] Número da SOB inválido.")

            sob_id = obter_sob_id(sob_raw)
            checklist["SOB_ID válido"] = True

            sob_name = obter_sob_name(sob_raw)
            checklist["SOB_NAME válido"] = True
            resultado["estado"] = "SOB_VALIDADA"

            # ETAPA A04 & A05: Selecionar e Validar DESTINATION_ROOT
            resultado["etapa"] = "VALIDAR_DESTINO"
            self._notificar_progresso(callback_progresso, "VALIDAR_DESTINO", "Validando diretório de destino...", 3)
            self._checar_cancelamento(verificador_cancelamento or callback_progresso)
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
            caminhos = derivar_caminhos_sob(sob_raw, destination_root, self.origem_base, base=base)
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
            resultado["BASE"] = caminhos.get("BASE_SIGLA", "PE")
            resultado["NOME_BASE_DWG"] = caminhos.get("NOME_BASE_DWG", base_dwg.name)
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
            self._notificar_progresso(callback_progresso, "VALIDAR_BASE_TEMPLATE", "Validando modelo de desenho DWG...", 4)
            self._checar_cancelamento(verificador_cancelamento or callback_progresso)
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

            # ETAPA A15: Encerrar pré-validação preliminar com sucesso
            checklist["Pré-validação concluída"] = True
            resultado["pre_validacao"] = "OK"

            # =========================================================================
            # FASE 1 — PREPARAÇÃO LOCAL (Pastas, Cópia dos Modelos, Renomeação e Validação)
            # =========================================================================
            resultado["fase"] = "PREPARACAO_LOCAL"
            resultado["estado"] = "PREPARANDO_LOCAL"
            resultado["etapa"] = "CRIAR_ESTRUTURA"
            self._notificar_progresso(callback_progresso, "PREPARANDO_LOCAL", "Criando pastas locais do projeto...", 5)
            self._checar_cancelamento(verificador_cancelamento or callback_progresso)

            if rollback_ctx:
                rollback_ctx.inicializar_fase_b()

            # Criação de diretórios locais: SOB_ROOT e CROQUI_DIR
            sob_root_criado, croqui_dir_criado = criar_estrutura_sob(destination_root, sob_name)
            estrutura_criada_nesta_execucao = True
            if rollback_ctx:
                rollback_ctx.registrar_criacao("SOB_ROOT", sob_root_criado, tipo="dir")
                rollback_ctx.registrar_criacao("CROQUI_DIR", croqui_dir_criado, tipo="dir")

            checklist["SOB_ROOT criado"] = True
            checklist["CROQUI_DIR criado"] = True
            self.logger.info("Pasta da SOB criada")
            self.logger.info("Pasta CROQUI criada")

            # Grava manifesto inicial de execução em andamento (Seção 19.5)
            if not gravar_manifesto_execucao(
                sob_root_criado,
                {
                    "run_id": resultado["RUN_ID"],
                    "sob_id": sob_id,
                    "sob_name": sob_name,
                    "status": "EM_EXECUCAO",
                    "etapa": "PREPARANDO_LOCAL",
                    "timestamp_inicio": datetime.now(timezone.utc).isoformat(),
                },
            ):
                raise IOError("Manifesto inicial SOB não persistido.")

            # Cópia do arquivo-modelo BASE_TEMPLATE e renomeação para BASE_DWG
            resultado["etapa"] = "CRIAR_BASE_DWG"
            self._notificar_progresso(callback_progresso, "CRIAR_BASE_DWG", f"Copiando modelo para {base_dwg.name}...", 6)
            self._checar_cancelamento(verificador_cancelamento or callback_progresso)
            dwg_copiado = copiar_arquivo_base(
                base_template,
                sob_root_path,
                nome_destino=base_dwg.name,
            )
            if rollback_ctx:
                rollback_ctx.registrar_criacao("BASE_DWG", dwg_copiado, tipo="file")

            self._checar_cancelamento(verificador_cancelamento or callback_progresso)

            checklist["BASE_DWG criado"] = True
            checklist["Integridade validada"] = True
            checklist["BASE_TEMPLATE preservado"] = True
            self.logger.info("Arquivo-base copiado e renomeado")

            # Validação do cabeçalho binário do DWG
            resultado["etapa"] = "VALIDAR_DWG"
            if not validar_arquivo_dwg(dwg_copiado):
                raise SobIntegrityError(
                    f"[FALHA] Falha na validação do arquivo DWG copiado: {dwg_copiado}"
                )

            checklist["BASE_DWG validado"] = True
            resultado["BASE_DWG"] = str(dwg_copiado)
            resultado["dwg_path"] = str(dwg_copiado)

            # Validação da estrutura local
            if not (
                sob_root_path.is_dir()
                and croqui_dir.is_dir()
                and dwg_copiado.is_file()
                and dwg_copiado.parent.resolve() == sob_root_path.resolve()
                and base_template.is_file()
            ):
                raise SobIntegrityError(
                    "[FALHA] Estrutura local da SOB não passou na validação."
                )

            checklist["Estrutura final validada"] = True
            resultado["estado"] = "LOCAL_PREPARADO"
            resultado["etapa"] = "LOCAL_PREPARADO"
            self.logger.info("Estrutura local preparada e validada com sucesso")

            # Grava manifesto intermediário de estrutura local preparada
            if not gravar_manifesto_execucao(
                sob_root_criado,
                {
                    "run_id": resultado["RUN_ID"],
                    "sob_id": sob_id,
                    "sob_name": sob_name,
                    "status": "LOCAL_PREPARADO",
                    "etapa": "LOCAL_PREPARADO",
                    "base_dwg": str(dwg_copiado),
                    "timestamp_inicio": datetime.now(timezone.utc).isoformat(),
                },
            ):
                raise IOError("Manifesto inicial SOB não persistido.")

            # =========================================================================
            # FASE 2 — CONSULTA E DOWNLOAD DO SHAREPOINT (Somente após LOCAL_PREPARADO)
            # =========================================================================
            if baixar_croqui_sp:
                resultado["estado"] = "SHAREPOINT_PENDENTE"
                resultado["etapa"] = "SHAREPOINT_CONSULTA"
                self.logger.info("Iniciando consulta ao SharePoint corporativo...")
                self._notificar_progresso(callback_progresso, "SHAREPOINT_CONSULTA", "Consultando SharePoint corporativo...", 7)
                self._checar_cancelamento(verificador_cancelamento or callback_progresso)

                client = self.sharepoint_client
                if not client:
                    login, senha = obter_credenciais_sharepoint()
                    self.logger.adicionar_segredo(senha)
                    client = SharePointClient(login=login, senha=senha, headless=True, logger=self.logger)

                try:
                    checklist["Credenciais SharePoint validadas"] = True
                    client.autenticar()
                    checklist["Autenticação validada"] = True

                    try:
                        pasta_info = client.localizar_pasta_sob(sob_id)
                        checklist["SOB encontrada no SharePoint"] = True
                        client.validar_conteudo_disponivel(pasta_info)
                        checklist["Conteúdo disponível para download"] = True
                    except (SobConflictError, SobNotFoundError) as e_loc:
                        ocorrencias = getattr(e_loc, "ocorrencias", [])
                        url_b = getattr(e_loc, "url_busca", "")
                        motivo = "MÚLTIPLAS_OCORRÊNCIAS_SHAREPOINT" if isinstance(e_loc, SobConflictError) else "SOB_NÃO_ENCONTRADA_SHAREPOINT"
                        res_fb = executar_fallback_intervencao_manual(
                            sob_id=sob_id,
                            ocorrencias=ocorrencias,
                            url_busca=url_b,
                            callback_progresso=callback_progresso,
                            logger=self.logger,
                            motivo=motivo,
                        )
                        if res_fb.get("url_sharepoint"):
                            url_sp = res_fb["url_sharepoint"]
                            pasta_info = {"tipo": "url_direta", "url": url_sp, "sob": sob_id}
                            resultado["CROQUI"] = "DOWNLOAD_AUTOMATICO_POR_LINK"
                            checklist["SOB encontrada no SharePoint"] = True
                            checklist["Conteúdo disponível para download"] = True
                        elif res_fb.get("sem_croqui"):
                            pasta_info = None
                            resultado["CROQUI"] = "SEM_ARQUIVOS"
                            arquivos_manuais_validados = []
                            checklist["SOB encontrada no SharePoint"] = True
                            checklist["Conteúdo disponível para download"] = True
                        elif res_fb.get("arquivos"):
                            pasta_info = None
                            resultado["CROQUI"] = "DOWNLOAD_MANUAL_VALIDADO"
                            arquivos_manuais_validados = res_fb.get("arquivos", [])
                            checklist["SOB encontrada no SharePoint"] = True
                            checklist["Conteúdo disponível para download"] = True
                        else:
                            raise e_loc

                    # Download do conteúdo do croqui
                    if arquivos_manuais_validados:
                        arqs_copiados = copiar_arquivos_manuais_para_croqui(arquivos_manuais_validados, croqui_dir)
                        if rollback_ctx:
                            for a in arqs_copiados:
                                rollback_ctx.registrar_download_arquivo(a)
                        checklist["Download concluído"] = True
                        checklist["Conteúdo do CROQUI validado"] = True
                        resultado["arquivos_croqui"] = [str(a) for a in arqs_copiados]
                    elif resultado.get("CROQUI") == "SEM_ARQUIVOS":
                        checklist["Download concluído"] = True
                        checklist["Conteúdo do CROQUI validado"] = True
                        resultado["arquivos_croqui"] = []
                    elif pasta_info:
                        arqs = client.baixar_croqui(pasta_info, croqui_dir)
                        if rollback_ctx:
                            for a in arqs:
                                rollback_ctx.registrar_download_arquivo(a)
                        client.validar_download(croqui_dir)
                        checklist["Download concluído"] = True
                        checklist["Conteúdo do CROQUI validado"] = True
                        resultado["arquivos_croqui"] = [str(a) for a in arqs]
                    else:
                        checklist["Download concluído"] = True
                        checklist["Conteúdo do CROQUI validado"] = True

                    resultado["estado"] = "SHAREPOINT_CONCLUIDO"
                    self.logger.info("Consulta e download SharePoint concluídos com sucesso")

                except Exception as e_sp:
                    if isinstance(e_sp, SobCancellationRequestedError):
                        self.logger.info("Cancelamento solicitado pelo usuário no SharePoint.")
                        raise e_sp
                    self.logger.warning(f"Falha na consulta ao SharePoint: {e_sp}")
                    if self._perguntar_decisao_sharepoint(e_sp, callback_progresso, "SHAREPOINT_CONSULTA", continuar_sem_sharepoint_em_falha):
                        self.logger.info("Usuário optou por IGNORAR a falha do SharePoint e continuar com a estrutura local.")
                        checklist["Credenciais SharePoint validadas"] = True
                        checklist["Autenticação validada"] = True
                        checklist["SOB encontrada no SharePoint"] = True
                        checklist["Conteúdo disponível para download"] = True
                        checklist["Download concluído"] = True
                        checklist["Conteúdo do CROQUI validado"] = True
                        resultado["estado"] = "SHAREPOINT_IGNORADO"
                        resultado["SHAREPOINT_IGNORADO"] = True
                        resultado["aviso_sharepoint"] = f"SharePoint ignorado a pedido do usuário: {e_sp}"
                    else:
                        self.logger.info("Usuário optou por CANCELAR e executar rollback devido a erro no SharePoint.")
                        raise e_sp
            else:
                # Modo offline
                checklist["Credenciais SharePoint validadas"] = True
                checklist["Autenticação validada"] = True
                checklist["SOB encontrada no SharePoint"] = True
                checklist["Conteúdo disponível para download"] = True
                checklist["Download concluído"] = True
                checklist["Conteúdo do CROQUI validado"] = True
                resultado["arquivos_croqui"] = []

            # =========================================================================
            # FASE 3 — CONSULTA E DOWNLOAD DO GOMNET (Somente após SharePoint)
            # =========================================================================
            anexos_gomnet: List[GomnetAnexo] = []
            gom_client = self.gomnet_client
            if consultar_gomnet and (self.gomnet_client is not None or (baixar_croqui_sp and self.sharepoint_client is None)):
                resultado["estado"] = "GOMNET_PENDENTE"
                resultado["etapa"] = "GOMNET_CONSULTA"
                self.logger.info("Iniciando consulta ao GOMNET...")
                self._notificar_progresso(callback_progresso, "GOMNET_CONSULTA", "Consultando GOMNET...", 9)
                self._checar_cancelamento(verificador_cancelamento or callback_progresso)

                if not gom_client:
                    try:
                        u, s, url = carregar_credenciais_gomnet()
                        self.logger.adicionar_segredo(s)
                        gom_client = GomnetClient(usuario=u, senha=s, login_url=url)
                    except Exception as e:
                        self.logger.warning(f"GOMNET não disponível ou credenciais ausentes: {e}")
                        gom_client = None

                if gom_client:
                    try:
                        gom_client.autenticar()
                        self._notificar_progresso(callback_progresso, "GOMNET_CONSULTAR", "Consultando modal de anexos da SOB no GOMNET...", 10)
                        self._checar_cancelamento(verificador_cancelamento or callback_progresso)
                        anexos_gomnet = gom_client.localizar_sob_e_listar_anexos(sob_id)
                        checklist["GOMNET validado"] = True
                        self.logger.info(f"GOMNET: {len(anexos_gomnet)} anexo(s) identificado(s)")

                        if anexos_gomnet:
                            created_files, attach_info = baixar_anexos_gomnet_fase_b(
                                anexos_gomnet=anexos_gomnet,
                                gom_client=gom_client,
                                croqui_dir=croqui_dir,
                                rollback_ctx=rollback_ctx,
                                callback_progresso=callback_progresso,
                                checar_cancelamento_fn=lambda: self._checar_cancelamento(verificador_cancelamento or callback_progresso),
                                logger=self.logger,
                            )
                            resultado["ANEXOS_DIR"] = str(croqui_dir / "ANEXOS")
                            resultado["GOMNET_CREATED_FILES"].extend(created_files)
                            resultado["GOMNET_ATTACHMENTS"].extend(attach_info)

                        checklist["Download GOMNET concluído"] = True
                        resultado["estado"] = "GOMNET_CONCLUIDO"
                        self.logger.info("Download de anexos GOMNET concluído com sucesso")

                    except Exception as e_gom:
                        if isinstance(e_gom, SobCancellationRequestedError):
                            self.logger.info("Cancelamento solicitado pelo usuário no GOMNET.")
                            raise e_gom
                        self.logger.warning(f"Erro ao acessar o GOMNET: {e_gom}")
                        if self._perguntar_decisao_gomnet(e_gom, callback_progresso, "GOMNET_CONSULTA", continuar_sem_gomnet_em_falha):
                            self.logger.info("Usuário optou por IGNORAR a falha do GOMNET e continuar.")
                            checklist["GOMNET validado"] = True
                            checklist["Download GOMNET concluído"] = True
                            resultado["estado"] = "GOMNET_IGNORADO"
                            resultado["GOMNET_IGNORADO"] = True
                            resultado["GOMNET_DOWNLOAD_IGNORADO"] = True
                            resultado["aviso_gomnet"] = f"GOMNET ignorado a pedido do usuário: {e_gom}"
                        else:
                            self.logger.info("Usuário optou por CANCELAR e executar rollback devido a erro no GOMNET.")
                            raise e_gom
                else:
                    checklist["GOMNET validado"] = True
                    checklist["Download GOMNET concluído"] = True
            else:
                checklist["GOMNET validado"] = True
                checklist["Download GOMNET concluído"] = True

            # =========================================================================
            # FASE 4 — CONCLUSÃO E FINALIZAÇÃO
            # =========================================================================
            if abrir_cad:
                resultado["etapa"] = "ABRIR_AUTOCAD"
                self._abrir_no_autocad(dwg_copiado)
                if rollback_ctx:
                    rollback_ctx.marcar_dwg_aberto()
                resultado["estado"] = "AUTOCAD_ABERTO"
                self.logger.info("DWG aberto no AutoCAD")

            # ETAPA B11: Validação final (Regra de Não Falso Sucesso)
            if all(checklist.values()):
                # Persiste o manifesto definitivo de execução concluída (Seção 19.5 e 19.7)
                if not gravar_manifesto_execucao(
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
                ):
                    raise IOError("Manifesto final SOB não persistido.")

                resultado["sucesso"] = True
                resultado["status"] = "CONCLUÍDO"
                resultado["estado"] = "CONCLUÍDO"
                resultado["etapa"] = "FINALIZADO"
                resultado["mensagem"] = "Processo concluído com sucesso."
                self._notificar_progresso(callback_progresso, "CONCLUIDO", "Projeto preparado com sucesso!", 12, perc=100.0, estado="SUCESSO")
                self.logger.info("Processo concluído")

                # Inicialização do controle operacional de tempo do OXCAD para a nova SOB (OXCAD 0.5.0)
                try:
                    from workspace.workspace_time import inicializar_tempo_projeto
                    inicializar_tempo_projeto(
                        root_dir=sob_root_path,
                        sob_id=sob_id,
                        dwg_path=str(dwg_copiado),
                        iniciar_imediatamente=True,
                    )
                    self.logger.info("Apontamento operacional de tempo inicializado para a SOB")
                except Exception as ex_tempo:
                    self.logger.warning(f"Não foi possível inicializar apontamento de tempo: {ex_tempo}")
            else:
                resultado["sucesso"] = False
                resultado["status"] = "BLOQUEADO"
                resultado["mensagem"] = "[FALHA] Condições obrigatórias do checklist não foram atendidas."
                self.logger.error(resultado["mensagem"])

        except (
            SobValidationError, SobDirectoryExistsError, SobFileExistsError,
            SobFileNotFoundError, SobIntegrityError, SobEnvNotFoundError,
            SobCredentialError, SobAuthenticationError, SobSharepointUnavailableError,
            SobNotFoundError, SobConflictError, SobDownloadError,
            SobDownloadIncompleteError, IOError,
        ) as e:
            self._tratar_falha(e, str(e), rollback_ctx, sob_root_path, resultado, callback_progresso)

        except Exception as e:
            self._tratar_falha(
                e,
                f"[FALHA] Erro inesperado durante a operação: {str(e)}",
                rollback_ctx,
                sob_root_path,
                resultado,
                callback_progresso,
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


def main(args_list: Optional[list] = None):
    """Ponto de entrada de linha de comando para automação da SOB."""
    from sob_cli import main as cli_main

    cli_main(args_list)


if __name__ == "__main__":
    main()
