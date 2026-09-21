# Shoe Discount Tracker → Telegram

Checks Superkicks, Crepdogcrew, VegNonVeg, and Onitsuka Tiger India every 30
minutes for discounted stock in UK 11 / 11.5 / 12 / 12.5, and pings your
Telegram bot when something new shows up. Runs for free on GitHub Actions —
your phone or laptop don't need to be on.

## ⚠️ About Nike.in and Adidas.co.in

These two are **not included** in `tracker.py`. Both run on large,
enterprise e-commerce platforms with active bot-detection (rate limiting,
CAPTCHAs, IP blocking) — a scraper running from GitHub's shared IP ranges
gets blocked almost immediately, so it wouldn't give reliable alerts and
could also flag the GitHub Actions IP.

Options if you still want them covered:
1. **Manual check** — keep an eye on their sale pages yourself.
2. **A browser-based watcher** (e.g. Distill.io / Visualping) that runs
   from your own IP with a real browser — much more likely to survive
   their bot protection than a script.
3. Tell me and I can add a best-effort scraper for one of them, with the
   caveat that it may break or get blocked without warning.

## Setup (10 minutes)

### 1. Create a GitHub repo
- Create a new **private** repo (e.g. `shoe-alert-bot`).
- Upload `tracker.py`, `README.md`, and the `.github/workflows/track.yml`
  file (keep that folder structure — GitHub only picks up workflows from
  exactly `.github/workflows/`).

### 2. Add your Telegram secrets
In the repo: **Settings → Secrets and variables → Actions → New repository secret**
- `TELEGRAM_TOKEN` = your bot token from BotFather
- `TELEGRAM_CHAT_ID` = your chat ID (from the `getUpdates` step)

### 3. Turn it on
- Go to the **Actions** tab → you should see "Shoe Discount Tracker" →
  click **Enable workflow** if prompted.
- Click **Run workflow** once to test it manually.
- After that, it runs automatically every 30 minutes.

### 4. Confirm it's working
- Check the Actions tab for a green checkmark on the run.
- You should get a Telegram message for any currently discounted item in
  your sizes the first time it runs (this is expected — it's your
  baseline). After that, you'll only get pinged for *new* discounts.

## Adjusting things later
- **Sizes**: edit `TARGET_SIZES` at the top of `tracker.py`.
- **Check frequency**: edit the `cron` line in `track.yml` (careful — GitHub
  Actions free tier has usage limits; every 30 min is a safe default).
- **Add another Shopify-based store**: add `{"name": ..., "base": "https://..."}`
  to `SHOPIFY_SITES` in `tracker.py`.
