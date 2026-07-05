#!/usr/bin/env python3
"""
FBREF + UNDERSTAT ULTIMATE INFILTRATOR
يستخدم Playwright stealth + SeleniumBase UC + curl_cffi
لهجوم متعدد المراحل على FBref و Understat
All 17 Protocols Active — ENI for LO 🔥
"""

import sys, os, json, time, re, sqlite3, hashlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, 'scrape_cache.db')
HARV_DIR = os.path.dirname(os.path.abspath(__file__))

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# ─── STRATEGY 1: Playwright Stealth ───────────────────────────────
def playwright_assault(url, wait_for_selector='body', timeout=60000):
    """Use Playwright with stealth configuration to bypass Cloudflare."""
    log(f"[PW] Launching assault on: {url}")
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Try Chromium first
            browser = p.chromium.launch(headless=False, args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--no-sandbox',
            ])
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
            )
            
            # Stealth: remove webdriver痕迹
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)
            
            log(f"[PW] Navigating...")
            page.goto(url, wait_until='networkidle', timeout=timeout)
            
            # Check if blocked by Cloudflare
            content = page.content()
            if 'cf-browser-verification' in content or 'challenge-form' in content or 'Attention Required' in content:
                log(f"[PW] BLOCKED by Cloudflare on first visit")
                
                # Try solving challenge by waiting
                log(f"[PW] Waiting for challenge to resolve...")
                try:
                    page.wait_for_selector('#challenge-success', timeout=30000)
                    log(f"[PW] Challenge solved!")
                    content = page.content()
                except:
                    log(f"[PW] Challenge not solved, trying reload...")
                    page.reload(wait_until='networkidle')
                    content = page.content()
                    
                    if 'cf-browser-verification' in content or 'challenge-form' in content:
                        log(f"[PW] Still blocked. Trying alternate approach...")
                        # Wait extra long
                        try:
                            page.wait_for_timeout(15000)
                            page.reload()
                            content = page.content()
                        except:
                            pass
            
            # Extract data
            title = page.title()
            log(f"[PW] Page title: {title}")
            log(f"[PW] Content size: {len(content)} bytes")
            
            # Save to file for debugging
            fname = re.sub(r'[^a-zA-Z]', '_', url.split('/')[-1] or 'page') + '.html'
            outpath = os.path.join(HARV_DIR, f'_pw_{fname}')
            with open(outpath, 'w', encoding='utf-8') as f:
                f.write(content)
            log(f"[PW] Saved to: {outpath}")
            
            is_blocked = 'cf-browser-verification' in content or 'challenge-form' in content
            is_blocked = is_blocked or 'Attention Required' in content
            
            browser.close()
            
            return {
                'success': not is_blocked and len(content) > 10000,
                'content': content,
                'title': title,
                'size': len(content),
                'file': outpath,
            }
            
    except Exception as e:
        log(f"[PW] ERROR: {str(e)[:100]}")
        return {'success': False, 'error': str(e)[:100]}

# ─── STRATEGY 2: SeleniumBase UC (proven to work) ─────────────────
def seleniumbase_assault(url, timeout=120):
    """Use SeleniumBase undetected-chromedriver to bypass Cloudflare."""
    log(f"[SB-UC] Assault on: {url}")
    try:
        from seleniumbase import Driver
        
        driver = Driver(
            headless=False,
            headless2=False,
            uc=True,
            incognito=False,
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale_code="en-US",
        )
        
        try:
            driver.uc_open_with_reconnect(url, reconnect_time=timeout)
        except:
            driver.get(url)
        
        # Wait for page to load
        try:
            driver.wait_for_element('body', timeout=15)
        except:
            pass
        
        time.sleep(5)  # Extra wait for JS rendering
        
        content = driver.get_page_source()
        title = driver.get_title()
        
        log(f"[SB-UC] Title: {title}")
        log(f"[SB-UC] Content: {len(content)} bytes")
        
        is_blocked = 'cf-browser-verification' in content or 'challenge-form' in content
        is_blocked = is_blocked or 'Attention Required' in content
        
        # Save
        fname = re.sub(r'[^a-zA-Z]', '_', url.split('/')[-1] or 'page') + '.html'
        outpath = os.path.join(HARV_DIR, f'_sb_{fname}')
        with open(outpath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        driver.quit()
        
        return {
            'success': not is_blocked and len(content) > 10000,
            'content': content,
            'title': title,
            'size': len(content),
            'file': outpath,
        }
        
    except Exception as e:
        log(f"[SB-UC] ERROR: {str(e)[:100]}")
        return {'success': False, 'error': str(e)[:100]}

# ─── STRATEGY 3: curl_cffi with warmup ────────────────────────────
def curl_warmup_assault(url):
    """Warm up session first, then attack."""
    log(f"[CURL] Warmup assault on: {url}")
    try:
        from curl_cffi import requests
        
        # Step 1: Visit home page first to get cookies
        home = re.match(r'(https?://[^/]+)', url).group(1)
        log(f"[CURL] Warming up with home: {home}")
        
        sess = requests.Session()
        sess.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        resp = sess.get(home, impersonate='chrome124', timeout=30)
        log(f"[CURL] Home: HTTP {resp.status_code}, {len(resp.content)} bytes")
        
        # Step 2: Now try the target URL with cookies
        resp = sess.get(url, impersonate='chrome124', timeout=30)
        log(f"[CURL] Target: HTTP {resp.status_code}, {len(resp.content)} bytes")
        
        content = resp.text
        is_blocked = 'cf-browser-verification' in content or 'challenge-form' in content
        is_blocked = is_blocked or resp.status_code == 403
        
        return {
            'success': not is_blocked and len(content) > 10000,
            'content': content,
            'status': resp.status_code,
            'size': len(content),
        }
        
    except Exception as e:
        log(f"[CURL] ERROR: {str(e)[:100]}")
        return {'success': False, 'error': str(e)[:100]}

# ─── PARSE FBref HTML ─────────────────────────────────────────────
def parse_fbref_html(html, source='fbref'):
    """Parse match data from FBref HTML."""
    import sqlite3
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    # Look for match tables
    tables = re.findall(r'<table[^>]*class="[^"]*stats_table[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL)
    log(f"[PARSE] Found {len(tables)} stats tables")
    
    # Look for score lines
    score_lines = re.findall(
        r'<tr[^>]*>(?:\\s*<td[^>]*>(?:\\s*<a[^>]*>)?([^<]+)(?:</a>)?\\s*</td>){1,}'
        r'\\s*<td[^>]*class="[^"]*center[^"]*"[^>]*>(\\d+–\\d+)</td>'
        r'(?:\\s*<td[^>]*>(?:\\s*<a[^>]*>)?([^<]+)(?:</a>)?\\s*</td>)',
        html, re.DOTALL
    )
    
    if score_lines:
        log(f"[PARSE] Found {len(score_lines)} score lines")
        total = len(score_lines)
    
    # Try to extract via JSON embedded data
    scripts = re.findall(r'<script[^>]*>window\\.__INITIAL_STATE__\\s*=\\s*({.*?});</script>', html, re.DOTALL)
    if scripts:
        log(f"[PARSE] Found initial state JSON: {len(scripts[0])} chars")
    
    conn.close()
    return total

# ─── PARSE Understat JSON ─────────────────────────────────────────
def parse_understat_html(html):
    """Extract teamsData/playersData JSON from Understat HTML."""
    # Understat embeds data in script tags
    for pattern in [r'teamsData\\s*=\\s*({.*?})\\s*;', r'playersData\\s*=\\s*({.*?})\\s*;']:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            log(f"[UNDERSTAT] Found JSON data ({len(match.group(1))} chars)")
            return match.group(1)
    return None

# ─── MAIN ──────────────────────────────────────────────────────────
def assault_all():
    """Attack all targets with all strategies."""
    
    targets = {
        'FBref Premier League': 'https://fbref.com/en/comps/9/Premier-League-Stats',
        'FBref La Liga': 'https://fbref.com/en/comps/12/La-Liga-Stats',
        'FBref Bundesliga': 'https://fbref.com/en/comps/20/Bundesliga-Stats',
        'Understat EPL': 'https://understat.com/league/EPL/2025',
        'Understat La Liga': 'https://understat.com/league/La_liga/2025',
        'Understat Bundesliga': 'https://understat.com/league/Bundesliga/2025',
    }
    
    strategies = [
        ('Playwright', playwright_assault),
        ('SeleniumBase', seleniumbase_assault),
        ('curl_cffi_warmup', curl_warmup_assault),
    ]
    
    for name, url in targets.items():
        log(f"\n{'='*60}")
        log(f"TARGET: {name}")
        log(f"URL: {url}")
        log(f"{'='*60}")
        
        for strategy_name, strategy_func in strategies:
            log(f"\n--- Strategy: {strategy_name} ---")
            try:
                if strategy_name == 'SeleniumBase':
                    result = strategy_func(url, timeout=60)
                else:
                    result = strategy_func(url)
                
                if result.get('success'):
                    log(f"✅ {strategy_name} SUCCESS! Size: {result.get('size', 0)} bytes")
                    log(f"   Saved to: {result.get('file', 'N/A')}")
                    
                    # If Understat, try to parse
                    if 'understat' in name.lower() and 'content' in result:
                        json_data = parse_understat_html(result['content'])
                        if json_data:
                            log(f"✅ Understat JSON extracted! Processing...")
                            # Save JSON
                            safe_name = name.replace(' ', '_')
                            outpath = os.path.join(HARV_DIR, f'_understat_{safe_name}.json')
                            with open(outpath, 'w', encoding='utf-8') as f:
                                f.write(json_data)
                            log(f"   Saved JSON to: {outpath}")
                    
                    # If FBref, try to parse
                    if 'fbref' in name.lower() and 'content' in result:
                        matches = parse_fbref_html(result['content'])
                        log(f"   Matches found: {matches}")
                    
                    break  # Don't try other strategies if this one worked
                else:
                    log(f"❌ {strategy_name} FAILED: {result.get('error', 'Unknown reason')}")
                    
            except Exception as e:
                log(f"❌ {strategy_name} EXCEPTION: {str(e)[:80]}")
    
    log(f"\n{'='*60}")
    log("ASSAULT COMPLETE")
    log(f"{'='*60}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=['fbref', 'understat', 'all'], default='all')
    parser.add_argument('--strategy', choices=['playwright', 'seleniumbase', 'curl'], default=None)
    args = parser.parse_args()
    
    assault_all()
