import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { readFile, writeFile } from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const PROGRESS_FILE = path.join(PROJECT_ROOT, 'logs', 'discover_progress.json');
const LOCK_FILE = path.join(PROJECT_ROOT, 'logs', '.discovering');

export async function POST(request) {
  // Check not already running
  try {
    const lockData = await readFile(LOCK_FILE, 'utf-8');
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

  // Cross-check: block if collection is still running (shares same browser)
  const COLLECT_LOCK = path.join(PROJECT_ROOT, 'logs', '.collecting');
  try {
    const collectPid = parseInt((await readFile(COLLECT_LOCK, 'utf-8')).trim(), 10);
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

  const body = await request.json();
  const { url } = body;

  if (!url || !url.includes('amazon')) {
    return NextResponse.json({ error: 'Invalid Amazon URL' }, { status: 400 });
  }

  // Initialize progress
  const initialProgress = {
    status: 'starting',
    url,
    started_at: new Date().toISOString(),
    phase: 'discovery',
    steps: [],
    errors: [],
  };
  await writeFile(PROGRESS_FILE, JSON.stringify(initialProgress, null, 2));

  // Spawn discovery process
  const args = [
    path.join(PROJECT_ROOT, 'scripts', 'collectors', 'collect.py'),
    '--discover', url,
    '--progress-file', PROGRESS_FILE,
  ];

  const child = spawn('python3', args, {
    detached: true,
    stdio: 'ignore',
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });

  child.unref();
  const pid = child.pid;

  // Write lock file
  await writeFile(LOCK_FILE, String(pid));

  return NextResponse.json({
    started: true,
    pid,
    url,
  });
}

export async function GET() {
  // Check if running
  let isRunning = false;
  let pid = null;

  try {
    const lockData = await readFile(LOCK_FILE, 'utf-8');
    pid = parseInt(lockData.trim());
    if (pid) {
      try {
        process.kill(pid, 0);
        isRunning = true;
      } catch {
        // Dead process
        try { await writeFile(LOCK_FILE, ''); } catch {}
      }
    }
  } catch {}

  // Read progress
  let progress = null;
  try {
    progress = JSON.parse(await readFile(PROGRESS_FILE, 'utf-8'));
  } catch {}

  return NextResponse.json({
    isRunning,
    pid,
    progress,
  }, {
    headers: { 'Cache-Control': 'no-cache, no-store' },
  });
}

export async function DELETE() {
  try {
    const lockData = await readFile(LOCK_FILE, 'utf-8');
    const pid = parseInt(lockData.trim());
    if (pid) {
      try { process.kill(-pid, 'SIGTERM'); } catch {}
      try { process.kill(pid, 'SIGTERM'); } catch {}
    }
    await writeFile(LOCK_FILE, '');
  } catch {}

  return NextResponse.json({ stopped: true });
}
