"""Check Understat API response content"""
import requests

url = 'https://understat.com/getLeagueData/EPL/2025'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
}
r = requests.get(url, headers=headers, timeout=15)
print(f'Status: {r.status_code}')
print(f'Content-Type: {r.headers.get("Content-Type")}')
print(f'First 200 chars: {r.text[:200]}')
print(f'Last 100 chars: {r.text[-100:]}')

# Try to parse as JSON
import json
try:
    data = json.loads(r.text)
    print(f'\nPARSE OK! Keys: {list(data.keys())}')
    teams = data.get('teams', {})
    print(f'Teams: {len(teams)}')
    for tid, t in list(teams.items())[:2]:
        print(f'  {t.get("title")}: matches={len(t.get("history",[]))}')
    players = data.get('players', [])
    print(f'Players: {len(players)}')
except json.JSONDecodeError as e:
    print(f'\nNot JSON: {e}')
    # Maybe it's HTML with embedded JSON
    import re
    matches = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
    print(f'Script tags: {len(matches)}')
    for i, m in enumerate(matches[:5]):
        if 'teamsData' in m or 'playersData' in m or len(m) > 1000:
            print(f'  Script {i}: {len(m)} bytes, contains teamsData={ "teamsData" in m}')
