"""
SellerSprite .xlsx parsers — handles all 6 file formats.
"""
import os
import pandas as pd
import re
import logging

logger = logging.getLogger(__name__)


def _is_empty_file(filepath):
    """Return True if file is missing or 0 bytes."""
    try:
        return os.path.getsize(filepath) == 0
    except OSError:
        return True

# Column normalization maps
EXPAND_COLS = {
    'Keyword': 'keyword', '关键词': 'keyword', 'Keyword Phrase': 'keyword',
    'Click Share': 'traffic_share', '流量占比': 'traffic_share',
    'Keyword Distribution': 'traffic_source_type', '流量词类型': 'traffic_source_type',
    'Keywords type': 'traffic_source_type',
    'Weekly Searches': 'weekly_searches',
    'Estimated Weekly Impressions': 'weekly_searches',
    'ABA Rank / Week': 'aba_rank', 'ABA周排名': 'aba_rank',
    'Weekly ABA Rank': 'aba_rank',
    'Searched / Month': 'monthly_searches', '月搜索量': 'monthly_searches',
    'Monthly Searches': 'monthly_searches',
    'Purchase / Month': 'purchase_volume', '购买量': 'purchase_volume',
    'Monthly Purchase': 'purchase_volume',
    'Purchase Rate': 'purchase_rate', '购买率': 'purchase_rate',
    'Conversion': 'purchase_rate',
    'Impressions': 'impressions', '展示量': 'impressions',
    'Clicks': 'clicks', '点击量': 'clicks',
    'Products': 'product_count', '商品数': 'product_count',
    'SPR': 'spr',
    'Title Density': 'title_density', '标题密度': 'title_density',
    'Title density': 'title_density',
    'DSR': 'dsr', '需供比': 'dsr', 'Demand to Supply Ratio': 'dsr',
    'Organic Rank': 'organic_rank', '自然排名': 'organic_rank',
    'Sponsored Rank': 'sponsored_rank', '广告排名': 'sponsored_rank',
    'PPC Bid (Exact)': 'ppc_bid', 'PPC价格': 'ppc_bid', 'PPC bid': 'ppc_bid',
    'PPC': 'ppc_bid',
    'PPC Bid (Broad)': 'ppc_bid_broad',
    'PPC Bid (Phrase)': 'ppc_bid_phrase',
    'Suggested bid': 'suggested_bid',
    'Related ASINs': 'related_asins',
    'Sponsored ASINs': 'sponsored_asins',
    'Amazon Choice': 'amazon_choice',
    'Total Click Share': 'total_click_share',
    'Total Conversion Share': 'total_conversion_share',
    'Suggested bid(Broad)': 'suggested_bid_broad',
    'Suggested bid(Exact)': 'suggested_bid_exact',
}

MINING_COLS = {
    'Keyword': 'keyword',
    'Amazon Choice': 'amazon_choice',
    'Relevancy': 'relevancy',
    'Search Frequency Monthly Rank': 'aba_rank',
    'Search Frequency Weekly Rank': 'aba_rank_weekly',
    'Monthly Searches': 'monthly_searches',
    'Monthly Sales': 'purchase_volume',
    'Purchase Rate': 'purchase_rate',
    'Impressions': 'impressions',
    'Clicks': 'clicks',
    'SPR': 'spr',
    'Title Density': 'title_density',
    'PPC Bid (Broad)': 'ppc_bid_broad',
    'PPC Bid (Exact)': 'ppc_bid',
    'PPC Bid (Phrase)': 'ppc_bid_phrase',
    'Products': 'product_count',
    'DSR': 'dsr',
    'Growth Rate': 'growth_rate',
    'Total Click Share': 'total_click_share',
    'Total Conversion Share': 'total_conversion_share',
    'Traffic Cost': 'traffic_cost',
    'ABA Rank': 'aba_rank',
    'Word Count': 'word_count',
}

COMPETITOR_COLS = {
    'ASIN': 'asin',
    'Brand': 'brand',
    'Product Title': 'title',
    'Price($)': 'price',
    'Sales': 'monthly_sales',
    'Monthly Revenue($)': 'monthly_revenue',
    'Rating': 'rating',
    'Ratings': 'ratings_count',
    'Category BSR': 'category_bsr',
    'Sub-Category BSR': 'subcategory_bsr',
    'Date Available': 'launch_date',
    'Gross Margin': 'fba_margin',
    'Variations Count': 'variation_count',
    'Parent': 'parent_asin',
    'Product Image': 'image_url',
    'Category': 'category',
    'Seller': 'seller',
    'Seller Country': 'seller_country',
    'Fulfillment': 'fulfillment',
    'Revenue Growth': 'revenue_growth',
    'Sales Growth': 'sales_growth',
}

RESEARCH_COLS = {
    'Keyword': 'keyword',
    'ABA rank': 'aba_rank', 'ABA Rank': 'aba_rank',
    'Monthly Searches': 'monthly_searches',
    'Growth Rate': 'growth_rate',
    'Monthly Sales': 'purchase_volume',
    'Purchase Rate': 'purchase_rate',
    'Impressions': 'impressions',
    'Clicks': 'clicks',
    'Products': 'product_count',
    'DSR': 'dsr',
    'SPR': 'spr',
    'Title density': 'title_density',
    'Total Click Share': 'total_click_share',
    'Total Conversion Share': 'total_conversion_share',
    'Traffic Cost': 'traffic_cost',
}


def _clean_pct(val):
    """Convert percentage string to float."""
    if pd.isna(val) or val == '' or val == '--':
        return None
    if isinstance(val, str):
        val = val.strip().replace('%', '').replace(',', '')
        try:
            return float(val) / 100.0
        except ValueError:
            return None
    return float(val)


def _clean_numeric(val):
    """Convert numeric string to float."""
    if pd.isna(val) or val == '' or val == '--':
        return None
    if isinstance(val, str):
        val = val.strip().replace(',', '').replace('$', '')
        try:
            return float(val)
        except ValueError:
            return None
    return float(val)


def _clean_rank_array(val):
    """Convert a rank array string like '[0,0,0,13,0]' to a single value.

    AdsInsights stores daily rank values as 7-element arrays (one per day of the week).
    Strategy: return the last non-zero value (most recent daily rank).
    If all zeros → None (no ranking that week).
    If not an array string → delegate to _clean_numeric.
    """
    if pd.isna(val) or val == '' or val == '--':
        return None
    if isinstance(val, str) and val.strip().startswith('[') and val.strip().endswith(']'):
        try:
            inner = val.strip()[1:-1]
            nums = [int(x.strip()) for x in inner.split(',')]
            # Return the last non-zero value (most recent day with data)
            for n in reversed(nums):
                if n > 0:
                    return float(n)
            return None  # All zeros = no ranking recorded
        except (ValueError, IndexError):
            return _clean_numeric(val)
    return _clean_numeric(val)


def _normalize_columns(df, col_map):
    """Rename columns using map, strip whitespace from names.
    Avoids duplicate target names (first match wins)."""
    df.columns = [c.strip() for c in df.columns]
    rename = {}
    used_targets = set()
    for raw, norm in col_map.items():
        if raw in df.columns and norm not in used_targets:
            rename[raw] = norm
            used_targets.add(norm)
    df = df.rename(columns=rename)
    return df


def _extract_asin_from_filename(filepath):
    """Extract ASIN from filename pattern."""
    match = re.search(r'-(B[A-Z0-9]{9,})-', str(filepath))
    return match.group(1) if match else None


def parse_expand_keywords(filepath):
    """Parse ExpandKeywords (Reverse ASIN) xlsx. Returns DataFrame."""
    if _is_empty_file(filepath):
        logger.warning(f"Skipping empty file: {os.path.basename(filepath)}")
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(filepath)
        # Use first sheet (contains ASIN data)
        sheet_name = xl.sheet_names[0]
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        df = _normalize_columns(df, EXPAND_COLS)

        # Clean numeric columns
        for col in ['monthly_searches', 'purchase_volume', 'weekly_searches',
                     'impressions', 'clicks', 'product_count', 'spr']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        for col in ['purchase_rate', 'traffic_share']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_pct)

        for col in ['ppc_bid', 'ppc_bid_broad', 'ppc_bid_phrase']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        for col in ['organic_rank', 'sponsored_rank', 'aba_rank', 'title_density']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        # Tag source ASIN
        asin = _extract_asin_from_filename(filepath)
        df['source_asin'] = asin
        df['source_file'] = str(filepath).split('/')[-1]

        logger.info(f"Parsed ExpandKeywords: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse ExpandKeywords {filepath}: {e}")
        return pd.DataFrame()


def parse_keyword_mining(filepath):
    """Parse KeywordMining xlsx. Returns DataFrame."""
    if _is_empty_file(filepath):
        logger.warning(f"Skipping empty file: {os.path.basename(filepath)}")
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(filepath)
        sheet_name = xl.sheet_names[0]
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        df = _normalize_columns(df, MINING_COLS)

        for col in ['monthly_searches', 'purchase_volume', 'impressions',
                     'clicks', 'product_count', 'spr']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        for col in ['purchase_rate', 'growth_rate']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_pct)

        for col in ['ppc_bid', 'ppc_bid_broad', 'ppc_bid_phrase']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        df['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed KeywordMining: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse KeywordMining {filepath}: {e}")
        return pd.DataFrame()


def parse_compare_keywords(filepath):
    """Parse CompareKeywords (Traffic Comparison) xlsx. Returns DataFrame."""
    if _is_empty_file(filepath):
        logger.warning(f"Skipping empty file: {os.path.basename(filepath)}")
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(filepath)
        sheet_name = xl.sheet_names[0]
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        df.columns = [str(c).strip() for c in df.columns]

        # First column is always the keyword phrase
        keyword_col = df.columns[0]
        records = []

        # Parse alternating ASIN columns
        # Columns: Keyword Phrase, {ASIN1}(My), {ASIN1}Keywords type, {ASIN2}, {ASIN2}Keywords type, ...
        asin_cols = []
        i = 1
        while i < len(df.columns):
            col_name = df.columns[i]
            # Extract ASIN from column name
            asin_match = re.search(r'(B[A-Z0-9]{9,})', col_name)
            if asin_match:
                asin = asin_match.group(1)
                is_my = '(My)' in col_name or 'My' in col_name
                share_col = df.columns[i]
                type_col = df.columns[i + 1] if i + 1 < len(df.columns) else None
                asin_cols.append({
                    'asin': asin,
                    'is_mine': is_my,
                    'share_col': share_col,
                    'type_col': type_col
                })
                i += 2
            else:
                i += 1

        for _, row in df.iterrows():
            keyword = row[keyword_col]
            if pd.isna(keyword) or str(keyword).strip() == '':
                continue
            for ac in asin_cols:
                share = _clean_pct(row.get(ac['share_col']))
                kw_type = row.get(ac['type_col']) if ac['type_col'] else None
                records.append({
                    'keyword': str(keyword).strip(),
                    'asin': ac['asin'],
                    'is_mine': ac['is_mine'],
                    'click_share': share,
                    'keyword_type': kw_type if not pd.isna(kw_type) else None,
                })

        result = pd.DataFrame(records)
        result['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed CompareKeywords: {filepath} → {len(result)} rows")
        return result
    except Exception as e:
        logger.error(f"Failed to parse CompareKeywords {filepath}: {e}")
        return pd.DataFrame()


def parse_ads_insights(filepath):
    """Parse AdsInsights pivot xlsx. Returns long-format DataFrame."""
    if _is_empty_file(filepath):
        logger.warning(f"Skipping empty file: {os.path.basename(filepath)}")
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(filepath)
        all_records = []

        for sheet_name in xl.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
            if df.empty or len(df) < 4:
                continue

            # Row 0: week headers
            row0 = df.iloc[0]
            # Row 1: ASIN per block
            row1 = df.iloc[1]

            # Find week column positions
            week_blocks = []
            for col_idx in range(len(row0)):
                cell = row0.iloc[col_idx]
                if isinstance(cell, str) and 'week' in cell.lower():
                    # Extract week info
                    week_str = cell.strip()
                    asin_val = row1.iloc[col_idx] if col_idx < len(row1) else None
                    asin_str = str(asin_val).strip() if not pd.isna(asin_val) else sheet_name
                    week_blocks.append({
                        'week': week_str,
                        'asin': asin_str,
                        'start_col': col_idx,
                    })

            # Parse data rows (row 3+)
            for _, block in enumerate(week_blocks):
                start = block['start_col']
                for row_idx in range(3, len(df)):
                    row = df.iloc[row_idx]
                    keyword = row.iloc[start] if start < len(row) else None
                    if pd.isna(keyword) or str(keyword).strip() == '':
                        continue

                    record = {
                        'keyword': str(keyword).strip(),
                        'week': block['week'],
                        'asin': block['asin'],
                        'sheet': sheet_name,
                        'rank': _clean_rank_array(row.iloc[start + 1]) if start + 1 < len(row) else None,
                        'organic_rank': _clean_rank_array(row.iloc[start + 2]) if start + 2 < len(row) else None,
                        'aba_rank': _clean_numeric(row.iloc[start + 3]) if start + 3 < len(row) else None,
                        'monthly_searches': _clean_numeric(row.iloc[start + 4]) if start + 4 < len(row) else None,
                    }
                    all_records.append(record)

        result = pd.DataFrame(all_records)
        result['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed AdsInsights: {filepath} → {len(result)} rows")
        return result
    except Exception as e:
        logger.error(f"Failed to parse AdsInsights {filepath}: {e}")
        return pd.DataFrame()


def parse_competitor(filepath):
    """Parse Competitor Research xlsx. Returns DataFrame."""
    if _is_empty_file(filepath):
        logger.warning(f"Skipping empty file: {os.path.basename(filepath)}")
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(filepath)
        sheet_name = xl.sheet_names[0]
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        df = _normalize_columns(df, COMPETITOR_COLS)

        for col in ['price', 'monthly_revenue', 'monthly_sales', 'ratings_count',
                     'category_bsr', 'subcategory_bsr', 'variation_count']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        for col in ['rating', 'fba_margin']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        df['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed Competitor: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse Competitor {filepath}: {e}")
        return pd.DataFrame()


def parse_keyword_research(filepath):
    """Parse KeywordResearch xlsx. Returns DataFrame."""
    if _is_empty_file(filepath):
        logger.warning(f"Skipping empty file: {os.path.basename(filepath)}")
        return pd.DataFrame()
    try:
        xl = pd.ExcelFile(filepath)
        sheet_name = xl.sheet_names[0]
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        df = _normalize_columns(df, RESEARCH_COLS)

        for col in ['monthly_searches', 'purchase_volume', 'impressions',
                     'clicks', 'product_count', 'spr']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_numeric)

        for col in ['purchase_rate', 'growth_rate']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_pct)

        df['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed KeywordResearch: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse KeywordResearch {filepath}: {e}")
        return pd.DataFrame()
