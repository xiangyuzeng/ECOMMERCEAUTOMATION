@echo off
chcp 65001 >nul 2>&1
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
    echo [X] Docker 未安装！请先安装 Docker Desktop：
    echo    https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [X] Docker 未启动！请先打开 Docker Desktop 应用程序
    pause
    exit /b 1
)

echo [OK] Docker 已就绪

REM Create data directories
if not exist data mkdir data
if not exist inputs\sellersprite mkdir inputs\sellersprite
if not exist inputs\seller-central mkdir inputs\seller-central
if not exist outputs mkdir outputs
if not exist processed mkdir processed
if not exist logs mkdir logs

REM ---------------------------------------------------------------------------
REM .env setup — interactive prompts if not configured
REM ---------------------------------------------------------------------------
set "NEEDS_SETUP=0"

if not exist .env (
    copy .env.example .env >nul
    set "NEEDS_SETUP=1"
)

if "%NEEDS_SETUP%"=="0" (
    findstr /C:"your_api_key_here" /C:"YOUR_ADSPOWER_API_KEY" .env >nul 2>&1
    if not errorlevel 1 set "NEEDS_SETUP=1"
)

if "%NEEDS_SETUP%"=="1" (
    echo.
    echo ================================================
    echo   首次配置 — AdsPower 浏览器自动化设置
    echo ================================================
    echo.
    echo   检测 AdsPower...

    REM Try to detect AdsPower
    curl -sf http://localhost:50325/status >nul 2>&1
    if not errorlevel 1 (
        echo   [OK] AdsPower 已检测到 ^(localhost:50325^)
    ) else (
        echo   [!] 未检测到 AdsPower
        echo   请先启动 AdsPower 应用程序
        echo   如果不使用自动采集，可按 Enter 跳过
        echo.
    )

    echo.
    echo   步骤 1/2：输入 AdsPower API Key
    echo   获取方法：AdsPower 右上角齿轮 设置 -^> API -^> 复制 Key
    echo.
    set /p "API_KEY=   请粘贴 API Key（留空跳过）: "

    echo.
    echo   步骤 2/2：输入 Profile ID
    echo   获取方法：AdsPower 主界面 浏览器配置列表 复制 ID
    echo.
    set /p "PROFILE_ID=   请粘贴 Profile ID（留空跳过）: "

    REM Write .env
    (
        echo # 肯葳科技亚马逊自动运营系统 — 环境变量配置
        echo.
        echo # --- AdsPower 浏览器自动化 ---
        echo ADSPOWER_API_URL=http://localhost:50325
        echo ADSPOWER_API_KEY=%API_KEY%
        echo ADSPOWER_PROFILE_ID=%PROFILE_ID%
        echo.
        echo # --- 应用配置 ---
        echo NODE_ENV=production
        echo PORT=3000
    ) > .env

    echo.
    if defined API_KEY (
        if defined PROFILE_ID (
            echo   [OK] 配置已保存到 .env 文件
        ) else (
            echo   [!] 配置已保存（缺少 Profile ID，之后可编辑 .env 补充）
        )
    ) else (
        echo   已跳过 AdsPower 配置。系统仍可手动上传数据使用。
        echo   之后编辑 .env 文件填入 AdsPower 信息即可。
    )
    echo.
)

REM ---------------------------------------------------------------------------
REM Build and start
REM ---------------------------------------------------------------------------
echo.
echo 正在构建并启动系统...
echo    首次构建可能需要 5-10 分钟，请耐心等待
echo.

docker compose up -d --build

echo.
echo 等待系统启动...
timeout /t 10 /nobreak >nul

echo.
echo ================================================
echo   系统已启动！
echo.
echo   仪表盘地址: http://localhost:3000
echo.
echo   常用命令：
echo     查看日志:   docker compose logs -f
echo     停止系统:   docker compose down
echo     重新启动:   docker compose up -d
echo ================================================
echo.
pause
