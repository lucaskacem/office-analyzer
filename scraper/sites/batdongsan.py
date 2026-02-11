"""Scraper for batdongsan.com.vn - Largest Vietnamese RE site."""

import time
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


class BatDongSanScraper:
    BASE_URL = "https://batdongsan.com.vn"
    SEARCH_URL = f"{BASE_URL}/cho-thue-van-phong-da-nang"
    MAX_PAGES = 5

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
                    url = self.SEARCH_URL if page_num == 1 else f"{self.SEARCH_URL}/p{page_num}"
                    print(f"  Page {page_num}: {url}")

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3000)
                        html = page.content()
                        soup = BeautifulSoup(html, "html.parser")

                        items = soup.select(".js__card, .re__card-full, .product-item, [class*='ProductItem']")
                        if not items:
                            items = soup.select("a[href*='/cho-thue-van-phong-']")

                        print(f"    Found {len(items)} items")

                        for item in items:
                            try:
                                listing = self._parse_listing(item)
                                if listing:
                                    listings.append(listing)
                            except Exception as e:
                                continue

                        time.sleep(4)
                    except Exception as e:
                        print(f"    Page error: {e}")
                        continue

                browser.close()
        except ImportError:
            print("  Playwright not installed, skipping")
        except Exception as e:
            print(f"  Browser error: {e}")

        return listings

    def _parse_listing(self, item):
        # Title / name
        title_el = item.select_one(".re__card-title, .product-title, h3, .js__card-title")
        name = title_el.get_text(strip=True) if title_el else ""
        if not name:
            name = item.get_text(strip=True)[:80]

        # Link
        link = item.get("href", "")
        if not link:
            link_el = item.select_one("a[href]")
            link = link_el.get("href", "") if link_el else ""
        if link and not link.startswith("http"):
            link = self.BASE_URL + link

        # Price
        price_el = item.select_one(".re__card-config-price, .product-price, [class*='price']")
        price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

        # Area
        area_el = item.select_one(".re__card-config-area, .product-area, [class*='area']")
        area = self._parse_area(area_el.get_text(strip=True)) if area_el else None

        # Address
        addr_el = item.select_one(".re__card-location, .product-location, [class*='location']")
        address = addr_el.get_text(strip=True) if addr_el else ""

        # Posting date
        date_el = item.select_one(".re__card-published-info-published-at, [class*='date'], time")
        posting_date = self._parse_date(date_el.get_text(strip=True)) if date_el else None

        if not name and not address:
            return None

        return {
            "name": name[:100],
            "address": address,
            "price": price,
            "area": area,
            "sourceUrl": link,
            "postingDate": posting_date,
        }

    def _parse_price(self, text):
        """Parse Vietnamese price text into VND/month number."""
        if not text:
            return None
        text = text.lower().replace(",", ".").replace(" ", "")
        try:
            # "50 triệu/tháng" or "50tr"
            m = re.search(r"([\d.]+)\s*(triệu|tr)", text)
            if m:
                return int(float(m.group(1)) * 1_000_000)
            # "100.000.000"
            m = re.search(r"([\d.]+)", text.replace(".", ""))
            if m and len(m.group(1)) > 6:
                return int(m.group(1))
        except (ValueError, TypeError):
            pass
        return None

    def _parse_area(self, text):
        """Parse area text into m2 number."""
        if not text:
            return None
        m = re.search(r"([\d,.]+)\s*m", text)
        if m:
            return int(float(m.group(1).replace(",", ".")))
        return None

    def _parse_date(self, text):
        """Parse Vietnamese date into ISO format."""
        if not text:
            return None
        try:
            # "15/01/2025" format
            m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
            if m:
                return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            # "X ngày trước"
            m = re.search(r"(\d+)\s*ngày", text)
            if m:
                d = datetime.now() - timedelta(days=int(m.group(1)))
                return d.strftime("%Y-%m-%d")
            # "X tháng trước"
            m = re.search(r"(\d+)\s*tháng", text)
            if m:
                d = datetime.now() - timedelta(days=int(m.group(1)) * 30)
                return d.strftime("%Y-%m-%d")
        except Exception:
            pass
        return None
