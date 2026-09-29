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




# =========================
# v2 multi-store implementation
# =========================
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup

NIKE_CATEGORY_URLS = [
    "https://www.nike.com/in/w/mens-shoes-nik1zy7ok",
    "https://www.nike.com/in/w/womens-shoes-5e1x6zy7ok",
    "https://www.nike.com/in/w/kids-shoes-v4dhzy7ok",
]
NIKE_CHANNEL = "d9a5bc42-4b9c-4976-858a-f159cf99c647"

ADIDAS_LISTING_URLS = [
    "https://www.adidas.co.in/men-outlet",
    "https://www.adidas.co.in/women-outlet",
]
ONITSUKA_LISTING_URLS = [
    "https://www.onitsukatiger.com/in/en-in/shoes/all-shoes",
]
VNV_LISTING_URLS = [
    "https://www.vegnonveg.com/markdowns",
]

V2_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept-Language": "en-IN,en;q=0.9",
}

def v2_size(value):
    s = str(value or "").lower().replace("uk", "").replace("size", "").strip()
    m = re.search(r"(?<!\d)(\d{1,2}(?:\.\d)?)(?!\d)", s)
    return m.group(1) if m and m.group(1) in TARGET_SIZES else None

def v2_money(value):
    try:
        return float(str(value).replace(",", "").replace("₹", "").strip())
    except Exception:
        return None

def v2_load_state():
    if not STATE_FILE.exists():
        return {"items": {}, "initialized_sites": []}
    try:
        raw = json.loads(STATE_FILE.read_text())
        if isinstance(raw, list):
            items = {x: True for x in raw if isinstance(x, str)}
            return {
                "items": items,
                "initialized_sites": sorted({x.split(":", 1)[0] for x in items}),
            }
        if isinstance(raw, dict):
            return {
                "items": raw.get("items", {}),
                "initialized_sites": raw.get("initialized_sites", []),
            }
    except Exception as exc:
        print(f"[STATE] load failed: {exc}")
    return {"items": {}, "initialized_sites": []}

def v2_save_state(items, initialized):
    STATE_FILE.write_text(json.dumps({
        "items": items,
        "initialized_sites": sorted(initialized),
    }, indent=2))

def v2_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return False
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for attempt in range(1, 4):
        try:
            r = requests.post(
                endpoint,
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "disable_web_page_preview": False,
                },
                timeout=20,
            )
            if r.ok:
                print(f"[TELEGRAM] sent (attempt {attempt})")
                return True
            print(f"[TELEGRAM] HTTP {r.status_code}: {r.text[:800]}")
        except Exception as exc:
            print(f"[TELEGRAM] request failed: {exc}")
        time.sleep(attempt * 2)
    return False

def v2_get(url, jina=False, timeout=30):
    try:
        target = url
        if jina:
            target = "https://r.jina.ai/http://" + url.split("://", 1)[1]
        r = requests.get(target, headers=V2_HEADERS, timeout=timeout)
        if r.ok:
            return r.text
        print(f"[HTTP] {url} -> {r.status_code}")
    except Exception as exc:
        print(f"[HTTP] {url} -> {exc}")
    return None

def v2_shopify(name, base, current):
    found = set()
    page = 1
    while page <= 100:
        try:
            r = requests.get(
                f"{base}/products.json?limit=250&page={page}",
                headers=V2_HEADERS,
                timeout=25,
            )
            if not r.ok:
                print(f"[{name}] page {page}: HTTP {r.status_code}")
                break
            products = r.json().get("products", [])
        except Exception as exc:
            print(f"[{name}] page {page}: {exc}")
            break
        if not products:
            break
        print(f"[{name}] page {page}: {len(products)} products")
        for p in products:
            title = p.get("title", "Unknown")
            handle = p.get("handle", "")
            product_url = f"{base}/products/{handle}"
            for variant in p.get("variants", []):
                size = v2_size(variant.get("title"))
                if not size or not variant.get("available"):
                    continue
                price = v2_money(variant.get("price"))
                compare = v2_money(variant.get("compare_at_price"))
                if not price or not compare or compare <= price:
                    continue
                key = f"{name}:{variant.get('id')}:{price:g}"
                found.add(key)
                current[key] = {
                    "name": name,
                    "title": title,
                    "size": size,
                    "price": price,
                    "compare": compare,
                    "url": product_url,
                }
        page += 1
        time.sleep(0.4)
    print(f"[{name}] discounted target-size items: {len(found)}")
    return found

def v2_nike_products():
    products = []
    for category in NIKE_CATEGORY_URLS:
        html = v2_get(category)
        if not html:
            html = v2_get(category, jina=True)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", {"name": "branch:deeplink:$deeplink_path"})
        if not meta or not meta.get("content"):
            print(f"[Nike] no concept id: {category}")
            continue
        q = parse_qs(urlparse(meta["content"]).query)
        concept = q.get("conceptid", [None])[0]
        if not concept:
            continue
        path = urlparse(category).path.lstrip("/")
        api = (
            f"https://api.nike.com/discover/product_wall/v1/"
            f"marketplace/IN/language/en-GB/consumerChannelId/{NIKE_CHANNEL}"
        )
        params = {
            "path": path,
            "attributeIds": concept,
            "queryType": "PRODUCTS",
            "anchor": 0,
            "count": 100,
        }
        headers = {
            **V2_HEADERS,
            "nike-api-caller-id": "nike:dotcom:browse:wall.client:2.0",
            "origin": "https://www.nike.com",
            "referer": "https://www.nike.com/",
        }
        try:
            r = requests.get(api, params=params, headers=headers, timeout=30)
            if not r.ok:
                print(f"[Nike] API HTTP {r.status_code}")
                continue
            data = r.json()
            while True:
                for grouping in data.get("productGroupings", []):
                    arr = grouping.get("products") or []
                    if arr:
                        products.append(arr[0])
                nxt = (data.get("pages") or {}).get("next")
                if not nxt:
                    break
                nr = requests.get(
                    "https://api.nike.com" + nxt,
                    headers=headers,
                    timeout=30,
                )
                if not nr.ok:
                    break
                data = nr.json()
        except Exception as exc:
            print(f"[Nike] API error: {exc}")
    unique = []
    seen = set()
    for product in products:
        code = product.get("productCode") or product.get("id")
        if code and code not in seen:
            seen.add(code)
            unique.append(product)
    print(f"[Nike] discovered {len(unique)} products")
    return unique

def v2_nike_scan(current):
    found = set()
    for p in v2_nike_products():
        prices = p.get("prices") or {}
        price = v2_money(prices.get("currentPrice"))
        compare = (
            v2_money(prices.get("fullPrice"))
            or v2_money(prices.get("originalPrice"))
        )
        if not price or not compare or compare <= price:
            continue
        pdp = p.get("pdpUrl")
        raw_url = pdp.get("url") if isinstance(pdp, dict) else pdp
        if not raw_url:
            continue
        url = urljoin("https://www.nike.com", raw_url)
        html = v2_get(url)
        if not html:
            html = v2_get(url, jina=True)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            print(f"[Nike] no product JSON: {url}")
            continue
        try:
            data = json.loads(script.string)
            pd = data["props"]["pageProps"]["selectedProduct"]
            info = pd.get("productInfo") or {}
            title = info.get("title") or p.get("copy", {}).get("title") or "Nike"
            for size_obj in pd.get("sizes", []):
                size = v2_size(
                    size_obj.get("localizedLabel") or size_obj.get("label")
                )
                status = str(size_obj.get("status", "")).lower()
                if (
                    size
                    and status not in {
                        "oos", "out_of_stock", "unavailable",
                        "sold_out", "sold-out",
                    }
                    and "out" not in status
                ):
                    key = f"Nike India:{p.get('productCode')}:{size}:{price:g}"
                    found.add(key)
                    current[key] = {
                        "name": "Nike India",
                        "title": title,
                        "size": size,
                        "price": price,
                        "compare": compare,
                        "url": url,
                    }
        except Exception as exc:
            print(f"[Nike] parse error {url}: {exc}")
    print(f"[Nike] discounted target-size items: {len(found)}")
    return found

def v2_links(html, base):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    base_host = urlparse(base).netloc
    for a in soup.find_all("a", href=True):
        u = urljoin(base, a["href"]).split("?", 1)[0]
        if urlparse(u).netloc != base_host:
            continue
        if "/products/" in u or u.lower().endswith(".html"):
            links.append(u)
    return list(dict.fromkeys(links))

def v2_sale_pages(site, listing_urls, current, limit):
    found = set()
    product_urls = []
    for listing in listing_urls:
        html = v2_get(listing) or v2_get(listing, jina=True)
        if not html:
            continue
        product_urls.extend(v2_links(html, listing))
    product_urls = list(dict.fromkeys(product_urls))[:limit]
    print(f"[{site}] candidate product URLs: {len(product_urls)}")

    for idx, url in enumerate(product_urls, 1):
        for size in sorted(TARGET_SIZES, key=float):
            if site == "Adidas India":
                target = url + (
                    "&" if "?" in url else "?"
                ) + f"forceSelSize={size}"
            else:
                target = url
            html = v2_get(target) or v2_get(target, jina=True)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text(" ", strip=True)
            sale = re.search(
                r"Sale price\s*₹?\s*([0-9,]+(?:\.\d+)?)\s*"
                r"₹?\s*([0-9,]+(?:\.\d+)?)\s*Original price",
                text_content,
                re.I,
            )
            if not sale:
                sale = re.search(
                    r"₹\s*([0-9,]+(?:\.\d+)?)\s*₹\s*"
                    r"([0-9,]+(?:\.\d+)?)\s*Original price",
                    text_content,
                    re.I,
                )
            if not sale:
                continue
            price = v2_money(sale.group(1))
            compare = v2_money(sale.group(2))
            if not price or not compare or compare <= price:
                continue

            available = False
            if site == "Adidas India":
                available = (
                    re.search(
                        rf"colou?rs? available in size\s*{re.escape(size)}\b",
                        text_content,
                        re.I,
                    )
                    is not None
                    and "sold out" not in text_content.lower()
                    and "catch it next time" not in text_content.lower()
                    and "add to bag" in text_content.lower()
                )
            else:
                # VNV/Onitsuka expose orderable sizes in the public product page.
                available = (
                    re.search(rf"\b{re.escape(size)}\s*UK\b", text_content, re.I)
                    is not None
                    and "sold out" not in text_content.lower()
                )
            if not available:
                continue

            h1 = soup.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else site
            key = f"{site}:{url}:{size}:{price:g}"
            found.add(key)
            current[key] = {
                "name": site,
                "title": title,
                "size": size,
                "price": price,
                "compare": compare,
                "url": url,
            }
        if idx % 10 == 0:
            print(f"[{site}] checked {idx}/{len(product_urls)}")

    print(f"[{site}] discounted target-size items: {len(found)}")
    return found

def v2_vegnonveg(current):
    return v2_sale_pages(
        "VegNonVeg",
        VNV_LISTING_URLS,
        current,
        180,
    )

def v2_alert(found, current, state, initialized):
    old = state["items"]
    new_items = [current[k] for k in sorted(found) if k not in old]

    # Do not flood Telegram the first time a newly supported store is seen.
    new_sites = sorted({
        item["name"] for item in current.values()
        if item["name"] not in initialized
    })
    if new_sites:
        new_items = [
            item for item in new_items
            if item["name"] not in new_sites
        ]
        initialized.update(new_sites)
        print(f"[STATE] baseline: {', '.join(new_sites)}")

    for item in new_items:
        pct = round((1 - item["price"] / item["compare"]) * 100)
        v2_telegram(
            f"🔔 {item['name']}\n"
            f"{item['title']} — UK {item['size']}\n"
            f"₹{item['price']:.0f} "
            f"(was ₹{item['compare']:.0f}, {pct}% off)\n"
            f"{item['url']}"
        )
    print(f"[ALERTS] {len(new_items)} new discounted size matches")

def v2_main():
    state = v2_load_state()
    initialized = set(state.get("initialized_sites", []))
    current = {}
    found = set()

    if TEST_TELEGRAM:
        v2_telegram(
            "✅ Shoe Alert Bot is connected.\n"
            "GitHub Actions → Telegram delivery test passed."
        )

    shopify_sites = [
        ("Superkicks", "https://www.superkicks.in"),
        ("Crepdogcrew", "https://www.crepdogcrew.com"),
        ("Limited Edt India", "https://www.limitededt.in"),
    ]
    for name, base in shopify_sites:
        try:
            found |= v2_shopify(name, base, current)
        except Exception as exc:
            print(f"[{name}] fatal: {exc}")

    try:
        found |= v2_nike_scan(current)
    except Exception as exc:
        print(f"[Nike] fatal: {exc}")

    try:
        found |= v2_sale_pages(
            "Adidas India",
            ADIDAS_LISTING_URLS,
            current,
            180,
        )
    except Exception as exc:
        print(f"[Adidas India] fatal: {exc}")

    try:
        found |= v2_sale_pages(
            "Onitsuka Tiger India",
            ONITSUKA_LISTING_URLS,
            current,
            120,
        )
    except Exception as exc:
        print(f"[Onitsuka Tiger India] fatal: {exc}")

    try:
        found |= v2_vegnonveg(current)
    except Exception as exc:
        print(f"[VegNonVeg] fatal: {exc}")

    v2_alert(found, current, state, initialized)
    v2_save_state({k: True for k in found}, initialized)
    print(
        f"Done. {len(found)} discounted target-size items "
        "currently detected across all stores."
    )

if __name__ == "__main__":
    v2_main()
