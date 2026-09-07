@echo off
chcp 65001 >nul
title AUX CAD - Orçamento e Levantamento de Materiais

cd /d "%~dp0"
python orcamento_manager.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Ocorreu um problema ao executar o Gerenciador de Orçamento.
    pause
)
