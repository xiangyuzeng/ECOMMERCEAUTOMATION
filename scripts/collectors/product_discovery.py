"""Product Discovery — extract product info, competitors, and seed keywords from an Amazon URL."""

import os
import re
import json
import logging
from pathlib import Path

logger = logging.getLogger('collector.discovery')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def extract_asin_from_url(url):
    """Extract ASIN from various Amazon URL formats.

    Handles:
    - https://www.amazon.com/dp/B0BTRTZNS8
    - https://www.amazon.com/gp/product/B0BTRTZNS8
    - https://www.amazon.com/Some-Title/dp/B0BTRTZNS8/ref=xxx
    - https://amazon.com/dp/B0BTRTZNS8?th=1
    """
    patterns = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/gp/aw/d/([A-Z0-9]{10})',
        r'amazon\.\w+.*?/([A-Z0-9]{10})(?:[/?]|$)',
    ]
    for pat in patterns:
        match = re.search(pat, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def generate_seed_keywords(title, brand=''):
    """Auto-generate 2-3 seed keywords from product title.

    Strategy:
    1. Remove brand name from title
    2. Remove noise words (numbers, sizes, materials pct)
    3. Extract the most meaningful 2-3 word phrases

    Example:
    "COLD POSH Silk Blouses for Women Long Sleeve 100% Pure Silk Button Down Shirt"
    → ["silk blouse", "silk button down shirt", "silk shirt women"]
    """
    # Clean title
    clean = title
    if brand:
        clean = re.sub(re.escape(brand), '', clean, flags=re.IGNORECASE).strip()

    # Remove noise
    clean = re.sub(r'\d+%', '', clean)  # Remove percentages
    clean = re.sub(r'\b(with|and|for|the|a|an|in|on|of|by)\b', ' ', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[,\-\|/()]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    words = clean.lower().split()

    # Build keyword candidates
    seeds = []

    # Strategy 1: First meaningful 2-word phrase (usually the core product)
    # Skip size/material words to find the product type
    skip_words = {'pure', 'real', 'genuine', 'natural', 'premium', 'luxury',
                  'soft', 'comfortable', 'elegant', 'casual', 'classic',
                  'new', 'hot', 'best', 'top', 'long', 'short', 'sleeve',
                  'size', 'plus', 'small', 'medium', 'large', 'xl', 'xxl'}

    meaningful = [w for w in words if w not in skip_words and len(w) > 2]

    if len(meaningful) >= 2:
        # Core product: first noun-like pair
        seeds.append(f"{meaningful[0]} {meaningful[1]}")

    # Strategy 2: Product + "for women/men" if present
    gender = None
    for g in ['women', 'men', 'girls', 'boys', 'kids']:
        if g in words:
            gender = g
            break

    if gender and seeds:
        gender_kw = f"{seeds[0]} {gender}"
        if gender_kw not in seeds:
            seeds.append(gender_kw)

    # Strategy 3: Key material + product type
    materials = ['silk', 'cotton', 'linen', 'wool', 'cashmere', 'satin',
                 'mulberry', 'chiffon', 'velvet', 'leather', 'denim']
    product_types = ['blouse', 'shirt', 'top', 'dress', 'pants', 'skirt',
                     'jacket', 'coat', 'sweater', 'pajama', 'robe', 'scarf',
                     'pillowcase', 'bedding', 'mask', 'bonnet']

    found_material = None
    found_type = None
    for w in words:
        if w in materials and not found_material:
            found_material = w
        if w in product_types and not found_type:
            found_type = w

    if found_material and found_type:
        mat_type = f"{found_material} {found_type}"
        if mat_type not in seeds:
            seeds.append(mat_type)

    # Ensure we have at least 2 seeds
    if len(seeds) < 2 and meaningful:
        # Add a longer phrase
        long_phrase = ' '.join(meaningful[:4])
        if long_phrase not in seeds:
            seeds.append(long_phrase)

    # Limit to 3 seeds, filter out empty strings
    seeds = [s for s in seeds[:3] if s.strip()]
    if not seeds:
        # Last resort: use whatever was in the cleaned title
        fallback = clean.lower().strip()[:50]
        if fallback:
            seeds = [fallback]
    return seeds


async def scrape_amazon_product(page, asin):
    """Navigate to Amazon product page and extract key info.

    Returns dict with: title, price, brand, rating, review_count,
                       category, parent_asin, child_asins, image_url
    """
    from .utils import safe_goto

    url = f'https://www.amazon.com/dp/{asin}'
    logger.info(f"Scraping Amazon product: {url}")

    if not await safe_goto(page, url):
        logger.error(f"Failed to navigate to {url}")
        return None

    await page.wait_for_timeout(3000)

    # Check for CAPTCHA or bot detection
    if 'captcha' in page.url.lower() or 'validateCaptcha' in page.url:
        logger.error("Amazon CAPTCHA detected — cannot scrape")
        return None

    # Check for Amazon interstitial ("Click the button below to continue shopping")
    for attempt in range(3):
        try:
            body_text = await page.evaluate('document.body ? document.body.innerText : ""')
            if 'continue shopping' in body_text.lower() or 'click the button below' in body_text.lower():
                logger.warning(f"Amazon interstitial detected (attempt {attempt+1}/3) — clicking 'Continue shopping'...")
                # Try clicking the continue button
                for btn_sel in [
                    'input[type="submit"]',
                    'a:has-text("Continue shopping")',
                    'button:has-text("Continue")',
                    'span.a-button-text:has-text("Continue")',
                    'input.a-button-input',
                ]:
                    try:
                        btn = await page.query_selector(btn_sel)
                        if btn and await btn.is_visible():
                            await btn.click()
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        continue
                # After clicking, reload the product page
                if not await safe_goto(page, url):
                    logger.error("Failed to navigate after interstitial bypass")
                    return None
                await page.wait_for_timeout(3000)
            else:
                break  # No interstitial — proceed normally
        except Exception as e:
            logger.warning(f"Interstitial check error: {e}")
            break

    # Re-check for CAPTCHA after interstitial handling
    page_text = ''
    try:
        page_text = await page.evaluate('document.body ? document.body.innerText : ""')
    except Exception:
        pass
    if 'continue shopping' in page_text.lower() and '#productTitle' not in page_text:
        logger.error("Amazon interstitial persists after 3 attempts — cannot scrape")
        # Still try to proceed — JS extraction might work with partial data
        pass

    # Wait for product title to appear — try multiple selectors with extended timeout
    # Amazon pages are heavily JS-rendered and may take time in headless/AdsPower browsers
    title_found = False
    for selector in [
        '#productTitle',
        '#title span',
        'h1#title span',
        'h1 span.a-text-normal',
        '#titleSection',
        'h1',
    ]:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            title_found = True
            break
        except Exception:
            continue

    if not title_found:
        logger.warning("Product title selector not found, waiting extra 5s for page render...")
        await page.wait_for_timeout(5000)
        # Try once more with the broadest selector
        try:
            await page.wait_for_selector('h1, #productTitle', timeout=5000)
        except Exception:
            logger.warning("Still no product title — will attempt JS extraction anyway")

    info = {'asin': asin, 'url': url}

    # Take a debug screenshot for diagnostics
    try:
        from .utils import take_debug_screenshot
        await take_debug_screenshot(page, f'amazon_product_{asin}')
    except Exception:
        pass

    # Try JS-based bulk extraction first (more reliable than individual selectors)
    try:
        js_info = await page.evaluate('''() => {
            const result = {};
            // Title — extensive fallbacks for different Amazon layouts
            const titleEl = document.querySelector('#productTitle') ||
                            document.querySelector('#title span') ||
                            document.querySelector('h1 span.a-text-normal') ||
                            document.querySelector('#titleSection span') ||
                            document.querySelector('[data-csa-c-content-id="title"] span') ||
                            document.querySelector('h1');
            result.title = titleEl ? titleEl.textContent.trim() : '';

            // If title is still empty, try getting any h1 text from the page
            if (!result.title) {
                const h1 = document.querySelector('h1');
                if (h1) result.title = h1.textContent.trim();
            }

            // Price — extensive fallbacks
            const priceSelectors = [
                '.a-price .a-offscreen',
                '#priceblock_ourprice',
                '#priceblock_dealprice',
                '#corePrice_feature_div .a-offscreen',
                '#apex_offerDisplay_desktop .a-offscreen',
                '.a-price-whole',
                '#price_inside_buybox',
                '#newBuyBoxPrice',
                '[data-csa-c-content-id="price"] .a-offscreen',
                '.priceToPay .a-offscreen',
            ];
            let priceText = '';
            for (const sel of priceSelectors) {
                const el = document.querySelector(sel);
                if (el) {
                    priceText = el.textContent.trim();
                    if (priceText && priceText.includes('$')) break;
                }
            }
            result.price_text = priceText;

            // Brand — extensive fallbacks
            const brandEl = document.querySelector('#bylineInfo') ||
                            document.querySelector('a#brand') ||
                            document.querySelector('.po-brand .a-span9 span') ||
                            document.querySelector('[data-csa-c-content-id="brand"] a');
            result.brand_text = brandEl ? brandEl.textContent.trim() : '';

            // Rating
            const ratingEl = document.querySelector('#acrPopover .a-icon-alt') ||
                             document.querySelector('span[data-hook="rating-out-of-text"]') ||
                             document.querySelector('.a-icon-alt');
            result.rating_text = ratingEl ? ratingEl.textContent.trim() : '';

            // Review count
            const reviewEl = document.querySelector('#acrCustomerReviewText') ||
                             document.querySelector('#acrCustomerReviewLink span');
            result.review_text = reviewEl ? reviewEl.textContent.trim() : '';

            // Category breadcrumbs
            const bcs = document.querySelectorAll('#wayfinding-breadcrumbs_container li a, .a-breadcrumb li a');
            result.category = Array.from(bcs).map(el => el.textContent.trim()).filter(Boolean).join(' > ');

            // Image
            const imgEl = document.querySelector('#landingImage') || document.querySelector('#imgBlkFront');
            result.image_url = imgEl ? (imgEl.src || imgEl.getAttribute('data-old-hires') || '') : '';

            // Debug: report what selectors exist on the page
            result._debug = {
                has_productTitle: !!document.querySelector('#productTitle'),
                has_title_span: !!document.querySelector('#title span'),
                has_bylineInfo: !!document.querySelector('#bylineInfo'),
                has_price_a_offscreen: !!document.querySelector('.a-price .a-offscreen'),
                has_h1: !!document.querySelector('h1'),
                page_title: document.title,
            };

            return result;
        }''')
        if js_info:
            # Log debug info about which selectors exist
            debug = js_info.get('_debug', {})
            if debug:
                logger.info(f"Amazon page debug: {debug}")
            info['title'] = js_info.get('title', '')
            if not info['title']:
                logger.warning(f"JS extraction returned empty title. Page title: {debug.get('page_title', '?')}")
            # Price
            price_text = js_info.get('price_text', '')
            if price_text:
                try:
                    info['price'] = float(re.sub(r'[^\d.]', '', price_text))
                except ValueError:
                    info['price'] = None
            # Brand
            brand_text = js_info.get('brand_text', '')
            if brand_text:
                brand_text = re.sub(r'^(Visit the |Brand: )', '', brand_text)
                brand_text = re.sub(r' Store$', '', brand_text)
                info['brand'] = brand_text
            # Rating
            rating_text = js_info.get('rating_text', '')
            if rating_text:
                m = re.search(r'([\d.]+)', rating_text)
                if m:
                    info['rating'] = float(m.group(1))
            # Review count
            review_text = js_info.get('review_text', '')
            if review_text:
                info['review_count'] = int(re.sub(r'[^\d]', '', review_text) or '0')
            # Category & Image
            info['category'] = js_info.get('category', '')
            info['image_url'] = js_info.get('image_url', '')
    except Exception as e:
        logger.warning(f"JS extraction failed: {e}, falling back to individual selectors")

    # Fallback: individual selectors for any missing fields
    if not info.get('title'):
        try:
            title_el = await page.query_selector('#productTitle, #title span')
            if title_el:
                info['title'] = (await title_el.inner_text()).strip()
        except Exception:
            pass

    if not info.get('price'):
        try:
            price_el = await page.query_selector('.a-price .a-offscreen, #priceblock_ourprice')
            if price_el:
                price_text = (await price_el.inner_text()).strip()
                info['price'] = float(re.sub(r'[^\d.]', '', price_text))
        except Exception:
            info['price'] = None

    if not info.get('brand'):
        try:
            brand_el = await page.query_selector('#bylineInfo, a#brand')
            if brand_el:
                brand_text = (await brand_el.inner_text()).strip()
                brand_text = re.sub(r'^(Visit the |Brand: )', '', brand_text)
                brand_text = re.sub(r' Store$', '', brand_text)
                info['brand'] = brand_text
        except Exception:
            info['brand'] = ''

    # Parent ASIN (from page data)
    try:
        parent_asin = await page.evaluate('''() => {
            // Try multiple sources for parent ASIN
            if (window.__PRELOADED_STATE__) {
                const state = window.__PRELOADED_STATE__;
                if (state.parentAsin) return state.parentAsin;
            }
            // Check twister data
            const twisterEl = document.querySelector('#twister_feature_div, #variation_size_name');
            if (twisterEl) {
                const dataAsin = twisterEl.closest('[data-parent-asin]');
                if (dataAsin) return dataAsin.getAttribute('data-parent-asin');
            }
            // Check page source
            const bodyHtml = document.body.innerHTML;
            const match = bodyHtml.match(/"parentAsin":"([A-Z0-9]{10})"/);
            if (match) return match[1];
            return null;
        }''')
        info['parent_asin'] = parent_asin or asin
    except Exception:
        info['parent_asin'] = asin

    # Child ASINs (variations)
    try:
        child_asins = await page.evaluate('''() => {
            const asins = new Set();
            // From variation data
            const variationData = document.querySelectorAll('[data-defaultasin], [data-dp-url]');
            variationData.forEach(el => {
                const dpUrl = el.getAttribute('data-dp-url') || '';
                const match = dpUrl.match(/\\/dp\\/([A-Z0-9]{10})/);
                if (match) asins.add(match[1]);
                const defaultAsin = el.getAttribute('data-defaultasin');
                if (defaultAsin && /^[A-Z0-9]{10}$/.test(defaultAsin)) asins.add(defaultAsin);
            });
            // From page source
            const bodyHtml = document.body.innerHTML;
            const matches = bodyHtml.matchAll(/"dimensionValuesDisplayData"\\s*:\\s*\\{([^}]+)\\}/g);
            for (const m of matches) {
                const asinMatches = m[1].matchAll(/"([A-Z0-9]{10})"/g);
                for (const am of asinMatches) asins.add(am[1]);
            }
            return [...asins];
        }''')
        info['child_asins'] = child_asins if child_asins else [asin]
    except Exception:
        info['child_asins'] = [asin]

    logger.info(f"Scraped product: {info.get('title', 'N/A')[:60]}... "
                f"brand={info.get('brand')}, price=${info.get('price')}, "
                f"children={len(info.get('child_asins', []))}")

    return info


async def discover_competitors_via_sellersprite(page, seed_keyword, my_asin, max_competitors=4):
    """Use SellerSprite Competitor Research to find top competitors.

    Navigates to the competitor tool, searches the seed keyword,
    scrapes the top results (excluding our own product), returns up to max_competitors.

    Returns list of dicts: [{asin, brand, title, price, monthly_sales, rating}, ...]
    """
    from .utils import safe_goto, ensure_marketplace_us

    BASE_URL = 'https://www.sellersprite.com'

    logger.info(f"Discovering competitors via SellerSprite: '{seed_keyword}'")

    if not await safe_goto(page, f'{BASE_URL}/v3/competitor-lookup'):
        logger.error("Failed to navigate to competitor tool")
        return []

    await page.wait_for_timeout(2000)
    await ensure_marketplace_us(page)

    # Fill keyword — use case-insensitive selectors (same as main collector)
    input_selectors = [
        'input[placeholder*="keyword" i]',
        'input[placeholder*="关键词"]',
        'input[placeholder*="phrase" i]',
        'input[type="text"][class*="search"]',
        '.ant-input',
    ]
    input_el = None
    for sel in input_selectors:
        try:
            input_el = await page.query_selector(sel)
            if input_el and await input_el.is_visible():
                break
            input_el = None
        except Exception:
            continue

    if input_el:
        await input_el.fill(seed_keyword)
        logger.info(f"Filled competitor search with: '{seed_keyword}'")
    else:
        logger.error("Could not find competitor search input")
        return []

    await page.wait_for_timeout(1000)

    # 3-layer search trigger (same approach as main collector)
    # Attempt 1: Press Enter on the input
    search_triggered = False
    try:
        await input_el.press('Enter')
        logger.info("Discovery: pressed Enter to search")
        await page.wait_for_timeout(5000)
        # Check if results or loading appeared
        for check_sel in ['table tbody tr', '.ant-table-tbody tr', '.el-loading-spinner', '.ant-spin']:
            try:
                el = await page.query_selector(check_sel)
                if el and await el.is_visible():
                    search_triggered = True
                    break
            except Exception:
                continue
    except Exception:
        pass

    if not search_triggered:
        # Attempt 2: Click search button
        logger.info("Discovery: Enter didn't trigger search, trying button click...")
        search_btn = None
        for sel in [
            'button:has-text("Search")', 'button:has-text("搜索")',
            'button[type="submit"]', 'button.el-button--primary',
        ]:
            try:
                search_btn = await page.wait_for_selector(sel, timeout=5000, state='visible')
                if search_btn:
                    await search_btn.click()
                    search_triggered = True
                    logger.info(f"Discovery: clicked search button via '{sel}'")
                    break
            except Exception:
                continue

    if not search_triggered:
        # Attempt 3: JS fallback — find button near input
        try:
            result = await page.evaluate('''() => {
                const inputs = document.querySelectorAll('input[placeholder*="keyword" i], input[placeholder*="phrase" i]');
                for (const input of inputs) {
                    const container = input.closest('form') || input.closest('[class*="search"]') || input.parentElement?.parentElement;
                    if (container) {
                        const btn = container.querySelector('button');
                        if (btn) { btn.click(); return true; }
                    }
                }
                return false;
            }''')
            if result:
                search_triggered = True
                logger.info("Discovery: triggered search via JS fallback")
        except Exception:
            pass

    if not search_triggered:
        logger.error("Could not trigger competitor search")
        return []

    # Wait for results
    results_selector = 'table tbody tr, .ant-table-tbody tr, [class*="table"] tbody tr'
    try:
        await page.wait_for_selector(results_selector, timeout=60000, state='visible')
        await page.wait_for_timeout(3000)
    except Exception:
        logger.error("Competitor results did not load within 60s")
        return []

    # Scrape competitor table
    competitors = []
    try:
        rows = await page.query_selector_all(results_selector)
        logger.info(f"Found {len(rows)} competitor rows")

        for row in rows[:20]:  # Check first 20 rows
            cells = await row.query_selector_all('td')
            if len(cells) < 5:
                continue

            # Try to extract ASIN from the row
            row_html = await row.inner_html()
            asin_match = re.search(r'[A-Z0-9]{10}', await row.inner_text())

            # Also try link in the row
            link = await row.query_selector('a[href*="/dp/"], a[href*="amazon.com"]')
            comp_asin = None
            if link:
                href = await link.get_attribute('href') or ''
                asin_from_link = re.search(r'/dp/([A-Z0-9]{10})', href)
                if asin_from_link:
                    comp_asin = asin_from_link.group(1)

            if not comp_asin and asin_match:
                candidate = asin_match.group(0)
                # Verify it looks like an ASIN (starts with B0)
                if candidate.startswith('B0') or candidate.startswith('B1'):
                    comp_asin = candidate

            if not comp_asin:
                continue

            # Skip our own product
            if comp_asin == my_asin:
                continue

            # Extract other fields from cells
            comp = {'asin': comp_asin}
            try:
                texts = []
                for cell in cells:
                    texts.append((await cell.inner_text()).strip())

                # Common SellerSprite competitor table layout:
                # Image | Title/ASIN | Brand | Price | Sales | Revenue | Rating | ...
                # Note: Revenue ($739,583) appears before or near Price ($52.99).
                # Collect ALL dollar amounts, then pick the unit price (< $1000).
                dollar_amounts = []
                for t in texts:
                    for match in re.findall(r'\$([\d,]+\.?\d*)', t):
                        try:
                            val = float(match.replace(',', ''))
                            dollar_amounts.append(val)
                        except Exception:
                            pass
                # Unit price: smallest reasonable dollar amount (> $0.01, < $1000)
                unit_prices = [v for v in dollar_amounts if 0.01 < v < 1000]
                if unit_prices:
                    comp['price'] = min(unit_prices)
                    if re.match(r'^\d+\.\d$', t) and not comp.get('rating'):
                        try:
                            comp['rating'] = float(t)
                        except Exception:
                            pass

                # Brand: usually a short text without special chars
                for t in texts[1:4]:
                    if 2 <= len(t) <= 30 and not re.search(r'[$/\d]{3,}', t) and not comp.get('brand'):
                        comp['brand'] = t
                        break

                # Title: longest text in the row
                longest = max(texts, key=len)
                if len(longest) > 20:
                    comp['title'] = longest[:100]

            except Exception as e:
                logger.warning(f"Error parsing competitor row: {e}")

            competitors.append(comp)

            if len(competitors) >= max_competitors:
                break

    except Exception as e:
        logger.error(f"Error scraping competitor table: {e}")

    logger.info(f"Discovered {len(competitors)} competitors")
    for c in competitors:
        logger.info(f"  {c.get('asin')}: {c.get('brand', '?')} — ${c.get('price', '?')}")

    return competitors


def update_config_with_discovery(product_info, competitors, seed_keywords):
    """Update config.json with discovered product data, competitors, and seeds.

    Creates a backup before writing. Merges new competitors with existing ones
    (existing entries keyed by ASIN are preserved, new ones added to open slots).
    """
    import shutil
    config_path = PROJECT_ROOT / 'config.json'
    backup_path = PROJECT_ROOT / 'config.backup.json'

    with open(config_path) as f:
        config = json.load(f)

    # Backup current config before making changes
    shutil.copy2(config_path, backup_path)
    logger.info(f"Config backed up to {backup_path}")

    asin = product_info['asin']
    parent_asin = product_info.get('parent_asin', asin)
    child_asins = product_info.get('child_asins', [asin])
    brand = product_info.get('brand', '')

    # Update active_product
    config['active_product'] = {
        'asin_parent': parent_asin,
        'asin_listing': asin,
        'brand': brand,
        'title': product_info.get('title', ''),
        'url': f'https://www.amazon.com/dp/{asin}',
        'category': product_info.get('category', ''),
        'current_price': product_info.get('price'),
        'rating': product_info.get('rating'),
        'review_count': product_info.get('review_count', 0),
        'child_asins': child_asins,
        'image_url': product_info.get('image_url', ''),
    }

    # Replace competitors entirely — don't merge with old product's competitors
    # (Old competitors from a different product category would contaminate analysis)
    merged = {}
    for i, comp in enumerate(competitors[:4]):
        slot = f'C{i + 1}'
        merged[slot] = {
            'asin': comp['asin'],
            'brand': comp.get('brand', 'Unknown'),
            'title': comp.get('title', ''),
            'price': comp.get('price'),
            'rating': comp.get('rating'),
            'note': 'Auto-discovered competitor',
        }
    config['competitors'] = merged

    # Update seed keywords
    config['seed_keywords'] = seed_keywords

    # Update collection settings
    if 'collection' not in config:
        config['collection'] = {}

    # Reverse ASIN: our product + top 2 competitors
    reverse_asins = [asin]
    for comp in competitors[:2]:
        if comp['asin'] not in reverse_asins:
            reverse_asins.append(comp['asin'])
    config['collection']['reverse_asin_asins'] = reverse_asins

    # Comparison: our product + all competitors
    comparison_asins = [asin]
    for comp in competitors:
        if comp['asin'] not in comparison_asins:
            comparison_asins.append(comp['asin'])
    config['collection']['comparison_asins'] = comparison_asins

    # Mining seeds
    config['collection']['mining_seeds'] = seed_keywords

    # Research keyword: first seed
    config['collection']['research_keyword'] = seed_keywords[0] if seed_keywords else ''
    config['collection']['competitor_keyword'] = seed_keywords[0] if seed_keywords else ''

    # Ads insights: our parent ASIN + top competitor
    ads_asins = [parent_asin]
    if competitors:
        ads_asins.append(competitors[0]['asin'])
    config['collection']['ads_insights_asins'] = ads_asins

    # Clean old input files — critical to prevent data contamination between products
    # Archive old files to inputs/archive/<old_asin>/ before writing new config
    inputs_dir = PROJECT_ROOT / 'inputs'
    archive_base = inputs_dir / 'archive'
    for sub in ['sellersprite', 'seller-central']:
        sub_dir = inputs_dir / sub
        if not sub_dir.exists():
            continue
        pattern_exts = {'sellersprite': '*.xlsx', 'seller-central': '*.csv'}
        old_files = list(sub_dir.glob(pattern_exts.get(sub, '*')))
        if old_files:
            # Archive under timestamp to avoid conflicts
            from datetime import datetime as _dt
            archive_dir = archive_base / _dt.now().strftime('%Y%m%d_%H%M%S')
            archive_dir.mkdir(parents=True, exist_ok=True)
            moved_count = 0
            for f in old_files:
                try:
                    shutil.move(str(f), str(archive_dir / f.name))
                    moved_count += 1
                except Exception as e:
                    logger.warning(f"Could not archive {f.name}: {e}")
            if moved_count:
                logger.info(f"Archived {moved_count} old {sub} input files → {archive_dir}")

    # Also clear processed JSON and old outputs for clean slate
    processed_dir = PROJECT_ROOT / 'processed'
    if processed_dir.exists():
        for f in processed_dir.glob('*.json'):
            try:
                f.unlink()
            except Exception:
                pass

    # Write back
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.info(f"Config updated: product={asin}, {len(competitors)} competitors, {len(seed_keywords)} seeds")
    return config


async def run_discovery(page, amazon_url):
    """Full discovery flow: URL → product info → competitors → config update.

    Returns dict with discovery results for the dashboard to display.
    """
    result = {
        'status': 'running',
        'steps': [],
    }

    # Step 1: Extract ASIN
    asin = extract_asin_from_url(amazon_url)
    if not asin:
        return {'status': 'failed', 'error': f'Could not extract ASIN from URL: {amazon_url}'}
    result['asin'] = asin
    result['steps'].append({'step': 'extract_asin', 'status': 'ok', 'asin': asin})

    # Step 2: Scrape Amazon product page
    product_info = await scrape_amazon_product(page, asin)
    if not product_info:
        return {'status': 'failed', 'error': f'Could not scrape Amazon product page for {asin}'}
    result['product'] = product_info
    result['steps'].append({
        'step': 'scrape_product',
        'status': 'ok',
        'title': product_info.get('title', '')[:80],
        'brand': product_info.get('brand', ''),
        'price': product_info.get('price'),
    })

    # Step 3: Generate seed keywords
    seed_keywords = generate_seed_keywords(
        product_info.get('title', ''),
        product_info.get('brand', ''),
    )
    # Filter out any empty seeds
    seed_keywords = [s for s in seed_keywords if s.strip()]
    if not seed_keywords:
        logger.warning("No seed keywords generated from title — trying SellerSprite title lookup...")
        # Fallback: try to get a title/keywords from SellerSprite's Reverse ASIN page
        try:
            from .utils import safe_goto
            ss_url = f'https://www.sellersprite.com/v3/reverse-asin?marketplace=US&month=1&q={asin}'
            if await safe_goto(page, ss_url):
                await page.wait_for_timeout(5000)
                # Try to extract the product title from SellerSprite's page
                ss_title = await page.evaluate('''() => {
                    const el = document.querySelector('.product-title, .asin-title, h2, .el-card__header');
                    return el ? el.innerText.trim() : '';
                }''')
                if ss_title and len(ss_title) > 5:
                    logger.info(f"Got title from SellerSprite: {ss_title[:80]}")
                    product_info['title'] = ss_title
                    seed_keywords = generate_seed_keywords(ss_title, product_info.get('brand', ''))
                    seed_keywords = [s for s in seed_keywords if s.strip()]
        except Exception as e:
            logger.warning(f"SellerSprite title lookup failed: {e}")

    if not seed_keywords:
        logger.warning("Still no seed keywords — collection will have limited keyword data")

    result['seed_keywords'] = seed_keywords
    result['steps'].append({
        'step': 'generate_seeds',
        'status': 'ok' if seed_keywords else 'partial',
        'seeds': seed_keywords,
    })

    # Step 4: Discover competitors via SellerSprite
    # Use first seed keyword, or ASIN as fallback search term
    search_seed = seed_keywords[0] if seed_keywords else asin
    competitors = await discover_competitors_via_sellersprite(
        page,
        seed_keyword=search_seed,
        my_asin=asin,
        max_competitors=4,
    )
    result['competitors'] = competitors
    result['steps'].append({
        'step': 'discover_competitors',
        'status': 'ok' if competitors else 'partial',
        'count': len(competitors),
        'competitors': [{'asin': c['asin'], 'brand': c.get('brand', '?')} for c in competitors],
    })

    # Step 5: Update config.json
    try:
        updated_config = update_config_with_discovery(product_info, competitors, seed_keywords)
        result['steps'].append({'step': 'update_config', 'status': 'ok'})
    except Exception as e:
        logger.error(f"Config update failed: {e}")
        result['steps'].append({'step': 'update_config', 'status': 'failed', 'error': str(e)})

    result['status'] = 'completed'
    return result
