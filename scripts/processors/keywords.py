"""
Keyword library builder — merge, dedup, classify 6000+ keywords.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def _classify_primary(row, config):
    """Assign primary classification (一级分类)."""
    kw = str(row.get('keyword', '')).lower()
    searches = row.get('monthly_searches') or 0

    # Check brand keywords first
    cls = config.get('keyword_classification', {})
    brand_names = cls.get('primary', {}).get('竞品品牌词', {}).get('brand_names', [])
    for brand in brand_names:
        if brand.lower() in kw:
            return '竞品品牌词'

    if searches > 50000:
        return '大词'
    elif 10000 <= searches <= 50000:
        return '核心关键词'
    elif 3000 <= searches < 10000:
        return '功能/场景/人群+核心词'
    else:
        return '长尾词'


def _classify_secondary(row, config):
    """Assign secondary classification (二级分类)."""
    searches = row.get('monthly_searches') or 0
    purchase_rate = row.get('purchase_rate') or 0
    organic_rank = row.get('organic_rank')
    ppc_bid = row.get('ppc_bid') or 0
    purchase_volume = row.get('purchase_volume') or 0

    # 主力出单词
    if purchase_rate > 0.02 and organic_rank is not None and organic_rank <= 20:
        return '主力出单词'

    # 潜力测试词
    if searches > 5000 and organic_rank is not None and organic_rank > 50:
        return '潜力测试词'

    # 流量词/防御词
    if searches > 10000 and purchase_rate < 0.005:
        return '流量词/防御词'

    # 无效词/亏损词
    if purchase_volume == 0 and organic_rank is None and ppc_bid > 2.00:
        return '无效词/亏损词'

    return '常规词'


def _search_tier(searches):
    """Assign search volume tier."""
    if searches > 50000:
        return 'S级'
    elif searches > 10000:
        return 'A级'
    elif searches > 3000:
        return 'B级'
    elif searches > 1000:
        return 'C级'
    else:
        return 'D级'


def build_keyword_library(expand_dfs, mining_dfs, compare_dfs, research_dfs,
                          search_term_df, config):
    """
    Merge all keyword sources, deduplicate, classify.
    Returns DataFrame with 6000+ keywords.
    """
    all_kw = []

    # 1. ExpandKeywords (Reverse ASIN)
    for df in expand_dfs:
        if df.empty:
            continue
        cols = ['keyword', 'monthly_searches', 'purchase_volume', 'purchase_rate',
                'ppc_bid', 'organic_rank', 'sponsored_rank', 'aba_rank',
                'traffic_share', 'impressions', 'clicks', 'source_file']
        available = [c for c in cols if c in df.columns]
        sub = df[available].copy()
        sub['data_source'] = 'ExpandKeywords'
        all_kw.append(sub)

    # 2. KeywordMining
    for df in mining_dfs:
        if df.empty:
            continue
        cols = ['keyword', 'monthly_searches', 'purchase_volume', 'purchase_rate',
                'ppc_bid', 'aba_rank', 'growth_rate', 'source_file']
        available = [c for c in cols if c in df.columns]
        sub = df[available].copy()
        sub['data_source'] = 'KeywordMining'
        all_kw.append(sub)

    # 3. KeywordResearch — filter by relevance to product seed keywords/title
    # Build relevance token set from config seeds + product title
    seed_tokens = set()
    if config:
        for seed in config.get('collection', {}).get('mining_seeds', []):
            if seed and seed.strip():
                seed_tokens.update(seed.lower().split())
        title = config.get('active_product', {}).get('title', '')
        # Add meaningful title words (skip short/common words)
        skip_words = {'for', 'and', 'the', 'with', 'from', 'this', 'that', 'size',
                      'new', 'hot', 'best', 'top', 'pack', 'set', 'day', 'gift',
                      'plus', 'small', 'medium', 'large', 'color', 'inch'}
        for word in title.lower().split():
            clean = ''.join(c for c in word if c.isalpha())
            if len(clean) > 3 and clean not in skip_words:
                seed_tokens.add(clean)
        # Add brand name
        brand = config.get('active_product', {}).get('brand', '')
        if brand:
            seed_tokens.update(brand.lower().split())

    for df in research_dfs:
        if df.empty:
            continue
        cols = ['keyword', 'monthly_searches', 'purchase_volume', 'purchase_rate',
                'aba_rank', 'growth_rate', 'source_file']
        available = [c for c in cols if c in df.columns]
        sub = df[available].copy()

        # Filter: only keep keywords with at least one token matching seed/title
        if seed_tokens and 'keyword' in sub.columns:
            before = len(sub)
            def _is_relevant(kw):
                kw_tokens = set(str(kw).lower().split())
                return bool(kw_tokens & seed_tokens)
            sub = sub[sub['keyword'].apply(_is_relevant)]
            logger.info(f"KeywordResearch filtered: {before} → {len(sub)} rows (seed tokens: {len(seed_tokens)})")

        sub['data_source'] = 'KeywordResearch'
        all_kw.append(sub)

    # 4. CompareKeywords (Traffic Comparison)
    for df in (compare_dfs or []):
        if df.empty:
            continue
        cols = ['keyword', 'click_share', 'source_file']
        available = [c for c in cols if c in df.columns]
        sub = df[available].copy()
        if 'click_share' in sub.columns:
            sub = sub.rename(columns={'click_share': 'traffic_share'})
        sub['data_source'] = 'CompareKeywords'
        all_kw.append(sub)

    # 5. Search Term Report
    if search_term_df is not None and not search_term_df.empty:
        st_records = []
        for _, row in search_term_df.iterrows():
            term = row.get('Customer Search Term')
            if pd.isna(term):
                continue
            st_records.append({
                'keyword': str(term).strip(),
                'data_source': 'SearchTermReport',
                'ad_spend': row.get('Spend'),
                'ad_sales': row.get('7 Day Total Sales'),
                'ad_acos': row.get('Total Advertising Cost of Sales (ACoS)'),
                'ad_orders': row.get('7 Day Total Orders (#)'),
                'ad_clicks': row.get('Clicks'),
                'ad_impressions': row.get('Impressions'),
            })
        if st_records:
            all_kw.append(pd.DataFrame(st_records))

    if not all_kw:
        logger.warning("No keyword data found")
        return pd.DataFrame()

    # Merge all
    merged = pd.concat(all_kw, ignore_index=True)

    # Deduplicate: keep row with highest monthly_searches per keyword
    merged['keyword_lower'] = merged['keyword'].str.lower().str.strip()
    merged['monthly_searches'] = pd.to_numeric(merged['monthly_searches'], errors='coerce').fillna(0)

    # Aggregate: for each keyword, take the max values and combine sources
    agg_funcs = {
        'keyword': 'first',
        'monthly_searches': 'max',
        'purchase_volume': 'max',
        'purchase_rate': 'max',
        'ppc_bid': 'max',
        'organic_rank': 'min',  # best rank
        'sponsored_rank': 'min',
        'aba_rank': 'min',
        'traffic_share': 'max',
        'data_source': lambda x: ' | '.join(sorted(set(str(v) for v in x if pd.notna(v)))),
    }
    # Only aggregate columns that exist
    available_agg = {k: v for k, v in agg_funcs.items() if k in merged.columns}
    deduped = merged.groupby('keyword_lower', as_index=False).agg(available_agg)

    # Merge ad data if available
    if 'ad_spend' in merged.columns:
        ad_data = merged[merged['ad_spend'].notna()].groupby('keyword_lower').agg({
            'ad_spend': 'sum',
            'ad_sales': 'sum',
            'ad_acos': 'mean',
            'ad_orders': 'sum',
            'ad_clicks': 'sum',
            'ad_impressions': 'sum',
        }).reset_index()
        deduped = deduped.merge(ad_data, on='keyword_lower', how='left')

    # Compute CPA (cost per acquisition)
    if 'ad_spend' in deduped.columns and 'ad_orders' in deduped.columns:
        deduped['cpa'] = deduped.apply(
            lambda r: r['ad_spend'] / r['ad_orders'] if pd.notna(r.get('ad_orders')) and r.get('ad_orders', 0) > 0 else None,
            axis=1
        )

    # Classify
    deduped['一级分类'] = deduped.apply(lambda r: _classify_primary(r, config), axis=1)
    deduped['二级分类'] = deduped.apply(lambda r: _classify_secondary(r, config), axis=1)
    deduped['搜索层级'] = deduped['monthly_searches'].apply(_search_tier)

    # Determine usage
    def _usage(row):
        cls1 = row['一级分类']
        cls2 = row['二级分类']
        if cls2 == '主力出单词':
            return '标题+广告主推'
        elif cls2 == '潜力测试词':
            return '广告测试'
        elif cls2 == '流量词/防御词':
            return '广告防御'
        elif cls2 == '无效词/亏损词':
            return '否定词候选'
        elif cls1 == '竞品品牌词':
            return '竞品定向'
        elif cls1 == '大词':
            return '引流+品牌曝光'
        elif cls1 == '核心关键词':
            return '标题+描述+广告'
        else:
            return '长尾补充'

    deduped['用途'] = deduped.apply(_usage, axis=1)

    # Sort by monthly searches descending
    deduped = deduped.sort_values('monthly_searches', ascending=False).reset_index(drop=True)

    # Drop helper column
    deduped = deduped.drop(columns=['keyword_lower'], errors='ignore')

    logger.info(f"Keyword library built: {len(deduped)} unique keywords")
    return deduped
