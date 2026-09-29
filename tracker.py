"""
Shoe Discount Tracker
---------------------
Checks a list of sneaker/shoe stores for discounted stock in your sizes
(UK 11, 11.5, 12, 12.5, 13) and sends a Telegram alert for anything new.

Confirmed Shopify stores (reliable, hit their public /products.json feed
directly):
    - Superkicks
    - Crepdogcrew

Unconfirmed platform (script auto-tries a few known URL patterns each run
and logs which one — if any — works):
    - VegNonVeg
    - Onitsuka Tiger India
    - Limited Edt India

NOT covered here (see README.md "Nike & Adidas" section for why):
    - Nike.in
    - Adidas.co.in

Run manually with:  python tracker.py
(Needs TELEGRAM_TOKEN and TELEGRAM_CHAT_ID as environment variables.)
"""

import json
import os
import re
import time
from pathlib import Path

import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# UK sizes you're tracking
TARGET_SIZES = {"11", "11.5", "12", "12.5", "13"}

STATE_FILE = Path("state.json")

SHOPIFY_SITES = [
    {"name": "Superkicks", "base": "https://www.superkicks.in"},
    {"name": "Crepdogcrew", "base": "https://www.crepdogcrew.com"},
]

# Sites where we're not 100% sure of the platform / correct base URL yet.
# The script tries each candidate base in order and uses the first one
# that returns a real Shopify product feed. Whichever one works (or if
# none do) gets printed clearly in the log so we can lock in the right
# one.
UNCONFIRMED_SITES = [
    {
        "name": "VegNonVeg",
        "candidates": [
            "https://www.vegnonveg.com",
            "https://vegnonveg.com",
            "https://store.vegnonveg.com",
            "https://shop.vegnonveg.com",
        ],
    },
    {
        "name": "Onitsuka Tiger India",
        "candidates": [
            "https://www.onitsukatiger.com/en-in",
            "https://www.onitsukatiger.com/in/en",
            "https://www.onitsukatiger.com/in",
            "https://www.onitsukatiger.com",
        ],
    },
    {
        "name": "Limited Edt India",
        "candidates": [
            "https://www.limitededt.in",
            "https://limitededt.in",
        ],
    },
]

# NOT included — these are large enterprise platforms with active bot
# protection. A scheduled scraper from GitHub's shared IPs gets blocked
# almost immediately, so including them would give unreliable/no alerts
# rather than working ones. See README.md for options.
#   - Nike.in
#   - Adidas.co.in

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def load_state() -> set:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_state(seen: set) -> None:
    STATE_FILE.write_text(json.dumps(sorted(seen), indent=2))


def size_matches(variant_title: str):
    """
    Shopify variant titles look like 'UK 11 / Black' or '11.5' etc.
    Pull the first number-like token out and see if it's one we track.
    """
    title = variant_title.lower().replace("uk", "").strip()
    match = re.search(r"(\d{1,2}(?:\.\d)?)", title)
    if not match:
        return None
    size = match.group(1)
    return size if size in TARGET_SIZES else None


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"Telegram error: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Telegram send failed: {e}")


def find_working_base(name: str, candidates: list) -> str | None:
    """Try each candidate base URL and return the first that serves a real
    Shopify product feed (i.e. valid JSON with a 'products' key)."""
    for base in candidates:
        url = f"{base}/products.json?limit=1"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if "products" in data:
                    print(f"[{name}] confirmed working base: {base}")
                    return base
            print(f"[{name}] tried {base} -> HTTP {resp.status_code}")
        except Exception as e:
            print(f"[{name}] tried {base} -> error: {e}")
    print(
        f"[{name}] none of the candidate URLs served a Shopify product feed. "
        f"This store likely isn't on Shopify (or uses a different setup) — "
        f"skipping until the correct source is confirmed."
    )
    return None


def check_shopify_site(site: dict, seen: set, newly_seen: set) -> None:
    base = site["base"]
    name = site["name"]
    page = 1

    while True:
        url = f"{base}/products.json?limit=250&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[{name}] fetch failed on page {page}: {e}")
            break

        products = data.get("products", [])
        if not products:
            break

        for product in products:
            title = product.get("title", "Unknown product")
            handle = product.get("handle", "")
            product_url = f"{base}/products/{handle}"

            for variant in product.get("variants", []):
                size = size_matches(variant.get("title", "") or "")
                if not size or not variant.get("available"):
                    continue

                try:
                    price = float(variant.get("price") or 0)
                except (TypeError, ValueError):
                    continue

                compare_raw = variant.get("compare_at_price")
                try:
                    compare_at = float(compare_raw) if compare_raw else 0
                except (TypeError, ValueError):
                    compare_at = 0

                if compare_at and compare_at > price:
                    discount_pct = round((1 - price / compare_at) * 100)
                    key = f"{name}:{variant.get('id')}"
                    newly_seen.add(key)

                    if key not in seen:
                        msg = (
                            f"\U0001F514 <b>{name}</b>\n"
                            f"{title} — UK {size}\n"
                            f"₹{price:.0f} (was ₹{compare_at:.0f}, {discount_pct}% off)\n"
                            f"{product_url}"
                        )
                        send_telegram(msg)

        page += 1
        if page > 20:  # safety cap so a bug can't loop forever
            break
        time.sleep(1)  # be polite to the store's servers


def main():
    seen = load_state()
    newly_seen: set = set()

    for site in SHOPIFY_SITES:
        check_shopify_site(site, seen, newly_seen)

    for site in UNCONFIRMED_SITES:
        base = find_working_base(site["name"], site["candidates"])
        if base:
            check_shopify_site({"name": site["name"], "base": base}, seen, newly_seen)

    save_state(newly_seen)
    print(f"Done. {len(newly_seen)} discounted items in your sizes currently listed.")


if __name__ == "__main__":
    main()
