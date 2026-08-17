@echo off
REM ============================================================
REM  F1 Race Engineer 演示模式（纯 cmd，不依赖 PowerShell）
REM
REM  不开游戏也能验证「手机 App 实时遥测」整条链路：
REM    1. 在独立端口起一个演示后端（8001 / UDP 20778，演示库 demo.sqlite3）
REM    2. 把生产库里昨天的【真实比赛帧】按 20 帧/秒回放到演示后端
REM    3. 后端按与真实游戏完全相同的路径 校验 → 入库 → WS 广播
REM    4. 手机 App 设置页填 电脑 IP + 端口 8001，点连接即可看到速度/挡位/转速滚动
REM
REM  为什么用独立端口和演示库：回放帧与游戏直发帧入库后不可区分，
REM  混进生产库会污染 AI/对比分析数据，所以演示与生产完全隔离。
REM  用完关掉两个窗口即可，随时可重复。
REM ============================================================
setlocal EnableExtensions EnableDelayedExpansion
title F1 RE 演示模式
cd /d "%~dp0"

set "PORT=8001"
set "UDP_PORT=20778"
set "DB=demo.sqlite3"

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
) else (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /I "WindowsApps" >nul || if not defined PY set "PY=%%P"
    )
)
if not defined PY (
    echo [错误] 找不到 Python（需要项目 .venv）。
    pause
    exit /b 1
)

echo [1/3] 清理端口 %PORT% / UDP %UDP_PORT% 上的旧演示实例...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do taskkill /F /PID %%P >nul 2>&1
for /f "tokens=4" %%P in ('netstat -ano -p UDP ^| findstr /R /C:":%UDP_PORT% "') do taskkill /F /PID %%P >nul 2>&1

echo [2/3] 启动演示后端（窗口「F1 RE Demo Backend」）
start "F1 RE Demo Backend" cmd /k ""%PY%" scripts\serve.py --db "%DB%" --port %PORT% --udp-port %UDP_PORT%"

echo [3/3] 等待就绪...
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

if "!READY!"=="0" (
    echo [错误] 演示后端未就绪，请查看「F1 RE Demo Backend」窗口报错。
    pause
    exit /b 1
)

echo 启动回放（窗口「F1 RE Replay」，Ctrl+C 停止）...
start "F1 RE Replay - 回放真实帧（关闭即停）" cmd /k ""%PY%" scripts\replay_udp.py --db telemetry.sqlite3 --target 127.0.0.1:%UDP_PORT% --rate 20 --loop"

echo.
echo ============================================================
echo  演示已启动！手机 App「设置」页填：
echo     主机 IP = 下面某个 IPv4 地址（与电脑同 WiFi 的 WLAN 那个）
echo     端口   = %PORT%
echo   然后到「仪表盘」点「连接」→ 实时遥测区约 2 秒后开始滚动。
for /f "tokens=*" %%L in ('ipconfig ^| findstr /C:"IPv4"') do echo     %%L
echo.
echo  USB 方式：另开 usb_connect.bat 后改用 adb reverse tcp:%PORT% tcp:%PORT%，
echo  App 填 127.0.0.1:%PORT%
echo  （演示数据落 %DB%，用完可整库删除，不影响生产 telemetry.sqlite3）
echo ============================================================
pause
