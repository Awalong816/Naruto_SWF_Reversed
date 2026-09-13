:: 不显示执行过程，只显示结果
@echo off
:: utf8编码
chcp 65001 >NUL
:: 所有变量只对脚本内有效
setlocal
:: 目标进程
set "PROCESS_NAME=ProxyBridge_CLI.exe"

echo [INFO] 正在检查 %PROCESS_NAME% 进程...
:: 用 tasklist 检查进程是否存在，输出重定向到 nul 避免显示
tasklist /FI "IMAGENAME eq %PROCESS_NAME%" 2>NUL | find /I "%PROCESS_NAME%" >NUL
:: if %ERRORLEVEL% EQU 0 -> 如果执行成功=发现
if %ERRORLEVEL% EQU 0 (
    echo [WARN] 发现 %PROCESS_NAME% 残留进程，正在结束...

    :: /F 强制结束，/IM 指定映像名，/T 结束子进程树
    taskkill /F /IM "%PROCESS_NAME%" /T

    if !ERRORLEVEL! EQU 0 (
        echo [INFO] %PROCESS_NAME% 已成功结束。
    ) else (
        echo [ERROR] 结束 %PROCESS_NAME% 失败，请以管理员身份运行此脚本。
    )
) else (
    echo [INFO] 未发现 %PROCESS_NAME% 残留进程。
)

echo.
pause
endlocal