@echo off
chcp 65001 >nul
title AUX CAD - Limpeza e Manutencao de Temporarios
cd /d "%~dp0"

echo ===============================================================
echo     AUX CAD - LIMPEZA DE TEMPORARIOS E ARQUIVOS DE CACHE
echo ===============================================================
echo.

echo [1/5] Limpando pastas temporarias do Windows e downloads incompletos...
del /f /s /q "%temp%\*.*" 2>nul
del /f /s /q "%temp%\*.crdownload" 2>nul
del /f /s /q "%temp%\scoped_dir*" 2>nul
rd /s /q "%temp%" 2>nul
md "%temp%" 2>nul

del /f /s /q "%systemroot%\Temp\*.*" 2>nul
rd /s /q "%systemroot%\Temp" 2>nul
md "%systemroot%\Temp" 2>nul

echo [2/5] Removendo arquivos temporarios do AutoCAD (*.bak, *.dcl_tmp, *.tmp)...
del /f /s /q *.bak 2>nul
del /f /s /q *.dcl_tmp 2>nul
del /f /s /q *.tmp 2>nul

echo [3/5] Limpando caches de execucao Python e testes...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
if exist .pytest_cache rd /s /q .pytest_cache 2>nul
if exist .coverage del /f /q .coverage 2>nul

echo [4/5] Limpando artefatos temporarios de geoprocessamento e downloads...
del /f /s /q *.crdownload 2>nul
if exist kmz_import_postes_exec.lsp del /f /q kmz_import_postes_exec.lsp 2>nul

echo [5/5] Verificando integridade das pastas essenciais...
if not exist scratch md scratch 2>nul
if not exist modelos md modelos 2>nul
if not exist documentos md documentos 2>nul

echo.
echo ===============================================================
echo  [OK] Limpeza e manutencao concluidas com sucesso!
echo ===============================================================
echo.
pause