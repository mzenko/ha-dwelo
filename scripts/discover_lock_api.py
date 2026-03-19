"""
Playwright script to discover which API endpoints the Dwelo web app
calls when rendering the community locks section.

Run with:
    uv run python scripts/discover_lock_api.py
"""
import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

TOKEN = os.environ["DWELO_TOKEN"]
GATEWAY_ID = os.environ["DWELO_GATEWAY_ID"]
COMMUNITY_ID = os.environ.get("DWELO_COMMUNITY_ID", "")
UNIT_URL = f"https://web.dwelo.com/units/{GATEWAY_ID}?community={COMMUNITY_ID}"

# Extract user ID from the JWT payload at runtime.
import base64, json as _json
_payload = TOKEN.split(".")[1]
_payload += "=" * (-len(_payload) % 4)
USER_ID = str(_json.loads(base64.b64decode(_payload))["id"])

SCREENSHOT = "/tmp/dwelo_page.png"


async def main():
    api_calls: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # The app stores auth via Angular's $cookies service.
        # Keys confirmed from app JS bundle: "authToken" and "currentUserId".
        await context.add_cookies([
            {"name": "authToken",     "value": TOKEN,   "domain": ".dwelo.com", "path": "/"},
            {"name": "currentUserId", "value": USER_ID, "domain": ".dwelo.com", "path": "/"},
        ])

        page = await context.new_page()

        # Also inject the Authorization header on every API request as a belt-and-suspenders approach
        async def inject_auth(route, request):
            headers = {**request.headers, "authorization": f"Token {TOKEN}"}
            await route.continue_(headers=headers)

        await page.route("**/api.dwelo.com/**", inject_auth)

        # Track all API calls
        async def on_response(response):
            if "api.dwelo.com" in response.url:
                try:
                    body = await response.json()
                except Exception:
                    body = None
                api_calls.append({
                    "method": response.request.method,
                    "url": response.url,
                    "status": response.status,
                    "body": body,
                })

        page.on("response", on_response)

        print(f"Navigating to {UNIT_URL} ...")
        try:
            await page.goto(UNIT_URL, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"  (warning: {e})")

        await page.wait_for_timeout(3000)

        print(f"Final URL : {page.url}")
        print(f"Page title: {await page.title()}")
        await page.screenshot(path=SCREENSHOT, full_page=True)
        print(f"Screenshot: {SCREENSHOT}")

        await browser.close()

    print(f"\n=== {len(api_calls)} API call(s) to api.dwelo.com ===\n")
    for call in api_calls:
        body = call["body"]
        results = body.get("results", body) if isinstance(body, dict) else body
        count = len(results) if isinstance(results, list) else "(object)"
        print(f"[{call['method']}] {call['url']}  ->  {call['status']}  ({count} results)")
        if isinstance(results, list) and results and isinstance(results[0], dict):
            print(f"  keys: {list(results[0].keys())}")
            if any("lock" in str(r).lower() for r in results[:5]):
                print("  *** LOCK DATA ***")
                for r in results[:3]:
                    print(f"  {r}")
        elif isinstance(results, dict):
            print(f"  {results}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
