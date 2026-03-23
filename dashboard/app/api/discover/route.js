import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { readFile, writeFile } from 'fs/promises';
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

function getProgressFile(productId) {
  if (productId) {
    const productLogs = path.join(PROJECT_ROOT, 'data', productId, 'logs');
    if (!fs.existsSync(productLogs)) fs.mkdirSync(productLogs, { recursive: true });
    return path.join(productLogs, 'discover_progress.json');
  }
  return path.join(PROJECT_ROOT, 'logs', 'discover_progress.json');
}

function getLockFile(productId) {
  if (productId) {
    const productLogs = path.join(PROJECT_ROOT, 'data', productId, 'logs');
    if (!fs.existsSync(productLogs)) fs.mkdirSync(productLogs, { recursive: true });
    return path.join(productLogs, '.discovering');
  }
  return path.join(PROJECT_ROOT, 'logs', '.discovering');
}

function getCollectLockFile(productId) {
  if (productId) {
    return path.join(PROJECT_ROOT, 'data', productId, 'logs', '.collecting');
  }
  return path.join(PROJECT_ROOT, 'logs', '.collecting');
}

export async function POST(request) {
  const body = await request.json();
  const { url } = body;
  const productId = body.product_id || resolveActiveProductId();

  const lockFile = getLockFile(productId);
  const progressFile = getProgressFile(productId);

  // Check not already running
  try {
    const lockData = await readFile(lockFile, 'utf-8');
    const pid = parseInt(lockData.trim());
    if (pid) {
      try {
        process.kill(pid, 0); // Check if alive
        return NextResponse.json({ error: 'Discovery already running', pid }, { status: 409 });
      } catch {
        // Process dead, clean up
      }
    }
  } catch {}

  // Also check global lock for backward compat
  const globalLock = path.join(PROJECT_ROOT, 'logs', '.discovering');
  if (lockFile !== globalLock) {
    try {
      const lockData = await readFile(globalLock, 'utf-8');
      const pid = parseInt(lockData.trim());
      if (pid) {
        try {
          process.kill(pid, 0);
          return NextResponse.json({ error: 'Discovery already running (global)', pid }, { status: 409 });
        } catch {}
      }
    } catch {}
  }

  // Cross-check: block if collection is still running (shares same browser)
  const collectLock = getCollectLockFile(productId);
  try {
    const collectPid = parseInt((await readFile(collectLock, 'utf-8')).trim(), 10);
    if (collectPid) {
      try {
        process.kill(collectPid, 0);
        return NextResponse.json(
          { error: 'Collection is running. Stop it first.', pid: collectPid },
          { status: 409 }
        );
      } catch {
        // Process dead, ignore
      }
    }
  } catch {}
  // Also check global collect lock
  const globalCollectLock = path.join(PROJECT_ROOT, 'logs', '.collecting');
  if (collectLock !== globalCollectLock) {
    try {
      const collectPid = parseInt((await readFile(globalCollectLock, 'utf-8')).trim(), 10);
      if (collectPid) {
        try {
          process.kill(collectPid, 0);
          return NextResponse.json(
            { error: 'Collection is running. Stop it first.', pid: collectPid },
            { status: 409 }
          );
        } catch {}
      }
    } catch {}
  }

  if (!url || !url.includes('amazon')) {
    return NextResponse.json({ error: 'Invalid Amazon URL' }, { status: 400 });
  }

  // Initialize progress
  const initialProgress = {
    status: 'starting',
    url,
    product_id: productId,
    started_at: new Date().toISOString(),
    phase: 'discovery',
    steps: [],
    errors: [],
  };
  await writeFile(progressFile, JSON.stringify(initialProgress, null, 2));

  // Spawn discovery process
  const args = [
    path.join(PROJECT_ROOT, 'scripts', 'collectors', 'collect.py'),
    '--discover', url,
    '--progress-file', progressFile,
  ];

  if (productId) {
    args.push('--product-id', productId);
  }

  const child = spawn('python3', args, {
    detached: true,
    stdio: 'ignore',
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });

  child.unref();
  const pid = child.pid;

  // Write lock file
  await writeFile(lockFile, String(pid));

  return NextResponse.json({
    started: true,
    pid,
    url,
    product_id: productId,
  });
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const productId = searchParams.get('product_id') || resolveActiveProductId();

  const lockFile = getLockFile(productId);
  const progressFile = getProgressFile(productId);

  // Check if running
  let isRunning = false;
  let pid = null;

  try {
    const lockData = await readFile(lockFile, 'utf-8');
    pid = parseInt(lockData.trim());
    if (pid) {
      try {
        process.kill(pid, 0);
        isRunning = true;
      } catch {
        // Dead process
        try { await writeFile(lockFile, ''); } catch {}
      }
    }
  } catch {}

  // Also check global lock for backward compat
  if (!isRunning) {
    const globalLock = path.join(PROJECT_ROOT, 'logs', '.discovering');
    if (lockFile !== globalLock) {
      try {
        const lockData = await readFile(globalLock, 'utf-8');
        const globalPid = parseInt(lockData.trim());
        if (globalPid) {
          try {
            process.kill(globalPid, 0);
            isRunning = true;
            pid = globalPid;
          } catch {}
        }
      } catch {}
    }
  }

  // Read progress
  let progress = null;
  try {
    progress = JSON.parse(await readFile(progressFile, 'utf-8'));
  } catch {}

  // Fall back to global progress if no product-specific progress
  if (!progress && productId) {
    const globalProgress = path.join(PROJECT_ROOT, 'logs', 'discover_progress.json');
    try {
      progress = JSON.parse(await readFile(globalProgress, 'utf-8'));
    } catch {}
  }

  return NextResponse.json({
    isRunning,
    pid,
    progress,
    product_id: productId,
  }, {
    headers: { 'Cache-Control': 'no-cache, no-store' },
  });
}

export async function DELETE(request) {
  const { searchParams } = new URL(request.url);
  const productId = searchParams.get('product_id') || resolveActiveProductId();

  const lockFile = getLockFile(productId);

  try {
    const lockData = await readFile(lockFile, 'utf-8');
    const pid = parseInt(lockData.trim());
    if (pid) {
      try { process.kill(-pid, 'SIGTERM'); } catch {}
      try { process.kill(pid, 'SIGTERM'); } catch {}
    }
    await writeFile(lockFile, '');
  } catch {}

  // Also clean global lock
  const globalLock = path.join(PROJECT_ROOT, 'logs', '.discovering');
  if (lockFile !== globalLock) {
    try {
      const lockData = await readFile(globalLock, 'utf-8');
      const pid = parseInt(lockData.trim());
      if (pid) {
        try { process.kill(-pid, 'SIGTERM'); } catch {}
        try { process.kill(pid, 'SIGTERM'); } catch {}
      }
      await writeFile(globalLock, '');
    } catch {}
  }

  return NextResponse.json({ stopped: true });
}
