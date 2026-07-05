"""
GMAIL LOGIN v4 - handles phone verification + waits forever for user
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

async def extract_keys_from_page(page):
    """Extract API keys from the current Gmail page"""
    keys = []
    for query in ['football-data', 'footballdata', 'newsapi', 'Your API', 'welcome', 'api key']:
        log(f"  Searching: '{query}'")
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            search_box = await page.query_selector('input[gh="s"]') or await page.query_selector('[aria-label*="Search"]')
            if search_box:
                await search_box.click()
                await search_box.fill('')
                await page.keyboard.type(query, delay=3)
                await asyncio.sleep(0.3)
                await page.keyboard.press('Enter')
                await asyncio.sleep(2)
                
                emails = await page.query_selector_all('.zA')
                log(f"    Found {len(emails)} emails")
                
                for idx in range(min(len(emails), 100)):
                    try:
                        fresh = await page.query_selector_all('.zA')
                        if idx < len(fresh):
                            await fresh[idx].click()
                            await asyncio.sleep(0.5)
                            body_el = await page.query_selector('.a3s, .ii')
                            if body_el:
                                text = await body_el.inner_text()
                                for pat in [r'Your API Key[:\s]+([A-Za-z0-9_\-]{20,50})', 
                                           r'Key[:\s]+([A-Za-z0-9_\-]{20,50})',
                                           r'[A-Za-z0-9]{30,40}']:
                                    for m in re.findall(pat, text, re.IGNORECASE):
                                        mc = m.strip()
                                        if len(mc) >= 20 and mc not in keys:
                                            keys.append(mc)
                                            log(f"    KEY: {mc[:40]}")
                            await page.go_back()
                            await asyncio.sleep(0.3)
                    except:
                        pass
        except:
            pass
    return keys

async def main():
    log("="*60)
    log("GMAIL LOGIN v4 - WAITS FOREVER FOR YOU!")
    log("="*60)
    
    pw = await async_playwright().start()
    context = await pw.chromium.launch_persistent_context(
        PROFILE,
        headless=False,
        viewport={'width': 1280, 'height': 720},
        args=['--disable-blink-features=AutomationControlled']
    )
    page = context.pages[0]
    
    log("[1] Navigating to Gmail...")
    await page.goto('https://accounts.google.com/v3/signin/identifier?continue=https://mail.google.com/mail/u/0/&service=mail&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                   wait_until='load', timeout=30000)
    await asyncio.sleep(2)
    log(f"    URL: {page.url[:70]}")
    
    # Try auto-fill email
    email_input = await page.query_selector('#identifierId')
    if email_input:
        log("[2] Filling email...")
        await email_input.fill(EMAIL)
        await asyncio.sleep(0.3)
        next_btn = await page.query_selector('#identifierNext')
        if next_btn:
            await next_btn.click()
            await asyncio.sleep(2)
            
            if 'rejected' not in page.url:
                pw_input = await page.query_selector('input[type="password"]')
                if pw_input:
                    log("[3] Filling password...")
                    await pw_input.fill(PASSWORD)
                    await asyncio.sleep(0.3)
                    pw_next = await page.query_selector('#passwordNext')
                    if pw_next:
                        await pw_next.click()
                        await asyncio.sleep(2)
    
    # Wait for manual login INFINITE LOOP
    log("\n" + "="*60)
    log("CHROME WINDOW IS ON YOUR SCREEN!")
    log("Email: elbazamine27@gmail.com")
    log("Password: ABDO1122334455")
    log("FINISH THE LOGIN AND I WILL EXTRACT KEYS!")
    log("="*60)
    
    wait_count = 0
    while True:
        try:
            url = page.url
            is_in_gmail = ('inbox' in url.lower() and 'mail.google' in url.lower())
            has_search = await page.query_selector('input[gh="s"]') is not None
            
            if is_in_gmail or has_search:
                log(f"GMAIL ACCESSED! URL: {url[:60]}")
                break
        except:
            pass
        
        wait_count += 1
        if wait_count % 12 == 0:
            # Also check bot progress
            try:
                with open(REG) as f:
                    r = json.load(f)
                log(f"  Waiting... ({wait_count*5}s) | Regs: {len(r)}")
            except:
                log(f"  Waiting... ({wait_count*5}s)")
        
        await asyncio.sleep(5)
    
    # EXTRACT KEYS
    log("\n[4] EXTRACTING API KEYS FROM GMAIL...")
    try:
        with open(REG) as f: regs = json.load(f)
        log(f"  {len(regs)} total registrations")
    except:
        regs = []
    
    all_keys = await extract_keys_from_page(page)
    
    # SAVE
    log(f"\n[5] SAVING {len(all_keys)} API KEYS...")
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("SCORE EXACT 100 - FINAL API KEYS\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write("="*60 + "\n\n")
        if all_keys:
            for i, k in enumerate(all_keys, 1):
                f.write(f"KEY {i}: {k}\n")
        else:
            f.write("(No keys in inbox - emails may take time)\n")
        f.write(f"\n\nRegistrations: {len(regs)}\n")
        for r in regs:
            f.write(f"  {r['email']} [{r['service']}] [{r['status']}]\n")
    
    log(f"  DONE! Saved to {OUT}")
    input("\nPress ENTER to close Chrome...")
    await context.close()
    await pw.stop()

asyncio.run(main())
