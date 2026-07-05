"""Debug Google login - what's on screen?"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
    )
    context = await browser.new_context(viewport={'width': 1280, 'height': 720})
    page = await context.new_page()
    
    print("[1] Opening Google login...")
    await page.goto('https://accounts.google.com/v3/signin/identifier?service=mail', wait_until='load')
    await asyncio.sleep(5)
    
    print(f"    URL: {page.url}")
    print(f"    Title: {await page.title()}")
    
    # Get ALL page text
    text = await page.evaluate('() => document.body.innerText')
    print(f"\n[2] Page text:\n{text[:1000]}")
    
    # Get form structure
    forms = await page.evaluate('''() => {
        const els = document.querySelectorAll('form, div[role="form"], .form, input, button, [role="button"]');
        return Array.from(els).slice(0,20).map(el => ({
            tag: el.tagName,
            id: el.id,
            class: (el.className || '').slice(0,30),
            role: el.getAttribute('role'),
            type: el.getAttribute('type'),
            name: el.getAttribute('name')
        }));
    }')
    print(f"\n[3] Form elements: {len(forms)}")
    for f in forms[:15]:
        print(f"    {f}")
    
    print("\n[4] Browser is open - check it on your screen!")
    print("    Waiting 60 seconds...")
    await asyncio.sleep(60)
    
    await browser.close()
    await pw.stop()

asyncio.run(main())
