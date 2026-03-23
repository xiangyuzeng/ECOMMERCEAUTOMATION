import { NextResponse } from 'next/server';
import { readdir, readFile, stat } from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

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

export async function GET() {
  const sellersprite = await listDir(path.join(PROJECT_ROOT, 'inputs', 'sellersprite'));
  const sellerCentral = await listDir(path.join(PROJECT_ROOT, 'inputs', 'seller-central'));
  const processed = await listDir(path.join(PROJECT_ROOT, 'processed'));

  let lastRun = null;
  let ignoreList = [];
  let adspower = {};
  try {
    const config = JSON.parse(await readFile(path.join(PROJECT_ROOT, 'config.json'), 'utf-8'));
    lastRun = config.last_run || null;
    ignoreList = config.sellersprite_files?.ignore || [];
    adspower = config.adspower || {};
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
    inputFiles: { sellersprite: ssFiltered, sellerCentral },
    processedFiles: processed,
  }, {
    headers: { 'Cache-Control': 'no-cache, no-store' },
  });
}
