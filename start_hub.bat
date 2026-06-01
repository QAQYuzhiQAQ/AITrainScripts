@echo off
chcp 65001 >nul
cd /d "%~dp0"

title AITrainScripts Hub

REM 优先 py 启动器，其次 python / python3
where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py"
  goto :run
)
where python >nul 2>&1
if %errorlevel%==0 (
  set "PY=python"
  goto :run
)
where python3 >nul 2>&1
if %errorlevel%==0 (
  set "PY=python3"
  goto :run
)

echo [错误] 未找到 Python。请从 https://www.python.org 安装并勾选 "Add to PATH"。
pause
exit /b 1

:run
%PY% "%~dp0start_hub.py"
if errorlevel 1 pause
