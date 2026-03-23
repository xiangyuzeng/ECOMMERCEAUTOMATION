import { NextResponse } from 'next/server';
import { execFile } from 'child_process';
import { access, writeFile, unlink } from 'fs/promises';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const LOCK_FILE = path.join(PROJECT_ROOT, 'logs', '.processing');

async function isLocked() {
  try {
    await access(LOCK_FILE);
    return true;
  } catch {
    return false;
  }
}

export async function POST() {
  if (await isLocked()) {
    return NextResponse.json(
      { error: 'Pipeline is already running' },
      { status: 409 }
    );
  }

  const start = Date.now();

  try {
    await writeFile(LOCK_FILE, new Date().toISOString());

    const result = await new Promise((resolve, reject) => {
      execFile(
        'python3',
        [path.join(PROJECT_ROOT, 'scripts', 'generate_report.py')],
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
      stdout: result.stdout,
      stderr: result.stderr,
      elapsed_ms: Date.now() - start,
    });
  } catch (err) {
    return NextResponse.json({
      success: false,
      stdout: err.stdout || '',
      stderr: err.stderr || '',
      error: err.message,
      elapsed_ms: Date.now() - start,
    });
  } finally {
    try { await unlink(LOCK_FILE); } catch {}
  }
}
