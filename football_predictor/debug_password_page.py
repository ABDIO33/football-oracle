"""Debug Google password page"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    
    print("[1] Opening Google login...")
    await page.goto('https://accounts.google.com/v3/signin/identifier?service=mail', wait_until='networkidle')
    await asyncio.sleep(2)
    
    print("[2] Entering email: elbazamine27@gmail.com")
    await page.fill('#identifierId', 'elbazamine27@gmail.com')
    await asyncio.sleep(1)
    await page.click('#identifierNext')
    await asyncio.sleep(3)
    
    print(f"    URL now: {page.url[:80]}")
    print(f"    Title: {await page.title()}")
    
    # Check for password input
    pw_inputs = await page.query_selector_all('input')
    print(f"\n[3] Inputs found: {len(pw_inputs)}")
    for inp in pw_inputs:
        info = await inp.evaluate('el => ({type: el.type, name: el.name, id: el.id, class: el.className.slice(0,40)})')
        print(f"    {info}")
    
    # Look for password field specifically
    pw_field = await page.query_selector('input[type="password"]')
    print(f"\n    Password field [type=password]: {pw_field is not None}")
    
    # Try different selectors
    for sel in ['#password', '#Passwd', 'input[name="Passwd"]', 'input[autocomplete="current-password"]',
                '#passwordField', 'input[name="password"]', '#credentials-password']:
        el = await page.query_selector(sel)
        if el:
            print(f"    Found with: {sel}")
    
    # Check all text
    text = await page.evaluate('() => document.body.innerText')
    print(f"\n[4] Page text: {text[:500]}")
    
    await page.screenshot(path='C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor/api_keys/password_page.png')
    print(f"\n[5] Screenshot saved")
    
    await browser.close()
    await pw.stop()

asyncio.run(main())
