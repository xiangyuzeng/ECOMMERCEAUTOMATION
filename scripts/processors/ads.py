"""
Ads monitoring — weekly tracking heatmap from AdsInsights + SearchTerm data.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def build_ads_monitoring(ads_insights_df, search_term_df, campaign_df, config=None):
    """
    Build weekly tracking grid for top 5 keywords.
    Returns dict with 'heatmap', 'search_term_summary', 'campaign_summary'.
    Heatmap: top 5 keywords x 4 sub-rows (曝光/点击/订单/位置) x weeks.
    """
    search_term_summary = []
    campaign_summary = []

    # Build search term lookup for 曝光/点击/订单 per keyword
    st_lookup = {}
    if search_term_df is not None and not search_term_df.empty:
        for _, row in search_term_df.iterrows():
            term = row.get('Customer Search Term')
            if pd.isna(term):
                continue
            kw = str(term).strip().lower()
            st_lookup[kw] = {
                'impressions': row.get('Impressions', 0) or 0,
                'clicks': row.get('Clicks', 0) or 0,
                'orders': row.get('7 Day Total Orders (#)', 0) or 0,
            }
            search_term_summary.append({
                'keyword': str(term).strip(),
                'impressions': row.get('Impressions', 0),
                'clicks': row.get('Clicks', 0),
                'ctr': row.get('Click-Thru Rate (CTR)', 0),
                'cpc': row.get('Cost Per Click (CPC)', 0),
                'spend': row.get('Spend', 0),
                'sales': row.get('7 Day Total Sales', 0),
                'acos': row.get('Total Advertising Cost of Sales (ACoS)', 0),
                'orders': row.get('7 Day Total Orders (#)', 0),
                'units': row.get('7 Day Total Units (#)', 0),
                'cvr': row.get('7 Day Conversion Rate', 0),
            })

    # Build heatmap from AdsInsights
    heatmap = {'keywords': [], 'weeks': [], 'grid': {}}

    if ads_insights_df is not None and not ads_insights_df.empty:
        # Filter to primary product ASINs only (exclude competitor ad data)
        if config and 'asin' in ads_insights_df.columns:
            primary_asins = set()
            ap = config.get('active_product', {})
            for key in ['asin_parent', 'asin_listing']:
                val = ap.get(key, '')
                if val:
                    primary_asins.add(val)
            # Include child ASINs — AdsInsights often uses variation ASINs
            child_asins = ap.get('child_asins', [])
            if child_asins:
                primary_asins.update(child_asins)

            if primary_asins:
                my_ads = ads_insights_df[ads_insights_df['asin'].isin(primary_asins)]
                if not my_ads.empty:
                    logger.info(f"AdsInsights filtered to primary ASINs: {len(ads_insights_df)} → {len(my_ads)} rows")
                    ads_insights_df = my_ads
                else:
                    # Try matching by source_file — file named after our parent ASIN
                    parent = ap.get('asin_parent', '')
                    if parent and 'source_file' in ads_insights_df.columns:
                        my_ads = ads_insights_df[ads_insights_df['source_file'].str.contains(parent, na=False)]
                        if not my_ads.empty:
                            logger.info(f"AdsInsights filtered by source_file ({parent}): {len(ads_insights_df)} → {len(my_ads)} rows")
                            ads_insights_df = my_ads
                        else:
                            logger.warning(f"No AdsInsights match for product ASINs — using all data")

        # Get top 5 keywords by frequency across weeks
        kw_counts = ads_insights_df.groupby('keyword').size().sort_values(ascending=False)
        top_keywords = kw_counts.head(5).index.tolist()
        weeks = sorted(ads_insights_df['week'].unique())

        heatmap['keywords'] = top_keywords
        heatmap['weeks'] = weeks

        for kw in top_keywords:
            kw_data = ads_insights_df[ads_insights_df['keyword'] == kw]
            kw_lower = kw.lower().strip()
            st_info = st_lookup.get(kw_lower, {})

            grid_entry = {
                '曝光': {},
                '点击': {},
                '订单': {},
                '位置': {},
            }

            for week in weeks:
                week_data = kw_data[kw_data['week'] == week]
                if not week_data.empty:
                    row = week_data.iloc[0]
                    # 位置 from AdsInsights rank/organic_rank
                    rank_val = row.get('rank')
                    org_rank = row.get('organic_rank')
                    if pd.notna(rank_val):
                        grid_entry['位置'][week] = rank_val
                    elif pd.notna(org_rank):
                        grid_entry['位置'][week] = org_rank
                    else:
                        grid_entry['位置'][week] = None
                else:
                    grid_entry['位置'][week] = None

                # 曝光/点击/订单 from SearchTerm data (aggregate, not per-week)
                # Spread evenly across weeks as SearchTerm doesn't have weekly breakdown
                n_weeks = len(weeks) or 1
                if st_info:
                    grid_entry['曝光'][week] = round(st_info.get('impressions', 0) / n_weeks)
                    grid_entry['点击'][week] = round(st_info.get('clicks', 0) / n_weeks)
                    grid_entry['订单'][week] = round(st_info.get('orders', 0) / n_weeks)
                else:
                    # No search term data — use None (not 0) to distinguish "no data" from "zero"
                    grid_entry['曝光'][week] = None
                    grid_entry['点击'][week] = None
                    grid_entry['订单'][week] = None

            heatmap['grid'][kw] = grid_entry

    # Campaign summary
    if campaign_df is not None and not campaign_df.empty:
        for _, row in campaign_df.iterrows():
            campaign_summary.append({
                'campaign': row.get('Campaign Name', ''),
                'status': row.get('Campaign Status', ''),
                'budget': row.get('Campaign Budget Amount', 0),
                'impressions': row.get('Impressions', 0),
                'clicks': row.get('Clicks', 0),
                'spend': row.get('Spend', 0),
                'sales': row.get('7 Day Total Sales', 0),
                'acos': row.get('Total Advertising Cost of Sales (ACoS)', 0),
                'orders': row.get('7 Day Total Orders (#)', 0),
            })

    logger.info(f"Ads monitoring built: {len(heatmap['keywords'])} heatmap keywords, "
                f"{len(search_term_summary)} search terms, {len(campaign_summary)} campaigns")
    return {
        'heatmap': heatmap,
        'search_term_summary': search_term_summary,
        'campaign_summary': campaign_summary,
    }
