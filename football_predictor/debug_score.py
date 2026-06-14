"""Debug score format in general data"""
import urllib.request, json, re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230'}
html = urllib.request.urlopen(urllib.request.Request('https://www.fotmob.com/match/4813374', headers=headers), timeout=15).read().decode('utf-8')
nd = json.loads(re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL).group(1))
general = nd['props']['pageProps']['general']

print(f'General keys: {list(general.keys())}')
ht = general.get('homeTeam', {})
at = general.get('awayTeam', {})
print(f'Home team: {ht}')
print(f'Away team: {at}')

# Check for score
print(f'\nhomeTeam score: {ht.get("score")}')
print(f'awayTeam score: {at.get("score")}')
print(f'Status: {general.get("status")}')
print(f'Match date UTC: {general.get("matchDateUTC")}')

# Check xG stats
content = nd['props']['pageProps']['content']
stats = content.get('stats', {})
periods = stats.get('Periods', {})
print('\n=== All stat keys ===')
all_keys = set()
for pn, pd in periods.items():
    for sg in pd.get('stats', []):
        for s in sg.get('stats', []):
            key = s.get('key', '')
            title = s.get('title', '')
            all_keys.add(f'{key} / {title}')
for k in sorted(all_keys):
    print(f'  {k}')
