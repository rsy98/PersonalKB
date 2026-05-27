@echo off
chcp 65001 >nul
echo 🚀 正在启动个人知识管理系统...
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python环境检测通过
echo.

:: 直接使用1号数据库启动，不显示选择界面
echo 📚 使用默认数据库: knowledge.db
echo.
python run.py --db knowledge.db

if %errorlevel% neq 0 (
    echo.
    echo ❌ 启动失败
    pause
    exit /b 1
)

echo.
echo 🌐 程序正在运行中...
echo 💡 请手动访问: http://localhost:5000
echo ⏹️  按Ctrl+C停止服务
echo.

pause
exit
