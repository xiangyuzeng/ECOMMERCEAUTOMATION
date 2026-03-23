import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';
import fs from 'fs';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

const FILES = {
  competitors: 'competitors.json',
  keywords: 'keywords.json',
  ads: 'ads.json',
  pricing: 'pricing.json',
  traffic: 'traffic.json',
  gapAnalysis: 'gap_analysis.json',
};

function getProcessedDir(productId) {
  if (productId) {
    const productProcessed = path.join(PROJECT_ROOT, 'data', productId, 'processed');
    if (fs.existsSync(productProcessed)) return productProcessed;
  }
  // Try to get active product from products.json
  const productsFile = path.join(PROJECT_ROOT, 'data', 'products.json');
  if (fs.existsSync(productsFile)) {
    try {
      const products = JSON.parse(fs.readFileSync(productsFile, 'utf-8'));
      if (products.active_product_id) {
        const activeProcessed = path.join(PROJECT_ROOT, 'data', products.active_product_id, 'processed');
        if (fs.existsSync(activeProcessed)) return activeProcessed;
      }
    } catch (e) {}
  }
  // Fallback to root processed/
  return path.join(PROJECT_ROOT, 'processed');
}

async function readJSON(dir, filename) {
  try {
    const content = await readFile(path.join(dir, filename), 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const productId = searchParams.get('product_id');
  const processedDir = getProcessedDir(productId);

  const data = {};
  let hasAny = false;

  for (const [key, filename] of Object.entries(FILES)) {
    data[key] = await readJSON(processedDir, filename);
    if (data[key] !== null) hasAny = true;
  }

  if (!hasAny) {
    return NextResponse.json({ exists: false }, {
      headers: { 'Cache-Control': 'no-cache, no-store' },
    });
  }

  return NextResponse.json(data, {
    headers: { 'Cache-Control': 'no-cache, no-store' },
  });
}
