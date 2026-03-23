import { NextResponse } from 'next/server';
import { spawn, execSync } from 'child_process';
import { readFile, writeFile, unlink, access } from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const PROGRESS_FILE = path.join(PROJECT_ROOT, 'logs', 'collect_progress.json');
const LOCK_FILE = path.join(PROJECT_ROOT, 'logs', '.collecting');

function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function readLock() {
  try {
    const content = await readFile(LOCK_FILE, 'utf-8');
    const pid = parseInt(content.trim(), 10);
    return isNaN(pid) ? null : pid;
  } catch {
    return null;
  }
}

async function readProgress() {
  try {
    const content = await readFile(PROGRESS_FILE, 'utf-8');
    return JSON.parse(content);
  } catch {
    return { status: 'idle', tasks: [], completed: 0, total: 0, errors: [] };
  }
}

// GET — Read collection progress
export async function GET() {
  const pid = await readLock();
  let progress = await readProgress();
  let isRunning = false;

  if (pid) {
    if (isPidAlive(pid)) {
      isRunning = true;
    } else {
      // Process died — clean up lock and mark progress as failed
      try { await unlink(LOCK_FILE); } catch {}
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
          await writeFile(PROGRESS_FILE, JSON.stringify(progress), 'utf-8');
        } catch {}
      }
    }
  }

  let chromeRunning = false;
  try { execSync('pgrep -f "Google Chrome"', { stdio: 'ignore' }); chromeRunning = true; } catch {}

  return NextResponse.json(
    { isRunning, pid: isRunning ? pid : null, progress, chromeRunning },
    { headers: { 'Cache-Control': 'no-cache, no-store' } }
  );
}

// POST — Start collection
export async function POST(request) {
  const existingPid = await readLock();
  if (existingPid && isPidAlive(existingPid)) {
    return NextResponse.json(
      { error: 'Collection already running', pid: existingPid },
      { status: 409 }
    );
  }

  // Cross-check: block if discovery is still running (shares same browser)
  const DISCOVER_LOCK = path.join(PROJECT_ROOT, 'logs', '.discovering');
  try {
    const discoverPid = parseInt((await readFile(DISCOVER_LOCK, 'utf-8')).trim(), 10);
    if (discoverPid && isPidAlive(discoverPid)) {
      return NextResponse.json(
        { error: 'Discovery is still running. Wait for it to finish.', pid: discoverPid },
        { status: 409 }
      );
    }
  } catch {}

  let body = {};
  try {
    body = await request.json();
  } catch {}

  const mode = body.mode || 'full';
  const chromeProfile = body.chromeProfile || null;

  // Read config to check if AdsPower is enabled
  let adspowerEnabled = false;
  try {
    const config = JSON.parse(await readFile(path.join(PROJECT_ROOT, 'config.json'), 'utf-8'));
    adspowerEnabled = config.adspower?.enabled === true;
  } catch {}

  const args = [
    path.join(PROJECT_ROOT, 'scripts', 'collectors', 'collect.py'),
    '--progress-file', PROGRESS_FILE,
  ];

  if (mode === 'sellersprite') args.push('--sellersprite-only');
  if (mode === 'seller-central') args.push('--seller-central-only');
  // When AdsPower is enabled, do NOT pass --chrome-profile (AdsPower manages its own browser)
  if (chromeProfile && !adspowerEnabled) args.push('--chrome-profile', chromeProfile);

  // Reset progress file before starting
  const initial = { status: 'starting', started_at: new Date().toISOString(), tasks: [], completed: 0, total: 0, errors: [] };
  try {
    await writeFile(PROGRESS_FILE, JSON.stringify(initial), 'utf-8');
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
    await writeFile(LOCK_FILE, String(pid), 'utf-8');
  } catch {}

  child.unref();

  // Clean up lock when process exits (if we can still hear it)
  child.on('error', async () => {
    try { await unlink(LOCK_FILE); } catch {}
  });
  child.on('exit', async () => {
    try { await unlink(LOCK_FILE); } catch {}
  });

  return NextResponse.json({ started: true, pid, mode });
}

// DELETE — Stop collection
export async function DELETE() {
  const pid = await readLock();

  if (!pid) {
    return NextResponse.json({ error: 'No collection running' }, { status: 404 });
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
  try { await unlink(LOCK_FILE); } catch {}

  // Update progress to reflect interruption
  try {
    const progress = await readProgress();
    if (progress.status === 'running') {
      progress.status = 'interrupted';
      for (const t of progress.tasks) {
        if (t.status === 'running') {
          t.status = 'failed';
          t.error = 'Stopped by user';
        }
      }
      await writeFile(PROGRESS_FILE, JSON.stringify(progress), 'utf-8');
    }
  } catch {}

  return NextResponse.json({ stopped: true });
}
