# ECOMMERCEAUTOMATION — Amazon AI-Powered Operations

Automated pipeline: raw SellerSprite + Seller Central data → 8-tab 运营方案 Excel + interactive web dashboard.

## Quick Start (Autonomous Mode)

```bash
# 1. Setup
cd ~/Desktop/ECOMMERCEAUTOMATION
chmod +x setup.sh && ./setup.sh

# 2. Drop data files
#    SellerSprite .xlsx → inputs/sellersprite/
#    Seller Central .csv → inputs/seller-central/

# 3. Build everything (autonomous — no permission prompts)
cd ~/Desktop/ECOMMERCEAUTOMATION
claude --dangerously-skip-permissions
# Type: /build

# 4. Or one-shot headless:
claude -p --dangerously-skip-permissions "Read CLAUDE.md. Run /build."
```

## Slash Commands

| Command | What It Does |
|---------|-------------|
| `/build` | Full build: scaffold → parse → process → Excel → dashboard |
| `/run` | Re-run pipeline only (skip dashboard build) |
| `/dashboard` | Build and start the web dashboard |

## Output

### 运营方案.xlsx (8 tabs)
1. **竞品分析** — 5 competitor deep-dives
2. **产品清单** — 4-scenario pricing model
3. **词库整理** — 6,000+ classified keywords
4. **广告指标监测** — Weekly PPC tracking grid
5. **定价策略** — Per-variant P&L with Excel formulas
6. **流量入口** — Traffic source strategy matrix
7. **关键词Gap分析** — Keyword gap vs competitors
8. **数据源日志** — Data audit trail

### Web Dashboard
Interactive version at `http://localhost:3000` — deploy to Vercel.

## Switch Products

1. Edit `config.json` → `active_product`, `competitors`, `seed_keywords`
2. Drop new data files in `inputs/`
3. Run: `/run`
