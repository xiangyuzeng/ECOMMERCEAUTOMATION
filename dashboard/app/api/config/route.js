import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

export async function GET() {
  try {
    const config = JSON.parse(await readFile(path.join(PROJECT_ROOT, 'config.json'), 'utf-8'));
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
