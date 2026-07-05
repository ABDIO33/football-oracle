"""Simple Gmail login - step by step"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    
    print("STEP 1: Go to Gmail login...")
    # Try direct Gmail URL which redirects to login
    await page.goto('https://mail.google.com', wait_until='load', timeout=30000)
    await asyncio.sleep(3)
    
    print(f"  URL: {page.url[:80]}")
    
    # Check what's visible
    text = await page.evaluate('() => document.body.innerText')
    print(f"  Text: {text[:300]}")
    
    # Try #identifierId
    has_id = await page.query_selector('#identifierId')
    print(f"  #identifierId exists: {has_id is not None}")
    
    if has_id:
        print("STEP 2: Fill email...")
        await has_id.click()
        await asyncio.sleep(0.3)
        await has_id.fill('elbazamine27@gmail.com')
        await asyncio.sleep(0.5)
        
        print("STEP 3: Click Next...")
        await page.click('#identifierNext')
        await asyncio.sleep(3)
        
        print(f"  URL: {page.url[:80]}")
        
        # Check password page
        pw_inputs = await page.query_selector_all('input[type="password"], input[name="Passwd"], #password, #Passwd')
        print(f"  Password inputs found: {len(pw_inputs)}")
        
        for sel in ['input[type="password"]', 'input[name="Passwd"]', '#password', '#Passwd']:
            el = await page.query_selector(sel)
            if el:
                print(f"  FOUND: {sel}")
                tag = sel
        
        text2 = await page.evaluate('() => document.body.innerText')
        print(f"  Page text: {text2[:400]}")
        
        # If we found password input
        pw_el = await page.query_selector('input[type="password"]')
        if not pw_el:
            pw_el = await page.query_selector('input[name="Passwd"]')
        if not pw_el:
            pw_el = await page.query_selector('input[autocomplete="current-password"]')
        
        if pw_el:
            print("STEP 4: Fill password...")
            await pw_el.click()
            await asyncio.sleep(0.3)
            await pw_el.fill('ABDO1122334455')
            await asyncio.sleep(0.5)
            
            print("STEP 5: Click Next...")
            await page.click('#passwordNext')
            await asyncio.sleep(3)
            
            print(f"  Final URL: {page.url[:80]}")
            
            if 'mail.google.com' in page.url:
                print("  SUCCESS! Logged into Gmail!")
                await page.screenshot(path='C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor/api_keys/gmail_success.png')
                
                # Now search for API keys
                print("\nSTEP 6: Search for API keys...")
                await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
                await asyncio.sleep(2)
                
                # Search 'football-data'
                search_box = await page.query_selector('input[gh="s"], input[aria-label*="Search"], input[aria-label*="search"]')
                if search_box:
                    await search_box.click()
                    await asyncio.sleep(0.3)
                    await search_box.fill('football-data.org')
                    await asyncio.sleep(0.5)
                    await page.keyboard.press('Enter')
                    await asyncio.sleep(3)
                    
                    # Click first result
                    emails = await page.query_selector_all('.zA, tr.zA')
                    print(f"  Found {len(emails)} emails for football-data")
                    
                    if emails:
                        await emails[0].click()
                        await asyncio.sleep(2)
                        
                        body = await page.query_selector('.a3s, .ii')
                        if body:
                            email_text = await body.inner_text()
                            print(f"\n  EMAIL CONTENT:\n{email_text[:1000]}")
                            
                            # Save
                            with open('C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor/api_keys/football_data_email.txt', 'w', encoding='utf-8') as f:
                                f.write(email_text)
                            
                            # Extract key
                            import re
                            keys = re.findall(r'[A-Za-z0-9]{20,45}', email_text)
                            print(f"\n  Possible keys: {keys[:5]}")
            else:
                print(f"  Login result: {await page.evaluate('() => document.body.innerText')[:200]}")
        else:
            print("  Could not find password input!")
    else:
        print("  Could not find email input!")
    
    print("\nDONE!")
    await asyncio.sleep(2)
    await browser.close()
    await pw.stop()

asyncio.run(main())
