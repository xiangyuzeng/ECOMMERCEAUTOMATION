# Data Schemas — Column Structures from Real Files

> Ground truth for building parsers. Exact column names + sample values.

---

## SellerSprite: ExpandKeywords (Reverse ASIN)
**Pattern**: `ExpandKeywords-US-{ASIN}-batch(*)-{date}-{id}.xlsx`
**Main sheet**: first sheet (name contains ASIN). **Rows**: 39–102. **Cols**: 32.
```
Keyword, Amazon Choice, Click Share, Keyword Distribution, Weekly Searches,
Products, Related ASINs, ABA Rank / Week, Searched / Month, Purchase / Month,
Purchase Rate, Impressions, Clicks, SPR, Title Density, DSR,
Sponsored ASINs, PPC Bid (Broad), PPC Bid (Exact), PPC Bid (Phrase),
Suggested bid(Broad), Suggested bid(Exact), Organic Rank, Sponsored Rank,
Total Click Share, Total Conversion Share
```
Secondary sheets: "Unique Words" (word frequency), "ASIN", "Notes"

## SellerSprite: KeywordMining
**Pattern**: `KeywordMining-US-{keyword}-Last-30-days-{id}.xlsx`
**Main sheet**: `US-{keyword}({count})_`. **Rows**: 1,706–2,569. **Cols**: 33.
```
Keyword, Amazon Choice, Relevancy, Search Frequency Monthly Rank,
Search Frequency Weekly Rank, Monthly Searches, Monthly Sales,
Purchase Rate, Impressions, Clicks, SPR, Title Density,
PPC Bid (Broad), PPC Bid (Exact), PPC Bid (Phrase),
Products, DSR, Growth Rate, Total Click Share, Total Conversion Share,
Traffic Cost, ABA Rank, Word Count
```

## SellerSprite: Competitor Research
**Pattern**: `Competitor-US-Last-30-days-{id}.xlsx`
**Main sheet**: `Competitor-US-Last-30-days`. **Rows**: up to 3,000. **Cols**: 64.
```
ASIN, SKU, Product Overview, Brand, Brand Link, Product Title, URL,
Product Image, Parent, Category Path, Category, Label,
Category BSR, Category BSR Increase, Category BSR Growth,
Sub-Category BSR, Sub-Category BSR Growth, Price($), Price Change(%),
Monthly Revenue($), Revenue Growth, Sales, Sales Growth,
Variations, Variations Count, Q&A, Rating, Ratings, Ratings Rate,
Seller, Seller Country, Fulfillment, Weight, Dimension,
Date Available, Gross Margin, Buy Box, Has Coupon
```

## SellerSprite: CompareKeywords (Traffic Comparison)
**Pattern**: `CompareKeywords-US-{ASIN}-{date}-{id}.xlsx`
**Main sheet**: first (name has "Click Share Change"). **Rows**: 30–306. **Cols**: 18–20.
```
Keyword Phrase,
{ASIN1}(My), {ASIN1}Keywords type,
{ASIN2}, {ASIN2}Keywords type,
... (repeating per ASIN),
Competing Products
```
Click share values: "16.06%", "" (empty). Keywords type: "Highly searched", "Organic words", "SP ad words", "".

## SellerSprite: AdsInsights — PIVOT FORMAT (⚠️ complex)
**Pattern**: `AdsInsights-US-{ASIN}-{id}.xlsx`
**Sheets**: multiple per child ASIN (4-letter suffix).
```
Row 0: "week 10.2026 (03/08~03/14)" | empty | empty | empty | empty | "week 08.2026 ..." | ...
Row 1: "B0BTRTZNS8"                  | empty | empty | empty | empty | "B0BTRTZNS8"       | ...
Row 2: (sub-headers vary)
Row 3+: keyword | rank | organic_rank | aba_rank | monthly_searches | keyword | ...
```
Each week = 5-column block. Parse with `header=None`, scan Row 0 for "week", extract blocks.

## SellerSprite: KeywordResearch
**Pattern**: `KeywordResearch-US-{yearmonth}-{id}.xlsx`
**Main sheet**: `Keywords({count})`. **Rows**: 1,373. **Cols**: 27.
```
Keyword, ABA rank, Monthly Searches, Growth Rate, Monthly Sales,
Purchase Rate, Impressions, Clicks, Products, DSR, SPR,
Title density, Total Click Share, Total Conversion Share, Traffic Cost
```

---

## Seller Central: BusinessReport CSV (19 rows)
```
(Parent) ASIN, (Child) ASIN, Title, Sessions, Session Percentage,
Page Views, Page Views Percentage, Buy Box Percentage, Units Ordered,
Units Ordered - B2B, Unit Session Percentage, Unit Session Percentage - B2B,
Ordered Product Sales, Ordered Product Sales - B2B,
Total Order Items, Total Order Items - B2B
```
Types: Sessions=int, Buy Box="98.2%" string, Revenue="$989.91" string.

## Seller Central: SpSearchTermReport CSV (49 rows)
⚠️ **Trailing spaces in column names**: `"7 Day Total Sales "`, `"ACoS "`
```
Date, Campaign Name, Ad Group Name, Targeting, Match Type,
Customer Search Term, Impressions, Clicks, Click-Thru Rate (CTR),
Cost Per Click (CPC), Spend, 7 Day Total Sales ,
Total Advertising Cost of Sales (ACoS) ,
Total Return on Advertising Spend (RoAS),
7 Day Total Orders (#), 7 Day Total Units (#), 7 Day Conversion Rate
```

## Seller Central: SpCampaignReport CSV (9 rows)
Same trailing-space issue. Same column patterns as search term but campaign-level.

## Seller Central: FBAFeePreview CSV (13 rows)
```
sku, fnsku, asin, product-name, product-group, brand, fulfilled-by,
your-price, longest-side, median-side, shortest-side,
product-size-tier, estimated-fee-total, estimated-referral-fee-per-unit,
expected-fulfillment-fee-per-unit, estimated-monthly-storage-fee
```
Types: fees=float (no $ prefix), "--" for null.
