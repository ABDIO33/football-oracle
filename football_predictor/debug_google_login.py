"""Debug Google login page structure"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    
    print("[1] Opening Google login...")
    await page.goto('https://accounts.google.com/ServiceLogin?service=mail', wait_until='networkidle')
    await asyncio.sleep(3)
    
    print(f"    URL: {page.url}")
    print(f"    Title: {await page.title()}")
    
    # Get all input elements
    inputs = await page.query_selector_all('input')
    print(f"\n[2] Found {len(inputs)} inputs:")
    for inp in inputs:
        attrs = await inp.evaluate('el => ({type: el.type, name: el.name, id: el.id, autocomplete: el.autocomplete, placeholder: el.placeholder, aria: el.getAttribute("aria-label")})')
        print(f"    {attrs}")
    
    # Get all visible text
    text = await page.evaluate('() => document.body.innerText')
    print(f"\n[3] Page text preview: {text[:500]}")
    
    # Take screenshot
    await page.screenshot(path='C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor/api_keys/google_login_debug.png')
    print("\n[4] Screenshot saved")
    
    await browser.close()
    await pw.stop()

asyncio.run(main())
