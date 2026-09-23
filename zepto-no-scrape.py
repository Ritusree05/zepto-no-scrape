import json
import sys
import os

import requests
from dotenv import load_dotenv

load_dotenv()

url = "https://bff-gateway.zepto.com/cfs/api/v1/cart/coupons/fetch-list"

def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        sys.exit(f"Missing {name} in .env")
    return value

payload = json.dumps({
  "activeTab": "PAYMENT_OFFERS_TAB",
  "filterKey": None,
  "renderHeader": False,
  "cartId": env("ZEPTO_CART_ID"),
    "storeId": env("ZEPTO_STORE_ID"),
    "latitude": float(env("ZEPTO_LATITUDE")),
    "longitude": float(env("ZEPTO_LONGITUDE")),
    "userAddressId": env("ZEPTO_USER_ADDRESS_ID"),
  "useZCoins": False,
  "useZeptoCash": True,
  "removedCampaignProducts": [],
  "installedUpiApps": [],
  "isCredPayEligible": True,
  "enableTabbedView": True,
  "pageType": "COUPON_REVAMP"
})

headers = {
  'app_version': '16.31.6',
  'appversion': '16.31.6',
  'auth_from_cookie': 'true',
  'auth_revamp_flow': 'v2',
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36',
  "Cookie": (
        f"user_id={env('ZEPTO_USER_ID')}; "
        f"aws-waf-token={env('ZEPTO_AWS_WAF_TOKEN')}; "
        "isAuth=true; "
        f"accessToken={env('ZEPTO_ACCESS_TOKEN')}; "
        f"refreshToken={env('ZEPTO_REFRESH_TOKEN')}"
    ),
}


# Error Handling
def fetch_raw_offers(out_path: str = "raw_offers.json") -> int:
    # 1. Network / request-level errors (DNS failure, timeout, connection reset, etc.)
    try:
        response = requests.request(
            "POST", url, headers=headers, data=payload, timeout=15
        )
    except requests.exceptions.Timeout:
        print("Request timed out. Zepto's servers may be slow or unreachable right now.")
        return 1
    except requests.exceptions.ConnectionError:
        print("Connection error. Check your network connection and try again.")
        return 1
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return 1

    # 2. Auth / HTTP-status errors — token expired, forbidden, rate-limited, server error
    if response.status_code in (401, 403):
        print(
            f"Auth failed (HTTP {response.status_code}). "
            "Your accessToken/refreshToken/cookie is likely expired — log in again and retry."
        )
        return 1
    if response.status_code == 429:
        print("Rate-limited (HTTP 429) by Zepto or the WAF. Wait and retry later.")
        return 1
    if not response.ok:
        print(f"Request failed with HTTP {response.status_code}: {response.text[:500]}")
        return 1

    # 3. Body must actually be valid JSON
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Response was not valid JSON (got HTML or an empty body). "
              "This usually means the session expired or a WAF challenge page was returned instead of data.")
        print(f"Raw response (truncated): {response.text[:500]}")
        return 1

    # 4. Body-level auth/session failure even on HTTP 200
    #    (some APIs return 200 with an error payload instead of a proper HTTP status)
    if isinstance(data, dict) and any(
        str(data.get(k, "")).upper() in ("UNAUTHORIZED", "UNAUTHENTICATED", "TOKEN_EXPIRED", "SESSION_EXPIRED")
        for k in ("status", "statusCode", "errorCode", "code")
    ):
        print(f"Session/token rejected by the API: {data}")
        return 1

    # 5. Sanity check: the shape we actually need downstream must be present
    if not isinstance(data, dict) or "pageLayout" not in data:
        print("Response was valid JSON but didn't contain the expected 'pageLayout' offers data. "
              "Token may be stale, or the cart/store context (cartId/storeId) may be invalid.")
        print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        return 1

    # Only now — verified token, valid response, expected shape — do we persist and report success
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"Fetched data successfully but failed to write {out_path}: {e}")
        return 1

    print(f"{out_path} successfully created")
    return 0


def main() -> int:
    return fetch_raw_offers()


if __name__ == "__main__":
    sys.exit(main())