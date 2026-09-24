@echo off
title Workspace da SOB - AUX CAD
echo Iniciando Workspace da SOB / Projeto (Contexto e Artefatos)...
start "" py "%~dp0workspace\workspace_cli.py" --gui
