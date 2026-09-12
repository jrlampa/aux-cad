@echo off
chcp 65001 >nul
title AUX CAD - Limpeza e Manutencao de Temporarios
cd /d "%~dp0"

echo ===============================================================
echo     AUX CAD - LIMPEZA DE TEMPORARIOS E ARQUIVOS DE CACHE
echo ===============================================================
echo.

echo [1/4] Limpando pastas temporarias do Windows...
del /f /s /q "%temp%\*.*" 2>nul
rd /s /q "%temp%" 2>nul
md "%temp%" 2>nul

del /f /s /q "%systemroot%\Temp\*.*" 2>nul
rd /s /q "%systemroot%\Temp" 2>nul
md "%systemroot%\Temp" 2>nul

echo [2/4] Removendo arquivos temporarios do AutoCAD (*.bak, *.dcl_tmp, *.tmp)...
del /f /s /q *.bak 2>nul
del /f /s /q *.dcl_tmp 2>nul
del /f /s /q *.tmp 2>nul

echo [3/4] Limpando caches de execucao Python e testes...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
if exist .pytest_cache rd /s /q .pytest_cache 2>nul
if exist .coverage del /f /q .coverage 2>nul

echo [4/4] Verificando integridade das pastas essenciais...
if not exist scratch md scratch 2>nul

echo.
echo ===============================================================
echo  [OK] Limpeza e manutencao concluidas com sucesso!
echo ===============================================================
echo.
pause