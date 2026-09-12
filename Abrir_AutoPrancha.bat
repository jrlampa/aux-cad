@echo off
chcp 65001 >nul
title AUX CAD - AutoPrancha Enel / HBT (ModelSpace)
cd /d "%~dp0"

echo =======================================================
echo    AUX CAD - AUTOPRANCHA ENEL / HBT (MODELSPACE 1:1)
echo =======================================================
echo.
echo Comandos no AutoCAD:
echo   - AUTOPRANCHA (ou PRANCHA / ENQUADRAR / FOLHA)
echo   - RECARREGAR_PRANCHA
echo.
echo Modos suportados:
echo   - [Auto] : Enquadramento ótimo (folha A0..A4 + escala 1:500..1:2000)
echo   - [Escala] : Forçar escala específica (ex: 1:1000)
echo   - [Formato] : Forçar formato de folha (ex: A1)
echo.
py prancha\autoprancha_core.py 2>nul || python prancha\autoprancha_core.py
echo.
pause
