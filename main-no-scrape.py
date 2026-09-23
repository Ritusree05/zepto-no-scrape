import io
import json
import re
import sys

# Ensure utf-8 output on Windows consoles that default to cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Non-bank brands (card networks, wallets, UPI apps & fintechs)
NON_BANK_BRANDS: list[str] = [
    "Visa",
    "Mastercard",
    "RuPay",
    "Rupay",
    "Novio",
    "Amex",
    "American Express",
    "Paytm",
    "Amazon Pay",
    "Amazon",
    "MobiKwik",
    "Mobikwik",
    "Bajaj Pay",
    "Bajaj",
    "Jupiter",
    "BHIM",
]

_non_bank_pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(b) for b in NON_BANK_BRANDS) + r")\b",
    re.IGNORECASE,
)

# Patterns to extract issuer / bank / service name from heading:
# 1. "... with/via/using/on <Issuer> Credit/Debit/UPI/wallet/app/Balance ..."
_issuer_prep_pattern = re.compile(
    r"\b(?:with|via|using|on)\s+(.+?)\s+(?:Credit|Debit|UPI|wallet|app|App|Balance|Later|card|cards)\b",
    re.IGNORECASE,
)
# 2. "... Off <Issuer> Credit/Debit ..."
_issuer_off_pattern = re.compile(
    r"\bOff\s+(.+?)\s+(?:Credit|Debit|UPI|app)\b",
    re.IGNORECASE,
)
# 3. Fallback: match after "with/via/using/on " till end of string
_issuer_fallback_pattern = re.compile(
    r"\b(?:with|via|using|on)\s+(.+)$",
    re.IGNORECASE,
)

# Does the heading explicitly mention a Credit Card or Debit Card?
# Catches "Visa Credit Card", "any Debit Card", "RuPay Credit Cards", etc.,
# regardless of whether the issuer is a bank or a non-bank network.
_card_mention_pattern = re.compile(
    r"\b(?:credit|debit)\s*cards?\b",
    re.IGNORECASE,
)


# Classification helpers

def extract_issuer(heading: str) -> str | None:
    # Clean trailing punctuation
    clean_heading = heading.rstrip(" .")

    m = (
        _issuer_prep_pattern.search(clean_heading)
        or _issuer_off_pattern.search(clean_heading)
        or _issuer_fallback_pattern.search(clean_heading)
    )
    if not m:
        return None

    issuer = m.group(1).strip()
    # Strip common leading words like "payment via", "using", etc. if captured
    issuer = re.sub(r"^(?:payment via|payments via|using|payment)\s+", "", issuer, flags=re.IGNORECASE).strip()
    return issuer or None


def is_bank_related(heading: str) -> bool:
    issuer = extract_issuer(heading)
    if issuer is None:
        return True  # conservative fallback

    # Check if the issuer is purely one of the non-bank brands
    return not bool(re.fullmatch(
        r"(?:" + "|".join(re.escape(b) for b in NON_BANK_BRANDS) + r")[\w\s,&./]*",
        issuer,
        re.IGNORECASE,
    ))


def mentions_card(heading: str) -> bool:
    return bool(_card_mention_pattern.search(heading))


def is_relevant(heading: str) -> bool:
    return is_bank_related(heading) or mentions_card(heading)


# Data extraction

def extract_offers(raw: dict) -> list[dict]:
    offers = []
    for widget in raw.get("pageLayout", {}).get("widgets", []):
        if widget.get("widgetType") != "COUPON_CARD_WIDGET":
            continue
        items = widget["data"]["items"]
        meta = items["couponButton"]["action"]["actionMeta"]
        heading = items["heading"]["text"]
        offers.append({
            "heading": heading,
            "coupon_code": items["couponCode"]["text"],
            "issuer": extract_issuer(heading),
            "is_bank": is_bank_related(heading),
            "mentions_card": mentions_card(heading),
            "is_relevant": is_relevant(heading),
            "coupon_type": meta.get("couponType", ""),
            "coupon_id": meta.get("couponId", ""),
            "state": items["couponButton"].get("state", ""),
            "description": items.get("termsAndConditions", {}).get("description", ""),
            "terms": items.get("termsAndConditions", {}).get("terms", []),
        })
    return offers


# To print dropped (wallet/UPI/app-balance only) offers
def print_dropped_offers(offers: list[dict]) -> None:
    dropped = [o for o in offers if not o["is_relevant"]]

    print("=" * 60)
    print(f"  Dropped Offers - wallet / UPI / app-balance only ({len(dropped)})")
    print("=" * 60)
    if not dropped:
        print("  (none found)")
        return

    for i, offer in enumerate(dropped, 1):
        print(f"\n  {i:2d}. {offer['heading']}")
        print(f"      Code  : {offer['coupon_code']}")
        print(f"      Brand : {offer['issuer']}")
        print(f"      Type  : {offer['coupon_type']}")
        print(f"      State : {offer['state']}")
        print(f"      Desc  : {offer['description']}")


def print_kept_offers(offers: list[dict]) -> None:
    kept = [o for o in offers if o["is_relevant"]]

    print(f"\n{'='*60}")
    print(f"  Bank & Card Offers ({len(kept)})")
    print(f"{'='*60}")

    for i, offer in enumerate(kept, 1):
        tag = "Bank" if offer["is_bank"] else "Card network"
        print(f"\n  {i:2d}. {offer['heading']}")
        print(f"      Code  : {offer['coupon_code']}")
        print(f"      Issuer: {offer['issuer']} ({tag})")
        print(f"      Type  : {offer['coupon_type']}")
        print(f"      State : {offer['state']}")
        print(f"      Desc  : {offer['description']}")

    print(f"\n{'='*60}\n")


def filter_and_print(raw_path: str = "raw_offers.json") -> None:
    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    all_offers = extract_offers(raw)
    kept = [o for o in all_offers if o["is_relevant"]]
    dropped = [o for o in all_offers if not o["is_relevant"]]

    # Summary
    print(f"Total payment offers      : {len(all_offers)}")
    print(f"Bank / card offers (kept) : {len(kept)}")
    print(f"Dropped (wallet/UPI/etc.) : {len(dropped)}")

    # Persist dropped offers for reference
    with open("non_bank_offers.json", "w", encoding="utf-8") as f:
        json.dump(dropped, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(dropped)} dropped offers -> non_bank_offers.json")

    # Persist kept offers too, since that's the actual deliverable now
    with open("kept_offers.json", "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(kept)} kept offers -> kept_offers.json")

    print_kept_offers(all_offers)


def run_workflow() -> None:
    print("\nFiltering and printing offers...\n")
    filter_and_print()


if __name__ == "__main__":
    run_workflow()