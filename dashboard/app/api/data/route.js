import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const PROCESSED_DIR = path.join(PROJECT_ROOT, 'processed');

const FILES = {
  competitors: 'competitors.json',
  keywords: 'keywords.json',
  ads: 'ads.json',
  pricing: 'pricing.json',
  traffic: 'traffic.json',
  gapAnalysis: 'gap_analysis.json',
};

async function readJSON(filename) {
  try {
    const content = await readFile(path.join(PROCESSED_DIR, filename), 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export async function GET() {
  const data = {};
  let hasAny = false;

  for (const [key, filename] of Object.entries(FILES)) {
    data[key] = await readJSON(filename);
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
