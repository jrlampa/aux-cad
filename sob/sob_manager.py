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
    verificar_pasta_sob_existente,
    criar_estrutura_sob,
    copiar_arquivo_base,
    validar_arquivo_dwg,
    SobValidationError,
    SobDirectoryExistsError,
    SobFileNotFoundError,
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
    """Orquestrador do ciclo de vida da preparação de projeto SOB."""

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
        Executa o fluxo completo da SOB de acordo com as regras de negócio:
        1. Validar e normalizar SOB
        2. Validar destino
        3. Checar existência prévia (não sobrescrever)
        4. Criar estrutura SOB_ROOT e CROQUI
        5. Conectar e baixar croqui do SharePoint (se solicitado)
        6. Copiar e validar prancha.dwg para BASE_SOB_DESENHO.dwg
        7. Abrir no AutoCAD (se solicitado via CLI)
        """
        resultado = {
            "sucesso": False,
            "etapa": "INICIO",
            "mensagem": "",
            "sob": "",
            "sob_root": "",
            "croqui_dir": "",
            "dwg_path": "",
            "arquivos_croqui": [],
        }

        try:
            self.logger.info("Início da operação")

            # ETAPA 1: Validação e Normalização da SOB
            resultado["etapa"] = "VALIDAR_SOB"
            if not sob_raw or not sob_raw.strip():
                raise SobValidationError("O número da SOB não pode ser vazio.")

            if not validar_sob(sob_raw):
                raise SobValidationError(
                    f"Número de SOB com formato inválido: '{sob_raw.strip()}'. "
                    "Use apenas caracteres alfanuméricos."
                )

            pasta_sob = normalizar_sob(sob_raw)
            resultado["sob"] = pasta_sob
            self.logger.info(f"SOB identificada: {pasta_sob}")

            # ETAPA 2: Seleção e Validação do Destino
            resultado["etapa"] = "VALIDAR_DESTINO"
            if not destino_dir or not str(destino_dir).strip():
                raise SobValidationError(
                    "Operação cancelada: nenhum diretório de destino selecionado."
                )

            destino_path = Path(destino_dir).resolve()
            if not destino_path.is_dir():
                raise SobFileNotFoundError(
                    f"Diretório de destino inválido ou inexistente: {destino_path}"
                )

            self.logger.info(f"Diretório selecionado: {destino_path}")

            # ETAPA 3 & 4: Proteção contra existência e Criação da Estrutura
            resultado["etapa"] = "CRIAR_ESTRUTURA"
            if verificar_pasta_sob_existente(destino_path, pasta_sob):
                raise SobDirectoryExistsError(
                    "A pasta da SOB já existe no local selecionado.\n"
                    "Nenhum arquivo foi sobrescrito."
                )

            sob_root, croqui_dir = criar_estrutura_sob(destino_path, pasta_sob)
            resultado["sob_root"] = str(sob_root)
            resultado["croqui_dir"] = str(croqui_dir)

            self.logger.info("Pasta da SOB criada")
            self.logger.info("Pasta CROQUI criada")

            # ETAPA 5: Acesso ao SharePoint e Download do Croqui
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
                    self.logger.info("SOB localizada")
                    pasta_info = client.localizar_pasta_sob(pasta_sob)

                    self.logger.info("Download iniciado")
                    arquivos = client.baixar_croqui(pasta_info, croqui_dir)

                    client.validar_download(croqui_dir)
                    resultado["arquivos_croqui"] = [str(a) for a in arquivos]
                    self.logger.info("Download concluído")
                finally:
                    if not self.sharepoint_client:
                        client.fechar()

            # ETAPA 6: Cópia e Validação do Arquivo-Base DWG
            resultado["etapa"] = "COPIAR_ARQUIVO_BASE"
            if not self.origem_base.is_file():
                raise SobFileNotFoundError(
                    f"Arquivo-base não encontrado: {self.origem_base}"
                )

            self.logger.info("Arquivo-base localizado")
            dwg_copiado = copiar_arquivo_base(self.origem_base, sob_root)
            self.logger.info("Arquivo-base copiado")

            resultado["etapa"] = "VALIDAR_DWG"
            if not validar_arquivo_dwg(dwg_copiado):
                raise IOError(
                    f"Falha na validação do arquivo DWG copiado: {dwg_copiado}"
                )

            resultado["dwg_path"] = str(dwg_copiado)
            self.logger.info("DWG validado")

            # ETAPA 7: Abertura do DWG no AutoCAD (se solicitado via CLI)
            if abrir_cad:
                resultado["etapa"] = "ABRIR_AUTOCAD"
                self._abrir_no_autocad(dwg_copiado)
                self.logger.info("DWG aberto")

            resultado["sucesso"] = True
            resultado["etapa"] = "FINALIZADO"
            resultado["mensagem"] = "Processo concluído com sucesso."
            self.logger.info("Processo concluído")

        except (
            SobValidationError,
            SobDirectoryExistsError,
            SobFileNotFoundError,
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
            resultado["mensagem"] = str(e)
            self.logger.error(str(e))
        except Exception as e:
            resultado["sucesso"] = False
            resultado["mensagem"] = f"Erro inesperado durante o processo: {str(e)}"
            self.logger.error(resultado["mensagem"])

        return resultado

    def _abrir_no_autocad(self, dwg_path: Path):
        """Dispara a abertura do DWG no AutoCAD."""
        try:
            # No Windows, os.startfile aciona o aplicativo associado (AutoCAD)
            os.startfile(str(dwg_path))
        except Exception as e:
            raise IOError(f"Não foi possível abrir o arquivo DWG no AutoCAD: {e}")


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
