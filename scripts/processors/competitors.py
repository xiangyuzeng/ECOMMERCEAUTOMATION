"""
Competitor comparison matrix builder.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def build_competitor_matrix(competitor_dfs, expand_dfs, business_df, config):
    """
    Build vertical comparison: my product vs 4 competitors.
    Returns dict with product data for each ASIN.
    """
    active = config.get('active_product', {})
    competitors_cfg = config.get('competitors', {})
    # Competitors may be a dict (keyed by C1, C2, ...) or a list
    competitors = list(competitors_cfg.values()) if isinstance(competitors_cfg, dict) else competitors_cfg
    my_asin = active.get('asin_listing', '')
    parent_asin = active.get('asin_parent', '')

    # Merge all competitor data
    all_comp = pd.concat(competitor_dfs, ignore_index=True) if competitor_dfs else pd.DataFrame()

    # Build matrix
    products = []

    # My product from config + business report
    my_data = {
        'asin': my_asin,
        'brand': active.get('brand', '') or 'Unknown',
        'title': active.get('title', ''),
        'price': active.get('current_price'),
        'rating': active.get('rating'),
        'ratings_count': active.get('review_count'),
        'category_bsr': active.get('bsr'),
        'subcategory_bsr': active.get('subcategory_bsr'),
        'launch_date': active.get('launch_date'),
        'variation_count': active.get('variant_count'),
        'is_mine': True,
    }

    # Enrich from competitor exports (our product may appear in the competitor scan)
    if not all_comp.empty and 'asin' in all_comp.columns:
        for lookup_asin in [my_asin, parent_asin]:
            if not lookup_asin:
                continue
            match = all_comp[all_comp['asin'] == lookup_asin]
            if not match.empty:
                row = match.iloc[0]
                if my_data.get('price') is None:
                    my_data['price'] = row.get('price')
                if not my_data.get('monthly_sales'):
                    my_data['monthly_sales'] = row.get('monthly_sales')
                if not my_data.get('monthly_revenue'):
                    my_data['monthly_revenue'] = row.get('monthly_revenue')
                if not my_data.get('fba_margin'):
                    my_data['fba_margin'] = row.get('fba_margin')
                if not my_data.get('category_bsr'):
                    my_data['category_bsr'] = row.get('category_bsr')
                if not my_data.get('subcategory_bsr'):
                    my_data['subcategory_bsr'] = row.get('subcategory_bsr')
                if not my_data.get('launch_date'):
                    my_data['launch_date'] = row.get('launch_date')
                if not my_data.get('variation_count'):
                    my_data['variation_count'] = row.get('variation_count')
                break

    # Enrich from business report
    if business_df is not None and not business_df.empty:
        parent_rows = business_df[business_df['(Parent) ASIN'] == parent_asin]
        if not parent_rows.empty:
            my_data['monthly_sales'] = parent_rows['Units Ordered'].sum()
            my_data['monthly_revenue'] = parent_rows['Ordered Product Sales'].sum()
            my_data['sessions'] = parent_rows['Sessions'].sum()

    # Get top 5 keywords from expand data
    my_expand = [df for df in expand_dfs if not df.empty and
                 df.get('source_asin', pd.Series()).iloc[0] == parent_asin]
    if not my_expand:
        # Try matching by listing ASIN
        my_expand = [df for df in expand_dfs if not df.empty and
                     (df.get('source_asin', pd.Series()).iloc[0] in [my_asin, parent_asin])]

    if my_expand:
        sort_col = 'traffic_share' if 'traffic_share' in my_expand[0].columns and my_expand[0]['traffic_share'].notna().any() else 'monthly_searches'
        exp_df = my_expand[0].copy()
        exp_df[sort_col] = pd.to_numeric(exp_df[sort_col], errors='coerce').fillna(0)
        top5 = exp_df.nlargest(5, sort_col)['keyword'].tolist()
        my_data['top_keywords'] = ', '.join(str(k) for k in top5 if pd.notna(k))
        my_data['keyword_count'] = len(my_expand[0])
    else:
        my_data['top_keywords'] = 'N/A'
        my_data['keyword_count'] = 0

    products.append(my_data)

    # Competitors
    for comp in competitors:
        if not isinstance(comp, dict):
            continue
        comp_asin = comp.get('asin', comp.get('asin_listing', ''))
        comp_data = {
            'asin': comp_asin,
            'brand': comp.get('brand', ''),
            'label': comp.get('label', ''),
            'is_mine': False,
        }

        # Pre-fill from config if available (fallback data)
        for cfg_key, data_key in [('price', 'price'), ('rating', 'rating'),
                                   ('ratings_count', 'ratings_count'),
                                   ('title', 'title')]:
            if cfg_key in comp:
                comp_data[data_key] = comp[cfg_key]

        # Look up in competitor exports (overwrites config values if found)
        if not all_comp.empty and 'asin' in all_comp.columns:
            match = all_comp[all_comp['asin'] == comp_asin]
            if not match.empty:
                row = match.iloc[0]
                comp_data['title'] = row.get('title', '') or comp_data.get('title', '')
                comp_data['price'] = row.get('price') or comp_data.get('price')
                comp_data['rating'] = row.get('rating') or comp_data.get('rating')
                comp_data['ratings_count'] = row.get('ratings_count') or comp_data.get('ratings_count')
                comp_data['monthly_sales'] = row.get('monthly_sales')
                comp_data['monthly_revenue'] = row.get('monthly_revenue')
                comp_data['category_bsr'] = row.get('category_bsr')
                comp_data['subcategory_bsr'] = row.get('subcategory_bsr')
                comp_data['launch_date'] = row.get('launch_date')
                comp_data['variation_count'] = row.get('variation_count')
                comp_data['fba_margin'] = row.get('fba_margin')
                comp_data['image_url'] = row.get('image_url')

        # Get top keywords from expand data for this competitor
        comp_expand = [df for df in expand_dfs if not df.empty and
                       df.get('source_asin', pd.Series()).iloc[0] == comp_asin]
        if comp_expand:
            sort_col = 'traffic_share' if 'traffic_share' in comp_expand[0].columns and comp_expand[0]['traffic_share'].notna().any() else 'monthly_searches'
            cexp_df = comp_expand[0].copy()
            cexp_df[sort_col] = pd.to_numeric(cexp_df[sort_col], errors='coerce').fillna(0)
            top5 = cexp_df.nlargest(5, sort_col)['keyword'].tolist()
            comp_data['top_keywords'] = ', '.join(str(k) for k in top5 if pd.notna(k))
            comp_data['keyword_count'] = len(comp_expand[0])
        else:
            comp_data['top_keywords'] = 'N/A'
            comp_data['keyword_count'] = 0

        products.append(comp_data)

    logger.info(f"Competitor matrix built: {len(products)} products")
    return products
