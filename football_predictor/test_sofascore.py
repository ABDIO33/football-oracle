"""Test SofaScore API access methods"""
import json, sys, time

# Method 1: cloudscraper
print("=== Method 1: cloudscraper ===")
try:
    import cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    url = 'https://www.sofascore.com/api/v1/unique-tournament/1/season/52162/events/last/0'
    headers = {
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.sofascore.com/',
        'Origin': 'https://www.sofascore.com',
        'x-requested-with': 'XMLHttpRequest'
    }
    resp = scraper.get(url, headers=headers, timeout=20)
    print(f'Status: {resp.status_code}')
    if resp.status_code == 200:
        data = resp.json()
        print(f'Events: {len(data.get("events", []))}')
    else:
        print(f'Body: {resp.text[:300]}')
except Exception as e:
    print(f'Error: {e}')

# Method 2: curl_cffi with newer Chrome impersonation
print("\n=== Method 2: curl_cffi (chrome124) ===")
try:
    from curl_cffi import requests as curl_requests
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'),
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.sofascore.com/',
        'Origin': 'https://www.sofascore.com',
        'x-requested-with': 'XMLHttpRequest'
    }
    resp = curl_requests.get(
        'https://www.sofascore.com/api/v1/unique-tournament/1/season/52162/events/last/0',
        headers=headers,
        impersonate="chrome124",
        timeout=20
    )
    print(f'Status: {resp.status_code}')
    if resp.status_code == 200:
        data = resp.json()
        print(f'Events: {len(data.get("events", []))}')
    else:
        print(f'Body: {resp.text[:300]}')
except Exception as e:
    print(f'Error: {e}')

# Method 3: Try Playwright with stealth
print("\n=== Method 3: Playwright (stealth) ===")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-web-security',
            ]
        )
        context = browser.new_context(
            user_agent=('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/125.0.0.0 Safari/537.36'),
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
        )
        page = context.new_page()
        
        # Override navigator.webdriver
        page.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        ''')
        
        page.goto('https://www.sofascore.com', wait_until='domcontentloaded', timeout=20000)
        time.sleep(4)
        
        result = page.evaluate('''
            async () => {
                try {
                    const resp = await fetch('/api/v1/unique-tournament/1/season/52162/events/last/0', {
                        headers: {'Accept': 'application/json'}
                    });
                    if (!resp.ok) return {error: 'HTTP ' + resp.status};
                    const data = await resp.json();
                    return {events: (data.events || []).length};
                } catch(e) {
                    return {error: e.message};
                }
            }
        ''')
        print(f'Result: {json.dumps(result)}')
        browser.close()
except Exception as e:
    print(f'Error: {e}')

print("\nDone.")
