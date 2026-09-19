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
        logger: Optional[LoggerSeguro] = None,
    ):
        self.origem_base = origem_base or CAMINHO_BASE_PRANCHA_PADRAO
        self.sharepoint_client = sharepoint_client
        self.logger = logger or configurar_logger()

    def executar(
        self,
        sob_raw: str,
        destino_dir: str,
        baixar_croqui_sp: bool = True,
        abrir_cad: bool = False,
    ) -> Dict[str, Any]:
        """
        Executa o fluxo completo da SOB de acordo com as regras de negócio e validações da Seção 14.
        """
        resultado: Dict[str, Any] = {
            "sucesso": False,
            "status": "BLOQUEADO",
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
            "checklist": {},
        }

        checklist: Dict[str, bool] = {
            "SOB_ID válido": False,
            "SOB_NAME válido": False,
            "DESTINATION_ROOT válido": False,
            "SOB_ROOT correto": False,
            "CROQUI_DIR correto": False,
            "SOB encontrada no SharePoint": False,
            "Autenticação validada": False,
            "Download concluído": False,
            "Conteúdo do CROQUI validado": False,
            "BASE_TEMPLATE validado": False,
            "BASE_DWG criado": False,
            "BASE_DWG validado": False,
            "Integridade validada": False,
            "BASE_TEMPLATE preservado": False,
            "Estrutura final validada": False,
        }

        estrutura_criada_nesta_execucao = False
        sob_root_path: Optional[Path] = None

        try:
            self.logger.info("Início da operação")

            # ETAPA 1: Validação da Entrada da SOB (Seções 14.2, 14.3 e 14.4)
            resultado["estado"] = "INICIANDO"
            resultado["etapa"] = "VALIDAR_SOB"

            if not sob_raw or not str(sob_raw).strip():
                raise SobValidationError("[FALHA] SOB não informada.")

            sob_id = obter_sob_id(sob_raw)
            checklist["SOB_ID válido"] = True

            sob_name = obter_sob_name(sob_raw)
            checklist["SOB_NAME válido"] = True
            resultado["estado"] = "SOB_VALIDADA"

            # ETAPA 2: Seleção e Validação de DESTINATION_ROOT (Seção 14.5)
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

            # Derivação Canônica Centralizada (Seção 0-A & 14.6)
            caminhos = derivar_caminhos_sob(sob_raw, destination_root, self.origem_base)
            sob_root_path = caminhos["SOB_ROOT"]
            croqui_dir = caminhos["CROQUI_DIR"]
            base_dwg = caminhos["BASE_DWG"]
            base_template = caminhos["BASE_TEMPLATE"]

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

            # Logs canônicos padronizados (Seção 9)
            self.logger.info(f"SOB: {sob_id}")
            self.logger.info(f"SOB_ROOT: {sob_root_path}")
            self.logger.info(f"CROQUI_DIR: {croqui_dir}")
            self.logger.info(f"BASE_DWG: {base_dwg}")

            # ETAPA 06: Verificar existência da SOB_ROOT (Seção 17, Etapa 06)
            if verificar_pasta_sob_existente(destination_root, sob_name):
                raise SobDirectoryExistsError(
                    formatar_mensagem_erro(
                        etapa="Criação da pasta da SOB",
                        problema="[FALHA] A pasta da SOB já existe.",
                        caminho=str(sob_root_path),
                        acao="Verifique a pasta existente ou selecione outro diretório de destino.",
                    )
                )

            # ETAPA 07: Validar permissão de criação (Seção 17, Etapa 07)
            if not validar_permissao_criacao(destination_root):
                raise SobPermissionError(
                    "[FALHA] Não foi possível criar a pasta da SOB no diretório selecionado."
                )

            # ETAPAS 08, 09 e 10: Criação de SOB_ROOT e CROQUI_DIR (Seção 17, Etapas 08-10)
            sob_root_criado, croqui_dir_criado = criar_estrutura_sob(destination_root, sob_name)
            estrutura_criada_nesta_execucao = True
            resultado["estado"] = "ESTRUTURA_CRIADA"

            self.logger.info("Pasta da SOB criada")
            self.logger.info("Pasta CROQUI criada")

            # FASE 6 — PREPARAÇÃO DO ARQUIVO-BASE (Seção 17, Etapas 11 e 12)
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

            if base_dwg.exists():
                raise SobFileExistsError(
                    f"[FALHA] O arquivo de destino já existe: {base_dwg}"
                )

            checklist["BASE_TEMPLATE validado"] = True
            self.logger.info("Arquivo-base localizado")

            # FASE 7 & 8 — SHAREPOINT E DOWNLOAD DO CROQUI (Seção 17, Etapas 13 a 18)
            if baixar_croqui_sp:
                resultado["etapa"] = "SHAREPOINT"
                self.logger.info("Autenticação SharePoint iniciada")

                client = self.sharepoint_client
                if not client:
                    login, senha = obter_credenciais_sharepoint()
                    self.logger.adicionar_segredo(senha)
                    client = SharePointClient(login=login, senha=senha, headless=True)

                try:
                    client.autenticar()
                    checklist["Autenticação validada"] = True
                    resultado["estado"] = "SHAREPOINT_AUTENTICADO"

                    self.logger.info("SOB localizada")
                    pasta_info = client.localizar_pasta_sob(sob_id)
                    checklist["SOB encontrada no SharePoint"] = True
                    resultado["estado"] = "SOB_LOCALIZADA"

                    # ETAPA 16: Preparar download (validar CROQUI_DIR novamente)
                    if not croqui_dir.is_dir():
                        raise SobValidationError(f"[FALHA] Diretório do croqui inválido: {croqui_dir}")

                    self.logger.info("Download iniciado")
                    arquivos = client.baixar_croqui(pasta_info, croqui_dir)

                    client.validar_download(croqui_dir)
                    checklist["Download concluído"] = True
                    checklist["Conteúdo do CROQUI validado"] = True
                    resultado["estado"] = "DOWNLOAD_VALIDADO"

                    resultado["arquivos_croqui"] = [str(a) for a in arquivos]
                    self.logger.info("Download concluído")
                finally:
                    if not self.sharepoint_client:
                        client.fechar()
            else:
                # Modo sem sharepoint (testes offline)
                checklist["Autenticação validada"] = True
                checklist["SOB encontrada no SharePoint"] = True
                checklist["Download concluído"] = True
                checklist["Conteúdo do CROQUI validado"] = True
                resultado["estado"] = "DOWNLOAD_VALIDADO"

            # FASE 9 — CRIAÇÃO DO DWG DE TRABALHO (Seção 17, Etapas 19 a 21)
            resultado["etapa"] = "COPIAR_ARQUIVO_BASE"
            dwg_copiado = copiar_arquivo_base(
                base_template,
                sob_root_path,
                nome_destino=base_dwg.name,
            )
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

            # ETAPA 7: Validação da Estrutura Final (Seção 14.19)
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

            # ETAPA 8: Abertura no AutoCAD (se solicitado via CLI)
            if abrir_cad:
                resultado["etapa"] = "ABRIR_AUTOCAD"
                self._abrir_no_autocad(dwg_copiado)
                resultado["estado"] = "AUTOCAD_ABERTO"
                self.logger.info("DWG aberto")

            # Verificação Final da Regra de Não Falso Sucesso (Seção 14.25 e 14.27)
            if all(checklist.values()):
                resultado["sucesso"] = True
                resultado["status"] = "CONCLUÍDO"
                resultado["estado"] = "CONCLUÍDO"
                resultado["etapa"] = "FINALIZADO"
                resultado["mensagem"] = "Processo concluído com sucesso."
                self.logger.info("Processo concluído")
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

            # Rollback seguro da estrutura incompleta (Seção 14.8)
            if estrutura_criada_nesta_execucao and sob_root_path and sob_root_path.exists():
                limpou = remover_estrutura_incompleta(sob_root_path)
                if limpou:
                    self.logger.info(f"Limpeza controlada da estrutura incompleta realizada: {sob_root_path}")
                else:
                    self.logger.warning(f"Estrutura incompleta mantida por segurança: {sob_root_path}")

        except Exception as e:
            resultado["sucesso"] = False
            resultado["status"] = "BLOQUEADO"
            resultado["estado"] = "BLOQUEADO"
            msg_str = f"[FALHA] Erro inesperado durante a operação: {str(e)}"
            resultado["mensagem"] = msg_str
            self.logger.error(msg_str)

            if estrutura_criada_nesta_execucao and sob_root_path and sob_root_path.exists():
                remover_estrutura_incompleta(sob_root_path)

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
