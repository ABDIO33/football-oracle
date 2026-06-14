"""Debug shotmap data"""
import urllib.request, json, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230',
}

html = urllib.request.urlopen(urllib.request.Request('https://www.fotmob.com/match/4813374', headers=headers), timeout=15).read().decode('utf-8')
nd = json.loads(re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL).group(1))
content = nd['props']['pageProps']['content']

shotmap = content.get('shotmap', {})
shots = shotmap.get('shots', [])
print(f'Total shots: {len(shots)}')

# Check first 3 shots
for s in shots[:3]:
    print(f'\nShot: {json.dumps(s, indent=2)[:300]}')

# Check all shot keys
all_keys = set()
for s in shots:
    all_keys.update(s.keys())
print(f'\nAll keys: {all_keys}')

# Count by teamId
team_counts = {}
for s in shots:
    tid = s.get('teamId', s.get('team', {}).get('id', '?'))
    team_counts[tid] = team_counts.get(tid, 0) + 1
print(f'\nShots by teamId: {team_counts}')

# Aggregate xG by teamId
team_xg = {}
for s in shots:
    tid = s.get('teamId', s.get('team', {}).get('id', '?'))
    xg = s.get('expectedGoals', 0)
    team_xg[tid] = team_xg.get(tid, 0) + xg
print(f'xG by teamId: {team_xg}')

# Match info: home and away team IDs
general = nd['props']['pageProps']['general']
print(f'\nHome team id: {general.get("homeTeam",{}).get("id")} ({general.get("homeTeam",{}).get("name")})')
print(f'Away team id: {general.get("awayTeam",{}).get("id")} ({general.get("awayTeam",{}).get("name")})')
