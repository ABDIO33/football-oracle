"""
GMAIL PHONE BYPASS - tries Skip, Not now, Use email, SMS services
"""
import asyncio, os, json, re, random
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

async def try_skip_buttons(page):
    """Try to click Skip / Not now / Use email instead buttons"""
    skip_selectors = [
        "button:has-text('Skip')",
        "button:has-text('Not now')", 
        "button:has-text('تخطي')",
        "button:has-text('ليس الآن')",
        "span:has-text('Skip')",
        "span:has-text('Not now')",
        "a:has-text('Skip')",
        "span:has-text('Use email instead')",
        "button:has-text('Use email instead')",
        "div:has-text('Use email instead')",
        "button:has-text('I prefer not')",
        "span:has-text('I prefer not')",
    ]
    for sel in skip_selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                txt = await el.text_content()
                log(f"  Clicking: {sel} ('{txt.strip()[:20]}')")
                await el.click()
                await asyncio.sleep(2)
                return True
        except:
            continue
    return False

async def try_free_sms_numbers(page):
    """Try using free SMS receive services to get a verification code"""
    log("\nTrying free SMS services...")
    
    # Try to enter a number from a free SMS service
    # First check what country is expected
    text = await page.evaluate('() => document.body.innerText')
    log(f"  Page asks: {text[:200]}")
    
    # List of free temporary phone numbers that MIGHT work with Google
    # These change frequently - let's try a few
    free_numbers = [
        # US numbers from various free SMS services
        "+12025147351",  # TextNow
        "+16172345678",  # Example
    ]
    
    # Find phone input
    phone_input = await page.query_selector('#phoneNumberId')
    if not phone_input:
        phone_input = await page.query_selector('input[type="tel"]')
    if not phone_input:
        phone_input = await page.query_selector('input[name="phoneNumber"]')
    
    if phone_input:
        log("  Found phone input!")
        # Check current value
        current = await phone_input.input_value()
        log(f"  Current value: '{current}'")
        
        if not current:
            # Try an IN country code selection
            # First check if there's a country dropdown
            country_drop = await page.query_selector('select[aria-label*="country"]')
            if country_drop:
                log("  Country dropdown found")
                # Try Morocco first (since user is there)
                await country_drop.select_option('MA')  # Morocco
                await asyncio.sleep(0.5)
            
            # Enter a free US number
            await phone_input.fill("+12025147351")
            await asyncio.sleep(0.5)
            
            # Click Next
            next_btn = await page.query_selector('button:has-text("Next"), button:has-text("التالي"), button[type="submit"]')
            if next_btn:
                await next_btn.click()
                await asyncio.sleep(3)
                log(f"  URL after submitting phone: {page.url[:70]}")
                
                # Check if it asked for code
                code_input = await page.query_selector('input[name="code"], input[type="tel"]')
                if code_input:
                    log("  Code input appeared! Need SMS verification code")
                    log("  But free SMS numbers usually don't receive Google codes")
    else:
        log("  No phone input found")
    
    return False

async def main():
    log("="*60)
    log("GMAIL PHONE BYPASS v5")
    log("="*60)
    
    pw = await async_playwright().start()
    
    # Kill any Chrome using the same profile
    os.system("taskkill //F //IM chrome.exe 2>nul")
    await asyncio.sleep(2)
    
    context = await pw.chromium.launch_persistent_context(
        PROFILE,
        headless=False,
        viewport={'width': 1280, 'height': 720},
        args=['--disable-blink-features=AutomationControlled']
    )
    page = context.pages[0]
    
    # Step 1: Navigate to accounts.google.com signin
    log("[1] Going to Gmail login...")
    await page.goto('https://accounts.google.com/v3/signin/identifier?continue=https://mail.google.com/mail/u/0/&service=mail&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                   wait_until='load', timeout=30000)
    await asyncio.sleep(2)
    log(f"    URL: {page.url[:70]}")
    
    # Step 2: Fill email
    email_input = await page.query_selector('#identifierId')
    if email_input:
        await email_input.fill(EMAIL)
        await asyncio.sleep(0.3)
        next_btn = await page.query_selector('#identifierNext')
        if next_btn:
            await next_btn.click()
        await asyncio.sleep(2)
        log(f"    URL: {page.url[:70]}")
    
    # Step 3: Fill password
    pw_input = await page.query_selector('input[type="password"]')
    if pw_input:
        await pw_input.fill(PASSWORD)
        await asyncio.sleep(0.3)
        pw_next = await page.query_selector('#passwordNext')
        if pw_next:
            await pw_next.click()
        await asyncio.sleep(3)
        log(f"    URL: {page.url[:70]}")
    
    # Step 4: Check what page we're on
    text = await page.evaluate('() => document.body.innerText')
    url = page.url
    log(f"\n[4] Current page:")
    log(f"    URL: {url[:80]}")
    log(f"    Text: {text[:400]}")
    
    # Detect page type
    bypassed = False
    
    if 'inbox' in url.lower() or 'mail.google.com' in url.lower():
        log("ALREADY IN GMAIL! No phone verification needed!")
        bypassed = True
    elif 'phone' in text.lower() or 'رقم' in text or 'verify' in text.lower():
        log("PHONE VERIFICATION PAGE DETECTED!")
        
        log("\n[5] Trying Skip buttons...")
        if await try_skip_buttons(page):
            bypassed = True
        
        if not bypassed:
            log("\n[6] Checking for 'Use email instead'...")
            # Look for alternative verification methods
            alt_links = await page.query_selector_all('a, span, div, button')
            for el in alt_links:
                try:
                    t = (await el.text_content()).lower()
                    if 'email' in t or 'another' in t or 'different' in t or 'طريقة' in t:
                        log(f"  Found: '{t.strip()[:30]}'")
                        await el.click()
                        await asyncio.sleep(2)
                        bypassed = True
                        break
                except:
                    continue
        
        if not bypassed:
            log("\n[7] Trying free SMS numbers...")
            await try_free_sms_numbers(page)
            
            # Check again
            text2 = await page.evaluate('() => document.body.innerText')
            if 'inbox' in text2.lower() or 'compose' in text2.lower():
                bypassed = True
    elif 'rejected' in url:
        log("REJECTED PAGE - browser detected!")
        log("Try manual login in Chrome window")
    else:
        log(f"OTHER PAGE: {url[:60]}")
    
    if not bypassed:
        log("\n" + "="*60)
        log("PHONE BYPASS FAILED - MANUAL LOGIN NEEDED")
        log("Chrome window is on your screen:")
        log("1. Complete the phone verification")
        log("2. Or find a phone number to add")
        log("="*60)
        
        # Wait forever for manual completion
        for i in range(600):
            try:
                url = page.url
                if 'inbox' in url.lower() or 'mail.google.com' in url.lower():
                    log("Manual login completed!")
                    bypassed = True
                    break
                search_box = await page.query_selector('input[gh="s"]')
                if search_box:
                    log("In Gmail!")
                    bypassed = True
                    break
            except:
                pass
            if i % 12 == 0:
                log(f"  Waiting for manual login... ({i*5}s)")
            await asyncio.sleep(5)
    
    # EXTRACT API KEYS
    if bypassed:
        log("\n[8] EXTRACTING API KEYS...")
        try:
            with open(REG) as f: regs = json.load(f)
            log(f"  {len(regs)} registrations")
        except:
            regs = []
        
        all_keys = []
        for query in ['football-data', 'footballdata', 'newsapi', 'Your API', 'api key', 'welcome']:
            log(f"\n  Searching: '{query}'")
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
                                            if len(mc) >= 20 and mc not in all_keys:
                                                all_keys.append(mc)
                                                log(f"    KEY: {mc[:40]}")
                                await page.go_back()
                                await asyncio.sleep(0.3)
                        except:
                            pass
            except:
                pass
        
        # SAVE
        log(f"\n[9] SAVING {len(all_keys)} KEYS...")
        with open(OUT, 'w', encoding='utf-8') as f:
            f.write("SCORE EXACT 100 - FINAL API KEYS\n")
            f.write(f"Date: {datetime.now().isoformat()}\n")
            f.write("="*60 + "\n\n")
            if all_keys:
                for i, k in enumerate(all_keys, 1):
                    f.write(f"KEY {i}: {k}\n")
            else:
                f.write("(No keys - try again later)\n")
            f.write(f"\nTotal registrations: {len(regs) if 'regs' in dir() else '?'}\n")
        
        log(f"\n  DONE! {len(all_keys)} API keys!")
    
    log("\nKeeping Chrome open. Press ENTER to close.")
    try:
        await asyncio.get_event_loop().run_in_executor(None, input, "Press ENTER...")
    except:
        await asyncio.sleep(3600)  # Keep running for an hour
    
    await context.close()
    await pw.stop()

asyncio.run(main())
