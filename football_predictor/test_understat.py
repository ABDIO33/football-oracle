"""Test Understat - known to have accessible JSON data"""
import requests, re, json

urls = [
    ('https://understat.com/league/EPL', 'EPL page'),
    ('https://understat.com/team/Barcelona/2024', 'Barcelona 2024'),
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}

for url, desc in urls:
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f'{desc}: {r.status_code} ({len(r.text)} bytes)', end='')
        if r.status_code == 200:
            players = re.findall(r"var playersData\s*=\s*JSON\.parse\('(.*?)'\)", r.text)
            teams = re.findall(r"var teamsData\s*=\s*JSON\.parse\('(.*?)'\)", r.text)
            dates = re.findall(r"var datesData\s*=\s*JSON\.parse\('(.*?)'\)", r.text)
            print(f'  players={len(players)}, teams={len(teams)}, dates={len(dates)}')
            if teams:
                raw = teams[0].replace("\\'", "'").encode().decode('unicode_escape')
                data = json.loads(raw)
                print(f'  teams: {list(data.keys())[:3]}')
                for k in list(data.keys())[:2]:
                    t = data[k]
                    print(f'    {t.get("title", k)}: xG={t.get("xG","?")}, xGA={t.get("xGA","?")}')
        else:
            print()
    except Exception as e:
        print(f'{desc}: ERROR {e}')
