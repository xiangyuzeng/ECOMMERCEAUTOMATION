import { NextResponse } from 'next/server';
import { readdir, readFile } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import os from 'os';
import { execSync } from 'child_process';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

function getChromeDir() {
  // Check config first
  try {
    const config = JSON.parse(require('fs').readFileSync(path.join(PROJECT_ROOT, 'config.json'), 'utf-8'));
    const dir = config?.collection?.chrome_profile_dir;
    if (dir) return dir.replace(/^~/, os.homedir());
  } catch {}

  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome');
  } else if (process.platform === 'win32') {
    return path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'User Data');
  }
  return path.join(os.homedir(), '.config', 'google-chrome');
}

function isChromeRunning() {
  try {
    execSync('pgrep -f "Google Chrome"', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

export async function GET() {
  const chromeDir = getChromeDir();
  const chromeRunning = isChromeRunning();

  if (!existsSync(chromeDir)) {
    return NextResponse.json({ profiles: [], chromeRunning, error: 'Chrome not found' });
  }

  const entries = await readdir(chromeDir);
  const profileDirs = entries.filter(
    e => e === 'Default' || /^Profile \d+$/.test(e)
  ).sort((a, b) => {
    if (a === 'Default') return -1;
    if (b === 'Default') return 1;
    return parseInt(a.replace('Profile ', '')) - parseInt(b.replace('Profile ', ''));
  });

  const profiles = [];
  for (const dirName of profileDirs) {
    const profilePath = path.join(chromeDir, dirName);
    let displayName = dirName;

    try {
      const prefsRaw = await readFile(path.join(profilePath, 'Preferences'), 'utf-8');
      const prefs = JSON.parse(prefsRaw);
      displayName = prefs?.profile?.name || dirName;
    } catch {}

    // Use Python to check cookies (avoids native sqlite3 dependency in Node)
    let hasSS = null;
    let hasSC = null;
    if (!chromeRunning) {
      try {
        const result = execSync(
          `python3 -c "
import sqlite3, shutil, os, json, sys
profile='${profilePath.replace(/'/g, "\\'")}'
cookies=os.path.join(profile,'Cookies')
if not os.path.exists(cookies):
    print(json.dumps({'ss':False,'sc':False}))
    sys.exit()
tmp=cookies+'.tmp_check'
shutil.copy2(cookies,tmp)
try:
    c=sqlite3.connect(tmp)
    ss=c.execute(\"SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%sellersprite%'\").fetchone()[0]
    sc=c.execute(\"SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%sellercentral%' OR host_key LIKE '%amazon.com%'\").fetchone()[0]
    c.close()
    print(json.dumps({'ss':ss>0,'sc':sc>0}))
except: print(json.dumps({'ss':False,'sc':False}))
finally: os.remove(tmp) if os.path.exists(tmp) else None
"`, { encoding: 'utf-8', timeout: 5000 }
        ).trim();
        const parsed = JSON.parse(result);
        hasSS = parsed.ss;
        hasSC = parsed.sc;
      } catch {}
    }

    profiles.push({
      id: dirName,
      name: displayName,
      has_sellersprite: hasSS,
      has_seller_central: hasSC,
    });
  }

  return NextResponse.json(
    { profiles, chromeRunning },
    { headers: { 'Cache-Control': 'no-cache, no-store' } }
  );
}
