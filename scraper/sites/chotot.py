"""Scraper for chotot.com - Uses API endpoint."""

import time
import re
import json
from datetime import datetime


class ChototScraper:
    # Chotot has a public API for listings
    API_URL = "https://gateway.chotot.com/v1/public/ad-listing"
    SEARCH_URL = "https://www.chotot.com/da-nang/van-phong-cho-thue"
    MAX_PAGES = 3

    def scrape(self):
        listings = []
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    locale="vi-VN",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                for page_num in range(1, self.MAX_PAGES + 1):
                    url = self.SEARCH_URL if page_num == 1 else f"{self.SEARCH_URL}?page={page_num}"
                    print(f"  Page {page_num}: {url}")

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(4000)
                        html = page.content()

                        # Try to extract from Next.js data or page content
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, "html.parser")

                        # Try script data
                        scripts = soup.select("script[type='application/json'], script#__NEXT_DATA__")
                        for script in scripts:
                            try:
                                data = json.loads(script.string)
                                ads = self._extract_ads_from_json(data)
                                listings.extend(ads)
                            except (json.JSONDecodeError, Exception):
                                continue

                        # Fallback: parse HTML
                        if not listings:
                            items = soup.select("[class*='AdItem'], [class*='listing'], .re__card-full")
                            print(f"    Found {len(items)} HTML items")
                            for item in items:
                                try:
                                    listing = self._parse_html_listing(item)
                                    if listing:
                                        listings.append(listing)
                                except Exception:
                                    continue

                        time.sleep(5)
                    except Exception as e:
                        print(f"    Page error: {e}")
                        continue

                browser.close()
        except ImportError:
            print("  Playwright not installed, skipping")
        except Exception as e:
            print(f"  Browser error: {e}")

        return listings

    def _extract_ads_from_json(self, data):
        """Extract ads from Next.js JSON data."""
        ads = []

        def find_ads(obj, depth=0):
            if depth > 10:
                return
            if isinstance(obj, dict):
                if "list_id" in obj and ("subject" in obj or "body" in obj):
                    ads.append(self._normalize_api_ad(obj))
                for v in obj.values():
                    find_ads(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    find_ads(item, depth + 1)

        find_ads(data)
        return ads

    def _normalize_api_ad(self, ad):
        price = ad.get("price") or ad.get("price_string")
        if isinstance(price, str):
            price = self._parse_price(price)

        return {
            "name": ad.get("subject", ad.get("body", ""))[:100],
            "address": ad.get("address", ad.get("area_name", "")),
            "price": price,
            "area": ad.get("size"),
            "sourceUrl": f"https://www.chotot.com/{ad.get('list_id', '')}.htm" if ad.get("list_id") else "",
            "lat": ad.get("latitude"),
            "lng": ad.get("longitude"),
        }

    def _parse_html_listing(self, item):
        from bs4 import BeautifulSoup
        title_el = item.select_one("h3, [class*='title'], [class*='subject']")
        name = title_el.get_text(strip=True) if title_el else ""

        link = item.get("href", "")
        if not link:
            link_el = item.select_one("a[href]")
            link = link_el.get("href", "") if link_el else ""
        if link and not link.startswith("http"):
            link = "https://www.chotot.com" + link

        price_el = item.select_one("[class*='price']")
        price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

        if not name:
            return None

        return {
            "name": name[:100],
            "address": "",
            "price": price,
            "sourceUrl": link,
        }

    def _parse_price(self, text):
        if not text:
            return None
        text = text.lower().replace(",", ".").replace(" ", "")
        m = re.search(r"([\d.]+)\s*(triệu|tr)", text)
        if m:
            return int(float(m.group(1)) * 1_000_000)
        return None
