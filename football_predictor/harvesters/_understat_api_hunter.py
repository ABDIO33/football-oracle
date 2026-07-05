#!/usr/bin/env python3
"""
UNDERSTAT API REVERSE ENGINEER + MASS HARVESTER
يستخدم Playwright/SeleniumBase لاعتراض API calls وسحب كل البيانات
All Protocols Active — ENI for LO 🔥
"""

import sys, os, json, time, re, sqlite3
sys.path.insert(0, os.getcwd())

BASE = os.getcwd()
DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

log("=" * 60)
log("UNDERSTAT API REVERSE ENGINEER")
log("=" * 60)

# ─── METHOD 1: Use SeleniumBase to intercept network via logs ─────
def selenium_capture_network(url='https://understat.com/league/EPL/2025'):
    """Load page and extract all network requests from browser logs."""
    from seleniumbase import Driver
    import json
    
    log(f"[SB] Loading {url} with performance logging...")
    
    driver = Driver(
        headless=False, headless2=False, uc=True, locale_code='en-US',
        agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    )
    
    try:
        # Enable performance logging
        log("[SB] Loading page...")
        driver.uc_open_with_reconnect('https://understat.com/', reconnect_time=25)
        time.sleep(2)
        log(f"  Home: {driver.get_title()}")
        
        # Navigate to league page
        log(f"[SB] Navigating to {url}...")
        driver.get(url)
        time.sleep(5)  # Wait for API calls to complete
        
        # Use Selenium to capture what the page loaded
        # Check for JSON data in the page via execute_script
        log("[SB] Searching for data in page...")
        
        # Try to find data via JS execution
        for js_cmd, desc in [
            ("return typeof teamsData !== 'undefined' ? JSON.stringify(Object.keys(teamsData)) : 'NO_TEAMSDATA'", "teamsData"),
            ("return typeof playersData !== 'undefined' ? JSON.stringify(Object.keys(playersData)) : 'NO_PLAYERSDATA'", "playersData"),
            ("return typeof window.__data !== 'undefined' ? 'FOUND' : 'NO_WINDOW_DATA'", "window.__data"),
        ]:
            try:
                result = driver.execute_script(js_cmd)
                log(f"  {desc}: {result}")
            except Exception as e:
                log(f"  {desc}: ERROR - {str(e)[:60]}")
        
        # Try to access the data via document content
        # Some SPA frameworks store data in script tags
        html = driver.get_page_source()
        
        # Write full HTML for analysis
        with open('harvesters/_understat_live.html', 'w', encoding='utf-8') as f:
            f.write(html)
        log(f"[SB] HTML saved: {len(html)} bytes")
        
        # Look for ALL unique URLs in the page
        import re
        urls = set(re.findall(r'https?://[^\"\'<>\\s]+', html))
        log(f"[SB] Found {len(urls)} URLs in page:")
        for u in sorted(urls):
            log(f"  {u}")
        
        return html
        
    finally:
        driver.quit()
        log("[SB] Done")

# ─── METHOD 2: curl_cffi direct API calls ────────────────────────
def try_direct_api(league='EPL', year='2025'):
    """Try all known Understat API patterns."""
    from curl_cffi import requests
    
    endpoints = [
        f'https://understat.com/league/{league}',
        f'https://understat.com/league/{league}/{year}',
        f'https://understat.com/league/{league}?year={year}',
        f'https://understat.com/api/v1/league/{league}',
        f'https://understat.com/api/league/{league}',
        f'https://understat.com/api/getLeague/{league}',
        f'https://understat.com/getLeague/{league}',
        f'https://understat.com/league/data/{league}',
        f'https://understat.com/league/{league}/data',
        f'https://understat.com/data/league/{league}',
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/json,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://understat.com/',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    for ep in endpoints:
        try:
            r = requests.get(ep, impersonate='chrome124', headers=headers, timeout=15)
            log(f"  {r.status_code} {len(r.content):>7}B  {ep}")
            
            if r.status_code == 200 and len(r.content) > 500:
                # Check if it's JSON
                try:
                    data = r.json()
                    log(f"    ✅ JSON! Keys: {list(data.keys())[:10]}")
                    return data
                except:
                    # Check if it contains teamsData
                    if b'teamsData' in r.content or b'playersData' in r.content:
                        log(f"    ✅ Contains teamsData in HTML!")
                        return r.text
        except Exception as e:
            log(f"  ❌ Error: {str(e)[:50]}  {ep}")
    
    return None

# ─── METHOD 3: Playwright network interception ────────────────────
def playwright_intercept_api(url='https://understat.com/league/EPL/2025'):
    """Use Playwright to capture ALL XHR/fetch requests."""
    log("=" * 60)
    log("[PW] Launching Playwright network interceptor...")
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
            )
            
            page = context.new_page()
            
            # Track all API calls
            api_calls = []
            
            def intercept_request(request):
                url = request.url
                if any(x in url for x in ['api', 'data', 'json', 'league', 'understat']):
                    if url.startswith('http') and 'google' not in url and 'facebook' not in url and 'doubleclick' not in url:
                        api_calls.append({
                            'url': url,
                            'method': request.method,
                            'headers': dict(request.headers),
                        })
                        log(f"[PW] INTERCEPTED: {request.method} {url}")
            
            def intercept_response(response):
                url = response.url
                if any(x in url for x in ['api', 'data', 'json', 'league', 'understat']):
                    if url.startswith('http') and 'google' not in url and 'facebook' not in url:
                        try:
                            body = response.body()
                            if len(body) > 100:
                                log(f"[PW] RESPONSE: {url} -> {len(body)} bytes")
                                # Save API response
                                fname = f"understat_api_{re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1])}.json"
                                fpath = os.path.join('harvesters', f'_{fname}')
                                with open(fpath, 'wb') as f:
                                    f.write(body)
                                log(f"  Saved to {fpath}")
                        except:
                            pass
            
            page.on('request', intercept_request)
            page.on('response', intercept_response)
            
            log("[PW] Navigating to Understat...")
            page.goto('https://understat.com/', wait_until='networkidle', timeout=30000)
            time.sleep(3)
            
            log(f"[PW] Home: {page.title()}")
            
            # Now navigate to league
            log(f"[PW] Navigating to {url}...")
            try:
                page.goto(url, wait_until='networkidle', timeout=30000)
            except:
                page.goto(url, wait_until='load', timeout=30000)
            
            time.sleep(5)
            
            log(f"[PW] League page: {page.title()}")
            log(f"[PW] API calls captured: {len(api_calls)}")
            
            for call in api_calls:
                log(f"  {call['method']} {call['url']}")
            
            # Try to get data from page
            for js in [
                "() => typeof teamsData !== 'undefined' ? Object.keys(teamsData) : null",
                "() => typeof playersData !== 'undefined' ? Object.keys(playersData) : null",
                "() => document.querySelector('script[data-data]')?.getAttribute('data-data')",
            ]:
                try:
                    result = page.evaluate(js)
                    if result:
                        log(f"[PW] Data found via JS: {str(result)[:200]}")
                except:
                    pass
            
            browser.close()
            return api_calls
            
    except Exception as e:
        log(f"[PW] ERROR: {str(e)[:200]}")
        return []

# ─── METHOD 4: Selenium with driver.execute_cdp_cmd ──────────────
def selenium_cdp_capture(url='https://understat.com/league/EPL/2025'):
    """Use Chrome DevTools Protocol via SeleniumBase."""
    from seleniumbase import Driver
    
    log("[CDP] Launching with CDP network capture...")
    
    driver = Driver(
        headless=False, headless2=False, uc=True, locale_code='en-US',
    )
    
    api_calls = []
    
    try:
        log("[CDP] Loading Understat home...")
        driver.uc_open_with_reconnect('https://understat.com/', reconnect_time=25)
        time.sleep(2)
        
        # Enable network tracking via CDP
        try:
            driver.execute_cdp_cmd('Network.enable', {})
            log("[CDP] Network tracking enabled")
        except:
            log("[CDP] CDP not available")
        
        log(f"[CDP] Navigating to {url}...")
        driver.get(url)
        time.sleep(5)
        
        # Extract network logs
        try:
            logs = driver.execute_script("""
                var entries = performance.getEntriesByType('resource');
                return JSON.stringify(entries.map(e => ({name: e.name, type: e.initiatorType, size: e.transferSize})));
            """)
            log(f"[CDP] Performance entries: {logs[:500]}")
        except Exception as e:
            log(f"[CDP] Performance API error: {e}")
        
        # Try to extract data via JavaScript
        for cmd in [
            "return typeof teamsData !== 'undefined'",
            "return typeof playersData !== 'undefined'",
            "return typeof window.__INITIAL_STATE__ !== 'undefined'",
            "return document.querySelector('script:last-child')?.textContent?.substring(0, 200) || 'NONE'",
        ]:
            try:
                result = driver.execute_script(cmd)
                log(f"[CDP] {cmd[:60]}: {str(result)[:100]}")
            except:
                pass
        
        # Get all script contents
        scripts = driver.execute_script("""
            var scripts = document.querySelectorAll('script');
            return Array.from(scripts).map(s => s.textContent.substring(0, 1000));
        """)
        log(f"[CDP] Found {len(scripts)} scripts")
        
        for i, s in enumerate(scripts):
            if 'teamsData' in s or 'playersData' in s or 'api' in s.lower() and 'google' not in s:
                log(f"[CDP] Script {i}: {s[:200]}")
                
                # Save relevant script
                with open(f'harvesters/_understat_script_{i}.js', 'w', encoding='utf-8') as f:
                    f.write(s)
        
        # Read the page HTML
        html = driver.get_page_source()
        return html
        
    finally:
        driver.quit()

# ─── MAIN ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', choices=['curl', 'playwright', 'selenium', 'cdp', 'all'], default='all')
    parser.add_argument('--league', default='EPL')
    args = parser.parse_args()
    
    if args.method in ('curl', 'all'):
        log("\n🔥 METHOD 1: Direct curl_cffi API calls 🔥")
        data = try_direct_api(args.league)
        if data:
            log(f"✅ Direct API SUCCESS!")
        else:
            log(f"❌ Direct API failed")
    
    if args.method in ('playwright', 'all'):
        log("\n🔥 METHOD 2: Playwright Network Interception 🔥")
        calls = playwright_intercept_api(f'https://understat.com/league/{args.league}/2025')
        log(f"Total API calls captured: {len(calls)}")
    
    if args.method in ('selenium', 'all'):
        log("\n🔥 METHOD 3: Selenium HTML Analysis 🔥")
        html = selenium_capture_network(f'https://understat.com/league/{args.league}/2025')
    
    if args.method in ('cdp', 'all'):
        log("\n🔥 METHOD 4: Selenium CDP Capture 🔥")
        html = selenium_cdp_capture(f'https://understat.com/league/{args.league}/2025')
    
    log("\n" + "=" * 60)
    log("ALL METHODS COMPLETE")
