@echo off
chcp 936 >nul
title 个人知识管理系统 - 一键启动

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║    个人知识管理系统 - 一键启动模式       ║
echo   ╚══════════════════════════════════════════╝
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 未找到 Python，请先安装 Python 3.8+
    echo.
    pause
    exit /b 1
)

:: 检查依赖
pip show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo   [提示] 检测到依赖未安装，正在安装...
    pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo   [错误] 依赖安装失败，请手动执行: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo   [完成] 依赖安装成功
    echo.
)

:: 直接启动，使用默认 knowledge.db
echo   正在启动 Web 界面...
echo   访问地址: http://localhost:5000
echo   按 Ctrl+C 停止服务器
echo   ──────────────────────────────────────────
echo.

python run.py --auto

if %errorlevel% neq 0 (
    echo.
    echo   [错误] 启动失败，请检查配置和日志
    pause
    exit /b 1
)

pause
