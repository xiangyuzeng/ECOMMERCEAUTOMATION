# Browser Automation Prompts — Manual Fallback

> Use with Claude in Chrome while OpenClaw automation is being built.

---

## SellerSprite Collection

**Logged into**: https://www.sellersprite.com

```
You are in my logged-in SellerSprite session.

RULES: Marketplace=US. No full-page screenshots. No billing buttons. Export limit: 40/day.

MY PRODUCT: B0CSFTRMDF (parent), B0BTRTZNS8 (child). Brand: COLD POSH.
COMPETITORS: B0BTRVJHSG, B07NKYR7VY, B0CM3FXDNW, B099MRVV9D
KEYWORDS: silk blouse, silk blouses for women, mulberry silk blouse

Do one task at a time. Wait for "proceed" between tasks:
1. Check export log at /v2/export-log
2. Reverse ASIN B0CSFTRMDF → Export
3. Reverse ASIN B07NKYR7VY → Export
4. Traffic Comparison all 5 ASINs → Export
5. KeywordMining "silk blouse" → Export
6. KeywordMining "mulberry silk" → Export
7. KeywordMining "silk clothes" → Export
8. Competitor Research "silk blouse" → Export
9. AdsInsights B0CSFTRMDF → Export
10. Keyword Research Clothing/Silk → Export
```

---

## Seller Central Collection

**Logged into**: https://sellercentral.amazon.com

```
You are in my logged-in Seller Central. READ-ONLY mission.

RULES: Never modify anything. No billing buttons. Marketplace=US.
BRAND: COLD POSH. KEY ASIN: B0CSFTRMDF / B0BTRTZNS8.

Tasks (one at a time):
1. Business Report (Child Item) — Reports→Business Reports→By ASIN→Child Item, 60 days, CSV
2. SP Search Term — Advertising→Reports→Create→SP→Search term, 60 days, CSV
3. SP Campaign — Same page→Create→SP→Campaign, 60 days, CSV
4. FBA Fee Preview — Reports→Fulfillment→Fee Preview→Request Download, CSV
```

After download, move files to: `~/Desktop/ECOMMERCEAUTOMATION/inputs/seller-central/`
Then run: `cd ~/Desktop/ECOMMERCEAUTOMATION && claude --dangerously-skip-permissions` → `/run`
