@echo off
REM F1 Race Engineer - USB adb reverse 一键打通（插上手机并开启 USB 调试后运行）
REM 把手机 127.0.0.1:8000 转发到电脑本机 8000，App 里主机 IP 填 127.0.0.1、端口 8000。
REM 需要 adb（已装在 C:\Users\lzh\platform-tools\adb.exe；若未装请先装 platform-tools）。

set "ADB=C:\Users\lzh\platform-tools\adb.exe"

echo [1/2] 检查手机连接...
"%ADB%" devices | findstr /R "device$" >nul
if errorlevel 1 (
    echo   未检测到手机。请确认：已插 USB 线、已开「USB 调试」、首次弹窗点允许。
    pause
    exit /b 1
)

echo [2/2] 建立 adb reverse tcp:8000 tcp:8000 ...
"%ADB%" reverse tcp:8000 tcp:8000
if errorlevel 1 (
    echo   失败，请重试。
    pause
    exit /b 1
)

echo 完成！App 设置页填：主机 IP = 127.0.0.1，端口 = 8000，点「测试连接」。
pause
