@echo off
REM ============================================================
REM  F1 Race Engineer 后端启动器（纯 cmd，不依赖 PowerShell）
REM
REM  双击运行即可，自动完成：
REM    1. 找 Python（优先项目 .venv，其次 PATH 上的 python，跳过商店占位）
REM    2. 停掉占用 TCP 8000 的旧后端实例（避免 Address already in use）
REM    3. 检查 UDP 20777 是否被别的进程占用（游戏遥测端口）
REM    4. 在新窗口启动后端（关掉「F1 RE Backend」窗口即停服）
REM    5. 轮询 /health 直到就绪（最长 25 秒）
REM    6. 打印手机 App 的连接信息（WiFi IP / USB 两种方式）
REM
REM  改端口：修改下面 PORT / UDP_PORT（两处需一致：本文件 + 游戏内设置）。
REM ============================================================
setlocal EnableExtensions EnableDelayedExpansion
title F1 Race Engineer 启动器
cd /d "%~dp0"

set "PORT=8000"
set "UDP_PORT=20777"
set "DB=telemetry.sqlite3"

REM ---------- [1/5] 找 Python ----------
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
) else (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /I "WindowsApps" >nul || if not defined PY set "PY=%%P"
    )
)
if not defined PY (
    echo [错误] 找不到可用的 Python。
    echo   请先在项目目录创建虚拟环境： python -m venv .venv
    echo   然后安装依赖： .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo [1/5] Python: %PY%

REM ---------- [2/5] 停掉占用 TCP 8000 的旧后端 ----------
echo [2/5] 检查端口 %PORT% 上的旧后端...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
    if not errorlevel 1 echo   已停止旧后端（PID %%P）
)

REM ---------- [3/5] 检查 UDP 20777 占用 ----------
echo [3/5] 检查 UDP %UDP_PORT% 占用...
for /f "tokens=4" %%P in ('netstat -ano -p UDP ^| findstr /R /C:":%UDP_PORT% "') do (
    tasklist /FI "PID eq %%P" /FO CSV /NH 2>nul | findstr /I "python.exe" >nul
    if not errorlevel 1 (
        taskkill /F /PID %%P >nul 2>&1
        if not errorlevel 1 echo   已停止占用 UDP %UDP_PORT% 的旧后端（PID %%P）
    ) else (
        echo   [警告] UDP %UDP_PORT% 被其他程序占用（PID %%P），游戏遥测可能收不到
    )
)

REM ---------- [4/5] 启动后端（独立窗口，窗口关闭即停服） ----------
echo [4/5] 启动后端：REST/WS :%PORT% + UDP :%UDP_PORT%
start "F1 RE Backend - 关闭此窗口即停服" cmd /k ""%PY%" scripts\serve.py --db "%DB%" --port %PORT% --udp-port %UDP_PORT%"

REM ---------- [5/5] 等 /health 就绪 ----------
echo [5/5] 等待后端就绪（最长 25 秒）...
set "READY=0"
for /l %%I in (1,1,25) do (
    curl -s --max-time 2 "http://127.0.0.1:%PORT%/health" 2>nul | findstr /C:"ok" >nul 2>&1
    if not errorlevel 1 (
        set "READY=1"
        goto :ready
    )
    ping -n 2 127.0.0.1 >nul
)
:ready

echo.
echo ============================================================
if "!READY!"=="1" (
    echo  ^>^> 后端已就绪！
    curl -s "http://127.0.0.1:%PORT%/health"
    echo.
) else (
    echo  ^>^> 健康检查超时：请查看「F1 RE Backend」窗口里的报错信息。
)
echo ============================================================
echo.
echo  手机 App 连接方式（二选一）：
echo.
echo  【方式一 WiFi】手机和电脑连同一个 WiFi，App「设置」页填：
echo     主机 IP = 下面列出的某个 IPv4 地址（一般是「无线局域网适配器 WLAN」）
echo     端口   = %PORT%
for /f "tokens=*" %%L in ('ipconfig ^| findstr /C:"IPv4"') do echo     %%L
echo.
echo  【方式二 USB】插上手机并开启 USB 调试，运行 scripts\usb_connect.bat，
echo     然后 App「设置」页填：主机 IP = 127.0.0.1，端口 = %PORT%
echo.
echo  注意：游戏内「遥测」设置改动后必须完全重启游戏才生效；
echo        实时遥测只在真正上赛道驾驶（未暂停）时推送。
echo.
pause
