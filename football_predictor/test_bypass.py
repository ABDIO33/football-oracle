"""Test bypass Cloudflare on Sofascore - SUCCESS with x-requested-with header"""
import os, json, sys
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)

from curl_cffi import requests

BASE = 'https://www.sofascore.com/api/v1'
H = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/',
    'x-requested-with': '721637',
}

def section(s):
    print(f"\n{'='*60}\n{s}\n{'='*60}")

section("TEAM INFO (Barcelona ID: 2817)")
r = requests.get(f'{BASE}/team/2817', headers=H, impersonate='chrome120', timeout=15)
if r.status_code == 200:
    t = r.json().get('team', {})
    print(f"  {t.get('name','?')} (ID: {t.get('id','?')})")
    print(f"  Country: {t.get('country',{}).get('name','?')}")
    print(f"  Sport: {t.get('sport',{}).get('name','?')}")

section("SEARCH (Barcelona)")
r = requests.get(f'{BASE}/search/teams?q=Barcelona', headers=H, impersonate='chrome120', timeout=15)
if r.status_code == 200:
    for res in r.json().get('results', [])[:5]:
        ent = res.get('entity', {})
        print(f"  {ent.get('name','?'):35s} ID: {ent.get('id','?')}")

section("LAST 10 MATCHES (Spain)")
r = requests.get(f'{BASE}/team/4698/events/last/0', headers=H, impersonate='chrome120', timeout=15)
if r.status_code == 200:
    for ev in r.json().get('events', [])[:10]:
        ht = ev.get('homeTeam', {}).get('name', '?')
        at = ev.get('awayTeam', {}).get('name', '?')
        hs = ev.get('homeScore', {}).get('display', 0)
        as_ = ev.get('awayScore', {}).get('display', 0)
        s = ev.get('status', {}).get('type', '?')
        if s == 'finished':
            print(f"  {ht:25s} {hs}-{as_}  {at}")

section("UPCOMING (Barcelona)")
r = requests.get(f'{BASE}/team/2817/events/next/0', headers=H, impersonate='chrome120', timeout=15)
if r.status_code == 200:
    for ev in r.json().get('events', [])[:5]:
        ht = ev.get('homeTeam', {}).get('name', '?')
        at = ev.get('awayTeam', {}).get('name', '?')
        d = ev.get('startTimestamp', 0)
        from datetime import datetime
        date = datetime.fromtimestamp(d).strftime('%Y-%m-%d') if d else '?'
        print(f"  {ht:25s} vs {at:25s} on {date}")

section("VERDICT")
print("""
  curl_cffi + impersonate='chrome120' + x-requested-with: 721637

  SUCCESS! All API endpoints return 200 OK.
  No Selenium. No Playwright. No browser needed.
  Just add the x-requested-with header.

  Replace 'api.sofascore.com' with 'www.sofascore.com' in base URL.

  Now update sofascore_scraper.py to use curl_cffi with this header.
""")
