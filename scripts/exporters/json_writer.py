"""
JSON writer for dashboard data.
"""
import json
import os
import logging
import math

logger = logging.getLogger(__name__)


def _sanitize(obj):
    """Make object JSON-serializable."""
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _sanitize(obj.tolist())
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def _df_to_records(df):
    """Convert DataFrame to list of dicts, handling NaN."""
    if df is None or df.empty:
        return []
    records = df.to_dict('records')
    return _sanitize(records)


def write_json_files(output_dir, competitor_matrix, keyword_library,
                     ads_data, pricing_data, traffic_sources,
                     gap_analysis):
    """Write all processed data as JSON for the dashboard."""
    os.makedirs(output_dir, exist_ok=True)

    files_written = []

    # Competitors
    path = os.path.join(output_dir, 'competitors.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_sanitize(competitor_matrix or []), f, ensure_ascii=False, indent=2)
    files_written.append(path)

    # Keywords
    path = os.path.join(output_dir, 'keywords.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_df_to_records(keyword_library), f, ensure_ascii=False, indent=2)
    files_written.append(path)

    # Ads
    path = os.path.join(output_dir, 'ads.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_sanitize(ads_data or {}), f, ensure_ascii=False, indent=2)
    files_written.append(path)

    # Pricing
    path = os.path.join(output_dir, 'pricing.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_sanitize(pricing_data or {}), f, ensure_ascii=False, indent=2)
    files_written.append(path)

    # Traffic
    path = os.path.join(output_dir, 'traffic.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_sanitize(traffic_sources or []), f, ensure_ascii=False, indent=2)
    files_written.append(path)

    # Gap analysis
    path = os.path.join(output_dir, 'gap_analysis.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_df_to_records(gap_analysis), f, ensure_ascii=False, indent=2)
    files_written.append(path)

    logger.info(f"JSON files written: {len(files_written)} files to {output_dir}")
    return files_written
