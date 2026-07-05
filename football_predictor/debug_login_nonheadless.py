"""Debug Google login - non-headless"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    pw = await async_playwright().start()
    
    # Use real Chrome with anti-detection
    browser = await pw.chromium.launch(
        headless=False,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--window-size=1280,720',
        ],
        slow_mo=50
    )
    
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    )
    
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
    """)
    
    page = await context.new_page()
    
    print("[1] Opening Google login...")
    await page.goto('https://accounts.google.com/v3/signin/identifier?service=mail', wait_until='load', timeout=30000)
    await asyncio.sleep(2)
    
    print(f"    URL: {page.url[:60]}")
    
    # Fill email
    print("[2] Filling email...")
    try:
        await page.wait_for_selector('#identifierId', timeout=10000)
        await page.click('#identifierId')
        await asyncio.sleep(0.5)
        await page.fill('#identifierId', 'elbazamine27@gmail.com')
        await asyncio.sleep(1)
        
        # Click Next
        await page.click('#identifierNext')
        await asyncio.sleep(3)
        
        print(f"    URL now: {page.url[:60]}")
        
        # Take screenshot
        await page.screenshot(path='C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor/api_keys/after_email.png')
        
        # Check for password field
        pw_input = await page.query_selector('input[type="password"]')
        pw_input2 = await page.query_selector('#password')
        pw_input3 = await page.query_selector('input[name="Passwd"]')
        
        print(f"    Password [type=password]: {pw_input is not None}")
        print(f"    Password #password: {pw_input2 is not None}")
        print(f"    Password [name=Passwd]: {pw_input3 is not None}")
        
        # Get page content
        text = await page.evaluate('() => document.body.innerText')
        print(f"\n    Page text: {text[:400]}")
        
    except Exception as e:
        print(f"    Error: {e}")
        await page.screenshot(path='C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor/api_keys/error.png')
    
    print("\n[3] Waiting 30s so you can see the browser...")
    await asyncio.sleep(30)
    
    await browser.close()
    await pw.stop()

asyncio.run(main())
