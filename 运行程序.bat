@echo off
chcp 936 >nul
title 个人知识管理系统

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║       个人知识管理系统 v1.0              ║
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

:: 选择数据库
echo   ┌──────────────────────────────────────────┐
echo   │  请选择知识库:                            │
echo   │    [1] knowledge.db  (通用知识)            │
echo   │    [2] art.db        (艺术)                │
echo   │    [3] AI.db         (人工智能)            │
echo   │    [4] math.db       (数学)                │
echo   │    [5] life.db       (生活记录)            │
echo   │    [6] physics.db    (物理科学)            │
echo   │    [0] 退出                                │
echo   └──────────────────────────────────────────┘
echo.
set /p choice="  请输入选项 (1/2/3/4/5/6/0): "

if "%choice%"=="0" exit /b 0
if "%choice%"=="1" set DB=knowledge.db && goto start
if "%choice%"=="2" set DB=art.db && goto start
if "%choice%"=="3" set DB=AI.db && goto start
if "%choice%"=="4" set DB=math.db && goto start
if "%choice%"=="5" set DB=life.db && goto start
if "%choice%"=="6" set DB=physics.db && goto start

echo   无效选项，使用默认数据库 knowledge.db
set DB=knowledge.db
goto start

:start
echo.
echo   启动中...
echo   数据库: %DB%
echo   访问地址: http://localhost:5000
echo   按 Ctrl+C 停止服务器
echo   ──────────────────────────────────────────
echo.

python run.py --db %DB%

if %errorlevel% neq 0 (
    echo.
    echo   [错误] 启动失败，请检查配置和日志
    pause
    exit /b 1
)

pause
