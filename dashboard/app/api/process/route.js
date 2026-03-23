import { NextResponse } from 'next/server';
import { execFile } from 'child_process';
import { access, readFile, writeFile, unlink } from 'fs/promises';
import path from 'path';
import fs from 'fs';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

function getLockFile(productId) {
  if (productId) {
    const productLogs = path.join(PROJECT_ROOT, 'data', productId, 'logs');
    if (!fs.existsSync(productLogs)) fs.mkdirSync(productLogs, { recursive: true });
    return path.join(productLogs, '.processing');
  }
  return path.join(PROJECT_ROOT, 'logs', '.processing');
}

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

async function isLocked(lockFile) {
  try {
    await access(lockFile);
    return true;
  } catch {
    return false;
  }
}

export async function POST(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {}

  const { searchParams } = new URL(request.url);
  const productId = searchParams.get('product_id') || body?.product_id || resolveActiveProductId();

  const lockFile = getLockFile(productId);
  // Also check global lock for backward compat
  const globalLock = path.join(PROJECT_ROOT, 'logs', '.processing');

  if (await isLocked(lockFile) || (lockFile !== globalLock && await isLocked(globalLock))) {
    return NextResponse.json(
      { error: 'Pipeline is already running' },
      { status: 409 }
    );
  }

  const start = Date.now();

  try {
    await writeFile(lockFile, new Date().toISOString());

    const args = [path.join(PROJECT_ROOT, 'scripts', 'generate_report.py')];
    if (productId) {
      args.push('--product-id', productId);
    }

    const result = await new Promise((resolve, reject) => {
      execFile(
        'python3',
        args,
        { cwd: PROJECT_ROOT, timeout: 120000, maxBuffer: 10 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error) {
            reject({ code: error.code, stdout, stderr, message: error.message });
          } else {
            resolve({ stdout, stderr });
          }
        }
      );
    });

    return NextResponse.json({
      success: true,
      product_id: productId,
      stdout: result.stdout,
      stderr: result.stderr,
      elapsed_ms: Date.now() - start,
    });
  } catch (err) {
    return NextResponse.json({
      success: false,
      product_id: productId,
      stdout: err.stdout || '',
      stderr: err.stderr || '',
      error: err.message,
      elapsed_ms: Date.now() - start,
    });
  } finally {
    try { await unlink(lockFile); } catch {}
  }
}
