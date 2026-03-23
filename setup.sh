#!/bin/bash
# ECOMMERCEAUTOMATION — One-time setup (idempotent — safe to re-run)
set -e
PROJECT="$HOME/Desktop/ECOMMERCEAUTOMATION"
echo "🚀 Setting up: $PROJECT"

# Create full directory structure
mkdir -p "$PROJECT/scripts/parsers"
mkdir -p "$PROJECT/scripts/processors"
mkdir -p "$PROJECT/scripts/exporters"
mkdir -p "$PROJECT/scripts/collectors"
mkdir -p "$PROJECT/inputs/sellersprite"
mkdir -p "$PROJECT/inputs/seller-central"
mkdir -p "$PROJECT/inputs/product-costs"
mkdir -p "$PROJECT/processed"
mkdir -p "$PROJECT/outputs"
mkdir -p "$PROJECT/logs"
mkdir -p "$PROJECT/dashboard/app"
mkdir -p "$PROJECT/dashboard/public"
mkdir -p "$PROJECT/.claude/commands"

# Create __init__.py files
for d in scripts scripts/parsers scripts/processors scripts/exporters scripts/collectors; do
    touch "$PROJECT/$d/__init__.py"
done

# Move any data files from project root into correct subdirs
cd "$PROJECT"
for f in *.xlsx; do
    [ -f "$f" ] || continue
    case "$f" in
        KeywordMining-*|ExpandKeywords-*|CompareKeywords-*|AdsInsights-*|Competitor-*|KeywordResearch-*)
            echo "  → Moving $f to inputs/sellersprite/"
            mv "$f" inputs/sellersprite/ 2>/dev/null || true ;;
    esac
done
for f in *.csv; do
    [ -f "$f" ] || continue
    case "$f" in
        BusinessReport*|SpSearchTerm*|SpCampaign*|FBAFee*)
            echo "  → Moving $f to inputs/seller-central/"
            mv "$f" inputs/seller-central/ 2>/dev/null || true ;;
    esac
done

# Extract SellerSprite zips from project root or Downloads
for zip in "$PROJECT"/sellersprite-export-table*.zip "$HOME/Downloads"/sellersprite-export-table*.zip; do
    [ -f "$zip" ] && echo "📦 Extracting: $(basename "$zip")" && unzip -o "$zip" -d "$PROJECT/inputs/sellersprite/" 2>/dev/null || true
done

# Copy Seller Central CSVs from Downloads if not already present
for csv in "$HOME/Downloads"/BusinessReport*.csv "$HOME/Downloads"/SpSearchTerm*.csv "$HOME/Downloads"/SpCampaign*.csv "$HOME/Downloads"/FBAFee*.csv; do
    [ -f "$csv" ] && echo "📋 Copying: $(basename "$csv")" && cp -n "$csv" "$PROJECT/inputs/seller-central/" 2>/dev/null || true
done

# Install Python deps
echo "📦 Installing Python dependencies..."
pip3 install pandas openpyxl xlrd --quiet --break-system-packages 2>/dev/null \
  || pip3 install pandas openpyxl xlrd --quiet 2>/dev/null \
  || pip install pandas openpyxl xlrd --quiet 2>/dev/null \
  || true

# Install Playwright for data collection automation
echo "📦 Installing Playwright..."
pip3 install playwright --quiet --break-system-packages 2>/dev/null \
  || pip3 install playwright --quiet 2>/dev/null \
  || true
python3 -m playwright install chromium 2>/dev/null || true

# Report
SS=$(find "$PROJECT/inputs/sellersprite" -name "*.xlsx" 2>/dev/null | wc -l | tr -d ' ')
SC=$(find "$PROJECT/inputs/seller-central" -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "✅ Ready: $PROJECT"
echo "   SellerSprite: $SS files | Seller Central: $SC files"
echo ""
