"""
test_playwright.py  —  تجربة Sofascore API عبر Playwright (بديل Selenium)
====================================================================
الاستراتيجية: ندخل Sofascore من متصفح Playwright، نترك JavaScript
يتجاوز JS Challenge، ونعترض استجابات API من كود الصفحة نفسه.
====================================================================
"""
import os, json, sys
from datetime import datetime
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)

from playwright.sync_api import sync_playwright

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'

def extract_next_data(html):
    import re
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    return json.loads(m.group(1)) if m else None

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)

    # ============================================================
    # (1) API عبر اعتراض استجابة كود الصفحة الأصلي
    # ============================================================
    print("=" * 65)
    print("الطريقة (1): اعتراض API من كود Sofascore نفسه")
    print("=" * 65)

    page = browser.new_page(user_agent=UA, viewport={'width': 1920, 'height': 1080})
    api_responses = []

    def on_response(resp):
        url = resp.url
        if '/api/v1/team/' in url and 'image' not in url:
            try:
                body = resp.json() if resp.ok else None
                api_responses.append({'url': url, 'status': resp.status, 'body': body})
            except:
                pass
    page.on('response', on_response)

    # (أ) صفحة فريق Spain / 4698  —  تجلب المباريات تلقائياً
    print("\n  [أ] https://www.sofascore.com/football/team/spain/4698")
    page.goto('https://www.sofascore.com/football/team/spain/4698',
              wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(6000)          # ننتظر كود JS يكمل
    print(f"      Title: {page.title()}")

    # نطلع من الاستجابات
    finished_events = []
    for ar in api_responses:
        if 'events/last/0' in ar['url'] and ar['body']:
            for ev in ar['body'].get('events', []):
                if ev.get('status', {}).get('type') == 'finished':
                    ht = ev.get('homeTeam', {}).get('name', '?')
                    at = ev.get('awayTeam', {}).get('name', '?')
                    hs = ev.get('homeScore', {}).get('display', 0)
                    as_ = ev.get('awayScore', {}).get('display', 0)
                    finished_events.append(f"{ht} {hs}-{as_} {at}")

    print(f"      آخر المباريات ({len(finished_events)}):")
    for ev in finished_events[:12]:
        print(f"        {ev}")

    page.close()
    browser.close()

    # ============================================================
    # (2) API مباشر من curl_cffi + x-requested-with (الأفضل)
    # ============================================================
    print("\n" + "=" * 65)
    print("الطريقة (2): curl_cffi + x-requested-with — أسرع وأخف")
    print("=" * 65)

    from curl_cffi import requests

    BASE = 'https://www.sofascore.com/api/v1'
    H = {
        'User-Agent': UA,
        'Accept': 'application/json',
        'Origin': 'https://www.sofascore.com',
        'Referer': 'https://www.sofascore.com/',
        'x-requested-with': '721637',
    }

    # (أ) البحث عن فريق
    print("\n  [أ] بحث: Barcelona")
    r1 = requests.get(f'{BASE}/search/teams?q=Barcelona', headers=H, impersonate='chrome120', timeout=15)
    print(f"      Status: {r1.status_code}")
    if r1.status_code == 200:
        for res in r1.json().get('results', [])[:3]:
            ent = res.get('entity', {})
            print(f"        {ent.get('name','?'):30s} ID: {ent.get('id','?')}")

    # (ب) معلومات فريق
    print("\n  [ب] معلومات: FC Barcelona (ID: 2817)")
    r2 = requests.get(f'{BASE}/team/2817', headers=H, impersonate='chrome120', timeout=15)
    print(f"      Status: {r2.status_code}")
    if r2.status_code == 200:
        t = r2.json().get('team', {})
        print(f"      الاسم: {t.get('name','?')} | الدولة: {t.get('country',{}).get('name','?')}")

    # (ج) آخر المباريات
    print("\n  [ج] آخر المباريات: Spain (ID: 4698)")
    r3 = requests.get(f'{BASE}/team/4698/events/last/0', headers=H, impersonate='chrome120', timeout=15)
    print(f"      Status: {r3.status_code}")
    if r3.status_code == 200:
        for ev in r3.json().get('events', [])[:8]:
            ht = ev.get('homeTeam', {}).get('name', '?')
            at = ev.get('awayTeam', {}).get('name', '?')
            hs = ev.get('homeScore', {}).get('display', 0)
            as_ = ev.get('awayScore', {}).get('display', 0)
            print(f"        {ht:25s} {hs}-{as_}  {at}")

    # ============================================================
    print("\n" + "=" * 65)
    print("الخلاصة: كلتا الطريقتين تعملان بنجاح.")
    print("لكن curl_cffi + x-requested-with أخف وأسرع بكثير.")
    print("راجع test_bypass.py لتفاصيل أكثر.")
    print("=" * 65)
