# Input File Acquisition Checklist

> COLD POSH — Silk Blouses for Women (B0BTRTZNS8)

This checklist covers every file the pipeline needs, how to export it, and where to put it.

---

## ASINs to Export

| Role | ASIN | Brand | Notes |
|------|------|-------|-------|
| **Own** | B0BTRTZNS8 | COLD POSH | Main listing ASIN |
| C1 | B0BTRVJHSG | COLD POSH | Sibling (V-neck ruffle) |
| C2 | B07NKYR7VY | LilySilk | Primary benchmark |
| C3 | B0CM3FXDNW | Generic | 93% silk blend |
| C4 | B099MRVV9D | Chigant | Budget satin silk |

---

## Section A: File Acquisition

### SellerSprite Exports → `inputs/sellersprite/`

#### 1. ExpandKeywords (Reverse ASIN / 反查ASIN)
- **Pattern:** `ExpandKeywords-*.xlsx`
- **Steps:**
  1. Open SellerSprite → Reverse ASIN (反查ASIN)
  2. Enter ASIN → Set US marketplace + Last 30 days
  3. Click Search → Wait for results
  4. Click Export to download .xlsx
- **Run for:** Own ASIN + each competitor ASIN (5 total exports)
- **Expected:** ~32 columns, 500-3000 rows per export
- **Feeds:** 竞品分析, 词库整理, Gap分析
- **Notes:** Multi-sheet format. Export all sheets. This is the most important SellerSprite file.

#### 2. KeywordMining (关键词挖掘)
- **Pattern:** `KeywordMining-*.xlsx`
- **Steps:**
  1. Open SellerSprite → Keyword Mining (关键词挖掘)
  2. Enter seed keyword (e.g., "silk blouse")
  3. Set US marketplace + Last 30 days → Search
  4. Click Export to download .xlsx
- **Run for:** Each seed keyword:
  - silk blouse, silk blouses for women, mulberry silk blouse
  - silk button down shirt women, 100% silk blouse
  - silk shirts for women, women silk top elegant
  - pure silk blouse long sleeve, silk blouse for work
  - luxury silk shirt women
- **Expected:** ~33 columns, up to 3000 rows
- **Feeds:** 词库整理

#### 3. CompareKeywords (Traffic Comparison / 流量对比)
- **Pattern:** `CompareKeywords-*.xlsx`
- **Steps:**
  1. Open SellerSprite → Traffic Comparison (流量对比)
  2. Enter own ASIN + all competitor ASINs
  3. Click Compare → Wait for results
  4. Click Export to download .xlsx
- **Run for:** Once (all ASINs in one export)
- **Expected:** Multi-ASIN alternating column format
- **Feeds:** 流量入口

#### 4. AdsInsights (广告洞察)
- **Pattern:** `AdsInsights-*.xlsx`
- **Steps:**
  1. Open SellerSprite → Ads Insights (广告洞察)
  2. Enter own ASIN → Search
  3. Select time range (recommend 8-12 weeks)
  4. Click Export to download .xlsx
- **Run for:** Own ASIN only
- **Expected:** Pivot format (5 columns per week block)
- **Feeds:** 广告指标监测
- **⚠ Important:** This is a pivot table format, not a standard table. Row 0 = week headers, Row 1 = ASIN, Row 3+ = data. Each sheet = different variant.

#### 5. Competitor (竞品调研)
- **Pattern:** `Competitor-*.xlsx`
- **Steps:**
  1. Open SellerSprite → Competitor Research (竞品调研)
  2. Enter category or keyword to find competitors
  3. Filter results as needed
  4. Click Export to download .xlsx
- **Run for:** Once per category search
- **Expected:** ~64 columns, up to 3000 rows
- **Feeds:** 竞品分析

#### 6. KeywordResearch (关键词调研)
- **Pattern:** `KeywordResearch-*.xlsx`
- **Steps:**
  1. Open SellerSprite → Keyword Research (关键词调研)
  2. Select market/category
  3. Click Export to download .xlsx
- **Run for:** Once per market
- **Feeds:** 词库整理

---

### Seller Central Reports → `inputs/seller-central/`

#### 7. BusinessReport (Business Report)
- **Pattern:** `BusinessReport*.csv`
- **Steps:**
  1. Log in to Seller Central → Reports → Business Reports
  2. Select "By Child Item" (Detail Page Sales and Traffic by Child Item)
  3. Set date range: Last 30 days
  4. Click Download (.csv)
- **Feeds:** 竞品分析, 产品清单, 定价策略
- **⚠ Gotchas:**
  - Column names have trailing spaces (e.g., `"7 Day Total Sales "`)
  - Currency values have `$` prefix (e.g., `"$989.91"`)
  - Percentages have `%` suffix (e.g., `"98.2%"`)

#### 8. SpSearchTerm (SP Search Term Report)
- **Pattern:** `SpSearchTerm*.csv`
- **Steps:**
  1. Log in to Seller Central → Advertising → Reports
  2. Click "Create Report"
  3. Select Report type: "Search term"
  4. Select Report period: Last 30-60 days
  5. Generate and download .csv
- **Feeds:** 广告指标监测, 词库整理
- **⚠ Gotchas:** Same trailing spaces and `$` prefix issues. `"--"` = null/zero.

#### 9. SpCampaign (SP Campaign Report)
- **Pattern:** `SpCampaign*.csv`
- **Steps:**
  1. Log in to Seller Central → Advertising → Reports
  2. Click "Create Report"
  3. Select Report type: "Campaign"
  4. Select Report period: Last 30-60 days
  5. Generate and download .csv
- **Feeds:** 广告指标监测, 定价策略

#### 10. FBAFee (FBA Fee Preview)
- **Pattern:** `FBAFee*.csv`
- **Steps:**
  1. Log in to Seller Central → Reports → Fulfillment
  2. Find "Fee Preview" report
  3. Click Download
- **Feeds:** 定价策略
- **⚠ Gotchas:** `"--"` = null values. Fees vary by product dimensions.

---

### Ignore Rules

Skip any files containing:
- `flashlight` in the filename
- `B08D66HCXW` in the filename

These belong to a different product line.

---

## Section B: Data Flow

```
File                    → Parser                    → Processor(s)         → Dashboard Tab(s)
─────────────────────────────────────────────────────────────────────────────────────────────
ExpandKeywords-*.xlsx   → parse_expand_keywords()   → keywords, competitors, gap → 竞品分析, 词库整理, Gap分析
KeywordMining-*.xlsx    → parse_keyword_mining()    → keywords            → 词库整理
CompareKeywords-*.xlsx  → parse_compare_keywords()  → keywords, traffic   → 词库整理, 流量入口
AdsInsights-*.xlsx      → parse_ads_insights()      → ads                 → 广告指标监测
Competitor-*.xlsx       → parse_competitor()         → competitors         → 竞品分析
KeywordResearch-*.xlsx  → parse_keyword_research()  → keywords            → 词库整理
BusinessReport*.csv     → parse_business_report()   → competitors, pricing → 竞品分析, 产品清单, 定价策略
SpSearchTerm*.csv       → parse_search_term_report() → ads, keywords      → 广告指标监测, 词库整理
SpCampaign*.csv         → parse_campaign_report()    → ads, pricing       → 广告指标监测, 定价策略
FBAFee*.csv             → parse_fba_fee_preview()   → pricing             → 定价策略
```

### Required vs Optional

**Critical (pipeline needs these):**
- `BusinessReport*.csv` — own product sales/traffic data
- `ExpandKeywords-*.xlsx` — keyword rankings for own + competitor ASINs

**Enhances output (recommended):**
- `KeywordMining-*.xlsx` — expands keyword library
- `SpSearchTerm*.csv` — ad search term performance
- `SpCampaign*.csv` — campaign-level ad data
- `FBAFee*.csv` — accurate FBA fee data for pricing

**Optional (supplements):**
- `CompareKeywords-*.xlsx` — traffic comparison
- `AdsInsights-*.xlsx` — weekly ad trends
- `Competitor-*.xlsx` — broader competitor data
- `KeywordResearch-*.xlsx` — market-level keywords

---

## Section C: Metric Glossary

### Keyword Classification Rules

**Primary Classification (一级分类):**

| Category | Condition | Description |
|----------|-----------|-------------|
| 大词 | monthly_searches > 50,000 | High-volume, high-competition head terms |
| 核心关键词 | 10,000 ≤ monthly_searches ≤ 50,000 | Main target keywords |
| 功能/场景/人群词 | 3,000 ≤ monthly_searches < 10,000 | Niche modifier keywords |
| 长尾词 | monthly_searches < 3,000 OR word_count ≥ 4 | Long-tail, low competition |
| 竞品品牌词 | keyword contains brand name | Competitor brand terms |

**Secondary Classification (二级分类):**

| Category | Condition | Description |
|----------|-----------|-------------|
| 主力出单词 | purchase_rate > 2% AND organic_rank ≤ 20 | Currently converting — protect these |
| 潜力测试词 | monthly_searches > 5,000 AND organic_rank > 50 | Opportunity — test with ads |
| 流量/防御词 | monthly_searches > 10,000 AND purchase_rate < 0.5% | Traffic but no conversion — monitor |
| 无效/亏损词 | no purchases AND no rank AND PPC bid > $2.00 | Losing money — consider pausing |

### Ad Metrics

| Metric | Formula | Healthy | Watch | Action |
|--------|---------|---------|-------|--------|
| ACoS | ad spend ÷ ad sales × 100% | < 20% | 20-30% | > 30% |
| TACoS | total ad spend ÷ total revenue × 100% | < 15% | 15-25% | > 25% |
| CTR | clicks ÷ impressions × 100% | > 0.5% | 0.3-0.5% | < 0.3% |
| CVR | orders ÷ clicks × 100% | > 10% | 5-10% | < 5% |

### Gap Analysis

| Gap Type | Meaning | Priority Multiplier | Action |
|----------|---------|---------------------|--------|
| MISSING | Competitor ranks, we don't | 1.0x (highest) | Create new campaigns, optimize listing |
| CATCHUP | Both rank, competitor ahead | 0.5x (medium) | Increase ad spend, improve content |
| DEFEND | We rank well, competitor weak | 0.2x (low) | Maintain position, defensive ads |

**Priority Score Formula:**
```
priority_score = monthly_searches × purchase_rate × gap_type_multiplier
```

### Pricing Tab Colors

| Cell Color | Meaning |
|------------|---------|
| Blue font + Yellow background | User-editable input (cost assumptions) |
| Green text | Positive profit/margin |
| Red text | Negative profit/loss |

### ACoS Color Coding

| Color | Range | Meaning |
|-------|-------|---------|
| Green | < 20% | Healthy — profitable ads |
| Orange | 20-30% | Watch — optimize targeting |
| Red | > 30% | Action needed — reduce waste |
