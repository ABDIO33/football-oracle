"""Debug match status format"""
import urllib.request, json, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230',
}

url = 'https://www.fotmob.com/leagues/47'
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8')
match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
nd = json.loads(match.group(1))
pp = nd.get('props', {}).get('pageProps', {})
matches = pp.get('overview', {}).get('leagueOverviewMatches', [])

# Show status formats for first few matches
print('Match status formats:')
for m in matches[:10]:
    mid = m.get('id')
    home = m.get('home', {}).get('name', '?')
    away = m.get('away', {}).get('name', '?')
    status = m.get('status', {})
    print(f'  {mid} {home} vs {away}:')
    print(f'    status keys={list(status.keys())}')
    print(f'    status={json.dumps(status)[:200]}')
    score_h = m.get('home', {}).get('score')
    score_a = m.get('away', {}).get('score')
    print(f'    score={score_h}-{score_a}')

# Find future/unplayed matches
future = []
for m in matches:
    status = m.get('status', {})
    if not status.get('finished', False) and not status.get('cancelled', False):
        if status.get('utcTime', '') > '2026-06-13':
            future.append(m)

print(f'\nFuture matches (after today): {len(future)}')
for m in future[:5]:
    print(f'  {m["id"]} {m["home"]["name"]} vs {m["away"]["name"]} at {m["status"]["utcTime"]}')

# Check if any match is ongoing
for m in matches:
    status = m.get('status', {})
    if status.get('started', False) and not status.get('finished', False):
        print(f'\nOngoing: {m["home"]["name"]} vs {m["away"]["name"]}')
        break
