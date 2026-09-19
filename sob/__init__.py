# -*- coding: utf-8 -*-
"""
Módulo de Preparação de Projeto SOB.
Automação integrada ao AutoCAD para criação da pasta da SOB, obtenção de croquis
do SharePoint da HBT/Enel, cópia do arquivo-base e abertura no AutoCAD.
"""

from .sob_core import (
    normalizar_sob,
    validar_sob,
    verificar_pasta_sob_existente,
    criar_estrutura_sob,
    copiar_arquivo_base,
    validar_arquivo_dwg,
)

__all__ = [
    "normalizar_sob",
    "validar_sob",
    "verificar_pasta_sob_existente",
    "criar_estrutura_sob",
    "copiar_arquivo_base",
    "validar_arquivo_dwg",
]
