# -*- coding: utf-8 -*-
"""
sob_logger.py - Utilitários de Logging e Formatação de Erros Seguros.
Responsabilidade única: Configuração de loggers, sanitização de credenciais em mensagens
e formatação padronizada de mensagens de erro conforme Seção 14.26.
"""

import logging
from pathlib import Path
import sys
from typing import Optional

from sob_sharepoint import sanitizar_mensagem


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
