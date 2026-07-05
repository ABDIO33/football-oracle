"""
FORCE GMAIL LOGIN - click sign in, fill credentials, extract API keys
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

EMAIL = "elbazamine27@gmail.com"
PASSWORD = "ABDO1122334455"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    safe = msg.encode('ascii', 'ignore').decode('ascii')
    print(f"[{ts}] {safe}", flush=True)

async def main():
    log("="*60)
    log("FORCE GMAIL LOGIN - AUTOMATED")
    log("="*60)
    
    pw = await async_playwright().start()
    
    log("[1] Opening Chrome...")
    context = await pw.chromium.launch_persistent_context(
        PROFILE,
        headless=False,
        viewport={'width': 1280, 'height': 720},
        args=['--disable-blink-features=AutomationControlled']
    )
    
    page = context.pages[0]
    
    log("[2] Navigating to Gmail...")
    # Go directly to accounts.google.com signin page
    await page.goto('https://accounts.google.com/v3/signin/identifier?continue=https://mail.google.com/mail/u/0/&service=mail&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                   wait_until='load', timeout=30000)
    await asyncio.sleep(2)
    log(f"    URL: {page.url[:70]}")
    
    # Check what page we're on
    page_text = await page.evaluate('() => document.body.innerText')
    log(f"    Text: {page_text[:200]}")
    
    # Try to find and fill email
    email_input = await page.query_selector('#identifierId')
    if email_input:
        log("[3] Filling email...")
        await email_input.fill(EMAIL)
        await asyncio.sleep(0.3)
        
        next_btn = await page.query_selector('#identifierNext')
        if next_btn:
            await next_btn.click()
            await asyncio.sleep(3)
            log(f"    URL: {page.url[:70]}")
            
            # Check if rejected ("This browser or app may not be secure")
            if 'rejected' in page.url:
                log("="*60)
                log("Google rejected automation!")
                log("Please log in MANUALLY in the Chrome window")
                log("="*60)
            else:
                # Fill password
                pw_input = await page.query_selector('input[type="password"]')
                if pw_input:
                    log("[4] Filling password...")
                    await pw_input.fill(PASSWORD)
                    await asyncio.sleep(0.3)
                    
                    pw_next = await page.query_selector('#passwordNext')
                    if pw_next:
                        await pw_next.click()
                        await asyncio.sleep(3)
                        log(f"    URL: {page.url[:70]}")
    else:
        log("[3] No email input found - checking if already logged in")
    
    # Check if in Gmail
    current_url = page.url
    log(f"\n    Current URL: {current_url[:80]}")
    
    # Wait for manual login if needed
    if 'inbox' not in current_url.lower() and 'mail.google' not in current_url.lower():
        log("\n" + "="*60)
        log("LOG IN TO GMAIL IN THE CHROME WINDOW!")
        log("Email: elbazamine27@gmail.com")
        log("Password: ABDO1122334455")
        log("="*60)
        
        for i in range(180):  # 15 minutes
            try:
                url2 = page.url
                if 'inbox' in url2.lower():
                    log(f"LOGGED IN! URL: {url2[:60]}")
                    break
                search_box = await page.query_selector('input[gh="s"]')
                if search_box:
                    log("In Gmail (search box found)!")
                    break
            except:
                pass
            
            if i % 12 == 0:
                log(f"  Waiting... ({i*5}s)")
            await asyncio.sleep(5)
    
    # EXTRACT API KEYS
    log("\n[5] SEARCHING GMAIL FOR API KEYS...")
    all_keys = []
    
    try:
        with open(REG) as f:
            regs = json.load(f)
        log(f"  {len(regs)} accounts registered")
    except:
        regs = []
    
    for query in ['football-data', 'footballdata', 'newsapi', 'Your API', 'welcome', 'api key']:
        log(f"\n  Searching: '{query}'")
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            
            search_box = await page.query_selector('input[gh="s"]')
            if not search_box:
                search_box = await page.query_selector('[aria-label*="Search"]')
            
            if search_box:
                await search_box.click()
                await search_box.fill('')
                await page.keyboard.type(query, delay=5)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(3)
                
                emails = await page.query_selector_all('.zA')
                log(f"    Found {len(emails)} emails")
                
                for idx in range(min(len(emails), 80)):
                    try:
                        fresh = await page.query_selector_all('.zA')
                        if idx < len(fresh):
                            await fresh[idx].click()
                            await asyncio.sleep(0.8)
                            
                            body_el = await page.query_selector('.a3s, .ii')
                            if body_el:
                                text = await body_el.inner_text()
                                patterns = [
                                    r'Your API Key[:\s]+([A-Za-z0-9_\-]{20,50})',
                                    r'Key[:\s]+([A-Za-z0-9_\-]{20,50})',
                                    r'[A-Za-z0-9]{30,40}',
                                ]
                                for pat in patterns:
                                    for m in re.findall(pat, text, re.IGNORECASE):
                                        mc = m.strip()
                                        if len(mc) >= 20 and mc not in all_keys:
                                            all_keys.append(mc)
                                            log(f"    KEY: {mc[:40]}")
                            
                            await page.go_back()
                            await asyncio.sleep(0.5)
                    except:
                        pass
        except Exception as e:
            log(f"    Error: {str(e)[:50]}")
    
    # SAVE
    log(f"\n[6] SAVING {len(all_keys)} API KEYS...")
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("SCORE EXACT 100 - FINAL API KEYS\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write("="*60 + "\n\n")
        
        if all_keys:
            for i, k in enumerate(all_keys, 1):
                f.write(f"KEY {i}: {k}\n")
        else:
            f.write("(No keys found - check Gmail manually)\n")
        
        f.write(f"\n\nTotal registrations: {len(regs)}\n")
        for r in regs:
            f.write(f"  {r['email']} [{r['service']}] [{r['status']}]\n")
    
    log(f"  File: {OUT}")
    
    log("\n" + "="*60)
    log(f"DONE! {len(all_keys)} keys extracted from {len(regs)} registrations")
    log("="*60)
    
    # Keep Chrome open
    input("\nPress ENTER to close...")
    await context.close()
    await pw.stop()

asyncio.run(main())
