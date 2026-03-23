@echo off
REM =============================================================================
REM 肯葳科技亚马逊自动运营系统 — 一键启动脚本 (Windows)
REM =============================================================================

echo ================================================
echo   肯葳科技亚马逊自动运营系统
echo   Amazon Operations Automation System
echo ================================================
echo.

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker 未安装！请先安装 Docker Desktop：
    echo    https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker 未启动！请先打开 Docker Desktop 应用程序
    pause
    exit /b 1
)

echo ✅ Docker 已就绪

REM Create .env if missing
if not exist .env (
    echo 📝 首次运行：从模板创建 .env 配置文件...
    copy .env.example .env
    echo.
    echo ⚠️  请编辑 .env 文件，填入你的 AdsPower API Key 和 Profile ID
    echo    文件位置: %cd%\.env
    echo.
    echo    填写完成后，重新运行此脚本即可
    pause
    exit /b 0
)

REM Create data directories
if not exist data mkdir data
if not exist inputs\sellersprite mkdir inputs\sellersprite
if not exist inputs\seller-central mkdir inputs\seller-central
if not exist outputs mkdir outputs
if not exist processed mkdir processed
if not exist logs mkdir logs

echo.
echo 🚀 正在构建并启动系统...
echo    首次构建可能需要 5-10 分钟，请耐心等待
echo.

docker compose up -d --build

echo.
echo ⏳ 等待系统启动...
timeout /t 10 /nobreak >nul

echo.
echo ================================================
echo   系统已启动！
echo.
echo   🌐 仪表盘地址: http://localhost:3000
echo.
echo   常用命令：
echo     查看日志:   docker compose logs -f
echo     停止系统:   docker compose down
echo     重新启动:   docker compose up -d
echo ================================================
echo.
pause
