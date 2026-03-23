#!/bin/bash
# =============================================================================
# 肯葳科技亚马逊自动运营系统 — 一键启动脚本 (Mac / Linux)
# =============================================================================
set -e

echo "================================================"
echo "  肯葳科技亚马逊自动运营系统"
echo "  Amazon Operations Automation System"
echo "================================================"
echo ""

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装！请先安装 Docker Desktop："
    echo "   https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Check Docker is running
if ! docker info &> /dev/null 2>&1; then
    echo "❌ Docker 未启动！请先打开 Docker Desktop 应用程序"
    exit 1
fi

echo "✅ Docker 已就绪"

# Create .env if missing
if [ ! -f .env ]; then
    echo "📝 首次运行：从模板创建 .env 配置文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，填入你的 AdsPower API Key 和 Profile ID"
    echo "   文件位置: $(pwd)/.env"
    echo ""
    echo "   填写完成后，重新运行此脚本即可"
    exit 0
fi

# Create data directories
mkdir -p data inputs/sellersprite inputs/seller-central outputs processed logs

# Build and start
echo ""
echo "🚀 正在构建并启动系统..."
echo "   首次构建可能需要 5-10 分钟，请耐心等待"
echo ""

docker compose up -d --build

echo ""
echo "⏳ 等待系统启动..."
sleep 8

# Check health
if curl -sf http://localhost:3000/api/status > /dev/null 2>&1; then
    echo ""
    echo "================================================"
    echo "  ✅ 系统启动成功！"
    echo ""
    echo "  🌐 仪表盘地址: http://localhost:3000"
    echo ""
    echo "  常用命令："
    echo "    查看日志:   docker compose logs -f"
    echo "    停止系统:   docker compose down"
    echo "    重新启动:   docker compose up -d"
    echo "================================================"
else
    echo "⏳ 系统仍在启动中，请稍候 10 秒后访问 http://localhost:3000"
    echo "   查看日志: docker compose logs -f"
fi
