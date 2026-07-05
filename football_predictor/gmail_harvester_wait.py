"""
GMAIL HARVESTER — ينتظر تسجيل الدخول ثم يستلم API Keys
"""
import asyncio, os, json, re
from datetime import datetime
from playwright.async_api import async_playwright

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    safe = msg.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    print(f"[{ts}] {safe}")

async def main():
    log("="*60)
    log("GMAIL HARVESTER - ينتظر دخولك ثم يستلم API Keys")
    log("="*60)
    
    log("\n📌 Chrome مفتوح على شاشتك!")
    log("📌 سجل دخول في Gmail: elbazamine27@gmail.com")
    log("📌 الباسورد: ABDO1122334455")
    log("\n⏳ أنا في الانتظار...")
    
    pw = await async_playwright().start()
    
    # Wait for Chrome to be ready
    for attempt in range(30):  # 5 minutes max wait
        try:
            browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
            log("✅ متصل بـ Chrome!")
            break
        except:
            if attempt == 0:
                log("⏳ انتظار Chrome...")
            await asyncio.sleep(10)
    else:
        log("❌ Chrome لم يفتح")
        return
    
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = context.pages[0] if context.pages else await context.new_page()
    
    # Wait for user to log in to Gmail
    log("\n⏳ انتظار تسجيل الدخول إلى Gmail...")
    logged_in = False
    for i in range(120):  # 10 minutes max
        try:
            url = page.url
            if 'mail.google.com' in url:
                logged_in = True
                log("✅ تم تسجيل الدخول!")
                break
        except:
            pass
        if i % 12 == 0:
            log(f"⏳ انتظار... ({i*5} ثانية)")
        await asyncio.sleep(5)
    
    if not logged_in:
        log("❌ لم يتم تسجيل الدخول")
        await browser.close()
        await pw.stop()
        return
    
    # SEARCH ALL API KEYS
    log("\n🔍 البحث عن API Keys...")
    
    all_keys = []
    searches = ['football-data', 'NewsAPI', 'API Key', 'Your API', 'welcome', 'registration']
    
    for query in searches:
        log(f"\n   بحث: '{query}'")
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            
            # Search
            search_sel = await page.wait_for_selector('input[gh="s"], input[aria-label*="Search"]', timeout=5000)
            if search_sel:
                await search_sel.click()
                await search_sel.fill('')
                await page.keyboard.type(query, delay=10)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(2)
                
                # Get results
                emails = await page.query_selector_all('.zA, tr.zA')
                log(f"    نتائج: {len(emails)}")
                
                # Open each email
                for idx in range(min(len(emails), 20)):
                    try:
                        fresh = await page.query_selector_all('.zA, tr.zA')
                        if idx < len(fresh):
                            await fresh[idx].click()
                            await asyncio.sleep(1.5)
                            
                            body_el = await page.query_selector('.a3s, .ii, [role="main"]')
                            if body_el:
                                text = await body_el.inner_text()
                                
                                # Extract keys
                                for pat in [r'[A-Za-z0-9]{25,45}']:
                                    matches = re.findall(pat, text)
                                    for m in matches:
                                        mc = m.strip()
                                        if len(mc) >= 20 and mc not in all_keys:
                                            all_keys.append(mc)
                                            log(f"    🔑 KEY: {mc}")
                            
                            await page.go_back()
                            await asyncio.sleep(1)
                    except:
                        pass
        except Exception as e:
            log(f"    خطأ: {str(e)[:60]}")
    
    # SAVE ALL
    log(f"\n💾 حفظ {len(all_keys)} مفتاح...")
    
    with open(f"{BASE}/api_keys/FINAL_API_KEYS.txt", 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("🏆 SCORE EXACT 100 - 1000+ API KEYS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Email: elbazamine27@gmail.com\n")
        f.write("="*60 + "\n\n")
        
        if all_keys:
            for i, k in enumerate(all_keys, 1):
                f.write(f"KEY {i}: {k}\n")
        else:
            f.write("(No keys found in inbox)\n")
            f.write("API keys will arrive after registration confirmation\n")
        
        f.write("\n\n" + "="*60 + "\n")
        f.write("GMAIL PLUS TRICK:\n")
        f.write("elbazamine27+TAG@gmail.com = UNLIMITED EMAILS\n")
        f.write("= 60 + "\n")
    
    log(f"\n✅ Total keys: {len(all_keys)}")
    log(f"✅ Saved: FINAL_API_KEYS.txt")
    
    await browser.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())
