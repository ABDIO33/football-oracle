"""Full Understat data test"""
import requests, json

# Test all leagues
leagues = ['EPL', 'La liga', 'Bundesliga', 'Serie A', 'Ligue 1']
for league in leagues:
    url = f'https://understat.com/getLeagueData/{league}/2025'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'}, timeout=15)
    if r.status_code == 200:
        data = r.json()
        teams = data.get('teams', {})
        players = data.get('players', [])
        print(f'{league:12s} {r.status_code}  teams={len(teams)}  players={len(players)}')

# Show one team's full data structure
print('\n=== Sample: Aston Villa matches ===')
url = 'https://understat.com/getLeagueData/EPL/2025'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'}, timeout=15)
data = r.json()
villa = data['teams']['71']  # Aston Villa
print(f'Team: {villa["title"]}')
print(f'xG: {villa.get("xG")}, xGA: {villa.get("xGA")}, npxG: {villa.get("npxG")}')
print(f'PPDA: {villa.get("ppda")}, Deep: {villa.get("deep")}, Pts: {villa.get("pts")}')
print(f'Last 3 matches:')
for m in villa['history'][-3:]:
    opp = ' vs '.join([str(m.get('h_a','?')), str(m.get('xG','?')), str(m.get('xGA','?'))])
    print(f'  h_a={m["h_a"]} xG={m["xG"]:.3f} xGA={m["xGA"]:.3f} result={m.get("result","?")} scored={m.get("scored","?")} missed={m.get("missed","?")}')

# Player data sample
print('\n=== Top 5 Players by xG ===')
sorted_players = sorted(data['players'], key=lambda p: float(p.get('xG',0)), reverse=True)
for p in sorted_players[:5]:
    print(f'  {p["player_name"]:25s} team={p["team_title"]:20s} goals={p.get("goals","?"):>3s} xG={p.get("xG","?"):>6s} xA={p.get("xA","?"):>6s} xG90={p.get("xG90","?"):>6s}')
