# Uber-Eats-Scraper
Python-based data scraper to gather Uber Eats restaurant data via internal API.

## Quick Start

```bash
# Set cookies (from browser DevTools → Application → Cookies)
export UBER_EATS_COOKIES="jwt-session=xxx; uev2.loc=yyy"

# Run scraper
python uber-eats-scraper.py --city Edmonton --state AB
```

## Requirements

- Python 3.7+
- Uber Eats session cookies (`jwt-session` and `uev2.loc`)

## Cookie Extraction

1. Open https://www.ubereats.com/ca in your browser
2. Set your delivery location
3. Open DevTools (F12) → Application → Cookies
4. Copy values for:
   - `jwt-session`
   - `uev2.loc`

Set as environment variable:
```bash
export UBER_EATS_COOKIES="jwt-session=YOUR_TOKEN; uev2.loc=YOUR_LOCATION_DATA"
```

## Usage

```bash
# Basic usage
python uber-eats-scraper.py --city Toronto --state ON

# Custom output file
python uber-eats-scraper.py --city Vancouver --state BC --output my-results.json

# Full province names also work
python uber-eats-scraper.py --city Edmonton --state Alberta
```

## Output Format

```json
{
    "Restaurant Name": [
        {
            "Delivery Time": "N/A",
            "Delivery Cost": "N/A",
            "Rating": "4.5"
        }
    ]
}
```

## How It Works

The scraper uses Uber Eats' internal API (`/_p/api/getFeedV1`) which returns structured JSON data instead of parsing HTML. This is:
- **Faster** - Direct API calls vs page rendering
- **More reliable** - JSON structure is stable
- **Less fragile** - API changes less frequently than CSS classes

## Troubleshooting

### Empty results
- Verify cookies are current (session may have expired)
- Check that location coordinates are valid
- Ensure state uses 2-letter abbreviation (AB, ON, BC)

### 401 Unauthorized
- Re-extract fresh cookies from browser
- Session tokens expire after ~24 hours
