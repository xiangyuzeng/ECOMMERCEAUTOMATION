import { NextResponse } from 'next/server';
import { readdir, readFile, stat } from 'fs/promises';
import path from 'path';
import fs from 'fs';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

function resolveActiveProductId() {
  const productsFile = path.join(PROJECT_ROOT, 'data', 'products.json');
  if (fs.existsSync(productsFile)) {
    try {
      const products = JSON.parse(fs.readFileSync(productsFile, 'utf-8'));
      return products.active_product_id || null;
    } catch (e) {}
  }
  return null;
}

function getInputDirs(productId) {
  if (productId) {
    const productDir = path.join(PROJECT_ROOT, 'data', productId);
    const ssDir = path.join(productDir, 'inputs', 'sellersprite');
    const scDir = path.join(productDir, 'inputs', 'seller-central');
    const processedDir = path.join(productDir, 'processed');
    if (fs.existsSync(ssDir) || fs.existsSync(scDir) || fs.existsSync(processedDir)) {
      return { ssDir, scDir, processedDir };
    }
  }
  // Fallback to root dirs
  return {
    ssDir: path.join(PROJECT_ROOT, 'inputs', 'sellersprite'),
    scDir: path.join(PROJECT_ROOT, 'inputs', 'seller-central'),
    processedDir: path.join(PROJECT_ROOT, 'processed'),
  };
}

function getConfigPath(productId) {
  if (productId) {
    const productConfig = path.join(PROJECT_ROOT, 'data', productId, 'config.json');
    if (fs.existsSync(productConfig)) return productConfig;
  }
  return path.join(PROJECT_ROOT, 'config.json');
}

async function listDir(dir) {
  try {
    const files = await readdir(dir);
    const results = [];
    for (const f of files) {
      if (f.startsWith('.')) continue;
      const st = await stat(path.join(dir, f));
      results.push({ name: f, size: st.size, modified: st.mtime.toISOString() });
    }
    return results;
  } catch {
    return [];
  }
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const productId = searchParams.get('product_id') || resolveActiveProductId();

  const { ssDir, scDir, processedDir } = getInputDirs(productId);
  const configPath = getConfigPath(productId);

  const sellersprite = await listDir(ssDir);
  const sellerCentral = await listDir(scDir);
  const processed = await listDir(processedDir);

  let lastRun = null;
  let ignoreList = [];
  let adspower = {};
  try {
    const config = JSON.parse(await readFile(configPath, 'utf-8'));
    lastRun = config.last_run || null;
    ignoreList = config.sellersprite_files?.ignore || [];
    adspower = config.adspower || {};
    // Override with data/setup.json (from setup wizard)
    try {
      const setupPath = path.join(PROJECT_ROOT, 'data', 'setup.json');
      if (fs.existsSync(setupPath)) {
        const setup = JSON.parse(fs.readFileSync(setupPath, 'utf-8'));
        if (setup.api_url) adspower.api_url = setup.api_url;
        if (setup.api_key) adspower.api_key = setup.api_key;
        if (setup.profile_id) adspower.profile_id = setup.profile_id;
      }
    } catch {}
    // Override with environment variables (highest priority, for Docker)
    if (process.env.ADSPOWER_API_URL) adspower.api_url = process.env.ADSPOWER_API_URL;
    if (process.env.ADSPOWER_API_KEY) adspower.api_key = process.env.ADSPOWER_API_KEY;
    if (process.env.ADSPOWER_PROFILE_ID) adspower.profile_id = process.env.ADSPOWER_PROFILE_ID;
  } catch {}

  // Filter out _removed directory and mark ignored files
  const ssFiltered = sellersprite
    .filter(f => !f.name.startsWith('_'))
    .map(f => ({
      ...f,
      ignored: ignoreList.includes(f.name) ||
               f.name.toLowerCase().includes('flashlight') ||
               f.name.includes('B08D66HCXW'),
    }));

  return NextResponse.json({
    hasData: processed.length > 0,
    lastRun,
    ignoreList,
    adspower,
    product_id: productId,
    inputFiles: { sellersprite: ssFiltered, sellerCentral },
    processedFiles: processed,
  }, {
    headers: { 'Cache-Control': 'no-cache, no-store' },
  });
}
