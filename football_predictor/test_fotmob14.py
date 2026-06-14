"""Full FotMob match data extraction"""
import requests, json, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230',
}

mid = 4813374
r = requests.get(f'https://www.fotmob.com/match/{mid}', headers=headers, timeout=15)
nd = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
data = json.loads(nd.group(1))
pp = data.get('props', {}).get('pageProps', {})

print(f'=== Match {mid} ===')

# 1. General
general = pp.get('general', {})
print(f'\n--- General ---')
print(f'Home: {general.get("homeTeam",{}).get("name","?")}')
print(f'Away: {general.get("awayTeam",{}).get("name","?")}')
print(f'Score: {general.get("homeTeam",{}).get("score","?")} - {general.get("awayTeam",{}).get("score","?")}')
print(f'League: {general.get("league",{}).get("name","?")}')
print(f'Season: {general.get("season",{}).get("name","?")}')
print(f'Round: {general.get("round","?")}')
print(f'Date: {general.get("matchDateUTC","?")}')

# 2. Content (this has lineups, stats, timeline, etc.)
content = pp.get('content', {})
print(f'\n--- Content keys ---')
for k in content:
    v = content[k]
    if isinstance(v, dict):
        print(f'  {k}: dict keys={list(v.keys())[:8]} size={len(json.dumps(v))}')
    elif isinstance(v, list):
        print(f'  {k}: list len={len(v)}')
    else:
        print(f'  {k}: {v}')

# 3. Check for xG data in the match
print(f'\n--- xG search ---')
def find_key(obj, target, depth=0, max_depth=4):
    if depth > max_depth:
        return []
    if isinstance(obj, dict):
        if target in obj:
            return [(depth, obj[target])]
        for k, v in obj.items():
            result = find_key(v, target, depth+1, max_depth)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj[:20]:
            result = find_key(item, target, depth+1, max_depth)
            if result:
                return result
    return []

for term in ['expectedGoals', 'xG', 'xg', 'expected', 'stats']:
    found = find_key(content, term)
    if found:
        print(f'  "{term}" found at depth {found[0][0]}: {str(found[0][1])[:200]}')
    else:
        print(f'  "{term}" not found in content')

# 4. Save full match data
with open('fotmob_match_detail.json', 'w') as f:
    json.dump(pp, f, indent=2)
print(f'\nSaved fotmob_match_detail.json ({len(json.dumps(pp))} bytes)')
