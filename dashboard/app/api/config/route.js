import { NextResponse } from 'next/server';
import { readFile, writeFile } from 'fs/promises';
import path from 'path';
import fs from 'fs';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

function getConfigPath(productId) {
  if (productId) {
    const productConfig = path.join(PROJECT_ROOT, 'data', productId, 'config.json');
    if (fs.existsSync(productConfig)) return productConfig;
  }
  // Check active product
  const productsFile = path.join(PROJECT_ROOT, 'data', 'products.json');
  if (fs.existsSync(productsFile)) {
    try {
      const products = JSON.parse(fs.readFileSync(productsFile, 'utf-8'));
      if (products.active_product_id) {
        const activeConfig = path.join(PROJECT_ROOT, 'data', products.active_product_id, 'config.json');
        if (fs.existsSync(activeConfig)) return activeConfig;
      }
    } catch (e) {}
  }
  return path.join(PROJECT_ROOT, 'config.json');
}

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const productId = searchParams.get('product_id');
    const configPath = getConfigPath(productId);

    const config = JSON.parse(await readFile(configPath, 'utf-8'));
    const product = config.active_product || {};
    const competitors = config.competitors || {};
    const seeds = config.seed_keywords || [];
    const collection = config.collection || {};

    return NextResponse.json({
      product: {
        asin: product.asin_listing || product.asin_parent || '',
        parentAsin: product.asin_parent || '',
        title: product.title || '',
        brand: product.brand || '',
        price: product.current_price,
        rating: product.rating,
        reviewCount: product.review_count || 0,
        category: product.category || '',
        imageUrl: product.image_url || '',
        childAsins: product.child_asins || [],
      },
      competitorCount: Object.keys(competitors).length,
      seedKeywords: seeds,
      skipSellerCentral: collection.skip_seller_central || false,
    }, {
      headers: { 'Cache-Control': 'no-cache, no-store' },
    });
  } catch {
    return NextResponse.json({ product: null }, {
      headers: { 'Cache-Control': 'no-cache, no-store' },
    });
  }
}

// PUT /api/config — update config sections
export async function PUT(req) {
  try {
    const body = await req.json();
    const { searchParams } = new URL(req.url);
    const productId = searchParams.get('product_id');
    const configPath = getConfigPath(productId);

    const config = JSON.parse(await readFile(configPath, 'utf-8'));

    // Merge updates into config
    if (body.notifications) {
      config.notifications = { ...(config.notifications || {}), ...body.notifications };
    }
    if (body.schedule) {
      config.schedule = { ...(config.schedule || {}), ...body.schedule };
    }
    if (body.cost_inputs) {
      config.cost_inputs = { ...(config.cost_inputs || {}), ...body.cost_inputs };
    }
    if (body.adspower) {
      config.adspower = { ...(config.adspower || {}), ...body.adspower };
    }

    await writeFile(configPath, JSON.stringify(config, null, 2));
    return NextResponse.json({ success: true });
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
