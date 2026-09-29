# Shoe Alert Bot

Checks for discounted shoes in UK **11, 11.5, 12, 12.5 and 13** and sends a Telegram alert when a matching discounted size is newly detected.

## Stores

- Superkicks
- Crepdogcrew
- Limited Edt India
- Nike India
- adidas India
- VegNonVeg
- Onitsuka Tiger India

## Detection

Shopify stores use their public product feed.

Nike uses Nike's public India product-wall data plus public product-page data for size availability.

adidas, VegNonVeg and Onitsuka use public storefront/listing and product-page data. The tracker does **not** solve CAPTCHAs, defeat authentication, or bypass access controls. If a retailer blocks the GitHub runner or changes its storefront, that store is logged as unavailable rather than producing false alerts.

## Telegram

Repository secrets required:

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

A code deployment to `main` sends one Telegram connection test. Scheduled runs stay quiet unless a matching shoe alert is found.

## Alert rules

A notification requires:

1. sale price below original price;
2. one of the tracked UK sizes is orderable;
3. the exact store/product/size/price combination was not already alerted.

A size that sells out and later returns can alert again. A price change can also alert again.

Newly added stores are baselined on their first successful scan so Telegram is not flooded with existing sale inventory.

## Schedule

GitHub Actions runs every 30 minutes. Your phone and computer do not need to be on.
