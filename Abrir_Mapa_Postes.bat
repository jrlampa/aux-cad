@echo off
chcp 65001 > nul
title AUX CAD - Estúdio de Lançamento de Postes & Cargas

echo =======================================================
echo    AUX CAD - ESTÚDIO DE LANÇAMENTO DE POSTES (SATÉLITE)
echo =======================================================
echo.
echo Iniciando servidor local do mapa interativo...
cd /d "%~dp0"
python mapa_postes\mapa_servidor.py
pause
