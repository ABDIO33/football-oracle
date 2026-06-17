"""
football_data_integration.py
Download + Parse + Map + Integrate Football-Data.co.uk odds into training pipeline
"""

import os, sys, sqlite3, re, json, time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import urllib.request

# ── paths ──
BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, 'scrape_cache.db')
DATA_DIR = os.path.join(BASE, 'football_data')
os.makedirs(DATA_DIR, exist_ok=True)

# ── league codes ──
LEAGUES = {
    'E0': ('England', 'Premier League'),
    'E1': ('England', 'Championship'),
    'E2': ('England', 'League 1'),
    'E3': ('England', 'League 2'),
    'EC': ('England', 'Conference'),
    'SC0': ('Scotland', 'Premiership'),
    'SC1': ('Scotland', 'Championship'),
    'SC2': ('Scotland', 'League 1'),
    'SC3': ('Scotland', 'League 2'),
    'D1': ('Germany', 'Bundesliga'),
    'D2': ('Germany', '2. Bundesliga'),
    'D3': ('Germany', '3. Liga'),
    'SP1': ('Spain', 'La Liga'),
    'SP2': ('Spain', 'Segunda'),
    'I1': ('Italy', 'Serie A'),
    'I2': ('Italy', 'Serie B'),
    'F1': ('France', 'Ligue 1'),
    'F2': ('France', 'Ligue 2'),
    'N1': ('Netherlands', 'Eredivisie'),
    'B1': ('Belgium', 'Pro League'),
    'P1': ('Portugal', 'Primeira Liga'),
    'T1': ('Turkey', 'Super Lig'),
    'G1': ('Greece', 'Super League'),
    'MLS': ('USA', 'MLS'),
    'J1': ('Japan', 'J1 League'),
    'K1': ('South Korea', 'K League 1'),
    'BRA': ('Brazil', 'Serie A'),
    'ARG': ('Argentina', 'Primera Division'),
}

# Each league has CSV files per season at football-data.co.uk
# URL pattern for recent seasons:
# https://www.football-data.co.uk/new/{CODE}.csv  (most recent)
# https://www.football-data.co.uk/mmz4281/2425/{CODE}.csv  (archived)

SEASONS = [
    '2425',  # 2024-25
    '2324',  # 2023-24
    '2223',  # 2022-23
    '2122',  # 2021-22
    '2021',  # 2020-21
]

def download_csvs():
    """Download all available CSVs from football-data.co.uk"""
    downloaded = 0
    failed = 0

    for code in LEAGUES:
        country, league = LEAGUES[code]

        # Try the "new" endpoint first (most recent season)
        url = f'https://www.football-data.co.uk/new/{code}.csv'
        dest = os.path.join(DATA_DIR, f'{code}_latest.csv')

        try:
            urllib.request.urlretrieve(url, dest)
            downloaded += 1
            print(f'  OK  {code} ({league}): latest')
            time.sleep(0.5)
            continue
        except:
            pass

        # Try archived seasons
        for season in SEASONS:
            url = f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv'
            dest = os.path.join(DATA_DIR, f'{code}_{season}.csv')

            try:
                urllib.request.urlretrieve(url, dest)
                downloaded += 1
                print(f'  OK  {code} ({league}): {season}')
                time.sleep(0.3)
                break
            except:
                pass
        else:
            failed += 1
            print(f'  --  {code} ({league}): not found')

    print(f'\nDownloaded: {downloaded}, Failed: {failed}')
    return downloaded

# ── Smart Parser ──
STANDARD_COLS = [
    'Div', 'Date', 'HomeTeam', 'AwayTeam',
    'FTHG', 'FTAG', 'FTR',
    'HTHG', 'HTAG', 'HTR',
    'HS', 'AS', 'HST', 'AST',
    'HF', 'AF', 'HC', 'AC',
    'HY', 'AY', 'HR', 'AR',
    'B365H', 'B365D', 'B365A',
    'BWH', 'BWD', 'BWA',
    'IWH', 'IWD', 'IWA',
    'PSH', 'PSD', 'PSA',
    'WHH', 'WHD', 'WHA',
    'VCH', 'VCD', 'VCA',
    'MaxH', 'MaxD', 'MaxA',
    'AvgH', 'AvgD', 'AvgA',
]

COL_ALIASES = {
    'HomeTeam': ['HomeTeam', 'Home', 'HT', 'Home_Team'],
    'AwayTeam': ['AwayTeam', 'Away', 'AT', 'Away_Team'],
    'FTHG': ['FTHG', 'HG', 'HomeGoals', 'Home_Goals'],
    'FTAG': ['FTAG', 'AG', 'AwayGoals', 'Away_Goals'],
    'FTR': ['FTR', 'Res', 'Result', 'FTResult'],
    'HTHG': ['HTHG'],
    'HTAG': ['HTAG'],
    'HTR': ['HTR'],
    'HS': ['HS', 'HomeShots', 'H_S'],
    'AS': ['AS', 'AwayShots', 'A_S'],
    'HST': ['HST', 'HomeShotsTarget', 'HSTarget'],
    'AST': ['AST', 'AwayShotsTarget', 'ASTarget'],
    'HF': ['HF', 'HomeFouls', 'H_F'],
    'AF': ['AF', 'AwayFouls', 'A_F'],
    'HC': ['HC', 'HomeCorners', 'H_C'],
    'AC': ['AC', 'AwayCorners', 'A_C'],
    'HY': ['HY', 'HomeYellow', 'H_Y'],
    'AY': ['AY', 'AwayYellow', 'A_Y'],
    'HR': ['HR', 'HomeRed', 'H_R'],
    'AR': ['AR', 'AwayRed', 'A_R'],
    'B365H': ['B365H', 'B365_H'],
    'B365D': ['B365D', 'B365_D'],
    'B365A': ['B365A', 'B365_A'],
    'AvgH': ['AvgH', 'Avg_H', 'Average_H'],
    'AvgD': ['AvgD', 'Avg_D', 'Average_D'],
    'AvgA': ['AvgA', 'Avg_A', 'Average_A'],
    'MaxH': ['MaxH', 'Max_H'],
    'MaxD': ['MaxD', 'Max_D'],
    'MaxA': ['MaxA', 'Max_A'],
}

def parse_csv(filepath):
    """Parse a single Football-Data CSV into unified format."""
    try:
        df = pd.read_csv(filepath, encoding='latin1')
    except:
        df = pd.read_csv(filepath, encoding='utf-8')

    # Detect columns
    rename = {}
    for std, aliases in COL_ALIASES.items():
        for a in aliases:
            if a in df.columns:
                rename[a] = std
                break

    df = df.rename(columns=rename)

    # Add missing columns
    for col in STANDARD_COLS:
        if col not in df.columns:
            df[col] = np.nan

    # Parse date
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df['DateStr'] = df['Date'].dt.strftime('%Y-%m-%d')

    # Extract league info from filename
    fname = os.path.basename(filepath)
    parts = fname.replace('.csv', '').split('_')
    code = parts[0]
    country, league_name = LEAGUES.get(code, ('Unknown', 'Unknown'))
    df['LeagueCode'] = code
    df['Country'] = country
    df['League'] = league_name

    return df[STANDARD_COLS + ['DateStr', 'LeagueCode', 'Country', 'League']]

def parse_all():
    """Parse all downloaded CSVs into single DataFrame."""
    all_dfs = []
    for f in sorted(os.listdir(DATA_DIR)):
        if not f.endswith('.csv'):
            continue
        fp = os.path.join(DATA_DIR, f)
        try:
            df = parse_csv(fp)
            all_dfs.append(df)
        except Exception as e:
            pass

    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()

# ── Team Name Mapping ──
MANUAL_MAP = {
    # England
    'Man City': 'Manchester City', 'Man United': 'Manchester United',
    'Man Utd': 'Manchester United', 'Tottenham': 'Tottenham Hotspur',
    'Newcastle': 'Newcastle United', 'West Ham': 'West Ham United',
    'Wolves': 'Wolverhampton Wanderers', 'Brighton': 'Brighton & Hove Albion',
    'Leicester': 'Leicester City', 'Leeds': 'Leeds United',
    'Ipswich': 'Ipswich Town', 'Norwich': 'Norwich City',
    'Stoke': 'Stoke City', 'Swansea': 'Swansea City',
    'Cardiff': 'Cardiff City', 'Hull': 'Hull City',
    'Derby': 'Derby County', 'Nottm Forest': 'Nottingham Forest',
    'QPR': 'Queens Park Rangers', 'Sheffield United': 'Sheffield Utd',
    'Sheffield Weds': 'Sheffield Wednesday', 'West Brom': 'West Bromwich Albion',
    'Rotherham': 'Rotherham United', 'Millwall': 'Millwall FC',
    'Bristol City': 'Bristol City FC', 'Blackburn': 'Blackburn Rovers',
    'Preston': 'Preston North End', 'Wigan': 'Wigan Athletic',
    'Birmingham': 'Birmingham City', 'Huddersfield': 'Huddersfield Town',
    'Coventry': 'Coventry City', 'Luton': 'Luton Town',
    'Bournemouth': 'AFC Bournemouth', 'Brentford': 'Brentford FC',
    'Crystal Palace': 'Crystal Palace FC', 'Southampton': 'Southampton FC',
    'Watford': 'Watford FC', 'Burnley': 'Burnley FC',
    'Everton': 'Everton FC', 'Liverpool': 'Liverpool FC',
    'Arsenal': 'Arsenal FC', 'Chelsea': 'Chelsea FC',
    'Fulham': 'Fulham FC',

    # Spain
    'Ath Madrid': 'Atletico Madrid', 'Ath Bilbao': 'Athletic Bilbao',
    'Celta': 'Celta Vigo', 'Vallecano': 'Rayo Vallecano',
    'Sociedad': 'Real Sociedad', 'Mallorca': 'RCD Mallorca',
    'Betis': 'Real Betis', 'Villarreal': 'Villarreal CF',
    'Sevilla': 'Sevilla FC', 'Valencia': 'Valencia CF',
    'Getafe': 'Getafe CF', 'Osasuna': 'CA Osasuna',
    'Alaves': 'Deportivo Alaves', 'Las Palmas': 'UD Las Palmas',
    'Cadiz': 'Cadiz CF', 'Granada': 'Granada CF',

    # Germany
    'Bayern Munich': 'Bayern Munich', 'Dortmund': 'Borussia Dortmund',
    'Mgladbach': 'Borussia Monchengladbach', 'Leverkusen': 'Bayer Leverkusen',
    'Wolfsburg': 'VfL Wolfsburg', 'Ein Frankfurt': 'Eintracht Frankfurt',
    'Freiburg': 'SC Freiburg', 'Mainz': 'Mainz 05',
    'Hoffenheim': 'TSG Hoffenheim', 'Augsburg': 'FC Augsburg',
    'Stuttgart': 'VfB Stuttgart', 'RB Leipzig': 'RB Leipzig',
    'Union Berlin': 'Union Berlin', 'Heidenheim': '1. FC Heidenheim',
    'Bochum': 'VfL Bochum', 'Koln': 'FC Cologne',
    'Werder Bremen': 'Werder Bremen', 'Hertha': 'Hertha Berlin',

    # Italy
    'Inter': 'Inter Milan', 'Milan': 'AC Milan',
    'Roma': 'AS Roma', 'Lazio': 'SS Lazio',
    'Napoli': 'Napoli', 'Atalanta': 'Atalanta BC',
    'Juventus': 'Juventus', 'Torino': 'Torino FC',
    'Fiorentina': 'Fiorentina', 'Bologna': 'Bologna FC',
    'Sassuolo': 'Sassuolo', 'Udinese': 'Udinese',
    'Lecce': 'Lecce', 'Genoa': 'Genoa',
    'Cagliari': 'Cagliari', 'Verona': 'Hellas Verona',

    # France
    'Paris SG': 'Paris Saint-Germain', 'Marseille': 'Olympique Marseille',
    'Lyon': 'Olympique Lyonnais', 'Lille': 'Lille OSC',
    'Monaco': 'AS Monaco', 'Rennes': 'Stade Rennais',
    'Nice': 'OGC Nice', 'Strasbourg': 'RC Strasbourg',
    'Nantes': 'FC Nantes', 'Montpellier': 'Montpellier HSC',
    'Reims': 'Stade Reims', 'Brest': 'Stade Brestois',
    'Lens': 'RC Lens', 'Toulouse': 'Toulouse FC',

    # Netherlands
    'Ajax': 'Ajax Amsterdam', 'PSV Eindhoven': 'PSV Eindhoven',
    'Feyenoord': 'Feyenoord', 'AZ Alkmaar': 'AZ Alkmaar',
    'Twente': 'FC Twente', 'Heerenveen': 'SC Heerenveen',
    'Vitesse': 'Vitesse Arnhem', 'Utrecht': 'FC Utrecht',

    # Portugal
    'Benfica': 'Benfica', 'Porto': 'FC Porto',
    'Sporting CP': 'Sporting CP', 'Braga': 'SC Braga',

    # Scotland
    'Celtic': 'Celtic', 'Rangers': 'Rangers',
    'Aberdeen': 'Aberdeen', 'Hearts': 'Heart of Midlothian',
    'Hibernian': 'Hibernian',

    # Belgium
    'Anderlecht': 'Anderlecht', 'Club Brugge': 'Club Brugge',
    'Genk': 'KRC Genk', 'Gent': 'KAA Gent',
    'Antwerp': 'Royal Antwerp', 'Standard': 'Standard Liege',

    # Turkey
    'Galatasaray': 'Galatasaray', 'Fenerbahce': 'Fenerbahce',
    'Besiktas': 'Besiktas', 'Trabzonspor': 'Trabzonspor',

    # USA
    'LA Galaxy': 'LA Galaxy', 'Seattle': 'Seattle Sounders',
    'Portland': 'Portland Timbers', 'Sporting KC': 'Sporting Kansas City',
    'NY Red Bulls': 'New York Red Bulls', 'NYCFC': 'New York City FC',
    'Inter Miami': 'Inter Miami CF',

    # Brazil
    'Flamengo': 'Flamengo', 'Palmeiras': 'Palmeiras',
    'Corinthians': 'Corinthians', 'Sao Paulo': 'Sao Paulo',
    'Santos': 'Santos', 'Gremio': 'Gremio',

    # Argentina
    'Boca Juniors': 'Boca Juniors', 'River Plate': 'River Plate',
    'Racing Club': 'Racing Club', 'Independiente': 'Independiente',
}

def build_team_mapping(conn):
    """Build mapping from Football-Data names to SofaScore names using manual + fuzzy."""
    # Get all SofaScore team names from walkforward_state
    sofa_teams = [r[0] for r in conn.execute(
        "SELECT DISTINCT team_name FROM walkforward_state"
    ).fetchall()]

    # Get all Football-Data team names
    fd_teams = set()
    for f in os.listdir(DATA_DIR):
        if not f.endswith('.csv'):
            continue
        try:
            df = pd.read_csv(os.path.join(DATA_DIR, f), encoding='latin1', nrows=0)
            cols = df.columns.tolist()
            ht = 'HomeTeam' if 'HomeTeam' in cols else ('Home' if 'Home' in cols else None)
            at = 'AwayTeam' if 'AwayTeam' in cols else ('Away' if 'Away' in cols else None)
            if ht:
                vals = pd.read_csv(os.path.join(DATA_DIR, f), usecols=[ht], encoding='latin1')
                fd_teams.update(vals[ht].dropna().unique())
            if at and at != ht:
                vals = pd.read_csv(os.path.join(DATA_DIR, f), usecols=[at], encoding='latin1')
                fd_teams.update(vals[at].dropna().unique())
        except:
            pass

    # Create mapping table
    conn.execute("DROP TABLE IF EXISTS team_name_mapping")
    conn.execute("""
        CREATE TABLE team_name_mapping (
            fd_name TEXT PRIMARY KEY,
            sofa_name TEXT,
            confidence REAL DEFAULT 1.0
        )
    """)

    # Load all FD matches into memory for head-to-head inference
    df = parse_all()
    fd_matches = df[df['Date'].notna() & df['HomeTeam'].notna() & df['AwayTeam'].notna()].copy()
    fd_matches['date'] = pd.to_datetime(fd_matches['Date']).dt.strftime('%Y-%m-%d')
    print(f'  Loaded {len(fd_matches)} FD matches for head-to-head inference')

    # Load all SofaScore matches
    sofa_matches = conn.execute("""
        SELECT date, home_team, away_team FROM sofa_historical_results
    """).fetchall()
    date_match_index = {}  # date -> [(home, away)]
    for d, h, a in sofa_matches:
        date_match_index.setdefault(d, []).append((h, a))
    print(f'  Loaded {len(sofa_matches)} SofaScore matches for head-to-head inference')

    inserted = set()

    def insert_mapping(fd_n, sofa_n, conf):
        key = str(fd_n).strip()
        if key and key not in inserted:
            conn.execute("INSERT OR REPLACE INTO team_name_mapping VALUES (?, ?, ?)",
                        (key, sofa_n, conf))
            inserted.add(key)
            return True
        return False

    # Phase 1: Manual mappings
    for fd_name, sofa_name in MANUAL_MAP.items():
        insert_mapping(fd_name, sofa_name, 1.0)

    # Phase 2: High-confidence fuzzy (ratio > 0.85)
    import difflib
    def norm(s):
        return re.sub(r'\s+', ' ', str(s).lower().replace(' fc', '').replace(' cf', '').replace(' afc', '')
                      .replace(' rc', '').replace(' fc', '').replace(' ac', '').replace(' as', '')).strip()

    unmapped_fuzzy = []
    for fd_name in sorted(fd_teams):
        fd_str = str(fd_name).strip()
        if not fd_str or fd_str in inserted:
            continue
        nfd = norm(fd_str)
        best = None
        best_score = 0
        for st in sofa_teams:
            nst = norm(st)
            score = difflib.SequenceMatcher(None, nfd, nst).ratio()
            if score > best_score and score > 0.85:
                best_score = score
                best = st
        if best:
            insert_mapping(fd_str, best, round(best_score, 3))
        else:
            unmapped_fuzzy.append(fd_str)

    print(f'  Phase 2 (high-conf fuzzy): {len(inserted)} mapped, {len(unmapped_fuzzy)} remaining')

    # Phase 3: Head-to-head inference via date matching
    h2h_count = 0
    for _, row in fd_matches.iterrows():
        fd_h = str(row['HomeTeam']).strip()
        fd_a = str(row['AwayTeam']).strip()
        d = row['date']

        if fd_h in inserted and fd_a in inserted:
            continue
        if d not in date_match_index:
            continue

        sofa_h = conn.execute("SELECT sofa_name FROM team_name_mapping WHERE fd_name = ?", (fd_h,)).fetchone()
        sofa_a = conn.execute("SELECT sofa_name FROM team_name_mapping WHERE fd_name = ?", (fd_a,)).fetchone()
        sofa_h = sofa_h[0] if sofa_h else None
        sofa_a = sofa_a[0] if sofa_a else None

        for s_h, s_a in date_match_index[d]:
            if sofa_h and fd_a not in inserted:
                if sofa_h == s_h:
                    insert_mapping(fd_a, s_a, 0.95)
                    h2h_count += 1
                elif sofa_h == s_a:
                    insert_mapping(fd_a, s_h, 0.95)
                    h2h_count += 1
            if sofa_a and fd_h not in inserted:
                if sofa_a == s_a:
                    insert_mapping(fd_h, s_h, 0.95)
                    h2h_count += 1
                elif sofa_a == s_h:
                    insert_mapping(fd_h, s_a, 0.95)
                    h2h_count += 1

    print(f'  Phase 3 (head-to-head): {h2h_count} new mappings')

    # Phase 4: Lower-confidence fuzzy for remaining (ratio > 0.7)
    unmapped_final = []
    for fd_str in unmapped_fuzzy:
        if fd_str in inserted:
            continue
        nfd = norm(fd_str)
        best = None
        best_score = 0
        for st in sofa_teams:
            nst = norm(st)
            score = difflib.SequenceMatcher(None, nfd, nst).ratio()
            if score > best_score and score > 0.7:
                best_score = score
                best = st
        if best:
            insert_mapping(fd_str, best, round(best_score, 3))
        else:
            unmapped_final.append(fd_str)

    # Phase 5: Fallback
    for fd_str in unmapped_final:
        if fd_str not in inserted:
            insert_mapping(fd_str, fd_str, 0.0)

    conn.commit()
    final_count = conn.execute("SELECT COUNT(*) FROM team_name_mapping").fetchone()[0]
    correct = conn.execute("SELECT COUNT(*) FROM team_name_mapping WHERE confidence > 0.85").fetchone()[0]
    print(f'Mapped {final_count} teams ({len(fd_teams)} FD -> {len(sofa_teams)} SofaScore) — {correct} high-confidence')
    return final_count

# ── Main Integration ──
def integrate():
    """Download → Parse → Map → Store → Return feature count."""
    conn = sqlite3.connect(DB)

    # 1. Download if needed
    csv_count = len([f for f in os.listdir(DATA_DIR) if f.endswith('.csv')])
    if csv_count < 10:
        print('Downloading Football-Data CSVs...')
        download_csvs()
    else:
        print(f'Already have {csv_count} CSVs')

    # 2. Parse all
    print('Parsing CSVs...')
    df = parse_all()
    df = df[df['Date'].notna()].copy()
    print(f'Parsed {len(df)} matches from Football-Data')

    # 3. Store raw
    conn.execute("""
        CREATE TABLE IF NOT EXISTS football_data_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_code TEXT, country TEXT, league TEXT,
            date TEXT, home_team TEXT, away_team TEXT,
            home_goals REAL, away_goals REAL, result TEXT,
            home_shots REAL, away_shots REAL,
            home_sot REAL, away_sot REAL,
            home_fouls REAL, away_fouls REAL,
            home_corners REAL, away_corners REAL,
            home_yellow REAL, away_yellow REAL,
            home_red REAL, away_red REAL,
            b365h REAL, b365d REAL, b365a REAL,
            avgh REAL, avgd REAL, avga REAL,
            maxh REAL, maxd REAL, maxa REAL
        )
    """)
    conn.execute("DELETE FROM football_data_matches")
    insert_sql = """
        INSERT INTO football_data_matches
        (league_code, country, league, date, home_team, away_team,
         home_goals, away_goals, result,
         home_shots, away_shots, home_sot, away_sot,
         home_fouls, away_fouls, home_corners, away_corners,
         home_yellow, away_yellow, home_red, away_red,
         b365h, b365d, b365a, avgh, avgd, avga, maxh, maxd, maxa)
        VALUES (?,?,?,?,?,?, ?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?,?)
    """
    batch = []
    for _, r in df.iterrows():
        batch.append((
            r.get('LeagueCode', ''), r.get('Country', ''), r.get('League', ''),
            r.get('DateStr', ''), r.get('HomeTeam', ''), r.get('AwayTeam', ''),
            safe_float(r.get('FTHG')), safe_float(r.get('FTAG')), r.get('FTR', ''),
            safe_float(r.get('HS')), safe_float(r.get('AS')),
            safe_float(r.get('HST')), safe_float(r.get('AST')),
            safe_float(r.get('HF')), safe_float(r.get('AF')),
            safe_float(r.get('HC')), safe_float(r.get('AC')),
            safe_float(r.get('HY')), safe_float(r.get('AY')),
            safe_float(r.get('HR')), safe_float(r.get('AR')),
            safe_float(r.get('B365H')), safe_float(r.get('B365D')), safe_float(r.get('B365A')),
            safe_float(r.get('AvgH')), safe_float(r.get('AvgD')), safe_float(r.get('AvgA')),
            safe_float(r.get('MaxH')), safe_float(r.get('MaxD')), safe_float(r.get('MaxA')),
        ))
        if len(batch) >= 500:
            conn.executemany(insert_sql, batch)
            batch = []
    if batch:
        conn.executemany(insert_sql, batch)
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM football_data_matches").fetchone()[0]
    print(f'Stored {total} matches in football_data_matches')

    # 4. Build team mapping
    build_team_mapping(conn)

    # 5. Count overlap
    overlap = conn.execute("""
        SELECT COUNT(*) FROM sofa_historical_results r
        WHERE EXISTS (
            SELECT 1 FROM football_data_matches fd
            JOIN team_name_mapping mh ON mh.fd_name = fd.home_team AND mh.sofa_name = r.home_team
            JOIN team_name_mapping ma ON ma.fd_name = fd.away_team AND ma.sofa_name = r.away_team
            WHERE fd.date = r.date
        )
    """).fetchone()[0]
    total_sofa = conn.execute("SELECT COUNT(*) FROM sofa_historical_results").fetchone()[0]
    print(f'Overlap: {overlap}/{total_sofa} matches ({100*overlap/total_sofa:.1f}%)')

    conn.close()
    return overlap

def safe_float(v):
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except:
        return None

if __name__ == '__main__':
    integrate()
