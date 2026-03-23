"""
Keyword gap analysis — MISSING/CATCHUP/DEFEND scoring vs competitor.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def build_gap_analysis(my_expand_df, competitor_expand_df, config=None):
    """
    Outer join my ExpandKeywords ↔ competitor ExpandKeywords.
    Returns DataFrame with gap_type, priority_score, recommended_action.
    """
    if my_expand_df is None or my_expand_df.empty:
        logger.warning("No data for my product in gap analysis")
        my_expand_df = pd.DataFrame(columns=['keyword', 'organic_rank', 'monthly_searches',
                                              'purchase_rate', 'ppc_bid'])

    if competitor_expand_df is None or competitor_expand_df.empty:
        logger.warning("No competitor data for gap analysis")
        competitor_expand_df = pd.DataFrame(columns=['keyword', 'organic_rank', 'monthly_searches',
                                                      'purchase_rate', 'ppc_bid'])

    # Derive competitor label from config
    comp_brand = 'Competitor'
    if config:
        # Try C2 first (primary benchmark), then C1
        competitors = config.get('competitors', {})
        for slot in ['C2', 'C1', 'C3', 'C4']:
            brand = competitors.get(slot, {}).get('brand', '') if isinstance(competitors.get(slot), dict) else ''
            if brand:
                comp_brand = brand
                break

    comp_rank_col = f'{comp_brand}_rank'

    # Both empty — return empty result immediately
    if my_expand_df.empty and competitor_expand_df.empty:
        logger.warning("Both my and competitor data are empty — skipping gap analysis")
        return pd.DataFrame(columns=['keyword', 'my_rank', comp_rank_col, 'gap_type',
                                      'monthly_searches', 'purchase_rate', 'ppc_bid',
                                      'priority_score', 'recommended_action'])

    # Normalize keywords for join
    my = my_expand_df.copy()
    comp = competitor_expand_df.copy()

    # Ensure keyword column is string before .str operations
    my['keyword'] = my['keyword'].astype(str)
    comp['keyword'] = comp['keyword'].astype(str)

    my['kw_lower'] = my['keyword'].str.lower().str.strip()
    comp['kw_lower'] = comp['keyword'].str.lower().str.strip()

    # Ensure required columns exist
    for col in ['organic_rank', 'monthly_searches', 'purchase_rate', 'ppc_bid']:
        if col not in my.columns:
            my[col] = None
        if col not in comp.columns:
            comp[col] = None

    # Deduplicate each side
    my_dedup = my.sort_values('monthly_searches', ascending=False).drop_duplicates('kw_lower', keep='first')
    comp_dedup = comp.sort_values('monthly_searches', ascending=False).drop_duplicates('kw_lower', keep='first')

    # Track which keywords came from which side
    my_dedup['_in_my'] = True
    comp_dedup['_in_comp'] = True

    # Outer join
    my_cols = [c for c in ['kw_lower', 'keyword', 'organic_rank', 'monthly_searches',
                            'purchase_rate', 'ppc_bid', '_in_my'] if c in my_dedup.columns]
    comp_cols = [c for c in ['kw_lower', 'organic_rank', 'monthly_searches',
                              'purchase_rate', 'ppc_bid', '_in_comp'] if c in comp_dedup.columns]

    merged = my_dedup[my_cols].merge(
        comp_dedup[comp_cols],
        on='kw_lower', how='outer', suffixes=('_my', '_comp')
    )

    # Fill keyword from either side, ensure string type
    merged['keyword'] = merged['keyword'].fillna(merged['kw_lower']).astype(str)
    merged['_in_my'] = merged['_in_my'].fillna(False)
    merged['_in_comp'] = merged['_in_comp'].fillna(False)

    # Check if organic_rank has any real data
    has_rank_data = False
    if 'organic_rank_my' in merged.columns:
        has_rank_data = merged['organic_rank_my'].notna().any()
    if not has_rank_data and 'organic_rank_comp' in merged.columns:
        has_rank_data = merged['organic_rank_comp'].notna().any()

    # Determine gap type
    def _gap_type(row):
        in_my = row.get('_in_my', False)
        in_comp = row.get('_in_comp', False)

        if has_rank_data:
            my_rank = row.get('organic_rank_my')
            comp_rank = row.get('organic_rank_comp')
            has_my = pd.notna(my_rank)
            has_comp = pd.notna(comp_rank)

            if not has_my and has_comp:
                return 'MISSING'
            elif has_my and has_comp:
                if my_rank > comp_rank:
                    return 'CATCHUP'
                else:
                    return 'DEFEND'
            elif has_my and not has_comp:
                return 'DEFEND'
            else:
                # Fall through to membership-based logic
                pass

        # Membership-based gap type (when organic_rank unavailable)
        if in_comp and not in_my:
            return 'MISSING'
        elif in_my and in_comp:
            return 'CATCHUP'
        elif in_my and not in_comp:
            return 'DEFEND'
        else:
            return 'MISSING'

    merged['gap_type'] = merged.apply(_gap_type, axis=1)

    # Use best available monthly searches
    merged['monthly_searches'] = merged['monthly_searches_my'].fillna(merged['monthly_searches_comp']).fillna(0)
    merged['purchase_rate'] = merged['purchase_rate_my'].fillna(merged['purchase_rate_comp']).fillna(0)
    merged['ppc_bid'] = merged['ppc_bid_my'].fillna(merged['ppc_bid_comp']).fillna(0)

    # Priority score = monthly_searches × purchase_rate × weight
    weights = {'MISSING': 1.0, 'CATCHUP': 0.5, 'DEFEND': 0.2}
    merged['priority_score'] = merged.apply(
        lambda r: r['monthly_searches'] * r['purchase_rate'] * weights.get(r['gap_type'], 0.5),
        axis=1
    )

    # Recommended action
    def _action(row):
        gt = row['gap_type']
        score = row['priority_score']
        if gt == 'MISSING':
            if score > 100:
                return '立即投放广告+埋词标题'
            else:
                return '广告测试+后台Search Terms'
        elif gt == 'CATCHUP':
            if score > 50:
                return '加大广告预算+优化listing'
            else:
                return '持续监测+广告覆盖'
        else:  # DEFEND
            if score > 50:
                return '保持广告位+监控排名'
            else:
                return '维持现状'

    merged['recommended_action'] = merged.apply(_action, axis=1)

    # Rename and select columns
    result = merged[['keyword', 'organic_rank_my', 'organic_rank_comp',
                      'gap_type', 'monthly_searches', 'purchase_rate',
                      'ppc_bid', 'priority_score', 'recommended_action']].copy()
    result.columns = ['keyword', 'my_rank', comp_rank_col, 'gap_type',
                       'monthly_searches', 'purchase_rate', 'ppc_bid',
                       'priority_score', 'recommended_action']

    # Filter out competitor brand names from gap results
    brand_names = []
    if config:
        brand_names = [b.lower() for b in config.get('keyword_classification', {}).get('brand_names', [])]
        brand_names += [config.get('active_product', {}).get('brand', '').lower()]
        competitors = config.get('competitors', {})
        comp_list = competitors.values() if isinstance(competitors, dict) else competitors
        for comp in comp_list:
            brand = comp.get('brand', '').lower() if isinstance(comp, dict) else ''
            if brand:
                brand_names.append(brand)
    if brand_names:
        brand_names = [b for b in brand_names if b]
        if not result.empty:
            result['keyword'] = result['keyword'].astype(str)
            result = result[~result['keyword'].str.lower().isin(brand_names)]

    # Sort by priority score descending
    result = result.sort_values('priority_score', ascending=False).reset_index(drop=True)

    logger.info(f"Gap analysis built: {len(result)} keywords "
                f"(MISSING: {(result['gap_type']=='MISSING').sum()}, "
                f"CATCHUP: {(result['gap_type']=='CATCHUP').sum()}, "
                f"DEFEND: {(result['gap_type']=='DEFEND').sum()})")
    return result
