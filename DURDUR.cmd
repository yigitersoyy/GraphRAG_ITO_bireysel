@echo off
chcp 65001 >nul
setlocal
title GraphRAG - Durduruluyor
pushd "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Kurulum bulunamadi.
  pause
  popd
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\runtime.py" stop --mode live
if errorlevel 1 (
  pause
  popd
  exit /b 1
)
echo Notlar korundu. Docker ve LM Studio ortak servisleri acik birakildi.
popd
exit /b 0
