import { NextResponse } from 'next/server';
import { spawn, execSync } from 'child_process';
import { readFile, writeFile, unlink, access } from 'fs/promises';
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
    return path.join(productLogs, 'collect_progress.json');
  }
  return path.join(PROJECT_ROOT, 'logs', 'collect_progress.json');
}

function getLockFile(productId) {
  if (productId) {
    const productLogs = path.join(PROJECT_ROOT, 'data', productId, 'logs');
    if (!fs.existsSync(productLogs)) fs.mkdirSync(productLogs, { recursive: true });
    return path.join(productLogs, '.collecting');
  }
  return path.join(PROJECT_ROOT, 'logs', '.collecting');
}

function getDiscoverLockFile(productId) {
  if (productId) {
    return path.join(PROJECT_ROOT, 'data', productId, 'logs', '.discovering');
  }
  return path.join(PROJECT_ROOT, 'logs', '.discovering');
}

function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function readLock(lockFile) {
  try {
    const content = await readFile(lockFile, 'utf-8');
    const pid = parseInt(content.trim(), 10);
    return isNaN(pid) ? null : pid;
  } catch {
    return null;
  }
}

async function readProgress(progressFile) {
  try {
    const content = await readFile(progressFile, 'utf-8');
    return JSON.parse(content);
  } catch {
    return { status: 'idle', tasks: [], completed: 0, total: 0, errors: [] };
  }
}

function getConfigPath(productId) {
  if (productId) {
    const productConfig = path.join(PROJECT_ROOT, 'data', productId, 'config.json');
    if (fs.existsSync(productConfig)) return productConfig;
  }
  return path.join(PROJECT_ROOT, 'config.json');
}

// GET -- Read collection progress
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const productId = searchParams.get('product_id') || resolveActiveProductId();

  const lockFile = getLockFile(productId);
  const progressFile = getProgressFile(productId);

  const pid = await readLock(lockFile);
  let progress = await readProgress(progressFile);
  let isRunning = false;

  if (pid) {
    if (isPidAlive(pid)) {
      isRunning = true;
    } else {
      // Process died -- clean up lock and mark progress as failed
      try { await unlink(lockFile); } catch {}
      if (progress.status === 'running') {
        progress.status = 'failed';
        progress.errors.push({ task: '_process', error: 'Process exited unexpectedly' });
        // Update the current running task to failed
        for (const t of progress.tasks) {
          if (t.status === 'running') {
            t.status = 'failed';
            t.error = 'Process exited';
          }
        }
        try {
          await writeFile(progressFile, JSON.stringify(progress), 'utf-8');
        } catch {}
      }
    }
  }

  // Also check global lock for backward compat
  if (!isRunning && productId) {
    const globalLock = path.join(PROJECT_ROOT, 'logs', '.collecting');
    if (lockFile !== globalLock) {
      const globalPid = await readLock(globalLock);
      if (globalPid && isPidAlive(globalPid)) {
        isRunning = true;
      }
    }
  }

  // If no product-specific progress, fall back to global
  if (progress.status === 'idle' && productId) {
    const globalProgressFile = path.join(PROJECT_ROOT, 'logs', 'collect_progress.json');
    const globalProgress = await readProgress(globalProgressFile);
    if (globalProgress.status !== 'idle') {
      progress = globalProgress;
    }
  }

  let chromeRunning = false;
  try { execSync('pgrep -f "Google Chrome"', { stdio: 'ignore' }); chromeRunning = true; } catch {}

  return NextResponse.json(
    { isRunning, pid: isRunning ? pid : null, progress, chromeRunning, product_id: productId },
    { headers: { 'Cache-Control': 'no-cache, no-store' } }
  );
}

// POST -- Start collection
export async function POST(request) {
  let body = {};
  try {
    body = await request.json();
  } catch {}

  const productId = body?.product_id || resolveActiveProductId();
  const lockFile = getLockFile(productId);
  const progressFile = getProgressFile(productId);

  const existingPid = await readLock(lockFile);
  if (existingPid && isPidAlive(existingPid)) {
    return NextResponse.json(
      { error: 'Collection already running', pid: existingPid },
      { status: 409 }
    );
  }

  // Also check global lock
  const globalLock = path.join(PROJECT_ROOT, 'logs', '.collecting');
  if (lockFile !== globalLock) {
    const globalPid = await readLock(globalLock);
    if (globalPid && isPidAlive(globalPid)) {
      return NextResponse.json(
        { error: 'Collection already running (global)', pid: globalPid },
        { status: 409 }
      );
    }
  }

  // Cross-check: block if discovery is still running (shares same browser)
  const discoverLock = getDiscoverLockFile(productId);
  try {
    const discoverPid = parseInt((await readFile(discoverLock, 'utf-8')).trim(), 10);
    if (discoverPid && isPidAlive(discoverPid)) {
      return NextResponse.json(
        { error: 'Discovery is still running. Wait for it to finish.', pid: discoverPid },
        { status: 409 }
      );
    }
  } catch {}
  // Also check global discover lock
  const globalDiscoverLock = path.join(PROJECT_ROOT, 'logs', '.discovering');
  if (discoverLock !== globalDiscoverLock) {
    try {
      const discoverPid = parseInt((await readFile(globalDiscoverLock, 'utf-8')).trim(), 10);
      if (discoverPid && isPidAlive(discoverPid)) {
        return NextResponse.json(
          { error: 'Discovery is still running. Wait for it to finish.', pid: discoverPid },
          { status: 409 }
        );
      }
    } catch {}
  }

  const mode = body.mode || 'full';
  const chromeProfile = body.chromeProfile || null;

  // Read config to check if AdsPower is enabled
  let adspowerEnabled = false;
  try {
    const configPath = getConfigPath(productId);
    const config = JSON.parse(await readFile(configPath, 'utf-8'));
    adspowerEnabled = config.adspower?.enabled === true;
  } catch {}

  const args = [
    path.join(PROJECT_ROOT, 'scripts', 'collectors', 'collect.py'),
    '--progress-file', progressFile,
  ];

  if (productId) args.push('--product-id', productId);
  if (mode === 'sellersprite') args.push('--sellersprite-only');
  if (mode === 'seller-central') args.push('--seller-central-only');
  // When AdsPower is enabled, do NOT pass --chrome-profile (AdsPower manages its own browser)
  if (chromeProfile && !adspowerEnabled) args.push('--chrome-profile', chromeProfile);

  // Reset progress file before starting
  const initial = { status: 'starting', started_at: new Date().toISOString(), product_id: productId, tasks: [], completed: 0, total: 0, errors: [] };
  try {
    await writeFile(progressFile, JSON.stringify(initial), 'utf-8');
  } catch {}

  const child = spawn('python3', args, {
    detached: true,
    stdio: 'ignore',
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });

  const pid = child.pid;

  // Write lock file with PID
  try {
    await writeFile(lockFile, String(pid), 'utf-8');
  } catch {}

  child.unref();

  // Clean up lock when process exits (if we can still hear it)
  child.on('error', async () => {
    try { await unlink(lockFile); } catch {}
  });
  child.on('exit', async () => {
    try { await unlink(lockFile); } catch {}
  });

  return NextResponse.json({ started: true, pid, mode, product_id: productId });
}

// DELETE -- Stop collection
export async function DELETE(request) {
  const { searchParams } = new URL(request.url);
  const productId = searchParams.get('product_id') || resolveActiveProductId();

  const lockFile = getLockFile(productId);
  const progressFile = getProgressFile(productId);

  const pid = await readLock(lockFile);

  if (!pid) {
    // Also try global lock
    const globalLock = path.join(PROJECT_ROOT, 'logs', '.collecting');
    const globalPid = await readLock(globalLock);
    if (!globalPid) {
      return NextResponse.json({ error: 'No collection running' }, { status: 404 });
    }
    // Kill global process
    try { process.kill(-globalPid, 'SIGTERM'); } catch {
      try { process.kill(globalPid, 'SIGTERM'); } catch {}
    }
    try { await unlink(globalLock); } catch {}
    return NextResponse.json({ stopped: true });
  }

  try {
    // Kill the process group (negative PID) to also kill Playwright browser
    process.kill(-pid, 'SIGTERM');
  } catch {
    try {
      // Fallback: kill just the process
      process.kill(pid, 'SIGTERM');
    } catch {}
  }

  // Clean up lock file
  try { await unlink(lockFile); } catch {}

  // Update progress to reflect interruption
  try {
    const progress = await readProgress(progressFile);
    if (progress.status === 'running') {
      progress.status = 'interrupted';
      for (const t of progress.tasks) {
        if (t.status === 'running') {
          t.status = 'failed';
          t.error = 'Stopped by user';
        }
      }
      await writeFile(progressFile, JSON.stringify(progress), 'utf-8');
    }
  } catch {}

  return NextResponse.json({ stopped: true });
}
