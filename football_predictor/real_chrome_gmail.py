"""
SCORE EXACT 100 — CONNECT TO REAL CHROME
يستخدم Chrome الحقيقي (ليس Playwright) لتجنب كشف Google
"""
import asyncio, os, json, re, time
from datetime import datetime
from playwright.async_api import async_playwright

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

EMAIL = "elbazamine27@gmail.com"
PASSWORD = "ABDO1122334455"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    safe = msg.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    print(f"[{ts}] {safe}")

async def main():
    log("="*60)
    log("SCORE EXACT 100 - CONNECT TO REAL CHROME")
    log("يستخدم Chrome الحقيقي عشان Google ما تمنع")
    log("="*60)
    
    pw = await async_playwright().start()
    
    # Connect to already running Chrome via CDP
    log("\n[1] الاتصال بـ Chrome الحقيقي...")
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    
    # Get all contexts/pages
    contexts = browser.contexts
    log(f"    عدد السياقات: {len(contexts)}")
    
    # Use existing context or create new one
    if contexts:
        context = contexts[0]
    else:
        context = await browser.new_context()
    
    pages = context.pages
    if pages:
        page = pages[0]
    else:
        page = await context.new_page()
    
    # Check current URL
    try:
        url = page.url
        log(f"    الصفحة الحالية: {url[:80]}")
    except:
        pass
    
    # If not on Gmail, go there
    if 'mail.google.com' not in page.url:
        log("\n[2] فتح Gmail...")
        await page.goto('https://mail.google.com', wait_until='load', timeout=30000)
        await asyncio.sleep(2)
        
        current_url = page.url
        log(f"    URL: {current_url[:80]}")
        
        # Check if login is needed
        if 'accounts.google.com' in current_url:
            log("    تحتاج تسجيل دخول...")
            
            # Check if already on login page or need email
            text = await page.evaluate('() => document.body.innerText')
            
            if 'Email or phone' in text or 'identifier' in current_url:
                log("\n[3] كتابة الإيميل...")
                await page.fill('#identifierId', EMAIL)
                await asyncio.sleep(1)
                await page.click('#identifierNext')
                await asyncio.sleep(3)
                
                # Check if password page or blocked
                new_url = page.url
                if 'rejected' in new_url:
                    log("    ❌ Google منع الاتصال!")
                    log("    Chrome الحقيقي لازم يكون مسجل دخول مسبقاً")
                    log("    سجل دخولك يدوياً في Chrome واستمر")
                    await page.screenshot(path=f"{BASE}/api_keys/rejected.png")
                    await asyncio.sleep(60)  # Wait for user
                else:
                    log(f"    URL بعد الإيميل: {new_url[:80]}")
                    
                    # Find password input
                    pw_sel = await page.wait_for_selector(
                        'input[type="password"], input[name="Passwd"], input[autocomplete="current-password"]', 
                        timeout=10000)
                    
                    if pw_sel:
                        log("\n[4] كتابة الباسورد...")
                        await pw_sel.click()
                        await asyncio.sleep(0.3)
                        await pw_sel.fill(PASSWORD)
                        await asyncio.sleep(0.5)
                        
                        await page.click('#passwordNext')
                        await asyncio.sleep(3)
                        
                        log(f"    URL بعد الباسورد: {page.url[:80]}")
                        
                        if 'mail.google.com' in page.url:
                            log("    ✅ نجحنا! داخل Gmail!")
                        else:
                            text2 = await page.evaluate('() => document.body.innerText')
                            log(f"    النتيجة: {text2[:200]}")
    
    # STEP 3: SEARCH FOR API KEYS
    if 'mail.google.com' in page.url:
        log("\n[5] البحث عن API Keys...")
        
        all_keys = []
        searches = ['football-data.org', 'NewsAPI', 'API Key', 'Your API']
        
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
                    await page.keyboard.type(query, delay=15)
                    await page.keyboard.press('Enter')
                    await asyncio.sleep(3)
                    
                    # Get emails
                    emails = await page.query_selector_all('.zA, tr.zA')
                    log(f"    نتائج: {len(emails)}")
                    
                    for i in range(min(len(emails), 3)):
                        try:
                            fresh = await page.query_selector_all('.zA, tr.zA')
                            if i < len(fresh):
                                await fresh[i].click()
                                await asyncio.sleep(2)
                                
                                body_el = await page.query_selector('.a3s, .ii')
                                if body_el:
                                    text = await body_el.inner_text()
                                    log(f"    --- ايميل {i+1} ---")
                                    log(f"    {text[:400]}")
                                    
                                    # Save
                                    sf = query.replace('.','_').replace(' ','_')
                                    with open(f"{BASE}/api_keys/email_{sf}.txt", 'w', encoding='utf-8') as f:
                                        f.write(text)
                                    
                                    # Extract keys
                                    for pat in [r'[A-Za-z0-9]{25,45}', r'(?:Key|Token)[=:]\s*["\']?([A-Za-z0-9_\-]{20,50})']:
                                        matches = re.findall(pat, text)
                                        for m in matches:
                                            mc = m.strip().strip('"\'')
                                            if len(mc) >= 15 and mc not in all_keys:
                                                all_keys.append(mc)
                                                log(f"    🔑 KEY: {mc}")
                                
                                await page.go_back()
                                await asyncio.sleep(1)
                        except Exception as e:
                            log(f"    خطأ: {str(e)[:60]}")
            except Exception as e:
                log(f"    خطأ بحث: {str(e)[:60]}")
        
        # Save all keys
        log(f"\n[6] حفظ المفاتيح...")
        with open(f"{BASE}/api_keys/FINAL_API_KEYS.txt", 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("SCORE EXACT 100 - API KEYS\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("="*60 + "\n\n")
            if all_keys:
                for i, k in enumerate(all_keys, 1):
                    f.write(f"KEY {i}: {k}\n")
            else:
                f.write("(No API keys found)\n")
                f.write("Check Gmail manually: mail.google.com\n")
                f.write("Search for: football-data, NewsAPI\n")
            f.write("\n" + "="*60 + "\n")
            f.write("GMAIL PLUS TRICK: elbazamine27+TAG@gmail.com\n")
            f.write("="*60 + "\n")
        
        log(f"\n✅ Keys: {len(all_keys)}")
        log(f"✅ Saved: {BASE}/api_keys/FINAL_API_KEYS.txt")
    else:
        log("\n❌ لم نستطع الدخول إلى Gmail")
        log("سجل دخولك يدوياً في Chrome إذا أردت")
    
    log("\nDONE!")
    await asyncio.sleep(5)
    await browser.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())
