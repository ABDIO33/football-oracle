"""
FIRE 🔥 — TRANSFERMARKT HEIST RUNNER
python -X utf8 heist_transfermarkt_runner.py
"""
import sys, os, time, json, re
from datetime import datetime
from curl_cffi import requests
from bs4 import BeautifulSoup
import sqlite3

print('🔥🔥🔥 TRANSFERMARKT SQUAD/VALUE/INJURY HEIST 🔥🔥🔥')

# Test connection
test = requests.get('https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1', 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230'},
                    impersonate='chrome120', timeout=15)
print(f'Connection: HTTP {test.status_code} ({len(test.text)} bytes)')
if test.status_code != 200:
    print('FAILED')
    sys.exit(1)

# Top clubs
TM_CLUBS = [
    ('manchester-city', 'GB1', 'Man City'),
    ('manchester-united', 'GB1', 'Man Utd'),
    ('liverpool', 'GB1', 'Liverpool'),
    ('chelsea', 'GB1', 'Chelsea'),
    ('arsenal', 'GB1', 'Arsenal'),
    ('tottenham-hotspur', 'GB1', 'Tottenham'),
    ('newcastle-united', 'GB1', 'Newcastle'),
    ('aston-villa', 'GB1', 'Aston Villa'),
    ('brighton-amp-hove-albion', 'GB1', 'Brighton'),
    ('crystal-palace', 'GB1', 'C Palace'),
    ('everton', 'GB1', 'Everton'),
    ('fulham', 'GB1', 'Fulham'),
    ('brentford', 'GB1', 'Brentford'),
    ('wolverhampton-wanderers', 'GB1', 'Wolves'),
    ('nottingham-forest', 'GB1', 'Nottm Forest'),
    ('afc-bournemouth', 'GB1', 'Bournemouth'),
    ('leicester-city', 'GB1', 'Leicester'),
    ('west-ham-united', 'GB1', 'West Ham'),
    ('real-madrid', 'ES1', 'Real Madrid'),
    ('fc-barcelona', 'ES1', 'Barcelona'),
    ('atletico-madrid', 'ES1', 'Atletico'),
    ('fc-bayern-muenchen', 'L1', 'Bayern'),
    ('borussia-dortmund', 'L1', 'Dortmund'),
    ('bayer-04-leverkusen', 'L1', 'Leverkusen'),
    ('rb-leipzig', 'L1', 'RB Leipzig'),
    ('inter-mailand', 'IT1', 'Inter'),
    ('ac-mailand', 'IT1', 'AC Milan'),
    ('juventus-turin', 'IT1', 'Juve'),
    ('ssc-neapel', 'IT1', 'Napoli'),
    ('as-rom', 'IT1', 'Roma'),
    ('fc-paris-saint-germain', 'FR1', 'PSG'),
    ('olympique-marseille', 'FR1', 'Marseille'),
    ('as-monaco', 'FR1', 'Monaco'),
    ('ajax-amsterdam', 'NL1', 'Ajax'),
    ('psv-eindhoven', 'NL1', 'PSV'),
    ('feyenoord-rotterdam', 'NL1', 'Feyenoord'),
    ('fc-porto', 'PO1', 'Porto'),
    ('sl-benfica', 'PO1', 'Benfica'),
    ('sporting-lissabon', 'PO1', 'Sporting'),
    ('celtic-glasgow', 'SC1', 'Celtic'),
    ('fc-rangers', 'SC1', 'Rangers'),
    ('galatasaray-istanbul', 'TR1', 'Gala'),
    ('fenerbahce-istanbul', 'TR1', 'Fener'),
    ('cr-flamengo', 'BRA1', 'Flamengo'),
    ('se-palmeiras', 'BRA1', 'Palmeiras'),
    ('river-plate', 'ARG1', 'River'),
    ('boca-juniors', 'ARG1', 'Boca'),
    ('cf-america', 'MX1', 'America'),
    ('la-galaxy', 'USA1', 'LA Galaxy'),
    ('inter-miami-cf', 'USA1', 'Inter Miami'),
    ('al-hilal-riadh', 'SA1', 'Al-Hilal'),
    ('al-nassr-riadh', 'SA1', 'Al-Nassr'),
    ('al-ahly-kairo', 'EGY1', 'Al-Ahly'),
    ('mamelodi-sundowns', 'SFR1', 'Sundowns'),
    ('sydney-fc', 'AUS1', 'Sydney FC'),
]

DB_PATH = 'scrape_cache.db'

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent5_heist_clubs (
        id INTEGER PRIMARY KEY, name TEXT, league TEXT, country TEXT,
        league_id TEXT, total_value REAL, squad_size INTEGER,
        avg_age REAL, fetched_at REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent5_heist_squad (
        id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER,
        player_name TEXT, position TEXT, age INTEGER, market_value REAL,
        nationality TEXT, contract_until TEXT, shirt_number INTEGER,
        injury TEXT, injury_until TEXT, profile_url TEXT, fetched_at REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent5_heist_injuries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER,
        player_name TEXT, injury_type TEXT, return_date TEXT,
        games_missed INTEGER, fetched_at REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent5_heist_market_values (
        club_id INTEGER PRIMARY KEY, total_value REAL, avg_value REAL,
        most_valuable_player TEXT, most_valuable_value REAL,
        position_breakdown_json TEXT, value_changes_json TEXT, fetched_at REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent5_heist_transfermarkt_progress (
        task TEXT PRIMARY KEY, status TEXT, total INTEGER,
        completed INTEGER, errors INTEGER, last_fetch REAL)''')
    conn.commit()
    return conn

def tm_fetch(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.transfermarkt.com/',
        'DNT': '1',
    }
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, impersonate='chrome120', timeout=20)
            if r.status_code == 200:
                return r.text
            time.sleep(2)
        except:
            time.sleep(3)
    return None

def parse_value(text):
    if not text: return None
    text = text.strip().replace(',', '.').replace(' ', '')
    # Remove euro sign (various encodings)
    text = text.replace('\\u20ac', '').replace('\\x80', '').replace('\\xe2\\x82\\xac', '')
    text = ''.join(c for c in text if c.isprintable() or c in '.')
    if 'm' in text.lower():
        v = text.lower().replace('mio', '').replace('m', '').strip()
        try: return float(v) * 1_000_000
        except: pass
    if 'k' in text.lower() or 'tsd' in text.lower():
        v = text.lower().replace('tsd', '').replace('k', '').strip()
        try: return float(v) * 1_000
        except: pass
    try: return float(text)
    except: return None

# Main scraping
conn = get_db()
total_players = 0
clubs_done = 0

print(f'\nScraping {len(TM_CLUBS)} clubs...\n')

for slug, comp, name in TM_CLUBS:
    try:
        url = f'https://www.transfermarkt.com/{slug}/startseite/verein/{comp}'
        html = tm_fetch(url)
        if not html:
            print(f'  X {name}: no data')
            continue
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get club ID from URL params
        m = re.search(r'/verein/(\d+)', url)
        club_id = int(m.group(1)) if m else hash(name) % 10_000_000
        
        squad = []
        for table in soup.find_all('table', class_='items'):
            for row in table.find_all('tr', class_=['odd', 'even']):
                player_data = {}
                
                # Name
                name_td = row.find('td', class_='hauptlink')
                if name_td:
                    a = name_td.find('a')
                    player_data['name'] = a.text.strip() if a else name_td.text.strip()
                    player_data['url'] = ('https://www.transfermarkt.com' + a['href']) if a and a.get('href') else ''
                
                # Position
                tds = row.find_all('td')
                if len(tds) >= 2:
                    player_data['position'] = tds[1].text.strip()
                
                # Age
                age_td = row.find('td', class_='zentriert')
                if age_td and age_td.text.strip().isdigit():
                    player_data['age'] = int(age_td.text.strip())
                
                # Market value
                mw_td = row.find('td', class_='rechts')
                if mw_td:
                    player_data['market_value'] = parse_value(mw_td.text.strip())
                
                # Nationality
                flags = row.find_all('img', class_='flaggenrahmen')
                if flags:
                    player_data['nationality'] = ', '.join(f.get('alt', '') for f in flags)
                
                # Contract
                contract_td = row.find_all('td', class_='zentriert')
                if len(contract_td) >= 3:
                    player_data['contract_until'] = contract_td[2].text.strip()
                
                if player_data.get('name'):
                    squad.append(player_data)
        
        if squad:
            conn.execute('INSERT OR REPLACE INTO agent5_heist_clubs VALUES (?,?,?,?,?,?,?,?,?)',
                        (club_id, name, '', '', comp, None, len(squad), None, time.time()))
            
            for p in squad:
                conn.execute('''INSERT INTO agent5_heist_squad 
                    (club_id, player_name, position, age, market_value, nationality, 
                     contract_until, shirt_number, injury, injury_until, profile_url, fetched_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (club_id, p.get('name',''), p.get('position',''), p.get('age'),
                     p.get('market_value'), p.get('nationality',''), p.get('contract_until',''),
                     None, '', '', p.get('url',''), time.time()))
            
            conn.commit()
            total_players += len(squad)
            clubs_done += 1
            print(f'  + {name:15s} => {len(squad):3d} players')
        else:
            print(f'  ? {name}: 0 players')
        
        time.sleep(0.3 + hash(slug) % 4 * 0.1)
    except Exception as e:
        print(f'  X {name}: {str(e)[:60]}')

conn.close()

# Summary
print(f'\n{"="*50}')
print(f'TRANSFERMARKT HEIST COMPLETE')
print(f'  Clubs: {clubs_done}/{len(TM_CLUBS)}')
print(f'  Players: {total_players}')
print(f'  Time: {datetime.now().isoformat()}')

# Save report
os.makedirs('heist_output/transfermarkt', exist_ok=True)
with open('heist_output/transfermarkt/heist_report.json', 'w') as f:
    json.dump({
        'source': 'transfermarkt',
        'clubs_scraped': clubs_done,
        'total_players': total_players,
        'completed_at': datetime.now().isoformat(),
    }, f, indent=2)
print('Report saved.')
