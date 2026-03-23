# ECOMMERCEAUTOMATION — AI-Powered Amazon Operations

> **Claude Code master prompt** — designed for `--dangerously-skip-permissions` mode.
> Project root: `~/Desktop/ECOMMERCEAUTOMATION/`
> Custom commands: `/build` (full build), `/run` (execute pipeline), `/dashboard` (start web UI)

---

## EXECUTION MODE

This project is built to run with:
```bash
claude --dangerously-skip-permissions
```

**Rules for autonomous execution:**
- Do NOT stop to ask questions. Make reasonable decisions and keep going.
- Do NOT ask for confirmation between steps. Execute sequentially.
- If a file is missing, skip it, log the gap, continue with remaining files.
- If a parse error occurs, try a fallback approach, log the error, continue.
- If a build error occurs, fix it inline and retry. Max 3 retries per step.
- Always produce partial output rather than crashing.
- Write all errors to `logs/pipeline.log`.
- At the end, print a summary of what succeeded and what failed.

---

## WHAT THIS BUILDS

```
INPUT:  SellerSprite .xlsx exports + Seller Central .csv reports (in inputs/)
OUTPUT: (1) 运营方案.xlsx — 8-tab Excel dashboard (in outputs/)
        (2) run_summary.md — strategic insights (in outputs/)
        (3) *.json — processed data for web dashboard (in processed/)
        (4) Next.js web dashboard (in dashboard/)
```

---

## PROJECT STRUCTURE

```
~/Desktop/ECOMMERCEAUTOMATION/
├── .claude/
│   ├── settings.json              ← Permission pre-approvals
│   └── commands/
│       ├── build.md               ← /build slash command
│       ├── run.md                 ← /run slash command
│       └── dashboard.md           ← /dashboard slash command
├── CLAUDE.md                      ← THIS FILE
├── config.json                    ← Product config (ASIN, competitors, costs, styling)
├── data_schemas.md                ← Exact column structures from real files
├── setup.sh                       ← Directory scaffolding + deps
├── requirements.txt               ← Python deps
├── README.md
├── INPUT_CHECKLIST.md
├── collector_prompts.md           ← Manual browser automation fallback prompts
│
├── scripts/
│   ├── generate_report.py         ← MAIN ENTRY POINT — runs full pipeline
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── sellersprite.py        ← Parse all SellerSprite .xlsx formats
│   │   └── seller_central.py      ← Parse all Seller Central .csv formats
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── keywords.py            ← Merge, dedup, classify 6000+ keywords
│   │   ├── competitors.py         ← Build competitor comparison matrix
│   │   ├── gap_analysis.py        ← Keyword gap vs LilySilk
│   │   ├── pricing.py             ← 4-scenario pricing model
│   │   ├── ads.py                 ← Ad monitoring + weekly tracking
│   │   └── traffic.py             ← Traffic source analysis
│   └── exporters/
│       ├── __init__.py
│       ├── excel_writer.py        ← Openpyxl 8-tab workbook generator
│       └── json_writer.py         ← JSON for dashboard
│
├── dashboard/                     ← Next.js 14 web dashboard
│   ├── package.json
│   ├── next.config.js
│   └── app/
│       ├── layout.jsx
│       ├── page.jsx               ← All UI: tabs + components
│       └── data.js                ← Imports processed JSON
│
├── inputs/
│   ├── sellersprite/              ← Drop .xlsx exports here
│   └── seller-central/            ← Drop .csv reports here
│
├── processed/                     ← JSON output for dashboard
├── outputs/                       ← Final xlsx + summary
└── logs/                          ← Pipeline logs
```

---

## FULL BUILD SEQUENCE

When the user says `/build` or "build everything", execute ALL steps below without stopping:

### Step 1: Scaffold
```bash
chmod +x setup.sh && ./setup.sh
pip3 install pandas openpyxl xlrd --quiet --break-system-packages 2>/dev/null || pip3 install pandas openpyxl xlrd --quiet
```

### Step 2: Verify Inputs
```bash
echo "=== SellerSprite ===" && ls -la inputs/sellersprite/*.xlsx 2>/dev/null | wc -l
echo "=== Seller Central ===" && ls -la inputs/seller-central/*.csv 2>/dev/null | wc -l
```
If inputs/ directories are empty, check if data files are in the project root and move them. Check for zip files and extract them.

### Step 3: Build Parsers
Create `scripts/parsers/sellersprite.py` — must handle ALL these file types:

| Pattern | Module | Parser Function | Key Complexity |
|---|---|---|---|
| `ExpandKeywords-*.xlsx` | Reverse ASIN | `parse_expand_keywords(filepath)` | 32 cols, multi-sheet |
| `KeywordMining-*.xlsx` | Keyword Mining | `parse_keyword_mining(filepath)` | 33 cols, up to 3000 rows |
| `CompareKeywords-*.xlsx` | Traffic Comparison | `parse_compare_keywords(filepath)` | Multi-ASIN alternating columns |
| `AdsInsights-*.xlsx` | Ads Insights | `parse_ads_insights(filepath)` | **PIVOT FORMAT** — reshape required |
| `Competitor-*.xlsx` | Competitor Research | `parse_competitor(filepath)` | 64 cols, up to 3000 rows |
| `KeywordResearch-*.xlsx` | Keyword Research | `parse_keyword_research(filepath)` | Standard table |

Create `scripts/parsers/seller_central.py` — must handle:

| Pattern | Function | Watch Out For |
|---|---|---|
| `BusinessReport*.csv` | `parse_business_report(filepath)` | $ in revenue, % in rates |
| `SpSearchTerm*.csv` | `parse_search_term_report(filepath)` | **Trailing spaces in column names!** |
| `SpCampaign*.csv` | `parse_campaign_report(filepath)` | Same trailing space issue |
| `FBAFee*.csv` | `parse_fba_fee_preview(filepath)` | "--" for null values |

**See `data_schemas.md` for exact column names and sample values.**

### Step 4: Build Processors
Create all processors in `scripts/processors/`. Each takes parsed DataFrames, returns processed data:

- `keywords.py` — `build_keyword_library(expand_dfs, mining_dfs, compare_dfs, research_df, search_term_df)` → 6000+ deduplicated, classified keywords
- `competitors.py` — `build_competitor_matrix(competitor_dfs, expand_dfs, business_df, config)` → 5 product comparison
- `gap_analysis.py` — `build_gap_analysis(my_expand_df, competitor_expand_df)` → MISSING/CATCHUP/DEFEND scored list
- `pricing.py` — `build_pricing_model(business_df, fba_df, campaign_df, config)` → per-variant P&L + 4 scenarios
- `ads.py` — `build_ads_monitoring(ads_insights_df, search_term_df, campaign_df)` → weekly tracking grid
- `traffic.py` — `build_traffic_sources(keyword_library, search_term_df, compare_dfs, config)` → channel strategy matrix

**Keyword classification rules** (from config.json):
```
一级分类:
  "大词"              → monthly_searches > 50,000
  "核心关键词"         → 10,000 ≤ monthly_searches ≤ 50,000
  "功能/场景/人群+核心词" → 3,000 ≤ monthly_searches < 10,000
  "长尾词"            → monthly_searches < 3,000 OR word_count ≥ 4
  "竞品品牌词"         → keyword contains brand name from config

二级分类:
  "主力出单词"   → purchase_rate > 0.02 AND organic_rank ≤ 20
  "潜力测试词"   → monthly_searches > 5,000 AND organic_rank > 50
  "流量词/防御词" → monthly_searches > 10,000 AND purchase_rate < 0.005
  "无效词/亏损词" → no purchases AND no rank AND ppc_bid > $2.00
```

### Step 5: Build Excel Writer
Create `scripts/exporters/excel_writer.py` — generates 8-tab workbook using openpyxl.

**CRITICAL RULES:**
- All calculated fields use **Excel formulas** (=B3*0.17, =SUM(), etc.), NOT Python values
- User-editable cells: blue font #0000FF + yellow fill #FFFF00
- Header: navy #1F4E79 fill, white bold Arial 11pt
- Body: Arial 10pt #2C3E50, alternating white/#F2F2F2 rows
- Borders: #BFBFBF thin all cells
- Freeze panes on header rows
- Auto-fit column widths (min 10, max 45)
- Conditional formatting on gap_type (MISSING=red, CATCHUP=orange, DEFEND=green)

**8 tabs (see detailed specs in TABS section below):**
1. 竞品分析 — vertical comparison matrix
2. 产品清单 — pricing model + listing audit
3. 词库整理 — keyword library with classification
4. 广告指标监测 — weekly tracking heatmap
5. 定价策略 — per-variant P&L table
6. 流量入口 — traffic channel strategy
7. 关键词Gap分析 — MISSING/CATCHUP/DEFEND analysis
8. 数据源日志 — file audit trail

### Step 6: Build Main Script
Create `scripts/generate_report.py` — the single entry point:
```python
# Pseudocode flow:
# 1. Load config.json
# 2. Scan inputs/ → classify files by pattern
# 3. Parse all SellerSprite .xlsx
# 4. Parse all Seller Central .csv
# 5. Run all processors (keywords, competitors, gap, pricing, ads, traffic)
# 6. Write Excel workbook → outputs/COLD_POSH_运营方案_YYYY-MM-DD.xlsx
# 7. Write JSON files → processed/*.json
# 8. Write run_summary.md → outputs/
# 9. Print completion summary
```

### Step 7: Run Pipeline
```bash
cd ~/Desktop/ECOMMERCEAUTOMATION && python3 scripts/generate_report.py
```
Verify output files exist and are non-empty.

### Step 8: Build Dashboard
Create Next.js 14 app in `dashboard/`:
- `package.json` with next, react, react-dom
- `next.config.js` with output: 'export' for static deploy
- `app/layout.jsx` — Inter + Noto Sans SC fonts, metadata
- `app/page.jsx` — full dashboard UI with 7 tabs
- `app/data.js` — load from `../processed/*.json`

**Dashboard tech rules:**
- NO Tailwind. Pure inline styles or CSS-in-JS only.
- ALWAYS light theme: #f8f9fb bg, #ffffff cards, #1f2937 text
- Accent: #0365C0 blue, #1A365D navy, #00A5A5 teal
- Tabs: Chinese labels with English subtitles
- Editable cost fields in 产品清单 and 定价策略 tabs
- Charts: use recharts (npm install recharts) or inline SVG

### Step 9: Build Dashboard
```bash
cd ~/Desktop/ECOMMERCEAUTOMATION/dashboard && npm install && npm run build
```

### Step 10: Completion Report
Print:
- ✅/❌ status of each step
- List of output files with sizes
- Count of keywords, competitors, gap keywords processed
- Any errors or gaps encountered
- Command to start dashboard: `cd dashboard && npm run dev`

---

## STORE CONTEXT

```yaml
Store:          COLD POSH (est. 2008)
Store URL:      https://www.amazon.com/stores/COLDPOSH/page/C28EB97E-1B2E-497C-B8B9-DD068BE581E6
Marketplace:    Amazon US
```

### Active Product
```yaml
ASIN (parent):   B0CSFTRMDF
ASIN (listing):  B0BTRTZNS8
Title:           COLD POSH Silk Blouses for Women Long Sleeve 100% Pure Silk Button Down Shirt
Category:        Clothing > Women > Button-Down Shirts
Price:           $109.99
Rating:          4.2 / 38 reviews
Child ASINs:     B0BTRTZNS8, B0BTRTLGMK, B0BTRKJ2CX, B0BVQKWK49
```

### Competitors
```yaml
C1: B0BTRVJHSG — COLD POSH sibling (V-neck ruffle silk)
C2: B07NKYR7VY — LilySilk (22mm, OEKO-TEX, primary benchmark, 102 keywords)
C3: B0CM3FXDNW — Generic (93% silk + 7% spandex blend)
C4: B099MRVV9D — Chigant (satin silk, budget tier)
```

### Seed Keywords
```
silk blouse, silk blouses for women, mulberry silk blouse, silk button down shirt women,
100% silk blouse, silk shirts for women, women silk top elegant, pure silk blouse long sleeve,
silk blouse for work, luxury silk shirt women
```

---

## INPUT FILE CLASSIFICATION

Scan `inputs/sellersprite/` and `inputs/seller-central/` and classify by filename:

| Filename Pattern | Source | Module |
|---|---|---|
| `KeywordMining-*.xlsx` | SellerSprite | Keyword Mining |
| `ExpandKeywords-*.xlsx` | SellerSprite | Reverse ASIN |
| `CompareKeywords-*.xlsx` | SellerSprite | Traffic Comparison |
| `AdsInsights-*.xlsx` | SellerSprite | Ads Insights |
| `Competitor-*.xlsx` | SellerSprite | Competitor Research |
| `KeywordResearch-*.xlsx` | SellerSprite | Keyword Research |
| `BusinessReport*.csv` | Seller Central | Business Report |
| `SpSearchTerm*.csv` | Seller Central | SP Search Term |
| `SpCampaign*.csv` | Seller Central | SP Campaign |
| `FBAFee*.csv` | Seller Central | FBA Fee Preview |

**IGNORE** files containing `flashlight` or `B08D66HCXW`.

---

## COLUMN TRANSLATIONS (SellerSprite CN→EN)

### ExpandKeywords / Reverse ASIN
| Raw | Normalized |
|---|---|
| Keyword / 关键词 | keyword |
| Click Share / 流量占比 | traffic_share |
| Keyword Distribution / 流量词类型 | traffic_source_type |
| Weekly Searches | weekly_searches |
| ABA Rank / Week / ABA周排名 | aba_rank |
| Searched / Month / 月搜索量 | monthly_searches |
| Purchase / Month / 购买量 | purchase_volume |
| Purchase Rate / 购买率 | purchase_rate |
| Impressions / 展示量 | impressions |
| Clicks / 点击量 | clicks |
| Products / 商品数 | product_count |
| SPR | spr |
| Title Density / 标题密度 | title_density |
| Organic Rank / 自然排名 | organic_rank |
| Sponsored Rank / 广告排名 | sponsored_rank |
| PPC Bid (Exact) / PPC价格 | ppc_bid |
| Demand to Supply Ratio / 需供比 | dsr |

### KeywordMining
| Raw | Normalized |
|---|---|
| Keyword | keyword |
| Relevancy | relevancy |
| Search Frequency Monthly Rank | aba_rank |
| Monthly Searches | monthly_searches |
| Monthly Sales | purchase_volume |
| Purchase Rate | purchase_rate |
| PPC Bid (Exact) | ppc_bid |
| Growth Rate | growth_rate |
| Total Click Share | click_share |
| Total Conversion Share | conversion_share |

### Competitor Research
| Raw | Normalized |
|---|---|
| ASIN | asin |
| Brand | brand |
| Product Title | title |
| Price($) | price |
| Sales | monthly_sales |
| Monthly Revenue($) | monthly_revenue |
| Rating | rating |
| Ratings | ratings_count |
| Category BSR | category_bsr |
| Sub-Category BSR | subcategory_bsr |
| Date Available | launch_date |
| Gross Margin | fba_margin |
| Variations Count | variation_count |
| Parent | parent_asin |
| Product Image | image_url |

---

## EXCEL TAB SPECIFICATIONS

### Tab 1: 竞品分析
Vertical comparison: rows = metrics, columns = my product + 4 competitors.
Row labels: 图片, 品牌, ASIN, 价格, 排名, 标题, 前五核心流量词, 评论数, 月销量, 月销售额, 上架日期, 变体数, FBA毛利率, 流量关键词数.
Data: Competitor exports + ExpandKeywords top 5 keywords + BusinessReport for own metrics.

### Tab 2: 产品清单
Section A — Cost model: rows = cost items, columns = 4 price scenarios ($45.99, $55.99, $65.99, $109.99).
Cost items: 成品成本, 包装, 头程运费, Amazon佣金(17%), FBA配送费, 月仓储费, 广告费(CPA), 退货损失, 总成本, 毛利润, 毛利率.
**ALL calculated cells = Excel formulas.** Editable cells = blue+yellow.
Section B — Variant sales from BusinessReport (sessions, CVR, revenue per child ASIN).

### Tab 3: 词库整理
Columns: 关键词, 一级分类, 二级分类, 搜索层级, 用途, 月搜索量, 搜索频率排名, 购买率, CPA, CPC, 自然排名, 广告排名, 广告花费, 广告ACoS, 数据来源.
6000+ rows sorted by monthly_searches desc. Auto-classified per rules above.

### Tab 4: 广告指标监测
Weekly heatmap: rows = top 5 keywords × 4 sub-rows (曝光/点击/订单/位置), columns = weeks.
Data: AdsInsights pivot + SpSearchTermReport.

### Tab 5: 定价策略
Columns: ASIN, MSKU, 销量, 销售额, 平均售价, 单位成本, 采购占比, 单位头程, 头程占比, 单位配送费, 配送费占比, 类目佣金, 佣金占比, 月仓储费, 月仓储费占比, 广告花费, ACoS, TACoS.
Per-row: each child ASIN from BusinessReport + FBAFeePreview + SpCampaignReport.
All 占比 = Excel formula (component ÷ 平均售价).

### Tab 6: 流量入口
| 流量入口 | 流量来源 | 方案 |
Auto-populate 方案 with actual keyword names + search volumes from 词库 data.

### Tab 7: 关键词Gap分析
Columns: keyword, my_rank, lilysilk_rank, gap_type, monthly_searches, purchase_rate, ppc_bid, priority_score, recommended_action.
Outer join my ExpandKeywords ↔ LilySilk ExpandKeywords.
priority_score = monthly_searches × purchase_rate × {MISSING:1.0, CATCHUP:0.5, DEFEND:0.2}.

### Tab 8: 数据源日志
Auto-generated: timestamp, source_file, source_type, module, records, feeds_tab, date_range, data_quality, notes.

---

## ADS INSIGHTS PIVOT PARSING (CRITICAL)

The AdsInsights file has a complex pivot structure. **Read data_schemas.md for full details.**

```
Row 0: Week headers — "week 10.2026 (03/08~03/14)" with empty cells between blocks
Row 1: ASIN per block
Row 2: Column sub-headers (not always present)
Row 3+: keyword | rank | organic_rank | aba_rank | monthly_searches (5 cols per week)
```

**Parse algorithm:**
1. `pd.read_excel(filepath, header=None)` — no header auto-detection
2. Scan row 0 for cells containing "week" → record column indices
3. Each week starts at that column index and spans 5 columns
4. For each week column and each data row (3+): extract keyword + 4 metrics
5. Output: long-format DataFrame (keyword, week, rank, organic_rank, aba_rank, monthly_searches)
6. Process ALL sheets (each sheet = different child ASIN variation)

---

## SELLER CENTRAL CSV GOTCHAS

1. **Trailing spaces in column names**: `"7 Day Total Sales "` (note trailing space). Always `.strip()` column names after reading.
2. **Currency strings**: `"$989.91"` → strip $ and , → float
3. **Percentage strings**: `"98.2%"` → strip % → float, then /100 if needed
4. **Dash for null**: `"--"` → None/NaN
5. **B2B columns**: Can be ignored (all zeros for this seller)

---

## DASHBOARD SPECS

Next.js 14, App Router. NO Tailwind. Pure inline styles.

```
Fonts:     Inter (body), JetBrains Mono (code/numbers), Noto Sans SC (Chinese)
BG:        #f8f9fb
Cards:     #ffffff, box-shadow: 0 1px 3px rgba(0,0,0,0.08)
Text:      #1f2937 primary, #6b7280 secondary
Accent:    #0365C0 blue, #1A365D navy, #00A5A5 teal
Success:   #22c55e
Warning:   #f59e0b
Danger:    #ef4444
```

7 tabs with Chinese label + English subtitle:
竞品分析 Competitors | 产品清单 Products | 词库整理 Keywords | 广告指标监测 Ads | 定价策略 Pricing | 流量入口 Traffic | Gap分析 Keyword Gap

Each tab loads data from `processed/*.json` via static import in `data.js`.

---

## HOW TO RUN

### First time (full build):
```bash
cd ~/Desktop/ECOMMERCEAUTOMATION
claude --dangerously-skip-permissions
# Then say: /build
```

### Re-run pipeline after new data:
```bash
cd ~/Desktop/ECOMMERCEAUTOMATION
claude --dangerously-skip-permissions
# Then say: /run
```

### Start dashboard:
```bash
cd ~/Desktop/ECOMMERCEAUTOMATION
claude --dangerously-skip-permissions
# Then say: /dashboard
```

### One-shot headless (CI-style):
```bash
cd ~/Desktop/ECOMMERCEAUTOMATION
claude -p --dangerously-skip-permissions "Read CLAUDE.md and config.json. Run /build."
```

---

## SWITCH TO DIFFERENT PRODUCT

1. Edit `config.json` → update `active_product`, `competitors`, `seed_keywords`
2. Drop new SellerSprite .xlsx into `inputs/sellersprite/`
3. Drop new Seller Central .csv into `inputs/seller-central/`
4. Run: `/run`

---

## ERROR HANDLING

- Missing file → skip, log to 数据源日志 tab, note in summary
- Missing column → fill with "N/A", log
- Data type error → attempt conversion, log failure, continue
- Empty export → note "0 records", skip
- Build error → fix inline, retry up to 3 times
- **NEVER crash.** Always produce partial output with clear gap notes.
