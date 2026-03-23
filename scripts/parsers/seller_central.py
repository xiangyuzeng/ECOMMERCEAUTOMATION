"""
Seller Central .csv parsers — handles 4 report types.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def _clean_currency(val):
    """Convert '$1,234.56' to float."""
    if pd.isna(val) or val == '--' or val == '':
        return None
    if isinstance(val, str):
        val = val.strip().replace('$', '').replace(',', '')
        try:
            return float(val)
        except ValueError:
            return None
    return float(val)


def _clean_pct(val):
    """Convert '98.2%' to float (0.982)."""
    if pd.isna(val) or val == '--' or val == '':
        return None
    if isinstance(val, str):
        val = val.strip().replace('%', '').replace(',', '')
        try:
            return float(val) / 100.0
        except ValueError:
            return None
    return float(val)


def _clean_int(val):
    """Convert to int, handle '--'."""
    if pd.isna(val) or val == '--' or val == '':
        return None
    if isinstance(val, str):
        val = val.strip().replace(',', '')
        try:
            return int(float(val))
        except ValueError:
            return None
    return int(val)


def _clean_float(val):
    """Convert to float, handle '--'."""
    if pd.isna(val) or val == '--' or val == '':
        return None
    if isinstance(val, str):
        val = val.strip().replace(',', '').replace('$', '')
        try:
            return float(val)
        except ValueError:
            return None
    return float(val)


def parse_business_report(filepath):
    """Parse Business Report CSV."""
    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip() for c in df.columns]

        # Clean types
        for col in ['Sessions', 'Page Views', 'Units Ordered', 'Units Ordered - B2B',
                     'Total Order Items', 'Total Order Items - B2B']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_int)

        for col in ['Session Percentage', 'Page Views Percentage',
                     'Buy Box Percentage', 'Unit Session Percentage',
                     'Unit Session Percentage - B2B']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_pct)

        for col in ['Ordered Product Sales', 'Ordered Product Sales - B2B']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_currency)

        df['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed BusinessReport: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse BusinessReport {filepath}: {e}")
        return pd.DataFrame()


def parse_search_term_report(filepath):
    """Parse SP Search Term Report CSV. Watch for trailing spaces in column names."""
    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip() for c in df.columns]

        for col in ['Impressions', 'Clicks', '7 Day Total Orders (#)',
                     '7 Day Total Units (#)', '7 Day Advertised SKU Units (#)',
                     '7 Day Other SKU Units (#)']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_int)

        for col in ['Click-Thru Rate (CTR)', 'Total Advertising Cost of Sales (ACoS)',
                     '7 Day Conversion Rate']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_pct)

        for col in ['Cost Per Click (CPC)', 'Spend', '7 Day Total Sales',
                     'Total Return on Advertising Spend (RoAS)',
                     '7 Day Advertised SKU Sales', '7 Day Other SKU Sales']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_currency)

        df['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed SpSearchTerm: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse SpSearchTerm {filepath}: {e}")
        return pd.DataFrame()


def parse_campaign_report(filepath):
    """Parse SP Campaign Report CSV."""
    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip() for c in df.columns]

        for col in ['Impressions', 'Clicks', '7 Day Total Orders (#)',
                     '7 Day Total Units (#)']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_int)

        for col in ['Click-Thru Rate (CTR)', 'Total Advertising Cost of Sales (ACoS)',
                     '7 Day Conversion Rate']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_pct)

        for col in ['Cost Per Click (CPC)', 'Spend', '7 Day Total Sales',
                     'Total Return on Advertising Spend (RoAS)',
                     '7 Day Advertised SKU Sales', '7 Day Other SKU Sales',
                     'Campaign Budget Amount']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_currency)

        df['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed SpCampaign: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse SpCampaign {filepath}: {e}")
        return pd.DataFrame()


def parse_fba_fee_preview(filepath):
    """Parse FBA Fee Preview CSV. '--' means null."""
    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip() for c in df.columns]

        # Replace '--' with NaN
        df = df.replace('--', pd.NA)

        for col in ['your-price', 'sales-price', 'estimated-fee-total',
                     'estimated-referral-fee-per-unit',
                     'expected-fulfillment-fee-per-unit',
                     'estimated-monthly-storage-fee',
                     'estimated-variable-closing-fee',
                     'estimated-order-handling-fee-per-order',
                     'estimated-pick-pack-fee-per-unit',
                     'estimated-weight-handling-fee-per-unit',
                     'estimated-future-fee',
                     'longest-side', 'median-side', 'shortest-side',
                     'item-package-weight']:
            if col in df.columns:
                df[col] = df[col].apply(_clean_float)

        df['source_file'] = str(filepath).split('/')[-1]
        logger.info(f"Parsed FBAFeePreview: {filepath} → {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to parse FBAFeePreview {filepath}: {e}")
        return pd.DataFrame()
