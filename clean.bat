@echo off
title Limpeza de Arquivos Temporários
del /f /s /q "%temp%\*.*" 2>nul
rd /s /q "%temp%" 2>nul
md "%temp%" 2>nul

del /f /s /q "%systemroot%\Temp\*.*" 2>nul
rd /s /q "%systemroot%\Temp" 2>nul
md "%systemroot%\Temp" 2>nul

echo [OK] Limpeza de arquivos temporários concluída com sucesso.
pause