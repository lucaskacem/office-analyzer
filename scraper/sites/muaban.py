"""Scraper for muaban.net."""

import time
import re
from bs4 import BeautifulSoup


class MuabanScraper:
    BASE_URL = "https://muaban.net"
    SEARCH_URL = f"{BASE_URL}/cho-thue-van-phong-mat-bang-da-nang-l15-c3408"
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
                        page.wait_for_timeout(3000)
                        html = page.content()
                        soup = BeautifulSoup(html, "html.parser")

                        items = soup.select(".listing-item, .item, [class*='PostItem']")
                        if not items:
                            items = soup.select("a[href*='/cho-thue']")

                        print(f"    Found {len(items)} items")

                        for item in items:
                            try:
                                listing = self._parse_listing(item)
                                if listing:
                                    listings.append(listing)
                            except Exception:
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
        title_el = item.select_one("h4, h3, .title, [class*='title']")
        name = title_el.get_text(strip=True) if title_el else ""

        link = item.get("href", "")
        if not link:
            link_el = item.select_one("a[href]")
            link = link_el.get("href", "") if link_el else ""
        if link and not link.startswith("http"):
            link = self.BASE_URL + link

        price_el = item.select_one("[class*='price'], .price")
        price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

        area_el = item.select_one("[class*='area'], .area")
        area = self._parse_area(area_el.get_text(strip=True)) if area_el else None

        addr_el = item.select_one("[class*='address'], [class*='location'], .address")
        address = addr_el.get_text(strip=True) if addr_el else ""

        if not name and not address:
            return None

        return {
            "name": name[:100],
            "address": address,
            "price": price,
            "area": area,
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

    def _parse_area(self, text):
        if not text:
            return None
        m = re.search(r"([\d,.]+)\s*m", text)
        if m:
            return int(float(m.group(1).replace(",", ".")))
        return None
