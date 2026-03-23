#!/usr/bin/env python3
"""Data collection orchestrator — SellerSprite + Seller Central.

Usage:
    python3 scripts/collectors/collect.py                   # Full collection
    python3 scripts/collectors/collect.py --sellersprite-only
    python3 scripts/collectors/collect.py --seller-central-only
    python3 scripts/collectors/collect.py --dry-run          # Verify login only
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path


class ProgressWriter:
    """Write collection progress to a JSON file for GUI polling.

    When filepath is None (CLI mode), all methods are no-ops.
    """

    def __init__(self, filepath):
        self.filepath = filepath
        self.data = None
        if filepath:
            self.data = {
                'status': 'idle',
                'started_at': None,
                'phase': None,
                'current_task': None,
                'tasks': [],
                'completed': 0,
                'total': 0,
                'errors': [],
            }

    def init_tasks(self, task_list):
        if not self.data:
            return
        self.data['status'] = 'running'
        self.data['started_at'] = datetime.now().isoformat()
        self.data['tasks'] = [
            {'id': t['id'], 'label': t['label'], 'group': t['group'],
             'status': 'pending', 'file': None, 'error': None}
            for t in task_list
        ]
        self.data['total'] = len(task_list)
        self.data['completed'] = 0
        self._write()

    def task_running(self, task_id, phase=None):
        if not self.data:
            return
        self.data['current_task'] = task_id
        if phase:
            self.data['phase'] = phase
        for t in self.data['tasks']:
            if t['id'] == task_id:
                t['status'] = 'running'
                break
        self._write()

    def task_completed(self, task_id, filename=None):
        if not self.data:
            return
        for t in self.data['tasks']:
            if t['id'] == task_id:
                t['status'] = 'completed'
                t['file'] = filename
                break
        self.data['completed'] = sum(1 for t in self.data['tasks'] if t['status'] == 'completed')
        self._write()

    def task_failed(self, task_id, error):
        if not self.data:
            return
        for t in self.data['tasks']:
            if t['id'] == task_id:
                t['status'] = 'failed'
                t['error'] = error
                break
        self.data['errors'].append({'task': task_id, 'error': error})
        self.data['completed'] = sum(1 for t in self.data['tasks'] if t['status'] == 'completed')
        self._write()

    def task_skipped(self, task_id, reason=None):
        if not self.data:
            return
        for t in self.data['tasks']:
            if t['id'] == task_id:
                t['status'] = 'skipped'
                t['error'] = reason
                break
        self.data['completed'] = sum(1 for t in self.data['tasks']
                                     if t['status'] in ('completed', 'skipped'))
        self._write()

    def update_phase(self, phase):
        if self.data:
            self.data['phase'] = phase
            self._write()

    def finish(self, final_status='completed'):
        if not self.data:
            return
        self.data['status'] = final_status
        self.data['current_task'] = None
        self._write()

    def _write(self):
        if not self.filepath:
            return
        tmp = self.filepath + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False)
        os.replace(tmp, self.filepath)


def build_task_manifest(config, args):
    """Build the full task list from config, respecting mode flags and config options."""
    collection = config.get('collection', {})
    skip_sc = collection.get('skip_seller_central', False)
    tasks = []

    if not args.seller_central_only:
        # SellerSprite tasks
        tasks.append({'id': 'export_log_check', 'label': 'Check Export Log', 'group': 'sellersprite'})
        for asin in collection.get('reverse_asin_asins', []):
            tasks.append({'id': f'reverse_asin_{asin}', 'label': f'Reverse ASIN: {asin}', 'group': 'sellersprite'})
        comparison_asins = collection.get('comparison_asins', [])
        if len(comparison_asins) >= 2:
            tasks.append({'id': 'traffic_comparison', 'label': 'Traffic Comparison', 'group': 'sellersprite'})
        tasks.append({'id': 'keyword_research', 'label': 'Keyword Research', 'group': 'sellersprite'})
        for seed in collection.get('mining_seeds', []):
            if not seed.strip():
                continue  # Skip empty seed keywords
            tid = f'keyword_mining_{seed.replace(" ", "_")}'
            tasks.append({'id': tid, 'label': f'Keyword Mining: {seed}', 'group': 'sellersprite'})
        tasks.append({'id': 'competitor_research', 'label': 'Competitor Research', 'group': 'sellersprite'})
        for asin in collection.get('ads_insights_asins', []):
            tasks.append({'id': f'ads_insights_{asin}', 'label': f'Ads Insights: {asin}', 'group': 'sellersprite'})

    if not args.sellersprite_only and not skip_sc:
        # Seller Central tasks (skipped if skip_seller_central=true in config)
        tasks.append({'id': 'business_report', 'label': 'Business Report', 'group': 'seller_central'})
        tasks.append({'id': 'search_term_report', 'label': 'SP Search Term Report', 'group': 'seller_central'})
        tasks.append({'id': 'campaign_report', 'label': 'SP Campaign Report', 'group': 'seller_central'})
        tasks.append({'id': 'fba_fee_preview', 'label': 'FBA Fee Preview', 'group': 'seller_central'})

    return tasks

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.collectors.utils import (
    setup_browser, setup_browser_adspower, adspower_stop_browser,
    BrowserLaunchError, PROJECT_ROOT as PROJ_ROOT
)
from scripts.collectors.sellersprite import SellerSpriteCollector
from scripts.collectors.seller_central import SellerCentralCollector

# Logging
LOG_DIR = PROJ_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_DIR / 'collector.log'), encoding='utf-8'),
    ],
)
logger = logging.getLogger('collector')


def load_config(product_id=None):
    """Load config - from data/{product_id}/config.json if product_id given, else root config.json."""
    if product_id:
        from scripts.config_manager import get_product_config
        return get_product_config(product_id)
    config_path = PROJ_ROOT / 'config.json'
    if not config_path.exists():
        logger.error(f"config.json not found at {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_summary(ss_results, sc_results):
    """Print a formatted summary of all collection results."""
    print("\n" + "=" * 60)
    print("COLLECTION SUMMARY")
    print("=" * 60)

    all_results = []

    if ss_results:
        print("\nSellerSprite:")
        for r in ss_results:
            status = r.get('status', 'UNKNOWN')
            icon = '\u2705' if 'OK' in status else '\u274c' if 'FAIL' in status else '\u23ed'
            task = r.get('task', '?')
            file = r.get('file', r.get('error', ''))
            detail = f" \u2192 {file}" if r.get('file') else f" ({file})" if file else ""
            print(f"  {icon} {task}: {status}{detail}")
            all_results.append(r)

    if sc_results:
        print("\nSeller Central:")
        for r in sc_results:
            status = r.get('status', 'UNKNOWN')
            icon = '\u2705' if 'OK' in status else '\u274c' if 'FAIL' in status else '\u23ed'
            task = r.get('task', '?')
            file = r.get('file', r.get('error', ''))
            detail = f" \u2192 {file}" if r.get('file') else f" ({file})" if file else ""
            print(f"  {icon} {task}: {status}{detail}")
            all_results.append(r)

    ok = sum(1 for r in all_results if 'OK' in r.get('status', ''))
    failed = sum(1 for r in all_results if 'FAIL' in r.get('status', ''))
    skipped = sum(1 for r in all_results if 'SKIP' in r.get('status', ''))

    print(f"\nTotal: {ok} succeeded, {failed} failed, {skipped} skipped")
    print("=" * 60)

    # List files in inputs/
    ss_dir = PROJ_ROOT / 'inputs' / 'sellersprite'
    sc_dir = PROJ_ROOT / 'inputs' / 'seller-central'
    ss_files = list(ss_dir.glob('*.xlsx')) if ss_dir.exists() else []
    sc_files = list(sc_dir.glob('*.csv')) if sc_dir.exists() else []
    print(f"\ninputs/sellersprite/: {len(ss_files)} .xlsx files")
    print(f"inputs/seller-central/: {len(sc_files)} .csv files")

    if ok > 0:
        print(f"\nNext step: python3 scripts/generate_report.py")

    return ok, failed


async def main():
    parser = argparse.ArgumentParser(description='Collect data from SellerSprite & Seller Central')
    parser.add_argument('--sellersprite-only', action='store_true',
                        help='Only collect from SellerSprite')
    parser.add_argument('--seller-central-only', action='store_true',
                        help='Only collect from Seller Central')
    parser.add_argument('--dry-run', action='store_true',
                        help='Verify login status only, no downloads')
    parser.add_argument('--headless', action='store_true',
                        help='Run in headless mode (may trigger anti-bot detection)')
    default_progress = str(PROJECT_ROOT / 'logs' / 'collect_progress.json')
    parser.add_argument('--progress-file', type=str, default=default_progress,
                        help='Path to write progress JSON (for GUI polling)')
    parser.add_argument('--chrome-profile', type=str, default=None,
                        help='Chrome profile directory name (e.g. "Default", "Profile 2")')
    parser.add_argument('--discover', type=str, default=None,
                        help='Amazon product URL to discover and analyze')
    parser.add_argument('--product-id', type=str, default=None,
                        help='Product ID for multi-product mode')
    args = parser.parse_args()

    product_id = args.product_id

    # Override progress file path for multi-product mode
    if product_id:
        from scripts.config_manager import get_product_paths
        ppaths = get_product_paths(product_id)
        os.makedirs(ppaths['logs'], exist_ok=True)
        if args.progress_file == default_progress:
            args.progress_file = os.path.join(ppaths['logs'], 'collect_progress.json')

    config = load_config(product_id=product_id)

    if 'collection' not in config:
        logger.error("No 'collection' section in config.json. Please add collection settings.")
        sys.exit(1)

    # Initialize progress writer (no-op when --progress-file is not set)
    progress = ProgressWriter(args.progress_file)
    if not args.discover:
        progress.init_tasks(build_task_manifest(config, args))

    download_dir = tempfile.mkdtemp(prefix='ecomm_collect_')
    logger.info(f"Temp download dir: {download_dir}")

    pw = None
    context = None
    ss_results = []
    sc_results = []

    def on_task_start(task_id, phase):
        progress.task_running(task_id, phase)

    def on_task_done(result):
        task_id = result.get('task', '')
        status = result.get('status', '')
        if 'OK' in status:
            progress.task_completed(task_id, result.get('file'))
        elif 'FAIL' in status:
            progress.task_failed(task_id, result.get('error', 'Unknown'))
        elif 'SKIP' in status:
            progress.task_skipped(task_id, result.get('error'))

    try:
        # Launch browser — AdsPower or Chrome profile
        use_adspower = config.get('adspower', {}).get('enabled', False)
        adspower_user_id = None
        browser = None

        try:
            if use_adspower:
                logger.info("Launching browser via AdsPower...")
                pw, browser, page, adspower_user_id = await setup_browser_adspower(config)
                context = browser.contexts[0]
            else:
                profile = args.chrome_profile
                logger.info(f"Launching browser with Chrome profile: {profile or 'default from config'}...")
                pw, context, page = await setup_browser(
                    config, headless=args.headless, profile_override=profile
                )
        except BrowserLaunchError as e:
            logger.error(f"Browser launch failed: {e}")
            progress.finish('failed')
            if progress.data:
                progress.data['errors'].append({'task': '_browser', 'error': str(e)})
                progress._write()
            return
        logger.info("Browser launched successfully")

        # Discovery mode: URL → discover → collect → pipeline
        if args.discover:
            logger.info(f"Discovery mode: {args.discover}")
            progress.update_phase('discovery')

            from scripts.collectors.product_discovery import run_discovery, extract_asin_from_url

            # Validate URL
            asin = extract_asin_from_url(args.discover)
            if not asin:
                logger.error(f"Could not extract ASIN from: {args.discover}")
                progress.finish('failed')
                return

            logger.info(f"Extracted ASIN: {asin}")

            # Run discovery
            discovery_result = await run_discovery(page, args.discover)

            if discovery_result.get('status') != 'completed':
                logger.error(f"Discovery failed: {discovery_result.get('error', 'Unknown')}")
                progress.finish('failed')
                return

            logger.info(f"Discovery complete: {len(discovery_result.get('competitors', []))} competitors, "
                       f"{len(discovery_result.get('seed_keywords', []))} seeds")

            # Write discovery results to progress
            if hasattr(progress, 'data') and progress.data:
                progress.data['discovery'] = discovery_result
                progress._write()

            # Reload config (it was updated by discovery)
            config = load_config(product_id=product_id)

            # Rebuild task manifest with new config
            # Fake args for task manifest
            class FakeArgs:
                sellersprite_only = True   # Only collect SellerSprite (no Seller Central)
                seller_central_only = False

            tasks = build_task_manifest(config, FakeArgs())
            progress.init_tasks(tasks)

            # Continue to collection phase (fall through to the normal collection code below)
            logger.info("Proceeding to collection phase...")
            args.sellersprite_only = True   # Only collect SellerSprite for now
            args.seller_central_only = False

        if args.dry_run:
            # Just verify login status
            logger.info("Dry run — checking login status only")
            # Check tool page — also detect GUEST mode (page loads but can't export)
            await page.goto('https://www.sellersprite.com/v3/keyword-reverse', timeout=30000)
            await page.wait_for_timeout(3000)
            ss_ok = 'login' not in page.url.lower() and 'signin' not in page.url.lower()
            if ss_ok:
                guest = await page.query_selector('header :text("GUEST"), header :text("Not Logged"), nav :text("GUEST"), nav :text("Not Logged")')
                if guest:
                    ss_ok = False
            print(f"SellerSprite login: {'OK' if ss_ok else 'NOT LOGGED IN'} (url: {page.url[:60]})")

            await page.goto('https://sellercentral.amazon.com', timeout=30000)
            await page.wait_for_timeout(3000)
            sc_ok = 'signin' not in page.url.lower()
            print(f"Seller Central login: {'OK' if sc_ok else 'NOT LOGGED IN'}")
            progress.finish('completed')
            return

        # Browser health check before collection phase
        # (Discovery may have spent 60+s waiting for results, browser could be dead)
        try:
            if page.is_closed():
                raise Exception("Page is closed")
            await page.evaluate('1')  # CDP round-trip
        except Exception:
            logger.warning("Browser died after discovery — attempting page recovery...")
            try:
                context = page.context
                if context.pages:
                    page = context.pages[-1]
                    await page.evaluate('1')  # Verify recovered page is alive
                    logger.info("Recovered active page from context")
                else:
                    page = await context.new_page()
                    logger.info("Created new page in existing context")
            except Exception as e2:
                logger.error(f"Browser recovery failed: {e2} — collection will likely fail")

        # Phase 1: SellerSprite
        if not args.seller_central_only:
            logger.info("Starting SellerSprite collection...")
            ss = SellerSpriteCollector(config, page, download_dir,
                                       on_task_start=lambda tid: on_task_start(tid, 'sellersprite'),
                                       on_task_done=on_task_done)
            ss_results = await ss.collect_all()

        # Phase 2: Seller Central
        skip_sc = config.get('collection', {}).get('skip_seller_central', False)
        if skip_sc:
            logger.info("Seller Central skipped (skip_seller_central=true in config)")
        if not args.sellersprite_only and not skip_sc:
            # Check browser health before starting SC (browser may have died during SS)
            try:
                if page.is_closed():
                    raise Exception("Page is closed")
                await page.evaluate('1')  # CDP round-trip check
            except Exception:
                logger.error("Browser died during SellerSprite — skipping Seller Central")
                # Mark all SC tasks as aborted
                for t in progress.data.get('tasks', []):
                    if t.get('group') == 'seller_central' and t.get('status') == 'pending':
                        t['status'] = 'failed'
                        t['error'] = 'Browser closed before Seller Central started'
                        progress._write()
            else:
                logger.info("Starting Seller Central collection...")
                sc = SellerCentralCollector(config, page, download_dir,
                                            on_task_start=lambda tid: on_task_start(tid, 'seller_central'),
                                            on_task_done=on_task_done)
                sc_results = await sc.collect_all()

        # Summary
        ok, failed = print_summary(ss_results, sc_results)

        # Write collection log
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'sellersprite_results': ss_results,
            'seller_central_results': sc_results,
            'succeeded': ok,
            'failed': failed,
        }
        log_path = LOG_DIR / 'collection_log.json'
        logs = []
        if log_path.exists():
            try:
                with open(log_path, 'r') as f:
                    logs = json.load(f)
            except Exception:
                logs = []
        logs.append(log_entry)
        with open(log_path, 'w') as f:
            json.dump(logs, f, indent=2, default=str)

        progress.finish('completed' if failed == 0 else 'completed_with_errors')

    except KeyboardInterrupt:
        logger.info("Collection interrupted by user")
        progress.finish('interrupted')
    except Exception as e:
        logger.error(f"Collection failed: {e}", exc_info=True)
        progress.finish('failed')
    finally:
        if use_adspower and adspower_user_id:
            # Don't close the AdsPower browser — just disconnect Playwright
            ads_config = config.get('adspower', {})
            adspower_stop_browser(
                ads_config.get('api_url', 'http://local.adspower.net:50325'),
                adspower_user_id,
                ads_config.get('api_key'),
            )
        elif context:
            await context.close()
        if pw:
            await pw.stop()
        # Clean up temp download dir
        shutil.rmtree(download_dir, ignore_errors=True)
        # Clean up lock files
        if product_id:
            from scripts.config_manager import get_product_paths
            log_dir = Path(get_product_paths(product_id)['logs'])
        else:
            log_dir = PROJECT_ROOT / 'logs'
        for lock_name in ['.discovering', '.collecting']:
            lock_path = log_dir / lock_name
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except OSError:
                pass
        logger.info("Browser closed, temp files cleaned up")

    # Auto-run pipeline AFTER browser cleanup (pipeline doesn't need browser)
    # Always run pipeline — even with partial data, generate whatever report we can
    logger.info("Running report pipeline...")
    progress.update_phase('pipeline')
    pipeline_ok = False
    try:
        import subprocess
        cmd = ['python3', str(PROJECT_ROOT / 'scripts' / 'generate_report.py')]
        if product_id:
            cmd.extend(['--product-id', product_id])
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            timeout=600,  # 10 minutes — large keyword sets can take 5+ min
        )
        if result.returncode == 0:
            logger.info("Pipeline completed successfully")
            pipeline_ok = True
        else:
            logger.error(f"Pipeline failed: {result.stderr[:500]}")
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")

    # Send macOS desktop notification
    _send_notification(pipeline_ok, progress, product_id=product_id)


def _send_notification(pipeline_ok, progress, product_id=None):
    """Send macOS notification with results summary and file paths."""
    import subprocess as _sp

    if product_id:
        from scripts.config_manager import get_product_paths
        ppaths = get_product_paths(product_id)
        outputs_dir = Path(ppaths['outputs'])
        processed_dir = Path(ppaths['processed'])
    else:
        outputs_dir = PROJECT_ROOT / 'outputs'
        processed_dir = PROJECT_ROOT / 'processed'

    # Find generated files
    xlsx_files = sorted(outputs_dir.glob('*.xlsx'), key=lambda f: f.stat().st_mtime, reverse=True)
    json_files = sorted(processed_dir.glob('*.json'))
    summary_files = sorted(outputs_dir.glob('*.md'), key=lambda f: f.stat().st_mtime, reverse=True)

    # Build notification message
    status = progress.data.get('status', 'unknown') if hasattr(progress, 'data') else 'unknown'
    tasks = progress.data.get('tasks', []) if hasattr(progress, 'data') else []
    completed = sum(1 for t in tasks if t.get('status') == 'completed')
    failed = sum(1 for t in tasks if t.get('status') == 'failed')
    total = len(tasks)

    if pipeline_ok:
        title = "✅ Collection & Report Complete"
        msg_parts = [f"Tasks: {completed}/{total} succeeded"]
        if failed:
            msg_parts[0] += f", {failed} failed"
        if xlsx_files:
            msg_parts.append(f"Report: {xlsx_files[0].name}")
        msg_parts.append(f"JSON: {len(json_files)} files in processed/")
        msg = "\\n".join(msg_parts)
    else:
        title = "⚠️ Collection Done — Pipeline Failed"
        msg = f"Tasks: {completed}/{total} succeeded, {failed} failed\\nPipeline did not generate report."

    # macOS notification via osascript
    try:
        _sp.run([
            'osascript', '-e',
            f'display notification "{msg}" with title "{title}" sound name "Glass"'
        ], timeout=5, capture_output=True)
    except Exception:
        pass

    # Log file paths for easy review
    logger.info("=" * 60)
    logger.info("📊 OUTPUT FILES:")
    if xlsx_files:
        for f in xlsx_files[:3]:
            logger.info(f"  Excel: {f}")
    if summary_files:
        for f in summary_files[:2]:
            logger.info(f"  Summary: {f}")
    if json_files:
        logger.info(f"  JSON ({len(json_files)} files): {processed_dir}/")
    logger.info(f"  Logs: {PROJECT_ROOT / 'logs' / 'collector.log'}")
    logger.info("=" * 60)

    # Also write output paths to progress for the dashboard to display
    if hasattr(progress, 'data') and progress.data:
        progress.data['output_files'] = {
            'excel': [str(f) for f in xlsx_files[:3]],
            'summary': [str(f) for f in summary_files[:2]],
            'json_dir': str(processed_dir),
            'json_count': len(json_files),
        }
        progress._write()


if __name__ == '__main__':
    asyncio.run(main())
