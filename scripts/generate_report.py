#!/usr/bin/env python3
"""
COLD POSH Amazon Operations — Main Pipeline
Scans inputs, parses, processes, exports Excel + JSON.
"""
import os
import sys
import json
import glob
import logging
import pandas as pd
from datetime import datetime

# Setup paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Setup logging
os.makedirs(os.path.join(PROJECT_ROOT, 'logs'), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(PROJECT_ROOT, 'logs', 'pipeline.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('pipeline')

from scripts.parsers.sellersprite import (
    parse_expand_keywords, parse_keyword_mining, parse_compare_keywords,
    parse_ads_insights, parse_competitor, parse_keyword_research
)
from scripts.parsers.seller_central import (
    parse_business_report, parse_search_term_report,
    parse_campaign_report, parse_fba_fee_preview
)
from scripts.processors.keywords import build_keyword_library
from scripts.processors.competitors import build_competitor_matrix
from scripts.processors.gap_analysis import build_gap_analysis
from scripts.processors.pricing import build_pricing_model
from scripts.processors.ads import build_ads_monitoring
from scripts.processors.traffic import build_traffic_sources
from scripts.exporters.excel_writer import write_workbook
from scripts.exporters.json_writer import write_json_files
from scripts.config_manager import get_product_config, get_product_paths, update_product_stats, get_active_product_id


def load_config(product_id=None):
    """Load config - from data/{product_id}/config.json if product_id given, else root config.json."""
    if product_id:
        from scripts.config_manager import get_product_config
        return get_product_config(product_id)
    config_path = os.path.join(PROJECT_ROOT, 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def classify_files(config, product_id=None):
    """Scan inputs/ and classify files by pattern."""
    if product_id:
        from scripts.config_manager import get_product_paths
        paths = get_product_paths(product_id)
        ss_dir = paths['inputs_sellersprite']
        sc_dir = paths['inputs_seller_central']
    else:
        ss_dir = os.path.join(PROJECT_ROOT, 'inputs', 'sellersprite')
        sc_dir = os.path.join(PROJECT_ROOT, 'inputs', 'seller-central')

    ignore_list = config.get('sellersprite_files', {}).get('ignore', [])

    files = {
        'expand_keywords': [],
        'keyword_mining': [],
        'compare_keywords': [],
        'ads_insights': [],
        'competitor': [],
        'keyword_research': [],
        'business_report': [],
        'search_term': [],
        'campaign': [],
        'fba_fee': [],
    }

    # SellerSprite
    for fp in sorted(glob.glob(os.path.join(ss_dir, '*.xlsx'))):
        fname = os.path.basename(fp)
        if fname in ignore_list:
            logger.info(f"IGNORED: {fname}")
            continue
        if 'flashlight' in fname.lower() or 'B08D66HCXW' in fname:
            logger.info(f"IGNORED (filter): {fname}")
            continue

        if fname.startswith('ExpandKeywords') or fname.startswith('ReverseASIN'):
            files['expand_keywords'].append(fp)
        elif fname.startswith('KeywordMining'):
            files['keyword_mining'].append(fp)
        elif fname.startswith('CompareKeywords'):
            files['compare_keywords'].append(fp)
        elif fname.startswith('AdsInsights'):
            files['ads_insights'].append(fp)
        elif fname.startswith('Competitor'):
            files['competitor'].append(fp)
        elif fname.startswith('KeywordResearch'):
            files['keyword_research'].append(fp)
        else:
            logger.warning(f"Unclassified SellerSprite file: {fname}")

    # Seller Central
    for fp in sorted(glob.glob(os.path.join(sc_dir, '*.csv'))):
        fname = os.path.basename(fp)
        if fname.startswith('BusinessReport'):
            files['business_report'].append(fp)
        elif fname.startswith('SpSearchTerm'):
            files['search_term'].append(fp)
        elif fname.startswith('SpCampaign'):
            files['campaign'].append(fp)
        elif fname.startswith('FBAFee'):
            files['fba_fee'].append(fp)
        else:
            logger.warning(f"Unclassified Seller Central file: {fname}")

    return files


def run_pipeline(product_id=None):
    """Execute full pipeline."""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Pipeline — Starting")
    logger.info("=" * 60)

    results = {}
    errors = []
    file_log = []

    # 1. Load config
    try:
        config = load_config(product_id=product_id)
        brand = config.get('active_product', {}).get('brand', '') or 'PRODUCT'
        logger.info(f"✓ Config loaded — brand: {brand}")
    except Exception as e:
        logger.error(f"✗ Config load failed: {e}")
        return

    # 2. Classify files
    files = classify_files(config, product_id=product_id)
    for cat, fps in files.items():
        logger.info(f"  {cat}: {len(fps)} files")

    total_files = sum(len(fps) for fps in files.values())
    if total_files == 0:
        logger.warning("⚠ No input files found in inputs/ directories! Report will contain empty data.")

    # 3. Parse SellerSprite
    logger.info("--- Parsing SellerSprite ---")
    expand_dfs = []
    for fp in files['expand_keywords']:
        df = parse_expand_keywords(fp)
        if not df.empty:
            expand_dfs.append(df)
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'SellerSprite',
                'module': 'Reverse ASIN',
                'records': len(df),
                'feeds_tab': '竞品分析, 词库整理, Gap分析',
                'data_quality': 'OK',
                'notes': '',
            })

    mining_dfs = []
    for fp in files['keyword_mining']:
        df = parse_keyword_mining(fp)
        if not df.empty:
            mining_dfs.append(df)
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'SellerSprite',
                'module': 'Keyword Mining',
                'records': len(df),
                'feeds_tab': '词库整理',
                'data_quality': 'OK',
                'notes': '',
            })

    compare_dfs = []
    for fp in files['compare_keywords']:
        df = parse_compare_keywords(fp)
        if not df.empty:
            compare_dfs.append(df)
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'SellerSprite',
                'module': 'Traffic Comparison',
                'records': len(df),
                'feeds_tab': '流量入口',
                'data_quality': 'OK',
                'notes': '',
            })

    ads_insights_dfs = []
    for fp in files['ads_insights']:
        df = parse_ads_insights(fp)
        if not df.empty:
            ads_insights_dfs.append(df)
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'SellerSprite',
                'module': 'Ads Insights',
                'records': len(df),
                'feeds_tab': '广告指标监测',
                'data_quality': 'OK',
                'notes': '',
            })

    competitor_dfs = []
    for fp in files['competitor']:
        df = parse_competitor(fp)
        if not df.empty:
            competitor_dfs.append(df)
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'SellerSprite',
                'module': 'Competitor Research',
                'records': len(df),
                'feeds_tab': '竞品分析',
                'data_quality': 'OK',
                'notes': '',
            })

    research_dfs = []
    for fp in files['keyword_research']:
        df = parse_keyword_research(fp)
        if not df.empty:
            research_dfs.append(df)
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'SellerSprite',
                'module': 'Keyword Research',
                'records': len(df),
                'feeds_tab': '词库整理',
                'data_quality': 'OK',
                'notes': '',
            })

    # 4. Parse Seller Central
    logger.info("--- Parsing Seller Central ---")
    business_df = None
    for fp in files['business_report']:
        business_df = parse_business_report(fp)
        if business_df is not None and not business_df.empty:
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'Seller Central',
                'module': 'Business Report',
                'records': len(business_df),
                'feeds_tab': '竞品分析, 产品清单, 定价策略',
                'data_quality': 'OK',
                'notes': '',
            })

    search_term_df = None
    for fp in files['search_term']:
        search_term_df = parse_search_term_report(fp)
        if search_term_df is not None and not search_term_df.empty:
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'Seller Central',
                'module': 'SP Search Term',
                'records': len(search_term_df),
                'feeds_tab': '词库整理, 广告指标监测',
                'data_quality': 'OK',
                'notes': '',
            })

    campaign_df = None
    for fp in files['campaign']:
        campaign_df = parse_campaign_report(fp)
        if campaign_df is not None and not campaign_df.empty:
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'Seller Central',
                'module': 'SP Campaign',
                'records': len(campaign_df),
                'feeds_tab': '广告指标监测, 定价策略',
                'data_quality': 'OK',
                'notes': '',
            })

    fba_df = None
    for fp in files['fba_fee']:
        fba_df = parse_fba_fee_preview(fp)
        if fba_df is not None and not fba_df.empty:
            file_log.append({
                'timestamp': datetime.now().isoformat(),
                'source_file': os.path.basename(fp),
                'source_type': 'Seller Central',
                'module': 'FBA Fee Preview',
                'records': len(fba_df),
                'feeds_tab': '定价策略',
                'data_quality': 'OK',
                'notes': '',
            })

    # 5. Run processors
    logger.info("--- Running Processors ---")

    # Keywords
    try:
        keyword_library = build_keyword_library(
            expand_dfs, mining_dfs, compare_dfs, research_dfs,
            search_term_df, config
        )
        results['keywords'] = len(keyword_library) if keyword_library is not None else 0
        logger.info(f"✓ Keyword library: {results['keywords']} keywords")
    except Exception as e:
        logger.error(f"✗ Keyword library failed: {e}")
        errors.append(f"keywords: {e}")
        keyword_library = None

    # Competitors
    try:
        competitor_matrix = build_competitor_matrix(
            competitor_dfs, expand_dfs, business_df, config
        )
        results['competitors'] = len(competitor_matrix)
        logger.info(f"✓ Competitor matrix: {results['competitors']} products")
    except Exception as e:
        logger.error(f"✗ Competitor matrix failed: {e}")
        errors.append(f"competitors: {e}")
        competitor_matrix = []

    # Gap analysis
    try:
        # Find my expand and first competitor expand
        my_asin = config['active_product'].get('asin_listing', '')
        parent_asin = config['active_product'].get('asin_parent', '')
        my_asins = {my_asin, parent_asin} - {''}

        # Get first competitor ASIN from config
        competitors_cfg = config.get('competitors', {})
        comp_asin = ''
        if isinstance(competitors_cfg, dict):
            first_comp = next(iter(competitors_cfg.values()), {})
            comp_asin = first_comp.get('asin', first_comp.get('asin_listing', ''))
        elif isinstance(competitors_cfg, list) and competitors_cfg:
            comp_asin = competitors_cfg[0].get('asin', competitors_cfg[0].get('asin_listing', ''))

        # Also include child ASINs as "mine"
        child_asins = config['active_product'].get('child_asins', [])
        if child_asins:
            my_asins.update(child_asins)

        # Collect ALL matching expand_dfs and concat (don't overwrite)
        my_expands = []
        comp_expands = []
        for df in expand_dfs:
            if df.empty:
                continue
            src = df['source_asin'].iloc[0] if 'source_asin' in df.columns else None
            if src in my_asins:
                my_expands.append(df)
            elif comp_asin and src == comp_asin:
                comp_expands.append(df)
            elif src and src not in my_asins:
                comp_expands.append(df)

        my_expand = pd.concat(my_expands, ignore_index=True) if my_expands else None
        comp_expand = pd.concat(comp_expands, ignore_index=True) if comp_expands else None
        logger.info(f"Gap analysis: my_expand={len(my_expand) if my_expand is not None else 0} rows from {len(my_expands)} files, "
                     f"comp_expand={len(comp_expand) if comp_expand is not None else 0} rows from {len(comp_expands)} files")

        gap_analysis = build_gap_analysis(my_expand, comp_expand, config=config)
        results['gap_keywords'] = len(gap_analysis) if gap_analysis is not None else 0
        logger.info(f"✓ Gap analysis: {results['gap_keywords']} keywords")
    except Exception as e:
        logger.error(f"✗ Gap analysis failed: {e}")
        errors.append(f"gap_analysis: {e}")
        gap_analysis = None

    # Pricing
    try:
        pricing_data = build_pricing_model(business_df, fba_df, campaign_df, config, competitor_matrix=competitor_matrix)
        results['variants'] = len(pricing_data.get('variants', []))
        logger.info(f"✓ Pricing model: {results['variants']} variants")
    except Exception as e:
        logger.error(f"✗ Pricing model failed: {e}")
        errors.append(f"pricing: {e}")
        pricing_data = {'scenarios': [], 'variants': [], 'cost_inputs': {}}

    # Ads
    try:
        ads_insights_combined = None
        if ads_insights_dfs:
            ads_insights_combined = pd.concat(ads_insights_dfs, ignore_index=True)

        ads_data = build_ads_monitoring(ads_insights_combined, search_term_df, campaign_df, config=config)
        results['search_terms'] = len(ads_data.get('search_term_summary', []))
        logger.info(f"✓ Ads monitoring: {results['search_terms']} search terms")
    except Exception as e:
        logger.error(f"✗ Ads monitoring failed: {e}")
        errors.append(f"ads: {e}")
        ads_data = {'heatmap': {'keywords': [], 'weeks': [], 'grid': {}}, 'search_term_summary': [], 'campaign_summary': []}

    # Traffic
    try:
        traffic_sources = build_traffic_sources(
            keyword_library, search_term_df, compare_dfs, config
        )
        results['traffic_channels'] = len(traffic_sources)
        logger.info(f"✓ Traffic sources: {results['traffic_channels']} channels")
    except Exception as e:
        logger.error(f"✗ Traffic sources failed: {e}")
        errors.append(f"traffic: {e}")
        traffic_sources = []

    # 6. Export Excel
    logger.info("--- Exporting ---")
    if product_id:
        from scripts.config_manager import get_product_paths
        paths = get_product_paths(product_id)
        outputs_dir = paths['outputs']
        processed_dir = paths['processed']
    else:
        outputs_dir = os.path.join(PROJECT_ROOT, 'outputs')
        processed_dir = os.path.join(PROJECT_ROOT, 'processed')
    os.makedirs(outputs_dir, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    brand_slug = brand.replace(' ', '_')
    excel_path = os.path.join(outputs_dir, f'{brand_slug}_运营方案_{today}.xlsx')

    try:
        write_workbook(
            excel_path, competitor_matrix, keyword_library,
            ads_data, pricing_data, traffic_sources,
            gap_analysis, file_log, config
        )
        results['excel'] = excel_path
        logger.info(f"✓ Excel: {excel_path}")
    except Exception as e:
        logger.error(f"✗ Excel export failed: {e}")
        errors.append(f"excel: {e}")

    # 7. Export JSON
    try:
        json_files = write_json_files(
            processed_dir, competitor_matrix, keyword_library,
            ads_data, pricing_data, traffic_sources, gap_analysis
        )
        results['json_files'] = len(json_files)
        logger.info(f"✓ JSON: {len(json_files)} files")
    except Exception as e:
        logger.error(f"✗ JSON export failed: {e}")
        errors.append(f"json: {e}")

    # 8. Write run summary
    summary_path = os.path.join(outputs_dir, 'run_summary.md')
    try:
        _write_summary(summary_path, results, errors, file_log, config, start_time)
        logger.info(f"✓ Summary: {summary_path}")
    except Exception as e:
        logger.error(f"✗ Summary failed: {e}")

    # 9. Update config last_run (only on clean run)
    try:
        if not errors:
            config['last_run'] = datetime.now().isoformat()
        else:
            config['last_run_partial'] = datetime.now().isoformat()
        if product_id:
            from scripts.config_manager import save_product_config
            save_product_config(product_id, config)
        else:
            with open(os.path.join(PROJECT_ROOT, 'config.json'), 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Update product stats after successful pipeline
    if product_id:
        try:
            from scripts.config_manager import update_product_stats
            update_product_stats(product_id,
                last_pipeline=datetime.now().isoformat(),
                keywords_count=len(keyword_library) if keyword_library else 0,
            )
        except Exception:
            pass

    # 10. Print completion
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Time: {elapsed:.1f}s")
    print(f"Keywords: {results.get('keywords', 0)}")
    print(f"Competitors: {results.get('competitors', 0)}")
    print(f"Gap keywords: {results.get('gap_keywords', 0)}")
    print(f"Variants: {results.get('variants', 0)}")
    print(f"Search terms: {results.get('search_terms', 0)}")
    print(f"Traffic channels: {results.get('traffic_channels', 0)}")
    print(f"Excel: {results.get('excel', 'FAILED')}")
    print(f"JSON files: {results.get('json_files', 0)}")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("\n✓ All steps completed successfully!")
    print("=" * 60)


def _write_summary(path, results, errors, file_log, config, start_time):
    """Write run_summary.md."""
    elapsed = (datetime.now() - start_time).total_seconds()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"# {config['active_product'].get('brand', '') or 'PRODUCT'} 运营方案 — Run Summary\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Duration**: {elapsed:.1f}s\n")
        f.write(f"**Product**: {config['active_product']['title']}\n")
        f.write(f"**ASIN**: {config['active_product']['asin_listing']}\n\n")

        f.write("## Results\n\n")
        f.write(f"| Metric | Count |\n|---|---|\n")
        for k, v in results.items():
            f.write(f"| {k} | {v} |\n")

        f.write("\n## Data Sources\n\n")
        f.write(f"| File | Type | Records |\n|---|---|---|\n")
        for entry in file_log:
            f.write(f"| {entry['source_file']} | {entry['module']} | {entry['records']} |\n")

        if errors:
            f.write("\n## Errors\n\n")
            for e in errors:
                f.write(f"- {e}\n")

        f.write("\n## Strategic Insights\n\n")
        f.write("1. **Keyword Coverage**: Review 词库整理 tab for classification gaps\n")
        f.write("2. **Gap Analysis**: Focus on MISSING keywords with high priority scores\n")
        f.write("3. **Pricing**: Current $109.99 price point — review 4-scenario model\n")
        f.write("4. **Ads**: Monitor ACoS trends in 广告指标监测 tab\n")
        f.write("5. **Traffic**: Diversify beyond SP ads — see 流量入口 tab\n")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate operations report')
    parser.add_argument('--product-id', type=str, default=None,
                        help='Product ID for multi-product mode (loads from data/{product_id}/)')
    args = parser.parse_args()
    run_pipeline(product_id=args.product_id)
