"""Shared utilities for Playwright-based data collectors."""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import glob
import shutil
import logging
import platform
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger('collector')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUTS_SS = PROJECT_ROOT / 'inputs' / 'sellersprite'
INPUTS_SC = PROJECT_ROOT / 'inputs' / 'seller-central'


# ─── AdsPower Integration ───────────────────────────────────────────

def adspower_api(base_url, endpoint, api_key=None, params=None):
    """Call AdsPower Local API and return parsed JSON response."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    if params:
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        url += f'?{qs}'
    req = urllib.request.Request(url)
    if api_key:
        req.add_header('Authorization', f'Bearer {api_key}')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.URLError as e:
        raise BrowserLaunchError(
            f"Cannot reach AdsPower at {base_url}. Is AdsPower running? Error: {e}"
        )


def adspower_list_profiles(base_url, api_key=None):
    """List all AdsPower browser profiles."""
    data = adspower_api(base_url, '/api/v1/user/list', api_key, {'page': '1', 'page_size': '100'})
    if data.get('code') != 0:
        raise BrowserLaunchError(f"AdsPower API error: {data.get('msg')}")
    return data.get('data', {}).get('list', [])


def adspower_start_browser(base_url, user_id, api_key=None):
    """Start an AdsPower browser profile. Returns WebSocket URL and debug port."""
    data = adspower_api(base_url, '/api/v1/browser/start', api_key, {'user_id': user_id})
    if data.get('code') != 0:
        raise BrowserLaunchError(f"AdsPower failed to start browser: {data.get('msg')}")
    ws_url = data['data']['ws']['puppeteer']
    debug_port = data['data'].get('debug_port')
    logger.info(f"AdsPower browser started: user_id={user_id}, port={debug_port}")
    return ws_url, debug_port


def adspower_stop_browser(base_url, user_id, api_key=None):
    """Stop an AdsPower browser profile."""
    try:
        data = adspower_api(base_url, '/api/v1/browser/stop', api_key, {'user_id': user_id})
        logger.info(f"AdsPower browser stopped: user_id={user_id}")
        return data.get('code') == 0
    except Exception as e:
        logger.warning(f"Failed to stop AdsPower browser: {e}")
        return False


def adspower_check_status(base_url, user_id, api_key=None):
    """Check if an AdsPower browser profile is running."""
    try:
        data = adspower_api(base_url, '/api/v1/browser/active', api_key, {'user_id': user_id})
        return data.get('data', {}).get('status') == 'Active'
    except Exception:
        return False


async def setup_browser_adspower(config):
    """Launch browser via AdsPower API and connect Playwright.

    Returns (pw, browser, page, adspower_user_id) tuple.
    The caller should call adspower_stop_browser() when done.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise BrowserLaunchError("Playwright not installed. Run: pip3 install playwright")

    ads_config = config.get('adspower', {})
    base_url = ads_config.get('api_url', 'http://local.adspower.net:50325')
    api_key = ads_config.get('api_key')
    user_id = ads_config.get('profile_id')

    if not user_id:
        # Auto-detect: use first available profile
        profiles = adspower_list_profiles(base_url, api_key)
        if not profiles:
            raise BrowserLaunchError("No AdsPower profiles found. Create one in AdsPower first.")
        user_id = profiles[0]['user_id']
        logger.info(f"Auto-selected AdsPower profile: {profiles[0].get('name', user_id)}")

    # Start the browser and get WebSocket URL
    ws_url, _ = adspower_start_browser(base_url, user_id, api_key)

    # Connect Playwright via CDP
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(ws_url)
    except Exception as e:
        await pw.stop()
        raise BrowserLaunchError(f"Failed to connect to AdsPower browser: {e}")

    # Use the existing context and page from AdsPower
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    # AdsPower may have multiple pages open — use the last one or create new
    if context.pages:
        page = context.pages[-1]
    else:
        page = await context.new_page()

    # Navigate to a blank page first to ensure the page is active
    try:
        await page.goto('about:blank', timeout=5000)
    except Exception:
        # If current page is dead, create a new one
        page = await context.new_page()

    logger.info(f"Connected to AdsPower browser: {user_id}")
    return pw, browser, page, user_id


def get_chrome_user_data_dir(config=None):
    """Return the Chrome user data directory for the current platform."""
    if config and config.get('collection', {}).get('chrome_profile_dir'):
        return os.path.expanduser(config['collection']['chrome_profile_dir'])

    system = platform.system()
    if system == 'Darwin':
        return os.path.expanduser('~/Library/Application Support/Google/Chrome')
    elif system == 'Windows':
        return os.path.expandvars(r'%LOCALAPPDATA%\\Google\\Chrome\\User Data')
    else:  # Linux
        return os.path.expanduser('~/.config/google-chrome')

# Keep old name as alias
get_chrome_profile_path = get_chrome_user_data_dir


def get_chrome_profile_name(config=None):
    """Return which Chrome profile to use (e.g. 'Default', 'Profile 1')."""
    if config and config.get('collection', {}).get('chrome_profile_name'):
        return config['collection']['chrome_profile_name']
    return 'Default'


def list_chrome_profiles(config=None):
    """List all Chrome profiles with display names and cookie info.

    Returns list of dicts: [{id, name, has_sellersprite, has_seller_central}]
    """
    chrome_dir = get_chrome_user_data_dir(config)
    profiles = []

    # Profile directories: 'Default', 'Profile 1', 'Profile 2', etc.
    candidates = []
    if os.path.isdir(os.path.join(chrome_dir, 'Default')):
        candidates.append('Default')
    for entry in sorted(os.listdir(chrome_dir)):
        if re.match(r'^Profile \d+$', entry):
            candidates.append(entry)

    for profile_id in candidates:
        profile_dir = os.path.join(chrome_dir, profile_id)
        prefs_path = os.path.join(profile_dir, 'Preferences')

        display_name = profile_id
        try:
            with open(prefs_path, 'r', encoding='utf-8') as f:
                prefs = json.load(f)
            display_name = prefs.get('profile', {}).get('name', profile_id)
        except Exception:
            pass

        # Check cookies for SellerSprite and Seller Central
        has_ss = False
        has_sc = False
        cookies_path = os.path.join(profile_dir, 'Cookies')
        if os.path.exists(cookies_path):
            try:
                # Copy cookies db to avoid lock conflicts with running Chrome
                tmp_cookies = os.path.join(profile_dir, '.cookies_check_tmp')
                shutil.copy2(cookies_path, tmp_cookies)
                conn = sqlite3.connect(tmp_cookies)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%sellersprite%'"
                )
                has_ss = cursor.fetchone()[0] > 0
                cursor.execute(
                    "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%sellercentral%' OR host_key LIKE '%amazon.com%'"
                )
                has_sc = cursor.fetchone()[0] > 0
                conn.close()
                os.remove(tmp_cookies)
            except Exception:
                pass  # Cookies DB may be locked or encrypted

        profiles.append({
            'id': profile_id,
            'name': display_name,
            'has_sellersprite': has_ss,
            'has_seller_central': has_sc,
        })

    return profiles


def is_chrome_running():
    """Check if Google Chrome is currently running."""
    try:
        # Use pgrep with exact match on the Chrome binary path to avoid
        # false positives from other processes (e.g. "Claude in Chrome" MCP)
        result = subprocess.run(
            ['pgrep', '-f', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


class BrowserLaunchError(Exception):
    """Raised when browser cannot be launched (Chrome running, profile locked, etc.)."""
    pass


async def setup_browser(config=None, headless=False, profile_override=None):
    """Launch Playwright Chromium with the user's Chrome profile (persistent context).

    Returns (pw, context, page) tuple. headless=False required — SellerSprite
    detects headless browsers.

    Raises BrowserLaunchError with user-friendly message on failure.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise BrowserLaunchError(
            "Playwright not installed. Run: pip3 install playwright && python3 -m playwright install chromium"
        )

    user_data_dir = get_chrome_user_data_dir(config)
    profile_name = profile_override or get_chrome_profile_name(config)
    profile_path = os.path.join(user_data_dir, profile_name)

    # Check profile directory exists
    if not os.path.isdir(profile_path):
        raise BrowserLaunchError(
            f"Chrome profile not found: {profile_name}. "
            f"Available profiles: {', '.join(p['id'] for p in list_chrome_profiles(config))}"
        )

    # Check if Chrome is running — Playwright needs exclusive access to the profile
    if is_chrome_running():
        raise BrowserLaunchError(
            "Google Chrome is still running. Please quit Chrome completely "
            "(Cmd+Q on macOS) before starting collection. "
            "Playwright needs exclusive access to your Chrome profile."
        )

    # Check for stale SingletonLock
    lock_path = os.path.join(user_data_dir, 'SingletonLock')
    if os.path.exists(lock_path) and not is_chrome_running():
        logger.info("Removing stale Chrome SingletonLock file")
        try:
            os.remove(lock_path)
        except Exception:
            pass

    # Launch with retry (Chrome may still be shutting down)
    pw = await async_playwright().start()
    last_error = None
    for attempt in range(3):
        try:
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=headless,
                channel='chrome',
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run',
                    '--no-default-browser-check',
                ],
                viewport={'width': 1440, 'height': 900},
                accept_downloads=True,
                slow_mo=100,  # Human-like pacing
            )
            page = context.pages[0] if context.pages else await context.new_page()
            logger.info(f"Browser launched with profile: {profile_name}")
            return pw, context, page
        except Exception as e:
            last_error = e
            err_msg = str(e).lower()
            if 'single instance' in err_msg or 'lock' in err_msg or 'already' in err_msg:
                if attempt < 2:
                    logger.warning(f"Chrome profile locked, retrying in 3s (attempt {attempt + 1}/3)...")
                    import asyncio
                    await asyncio.sleep(3)
                    continue
                raise BrowserLaunchError(
                    "Chrome profile is locked. Please make sure Chrome is fully closed "
                    "(check Activity Monitor for lingering Chrome processes) and try again."
                )
            raise BrowserLaunchError(f"Failed to launch browser: {e}")

    await pw.stop()
    raise BrowserLaunchError(f"Failed to launch browser after 3 attempts: {last_error}")


async def wait_for_download(page, timeout=120):
    """Wait for a Playwright download event and return the saved file path.

    Uses Playwright's built-in download event rather than polling the filesystem.
    """
    try:
        async with page.expect_download(timeout=timeout * 1000) as download_info:
            pass  # Caller should trigger the download before calling this
    except Exception:
        # Fallback: this function is called after download is already triggered
        pass

    download = download_info.value
    dest = os.path.join(
        str(PROJECT_ROOT / 'downloads'),
        download.suggested_filename
    )
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    await download.save_as(dest)
    logger.info(f"Downloaded: {download.suggested_filename}")
    return dest


async def wait_for_download_via_event(page, trigger_action, timeout=120):
    """Trigger an action and wait for the resulting download.

    Args:
        page: Playwright page
        trigger_action: async callable that triggers the download (e.g. clicking a button)
        timeout: seconds to wait

    Returns:
        Path to the saved file.
    """
    download_dir = str(PROJECT_ROOT / 'downloads')
    os.makedirs(download_dir, exist_ok=True)

    async with page.expect_download(timeout=timeout * 1000) as download_info:
        await trigger_action()

    download = download_info.value
    dest = os.path.join(download_dir, download.suggested_filename)
    await download.save_as(dest)
    logger.info(f"Downloaded: {download.suggested_filename}")
    return dest


def wait_for_file(directory, prefix, timeout=120, poll_interval=2):
    """Poll filesystem for a new file matching prefix. Fallback for non-event downloads.

    Returns filepath when found, raises TimeoutError if not.
    """
    directory = str(directory)
    # Snapshot existing files
    before = set(glob.glob(os.path.join(directory, f'{prefix}*')))
    deadline = time.time() + timeout

    while time.time() < deadline:
        current = set(glob.glob(os.path.join(directory, f'{prefix}*')))
        new_files = current - before
        if new_files:
            # Return the newest file
            newest = max(new_files, key=os.path.getmtime)
            # Make sure it's not still being written (size stable for 1s)
            size1 = os.path.getsize(newest)
            time.sleep(1)
            size2 = os.path.getsize(newest)
            if size1 == size2 and size1 > 0:
                return newest
        time.sleep(poll_interval)

    raise TimeoutError(f"No new file matching '{prefix}*' in {directory} after {timeout}s")


def move_to_inputs(filepath, category='sellersprite'):
    """Move downloaded file to the correct inputs/ subdirectory.

    Args:
        filepath: path to the downloaded file
        category: 'sellersprite' or 'seller-central'

    Returns:
        New filepath in inputs/
    """
    dest_dir = INPUTS_SS if category == 'sellersprite' else INPUTS_SC
    os.makedirs(str(dest_dir), exist_ok=True)

    filename = os.path.basename(filepath)
    dest = os.path.join(str(dest_dir), filename)

    # If file already exists, overwrite
    if os.path.exists(dest):
        os.remove(dest)

    shutil.move(filepath, dest)
    logger.info(f"Moved {filename} → inputs/{category}/")
    return dest


async def check_export_log(page, base_url='https://www.sellersprite.com'):
    """Navigate to SellerSprite export log, parse the table, return list of exports.

    Each export is a dict with: filename, status, date, module, download_url.
    Used to avoid duplicate exports and to download completed ones.
    """
    await page.goto(f'{base_url}/v2/export-log', wait_until='networkidle', timeout=30000)
    await page.wait_for_timeout(2000)

    exports = []
    rows = await page.query_selector_all('table tbody tr')

    for row in rows:
        cells = await row.query_selector_all('td')
        if len(cells) < 5:
            continue

        # SellerSprite export log table columns (2026):
        # [0] = checkbox (#), [1] = filename + badge, [2] = source, [3] = date, [4] = status, [5] = actions
        raw_filename = (await cells[1].inner_text()).strip()
        # Strip "Latest", "New" badges from filename
        import re as _re
        filename = _re.sub(r'\s*(Latest|New|最新)\s*$', '', raw_filename).strip()

        export = {
            'filename': filename,
            'status': (await cells[4].inner_text()).strip() if len(cells) > 4 else '',
            'date': (await cells[3].inner_text()).strip() if len(cells) > 3 else '',
            'module': (await cells[2].inner_text()).strip() if len(cells) > 2 else '',
            'download_url': None,
        }

        # Look for download link (direct URL to xlsx)
        link = await row.query_selector('a[href*="download"], a[download], a[href*=".xlsx"], a[href*="batch-exports"]')
        if link:
            export['download_url'] = await link.get_attribute('href')

        exports.append(export)

    logger.info(f"Export log: {len(exports)} entries found")
    return exports


async def poll_export_log_for_new(page, existing_count, prefix='',
                                   timeout=300, poll_interval=10,
                                   base_url='https://www.sellersprite.com'):
    """Poll export log until a new completed export appears.

    Uses a separate browser tab so the main page state is preserved.
    Scans up to 15 rows (not just 5) to find the matching export.
    Detects 'exporting' status and extends timeout automatically.

    Args:
        page: Playwright page (main page — NOT navigated away)
        existing_count: number of exports before triggering a new one
        prefix: filename prefix to match (e.g. 'ExpandKeywords')
        timeout: seconds to wait
        poll_interval: seconds between polls

    Returns:
        The new export dict, or None if timeout.
    """
    import re as _re
    deadline = time.time() + timeout
    context = page.context
    poll_page = await context.new_page()
    found_exporting = False  # Track if we saw the file being generated

    try:
        while time.time() < deadline:
            # Navigate the poll tab (not the main page)
            try:
                await poll_page.goto(f'{base_url}/v2/export-log', wait_until='load', timeout=30000)
            except Exception:
                try:
                    await poll_page.goto(f'{base_url}/v2/export-log', wait_until='domcontentloaded', timeout=20000)
                except Exception:
                    logger.warning("Export log tab navigation failed, retrying next poll...")
                    await poll_page.wait_for_timeout(poll_interval * 1000)
                    continue

            # Wait for the table to render (JS-driven)
            try:
                await poll_page.wait_for_selector('table tbody tr', timeout=10000)
            except Exception:
                logger.info("Export log table not rendered yet, retrying...")
                await poll_page.wait_for_timeout(poll_interval * 1000)
                continue

            rows = await poll_page.query_selector_all('table tbody tr')

            # Scan up to 15 rows (exports may not be at the top)
            for row in rows[:15]:
                cells = await row.query_selector_all('td')
                if len(cells) < 5:
                    continue

                raw_filename = (await cells[1].inner_text()).strip()
                filename = _re.sub(r'\s*(Latest|New|最新)\s*$', '', raw_filename).strip()
                status = (await cells[4].inner_text()).strip().lower()

                if prefix and not filename.startswith(prefix):
                    continue

                # Found our file — check status
                if 'completed' in status or 'complete' in status or '完成' in status:
                    link = await row.query_selector('a[href*=".xlsx"], a[href*="batch-exports"], a[href*="download"], a[download]')
                    download_url = await link.get_attribute('href') if link else None
                    return {
                        'filename': filename,
                        'status': status,
                        'download_url': download_url,
                    }
                elif 'exporting' in status or '导出中' in status or 'generating' in status or 'processing' in status:
                    # File is being generated — extend deadline if first time seeing it
                    if not found_exporting:
                        found_exporting = True
                        extra = 120  # Give 2 more minutes for generation
                        deadline = max(deadline, time.time() + extra)
                        logger.info(f"Export '{prefix}' is being generated on server, extended wait by {extra}s")
                    break  # Stop scanning rows, wait and re-check

            logger.info(f"Export not ready yet, polling again in {poll_interval}s...")
            await poll_page.wait_for_timeout(poll_interval * 1000)

        logger.warning(f"Export poll timeout after {timeout}s for prefix '{prefix}'")
        return None
    finally:
        try:
            await poll_page.close()
        except Exception:
            pass


async def download_from_export_log(page, export_entry, download_dir):
    """Download a file from the export log by clicking its download link.

    Returns the path to the downloaded file.
    Supports both direct URL downloads and click-to-download.
    """
    download_dir = str(download_dir)
    os.makedirs(download_dir, exist_ok=True)

    # Method 1: Direct URL download (if we have a batch-exports URL)
    download_url = export_entry.get('download_url')
    if download_url and 'batch-exports' in download_url:
        import urllib.request
        filename = export_entry.get('filename', 'export') + '.xlsx'
        if not filename.endswith('.xlsx'):
            filename += '.xlsx'
        dest = os.path.join(download_dir, filename)
        try:
            # Navigate to the download URL to trigger browser download
            async with page.expect_download(timeout=60000) as download_info:
                await page.evaluate(f'() => window.open("{download_url}", "_blank")')
            download = await download_info.value
            dest = os.path.join(download_dir, download.suggested_filename)
            await download.save_as(dest)
            logger.info(f"Downloaded via direct URL: {download.suggested_filename}")
            return dest
        except Exception as e:
            logger.warning(f"Direct URL download failed, trying click method: {e}")

    # Method 2: Navigate to export log and click download for the matching row
    target_filename = export_entry.get('filename', '')
    try:
        await page.goto('https://www.sellersprite.com/v2/export-log', wait_until='load', timeout=30000)
    except Exception:
        await page.goto('https://www.sellersprite.com/v2/export-log', wait_until='domcontentloaded', timeout=20000)

    try:
        await page.wait_for_selector('table tbody tr', timeout=10000)
    except Exception:
        raise ValueError("Export log table didn't render for download")

    rows = await page.query_selector_all('table tbody tr')
    download_btn = None
    for row in rows[:15]:
        cells = await row.query_selector_all('td')
        if len(cells) < 5:
            continue
        row_text = (await cells[1].inner_text()).strip()
        if target_filename and target_filename in row_text:
            download_btn = await row.query_selector(
                'a[href*=".xlsx"], a[href*="batch-exports"], a[href*="download"], '
                'a[download], button:has-text("Download"), button:has-text("下载"), '
                '.download-btn, [class*="download"]'
            )
            if not download_btn:
                download_btn = await row.query_selector('a[href]')
            break

    if not download_btn:
        raise ValueError(f"No download button found for {target_filename}")

    async with page.expect_download(timeout=60000) as download_info:
        await download_btn.click(force=True)

    download = await download_info.value
    dest = os.path.join(download_dir, download.suggested_filename)
    await download.save_as(dest)
    logger.info(f"Downloaded from export log: {download.suggested_filename}")
    return dest


async def ensure_marketplace_us(page):
    """Ensure the SellerSprite marketplace is set to United States.

    Looks for marketplace selector and sets it to US if not already selected.
    """
    # Try common selector patterns for marketplace dropdown
    selectors = [
        'select[class*="marketplace"]',
        'select[name*="marketplace"]',
        '[class*="country-select"] select',
        '.marketplace-selector select',
        'select:has(option[value="US"])',
    ]

    for selector in selectors:
        el = await page.query_selector(selector)
        if el:
            await el.select_option(value='US')
            logger.info("Marketplace set to US via select")
            await page.wait_for_timeout(1000)
            return True

    # Try clicking a dropdown button approach
    dropdown_triggers = [
        '[class*="marketplace"] .ant-select',
        '.country-flag',
        'img[alt*="US"], img[alt*="United States"]',
    ]
    for trigger in dropdown_triggers:
        el = await page.query_selector(trigger)
        if el:
            await el.click()
            await page.wait_for_timeout(500)
            us_option = await page.query_selector(
                '[class*="option"]:has-text("United States"), '
                '[class*="option"]:has-text("美国"), '
                'li:has-text("United States"), li:has-text("US")'
            )
            if us_option:
                await us_option.click()
                logger.info("Marketplace set to US via dropdown")
                await page.wait_for_timeout(1000)
                return True

    logger.warning("Could not find marketplace selector — may already be set to US")
    return False


async def detect_login_redirect(page, expected_domain):
    """Check if the page was redirected to a login page.

    Returns True if logged out (needs re-login).
    """
    url = page.url.lower()
    login_indicators = ['login', 'signin', 'sign-in', 'auth', 'sso']
    if any(ind in url for ind in login_indicators) and expected_domain not in url:
        return True
    return False


async def safe_goto(page, url, retries=1, timeout=30000):
    """Navigate to a URL with retry on failure.

    Uses 'domcontentloaded' for Amazon pages (they never reach 'networkidle'
    due to ad/tracking background requests). Uses 'load' for other sites.
    """
    # Amazon pages never reach networkidle — use domcontentloaded
    is_amazon = 'amazon.com' in url
    wait_strategy = 'domcontentloaded' if is_amazon else 'load'

    for attempt in range(retries + 1):
        try:
            await page.goto(url, wait_until=wait_strategy, timeout=timeout)
            return True
        except Exception as e:
            if attempt < retries:
                logger.warning(f"Navigation failed ({e}), retrying...")
                try:
                    await page.wait_for_timeout(3000)
                except Exception:
                    pass
            else:
                logger.error(f"Navigation failed after {retries + 1} attempts: {url} — {e}")
                return False


async def human_delay(page, min_sec=3, max_sec=5):
    """Add a human-like delay between actions."""
    import random
    delay = random.uniform(min_sec, max_sec) * 1000
    await page.wait_for_timeout(delay)


async def take_debug_screenshot(page, name='debug'):
    """Save a screenshot for debugging when something goes wrong."""
    try:
        screenshots_dir = PROJECT_ROOT / 'logs' / 'screenshots'
        os.makedirs(str(screenshots_dir), exist_ok=True)
        path = str(screenshots_dir / f'{name}_{int(time.time())}.png')
        await page.screenshot(path=path, full_page=False, timeout=10000)
        logger.info(f"Debug screenshot saved: {path}")
        return path
    except Exception as e:
        logger.warning(f"Debug screenshot failed ({name}): {e}")
        return None
