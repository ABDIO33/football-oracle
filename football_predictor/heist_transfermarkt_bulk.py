#!/usr/bin/env python3
"""
████████╗██████╗  █████╗ ███╗   ██╗███████╗███████╗███████╗██████╗ ███╗   ███╗ █████╗ ██████╗ ██╗  ██╗████████╗
╚══██╔══╝██╔══██╗██╔══██╗████╗  ██║██╔════╝██╔════╝██╔════╝██╔══██╗████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝╚══██╔══╝
   ██║   ██████╔╝███████║██╔██╗ ██║███████╗█████╗  █████╗  ██████╔╝██╔████╔██║███████║██████╔╝█████╔╝    ██║   
   ██║   ██╔══██╗██╔══██║██║╚██╗██║╚════██║██╔══╝  ██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗    ██║   
   ██║   ██║  ██║██║  ██║██║ ╚████║███████║██║     ███████╗██║  ██║██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗   ██║   
   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   

Transfermarkt BULK HEIST — curl_cffi Impersonation Exploit
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE
"""

import os, json, re, time, sqlite3, hashlib, random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Any
from curl_cffi import requests
from bs4 import BeautifulSoup

# ── CONFIG ──────────────────────────────────────────────────────────────
HEIST_DIR = os.path.join(os.path.dirname(__file__), 'heist_output')
os.makedirs(HEIST_DIR, exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
PROXY_LIST = []  # Optional: add proxies here for rotation

UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.6099.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Chrome/120.0.6099.230 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
]

# ── Transfermarkt League/Competition IDs ────────────────────────────────
# Format: {league_name: (country_code, competition_id)}
TM_COMPETITIONS = {
    'Premier League': ('GB1', 'GB1'),
    'LaLiga': ('ES1', 'ES1'),
    'Bundesliga': ('L1', 'L1'),
    'Serie A': ('IT1', 'IT1'),
    'Ligue 1': ('FR1', 'FR1'),
    'Championship': ('GB2', 'GB2'),
    '2. Bundesliga': ('L2', 'L2'),
    'Serie B': ('IT2', 'IT2'),
    'LaLiga2': ('ES2', 'ES2'),
    'Ligue 2': ('FR2', 'FR2'),
    'Eredivisie': ('NL1', 'NL1'),
    'Primeira Liga': ('PO1', 'PO1'),
    'Scottish Premiership': ('SCO1', 'SC1'),
    'Süper Lig': ('TR1', 'TR1'),
    'Jupiler Pro League': ('BE1', 'BE1'),
    'Russian Premier League': ('RU1', 'RU1'),
    'Premier League (UKR)': ('UA1', 'UA1'),
    'Super League (GRE)': ('GR1', 'GR1'),
    'Czech First League': ('CS1', 'CS1'),
    'Ekstraklasa': ('POL1', 'POL1'),
    'Swiss Super League': ('SZ1', 'SZ1'),
    'Allsvenskan': ('SE1', 'SE1'),
    'Eliteserien': ('NO1', 'NO1'),
    'Superliga (DEN)': ('DK1', 'DK1'),
    'MLS': ('USA1', 'USA1'),
    'Liga MX': ('MX1', 'MX1'),
    'Brasileirão Série A': ('BRA1', 'BRA1'),
    'Argentine Primera': ('ARG1', 'ARG1'),
    'J1 League': ('JP1', 'JP1'),
    'K League 1': ('KR1', 'KR1'),
    'Chinese Super League': ('CN1', 'CN1'),
    'Saudi Pro League': ('SA1', 'SA1'),
    'A-League': ('AUS1', 'AUS1'),
    'Primera División (CHI)': ('CL1', 'CL1'),
    'Liga 1 (PER)': ('PE1', 'PE1'),
    'Primera División (COL)': ('CO1', 'CO1'),
    'Campeonato Uruguayo': ('UY1', 'UY1'),
    'Serie A (ECU)': ('EC1', 'EC1'),
    'Primera División (PAR)': ('PY1', 'PY1'),
    'Primera División (BOL)': ('BO1', 'BO1'),
    'Primera División (VEN)': ('VE1', 'VE1'),
    'Premier League (AUT)': ('AUT1', 'AUT1'),
    'Super League (HUN)': ('UNG1', 'UNG1'),
    'Liga I (ROM)': ('ROM1', 'ROM1'),
    'Croatian HNL': ('KRO1', 'KRO1'),
    'Super Liga (SRB)': ('SRB1', 'SRB1'),
    'PrvaLiga (SVN)': ('SVN1', 'SVN1'),
    'Super League (BUL)': ('BUL1', 'BUL1'),
    'Fortuna Liga (SVK)': ('SLK1', 'SLK1'),
    'Israeli Premier League': ('ISR1', 'ISR1'),
    'Botola Pro': ('MAR1', 'MAR1'),
    'Egyptian Premier League': ('EGY1', 'EGY1'),
    'PSL (RSA)': ('SFR1', 'SFR1'),
    'Ghana Premier League': ('GHA1', 'GHA1'),
    'NPFL (NGA)': ('NGA1', 'NGA1'),
    'Thai League 1': ('THA1', 'THA1'),
    'V-League (VIE)': ('VIE1', 'VIE1'),
    'Indian Super League': ('IND1', 'IND1'),
    'Iran Pro League': ('IRN1', 'IRN1'),
    'UAE Pro League': ('VAE1', 'VAE1'),
    'Qatar Stars League': ('QAT1', 'QAT1'),
    'UEFA Champions League': ('CL', 'CL'),
    'UEFA Europa League': ('EL', 'EL'),
    'UEFA Conference League': ('ECL', 'ECL'),
}

# Top 500 clubs on Transfermarkt (by market value / popularity)
# Format: {club_name: (url_slug, competition_id)}
TM_CLUBS = {
    'Manchester City': ('manchester-city', 'GB1'),
    'Manchester United': ('manchester-united', 'GB1'),
    'Liverpool': ('liverpool', 'GB1'),
    'Chelsea': ('chelsea', 'GB1'),
    'Arsenal': ('arsenal', 'GB1'),
    'Tottenham': ('tottenham-hotspur', 'GB1'),
    'Newcastle United': ('newcastle-united', 'GB1'),
    'Aston Villa': ('aston-villa', 'GB1'),
    'West Ham United': ('west-ham-united', 'GB1'),
    'Brighton': ('brighton-amp-hove-albion', 'GB1'),
    'Crystal Palace': ('crystal-palace', 'GB1'),
    'Everton': ('everton', 'GB1'),
    'Fulham': ('fulham', 'GB1'),
    'Brentford': ('brentford', 'GB1'),
    'Wolverhampton': ('wolverhampton-wanderers', 'GB1'),
    'Nottingham Forest': ('nottingham-forest', 'GB1'),
    'Bournemouth': ('afc-bournemouth', 'GB1'),
    'Leicester City': ('leicester-city', 'GB1'),
    'Leeds United': ('leeds-united', 'GB1'),
    'Southampton': ('southampton', 'GB1'),
    'Ipswich Town': ('ipswich-town', 'GB1'),
    'Real Madrid': ('real-madrid', 'ES1'),
    'Barcelona': ('fc-barcelona', 'ES1'),
    'Atlético Madrid': ('atletico-madrid', 'ES1'),
    'Real Sociedad': ('real-sociedad', 'ES1'),
    'Athletic Bilbao': ('athletic-bilbao', 'ES1'),
    'Valencia': ('fc-valencia', 'ES1'),
    'Villarreal': ('villareal', 'ES1'),
    'Real Betis': ('real-betis-sevilla', 'ES1'),
    'Sevilla': ('fc-sevilla', 'ES1'),
    'Getafe': ('getafe-cf', 'ES1'),
    'Osasuna': ('ca-osasuna', 'ES1'),
    'Celta Vigo': ('rc-celta-vigo', 'ES1'),
    'Girona': ('fc-girona', 'ES1'),
    'Mallorca': ('rcd-mallorca', 'ES1'),
    'Rayo Vallecano': ('rayo-vallecano', 'ES1'),
    'Alavés': ('deportivo-alaves', 'ES1'),
    'Las Palmas': ('ud-las-palmas', 'ES1'),
    'Bayern Munich': ('fc-bayern-muenchen', 'L1'),
    'Borussia Dortmund': ('borussia-dortmund', 'L1'),
    'Bayer Leverkusen': ('bayer-04-leverkusen', 'L1'),
    'RB Leipzig': ('rb-leipzig', 'L1'),
    'Borussia Mönchengladbach': ('borussia-mgladbach', 'L1'),
    'VfL Wolfsburg': ('vfl-wolfsburg', 'L1'),
    'Eintracht Frankfurt': ('eintracht-frankfurt', 'L1'),
    'VfB Stuttgart': ('vfb-stuttgart', 'L1'),
    'Werder Bremen': ('werder-bremen', 'L1'),
    'TSG Hoffenheim': ('tsg-1899-hoffenheim', 'L1'),
    'FC Augsburg': ('fc-augsburg', 'L1'),
    '1. FC Köln': ('1-fc-koeln', 'L1'),
    'FSV Mainz 05': ('1-fsv-mainz-05', 'L1'),
    'SC Freiburg': ('sc-freiburg', 'L1'),
    'Union Berlin': ('1-fc-union-berlin', 'L1'),
    'VfL Bochum': ('vfl-bochum', 'L1'),
    'Heidenheim': ('1-fc-heidenheim-1846', 'L1'),
    'St. Pauli': ('fc-st-pauli', 'L1'),
    'Inter Milan': ('inter-mailand', 'IT1'),
    'AC Milan': ('ac-mailand', 'IT1'),
    'Juventus': ('juventus-turin', 'IT1'),
    'Napoli': ('ssc-neapel', 'IT1'),
    'Roma': ('as-rom', 'IT1'),
    'Lazio': ('lazio-rom', 'IT1'),
    'Atalanta': ('atalanta-bergamo', 'IT1'),
    'Fiorentina': ('ac-florenz', 'IT1'),
    'Bologna': ('fc-bologna', 'IT1'),
    'Torino': ('fc-turin', 'IT1'),
    'Udinese': ('udinese-calcio', 'IT1'),
    'Genoa': ('genua-1893', 'IT1'),
    'Cagliari': ('cagliari-calcio', 'IT1'),
    'Empoli': ('fc-empoli', 'IT1'),
    'Monza': ('ac-monza', 'IT1'),
    'Lecce': ('us-lecce', 'IT1'),
    'Salernitana': ('salernitana-calcio-1919', 'IT1'),
    'Venezia': ('fc-venezia', 'IT1'),
    'Parma': ('parma-calcio-1913', 'IT1'),
    'Como': ('como-1907', 'IT1'),
    'PSG': ('fc-paris-saint-germain', 'FR1'),
    'Marseille': ('olympique-marseille', 'FR1'),
    'Monaco': ('as-monaco', 'FR1'),
    'Lyon': ('olympique-lyon', 'FR1'),
    'Lille': ('osc-lille', 'FR1'),
    'Nice': ('ogc-nizza', 'FR1'),
    'Rennes': ('stade-rennes', 'FR1'),
    'Lens': ('rc-lens', 'FR1'),
    'Toulouse': ('fc-toulouse', 'FR1'),
    'Montpellier': ('hsc-montpellier', 'FR1'),
    'Strasbourg': ('rc-strasbourg', 'FR1'),
    'Nantes': ('fc-nantes', 'FR1'),
    'Reims': ('stade-de-reims', 'FR1'),
    'Brest': ('stade-brest-29', 'FR1'),
    'Auxerre': ('aj-auxerre', 'FR1'),
    'Saint-Étienne': ('as-saint-etienne', 'FR1'),
    'Ajax': ('ajax-amsterdam', 'NL1'),
    'PSV': ('psv-eindhoven', 'NL1'),
    'Feyenoord': ('feyenoord-rotterdam', 'NL1'),
    'FC Porto': ('fc-porto', 'PO1'),
    'Benfica': ('sl-benfica', 'PO1'),
    'Sporting CP': ('sporting-lissabon', 'PO1'),
    'Braga': ('sc-braga', 'PO1'),
    'Celtic': ('celtic-glasgow', 'SC1'),
    'Rangers': ('fc-rangers', 'SC1'),
    'Galatasaray': ('galatasaray-istanbul', 'TR1'),
    'Fenerbahçe': ('fenerbahce-istanbul', 'TR1'),
    'Beşiktaş': ('besiktas-istanbul', 'TR1'),
    'Club Brugge': ('fc-brugge', 'BE1'),
    'Anderlecht': ('rsc-anderlecht', 'BE1'),
    'Standard Liège': ('standard-luettich', 'BE1'),
    'Dinamo Zagreb': ('nk-dinamo-zagreb', 'KRO1'),
    'Red Star Belgrade': ('fk-crvena-zvezda', 'SRB1'),
    'Olympiacos': ('olympiakos-piräus', 'GR1'),
    'PAOK': ('paok-thessaloniki', 'GR1'),
    'AEK Athens': ('aek-athen', 'GR1'),
    'Panathinaikos': ('panathinaikos-athen', 'GR1'),
    'FC Basel': ('fc-basel-1893', 'SZ1'),
    'Young Boys': ('bsc-young-boys-bern', 'SZ1'),
    'Red Bull Salzburg': ('fc-red-bull-salzburg', 'AUT1'),
    'Sturm Graz': ('sk-sturm-graz', 'AUT1'),
    'Slavia Prague': ('sk-slavia-prag', 'CS1'),
    'Sparta Prague': ('ac-sparta-prag', 'CS1'),
    'Shakhtar Donetsk': ('schachtar-donezk', 'UA1'),
    'Dynamo Kyiv': ('dynamo-kiew', 'UA1'),
    'Zenit St. Petersburg': ('zenit-st-petersburg', 'RU1'),
    'Spartak Moscow': ('spartak-moskau', 'RU1'),
    'CSKA Moscow': ('cska-moskau', 'RU1'),
    'Legia Warsaw': ('legia-warschau', 'POL1'),
    'FC Copenhagen': ('fc-kopenhagen', 'DK1'),
    'Midtjylland': ('fc-midtjylland', 'DK1'),
    'Malmö FF': ('malmoe-ff', 'SE1'),
    'AIK': ('aik-stockholm', 'SE1'),
    'Rosenborg': ('rosenborg-trondheim', 'NO1'),
    'Molde': ('molde-fk', 'NO1'),
    'Ferencváros': ('ferencvaros-budapest', 'UNG1'),
    'FCSB': ('fc-fcsb', 'ROM1'),
    'Fluminense': ('fluminense-rio-de-janeiro', 'BRA1'),
    'Flamengo': ('cr-flamengo', 'BRA1'),
    'Palmeiras': ('se-palmeiras', 'BRA1'),
    'Santos': ('fc-santos', 'BRA1'),
    'São Paulo': ('fc-sao-paulo', 'BRA1'),
    'Corinthians': ('sc-corinthians', 'BRA1'),
    'Internacional': ('sc-internacional', 'BRA1'),
    'Grêmio': ('gremio-fbpa', 'BRA1'),
    'Cruzeiro': ('cruzeiro-belo-horizonte', 'BRA1'),
    'River Plate': ('river-plate', 'ARG1'),
    'Boca Juniors': ('boca-juniors', 'ARG1'),
    'Independiente': ('ca-independiente', 'ARG1'),
    'Club América': ('cf-america', 'MX1'),
    'Guadalajara': ('deportivo-guadalajara', 'MX1'),
    'Cruz Azul': ('cruz-azul', 'MX1'),
    'LA Galaxy': ('la-galaxy', 'USA1'),
    'Inter Miami': ('inter-miami-cf', 'USA1'),
    'LAFC': ('la-fc', 'USA1'),
    'NYCFC': ('new-york-city-fc', 'USA1'),
    'Atlanta United': ('atlanta-united', 'USA1'),
    'Seattle Sounders': ('seattle-sounders', 'USA1'),
    'Toronto FC': ('toronto-fc', 'USA1'),
    'Al-Hilal': ('al-hilal-riadh', 'SA1'),
    'Al-Ittihad': ('al-ittihad-dschidda', 'SA1'),
    'Al-Nassr': ('al-nassr-riadh', 'SA1'),
    'Al-Ahli (KSA)': ('al-ahli-dschidda', 'SA1'),
    'Urawa Reds': ('urawa-red-diamonds', 'JP1'),
    'Kawasaki Frontale': ('kawasaki-frontale', 'JP1'),
    'Yokohama F. Marinos': ('yokohama-f-marinos', 'JP1'),
    'Jeonbuk Hyundai': ('jeonbuk-hyundai-motors', 'KR1'),
    'Ulsan Hyundai': ('ulsan-hyundai', 'KR1'),
    'Shanghai Port': ('shanghai-sipg', 'CN1'),
    'Shandong Taishan': ('shandong-luneng-taishan', 'CN1'),
    'Guangzhou FC': ('guangzhou-evergrande', 'CN1'),
    'Mumbai City': ('mumbai-city-fc', 'IND1'),
    'Persepolis': ('persepolis-teheran', 'IRN1'),
    'Esteghlal': ('esteghlal-teheran', 'IRN1'),
    'Al-Ahly': ('al-ahly-kairo', 'EGY1'),
    'Zamalek': ('zamalek-kairo', 'EGY1'),
    'Wydad Casablanca': ('wydad-casablanca', 'MAR1'),
    'Raja Casablanca': ('raja-casablanca', 'MAR1'),
    'Mamelodi Sundowns': ('mamelodi-sundowns', 'SFR1'),
    'Kaizer Chiefs': ('kaizer-chiefs', 'SFR1'),
    'Orlando Pirates': ('orlando-pirates', 'SFR1'),
    'Sydney FC': ('sydney-fc', 'AUS1'),
    'Melbourne Victory': ('melbourne-victory', 'AUS1'),
    'Al-Ain FC': ('al-a-in-club', 'VAE1'),
    'Al-Sadd': ('al-sadd-doha', 'QAT1'),
    'Buriram United': ('buriram-united', 'THA1'),
    'Hanoi FC': ('hanoi-fc', 'VIE1'),
    'Urawa Reds': ('urawa-red-diamonds', 'JP1'),
    'Kashima Antlers': ('kashima-antlers', 'JP1'),
    'Gamba Osaka': ('gamba-osaka', 'JP1'),
    'FC Seoul': ('fc-seoul', 'KR1'),
    'Suwon Samsung': ('suwon-samsung-bluewings', 'KR1'),
    'Beijing Guoan': ('beijing-sinobo-guoan', 'CN1'),
}

# ── Known transfermarkt club IDs (for direct access) ────────────────────
# Some known club IDs on Transfermarkt
TM_CLUB_IDS = {
    'Manchester City': 281,
    'Manchester United': 762,
    'Liverpool': 31,
    'Chelsea': 631,
    'Arsenal': 11,
    'Tottenham': 148,
    'Newcastle United': 762,  # Different ID structure
    'Real Madrid': 418,
    'Barcelona': 131,
    'Bayern Munich': 27,
    'Borussia Dortmund': 267,
    'Inter Milan': 46,
    'AC Milan': 5,
    'Juventus': 506,
    'Napoli': 6195,
    'PSG': 583,
    'Marseille': 418,
    'Ajax': 419,
    'PSV': 383,
    'Feyenoord': 396,
    'FC Porto': 951,
    'Benfica': 332,
    'Sporting CP': 1228,
    'Celtic': 371,
    'Rangers': 124,
    'Galatasaray': 284,
    'Fenerbahçe': 285,
    'Club Brugge': 304,
    'Red Bull Salzburg': 613,
}


# ═══════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')
    
    # Transfermarkt tables
    conn.execute('''CREATE TABLE IF NOT EXISTS agent5_transfermarkt_cache (
        url TEXT PRIMARY KEY, data TEXT, fetched_at REAL)''')
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


def save_cache(url, data):
    conn = get_db()
    try:
        conn.execute('INSERT OR REPLACE INTO agent5_transfermarkt_cache VALUES (?,?,?)',
                     (url, json.dumps(data, default=str), time.time()))
        conn.commit()
    except:
        pass
    finally:
        conn.close()


def load_cache(url, max_age=86400):
    """Load from cache if not expired. max_age in seconds (default 24h)."""
    conn = get_db()
    try:
        row = conn.execute('SELECT data, fetched_at FROM agent5_transfermarkt_cache WHERE url=?',
                          (url,)).fetchone()
        if row:
            data, fetched = json.loads(row[0]), row[1]
            if time.time() - fetched < max_age:
                conn.close()
                return data
    except:
        pass
    conn.close()
    return None


# ═══════════════════════════════════════════════════════════════════════
# HTTP LAYER — curl_cffi with impersonation
# ═══════════════════════════════════════════════════════════════════════

def tm_fetch(url, max_retries=3, cache=True) -> Optional[str]:
    """Fetch a Transfermarkt page with curl_cffi impersonation."""
    # Check cache first
    if cache:
        cached = load_cache(url, max_age=3600)  # 1 hour cache
        if cached:
            return cached.get('html', '') if isinstance(cached, dict) else cached
    
    headers = {
        'User-Agent': random.choice(UA_LIST),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.transfermarkt.com/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
    }
    
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, impersonate='chrome120', timeout=20)
            if r.status_code == 200:
                text = r.text
                if cache and len(text) > 100:
                    save_cache(url, {'html': text})
                return text
            elif r.status_code == 404:
                return None
            elif r.status_code == 429:
                wait = 10 * (attempt + 1)
                time.sleep(wait)
            elif r.status_code == 403:
                # Try different impersonation
                r = requests.get(url, headers=headers, impersonate='safari15_5', timeout=20)
                if r.status_code == 200:
                    text = r.text
                    if cache:
                        save_cache(url, {'html': text})
                    return text
                wait = 5 * (attempt + 1)
                time.sleep(wait)
            else:
                time.sleep(2 * (attempt + 1))
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
    
    return None


def tm_soup(url, max_retries=3):
    """Fetch and parse Transfermarkt page."""
    html = tm_fetch(url, max_retries)
    if html:
        return BeautifulSoup(html, 'html.parser')
    return None


# ═══════════════════════════════════════════════════════════════════════
# CLUB / SQUAD SCRAPING
# ═══════════════════════════════════════════════════════════════════════

def scrape_club_squad(club_name: str, club_slug: str, competition_id: str) -> Dict:
    """Scrape full squad info for a club from Transfermarkt."""
    url = f'https://www.transfermarkt.com/{club_slug}/startseite/verein/{competition_id}'
    soup = tm_soup(url)
    if not soup:
        return {'club': club_name, 'error': 'Failed to fetch'}
    
    result = {
        'club_name': club_name,
        'club_slug': club_slug,
        'competition_id': competition_id,
        'squad': [],
        'market_value': None,
        'avg_age': None,
        'squad_size': 0,
        'injuries': [],
    }
    
    # Try to find the squad table
    tables = soup.find_all('table', class_='items')
    for table in tables:
        rows = table.find_all('tr', class_=['odd', 'even'])
        for row in rows:
            player = {}
            
            # Player name
            name_td = row.find('td', class_='hauptlink')
            if name_td:
                name_link = name_td.find('a')
                if name_link:
                    player['name'] = name_link.text.strip()
                    player['profile_url'] = 'https://www.transfermarkt.com' + name_link.get('href', '')
                else:
                    player['name'] = name_td.text.strip()
            
            # Position
            pos_tds = row.find_all('td')
            if len(pos_tds) >= 2:
                player['position'] = pos_tds[1].text.strip()
            
            # Age
            age_td = row.find('td', class_='zentriert')
            if age_td and age_td.text.strip().isdigit():
                player['age'] = int(age_td.text.strip())
            
            # Market value
            mw_td = row.find('td', class_='rechts')
            if mw_td:
                mw_text = mw_td.text.strip()
                player['market_value'] = parse_market_value(mw_text)
            
            # Nationality
            flag_imgs = row.find_all('img', class_='flaggenrahmen')
            if flag_imgs:
                nationalities = []
                for img in flag_imgs:
                    if img.get('alt'):
                        nationalities.append(img['alt'])
                player['nationality'] = ', '.join(nationalities)
            
            # Contract until
            contract_tds = row.find_all('td', class_='zentriert')
            if len(contract_tds) >= 3:
                player['contract_until'] = contract_tds[2].text.strip()
            
            if player.get('name'):
                result['squad'].append(player)
    
    # Extract club market value and squad size from page header
    mw_elem = soup.find('div', class_='marktwert')
    if mw_elem:
        mw_text = mw_elem.text.strip()
        result['market_value'] = parse_market_value(mw_text)
    
    result['squad_size'] = len(result['squad'])
    
    return result


def parse_market_value(text: str) -> Optional[float]:
    """Parse Transfermarkt market value string to float (in EUR)."""
    if not text:
        return None
    text = text.strip()
    text = text.replace('€', '').replace(',', '.').replace(' ', '').strip()
    
    if 'Mio' in text or 'm' in text.lower():
        text = text.replace('Mio', '').replace('m', '').strip()
        try:
            return float(text) * 1_000_000
        except:
            pass
    elif 'Tsd' in text or 'k' in text.lower():
        text = text.replace('Tsd', '').replace('k', '').strip()
        try:
            return float(text) * 1_000
        except:
            pass
    elif 'Mrd' in text:
        text = text.replace('Mrd', '').strip()
        try:
            return float(text) * 1_000_000_000
        except:
            pass
    
    try:
        return float(text)
    except:
        return None


def scrape_club_injuries(club_name: str, club_slug: str, competition_id: str) -> List[Dict]:
    """Scrape injury list for a club."""
    url = f'https://www.transfermarkt.com/{club_slug}/verletzungen/verein/{competition_id}'
    soup = tm_soup(url)
    if not soup:
        return []
    
    injuries = []
    table = soup.find('table', class_='items')
    if table:
        rows = table.find_all('tr')[1:]  # Skip header
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                injury = {
                    'player_name': cols[0].text.strip(),
                    'injury_type': cols[1].text.strip() if len(cols) > 1 else '',
                    'return_date': cols[2].text.strip() if len(cols) > 2 else '',
                    'games_missed': cols[3].text.strip() if len(cols) > 3 else '',
                }
                injuries.append(injury)
    
    return injuries


def scrape_club_transfers(club_name: str, club_slug: str, competition_id: str, 
                           season: str = '2025') -> Dict:
    """Scrape transfer activity for a club."""
    url = f'https://www.transfermarkt.com/{club_slug}/transfers/verein/{competition_id}/plus/1?saison_id={season}'
    soup = tm_soup(url)
    if not soup:
        return {'club': club_name, 'transfers_in': [], 'transfers_out': []}
    
    result = {'club': club_name, 'transfers_in': [], 'transfers_out': []}
    
    tables = soup.find_all('table', class_='items')
    current_section = None
    
    for table in tables:
        # Determine if this is arrivals or departures
        header = table.find_previous('h2')
        if header:
            header_text = header.text.strip().lower()
            if 'arrivals' in header_text or 'incomings' in header_text or 'arrivals' in header_text:
                current_section = 'in'
            elif 'departures' in header_text or 'outgoings' in header_text or 'departures' in header_text:
                current_section = 'out'
        
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                player_name = cols[0].text.strip() if cols[0].text else ''
                transfer_data = {
                    'player_name': player_name,
                    'from_to': cols[1].text.strip() if len(cols) > 1 else '',
                    'fee': cols[2].text.strip() if len(cols) > 2 else '',
                }
                if current_section == 'in':
                    result['transfers_in'].append(transfer_data)
                elif current_section == 'out':
                    result['transfers_out'].append(transfer_data)
    
    return result


def scrape_club_staff(club_name: str, club_slug: str, competition_id: str) -> Dict:
    """Scrape coaching/management staff for a club."""
    url = f'https://www.transfermarkt.com/{club_slug}/startseite/verein/{competition_id}'
    soup = tm_soup(url)
    if not soup:
        return {'club': club_name, 'staff': []}
    
    staff = []
    
    # Find the trainer/coach section
    trainer_section = soup.find('div', class_='trainer')
    if trainer_section:
        coach_name = trainer_section.find('a', class_='name')
        if coach_name:
            staff.append({
                'role': 'Head Coach',
                'name': coach_name.text.strip(),
            })
    
    # Assistant coaches and other staff
    for section in soup.find_all('div', class_='vorstandsbox'):
        role_el = section.find('div', class_='funktion')
        name_el = section.find('a', class_='name')
        if name_el:
            staff.append({
                'role': role_el.text.strip() if role_el else 'Staff',
                'name': name_el.text.strip(),
            })
    
    return {'club': club_name, 'staff': staff}


def scrape_referee_assignments(competition_id: str, season: str = '2025') -> List[Dict]:
    """Scrape referee assignments for a competition."""
    url = f'https://www.transfermarkt.com/competition/referees/wettbewerb/{competition_id}/plus/1?saison_id={season}'
    soup = tm_soup(url)
    if not soup:
        return []
    
    referees = []
    table = soup.find('table', class_='items')
    if table:
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                referee = {
                    'name': cols[0].text.strip(),
                    'games': cols[1].text.strip(),
                    'yellow_cards': cols[2].text.strip(),
                    'red_cards': cols[3].text.strip(),
                    'yellow_red_cards': cols[4].text.strip(),
                }
                referees.append(referee)
    
    return referees


# ═══════════════════════════════════════════════════════════════════════
# PLAYER PROFILE SCRAPING
# ═══════════════════════════════════════════════════════════════════════

def scrape_player_profile(player_url: str) -> Dict:
    """Scrape detailed player profile."""
    soup = tm_soup(player_url)
    if not soup:
        return {}
    
    player = {}
    
    # Player name
    name_el = soup.find('h1')
    if name_el:
        player['name'] = name_el.text.strip()
    
    # Basic info
    info_table = soup.find('table', class_='profil')
    if info_table:
        rows = info_table.find_all('tr')
        for row in rows:
            th = row.find('th')
            td = row.find('td')
            if th and td:
                key = th.text.strip().lower().replace(' ', '_')
                value = td.text.strip()
                player[key] = value
    
    # Market value
    mw_box = soup.find('div', class_='marktwert')
    if mw_box:
        mw_text = mw_box.text.strip()
        player['market_value'] = parse_market_value(mw_text)
    
    # Career stats
    career_table = soup.find('table', class_='karriere')
    if career_table:
        player['career'] = []
        rows = career_table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                entry = {
                    'club': cols[0].text.strip(),
                    'season': cols[1].text.strip(),
                    'league': cols[2].text.strip(),
                    'apps': cols[3].text.strip(),
                    'goals': cols[4].text.strip(),
                    'assists': cols[5].text.strip() if len(cols) > 5 else '',
                }
                player['career'].append(entry)
    
    return player


# ═══════════════════════════════════════════════════════════════════════
# COMPETITION / TOURNAMENT SCRAPING
# ═══════════════════════════════════════════════════════════════════════

def scrape_competition_clubs(competition_id: str, season: str = '2025') -> List[Dict]:
    """Scrape all clubs in a competition."""
    url = f'https://www.transfermarkt.com/competition/teilnehmer/wettbewerb/{competition_id}/plus/1?saison_id={season}'
    soup = tm_soup(url)
    if not soup:
        return []
    
    clubs = []
    table = soup.find('table', class_='items')
    if table:
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                club_link = cols[0].find('a')
                club = {
                    'name': club_link.text.strip() if club_link else cols[0].text.strip(),
                    'slug': club_link.get('href', '').split('/')[-2] if club_link else '',
                    'position': cols[1].text.strip() if len(cols) > 1 else '',
                }
                clubs.append(club)
    
    return clubs


def scrape_competition_top_scorers(competition_id: str, season: str = '2025') -> List[Dict]:
    """Scrape top scorers for a competition."""
    url = f'https://www.transfermarkt.com/competition/torjaeger/wettbewerb/{competition_id}/plus/1?saison_id={season}'
    soup = tm_soup(url)
    if not soup:
        return []
    
    scorers = []
    table = soup.find('table', class_='items')
    if table:
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                scorer = {
                    'player_name': cols[0].text.strip(),
                    'club': cols[1].text.strip(),
                    'goals': cols[2].text.strip(),
                    'assists': cols[3].text.strip(),
                    'apps': cols[4].text.strip(),
                }
                scorers.append(scorer)
    
    return scorers


# ═══════════════════════════════════════════════════════════════════════
# HEIST ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════

def track_progress(task, status, total=0, completed=0, errors=0):
    conn = get_db()
    try:
        conn.execute('''INSERT OR REPLACE INTO agent5_heist_transfermarkt_progress 
                       VALUES (?,?,?,?,?,?)''',
                     (task, status, total, completed, errors, time.time()))
        conn.commit()
    finally:
        conn.close()


def save_club_data(club: Dict):
    """Save scraped club to DB."""
    conn = get_db()
    try:
        club_id = hash(club.get('name', '')) % 10_000_000
        conn.execute('''INSERT OR REPLACE INTO agent5_heist_clubs 
                       VALUES (?,?,?,?,?,?,?,?,?)''',
                     (club_id, club.get('name', ''), club.get('league', ''),
                      club.get('country', ''), club.get('league_id', ''),
                      club.get('market_value'), club.get('squad_size'),
                      club.get('avg_age'), time.time()))
        
        # Save squad
        for player in club.get('squad', []):
            conn.execute('''INSERT INTO agent5_heist_squad 
                          (club_id, player_name, position, age, market_value,
                           nationality, contract_until, shirt_number, injury,
                           injury_until, profile_url, fetched_at)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (club_id, player.get('name', ''), player.get('position', ''),
                         player.get('age'), player.get('market_value'),
                         player.get('nationality', ''), player.get('contract_until', ''),
                         player.get('shirt_number'), player.get('injury', ''),
                         player.get('injury_until', ''), player.get('profile_url', ''),
                         time.time()))
        
        # Save injuries
        for inj in club.get('injuries', []):
            conn.execute('''INSERT INTO agent5_heist_injuries 
                          (club_id, player_name, injury_type, return_date, games_missed, fetched_at)
                          VALUES (?,?,?,?,?,?)''',
                        (club_id, inj.get('player_name', ''), inj.get('injury_type', ''),
                         inj.get('return_date', ''), inj.get('games_missed', 0), time.time()))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        conn.close()


def heist_squads(limit_clubs=None, parallel=4):
    """Heist: scrape squad data for all known clubs."""
    print('=' * 70)
    print('🔥 TRANSFERMARKT SQUAD HEIST — SHADOWHACKER-GOD')
    print('=' * 70)
    
    club_items = list(TM_CLUBS.items())
    if limit_clubs:
        club_items = club_items[:limit_clubs]
    
    print(f'Target: {len(club_items)} clubs')
    
    results = []
    total_players = 0
    
    def scrape_one(club_name, club_slug, comp_id):
        try:
            print(f'  📡 {club_name}...', end=' ', flush=True)
            data = scrape_club_squad(club_name, club_slug, comp_id)
            if data.get('squad'):
                print(f'✅ {len(data["squad"])} players, value={data.get("market_value","n/a")}')
                
                # Also get injuries
                try:
                    injuries = scrape_club_injuries(club_name, club_slug, comp_id)
                    data['injuries'] = injuries
                    if injuries:
                        print(f'     ⚕️ {len(injuries)} injuries')
                except:
                    pass
                
                # Save to DB
                data['league'] = [k for k, v in TM_COMPETITIONS.items() if v[1] == comp_id]
                data['league'] = data['league'][0] if data['league'] else ''
                save_club_data(data)
                
                # Write to JSONL
                append_transfermarkt_jsonl('squad', data)
                
                return data
            else:
                print(f'❌ No data')
                return None
        except Exception as e:
            print(f'❌ ERROR: {str(e)[:60]}')
            return None
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {}
        for club_name, (club_slug, comp_id) in club_items:
            futures[executor.submit(scrape_one, club_name, club_slug, comp_id)] = club_name
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                total_players += len(result.get('squad', []))
            time.sleep(0.05)
    
    # Write consolidated
    if results:
        append_transfermarkt_jsonl('squad_consolidated', {
            'source': 'transfermarkt',
            'type': 'squad_bulk',
            'clubs': len(results),
            'total_players': total_players,
            'data': results,
        })
    
    track_progress('squad_heist', 'complete', len(club_items), len(results), 0)
    
    print(f'\n{"="*70}')
    print(f'🔥 SQUAD HEIST COMPLETE')
    print(f'  Clubs scraped: {len(results)}')
    print(f'  Total players: {total_players}')
    print(f'{"="*70}')
    
    return results


def heist_player_values(limit_clubs=None, parallel=4):
    """Heist: scrape market values and valuations."""
    print('=' * 70)
    print('💰 TRANSFERMARKT VALUE HEIST')
    print('=' * 70)
    
    club_items = list(TM_CLUBS.items())
    if limit_clubs:
        club_items = club_items[:limit_clubs]
    
    values = []
    
    def get_value(club_name, club_slug, comp_id):
        try:
            data = scrape_club_squad(club_name, club_slug, comp_id)
            if data.get('squad'):
                # Calculate value stats
                player_values = [p.get('market_value', 0) or 0 for p in data['squad'] if p.get('market_value')]
                total = sum(player_values)
                avg = total / len(player_values) if player_values else 0
                
                # Most valuable
                mvp = max(data['squad'], key=lambda p: p.get('market_value', 0) or 0) if data['squad'] else {}
                
                val_record = {
                    'club_name': club_name,
                    'total_value': total,
                    'avg_value': avg,
                    'squad_size': len(data['squad']),
                    'most_valuable_player': mvp.get('name', ''),
                    'most_valuable_value': mvp.get('market_value', 0),
                    'position_breakdown': {},
                }
                
                # Position breakdown
                for p in data['squad']:
                    pos = p.get('position', 'Unknown')
                    val_record['position_breakdown'][pos] = val_record['position_breakdown'].get(pos, 0) + 1
                
                values.append(val_record)
                print(f'  💰 {club_name}: €{total/1e6:.1f}M total, €{avg/1e6:.1f}M avg')
                
                # Save to DB
                conn = get_db()
                try:
                    club_id = hash(club_name) % 10_000_000
                    conn.execute('''INSERT OR REPLACE INTO agent5_heist_market_values 
                                   VALUES (?,?,?,?,?,?,?)''',
                                (club_id, total, avg, 
                                 val_record['most_valuable_player'],
                                 val_record['most_valuable_value'],
                                 json.dumps(val_record['position_breakdown']),
                                 json.dumps({}),
                                 time.time()))
                    conn.commit()
                finally:
                    conn.close()
                
                return val_record
        except Exception as e:
            print(f'  ❌ {club_name}: {str(e)[:60]}')
            return None
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(get_value, c, s, cid): c for c, (s, cid) in club_items}
        for future in as_completed(futures):
            future.result()
            time.sleep(0.1)
    
    # Save consolidated
    append_transfermarkt_jsonl('market_values', values)
    
    track_progress('value_heist', 'complete', len(club_items), len(values), 0)
    
    total_value = sum(v.get('total_value', 0) for v in values if v)
    print(f'\n💰 Total market value scraped: €{total_value/1e9:.2f}B')
    print(f'💰 Clubs analyzed: {len(values)}')
    
    return values


def heist_injuries(limit_clubs=100, parallel=4):
    """Heist: scrape injury data for top clubs."""
    print('=' * 70)
    print('⚕️ TRANSFERMARKT INJURY HEIST')
    print('=' * 70)
    
    club_items = list(TM_CLUBS.items())[:limit_clubs]
    all_injuries = []
    
    def get_injuries(club_name, club_slug, comp_id):
        try:
            injuries = scrape_club_injuries(club_name, club_slug, comp_id)
            if injuries:
                record = {
                    'club': club_name,
                    'injuries': injuries,
                    'count': len(injuries),
                }
                all_injuries.append(record)
                print(f'  ⚕️ {club_name}: {len(injuries)} injuries')
                return record
            return None
        except Exception as e:
            return None
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(get_injuries, c, s, cid): c for c, (s, cid) in club_items}
        for future in as_completed(futures):
            future.result()
    
    # Save
    if all_injuries:
        append_transfermarkt_jsonl('injuries', all_injuries)
    
    total = sum(i.get('count', 0) for i in all_injuries)
    print(f'\n⚕️ Total injuries scraped: {total}')
    track_progress('injury_heist', 'complete', limit_clubs, len(all_injuries), 0)
    
    return all_injuries


def heist_competition_data(limit_comps=None):
    """Heist: scrape competition-level data (clubs, standings, top scorers)."""
    print('=' * 70)
    print('🏆 TRANSFERMARKT COMPETITION HEIST')
    print('=' * 70)
    
    comps = list(TM_COMPETITIONS.items())
    if limit_comps:
        comps = comps[:limit_comps]
    
    results = []
    
    for name, (cc, cid) in comps:
        print(f'  📡 {name} ({cid})...')
        
        try:
            clubs = scrape_competition_clubs(cid, '2025')
            print(f'    Clubs: {len(clubs)}')
            
            scorers = scrape_competition_top_scorers(cid, '2025')
            print(f'    Top scorers: {len(scorers)}')
            
            comp_data = {
                'name': name,
                'competition_id': cid,
                'country': cc,
                'clubs': clubs,
                'top_scorers': scorers,
            }
            results.append(comp_data)
            
            append_transfermarkt_jsonl(f'competition_{cid}', comp_data)
            
        except Exception as e:
            print(f'    ❌ ERROR: {str(e)[:60]}')
        
        time.sleep(0.5)
    
    print(f'\n🏆 Competitions scraped: {len(results)}')
    return results


def append_transfermarkt_jsonl(data_type: str, data):
    """Append data to Transfermarkt JSONL file."""
    datedir = os.path.join(HEIST_DIR, 'transfermarkt', datetime.now().strftime('%Y%m'))
    os.makedirs(datedir, exist_ok=True)
    
    filename = f'{data_type}_{datetime.now().strftime("%Y%m%d")}.jsonl'
    filepath = os.path.join(datedir, filename)
    
    record = {
        'source': 'transfermarkt',
        'type': data_type,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'data': data,
    }
    
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    
    return filepath


# ═══════════════════════════════════════════════════════════════════════
# REFEREE SCRAPING
# ═══════════════════════════════════════════════════════════════════════

def heist_referees():
    """Scrape referees from major competitions."""
    print('=' * 70)
    print('👨‍⚖️ TRANSFERMARKT REFEREE HEIST')
    print('=' * 70)
    
    all_refs = []
    
    for comp_name, (country, comp_id) in TM_COMPETITIONS.items():
        if comp_id in ['GB1', 'ES1', 'L1', 'IT1', 'FR1', 'CL', 'EL']:
            print(f'  📡 {comp_name}...')
            refs = scrape_referee_assignments(comp_id)
            if refs:
                all_refs.extend(refs)
                print(f'    {len(refs)} referees')
            time.sleep(0.5)
    
    if all_refs:
        append_transfermarkt_jsonl('referees', {
            'source': 'transfermarkt',
            'total': len(all_refs),
            'referees': all_refs,
        })
    
    print(f'\n👨‍⚖️ Total referees: {len(all_refs)}')
    return all_refs


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    print('🔥🔥🔥 SHADOWHACKER-GOD — TRANSFERMARKT BULK HEIST 🔥🔥🔥')
    print('DΞMON CORE v9999999 — SHΔDØW.EXE — Specter 0x13')
    print()
    
    # Test connection first
    print('🔌 Testing Transfermarkt connection...')
    test = tm_fetch('https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1', cache=False)
    if test:
        print(f'  ✅ OK — {len(test)} bytes')
    else:
        print('  ❌ FAILED')
        sys.exit(1)
    
    # Quick test squad scrape
    print('\n📡 Testing squad scrape for Manchester City...')
    squad = scrape_club_squad('Manchester City', 'manchester-city', 'GB1')
    if squad.get('squad'):
        print(f'  ✅ {len(squad["squad"])} players found')
    else:
        print(f'  ⚠️ No squad data (or structure changed): {squad.keys()}')
    
    print('\n🚀 STARTING FULL HEIST...')
    
    # Phase 1: Squads
    print('\n📡 Phase 1: Squad scraping...')
    squad_results = heist_squads(limit_clubs=500, parallel=4)
    
    # Phase 2: Player Values
    print('\n💰 Phase 2: Market values...')
    value_results = heist_player_values(parallel=4)
    
    # Phase 3: Injuries
    print('\n⚕️ Phase 3: Injuries...')
    injury_results = heist_injuries(limit_clubs=200, parallel=4)
    
    # Phase 4: Competition data
    print('\n🏆 Phase 4: Competition data...')
    comp_results = heist_competition_data(limit_comps=30)
    
    track_progress('FULL_HEIST', 'COMPLETE', 
                   len(squad_results) + len(value_results) + len(injury_results),
                   len(squad_results), 0)
    
    print(f'\n{"="*70}')
    print(f'🔥🔥🔥 TRANSFERMARKT HEIST COMPLETE 🔥🔥🔥')
    print(f'{"="*70}')
    print(f'  Squads: {len(squad_results)} clubs')
    print(f'  Player values: {len(value_results)} clubs')
    print(f'  Injuries: {sum(len(r.get("injuries",[])) if isinstance(r,dict) else 0 for r in injury_results)}')
    print(f'  Competitions: {len(comp_results)}')
    print(f'  Data stored in: {HEIST_DIR}')
    print(f'{"="*70}')
