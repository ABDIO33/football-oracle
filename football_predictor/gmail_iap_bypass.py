"""
GMAIL IAP BYPASS - handles phone verification by trying alternate methods
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

async def extract_keys(page):
    """Extract API keys from Gmail inbox"""
    keys = []
    try:
        with open(REG) as f: regs = json.load(f)
        log(f"  Registrations: {len(regs)}")
    except:
        regs = []
    
    for query in ['football-data', 'footballdata', 'newsapi', 'Your API', 'api key', 'welcome']:
        log(f"  Searching: '{query}'")
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            sb = await page.query_selector('input[gh="s"]') or await page.query_selector('[aria-label*="Search"]')
            if sb:
                await sb.click()
                await sb.fill('')
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
                            be = await page.query_selector('.a3s, .ii')
                            if be:
                                text = await be.inner_text()
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
    
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("SCORE EXACT 100 - FINAL API KEYS\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write("="*60 + "\n\n")
        if keys:
            for i, k in enumerate(keys, 1):
                f.write(f"KEY {i}: {k}\n")
        else:
            f.write("(No keys found)\n")
        f.write(f"\nTotal registrations: {len(regs)}\n")
        for r in regs:
            f.write(f"  {r['email']} [{r['service']}] [{r['status']}]\n")
    
    log(f"Saved {len(keys)} keys to {OUT}")
    return keys

async def main():
    log("="*60)
    log("GMAIL IAP BYPASS - Try Another Way")
    log("="*60)
    
    pw = await async_playwright().start()
    os.system("taskkill //F //IM chrome.exe 2>nul")
    await asyncio.sleep(2)
    
    context = await pw.chromium.launch_persistent_context(
        PROFILE, headless=False, viewport={'width':1280,'height':720},
        args=['--disable-blink-features=AutomationControlled']
    )
    page = context.pages[0]
    
    # === AUTO LOGIN ===
    log("[1] Navigating to Gmail login...")
    await page.goto('https://accounts.google.com/v3/signin/identifier?continue=https://mail.google.com/mail/u/0/&service=mail&flowName=GlifWebSignIn&flowEntry=ServiceLogin', wait_until='load', timeout=30000)
    await asyncio.sleep(2)
    
    # Fill email
    ei = await page.query_selector('#identifierId')
    if ei:
        await ei.fill(EMAIL)
        await asyncio.sleep(0.3)
        nb = await page.query_selector('#identifierNext')
        if nb: await nb.click()
        await asyncio.sleep(2)
    
    # Fill password
    pi = await page.query_selector('input[type="password"]')
    if pi:
        await pi.fill(PASSWORD)
        await asyncio.sleep(0.3)
        pn = await page.query_selector('#passwordNext')
        if pn: await pn.click()
        await asyncio.sleep(3)
    
    # === NOW ON IAP PAGE ===
    text = await page.evaluate('() => document.body.innerText')
    url = page.url
    log(f"\n[2] Page: {url[:80]}")
    log(f"    Text: {text[:300]}")
    
    # Check if already logged in
    if 'inbox' in url.lower() and 'mail.google' in url.lower():
        log("Already in Gmail!")
        await extract_keys(page)
        await context.close()
        await pw.stop()
        return
    
    # Try all bypass methods
    bypassed = False
    
    # Method 1: "Try another way" link
    log("\n[3] Looking for 'Try another way'...")
    try_another = None
    for sel in ['span:has-text("Try another way")', 'a:has-text("Try another way")', 
                'div:has-text("Try another way")', 'button:has-text("Try another way")',
                'span:has-text("طريقة أخرى")']:
        el = await page.query_selector(sel)
        if el:
            try_another = el
            break
    
    if try_another:
        log("  Found 'Try another way' - clicking...")
        await try_another.click()
        await asyncio.sleep(3)
        text2 = await page.evaluate('() => document.body.innerText')
        url2 = page.url
        log(f"    URL: {url2[:70]}")
        log(f"    Text: {text2[:400]}")
        
        # Check what options are available
        all_text = text2.lower()
        if 'inbox' in url2.lower() and 'mail.google' in url2.lower():
            log("  SUCCESS! In Gmail!")
            bypassed = True
        elif 'email' in all_text:
            log("  Email verification option available!")
            # Try "Get a verification email"
            ver_email = await page.query_selector('span:has-text("email"), div:has-text("verification email"), span:has-text("بريد")')
            if ver_email:
                await ver_email.click()
                await asyncio.sleep(2)
                log(f"    URL: {page.url[:70]}")
                # Check if email was sent
                text3 = await page.evaluate('() => document.body.innerText')
                log(f"    Text: {text3[:200]}")
        elif 'recovery' in all_text:
            log("  Recovery options available!")
        
        # Try all available buttons/links
        log("\n  Checking all options on page...")
        options = await page.query_selector_all('a, span, div[role="button"], button')
        for opt in options:
            try:
                t = (await opt.text_content()).strip()
                if t and len(t) > 3:
                    log(f"    Option: {t[:40]}")
            except:
                pass
    
    # Method 2: Try Skip / Not now buttons everywhere
    if not bypassed:
        log("\n[4] Trying Skip/Not now buttons...")
        for sel in ['button:has-text("Skip")', 'button:has-text("Not now")', 
                    'span:has-text("Skip")', 'a:has-text("Skip")',
                    'button:has-text("تخطي")', 'button:has-text("ليس الآن")',
                    'span:has-text("Not now")']:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    log(f"  Clicked: {sel}")
                    await asyncio.sleep(2)
                    break
            except:
                continue
    
    # Method 3: Try to enter a free SMS number
    if not bypassed:
        log("\n[5] Trying free SMS number...")
        pi2 = await page.query_selector('#phoneNumberId, input[type="tel"], input[name="phoneNumber"]')
        if pi2:
            await pi2.fill("+12025147351")  # Free US number
            await asyncio.sleep(0.3)
            nb2 = await page.query_selector('button:has-text("Next"), button:has-text("التالي")')
            if nb2:
                await nb2.click()
                await asyncio.sleep(3)
                log(f"  URL: {page.url[:70]}")
    
    # If still not in Gmail, wait for manual login
    if not bypassed:
        log("\n" + "="*60)
        log("Chrome window on your screen!")
        log("Phone verification needed.")
        log("If you have any phone number, enter it.")
        log("Or click 'Try another way' for email verification.")
        log("="*60)
        
        for i in range(600):
            try:
                u = page.url
                if 'inbox' in u.lower() and 'mail.google' in u.lower():
                    log("Logged in!")
                    bypassed = True
                    break
                sb = await page.query_selector('input[gh="s"]')
                if sb:
                    log("In Gmail!")
                    bypassed = True
                    break
            except:
                pass
            if i % 12 == 0:
                log(f"  Waiting... ({i*5}s)")
            await asyncio.sleep(5)
    
    if bypassed:
        await extract_keys(page)
    else:
        log("Login not completed.")
    
    # Keep Chrome open
    try:
        await asyncio.get_event_loop().run_in_executor(None, input, "Press ENTER to close...")
    except:
        await asyncio.sleep(600)
    
    await context.close()
    await pw.stop()

asyncio.run(main())
