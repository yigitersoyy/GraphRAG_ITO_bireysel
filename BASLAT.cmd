@echo off
chcp 65001 >nul
setlocal
title GraphRAG - Baslatiliyor
pushd "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Kurulum bulunamadi. Once scripts\setup.ps1 calistirilmalidir.
  pause
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -u "scripts\one_click.py"
if errorlevel 1 (
  echo.
  echo Ayrintilar: reports\runtime\launcher.log
  pause
  popd
  exit /b 1
)
popd
exit /b 0
