"""Test Understat API endpoint"""
import requests, json

url = 'https://understat.com/getLeagueData/EPL/2025'
headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
r = requests.get(url, headers=headers, timeout=15)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'Keys: {list(data.keys())}')
    teams = data.get('teams', {})
    print(f'Teams: {len(teams)}')
    for tid, t in list(teams.items())[:3]:
        name = t.get('title', '?')
        xG = t.get('xG', '?')
        xGA = t.get('xGA', '?')
        pts = t.get('pts', '?')
        print(f'  {name}: xG={xG}, xGA={xGA}, pts={pts}')
    players = data.get('players', [])
    print(f'Players: {len(players)}')
    if players:
        p = players[0]
        print(f'  Top: {p.get("player_name")} - {p.get("goals")} goals, xG={p.get("xG")}')
else:
    print(r.text[:500])
