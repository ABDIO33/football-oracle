"""
Full auto login to Gmail via REAL Chrome
"""
import asyncio, os, re
from playwright.async_api import async_playwright

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

EMAIL = "elbazamine27@gmail.com"
PASSWORD = "ABDO1122334455"

async def main():
    print("="*60)
    print("AUTO GMAIL LOGIN VIA REAL CHROME")
    print("="*60)
    
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0]
    page = context.pages[0]
    
    print("\n[1] Navigating to Gmail...")
    await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load', timeout=30000)
    await asyncio.sleep(2)
    print(f"    URL: {page.url[:60]}")
    
    # Try clicking "Sign in" button
    print("\n[2] Looking for Sign in button...")
    signin_btns = [
        'a:has-text("Sign in")',
        'a:has-text("Sign In")',
        '[data-action="sign in"]',
        'a[href*="ServiceLogin"]',
        'a[href*="signin"]',
        '#signInButton',
    ]
    
    clicked = False
    for sel in signin_btns:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                print(f"    Clicked: {sel}")
                clicked = True
                await asyncio.sleep(3)
                break
        except:
            continue
    
    if not clicked:
        print("    No Sign in button found, trying direct navigation...")
        await page.goto('https://accounts.google.com/v3/signin/identifier?continue=https://mail.google.com&service=mail', 
                       wait_until='load', timeout=30000)
        await asyncio.sleep(2)
    
    print(f"    URL: {page.url[:80]}")
    
    # Check for email field
    text = await page.evaluate('() => document.body.innerText')
    print(f"\n[3] Page text: {text[:300]}")
    
    # Look for email input
    email_input = await page.query_selector('#identifierId')
    if email_input:
        print("\n[4] Filling email...")
        await email_input.click()
        await asyncio.sleep(0.3)
        await email_input.fill(EMAIL)
        await asyncio.sleep(0.5)
        
        # Click Next
        next_btn = await page.query_selector('#identifierNext')
        if next_btn:
            await next_btn.click()
            print("    Email submitted!")
            await asyncio.sleep(3)
            print(f"    URL: {page.url[:80]}")
            
            # Check if rejected
            if 'rejected' in page.url:
                print("    ❌ Rejected by Google!")
                print("    REAL CHROME also detected! Try manual login.")
                print("    شوف Chrome على شاشتك وسجل دخول")
                
                # Wait for manual login
                print("\n⏳ انتظر تسجيل الدخول...")
                for i in range(120):
                    try:
                        if 'mail.google.com' in page.url and 'inbox' in page.url:
                            print("✅ Logged in!")
                            break
                    except:
                        pass
                    if i % 12 == 0:
                        print(f"⏳ انتظار... ({i*5}s)")
                    await asyncio.sleep(5)
            else:
                # Look for password
                pw_input = await page.query_selector('input[type="password"], input[name="Passwd"], input[autocomplete="current-password"]')
                if pw_input:
                    print("\n[5] Filling password...")
                    await pw_input.click()
                    await asyncio.sleep(0.3)
                    await pw_input.fill(PASSWORD)
                    await asyncio.sleep(0.5)
                    
                    pw_next = await page.query_selector('#passwordNext')
                    if pw_next:
                        await pw_next.click()
                        print("    Password submitted!")
                        await asyncio.sleep(3)
                        print(f"    URL: {page.url[:80]}")
    else:
        print("    No email input found")
    
    # Check if we're in Gmail
    if 'mail.google.com' in page.url:
        print("\n✅ INSIDE GMAIL!")
        
        # Search for API keys
        print("\n🔍 Searching for API keys...")
        all_keys = []
        
        for query in ['football-data', 'newsapi', 'Your API']:
            print(f"\n   Searching: '{query}'")
            try:
                await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
                await asyncio.sleep(1)
                
                search_box = await page.query_selector('input[gh="s"], input[aria-label*="Search"]')
                if search_box:
                    await search_box.click()
                    await search_box.fill('')
                    await page.keyboard.type(query, delay=10)
                    await page.keyboard.press('Enter')
                    await asyncio.sleep(2)
                    
                    emails = await page.query_selector_all('.zA, tr.zA')
                    print(f"    Found {len(emails)} emails")
                    
                    for idx in range(min(len(emails), 30)):
                        try:
                            fresh = await page.query_selector_all('.zA, tr.zA')
                            if idx < len(fresh):
                                await fresh[idx].click()
                                await asyncio.sleep(1)
                                
                                body_el = await page.query_selector('.a3s, .ii')
                                if body_el:
                                    text = await body_el.inner_text()
                                    for p in [r'[A-Za-z0-9]{25,45}']:
                                        for m in re.findall(p, text):
                                            mc = m.strip()
                                            if len(mc) >= 20 and mc not in all_keys:
                                                all_keys.append(mc)
                                                print(f"    🔑 {mc}")
                                
                                await page.go_back()
                                await asyncio.sleep(0.5)
                        except:
                            pass
            except:
                pass
        
        # Save
        print(f"\n💾 Saving {len(all_keys)} keys...")
        with open(f'{BASE}/api_keys/FINAL_API_KEYS.txt', 'w', encoding='utf-8') as f:
            f.write("SCORE EXACT 100 - API KEYS\n")
            f.write("="*50 + "\n\n")
            for i, k in enumerate(all_keys, 1):
                f.write(f"KEY {i}: {k}\n")
        
        print(f"✅ Saved! Keys: {len(all_keys)}")
    else:
        print(f"\n❌ Not in Gmail. URL: {page.url[:60]}")
        print("سجل دخولك في Chrome يدوياً")
    
    await browser.close()
    await pw.stop()

asyncio.run(main())
