@echo off
chcp 65001 >nul
title AUX CAD 2026 - Central de Automação & Engenharia
cd /d "%~dp0"
echo =======================================================
echo    AUX CAD 2026 - Central de Automação & Engenharia
echo =======================================================
echo Iniciando o Hub Central de Módulos...
start "" python aux_cad_hub.py
exit
