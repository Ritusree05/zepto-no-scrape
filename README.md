# Zepto Bank/Card Offers

Fetches the payment offers shown on Zepto's checkout page and lists the bank and card offers in a readable table.

## Run

```bash
pip install requests python-dotenv

cp .env.example .env   # then fill in your values

python zepto-no-scrape.py
python main-no-scrape.py
```

1. `zepto-no-scrape.py` calls Zepto's API and saves the response to `raw_offers.json`.
2. `main-no-scrape.py` reads `raw_offers.json`, filters the offers and prints them.

## Approach

This version does **not** use browser automation (no Selenium, Playwright or page scraping). Instead, it sends the same request the Zepto web app makes to load the offers list and calls that API directly from a Python script using `requests`.

- **Faster and more reliable:** there is no browser to launch and no page layout to break.
- **Structured data:** the API returns JSON, so there is no HTML to parse.
- **Auth via `.env`:** Zepto's offers need a logged-in session, so the session tokens and cart/location IDs are read from `.env`. This file is git-ignored. `.env.example` lists the keys to fill in.
- **Error handling:** expired tokens, WAF blocks, rate limits and unexpected responses each print a clear message instead of failing silently.

## Note

Session tokens expire quickly. If you see an auth error, log in to Zepto again and copy fresh values into `.env`.