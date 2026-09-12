@echo off
chcp 65001 >nul
title AUX CAD - Diagrama Unifilar e Proteção a Montante
cd /d "%~dp0"

echo =======================================================
echo    AUX CAD - DIAGRAMA UNIFILAR & PROTEÇÃO (KMZ / SGT)
echo =======================================================
echo.
echo Comandos no AutoCAD:
echo   - UNIFILAR ou PROTECAO : Localiza proteção a montante (SG) e desenha esquema
echo   - ARVORE : Consulta caminho elétrico a montante
echo.
echo [1] Iniciar busca CLI interativa de ponto / resumo...
echo.
py unifilar\unifilar_manager.py --help 2>nul || python unifilar\unifilar_manager.py --help
echo.
pause
