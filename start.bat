@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
title SGS Box Simulator

set "PY="
if exist "backend\.venv\Scripts\python.exe" set "PY=backend\.venv\Scripts\python.exe"
if not defined PY if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" set "PY=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set "PY=py"
)

if not defined PY (
  echo [X] 没有找到 Python，请安装 Python 3.10+ 后重试。
  echo     下载地址 https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

if /i "%~1"=="check" (
  "%PY%" run.py --check
  echo.
  pause
  exit /b 0
)

"%PY%" run.py
if errorlevel 1 (
  echo.
  echo [!] 模拟器没能启动，请把上面的提示截图反馈。
  echo     也可以双击 检查环境.bat 做一次体检。
  pause
)
