import { NextResponse } from 'next/server';
import { readFile, writeFile, mkdir } from 'fs/promises';
import path from 'path';
import fs from 'fs';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const SETUP_FILE = path.join(PROJECT_ROOT, 'data', 'setup.json');

function getAdsPowerUrl() {
  return process.env.ADSPOWER_API_URL || 'http://host.docker.internal:50325';
}

async function readSetup() {
  try {
    return JSON.parse(await readFile(SETUP_FILE, 'utf-8'));
  } catch {
    return null;
  }
}

// GET /api/setup — check current setup state
export async function GET(req) {
  const { searchParams } = new URL(req.url);
  const action = searchParams.get('action');

  // Test AdsPower connection
  if (action === 'detect') {
    const url = getAdsPowerUrl();
    try {
      const res = await fetch(`${url}/status`, { signal: AbortSignal.timeout(5000) });
      const data = await res.json();
      return NextResponse.json({ detected: true, url, status: data });
    } catch (e) {
      // Also try localhost directly (for non-Docker)
      try {
        const res2 = await fetch('http://localhost:50325/status', { signal: AbortSignal.timeout(3000) });
        const data2 = await res2.json();
        return NextResponse.json({ detected: true, url: 'http://localhost:50325', status: data2 });
      } catch {
        return NextResponse.json({ detected: false, url, error: e.message });
      }
    }
  }

  // List profiles (requires api_key)
  if (action === 'profiles') {
    const apiKey = searchParams.get('api_key');
    const url = getAdsPowerUrl();
    try {
      const res = await fetch(`${url}/api/v1/user/list?api_key=${apiKey}`, {
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json();
      const profiles = (data.data?.list || []).map(p => ({
        id: p.user_id,
        name: p.name,
        group: p.group_name || '',
        ip: p.ip || '',
      }));
      return NextResponse.json({ success: true, profiles });
    } catch (e) {
      // Try localhost fallback
      try {
        const res2 = await fetch(`http://localhost:50325/api/v1/user/list?api_key=${apiKey}`, {
          signal: AbortSignal.timeout(5000),
        });
        const data2 = await res2.json();
        const profiles2 = (data2.data?.list || []).map(p => ({
          id: p.user_id,
          name: p.name,
          group: p.group_name || '',
          ip: p.ip || '',
        }));
        return NextResponse.json({ success: true, profiles: profiles2 });
      } catch {
        return NextResponse.json({ success: false, error: e.message });
      }
    }
  }

  // Return current setup state
  const setup = await readSetup();
  return NextResponse.json({
    configured: !!(setup?.api_key && setup?.profile_id),
    setup: setup || {},
  });
}

// POST /api/setup — save credentials
export async function POST(req) {
  try {
    const body = await req.json();
    const { api_key, profile_id, api_url } = body;

    if (!api_key || !profile_id) {
      return NextResponse.json({ error: 'api_key and profile_id are required' }, { status: 400 });
    }

    // Test connection before saving
    const testUrl = api_url || getAdsPowerUrl();
    try {
      const res = await fetch(`${testUrl}/api/v1/user/list?api_key=${api_key}`, {
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json();
      if (!data.data?.list) {
        return NextResponse.json({ error: 'API Key invalid — no profiles returned' }, { status: 400 });
      }
    } catch (e) {
      // Try localhost fallback
      try {
        await fetch(`http://localhost:50325/api/v1/user/list?api_key=${api_key}`, {
          signal: AbortSignal.timeout(5000),
        });
      } catch {
        return NextResponse.json({ error: `Cannot reach AdsPower: ${e.message}` }, { status: 400 });
      }
    }

    // Save to data/setup.json
    const setupData = {
      api_url: testUrl,
      api_key,
      profile_id,
      configured_at: new Date().toISOString(),
    };

    await mkdir(path.dirname(SETUP_FILE), { recursive: true });
    await writeFile(SETUP_FILE, JSON.stringify(setupData, null, 2));

    // Also update config.json adspower section
    try {
      const configPath = path.join(PROJECT_ROOT, 'config.json');
      const config = JSON.parse(await readFile(configPath, 'utf-8'));
      config.adspower = {
        ...config.adspower,
        enabled: true,
        api_url: testUrl,
        api_key,
        profile_id,
      };
      await writeFile(configPath, JSON.stringify(config, null, 2));
    } catch {}

    return NextResponse.json({ success: true, setup: setupData });
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
