:: winget 更换国内镜像源脚本
:: 不显示执行过程，只显示结果
@echo off
:: utf8编码
chcp 65001 >NUL
:: 变量作用域: 脚本内
setlocal

:: ========== 管理员权限自检与提权 ==========
net session >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] 需要管理员权限，正在请求提权...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: ========== 以下代码以管理员权限运行 ==========
echo [INFO] 已获得管理员权限

set "SOURCE_NAME=winget"
set "SOURCE_URL=https://mirrors.ustc.edu.cn/winget-source"

:: 先尝试删除旧源（如果存在），避免重复添加报错
winget source remove %SOURCE_NAME% >NUL 2>&1

:: 添加镜像源
winget source add %SOURCE_NAME% %SOURCE_URL% --trust-level trusted

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [INFO] 镜像源添加成功
) else (
    echo.
    echo [ERROR] 镜像源添加失败，请检查网络或 winget 版本
)

echo.
pause
endlocal