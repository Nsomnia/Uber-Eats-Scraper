#!/usr/bin/env python3
"""
Uber Eats Scraper - Direct API Approach
Uses session cookies to call Uber Eats' internal API directly.
Faster and more reliable than HTML scraping.

Usage:
    python uber-eats-scraper.py --city Edmonton --state AB

    Or set UBER_EATS_COOKIES environment variable:
    export UBER_EATS_COOKIES="jwt-session=xxx; uev2.loc=yyy"
    python uber-eats-scraper.py --city Edmonton --state AB
"""

import json
import base64
import urllib.parse
import argparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl
import os
from typing import Optional, Dict, Any


def build_api_url(city: str, state: str) -> str:
    """Build the API endpoint URL for the given city/state."""
    state_normalized = normalize_state(state)
    return f"https://www.ubereats.com/_p/api/getFeedV1?localeCode=ca&city={city.lower()}&state={state_normalized}"


def normalize_state(state: str) -> str:
    """Normalize state/province to 2-letter code."""
    state = state.strip().upper()

    province_mapping = {
        "ALBERTA": "AB",
        "BRITISH COLUMBIA": "BC",
        "MANITOBA": "MB",
        "NEW BRUNSWICK": "NB",
        "NEWFOUNDLAND": "NL",
        "NOVA SCOTIA": "NS",
        "ONTARIO": "ON",
        "PRINCE EDWARD ISLAND": "PE",
        "QUEBEC": "QC",
        "SASKATCHEWAN": "SK",
        "YUKON": "YT",
        "NORTHWEST TERRITORIES": "NT",
        "NUNAVUT": "NU",
    }

    return province_mapping.get(state, state[:2] if len(state) > 2 else state)


def build_post_data(
    cookies: Dict[str, str], city: str = "", state: str = ""
) -> Dict[str, Any]:
    """Build the POST request data using location from cookies."""
    location_json = decode_uev2_loc(cookies.get("uev2.loc", ""))

    if (
        location_json
        and location_json.get("latitude")
        and location_json.get("longitude")
    ):
        latitude = location_json.get("latitude")
        longitude = location_json.get("longitude")
        address_data = location_json.get("address", {})
        address_title = address_data.get("title", "")
    else:
        address_title = f"{city}, {state}" if city and state else "Unknown"
        address_data = {
            "title": address_title,
            "subtitle": "",
            "address1": "",
            "address2": "",
            "eaterFormattedAddress": "",
        }
        latitude = 0
        longitude = 0

    cache_data = {
        "address": address_data,
        "latitude": latitude,
        "longitude": longitude,
        "reference": location_json.get("reference", "") if location_json else "",
        "referenceType": "google_places",
        "type": "google_places",
        "source": "user_autocomplete",
    }

    cache_key = base64.b64encode(json.dumps(cache_data).encode()).decode()
    cache_key += f"/DELIVERY///0/0//[]///"

    return {"cacheKey": cache_key, "pageInfo": {"endTime": "0", "startTime": "0"}}


def decode_uev2_loc(encoded: str) -> Optional[Dict]:
    """Decode the uev2.loc cookie which contains location info."""
    if not encoded:
        return None
    try:
        decoded = urllib.parse.unquote(encoded)
        return json.loads(decoded)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"⚠️  Could not decode uev2.loc: {e}")
        return None


def make_api_request(
    api_url: str, cookies: Dict[str, str], post_data: Dict[str, Any]
) -> Optional[Dict]:
    """Make the POST request to Uber Eats API."""
    cookie_string = "; ".join([f"{k}={v}" for k, v in cookies.items()])

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "x-csrf-token": "x",
        "x-uber-client-gitref": "web-eats-v2",
        "Origin": "https://www.ubereats.com",
        "Referer": "https://www.ubereats.com/ca/",
        "Cookie": cookie_string,
    }

    try:
        data_bytes = json.dumps(post_data).encode("utf-8")
        req = Request(api_url, data=data_bytes, headers=headers)

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        with urlopen(req, context=ssl_context, timeout=30) as response:
            response_data = response.read().decode("utf-8")
            return json.loads(response_data)

    except HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        print(f"   URL: {api_url}")
        if e.code == 401:
            print("   → Session cookies may have expired. Re-extract with Playwright.")
        return None
    except URLError as e:
        print(f"❌ URL Error: {e.reason}")
        return None
    except Exception as e:
        print(f"❌ Error making API request: {e}")
        return None


def parse_api_response(response: Dict) -> Dict[str, Any]:
    """Parse the API response and extract restaurant data with deals/savings."""
    restaurants = {}

    data = response.get("data", {})
    feed_items = data.get("feedItems", [])

    # Check for empty state
    for item in feed_items:
        if item.get("type") == "EMPTY_STATE":
            print(
                f"⚠️  API returned empty state: {item.get('title', 'No businesses available')}"
            )
            print(f"   Subtitle: {item.get('subtitle', '')}")
            return {}

    for item in feed_items:
        if item.get("type") != "REGULAR_STORE":
            continue

        store = item.get("store", {})
        if not store:
            continue

        title_obj = store.get("title", {})
        if isinstance(title_obj, dict):
            store_name = title_obj.get("text", "")
        else:
            store_name = str(title_obj)

        if not store_name:
            continue

        # Get store UUID for detailed lookups
        store_uuid = store.get("storeUuid", "")

        info = {
            "Delivery Time": "N/A",
            "Delivery Cost": "N/A",
            "Rating": "N/A",
            "Price Range": "N/A",
            "Deals & Badges": [],
            "Store URL": "",
        }

        # Extract store URL
        action_url = store.get("actionUrl", "")
        if action_url:
            info["Store URL"] = f"https://www.ubereats.com{action_url}"

        # Extract rating
        rating_info = store.get("rating", {})
        if isinstance(rating_info, dict):
            score = rating_info.get("text", rating_info.get("ratingValue", ""))
            if score:
                info["Rating"] = str(score)

        # Extract price range ($, $$, $$$)
        price_bucket = store.get("priceBucket", "")
        if price_bucket:
            info["Price Range"] = price_bucket

        # Extract promotional badges and deals from metadata
        metadata = store.get("meta", [])
        badges = []
        delivery_cost = "N/A"

        if isinstance(metadata, list):
            for meta in metadata:
                if isinstance(meta, dict):
                    text = meta.get("text", "")
                    badge_type = meta.get("badgeType", "")

                    # FARE badge = delivery fee (this is the key savings/deal info!)
                    if badge_type == "FARE" and text:
                        delivery_cost = text

                    if text:
                        badges.append(text)
                    if badge_type and badge_type not in [
                        "ETD"
                    ]:  # Skip ETD, already in delivery time
                        badges.append(f"[{badge_type}]")

            # Set delivery time from ETD badge
            for meta in metadata:
                if isinstance(meta, dict) and meta.get("badgeType") == "ETD":
                    info["Delivery Time"] = meta.get("text", "N/A")
                    break

        info["Delivery Cost"] = delivery_cost
        info["Deals & Badges"] = [b for b in badges if b != "N/A"]

        restaurants[store_name] = [info]

    return restaurants


def get_cookies_from_env() -> Optional[Dict[str, str]]:
    """Get cookies from UBER_EATS_COOKIES environment variable."""
    cookie_str = os.environ.get("UBER_EATS_COOKIES", "")
    if not cookie_str:
        return None

    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            cookies[key.strip()] = value.strip()

    if cookies:
        print("✅ Using cookies from UBER_EATS_COOKIES environment variable")
    return cookies if cookies else None


def main():
    parser = argparse.ArgumentParser(
        description="Uber Eats Scraper - Fetches restaurant data via internal API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --city Edmonton --state AB
  %(prog)s --city Toronto --state ON
  UBER_EATS_COOKIES="jwt-session=xxx" %(prog)s --city Vancouver --state BC
        """,
    )
    parser.add_argument("--city", "-c", required=True, help="City name")
    parser.add_argument(
        "--state",
        "-s",
        required=True,
        help="State/province (full name or abbreviation)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="final_result.json",
        help="Output file (default: final_result.json)",
    )

    args = parser.parse_args()

    print("🍕 Uber Eats Scraper - Direct API Mode")
    print("=" * 50)
    print(f"📍 Location: {args.city}, {args.state}")

    # Try to get cookies from environment
    cookies = get_cookies_from_env()

    if not cookies:
        print("\n❌ Cannot proceed without session cookies.")
        print("   Set UBER_EATS_COOKIES environment variable:")
        print('   export UBER_EATS_COOKIES="jwt-session=xxx; uev2.loc=yyy"')
        print("\n   To get cookies:")
        print("   1. Open https://www.ubereats.com/ca in browser")
        print("   2. Set your delivery location")
        print("   3. Open DevTools (F12) → Application → Cookies")
        print("   4. Copy jwt-session and uev2.loc values")
        return

    # Build API request
    api_url = build_api_url(args.city, args.state)
    post_data = build_post_data(cookies, args.city, args.state)

    print(f"\n🌐 Fetching restaurant data from Uber Eats API...")
    print(f"   URL: {api_url}")

    # Make API request
    response = make_api_request(api_url, cookies, post_data)

    if not response:
        print("❌ Failed to fetch data from Uber Eats API")
        return

    # Parse response
    print("📊 Parsing API response...")
    restaurants = parse_api_response(response)

    if not restaurants:
        print("⚠️  No restaurants found in API response")
        print("   Response keys:", list(response.keys()))
        with open("debug_response.json", "w") as f:
            json.dump(response, f, indent=2)
        print("   Saved full response to debug_response.json")
        return

    print(f"✅ Found {len(restaurants)} restaurants")

    # Save results
    output_file = args.output
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

    print(f"💾 Results saved to {output_file}")

    # Show sample
    print("\n📋 Sample results:")
    for i, (name, info) in enumerate(list(restaurants.items())[:10]):
        print(f"   • {name}: Rating {info[0]['Rating']}")

    if len(restaurants) > 10:
        print(f"   ... and {len(restaurants) - 10} more")


if __name__ == "__main__":
    main()
