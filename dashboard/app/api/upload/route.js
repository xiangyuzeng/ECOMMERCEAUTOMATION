import { NextResponse } from 'next/server';
import { writeFile } from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

const SELLERSPRITE_PATTERNS = [
  'ExpandKeywords', 'KeywordMining', 'CompareKeywords',
  'AdsInsights', 'Competitor', 'KeywordResearch',
];
const SELLER_CENTRAL_PATTERNS = [
  'BusinessReport', 'SpSearchTerm', 'SpCampaign', 'FBAFee',
];
const IGNORE_PATTERNS = ['flashlight', 'B08D66HCXW'];

function classifyFile(filename) {
  const lower = filename.toLowerCase();
  if (IGNORE_PATTERNS.some(p => lower.includes(p.toLowerCase()))) {
    return { rejected: true, reason: 'Matches ignore pattern' };
  }

  if (filename.endsWith('.xlsx')) {
    for (const pattern of SELLERSPRITE_PATTERNS) {
      if (filename.startsWith(pattern)) {
        return { dir: 'inputs/sellersprite', type: 'SellerSprite' };
      }
    }
    return { rejected: true, reason: 'Unknown .xlsx pattern' };
  }

  if (filename.endsWith('.csv')) {
    for (const pattern of SELLER_CENTRAL_PATTERNS) {
      if (filename.startsWith(pattern)) {
        return { dir: 'inputs/seller-central', type: 'Seller Central' };
      }
    }
    return { rejected: true, reason: 'Unknown .csv pattern' };
  }

  return { rejected: true, reason: 'Unsupported file type' };
}

export async function POST(request) {
  try {
    const formData = await request.formData();
    const files = formData.getAll('files');

    if (!files || files.length === 0) {
      return NextResponse.json({ error: 'No files provided' }, { status: 400 });
    }

    const saved = [];
    const rejected = [];

    for (const file of files) {
      const basename = path.basename(file.name);
      const classification = classifyFile(basename);

      if (classification.rejected) {
        rejected.push({ filename: basename, reason: classification.reason });
        continue;
      }

      const destDir = path.join(PROJECT_ROOT, classification.dir);
      const destPath = path.join(destDir, basename);
      const buffer = Buffer.from(await file.arrayBuffer());
      await writeFile(destPath, buffer);

      saved.push({
        filename: basename,
        type: classification.type,
        dir: classification.dir,
        size: buffer.length,
      });
    }

    return NextResponse.json({ saved, rejected });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
