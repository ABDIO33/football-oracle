"""
GMAIL HARVESTER - User logs in, I extract keys
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
    log("GMAIL HARVESTER - LOG IN TO EXTRACT API KEYS")
    log("="*60)
    
    pw = await async_playwright().start()
    
    log("[1] Opening Chrome with your profile...")
    context = await pw.chromium.launch_persistent_context(
        PROFILE,
        headless=False,
        viewport={'width': 1280, 'height': 720},
        args=['--disable-blink-features=AutomationControlled'],
        bypass_csp=True
    )
    
    page = context.pages[0]
    
    log("[2] Navigating to Gmail...")
    await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load', timeout=30000)
    await asyncio.sleep(2)
    
    current_url = page.url
    log(f"    URL: {current_url[:70]}")
    
    page_text = await page.evaluate('() => document.body.innerText')
    
    if 'inbox' in current_url.lower():
        log("ALREADY IN GMAIL!")
    else:
        log("="*60)
        log("CHROME IS OPEN ON YOUR SCREEN! LOG IN:")
        log("1. See the Chrome window on your screen")
        log("2. Enter: elbazamine27@gmail.com")
        log("3. Password: ABDO1122334455")
        log("="*60)
        
        for i in range(240):  # 20 minutes
            try:
                current_url = page.url
                if 'inbox' in current_url.lower() or 'mail.google.com' in current_url.lower():
                    log(f"LOGGED IN! URL: {current_url[:60]}")
                    break
                # Also check if search box is visible
                search_box = await page.query_selector('input[gh="s"]')
                if search_box:
                    log("Search box found - logged in!")
                    break
            except:
                pass
            
            if i % 12 == 0:  # every minute
                log(f"  Waiting for login... ({i*5}s)")
            
            await asyncio.sleep(5)
        else:
            log("Login timeout. Keys are saved if any found.")
    
    # EXTRACT API KEYS
    log("\n[3] SEARCHING GMAIL FOR API KEYS...")
    all_keys = []
    
    # Load registrations for reference
    try:
        with open(REG) as f:
            regs = json.load(f)
        log(f"  {len(regs)} accounts registered")
        fd = sum(1 for r in regs if r['service'] == 'football-data.org')
        news = sum(1 for r in regs if r['service'] == 'NewsAPI')
        log(f"  football-data.org: {fd}, NewsAPI: {news}")
    except:
        pass
    
    for query in ['football-data', 'footballdata', 'newsapi', 'Welcome', 'Your API', 'api key']:
        log(f"\n  Searching: '{query}'")
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            
            # Find search box
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
                
                for idx in range(min(len(emails), 60)):
                    try:
                        fresh = await page.query_selector_all('.zA')
                        if idx < len(fresh):
                            await fresh[idx].click()
                            await asyncio.sleep(0.8)
                            
                            body_el = await page.query_selector('.a3s, .ii')
                            if body_el:
                                text = await body_el.inner_text()
                                
                                # Extract keys - multiple patterns
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
        except:
            pass
    
    # SAVE
    log(f"\n[4] SAVING {len(all_keys)} API KEYS...")
    
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("SCORE EXACT 100 - FINAL API KEYS\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write("="*60 + "\n\n")
        
        if all_keys:
            for i, k in enumerate(all_keys, 1):
                f.write(f"KEY {i}: {k}\n")
        else:
            f.write("(No keys found in Gmail inbox)\n")
        
        f.write("\n\n--- ALL REGISTRATIONS ---\n")
        try:
            with open(REG) as regf:
                regs = json.load(regf)
            for r in regs:
                f.write(f"{r['email']} [{r['service']}] [{r['status']}]\n")
        except:
            pass
    
    log(f"  Saved to: {OUT}")
    log(f"  Total registrations: {len(regs) if 'regs' in dir() else '?'}")
    log(f"\n✅ DONE! Keep Chrome open for more results!")
    
    input("\nPress Enter to close Chrome...")
    await context.close()
    await pw.stop()

asyncio.run(main())
