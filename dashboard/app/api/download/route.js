import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';
import fs from 'fs';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

// GET /api/download?file=FILENAME&product_id=XXX
export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const file = searchParams.get('file');
  const productId = searchParams.get('product_id');

  if (!file) {
    return NextResponse.json({ error: 'file parameter required' }, { status: 400 });
  }

  // Security: only allow basename (no path traversal)
  const safeName = path.basename(file);

  // Search in outputs/ then processed/ for the product or root
  const searchDirs = [];
  if (productId) {
    searchDirs.push(
      path.join(PROJECT_ROOT, 'data', productId, 'outputs'),
      path.join(PROJECT_ROOT, 'data', productId, 'processed'),
    );
  }
  searchDirs.push(
    path.join(PROJECT_ROOT, 'outputs'),
    path.join(PROJECT_ROOT, 'processed'),
  );

  let filePath = null;
  for (const dir of searchDirs) {
    const candidate = path.join(dir, safeName);
    if (fs.existsSync(candidate)) {
      filePath = candidate;
      break;
    }
  }

  if (!filePath) {
    return NextResponse.json({ error: 'File not found' }, { status: 404 });
  }

  const content = await readFile(filePath);
  const ext = path.extname(safeName).toLowerCase();
  const contentType =
    ext === '.xlsx' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' :
    ext === '.json' ? 'application/json' :
    ext === '.md' ? 'text/markdown' :
    ext === '.csv' ? 'text/csv' :
    'application/octet-stream';

  return new NextResponse(content, {
    headers: {
      'Content-Type': contentType,
      'Content-Disposition': `attachment; filename="${encodeURIComponent(safeName)}"`,
      'Content-Length': String(content.length),
    },
  });
}
