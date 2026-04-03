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

# Create data directories
mkdir -p data inputs/sellersprite inputs/seller-central outputs processed logs

# ---------------------------------------------------------------------------
# .env setup — auto-detect AdsPower + interactive prompts
# ---------------------------------------------------------------------------
NEEDS_SETUP=false

if [ ! -f .env ]; then
    cp .env.example .env
    NEEDS_SETUP=true
elif grep -q "your_api_key_here\|YOUR_ADSPOWER_API_KEY\|^ADSPOWER_API_KEY=$" .env 2>/dev/null; then
    NEEDS_SETUP=true
fi

if [ "$NEEDS_SETUP" = true ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📋 首次配置 — AdsPower 浏览器自动化设置"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Try to auto-detect AdsPower
    ADSPOWER_URL="http://localhost:50325"
    ADSPOWER_DETECTED=false

    echo "🔍 正在检测 AdsPower..."
    if curl -sf "$ADSPOWER_URL/status" > /dev/null 2>&1; then
        echo "   ✅ AdsPower 已检测到 ($ADSPOWER_URL)"
        ADSPOWER_DETECTED=true
    else
        # Try common alternative ports
        for port in 50325 50326 52025; do
            if curl -sf "http://localhost:$port/status" > /dev/null 2>&1; then
                ADSPOWER_URL="http://localhost:$port"
                echo "   ✅ AdsPower 已检测到 ($ADSPOWER_URL)"
                ADSPOWER_DETECTED=true
                break
            fi
        done
    fi

    if [ "$ADSPOWER_DETECTED" = false ]; then
        echo "   ⚠️  未检测到 AdsPower"
        echo "   请先启动 AdsPower 应用程序"
        echo ""
        echo "   如果你不使用自动采集功能，可以按 Enter 跳过此步骤"
        echo "   （之后可以手动上传数据文件到 inputs/ 目录）"
        echo ""
    fi

    # --- API Key ---
    echo ""
    echo "📌 步骤 1/2：输入 AdsPower API Key"
    echo "   获取方法：打开 AdsPower → 右上角 ⚙️ 设置 → API → 复制 Key"
    echo ""

    # If AdsPower is running, try to auto-detect profiles with user-entered key
    read -p "   请粘贴你的 API Key（留空跳过）: " API_KEY

    # --- Profile ID ---
    PROFILE_ID=""
    if [ -n "$API_KEY" ] && [ "$ADSPOWER_DETECTED" = true ]; then
        echo ""
        echo "🔍 正在获取浏览器配置列表..."
        PROFILES=$(curl -sf "$ADSPOWER_URL/api/v1/user/list?api_key=$API_KEY" 2>/dev/null)

        if [ -n "$PROFILES" ]; then
            # Parse and display profiles
            PROFILE_LIST=$(echo "$PROFILES" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    profiles = data.get('data', {}).get('list', [])
    if profiles:
        for i, p in enumerate(profiles):
            print(f\"   {i+1}. {p.get('name', 'Unknown')} (ID: {p.get('user_id', '?')})\")
    else:
        print('   (无可用配置)')
except:
    print('   (解析失败)')
" 2>/dev/null)

            if [ -n "$PROFILE_LIST" ] && ! echo "$PROFILE_LIST" | grep -q "无可用配置\|解析失败"; then
                echo "   找到以下浏览器配置："
                echo "$PROFILE_LIST"
                echo ""

                # Auto-select if only one profile
                PROFILE_COUNT=$(echo "$PROFILES" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data.get('data', {}).get('list', [])))
except:
    print(0)
" 2>/dev/null)

                if [ "$PROFILE_COUNT" = "1" ]; then
                    PROFILE_ID=$(echo "$PROFILES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['data']['list'][0]['user_id'])
" 2>/dev/null)
                    echo "   ✅ 已自动选择唯一配置: $PROFILE_ID"
                else
                    echo "📌 步骤 2/2：输入 Profile ID"
                    echo "   从上方列表中复制你要使用的 ID（括号中的值）"
                    echo ""
                    read -p "   请粘贴 Profile ID: " PROFILE_ID
                fi
            else
                echo "   ⚠️  无法获取配置列表（API Key 可能不正确）"
                echo ""
                echo "📌 步骤 2/2：手动输入 Profile ID"
                echo "   获取方法：AdsPower 主界面 → 浏览器配置列表 → 复制 ID"
                echo ""
                read -p "   请粘贴 Profile ID（留空跳过）: " PROFILE_ID
            fi
        fi
    else
        echo ""
        echo "📌 步骤 2/2：输入 Profile ID"
        echo "   获取方法：AdsPower 主界面 → 浏览器配置列表 → 复制 ID"
        echo ""
        read -p "   请粘贴 Profile ID（留空跳过）: " PROFILE_ID
    fi

    # Write .env file
    cat > .env << ENVEOF
# =============================================================================
# 肯葳科技亚马逊自动运营系统 — 环境变量配置
# =============================================================================

# --- AdsPower 浏览器自动化 ---
ADSPOWER_API_URL=$ADSPOWER_URL
ADSPOWER_API_KEY=${API_KEY:-}
ADSPOWER_PROFILE_ID=${PROFILE_ID:-}

# --- 应用配置 ---
NODE_ENV=production
PORT=3000
ENVEOF

    echo ""
    if [ -n "$API_KEY" ] && [ -n "$PROFILE_ID" ]; then
        echo "✅ 配置已保存到 .env 文件"
    elif [ -n "$API_KEY" ]; then
        echo "⚠️  配置已保存（缺少 Profile ID，之后可编辑 .env 补充）"
    else
        echo "ℹ️  已跳过 AdsPower 配置。系统仍可手动上传数据使用。"
        echo "   之后需要自动采集时，编辑 .env 文件填入 AdsPower 信息即可。"
    fi
    echo ""
fi

# ---------------------------------------------------------------------------
# Build and start
# ---------------------------------------------------------------------------
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
