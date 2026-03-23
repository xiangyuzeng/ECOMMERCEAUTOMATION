"""
Multi-product config manager for ECOMMERCEAUTOMATION.

Manages a portfolio of products, each with its own config, inputs, outputs,
and processed data under data/{product_id}/.

Data structure:
    data/
      products.json              <- Product index
      {product_id}/
        config.json              <- Per-product config
        inputs/
          sellersprite/
          seller-central/
        processed/
        outputs/
        logs/
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
PRODUCTS_FILE = DATA_DIR / 'products.json'


def _ensure_data_dir():
    """Create data/ directory and products.json if they don't exist."""
    DATA_DIR.mkdir(exist_ok=True)
    if not PRODUCTS_FILE.exists():
        PRODUCTS_FILE.write_text(
            json.dumps({"products": [], "active_product_id": None}, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )


def list_products():
    """Return products.json data. Returns {"products": [], "active_product_id": None} if no file."""
    _ensure_data_dir()
    return json.loads(PRODUCTS_FILE.read_text(encoding='utf-8'))


def get_product_config(product_id):
    """Load data/{product_id}/config.json. Falls back to root config.json if product dir doesn't exist."""
    product_config = DATA_DIR / product_id / 'config.json'
    if product_config.exists():
        return json.loads(product_config.read_text(encoding='utf-8'))
    # Fallback to root config
    root_config = PROJECT_ROOT / 'config.json'
    if root_config.exists():
        return json.loads(root_config.read_text(encoding='utf-8'))
    return {}


def save_product_config(product_id, config):
    """Save config to data/{product_id}/config.json"""
    product_dir = DATA_DIR / product_id
    product_dir.mkdir(parents=True, exist_ok=True)
    config_path = product_dir / 'config.json'
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')


def get_product_paths(product_id):
    """Return dict of all paths for a product."""
    base = DATA_DIR / product_id
    return {
        'root': str(base),
        'config': str(base / 'config.json'),
        'inputs': str(base / 'inputs'),
        'inputs_sellersprite': str(base / 'inputs' / 'sellersprite'),
        'inputs_seller_central': str(base / 'inputs' / 'seller-central'),
        'processed': str(base / 'processed'),
        'outputs': str(base / 'outputs'),
        'logs': str(base / 'logs'),
    }


def create_product(asin, brand='', title='', price=None, category=''):
    """Create a new product directory structure and add to products.json index.
    Returns product_id (which is the ASIN)."""
    _ensure_data_dir()
    product_id = asin
    paths = get_product_paths(product_id)

    # Create directories
    for key in ['inputs_sellersprite', 'inputs_seller_central', 'processed', 'outputs', 'logs']:
        Path(paths[key]).mkdir(parents=True, exist_ok=True)

    # Create initial config from template (root config.json)
    root_config_path = PROJECT_ROOT / 'config.json'
    if root_config_path.exists():
        config = json.loads(root_config_path.read_text(encoding='utf-8'))
    else:
        config = {}

    # Update active_product with this product's info
    config['active_product'] = {
        'asin_parent': asin,
        'asin_listing': asin,
        'brand': brand,
        'title': title,
        'price': price or config.get('active_product', {}).get('price', 0),
        'category': category,
        'rating': None,
        'reviews': 0,
        'child_asins': [],
        'image_url': '',
    }
    # Clear competitors and collection for fresh start
    config['competitors'] = {}
    config['collection'] = config.get('collection', {})
    config['collection']['reverse_asin_asins'] = [asin]
    config['collection']['mining_seeds'] = []
    config['collection']['comparison_asins'] = []
    config['collection']['ads_insights_asins'] = []

    save_product_config(product_id, config)

    # Add to products.json index
    products_data = list_products()
    # Check if product already exists
    existing = [p for p in products_data['products'] if p['id'] == product_id]
    if not existing:
        products_data['products'].append({
            'id': product_id,
            'asin': asin,
            'brand': brand,
            'title': title,
            'price': price,
            'category': category,
            'created_at': datetime.now().isoformat(),
            'last_collection': None,
            'last_pipeline': None,
            'keywords_count': 0,
            'status': 'active',
        })

    # Set as active
    products_data['active_product_id'] = product_id
    PRODUCTS_FILE.write_text(json.dumps(products_data, indent=2, ensure_ascii=False), encoding='utf-8')

    return product_id


def set_active_product(product_id):
    """Set the active product in products.json."""
    _ensure_data_dir()
    products_data = list_products()
    # Verify product exists
    if not any(p['id'] == product_id for p in products_data['products']):
        raise ValueError(f"Product {product_id} not found")
    products_data['active_product_id'] = product_id
    PRODUCTS_FILE.write_text(json.dumps(products_data, indent=2, ensure_ascii=False), encoding='utf-8')


def get_active_product_id():
    """Return the active product ID, or None."""
    _ensure_data_dir()
    products_data = list_products()
    return products_data.get('active_product_id')


def update_product_stats(product_id, **kwargs):
    """Update product stats in products.json (last_collection, last_pipeline, keywords_count, etc.)."""
    _ensure_data_dir()
    products_data = list_products()
    for p in products_data['products']:
        if p['id'] == product_id:
            p.update(kwargs)
            break
    PRODUCTS_FILE.write_text(json.dumps(products_data, indent=2, ensure_ascii=False), encoding='utf-8')


def delete_product(product_id, archive=True):
    """Delete or archive a product. If archive=True, move to data/_archived/."""
    _ensure_data_dir()
    product_dir = DATA_DIR / product_id
    if not product_dir.exists():
        return

    if archive:
        archive_dir = DATA_DIR / '_archived'
        archive_dir.mkdir(exist_ok=True)
        dest = archive_dir / f"{product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.move(str(product_dir), str(dest))
    else:
        shutil.rmtree(str(product_dir))

    # Remove from products.json
    products_data = list_products()
    products_data['products'] = [p for p in products_data['products'] if p['id'] != product_id]
    if products_data['active_product_id'] == product_id:
        products_data['active_product_id'] = products_data['products'][0]['id'] if products_data['products'] else None
    PRODUCTS_FILE.write_text(json.dumps(products_data, indent=2, ensure_ascii=False), encoding='utf-8')


def migrate_flat_to_portfolio():
    """Migrate current flat file structure to multi-product portfolio.
    Reads config.json to determine the active product, creates product directory,
    moves input/processed/output files into it."""
    root_config_path = PROJECT_ROOT / 'config.json'
    if not root_config_path.exists():
        return None

    config = json.loads(root_config_path.read_text(encoding='utf-8'))
    asin = config.get('active_product', {}).get('asin_parent') or config.get('active_product', {}).get('asin_listing')
    if not asin:
        return None

    brand = config.get('active_product', {}).get('brand', '')
    title = config.get('active_product', {}).get('title', '')
    price = config.get('active_product', {}).get('price') or config.get('active_product', {}).get('current_price')
    category = config.get('active_product', {}).get('category', '')

    # Create product
    product_id = create_product(asin, brand, title, price, category)
    paths = get_product_paths(product_id)

    # Save full config as product config (overwrite the template-based one from create_product)
    save_product_config(product_id, config)

    # Move input files
    for sub in ['sellersprite', 'seller-central']:
        src = PROJECT_ROOT / 'inputs' / sub
        path_key = 'inputs_sellersprite' if sub == 'sellersprite' else 'inputs_seller_central'
        dest = Path(paths[path_key])
        if src.exists():
            for f in src.iterdir():
                if f.is_file():
                    shutil.copy2(str(f), str(dest / f.name))

    # Copy processed files
    src_processed = PROJECT_ROOT / 'processed'
    dest_processed = Path(paths['processed'])
    if src_processed.exists():
        for f in src_processed.iterdir():
            if f.is_file() and f.suffix == '.json':
                shutil.copy2(str(f), str(dest_processed / f.name))

    # Copy output files
    src_outputs = PROJECT_ROOT / 'outputs'
    dest_outputs = Path(paths['outputs'])
    if src_outputs.exists():
        for f in src_outputs.iterdir():
            if f.is_file():
                shutil.copy2(str(f), str(dest_outputs / f.name))

    # Update product stats
    keywords_count = 0
    kw_file = Path(paths['processed']) / 'keywords.json'
    if kw_file.exists():
        try:
            keywords_count = len(json.loads(kw_file.read_text(encoding='utf-8')))
        except Exception:
            pass

    update_product_stats(product_id,
        last_pipeline=datetime.now().isoformat(),
        keywords_count=keywords_count,
    )

    return product_id


# CLI interface for testing
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python config_manager.py [list|create|migrate|active|set-active|delete|paths]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'list':
        data = list_products()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif cmd == 'create' and len(sys.argv) >= 3:
        pid = create_product(sys.argv[2], brand=sys.argv[3] if len(sys.argv) > 3 else '')
        print(f"Created product: {pid}")
    elif cmd == 'migrate':
        pid = migrate_flat_to_portfolio()
        print(f"Migrated to product: {pid}")
    elif cmd == 'active':
        print(get_active_product_id())
    elif cmd == 'set-active' and len(sys.argv) >= 3:
        set_active_product(sys.argv[2])
        print(f"Active product set to: {sys.argv[2]}")
    elif cmd == 'delete' and len(sys.argv) >= 3:
        archive = '--no-archive' not in sys.argv
        delete_product(sys.argv[2], archive=archive)
        print(f"{'Archived' if archive else 'Deleted'} product: {sys.argv[2]}")
    elif cmd == 'paths' and len(sys.argv) >= 3:
        p = get_product_paths(sys.argv[2])
        print(json.dumps(p, indent=2))
    else:
        print(f"Unknown command: {cmd}")
