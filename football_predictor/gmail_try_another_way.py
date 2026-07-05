"""
GMAIL PHONE BYPASS - click Try another way and find email option
"""
import asyncio, os, json
from datetime import datetime
from playwright.async_api import async_playwright

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.chdir(BASE)
os.environ['PYTHONIOENCODING'] = 'utf-8'
PROFILE = "C:/Users/zake.exe/AppData/Local/Google/Chrome/User Data/Default"
EMAIL = "elbazamine27@gmail.com"
PASSWORD = "ABDO1122334455"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    safe = msg.encode('ascii', 'ignore').decode('ascii')
    print(f"[{ts}] {safe}", flush=True)

async def main():
    log("="*60)
    log("GMAIL BYPASS - TRY ANOTHER WAY")
    log("="*60)
    
    pw = await async_playwright().start()
    os.system("taskkill //F //IM chrome.exe 2>nul")
    await asyncio.sleep(2)
    
    context = await pw.chromium.launch_persistent_context(
        PROFILE, headless=False, viewport={'width':1280,'height':720},
        args=['--disable-blink-features=AutomationControlled']
    )
    page = context.pages[0]
    
    # Auto login
    log("[1] Login...")
    await page.goto('https://accounts.google.com/v3/signin/identifier?continue=https://mail.google.com/mail/u/0/&service=mail', wait_until='load')
    await asyncio.sleep(2)
    
    ei = await page.query_selector('#identifierId')
    if ei:
        await ei.fill(EMAIL)
        await asyncio.sleep(0.3)
        nb = await page.query_selector('#identifierNext')
        if nb: await nb.click()
        await asyncio.sleep(3)
        log(f"    Email submitted: {page.url[:60]}")
    
    pi = await page.query_selector('input[type="password"]')
    if pi:
        await pi.fill(PASSWORD)
        await asyncio.sleep(0.3)
        pn = await page.query_selector('#passwordNext')
        if pn: await pn.click()
        await asyncio.sleep(3)
        log(f"    Password submitted: {page.url[:60]}")
    
    # Current page
    url = page.url
    text = await page.evaluate('() => document.body.innerText')
    log(f"\n[2] Current: {url[:70]}")
    log(f"    {text[:300]}")
    
    if 'inbox' in url.lower() and 'mail.google' in url.lower():
        log("Already in Gmail!")
        return
    
    # Try Another Way
    log("\n[3] Looking for 'Try another way'...")
    for sel in [
        'span:has-text("Try another way")', 
        'div:has-text("Try another way")',
        'button:has-text("Try another way")',
        'a:has-text("Try another way")',
    ]:
        el = await page.query_selector(sel)
        if el:
            log(f"  Found! Clicking: {sel}")
            await el.click()
            await asyncio.sleep(3)
            break
    
    url2 = page.url
    text2 = await page.evaluate('() => document.body.innerText')
    log(f"\n[4] After click: {url2[:70]}")
    log(f"    {text2[:500]}")
    
    # Check for options
    if 'inbox' in url2.lower():
        log("INBOX ACCESSED!")
        return
    
    # List all clickable elements
    log("\n[5] All clickable options on page:")
    options = await page.query_selector_all('div[role="button"], span, a, button')
    seen = set()
    for opt in options:
        try:
            t = (await opt.text_content()).strip()
            if t and len(t) > 2 and t not in seen:
                seen.add(t)
                log(f"    [{t[:50]}]")
        except:
            pass
    
    # Look for email verification
    log("\n[6] Looking for email verification option...")
    email_opts = []
    for opt in options:
        try:
            t = await opt.text_content()
            tl = t.lower()
            if 'email' in tl or 'mail' in tl or 'بريد' in tl or 'another' in tl or 'different' in tl:
                email_opts.append(t.strip()[:50])
        except:
            pass
    
    if email_opts:
        log("  Email-related options:")
        for e in email_opts:
            log(f"    {e}")
    else:
        log("  No email options found")
    
    # Try all options systematically
    log("\n[7] Trying each option...")
    seen2 = set()
    for opt in options:
        try:
            t = (await opt.text_content()).strip()
            if t and len(t) > 5 and t not in seen2:
                seen2.add(t)
                log(f"  Clicking: {t[:40]}")
                await opt.click()
                await asyncio.sleep(2)
                u3 = page.url
                t3 = await page.evaluate('() => document.body.innerText')
                log(f"    URL: {u3[:60]}")
                if 'inbox' in u3.lower() and 'mail.google' in u3.lower():
                    log("*** INBOX! ***")
                    return
                if 'email' in t3.lower()[:100]:
                    log("    Email verification offered!")
                log(f"    {t3[:150]}")
        except:
            pass
    
    log("\n=== Manual login needed ===")
    log("Chrome is open. Try to verify via email or other method.")
    log("If not possible, just close Chrome.")
    
    for i in range(300):
        try:
            u = page.url
            if 'inbox' in u.lower() and 'mail.google' in u.lower():
                log("Logged in!")
                return
        except:
            pass
        if i % 12 == 0:
            log(f"  Waiting... ({i*5}s)")
        await asyncio.sleep(5)
    
    await context.close()
    await pw.stop()

asyncio.run(main())
