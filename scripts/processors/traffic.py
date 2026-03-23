"""
Traffic source analysis — channel strategy matrix.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def build_traffic_sources(keyword_library, search_term_df, compare_dfs, config, **kwargs):
    """
    Build traffic channel strategy matrix.
    Returns list of traffic channel dicts.
    """
    channels = []

    # 1. Organic Search (自然搜索)
    organic_keywords = []
    if keyword_library is not None and not keyword_library.empty:
        organic = pd.DataFrame()
        if 'organic_rank' in keyword_library.columns:
            organic = keyword_library[
                (keyword_library['organic_rank'].notna()) &
                (keyword_library['organic_rank'] <= 50)
            ]

        # Fallback: if no organic_rank data, use top keywords by monthly_searches
        if organic.empty and 'monthly_searches' in keyword_library.columns:
            organic = keyword_library.nlargest(20, 'monthly_searches')

        if not organic.empty:
            top_organic = organic.nlargest(10, 'monthly_searches')
            organic_keywords = [
                f"{row['keyword']}({int(row['monthly_searches'])})"
                for _, row in top_organic.iterrows()
            ]

    channels.append({
        'channel': '自然搜索',
        'source': 'Amazon Search',
        'strategy': f"核心词: {', '.join(organic_keywords[:5]) if organic_keywords else 'N/A'}. "
                    "优化标题、五点、后台Search Terms. 目标: 核心词进入Top 20."
    })

    # 2. SP Ads (广告流量)
    ad_keywords = []
    if search_term_df is not None and not search_term_df.empty:
        if '7 Day Total Sales' in search_term_df.columns:
            top_ads = search_term_df.nlargest(10, '7 Day Total Sales')
            def _fmt_acos(val):
                if pd.isna(val) or val == 0:
                    return '0%'
                v = float(val) if not isinstance(val, float) else val
                if v > 1:
                    v = v / 100
                return f"{v:.0%}"

            ad_keywords = [
                f"{row['Customer Search Term']}(ACoS:{_fmt_acos(row.get('Total Advertising Cost of Sales (ACoS)', 0))})"
                for _, row in top_ads.iterrows()
                if pd.notna(row.get('Customer Search Term'))
            ]

    channels.append({
        'channel': 'SP广告',
        'source': 'Sponsored Products',
        'strategy': f"高转化词: {', '.join(ad_keywords[:5]) if ad_keywords else 'N/A'}. "
                    "Auto+Exact双投策略, 每日预算$25, 目标ACoS<25%."
    })

    # 3. SB/SBV Ads
    product_title = config.get('active_product', {}).get('title', '')
    category = config.get('active_product', {}).get('category', '')
    # Build a short product descriptor for strategy text
    product_desc = category.split('>')[-1].strip() if category else (product_title.split(',')[0] if product_title else 'product')
    channels.append({
        'channel': 'SB/SBV广告',
        'source': 'Sponsored Brands / Video',
        'strategy': f"品牌视频广告展示产品特色. 产品类型: {product_desc}. 目标: 提升品牌知名度, CTR>0.5%."
    })

    # 4. Competitor Traffic (竞品流量)
    child_asins = config.get('active_product', {}).get('child_asins', [])
    parent_asin = config.get('active_product', {}).get('asin_parent', '')
    my_asins = set(child_asins + [parent_asin])
    comp_keywords = []
    for df in (compare_dfs or []):
        if df.empty:
            continue
        if 'keyword' in df.columns:
            if 'asin' in df.columns:
                comp_only = df[~df['asin'].isin(my_asins)]
            elif 'is_mine' in df.columns:
                comp_only = df[~df['is_mine']]
            else:
                continue
            if not comp_only.empty:
                comp_keywords.extend(comp_only['keyword'].head(5).tolist())

    # Deduplicate while preserving order
    seen = set()
    comp_keywords_dedup = []
    for kw in comp_keywords:
        kw_lower = kw.lower().strip()
        if kw_lower not in seen:
            seen.add(kw_lower)
            comp_keywords_dedup.append(kw)

    # Build primary competitor targeting text from config
    primary_comp_text = ''
    competitors_cfg = config.get('competitors', {})
    for slot in ['C2', 'C1', 'C3', 'C4']:
        comp_info = competitors_cfg.get(slot, {}) if isinstance(competitors_cfg.get(slot), dict) else {}
        comp_b = comp_info.get('brand', '')
        comp_a = comp_info.get('asin', '')
        if comp_b and comp_a:
            primary_comp_text = f" 重点定向{comp_b}({comp_a})."
            break

    channels.append({
        'channel': '竞品定向',
        'source': 'Product Targeting Ads',
        'strategy': f"定向竞品ASIN投放. 竞品词: {', '.join(comp_keywords_dedup[:5]) if comp_keywords_dedup else 'N/A'}."
                    f"{primary_comp_text}"
    })

    # 5. Brand Traffic
    brand_name = config.get('active_product', {}).get('brand', '') or 'Unknown'
    seed = config.get('seed_keywords', [])
    brand_kws = [kw for kw in seed if brand_name.lower() in kw.lower()] if seed else []
    channels.append({
        'channel': '品牌搜索',
        'source': 'Brand Search',
        'strategy': f"品牌词: {brand_name}. 确保品牌词搜索占据首位. 建设品牌旗舰店."
    })

    # 6. External Traffic
    channels.append({
        'channel': '站外引流',
        'source': 'Social / Influencer',
        'strategy': f"Instagram/TikTok相关领域博主合作. Pinterest优质图片引流. 产品: {product_desc}. 目标: 站外流量占比5%+."
    })

    # 7. Deal/Coupon Traffic
    channels.append({
        'channel': '促销活动',
        'source': 'Deals / Coupons',
        'strategy': "设置10-15% Coupon提升转化. Lightning Deal参与Prime Day/黑五. "
                    "Subscribe & Save暂不适用(非复购品)."
    })

    logger.info(f"Traffic sources built: {len(channels)} channels")
    return channels
