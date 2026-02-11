#!/usr/bin/env python3
"""
Office scraper for Vietnamese real estate sites.
Scrapes office-for-rent listings in Da Nang and outputs JSON.
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime, date
from pathlib import Path

# Add parent to path for module imports
sys.path.insert(0, str(Path(__file__).parent))

from sites.batdongsan import BatDongSanScraper
from sites.alonhadat import AlonhadatScraper
from sites.chotot import ChototScraper
from sites.muaban import MuabanScraper
from sites.dothi import DothiScraper
from sites.cafeland import CafelandScraper
from sites.homedy import HomedyScraper

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "scraped_offices.json"

SCRAPERS = [
    ("batdongsan.com.vn", BatDongSanScraper),
    ("alonhadat.com.vn", AlonhadatScraper),
    ("chotot.com", ChototScraper),
    ("muaban.net", MuabanScraper),
    ("dothi.net", DothiScraper),
    ("cafeland.vn", CafelandScraper),
    ("homedy.com", HomedyScraper),
]


def deduplicate(listings):
    """Remove duplicate listings based on address proximity and name similarity."""
    from math import radians, cos, sin, asin, sqrt

    def haversine(lat1, lng1, lat2, lng2):
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        return 6371 * 2 * asin(sqrt(a))

    unique = []
    for listing in listings:
        is_dup = False
        for existing in unique:
            if (listing.get("lat") and listing.get("lng") and
                existing.get("lat") and existing.get("lng")):
                dist = haversine(listing["lat"], listing["lng"],
                                existing["lat"], existing["lng"])
                if dist < 0.1:  # within 100m
                    is_dup = True
                    break
        if not is_dup:
            unique.append(listing)
    return unique


def calculate_months_on_market(posting_date_str):
    """Calculate months since posting date."""
    if not posting_date_str:
        return None
    try:
        posted = datetime.strptime(posting_date_str, "%Y-%m-%d").date()
        today = date.today()
        months = (today.year - posted.year) * 12 + (today.month - posted.month)
        return max(0, months)
    except (ValueError, TypeError):
        return None


def geocode_address(address):
    """Geocode an address using Nominatim (free)."""
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut

    geolocator = Nominatim(user_agent="office-analyzer-danang")
    try:
        # Try with full address first
        location = geolocator.geocode(f"{address}, Đà Nẵng, Vietnam", timeout=10)
        if location:
            return location.latitude, location.longitude

        # Try simplified
        simplified = address.split(",")[0].strip()
        location = geolocator.geocode(f"{simplified}, Da Nang, Vietnam", timeout=10)
        if location:
            return location.latitude, location.longitude
    except (GeocoderTimedOut, Exception) as e:
        print(f"  Geocoding failed for '{address}': {e}")
    return None, None


def normalize_listing(raw, source):
    """Normalize a raw listing into standard format."""
    lat = raw.get("lat")
    lng = raw.get("lng")

    # Geocode if no coordinates
    if not lat or not lng:
        address = raw.get("address", "")
        if address:
            lat, lng = geocode_address(address)
            time.sleep(1.5)  # Rate limit geocoding

    if not lat or not lng:
        return None  # Skip listings we can't locate

    months = raw.get("monthsOnMarket")
    if months is None and raw.get("postingDate"):
        months = calculate_months_on_market(raw["postingDate"])

    area = raw.get("area")
    floors = raw.get("floors")
    single_floor = raw.get("singleFloor")
    if single_floor is None and floors:
        single_floor = floors == 1

    return {
        "name": raw.get("name", "Unknown Office"),
        "address": raw.get("address", ""),
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "grade": raw.get("grade", ""),
        "price": raw.get("price"),
        "area": area,
        "floors": floors,
        "year": raw.get("year"),
        "monthsOnMarket": months,
        "singleFloor": single_floor,
        "source": source,
        "sourceUrl": raw.get("sourceUrl", ""),
        "scrapedAt": date.today().isoformat(),
    }


def merge_with_existing(new_listings):
    """Merge new listings with existing scraped data."""
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE) as f:
                existing = json.load(f)
            # Keep existing listings and add new ones
            all_listings = existing + new_listings
        except (json.JSONDecodeError, Exception):
            all_listings = new_listings
    else:
        all_listings = new_listings

    return deduplicate(all_listings)


def main():
    print("=" * 60)
    print(f"Office Scraper - Da Nang - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    all_listings = []
    errors = []

    for source_name, scraper_class in SCRAPERS:
        print(f"\n{'─' * 40}")
        print(f"Scraping: {source_name}")
        print(f"{'─' * 40}")

        try:
            scraper = scraper_class()
            raw_listings = scraper.scrape()
            print(f"  Found {len(raw_listings)} raw listings")

            normalized = []
            for raw in raw_listings:
                listing = normalize_listing(raw, source_name)
                if listing:
                    normalized.append(listing)

            print(f"  Normalized: {len(normalized)} valid listings")
            all_listings.extend(normalized)

        except Exception as e:
            print(f"  ERROR: {e}")
            errors.append((source_name, str(e)))
            continue

    print(f"\n{'=' * 60}")
    print(f"Total raw listings: {len(all_listings)}")

    # Merge and deduplicate
    final = merge_with_existing(all_listings)
    print(f"After dedup + merge: {len(final)} unique listings")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {OUTPUT_FILE}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for source, err in errors:
            print(f"  - {source}: {err}")

    print("Done!")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
