import { NextResponse } from 'next/server';
import path from 'path';
import fs from 'fs';
import { execSync } from 'child_process';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const PRODUCTS_FILE = path.join(PROJECT_ROOT, 'data', 'products.json');

function getProducts() {
  try {
    if (!fs.existsSync(PRODUCTS_FILE)) {
      // Initialize products.json
      const dataDir = path.join(PROJECT_ROOT, 'data');
      if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
      const initial = { products: [], active_product_id: null };
      fs.writeFileSync(PRODUCTS_FILE, JSON.stringify(initial, null, 2));
      return initial;
    }
    return JSON.parse(fs.readFileSync(PRODUCTS_FILE, 'utf-8'));
  } catch (e) {
    return { products: [], active_product_id: null };
  }
}

function saveProducts(data) {
  const dataDir = path.join(PROJECT_ROOT, 'data');
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(PRODUCTS_FILE, JSON.stringify(data, null, 2));
}

export async function GET() {
  const data = getProducts();

  // Enrich with file counts
  for (const product of data.products) {
    const productDir = path.join(PROJECT_ROOT, 'data', product.id);
    const ssDir = path.join(productDir, 'inputs', 'sellersprite');
    const scDir = path.join(productDir, 'inputs', 'seller-central');
    const processedDir = path.join(productDir, 'processed');

    product.file_counts = {
      sellersprite: fs.existsSync(ssDir) ? fs.readdirSync(ssDir).filter(f => f.endsWith('.xlsx')).length : 0,
      seller_central: fs.existsSync(scDir) ? fs.readdirSync(scDir).filter(f => f.endsWith('.csv')).length : 0,
      processed: fs.existsSync(processedDir) ? fs.readdirSync(processedDir).filter(f => f.endsWith('.json')).length : 0,
    };

    // Check for latest Excel report
    const outputsDir = path.join(productDir, 'outputs');
    if (fs.existsSync(outputsDir)) {
      const xlsxFiles = fs.readdirSync(outputsDir).filter(f => f.endsWith('.xlsx'));
      product.has_report = xlsxFiles.length > 0;
      if (xlsxFiles.length > 0) {
        product.latest_report = xlsxFiles.sort().reverse()[0];
      }
    }
  }

  return NextResponse.json(data);
}

export async function POST(request) {
  // Create new product or set active
  const body = await request.json();

  if (body.action === 'set_active') {
    const data = getProducts();
    if (!data.products.find(p => p.id === body.product_id)) {
      return NextResponse.json({ error: 'Product not found' }, { status: 404 });
    }
    data.active_product_id = body.product_id;
    saveProducts(data);
    return NextResponse.json({ success: true, active_product_id: body.product_id });
  }

  if (body.action === 'create') {
    try {
      const result = execSync(
        `python3 scripts/config_manager.py create "${body.asin}" "${body.brand || ''}" "${body.title || ''}"`,
        { cwd: PROJECT_ROOT, encoding: 'utf-8', timeout: 10000 }
      );
      return NextResponse.json({ success: true, product_id: body.asin, message: result.trim() });
    } catch (e) {
      return NextResponse.json({ error: e.message }, { status: 500 });
    }
  }

  if (body.action === 'migrate') {
    try {
      const result = execSync(
        'python3 scripts/config_manager.py migrate',
        { cwd: PROJECT_ROOT, encoding: 'utf-8', timeout: 30000 }
      );
      return NextResponse.json({ success: true, message: result.trim() });
    } catch (e) {
      return NextResponse.json({ error: e.message }, { status: 500 });
    }
  }

  if (body.action === 'delete') {
    try {
      const result = execSync(
        `python3 scripts/config_manager.py delete "${body.product_id}"`,
        { cwd: PROJECT_ROOT, encoding: 'utf-8', timeout: 10000 }
      );
      return NextResponse.json({ success: true, message: result.trim() });
    } catch (e) {
      return NextResponse.json({ error: e.message }, { status: 500 });
    }
  }

  return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
}

// DELETE /api/products?product_id=XXX — archive a product
export async function DELETE(req) {
  const { searchParams } = new URL(req.url);
  const productId = searchParams.get('product_id');
  if (!productId) {
    return NextResponse.json({ error: 'product_id required' }, { status: 400 });
  }

  const productDir = path.join(PROJECT_ROOT, 'data', productId);
  const archiveDir = path.join(PROJECT_ROOT, 'data', '_archived', productId);

  // Move product directory to archive
  if (fs.existsSync(productDir)) {
    fs.mkdirSync(path.join(PROJECT_ROOT, 'data', '_archived'), { recursive: true });
    if (fs.existsSync(archiveDir)) {
      // Archive already exists — remove old archive first
      fs.rmSync(archiveDir, { recursive: true, force: true });
    }
    fs.renameSync(productDir, archiveDir);
  }

  // Remove from products.json
  const productsFile = path.join(PROJECT_ROOT, 'data', 'products.json');
  if (fs.existsSync(productsFile)) {
    const products = JSON.parse(fs.readFileSync(productsFile, 'utf-8'));
    products.products = (products.products || []).filter(p => p.id !== productId);
    if (products.active_product_id === productId) {
      products.active_product_id = products.products[0]?.id || null;
    }
    fs.writeFileSync(productsFile, JSON.stringify(products, null, 2));
  }

  return NextResponse.json({ success: true, archived: productId });
}
