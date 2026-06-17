"""
Build STADIUM_DB efficiently - saves periodically, resumes if interrupted
"""
import os, json, time, sqlite3, sys
sys.path.insert(0, os.path.dirname(__file__))
from curl_cffi import requests as curl_requests
import urllib.request, urllib.parse

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
VENUE_FILE = os.path.join(os.path.dirname(__file__), 'stadium_venues.json')
OUTPUT = os.path.join(os.path.dirname(__file__), 'stadium_db.json')

SOFA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36',
    'Accept': 'application/json', 'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/', 'x-requested-with': '721637',
}
NOMINATIM_HEADERS = {'User-Agent': 'ScoreExact100/1.0 (research project)'}

from prediction_engine import TEAM_DB as team_db_dict

# Only top leagues + important teams (reduce from 388 to 150)
PRIORITY_TEAMS = [
    # EPL
    'Manchester City', 'Arsenal', 'Liverpool', 'Chelsea', 'Manchester United',
    'Tottenham Hotspur', 'Newcastle United', 'Aston Villa', 'Brighton & Hove Albion',
    'West Ham United', 'Brentford', 'Crystal Palace', 'Fulham', 'Wolverhampton',
    'Everton', 'Nottingham Forest', 'Bournemouth', 'Leicester City', 'Southampton',
    # La Liga
    'Barcelona', 'Real Madrid', 'Atletico Madrid', 'Athletic Bilbao',
    'Real Sociedad', 'Real Betis', 'Valencia', 'Villarreal', 'Sevilla', 'Girona',
    # Bundesliga
    'Bayern Munich', 'Borussia Dortmund', 'RB Leipzig', 'Bayer Leverkusen',
    'Eintracht Frankfurt', 'VfB Stuttgart', 'Borussia Monchengladbach',
    'VfL Wolfsburg', 'Union Berlin', 'SC Freiburg',
    # Serie A
    'Inter Milan', 'AC Milan', 'Juventus', 'Napoli', 'Atalanta', 'Roma',
    'Lazio', 'Fiorentina', 'Bologna', 'Torino',
    # Ligue 1
    'Paris Saint Germain', 'Marseille', 'Lyon', 'Monaco', 'Lille', 'Nice',
    'Rennes', 'Lens', 'Strasbourg', 'Toulouse',
    # Top others
    'Ajax', 'Feyenoord', 'PSV', 'Benfica', 'Porto', 'Sporting CP',
    'Celtic', 'Rangers', 'Galatasaray', 'Fenerbahce', 'Besiktas',
    'Club Brugge', 'Anderlecht', 'Dinamo Zagreb', 'Slavia Prague',
    'Sparta Prague', 'Olympiacos', 'PAOK', 'Red Bull Salzburg',
    'FC Copenhagen', 'Bodo Glimt', 'Malmo FF',
    # MLS
    'Inter Miami', 'LA Galaxy', 'Los Angeles FC',
    # Brazilian
    'Flamengo', 'Palmeiras', 'Santos', 'Sao Paulo', 'Corinthians',
    # Saudi
    'Al Hilal', 'Al Nassr', 'Al Ittihad',
    # NT (for friendlies)
    'Brazil', 'Argentina', 'England', 'France', 'Spain', 'Germany',
    'Portugal', 'Netherlands', 'Belgium', 'Croatia', 'Italy', 'Denmark',
    'Switzerland', 'Uruguay', 'Colombia', 'Mexico', 'United States',
    'Canada', 'Japan', 'Morocco', 'Senegal', 'Nigeria', 'Egypt',
    'Algeria', 'Ivory Coast', 'Ghana', 'Cameroon', 'Tunisia',
    'South Korea', 'Australia', 'Iran', 'Saudi Arabia', 'Ecuador',
]

all_teams = [t for t in PRIORITY_TEAMS if t in team_db_dict]
print(f'Target: {len(all_teams)} priority teams')

# Step 1: Get stadium names from SofaScore (with resume)
if os.path.exists(VENUE_FILE):
    with open(VENUE_FILE, 'r', encoding='utf-8') as f:
        team_venue = json.load(f)
    done = set(team_venue.keys())
    remaining = [t for t in all_teams if t not in done]
    print(f'Resuming: {len(done)} already done, {len(remaining)} remaining')
else:
    team_venue = {}
    remaining = all_teams
    print('Starting fresh')

for i, team_name in enumerate(remaining):
    try:
        q = team_name.replace(' ', '%20')
        r = curl_requests.get(f'https://www.sofascore.com/api/v1/search/teams?q={q}', headers=SOFA_HEADERS, impersonate='chrome120', timeout=15)
        time.sleep(0.35)
        if r.status_code == 200:
            data = r.json()
            for result in data.get('results', []):
                if result.get('type') != 'team':
                    continue
                ent = result.get('entity', {})
                sofa_name = ent.get('name', '')
                team_id = ent.get('id')
                if not team_id:
                    continue
                time.sleep(0.35)
                rd = curl_requests.get(f'https://www.sofascore.com/api/v1/team/{team_id}', headers=SOFA_HEADERS, impersonate='chrome120', timeout=15)
                if rd.status_code == 200:
                    td = rd.json()
                    ti = td.get('team', {})
                    venue = ti.get('venue') or {}
                    vname = venue.get('name', '')
                    city = (venue.get('city') or {}).get('name', '')
                    if vname:
                        team_venue[team_name] = {
                            'sofascore_name': sofa_name,
                            'team_id': team_id,
                            'venue_name': vname,
                            'city': city,
                        }
                break
    except Exception:
        pass
    
    if (i+1) % 20 == 0 or (i+1) == len(remaining):
        # Save progress
        with open(VENUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(team_venue, f, ensure_ascii=False, indent=2)
        print(f'  Step 1: {i+1}/{len(remaining)} ({len(team_venue)} venues found)')

print(f'Step 1 done: {len(team_venue)} stadiums')

# Step 2: Geocode via Nominatim (with resume, saves every 20)
if os.path.exists(OUTPUT):
    with open(OUTPUT, 'r', encoding='utf-8') as f:
        stadium_db = json.load(f)
    done = set(stadium_db.keys())
    to_geocode = [t for t in team_venue if t not in done]
    print(f'Resuming geocode: {len(done)} already done, {len(to_geocode)} remaining')
else:
    stadium_db = {}
    to_geocode = list(team_venue.keys())
    print(f'Starting geocode: {len(to_geocode)} venues')

geo_errors = 0
for i, team_name in enumerate(to_geocode):
    info = team_venue[team_name]
    query = f'{info["venue_name"]}, {info["city"]}'
    if info.get('city', ''):
        query = f'{info["venue_name"]}, {info["city"]}'
    else:
        query = info['venue_name']
    
    try:
        url = f'https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1'
        req = urllib.request.Request(url, headers=NOMINATIM_HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        time.sleep(1.1)
        
        if data and len(data) > 0:
            stadium_db[team_name] = {
                **info,
                'lat': float(data[0]['lat']),
                'lng': float(data[0]['lon']),
                'nominatim_name': data[0].get('display_name', ''),
            }
        else:
            geo_errors += 1
    except Exception:
        geo_errors += 1
    
    if (i+1) % 20 == 0 or (i+1) == len(to_geocode):
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(stadium_db, f, ensure_ascii=False, indent=2)
        print(f'  Step 2: {i+1}/{len(to_geocode)} ({len(stadium_db)} geocoded, {geo_errors} errors)')

print(f'\nDone! {len(stadium_db)} stadiums geocoded out of {len(team_venue)} venues found')
for team in list(stadium_db.keys())[:10]:
    info = stadium_db[team]
    print(f'  {team}: {info["venue_name"]} ({info["lat"]}, {info["lng"]})')
