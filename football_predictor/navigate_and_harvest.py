"""
Navigate Chrome to Gmail and wait for login
"""
import asyncio, os, re
from datetime import datetime
from playwright.async_api import async_playwright

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

async def main():
    print("Connecting to Chrome...")
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    
    context = browser.contexts[0]
    page = context.pages[0]
    
    # Navigate to Gmail
    print("Navigating to Gmail login...")
    await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load', timeout=30000)
    print(f"URL: {page.url[:80]}")
    
    # Check if we need to login
    text = await page.evaluate('() => document.body.innerText')
    print(f"Page text: {text[:300]}")
    
    if 'Sign in' in text or 'signin' in page.url:
        print("\n⚠️ Chrome يظهر شاشة تسجيل الدخول!")
        print("⚠️ سجل دخولك في Chrome الآن!")
        print("⚠️ الباسورد: ABDO1122334455")
        print("\n⏳ في انتظار تسجيل الدخول...")
        
        # Wait for login
        for i in range(120):  # 10 minutes
            try:
                url = page.url
                if 'mail.google.com' in url and 'inbox' in url:
                    print("✅ Gmail مفتوح!")
                    break
                has_search = await page.query_selector('input[gh="s"]')
                if has_search:
                    print("✅ Gmail مفتوح!")
                    break
            except:
                pass
            if i % 12 == 0:
                print(f"⏳ انتظار... ({i*5} ثانية)")
            await asyncio.sleep(5)
        else:
            print("❌ لم يتم تسجيل الدخول")
            return
    
    # We're in Gmail! Search for API keys
    print("\n🔍 البحث عن API Keys...")
    
    all_keys = []
    for query in ['football-data', 'newsapi', 'Your API', 'welcome']:
        print(f"\n   بحث: '{query}'")
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            
            search_box = await page.query_selector('input[gh="s"], input[aria-label*="Search"]')
            if search_box:
                await search_box.click()
                await search_box.fill('')
                await asyncio.sleep(0.2)
                await page.keyboard.type(query, delay=10)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(2)
                
                emails = await page.query_selector_all('.zA, tr.zA')
                print(f"    وجد {len(emails)} ايميل")
                
                for idx in range(min(len(emails), 30)):
                    try:
                        fresh = await page.query_selector_all('.zA, tr.zA')
                        if idx < len(fresh):
                            await fresh[idx].click()
                            await asyncio.sleep(1)
                            
                            body_el = await page.query_selector('.a3s, .ii')
                            if body_el:
                                text = await body_el.inner_text()
                                
                                # Extract keys
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
    print(f"\n💾 حفظ {len(all_keys)} مفتاح...")
    with open(f'{BASE}/api_keys/FINAL_API_KEYS.txt', 'w', encoding='utf-8') as f:
        f.write("SCORE EXACT 100 - API KEYS\n")
        f.write("="*50 + "\n\n")
        if all_keys:
            for i, k in enumerate(all_keys, 1):
                f.write(f"KEY {i}: {k}\n")
        else:
            f.write("(No keys found - check Gmail manually)\n")
    
    print(f"\n✅ Done! Keys: {len(all_keys)}")
    
    await browser.close()
    await pw.stop()

asyncio.run(main())
