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


def send_telegram(message: str) -> bool:
    """Send a plain-text Telegram message with retries and useful diagnostics."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return False

    endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": False,
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(endpoint, data=payload, timeout=20)
            if response.ok:
                print(f"[TELEGRAM] sent (attempt {attempt})")
                return True

            # Telegram's response usually contains the exact reason, e.g.
            # an invalid chat_id, blocked bot, or malformed message.
            print(
                f"[TELEGRAM] HTTP {response.status_code} "
                f"(attempt {attempt}): {response.text[:1000]}"
            )
        except requests.RequestException as exc:
            print(f"[TELEGRAM] request failed (attempt {attempt}): {exc}")

        if attempt < 3:
            time.sleep(2 * attempt)

    return False

