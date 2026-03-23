"""
Pricing model — 4-scenario P&L + per-variant cost breakdown.
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def build_pricing_model(business_df, fba_df, campaign_df, config, competitor_matrix=None):
    """
    Build pricing scenarios and per-variant P&L.
    Returns dict with 'scenarios' and 'variants' data.
    """
    cost = config.get('cost_inputs', {})
    scenarios = config.get('pricing_scenarios', [])
    active = config.get('active_product', {})
    child_asins = active.get('child_asins', [])

    # Build 4-scenario model
    scenario_data = []
    for sc in scenarios:
        price = sc['price']
        scenario_data.append({
            'scenario': sc['label'],
            'price': price,
            'unit_cost': cost.get('unit_cost_usd', 15.00),
            'packaging': cost.get('packaging_cost', 0.50) + cost.get('labeling_cost', 0.20),
            'inbound_shipping': cost.get('inbound_shipping_per_unit', 3.00),
            'referral_fee_rate': cost.get('referral_fee_rate', 0.17),
            'fba_fee': cost.get('fba_fee_estimate', 5.50),
            'storage_fee': cost.get('monthly_storage_estimate', 0.87),
            'ad_rate': cost.get('ppc_rate', 0.12),
            'return_rate': cost.get('return_rate', 0.15),
        })

    # Build per-variant breakdown
    variants = []
    if business_df is not None and not business_df.empty:
        _business_df_available = True
    else:
        _business_df_available = False

    if _business_df_available:
        parent_asin = active.get('asin_parent', '')
        parent_rows = business_df[business_df['(Parent) ASIN'] == parent_asin]

        # Get FBA fees per ASIN
        fba_lookup = {}
        if fba_df is not None and not fba_df.empty:
            for _, row in fba_df.iterrows():
                asin = row.get('asin', '')
                if pd.notna(asin):
                    fba_lookup[asin] = {
                        'sku': row.get('sku', ''),
                        'fba_fee': row.get('expected-fulfillment-fee-per-unit'),
                        'referral_fee': row.get('estimated-referral-fee-per-unit'),
                        'storage_fee': row.get('estimated-monthly-storage-fee'),
                        'total_fee': row.get('estimated-fee-total'),
                    }

        # Get ad spend per campaign (blouse campaigns only)
        total_blouse_spend = 0
        total_blouse_sales = 0
        total_blouse_units = 0
        if campaign_df is not None and not campaign_df.empty:
            # Try matching campaigns by child ASINs first, fall back to all campaigns
            matched = pd.DataFrame()
            if child_asins and 'Campaign Name' in campaign_df.columns:
                for asin in child_asins:
                    asin_match = campaign_df[campaign_df['Campaign Name'].str.contains(asin, case=False, na=False)]
                    if not asin_match.empty:
                        matched = pd.concat([matched, asin_match])
            if matched.empty:
                # Fallback: use all campaigns
                matched = campaign_df
            total_blouse_spend = matched['Spend'].sum() if 'Spend' in matched.columns else 0
            total_blouse_sales = matched['7 Day Total Sales'].sum() if '7 Day Total Sales' in matched.columns else 0
            total_blouse_units = matched['7 Day Total Units (#)'].sum() if '7 Day Total Units (#)' in matched.columns else 0

        for _, row in parent_rows.iterrows():
            child_asin = row.get('(Child) ASIN', '')
            units = row.get('Units Ordered', 0) or 0
            revenue = row.get('Ordered Product Sales', 0) or 0
            sessions = row.get('Sessions', 0) or 0
            avg_price = revenue / units if units > 0 else None

            fba_info = fba_lookup.get(child_asin, {})

            # Estimate per-unit ad spend
            ad_spend_per_unit = total_blouse_spend / total_blouse_units if total_blouse_units > 0 else 0
            acos = total_blouse_spend / total_blouse_sales if total_blouse_sales > 0 else 0
            variant_ad_spend = round(ad_spend_per_unit * units, 2) if units > 0 else 0
            tacos = variant_ad_spend / revenue if revenue > 0 else 0

            variants.append({
                'asin': child_asin,
                'sku': fba_info.get('sku', ''),
                'units_ordered': units,
                'revenue': revenue,
                'sessions': sessions,
                'cvr': units / sessions if sessions > 0 else 0,
                'avg_price': round(avg_price, 2) if avg_price is not None else None,
                'unit_cost': cost.get('unit_cost_usd', 15.00),
                'inbound_shipping': cost.get('inbound_shipping_per_unit', 3.00),
                'fba_fee': fba_info.get('fba_fee') or cost.get('fba_fee_estimate', 5.50),
                'referral_fee': fba_info.get('referral_fee') or (round(avg_price * 0.17, 2) if avg_price else 0),
                'storage_fee': fba_info.get('storage_fee') or cost.get('monthly_storage_estimate', 0.87),
                'ad_spend': variant_ad_spend,
                'acos': round(acos, 4),
                'tacos': round(tacos, 4),
            })

    elif competitor_matrix:
        # Fallback: build synthetic variants from competitor data + config when no Seller Central CSVs
        logger.info("No Seller Central data — building synthetic variants from competitor/config data")

        # Find our product in the competitor matrix
        my_product = None
        for prod in competitor_matrix:
            if prod.get('is_mine'):
                my_product = prod
                break

        # Determine listing ASINs to create rows for
        listing_asins = child_asins if child_asins else [active.get('asin_listing', active.get('asin_parent', ''))]

        for child_asin in listing_asins:
            if not child_asin:
                continue

            # Price: competitor matrix → config → last scenario
            price = None
            monthly_sales = None
            monthly_revenue = None

            if my_product:
                price = my_product.get('price')
                monthly_sales = my_product.get('monthly_sales')
                monthly_revenue = my_product.get('monthly_revenue')

            if price is None:
                price = active.get('current_price')
            if price is None and scenarios:
                price = scenarios[-1]['price']
            if price is None:
                price = 0

            # Estimate units from revenue/price if not directly available
            if monthly_sales is None and monthly_revenue and price and price > 0:
                monthly_sales = round(monthly_revenue / price)

            # Cost components from config
            unit_cost = cost.get('unit_cost_usd', 15.00)
            inbound = cost.get('inbound_shipping_per_unit', 3.00)
            referral_rate = cost.get('referral_fee_rate', 0.17)
            fba_fee_est = cost.get('fba_fee_estimate', 5.50)
            storage = cost.get('monthly_storage_estimate', 0.87)

            variants.append({
                'asin': child_asin,
                'sku': '(estimated)',
                'units_ordered': monthly_sales or 0,
                'revenue': monthly_revenue or (monthly_sales * price if monthly_sales and price else 0),
                'sessions': 0,
                'cvr': 0,
                'avg_price': round(price, 2) if price else 0,
                'unit_cost': unit_cost,
                'inbound_shipping': inbound,
                'fba_fee': fba_fee_est,
                'referral_fee': round(price * referral_rate, 2) if price else 0,
                'storage_fee': storage,
                'ad_spend': 0,
                'acos': 0,
                'tacos': 0,
                'is_estimated': True,
            })

        logger.info(f"Built {len(variants)} synthetic variants from competitor data")
    else:
        logger.warning("No Seller Central data and no competitor matrix — pricing tab will be empty")

    logger.info(f"Pricing model built: {len(scenario_data)} scenarios, {len(variants)} variants")
    return {
        'scenarios': scenario_data,
        'variants': variants,
        'cost_inputs': cost,
    }
