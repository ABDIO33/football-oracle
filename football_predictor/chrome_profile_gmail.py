"""
HARVEST GMAIL COOKIES + API KEYS FROM CHROME PROFILE
"""
import asyncio, os, json, re
from datetime import datetime
from playwright.async_api import async_playwright

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.chdir(BASE)
os.environ['PYTHONIOENCODING'] = 'utf-8'

PROFILE = "C:/Users/zake.exe/AppData/Local/Google/Chrome/User Data/Default"
OUT = f"{BASE}/api_keys/FINAL_API_KEYS.txt"
REG = f"{BASE}/api_keys/ALL_REGISTRATIONS.json"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    safe = msg.encode('ascii', 'ignore').decode('ascii')
    print(f"[{ts}] {safe}", flush=True)

async def main():
    log("="*60)
    log("GMAIL ACCESS VIA CHROME PROFILE COOKIES")
    log(f"Profile: {PROFILE}")
    log("="*60)
    
    pw = await async_playwright().start()
    
    # Launch with the existing Chrome profile
    log("\n[1] Launching Chrome with saved profile...")
    context = await pw.chromium.launch_persistent_context(
        PROFILE,
        headless=False,
        viewport={'width': 1280, 'height': 720},
        args=['--disable-blink-features=AutomationControlled',
              '--no-sandbox'],
        bypass_csp=True
    )
    
    page = context.pages[0] if context.pages else await context.new_page()
    
    log("[2] Going to Gmail...")
    await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load', timeout=30000)
    await asyncio.sleep(3)
    log(f"    URL: {page.url[:60]}")
    
    # Check if logged in
    page_text = await page.evaluate('() => document.body.innerText')
    
    if 'inbox' in page.url.lower() or 'Sign in' not in page_text[:200]:
        log("✅ ALREADY LOGGED INTO GMAIL!")
    elif 'identifier' in page.url or 'signin' in page.url.lower():
        log("⚠️ Google login page - need to enter credentials")
        log("   Trying pre-filled credentials...")
        
        # Check if email is pre-filled
        email_input = await page.query_selector('#identifierId')
        if email_input:
            current_val = await email_input.input_value()
            log(f"   Current value: '{current_val}'")
            if not current_val:
                await email_input.fill('elbazamine27@gmail.com')
                await asyncio.sleep(0.3)
                next_btn = await page.query_selector('#identifierNext')
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(3)
            
            # Now password
            pw_input = await page.query_selector('input[type="password"]')
            if pw_input:
                await pw_input.fill('ABDO1122334455')
                await asyncio.sleep(0.3)
                pw_next = await page.query_selector('#passwordNext')
                if pw_next:
                    await pw_next.click()
                    await asyncio.sleep(3)
        
        # Check again
        if 'inbox' in page.url.lower():
            log("✅ LOGGED IN!")
        else:
            log("❌ Login failed")
            log("   Check Chrome window and log in manually")
            # Give time for manual login
            for i in range(60):
                url = page.url
                if 'inbox' in url.lower():
                    log("✅ Manually logged in!")
                    break
                if i % 10 == 0:
                    log(f"   Waiting for manual login... ({i*5}s)")
                await asyncio.sleep(5)
    
    # Now inside Gmail
    log("\n[3] SEARCHING INBOX FOR API KEYS...")
    all_keys = []
    
    # First save what we already have
    registrations = {}
    try:
        with open(REG) as f:
            regs = json.load(f)
        for r in regs:
            svc = r['service']
            if svc not in registrations:
                registrations[svc] = 0
            registrations[svc] += 1
        log(f"   Known registrations: {len(regs)}")
        for s, c in registrations.items():
            log(f"     {s}: {c}")
    except:
        pass
    
    # Search in Gmail
    for query in ['football-data', 'footballdata', 'newsapi', 'weather', 'Your API', 'API Key']:
        log(f"\n   Searching: '{query}'")
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            
            # Click search box
            search_box = await page.query_selector('input[gh="s"]')
            if not search_box:
                search_box = await page.query_selector('input[aria-label*="Search"]')
            
            if search_box:
                await search_box.click()
                await search_box.fill('')
                await asyncio.sleep(0.2)
                await page.keyboard.type(query, delay=5)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(3)
                
                # Get emails
                emails = await page.query_selector_all('.zA, tr.zA')
                log(f"    Found {len(emails)} emails")
                
                for idx in range(min(len(emails), 50)):
                    try:
                        fresh_emails = await page.query_selector_all('.zA, tr.zA')
                        if idx < len(fresh_emails):
                            await fresh_emails[idx].click()
                            await asyncio.sleep(1)
                            
                            # Get email body
                            body_el = await page.query_selector('.a3s, .ii, [class*="message"]')
                            if body_el:
                                text = await body_el.inner_text()
                                
                                # Extract API keys
                                patterns = [
                                    r'(?:api[_-]?key|key|token|apikey)\s*[=:]\s*["\' ]*([A-Za-z0-9_\-]{20,50})',
                                    r'(?:X-Auth-Token|Authorization)[=:]\s*["\']?([A-Za-z0-9_\-]{20,50})',
                                    r'Your API key[:\s]+([A-Za-z0-9_\-]{20,50})',
                                    r'([A-Za-z0-9]{25,45})',
                                ]
                                for pat in patterns:
                                    matches = re.findall(pat, text, re.IGNORECASE)
                                    for m in matches:
                                        mc = m.strip().strip('"\'').strip()
                                        if len(mc) >= 20 and mc not in all_keys:
                                            all_keys.append(mc)
                                            log(f"    🔑 {mc[:30]}...")
                            
                            await page.go_back()
                            await asyncio.sleep(0.5)
                    except:
                        pass
        except Exception as e:
            log(f"    Error: {str(e)[:40]}")
    
    # SAVE ALL
    log(f"\n[4] SAVING {len(all_keys)} API KEYS...")
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write(f"SCORE EXACT 100 - API KEYS\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write("="*60 + "\n\n")
        
        for i, k in enumerate(all_keys, 1):
            f.write(f"KEY {i}: {k}\n")
        
        f.write(f"\n\nREGISTRATIONS:\n")
        try:
            with open(REG) as regf:
                regs = json.load(regf)
            for r in regs:
                f.write(f"  {r['email']} [{r['service']}] [{r['status']}]\n")
        except:
            pass
    
    log(f"\n✅ DONE! {len(all_keys)} API keys saved!")
    log(f"✅ File: {OUT}")
    
    await context.close()
    await pw.stop()

asyncio.run(main())
