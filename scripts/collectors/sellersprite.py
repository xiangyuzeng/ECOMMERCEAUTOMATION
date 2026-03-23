"""SellerSprite Playwright collector — automates all 10 export tasks."""

import os
import logging
from pathlib import Path

from .utils import (
    PROJECT_ROOT, INPUTS_SS,
    move_to_inputs, ensure_marketplace_us, safe_goto, human_delay,
    take_debug_screenshot, detect_login_redirect,
    check_export_log, poll_export_log_for_new, download_from_export_log,
)

logger = logging.getLogger('collector.sellersprite')

BASE_URL = 'https://www.sellersprite.com'

# Centralized selectors — update here if SellerSprite UI changes
SELECTORS = {
    # Common — use CSS case-insensitive flag [attr*="val" i] for placeholders
    'search_input': 'input[type="text"][class*="search"], input[placeholder*="ASIN" i], input[placeholder*="keyword" i], input[placeholder*="关键词"], .ant-input',
    'search_button': 'button:has-text("Search"), button:has-text("搜索"), button[type="submit"]',
    'export_button': 'button:has-text("Export"), button:has-text("导出"), button:has-text("Download"), [class*="export"]',
    'results_table': 'table tbody tr, .ant-table-tbody tr, [class*="table"] tbody tr',

    # Reverse ASIN specific
    'reverse_multi_tab': '[class*="tab"]:has-text("Reverse Multiple"), [class*="tab"]:has-text("批量反查")',
    'all_variations_toggle': 'input[type="checkbox"] + span:has-text("All Variations"), label:has-text("All Variations"), label:has-text("所有变体")',
    'asin_textarea': 'textarea[placeholder*="ASIN" i], textarea.ant-input, textarea',

    # Traffic Comparison
    'comparison_input': 'textarea[placeholder*="ASIN" i], input[placeholder*="ASIN" i]',

    # Keyword Mining — placeholder is "Keyword phrase, eg. flashlight" (capital K)
    'mining_input': 'input[placeholder*="keyword" i], input[placeholder*="关键词"], input[placeholder*="phrase" i]',

    # Competitor Research — placeholder is "Keyword, eg. garlic press"
    'competitor_input': 'input[placeholder*="keyword" i], input[placeholder*="关键词"], input[placeholder*="phrase" i]',
}


class SellerSpriteCollector:
    """Automates SellerSprite data exports via Playwright browser automation."""

    def __init__(self, config, page, download_dir, on_task_start=None, on_task_done=None):
        self.config = config
        self.page = page
        self.download_dir = download_dir
        self.collection = config.get('collection', {})
        self.delay = self.collection.get('delay_between_tasks_sec', 5)
        self.results = []
        self.on_task_start = on_task_start
        self.on_task_done = on_task_done

    def _notify_start(self, task_id):
        if self.on_task_start:
            self.on_task_start(task_id)

    def _notify_done(self, result):
        if self.on_task_done:
            self.on_task_done(result)

    async def _is_page_alive(self):
        """Check if the browser page is still open.

        Uses an actual CDP round-trip (page.evaluate) to detect when
        AdsPower kills the browser externally — page.is_closed() alone
        only checks the local Playwright state.
        """
        try:
            if self.page.is_closed():
                return False
            # Lightweight async check — verifies CDP connection is alive
            await self.page.evaluate('1')
            return True
        except Exception:
            return False

    def _abort_remaining(self, task_id, remaining_ids):
        """Mark remaining tasks as aborted when browser dies."""
        error = 'Browser closed — aborting remaining tasks'
        logger.error(error)
        results = []
        for tid in remaining_ids:
            self._notify_start(tid)
            r = {'task': tid, 'status': 'FAILED', 'error': error}
            results.append(r)
            self._notify_done(r)
        return results

    async def collect_all(self):
        """Run all SellerSprite collection tasks sequentially."""
        logger.info("=" * 50)
        logger.info("SellerSprite Collection — Starting")

        # Check if logged in
        if not await self._verify_login():
            logger.error("Not logged into SellerSprite. Please log in via Chrome first.")
            r = {'task': 'login_check', 'status': 'FAILED', 'error': 'Not logged in'}
            self._notify_done(r)
            return [r]

        # Skip export log check — we use direct downloads
        self._notify_start('export_log_check')
        r = {
            'task': 'export_log_check',
            'status': 'OK',
            'existing_count': 0,
            'note': 'Using direct download (no export log polling)',
        }
        self.results.append(r)
        self._notify_done(r)

        # Build ordered task list for clean iteration + early abort
        task_queue = []
        for asin in self.collection.get('reverse_asin_asins', []):
            task_queue.append(('reverse_asin', f'reverse_asin_{asin}', asin))
        if len(self.collection.get('comparison_asins', [])) >= 2:
            task_queue.append(('traffic_comparison', 'traffic_comparison', None))
        task_queue.append(('keyword_research', 'keyword_research', None))
        for seed in self.collection.get('mining_seeds', []):
            if not seed.strip():
                continue  # Skip empty seed keywords
            tid = f'keyword_mining_{seed.replace(" ", "_")}'
            task_queue.append(('keyword_mining', tid, seed))
        task_queue.append(('competitor_research', 'competitor_research', None))
        for asin in self.collection.get('ads_insights_asins', []):
            task_queue.append(('ads_insights', f'ads_insights_{asin}', asin))

        for i, (task_type, task_id, param) in enumerate(task_queue):
            # Check browser health before each task (async CDP round-trip)
            if not await self._is_page_alive():
                remaining = [t[1] for t in task_queue[i:]]
                self.results.extend(self._abort_remaining(task_id, remaining))
                break

            self._notify_start(task_id)
            try:
                if task_type == 'reverse_asin':
                    r = await self._collect_reverse_asin(param)
                elif task_type == 'traffic_comparison':
                    r = await self._collect_traffic_comparison()
                elif task_type == 'keyword_research':
                    r = await self._collect_keyword_research()
                elif task_type == 'keyword_mining':
                    r = await self._collect_keyword_mining(param)
                elif task_type == 'competitor_research':
                    r = await self._collect_competitor()
                elif task_type == 'ads_insights':
                    r = await self._collect_ads_insights(param)
                else:
                    r = {'task': task_id, 'status': 'SKIPPED', 'error': f'Unknown task type: {task_type}'}
            except Exception as e:
                logger.error(f"{task_id} crashed: {e}")
                r = {'task': task_id, 'status': 'FAILED', 'error': str(e)[:200]}
                # If the error is a browser closure, abort remaining tasks immediately
                if 'closed' in str(e).lower() or 'Target' in str(e):
                    self.results.append(r)
                    self._notify_done(r)
                    remaining = [t[1] for t in task_queue[i + 1:]]
                    if remaining:
                        self.results.extend(self._abort_remaining(task_id, remaining))
                    break

            self.results.append(r)
            self._notify_done(r)
            try:
                await human_delay(self.page, self.delay, self.delay + 3)
            except Exception as e:
                logger.warning(f"Inter-task delay failed (page may be degraded): {e}")
                try:
                    self.page = await self._get_active_page()
                except Exception:
                    pass  # _is_page_alive at top of loop will catch

        logger.info("SellerSprite Collection — Complete")
        return self.results

    async def _get_active_page(self):
        """Get the currently active page, handling AdsPower tab switching."""
        try:
            # Check if current page is still alive
            await self.page.evaluate('() => true')
            return self.page
        except Exception:
            # Page died — find the active one from context
            context = self.page.context
            if context.pages:
                self.page = context.pages[-1]
                logger.info("Switched to new active page")
            else:
                self.page = await context.new_page()
                logger.info("Created new page")
            return self.page

    async def _verify_login(self):
        """Check if user is logged into SellerSprite."""
        self.page = await self._get_active_page()
        if not await safe_goto(self.page, f'{BASE_URL}/v3/keyword-reverse'):
            return False
        self.page = await self._get_active_page()
        await self.page.wait_for_timeout(3000)

        # URL-based check
        url = self.page.url
        if 'login' in url.lower() or 'signin' in url.lower():
            return False

        # Check for GUEST indicator in the header/nav area only
        # (avoid matching generic "Sign In" text elsewhere on the page)
        guest_el = await self.page.query_selector(
            'header :text("GUEST"), header :text("Not Logged"), '
            'nav :text("GUEST"), nav :text("Not Logged")'
        )
        if guest_el:
            text = await guest_el.inner_text()
            logger.warning(f"SellerSprite detected guest/logged-out state: '{text.strip()}'")
            return False

        logger.info("SellerSprite login verified OK")
        return True

    async def _check_duplicate_export(self, prefix):
        """No-op — export log polling removed. Always returns None."""
        return None

    async def _trigger_export_and_download(self, prefix, task_name):
        """Click Export button → handle options panel → capture download → move to inputs/.

        SellerSprite export flow (as of 2026):
        1. Click "Export" button on results page
        2. An options panel/banner appears (checkboxes for variations, images)
        3. Download starts automatically or after clicking export again
        4. File downloads directly to browser (no export log queue)
        5. Some tools (Reverse ASIN) use "Export Keywords" which queues async server export
        """
        self.page = await self._get_active_page()

        # Step 0: Clear any overlays that might block clicks
        await self._dismiss_popups(timeout=1)

        # Step 1: Find the Export button
        # Accept both "Export" (direct download) and "Export Keywords" (async server export)
        # Prefer exact "Export" match; fall back to "Export Keywords" for Reverse ASIN
        export_btn = None
        is_async_export = False  # "Export Keywords" = async, needs export log polling

        for sel in [
            'button.success-border:has-text("Export")',
            'button:has-text("Export")',
            SELECTORS['export_button'],
        ]:
            try:
                candidates = await self.page.query_selector_all(sel)
                for c in candidates:
                    if await c.is_visible():
                        text = (await c.inner_text()).strip()
                        # Prefer exact "Export" match (direct download)
                        if text == 'Export' or text == '导出':
                            export_btn = c
                            is_async_export = False
                            break
                        # Accept "Export Keywords" / "导出关键词" (async export)
                        if 'export' in text.lower() or '导出' in text:
                            if not export_btn:
                                export_btn = c
                                is_async_export = ('keyword' in text.lower() or '关键词' in text)
                if export_btn and not is_async_export:
                    break  # Found exact "Export", stop searching selectors
            except Exception:
                continue

        if not export_btn:
            await take_debug_screenshot(self.page, f'{task_name}_no_export_btn')
            return {'task': task_name, 'status': 'FAILED', 'error': 'Export button not found'}

        if is_async_export:
            logger.info(f"Found 'Export Keywords' button for {task_name} — will use async export flow")
        else:
            logger.info(f"Found 'Export' button for {task_name} — will try direct download")

        # Step 2: Click Export — this may show options panel or start download directly
        # Use force=True to bypass any overlay (v-modal, yun-message-box) that intercepts clicks
        logger.info(f"Clicking Export button for {task_name}...")
        try:
            async with self.page.expect_download(timeout=15000) as download_info:
                await export_btn.click(force=True)
            # Direct download worked
            download = await download_info.value
            dest_path = os.path.join(self.download_dir, download.suggested_filename)
            await download.save_as(dest_path)
            logger.info(f"Direct download: {download.suggested_filename}")
            final = move_to_inputs(dest_path, 'sellersprite')
            return {'task': task_name, 'status': 'OK', 'file': os.path.basename(final)}

        except Exception:
            # No direct download — options panel appeared or async export queued
            logger.info("No direct download after click...")

        # For async exports ("Export Keywords"), skip Steps 3-5 and go straight to export log polling
        # This avoids wasting 60+ seconds on expect_download timeouts for server-queued exports
        if is_async_export:
            logger.info(f"'{task_name}' uses async export — skipping to export log polling...")
            await self.page.wait_for_timeout(3000)  # Give server time to queue the export
        else:
            # Step 3: Handle options panel — uncheck "Export Top3 Product Images" if present
            await self.page.wait_for_timeout(1000)
            try:
                images_checkbox = await self.page.query_selector(
                    'label:has-text("Top3"), label:has-text("Product Images"), '
                    'input[type="checkbox"]:near(:text("Top3"))'
                )
                if images_checkbox:
                    is_checked = await images_checkbox.is_checked() if hasattr(images_checkbox, 'is_checked') else False
                    if is_checked:
                        await images_checkbox.click()
                        logger.info("Unchecked 'Export Top3 Product Images'")
            except Exception:
                pass

            # Step 4: Look for a confirm/download button in the options panel, or click Export again
            await self.page.wait_for_timeout(1000)

            for sel in [
                'button:has-text("Export Keywords")',
                'button:has-text("导出关键词")',
                'button:has-text("Export"):visible',
                'button:has-text("Download"):visible',
            ]:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        logger.info(f"Clicking '{sel}' to trigger download...")
                        try:
                            async with self.page.expect_download(timeout=30000) as download_info:
                                await btn.click(force=True)
                            download = await download_info.value
                            dest_path = os.path.join(self.download_dir, download.suggested_filename)
                            await download.save_as(dest_path)
                            logger.info(f"Downloaded: {download.suggested_filename}")
                            final = move_to_inputs(dest_path, 'sellersprite')
                            return {'task': task_name, 'status': 'OK', 'file': os.path.basename(final)}
                        except Exception as e:
                            logger.warning(f"Click '{sel}' did not trigger download: {e}")
                            continue
                except Exception:
                    continue

            # Step 5: Last resort — try OK/Confirm buttons
            for sel in [
                'button:has-text("OK")', 'button:has-text("确定")',
                'button:has-text("Confirm")', '.el-button--primary:visible',
            ]:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        try:
                            async with self.page.expect_download(timeout=15000) as download_info:
                                await btn.click(force=True)
                            download = await download_info.value
                            dest_path = os.path.join(self.download_dir, download.suggested_filename)
                            await download.save_as(dest_path)
                            logger.info(f"Downloaded via confirm: {download.suggested_filename}")
                            final = move_to_inputs(dest_path, 'sellersprite')
                            return {'task': task_name, 'status': 'OK', 'file': os.path.basename(final)}
                        except Exception:
                            continue
                except Exception:
                    continue

        # Step 6: Export log polling (primary path for async exports, fallback for direct)
        logger.info(f"Trying export log polling for '{prefix}'...")
        try:
            poll_timeout = self.collection.get('export_poll_timeout_sec', 300)
            poll_interval = self.collection.get('export_poll_interval_sec', 10)
            new_export = await poll_export_log_for_new(
                self.page,
                existing_count=0,  # Check for any recent export matching prefix
                prefix=prefix,
                timeout=poll_timeout,
                poll_interval=poll_interval,
                base_url=BASE_URL,
            )
            if new_export:
                filepath = await download_from_export_log(self.page, new_export, self.download_dir)
                final = move_to_inputs(filepath, 'sellersprite')
                logger.info(f"Downloaded from export log: {os.path.basename(final)}")
                return {'task': task_name, 'status': 'OK', 'file': os.path.basename(final)}
        except Exception as e:
            logger.warning(f"Export log polling failed: {e}")

        await take_debug_screenshot(self.page, f'{task_name}_export_failed')
        return {'task': task_name, 'status': 'FAILED', 'error': 'Export failed — no download triggered after all attempts'}

    async def _find_and_click(self, selector_str, force=False):
        """Try multiple selectors (comma-separated) and click the first match."""
        selectors = [s.strip() for s in selector_str.split(',')]
        for selector in selectors:
            try:
                el = await self.page.wait_for_selector(selector, timeout=5000, state='visible')
                if el:
                    await el.click(force=force)
                    return True
            except Exception:
                continue
        return False

    async def _fill_input(self, selector_str, value):
        """Find input matching selectors and fill with value."""
        selectors = [s.strip() for s in selector_str.split(',')]
        for selector in selectors:
            try:
                el = await self.page.wait_for_selector(selector, timeout=5000, state='visible')
                if el:
                    await el.click()
                    await el.fill('')
                    await el.fill(value)
                    return True
            except Exception:
                continue
        return False

    async def _dismiss_popups(self, timeout=5):
        """Detect and dismiss common SellerSprite popups/modals that block results.

        Handles:
        - ASIN variation selection modal ("Select ASINs to Compare")
        - Generic close buttons on overlays
        - Tutorial/promo popups
        """
        # Wait for popup to potentially appear
        await self.page.wait_for_timeout(timeout * 1000)

        # 1. ASIN variation selection popup (Traffic Comparison, Reverse ASIN)
        # Scan ALL visible buttons for known popup text patterns
        try:
            buttons = await self.page.query_selector_all('button')
            for btn in buttons:
                try:
                    if not await btn.is_visible():
                        continue
                    text = (await btn.inner_text()).strip().lower()
                    # Match the exact ASIN / variations popup buttons
                    if 'exact asin' in text or '精确asin' in text:
                        await btn.click()
                        logger.info(f"Dismissed ASIN popup: clicked 'exact ASIN' button")
                        await self.page.wait_for_timeout(3000)
                        return True
                    if 'sells well variations' in text or '热卖变体' in text:
                        await btn.click()
                        logger.info(f"Dismissed ASIN popup: clicked 'variations' button")
                        await self.page.wait_for_timeout(3000)
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        # 2. SellerSprite "yun-message-box" overlay (usage/quota/promo popups)
        for sel in [
            '.yun-message-box .el-dialog__headerbtn',
            '.yun-box .el-dialog__headerbtn',
            '.yun-message-box button.close',
            '.yun-message-box [aria-label="Close"]',
        ]:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.info(f"Closed yun-message-box via: {sel}")
                    await self.page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue

        # 3. Try removing the overlay via JS if it blocks clicks
        try:
            removed = await self.page.evaluate('''() => {
                const overlays = document.querySelectorAll(
                    '.yun-message-box, .el-dialog__wrapper.yun-box, .v-modal, ' +
                    '.el-dialog__wrapper[style*="display: none"] ~ .v-modal'
                );
                let removed = 0;
                overlays.forEach(el => {
                    el.style.display = 'none';
                    el.style.pointerEvents = 'none';
                    removed++;
                });
                // Also remove any stale v-modal backdrops
                document.querySelectorAll('.v-modal').forEach(el => {
                    el.style.display = 'none';
                    removed++;
                });
                return removed;
            }''')
            if removed > 0:
                logger.info(f"Force-removed {removed} overlay(s) via JS")
                await self.page.wait_for_timeout(500)
                return True
        except Exception:
            pass

        # 4. Generic close/dismiss buttons on any modal overlay
        for sel in [
            '.el-dialog__headerbtn',
            '.el-message-box__headerbtn',
            'button.close',
            '[aria-label="Close"]',
        ]:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.info(f"Closed modal via: {sel}")
                    await self.page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue

        return False

    async def _wait_for_results(self, timeout=30):
        """Wait for results — checks table rows, export button, or keyword distribution."""
        # Try multiple indicators that the page has loaded results
        indicators = [
            SELECTORS['results_table'],
            'button:has-text("Export")',
            ':text("Keyword Distribution")',
            ':text("关键词分布")',
            '.el-table tr',
            'table tr:nth-child(2)',
        ]
        for sel in indicators:
            try:
                await self.page.wait_for_selector(sel, timeout=timeout * 1000, state='visible')
                await self.page.wait_for_timeout(2000)
                logger.info(f"Results detected via: {sel[:40]}")
                return True
            except Exception:
                continue
        logger.warning("Results not detected within timeout")
        return False

    # ── Task Methods ──────────────────────────────────────────────────

    async def _collect_reverse_asin(self, asin):
        """Reverse ASIN: navigate, search with All Variations, export."""
        task_name = f'reverse_asin_{asin}'
        logger.info(f"Task: Reverse ASIN — {asin}")
        self.page = await self._get_active_page()

        # Navigate to Reverse ASIN tool
        if not await safe_goto(self.page, f'{BASE_URL}/v3/keyword-reverse'):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

        await self.page.wait_for_timeout(2000)
        await ensure_marketplace_us(self.page)

        # Select "Reverse Multiple ASINs" mode
        # This is critical — single-ASIN mode returns 0 results for B0CSFTRMDF
        multi_tab = await self.page.query_selector(
            '[class*="tab"]:has-text("Reverse Multiple"), '
            '[class*="tab"]:has-text("批量反查"), '
            'a:has-text("Reverse Multiple"), '
            '.ant-tabs-tab:nth-child(2), '
            '[role="tab"]:nth-child(2)'
        )
        if multi_tab:
            try:
                await multi_tab.click(timeout=5000)
                await self.page.wait_for_timeout(1000)
                logger.info("Switched to Reverse Multiple ASINs mode")
            except Exception as e:
                logger.warning(f"Could not click multi-ASIN tab (may not be needed): {e}")
        else:
            logger.info("Multi-ASIN tab not found — using single ASIN mode")

        # Enter ASIN in search input
        input_el = await self.page.query_selector(
            'input[placeholder*="ASIN"], input[placeholder*="product"], textarea'
        )
        if input_el:
            await input_el.fill(asin)
            logger.info(f"Entered ASIN: {asin}")
        else:
            await self._fill_input(SELECTORS['search_input'], asin)

        # Enable "All Variations" toggle — use force click to bypass overlays
        variations_selectors = [
            'label:has-text("All Variations")',
            'label:has-text("所有变体")',
            'span:has-text("All Variations")',
            '.ant-checkbox-wrapper:has-text("Variation")',
            'input[type="checkbox"]',
        ]
        for sel in variations_selectors:
            checkbox = await self.page.query_selector(sel)
            if checkbox:
                try:
                    await checkbox.click(force=True, timeout=3000)
                    logger.info("Enabled All Variations")
                except Exception as e:
                    logger.warning(f"Could not click variations checkbox: {e}")
                break

        await human_delay(self.page, 1, 2)

        # Click Search — use force click to bypass any overlays
        if not await self._find_and_click(SELECTORS['search_button'], force=True):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'Search button not found'}

        # Dismiss any popups (ASIN variation selector, tutorials, etc.)
        await self._dismiss_popups()

        # Wait for results
        if not await self._wait_for_results(timeout=60):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'No results loaded'}

        # Export and download
        return await self._trigger_export_and_download(f'ExpandKeywords', task_name)

    async def _collect_traffic_comparison(self):
        """Traffic Comparison: all 5 ASINs."""
        task_name = 'traffic_comparison'
        asins = self.collection.get('comparison_asins', [])
        if not asins:
            return {'task': task_name, 'status': 'SKIPPED', 'error': 'No ASINs configured'}
        if len(asins) < 2:
            return {'task': task_name, 'status': 'SKIPPED', 'error': f'Need 2+ ASINs for comparison, got {len(asins)}'}

        logger.info(f"Task: Traffic Comparison — {len(asins)} ASINs")
        self.page = await self._get_active_page()

        if not await safe_goto(self.page, f'{BASE_URL}/v3/keyword-comparison'):
            return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

        await self.page.wait_for_timeout(2000)
        await ensure_marketplace_us(self.page)

        # Enter ASINs — SellerSprite Traffic Comparison accepts space-separated ASINs in one input
        asin_str = ' '.join(asins)
        filled = False
        for sel in [
            'input[placeholder*="ASIN" i]',
            'textarea[placeholder*="ASIN" i]',
            'textarea',
            SELECTORS['comparison_input'],
            SELECTORS['search_input'],
        ]:
            try:
                el = await self.page.wait_for_selector(sel, timeout=5000, state='visible')
                if el:
                    await el.click()
                    await el.fill(asin_str)
                    filled = True
                    logger.info(f"Entered {len(asins)} ASINs (space-separated)")
                    break
            except Exception:
                continue

        if not filled:
            return {'task': task_name, 'status': 'FAILED', 'error': 'Could not find ASIN input'}

        await human_delay(self.page, 1, 2)

        if not await self._find_and_click(SELECTORS['search_button']):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'Search button not found'}

        # Traffic Comparison has a special popup: "Select ASINs to Compare"
        # This appears when ASINs have variations — must click a button to proceed
        # Give the popup more time to appear (it can take 3-5 seconds)
        await self._dismiss_popups(timeout=8)

        if not await self._wait_for_results(timeout=60):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'No results loaded'}

        return await self._trigger_export_and_download('CompareKeywords', task_name)

    async def _collect_keyword_research(self):
        """Keyword Research: search by keyword with retry, login check, and v3 fallback."""
        task_name = 'keyword_research'
        keyword = self.collection.get('research_keyword', '')
        if not keyword:
            # Fallback to first seed keyword from collection config
            seeds = self.collection.get('mining_seeds', [])
            keyword = next((s for s in seeds if s.strip()), self.collection.get('asin', 'product'))

        logger.info(f"Task: Keyword Research — '{keyword}'")
        self.page = await self._get_active_page()

        # Try v2 first, then v3 as fallback
        endpoints = [
            f'{BASE_URL}/v2/keyword-research',
            f'{BASE_URL}/v3/keyword-research',
        ]

        max_retries = 2
        for endpoint in endpoints:
            for attempt in range(1, max_retries + 1):
                logger.info(f"Keyword Research: attempt {attempt} on {endpoint}")

                if not await safe_goto(self.page, endpoint):
                    continue

                await self.page.wait_for_timeout(2000)

                # Check if redirected to login
                if await detect_login_redirect(self.page, 'sellersprite.com'):
                    logger.error("Keyword Research: login session expired — aborting")
                    await take_debug_screenshot(self.page, task_name)
                    return {'task': task_name, 'status': 'FAILED', 'error': 'Login session expired'}

                # Check for "System error" or "Not Logged" text on page
                try:
                    body_text = await self.page.inner_text('body')
                    if 'system error' in body_text.lower() or 'not logged' in body_text.lower():
                        logger.warning(f"Keyword Research: server error on attempt {attempt}, retrying after delay...")
                        await self.page.wait_for_timeout(5000)
                        continue
                except Exception:
                    pass

                await ensure_marketplace_us(self.page)
                await self._fill_input(SELECTORS['search_input'], keyword)
                await human_delay(self.page, 1, 2)

                if not await self._find_and_click(SELECTORS['search_button']):
                    await take_debug_screenshot(self.page, task_name)
                    continue

                await self._dismiss_popups()

                if not await self._wait_for_results(timeout=60):
                    # Check again for server error after search
                    try:
                        body_text = await self.page.inner_text('body')
                        if 'system error' in body_text.lower():
                            logger.warning(f"Keyword Research: system error after search, attempt {attempt}")
                            await self.page.wait_for_timeout(5000)
                            continue
                    except Exception:
                        pass
                    await take_debug_screenshot(self.page, task_name)
                    continue

                # Success — export
                return await self._trigger_export_and_download('KeywordResearch', task_name)

            logger.warning(f"Keyword Research: exhausted {max_retries} retries on {endpoint}")

        await take_debug_screenshot(self.page, task_name)
        return {'task': task_name, 'status': 'FAILED', 'error': 'All endpoints/retries exhausted'}

    async def _collect_keyword_mining(self, seed):
        """Keyword Mining: search for a seed keyword, export results."""
        task_name = f'keyword_mining_{seed.replace(" ", "_")}'
        logger.info(f"Task: Keyword Mining — '{seed}'")
        self.page = await self._get_active_page()

        if not await safe_goto(self.page, f'{BASE_URL}/v3/keyword-miner'):
            return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

        await self.page.wait_for_timeout(2000)
        await ensure_marketplace_us(self.page)

        await self._fill_input(SELECTORS['search_input'], seed)
        await human_delay(self.page, 1, 2)

        if not await self._find_and_click(SELECTORS['search_button']):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'Search button not found'}

        # Dismiss any popups (ASIN variation selector, tutorials, etc.)
        await self._dismiss_popups()

        if not await self._wait_for_results(timeout=60):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'No results loaded'}

        return await self._trigger_export_and_download('KeywordMining', task_name)

    async def _collect_competitor(self):
        """Competitor Research: search by keyword."""
        task_name = 'competitor_research'
        keyword = self.collection.get('competitor_keyword', '')
        if not keyword:
            seeds = self.collection.get('mining_seeds', [])
            keyword = next((s for s in seeds if s.strip()), self.collection.get('asin', 'product'))

        logger.info(f"Task: Competitor Research — '{keyword}'")
        self.page = await self._get_active_page()

        if not await safe_goto(self.page, f'{BASE_URL}/v3/competitor-lookup'):
            return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

        await self.page.wait_for_timeout(2000)
        await ensure_marketplace_us(self.page)

        await self._fill_input(SELECTORS['competitor_input'], keyword)
        await human_delay(self.page, 1, 2)

        # Attempt 1: Press Enter to trigger search
        try:
            for sel in [s.strip() for s in SELECTORS['competitor_input'].split(',')]:
                try:
                    el = await self.page.wait_for_selector(sel, timeout=3000, state='visible')
                    if el:
                        await el.press('Enter')
                        logger.info("Competitor Research: pressed Enter to search")
                        break
                except Exception:
                    continue
        except Exception:
            pass

        await self.page.wait_for_timeout(5000)

        # Check if Enter triggered results (look for loading spinner or table rows)
        enter_worked = False
        for check_sel in [SELECTORS['results_table'], '.el-loading-spinner', '.ant-spin']:
            try:
                el = await self.page.query_selector(check_sel)
                if el and await el.is_visible():
                    enter_worked = True
                    break
            except Exception:
                continue

        if not enter_worked:
            # Attempt 2: Click search button scoped to content area (not header)
            logger.info("Enter did not trigger search, trying scoped button click...")
            clicked = await self._find_and_click(
                'main button:has-text("Search"), .el-form button:has-text("Search"), '
                'button.el-button--primary:has-text("Search")'
            )
            if not clicked:
                # Attempt 3: JS — find button nearest the search input
                try:
                    await self.page.evaluate('''() => {
                        const inputs = document.querySelectorAll('input[placeholder*="keyword" i]');
                        for (const input of inputs) {
                            const container = input.closest('form') || input.closest('[class*="search"]') || input.parentElement.parentElement;
                            if (container) {
                                const btn = container.querySelector('button');
                                if (btn) { btn.click(); return true; }
                            }
                        }
                        return false;
                    }''')
                    logger.info("Competitor Research: clicked via JS fallback")
                except Exception:
                    if not await self._find_and_click(SELECTORS['search_button']):
                        await take_debug_screenshot(self.page, task_name)
                        return {'task': task_name, 'status': 'FAILED', 'error': 'Search not triggered'}

        # Dismiss any popups (ASIN variation selector, tutorials, etc.)
        await self._dismiss_popups()

        if not await self._wait_for_results(timeout=60):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'No results loaded'}

        return await self._trigger_export_and_download('Competitor', task_name)

    async def _collect_ads_insights(self, asin):
        """Ads Insights: search by ASIN, export weekly ad data."""
        task_name = f'ads_insights_{asin}'
        logger.info(f"Task: Ads Insights — {asin}")
        self.page = await self._get_active_page()

        if not await safe_goto(self.page, f'{BASE_URL}/v3/ads-insights'):
            return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

        await self.page.wait_for_timeout(2000)
        await ensure_marketplace_us(self.page)

        await self._fill_input(SELECTORS['search_input'], asin)
        await human_delay(self.page, 1, 2)

        if not await self._find_and_click(SELECTORS['search_button']):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'Search button not found'}

        # Dismiss any popups (ASIN variation selector, tutorials, etc.)
        await self._dismiss_popups()

        if not await self._wait_for_results(timeout=60):
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': 'No results loaded'}

        return await self._trigger_export_and_download('AdsInsights', task_name)
