"""Seller Central Playwright collector — downloads 4 CSV reports."""

import os
import logging
from datetime import datetime, timedelta

from .utils import (
    PROJECT_ROOT, INPUTS_SC,
    move_to_inputs, safe_goto, human_delay,
    take_debug_screenshot, detect_login_redirect,
    wait_for_download_via_event,
)

logger = logging.getLogger('collector.seller_central')

SC_BASE = 'https://sellercentral.amazon.com'


class SellerCentralCollector:
    """Automates Seller Central CSV report downloads via Playwright."""

    def __init__(self, config, page, download_dir, on_task_start=None, on_task_done=None):
        self.config = config
        self.page = page
        self.download_dir = download_dir
        self.collection = config.get('collection', {})
        self.sc_config = self.collection.get('seller_central', {})
        self.date_range_days = self.sc_config.get('date_range_days', 60)
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
        """Check if the browser page is still open via CDP round-trip."""
        try:
            if self.page.is_closed():
                return False
            await self.page.evaluate('1')
            return True
        except Exception:
            return False

    def _abort_remaining(self, remaining_ids):
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
        """Run all Seller Central collection tasks."""
        logger.info("=" * 50)
        logger.info("Seller Central Collection — Starting")

        if not await self._verify_login():
            logger.error("Not logged into Seller Central. Please log in via Chrome first.")
            r = {'task': 'sc_login_check', 'status': 'FAILED', 'error': 'Not logged in'}
            self._notify_done(r)
            return [r]

        # Build task queue for clean iteration + early abort
        task_queue = [
            ('business_report', self._collect_business_report),
            ('search_term_report', self._collect_search_term_report),
            ('campaign_report', self._collect_campaign_report),
            ('fba_fee_preview', self._collect_fba_fee_preview),
        ]

        for i, (task_id, task_fn) in enumerate(task_queue):
            # Check browser health before each task
            if not await self._is_page_alive():
                remaining = [t[0] for t in task_queue[i:]]
                self.results.extend(self._abort_remaining(remaining))
                break

            self._notify_start(task_id)
            try:
                r = await task_fn()
            except Exception as e:
                logger.error(f"{task_id} crashed: {e}")
                r = {'task': task_id, 'status': 'FAILED', 'error': str(e)[:200]}
                # If browser closed, abort remaining immediately
                if 'closed' in str(e).lower() or 'Target' in str(e):
                    self.results.append(r)
                    self._notify_done(r)
                    remaining = [t[0] for t in task_queue[i + 1:]]
                    if remaining:
                        self.results.extend(self._abort_remaining(remaining))
                    break

            self.results.append(r)
            self._notify_done(r)
            try:
                await human_delay(self.page, self.delay, self.delay + 3)
            except Exception:
                pass

        logger.info("Seller Central Collection — Complete")
        return self.results

    async def _verify_login(self):
        """Check if user is logged into Seller Central."""
        if not await safe_goto(self.page, SC_BASE, timeout=30000):
            return False
        await self.page.wait_for_timeout(3000)

        url = self.page.url.lower()
        if 'signin' in url or 'ap/signin' in url:
            return False

        if await detect_login_redirect(self.page, 'sellercentral.amazon.com'):
            return False

        return True

    def _get_date_range(self):
        """Return (start_date, end_date) strings for the configured date range."""
        end = datetime.now()
        start = end - timedelta(days=self.date_range_days)
        return start.strftime('%m/%d/%Y'), end.strftime('%m/%d/%Y')

    async def _collect_business_report(self):
        """Download Business Report (By ASIN, Child Item, 60 days, CSV)."""
        task_name = 'business_report'
        logger.info(f"Task: Business Report — {self.date_range_days} days")

        try:
            # Navigate to Business Reports
            url = f'{SC_BASE}/business-reports/ref=xx_sitemetric_dnav_xx#/report?id=102%3ADetailSalesTrafficByChildItem&chartCols=0&columns=%2F0%2F1%2F2%2F3%2F4%2F5%2F6%2F7%2F8%2F9%2F10%2F11%2F12%2F13'
            if not await safe_goto(self.page, url, timeout=30000):
                return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

            await self.page.wait_for_timeout(5000)

            # Check for login redirect
            if await detect_login_redirect(self.page, 'sellercentral.amazon.com'):
                return {'task': task_name, 'status': 'FAILED', 'error': 'Session expired — please re-login'}

            # Set date range
            await self._set_date_range_business_report()

            await self.page.wait_for_timeout(3000)

            # Click CSV download button
            filepath = await self._click_download_csv(task_name)
            if not filepath:
                return {'task': task_name, 'status': 'FAILED', 'error': 'Download button not found'}

            # Generate filename matching expected pattern
            start_str, end_str = self._get_date_range()
            date_tag = datetime.now().strftime('%m-%d-%Y')
            dest = move_to_inputs(filepath, 'seller-central')

            # Rename to match expected pattern if needed
            basename = os.path.basename(dest)
            if not basename.startswith('BusinessReport'):
                new_name = f'BusinessReport-{date_tag}.csv'
                new_path = os.path.join(os.path.dirname(dest), new_name)
                os.rename(dest, new_path)
                dest = new_path
                basename = new_name

            return {'task': task_name, 'status': 'OK', 'file': basename}

        except Exception as e:
            logger.error(f"Business Report failed: {e}")
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': str(e)}

    async def _collect_search_term_report(self):
        """Download SP Search Term Report (60 days, CSV)."""
        task_name = 'search_term_report'
        logger.info(f"Task: SP Search Term Report — {self.date_range_days} days")

        try:
            # Navigate to Advertising Reports
            url = f'{SC_BASE}/advertising/reports'
            if not await safe_goto(self.page, url, timeout=30000):
                return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

            await self.page.wait_for_timeout(5000)

            if await detect_login_redirect(self.page, 'sellercentral.amazon.com'):
                return {'task': task_name, 'status': 'FAILED', 'error': 'Session expired'}

            # Create report: SP > Search Term > 60 days
            filepath = await self._create_ad_report('Search term', task_name)
            if not filepath:
                return {'task': task_name, 'status': 'FAILED', 'error': 'Report creation failed'}

            dest = move_to_inputs(filepath, 'seller-central')

            basename = os.path.basename(dest)
            if not basename.startswith('SpSearchTerm'):
                date_tag = datetime.now().strftime('%m-%d-%Y')
                new_name = f'SpSearchTermReport-{date_tag}.csv'
                new_path = os.path.join(os.path.dirname(dest), new_name)
                os.rename(dest, new_path)
                dest = new_path
                basename = new_name

            return {'task': task_name, 'status': 'OK', 'file': basename}

        except Exception as e:
            logger.error(f"Search Term Report failed: {e}")
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': str(e)}

    async def _collect_campaign_report(self):
        """Download SP Campaign Report (60 days, CSV)."""
        task_name = 'campaign_report'
        logger.info(f"Task: SP Campaign Report — {self.date_range_days} days")

        try:
            url = f'{SC_BASE}/advertising/reports'
            if not await safe_goto(self.page, url, timeout=30000):
                return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

            await self.page.wait_for_timeout(5000)

            if await detect_login_redirect(self.page, 'sellercentral.amazon.com'):
                return {'task': task_name, 'status': 'FAILED', 'error': 'Session expired'}

            filepath = await self._create_ad_report('Campaign', task_name)
            if not filepath:
                return {'task': task_name, 'status': 'FAILED', 'error': 'Report creation failed'}

            dest = move_to_inputs(filepath, 'seller-central')

            basename = os.path.basename(dest)
            if not basename.startswith('SpCampaign'):
                date_tag = datetime.now().strftime('%m-%d-%Y')
                new_name = f'SpCampaignReport-{date_tag}.csv'
                new_path = os.path.join(os.path.dirname(dest), new_name)
                os.rename(dest, new_path)
                dest = new_path
                basename = new_name

            return {'task': task_name, 'status': 'OK', 'file': basename}

        except Exception as e:
            logger.error(f"Campaign Report failed: {e}")
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': str(e)}

    async def _collect_fba_fee_preview(self):
        """Download FBA Fee Preview CSV."""
        task_name = 'fba_fee_preview'
        logger.info("Task: FBA Fee Preview")

        try:
            # Navigate to Fee Preview
            url = f'{SC_BASE}/reportcentral/FULFILLMENT_FEE_PREVIEW/0'
            if not await safe_goto(self.page, url, timeout=30000):
                # Try alternative path
                url = f'{SC_BASE}/hz/fba/profitabilitycalculator/index'
                if not await safe_goto(self.page, url, timeout=30000):
                    return {'task': task_name, 'status': 'FAILED', 'error': 'Navigation failed'}

            await self.page.wait_for_timeout(5000)

            if await detect_login_redirect(self.page, 'sellercentral.amazon.com'):
                return {'task': task_name, 'status': 'FAILED', 'error': 'Session expired'}

            # Look for Request Download / Download button
            filepath = await self._click_download_csv(task_name, button_texts=[
                'Request Download', 'Request .csv Download', 'Download',
                'Request download', 'CSV', 'Generate report',
            ])

            if not filepath:
                return {'task': task_name, 'status': 'FAILED', 'error': 'Download button not found'}

            dest = move_to_inputs(filepath, 'seller-central')

            basename = os.path.basename(dest)
            if not basename.startswith('FBAFee'):
                date_tag = datetime.now().strftime('%m-%d-%Y')
                new_name = f'FBAFeePreview-{date_tag}.csv'
                new_path = os.path.join(os.path.dirname(dest), new_name)
                os.rename(dest, new_path)
                dest = new_path
                basename = new_name

            return {'task': task_name, 'status': 'OK', 'file': basename}

        except Exception as e:
            logger.error(f"FBA Fee Preview failed: {e}")
            await take_debug_screenshot(self.page, task_name)
            return {'task': task_name, 'status': 'FAILED', 'error': str(e)}

    # ── Helper Methods ────────────────────────────────────────────────

    async def _set_date_range_business_report(self):
        """Set the date range on the Business Report page."""
        start_str, end_str = self._get_date_range()

        # Try clicking date range selector
        date_selectors = [
            '#daily-picker', '.date-range-picker', '[data-test-id="date-picker"]',
            'input[name="startDate"]', '.date-range', '#DatePickerComponent',
        ]

        for sel in date_selectors:
            el = await self.page.query_selector(sel)
            if el:
                await el.click()
                await self.page.wait_for_timeout(1000)
                break

        # Try to find start/end date inputs and fill them
        start_input = await self.page.query_selector(
            'input[name="startDate"], input[placeholder*="Start"], input:first-of-type'
        )
        end_input = await self.page.query_selector(
            'input[name="endDate"], input[placeholder*="End"], input:last-of-type'
        )

        if start_input and end_input:
            await start_input.fill(start_str)
            await end_input.fill(end_str)

            # Click Apply/Update
            apply_btn = await self.page.query_selector(
                'button:has-text("Apply"), button:has-text("Update"), '
                'button:has-text("Go"), input[type="submit"]'
            )
            if apply_btn:
                await apply_btn.click()
                await self.page.wait_for_timeout(3000)

    async def _click_download_csv(self, task_name, button_texts=None):
        """Find and click a CSV download button. Returns downloaded file path."""
        if button_texts is None:
            button_texts = ['CSV', 'Download CSV', 'Export', 'Download']

        # Build selectors from button texts
        for text in button_texts:
            selectors = [
                f'button:has-text("{text}")',
                f'a:has-text("{text}")',
                f'[data-test-id*="download"]',
                f'[id*="download"]',
                f'input[value*="{text}"]',
            ]
            for sel in selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        filepath = await wait_for_download_via_event(
                            self.page,
                            lambda b=btn: b.click(),
                            timeout=60,
                        )
                        return filepath
                except Exception:
                    continue

        # Fallback: look for any download-related link
        fallback_selectors = [
            'a[href*="download"]', 'a[href*="csv"]', 'a[href*="export"]',
            '[class*="download"]', '[class*="export"]',
        ]
        for sel in fallback_selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    filepath = await wait_for_download_via_event(
                        self.page,
                        lambda b=btn: b.click(),
                        timeout=60,
                    )
                    return filepath
            except Exception:
                continue

        await take_debug_screenshot(self.page, f'{task_name}_no_download_btn')
        return None

    async def _create_ad_report(self, report_type, task_name):
        """Create an advertising report (Search Term or Campaign) and download it.

        Args:
            report_type: 'Search term' or 'Campaign'
            task_name: for logging/screenshots

        Returns:
            Downloaded file path, or None on failure.
        """
        # Click "Create report" button
        create_btn = await self.page.query_selector(
            'button:has-text("Create report"), '
            'a:has-text("Create report"), '
            '[data-test-id="create-report"]'
        )
        if not create_btn:
            logger.warning("Create report button not found, looking for alternative")
            create_btn = await self.page.query_selector(
                'button.amzn-btn-primary, button[class*="create"]'
            )

        if create_btn:
            await create_btn.click()
            await self.page.wait_for_timeout(3000)

        # Select report type: Sponsored Products
        sp_selectors = [
            'label:has-text("Sponsored Products")',
            'input[value="SP"] + label',
            '[data-test-id="SP"]',
            'option:has-text("Sponsored Products")',
        ]
        for sel in sp_selectors:
            el = await self.page.query_selector(sel)
            if el:
                await el.click()
                await self.page.wait_for_timeout(1000)
                break

        # Select report subtype (Search term or Campaign)
        type_selectors = [
            f'label:has-text("{report_type}")',
            f'option:has-text("{report_type}")',
            f'[data-test-id*="{report_type.lower().replace(" ", "-")}"]',
        ]
        for sel in type_selectors:
            el = await self.page.query_selector(sel)
            if el:
                await el.click()
                await self.page.wait_for_timeout(1000)
                break

        # Set time period
        period_selectors = [
            'select[name*="period"]', 'select[name*="time"]',
            '[data-test-id="time-unit"]',
        ]
        for sel in period_selectors:
            el = await self.page.query_selector(sel)
            if el:
                try:
                    await el.select_option(label='Last 60 days')
                except Exception:
                    try:
                        await el.select_option(label='Last 65 days')
                    except Exception:
                        pass
                break

        # Click "Run report" / "Create" button
        run_btn = await self.page.query_selector(
            'button:has-text("Run report"), button:has-text("Create"), '
            'button[type="submit"], button.amzn-btn-primary'
        )
        if run_btn:
            await run_btn.click()
            await self.page.wait_for_timeout(5000)

        # Wait for report to generate and download link to appear
        # Advertising reports may take a moment to generate
        for attempt in range(12):  # Wait up to 60s
            download_btn = await self.page.query_selector(
                'a:has-text("Download"), button:has-text("Download"), '
                '[data-test-id="download-button"]'
            )
            if download_btn and await download_btn.is_visible():
                try:
                    filepath = await wait_for_download_via_event(
                        self.page,
                        lambda b=download_btn: b.click(),
                        timeout=60,
                    )
                    return filepath
                except Exception as e:
                    logger.warning(f"Download click failed: {e}")

            await self.page.wait_for_timeout(5000)
            # Refresh the page to check for completion
            if attempt > 0 and attempt % 3 == 0:
                await self.page.reload()
                await self.page.wait_for_timeout(3000)

        await take_debug_screenshot(self.page, f'{task_name}_report_timeout')
        logger.error(f"Report generation timed out for {report_type}")
        return None
