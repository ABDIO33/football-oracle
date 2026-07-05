#!/usr/bin/env python3
"""Phase 1a: Football-data.co.uk CSV download + integration."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
print('PHASE 1a: Football Data UK - Direct CSV Download')
print('=' * 60)

import urllib.request, urllib.error, csv, io as io2, gzip, json, sqlite3, os, time, hashlib

BASE = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor'
DB_PATH = os.path.join(BASE, 'scrape_cache.db')


def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')
    return conn


def safe_int(v):
    if v is None: return None
    try: return int(float(str(v).strip()))
    except: return None


def safe_float(v):
    if v is None: return None
    try: return float(str(v).strip())
    except: return None


def hash_row(row_dict):
    raw = json.dumps(row_dict, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def upsert_source(conn, table, data, conflict_col='hash'):
    cols = list(data.keys())
    placeholders = ','.join(['?'] * len(cols))
    update_cols = ','.join([f'{c}=excluded.{c}' for c in cols if c != conflict_col])
    try:
        conn.execute(f'''INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT({conflict_col}) DO UPDATE SET {update_cols}''', [data[c] for c in cols])
    except Exception as e:
        pass


conn = db_conn()
total = 0
errors = 0

# All seasons to try
seasons = ['2526', '2425', '2324', '2223', '2122', '2021', '1920', '1819', '1718']
leagues = ['E0', 'E1', 'E2', 'E3', 'EC', 'SC0', 'SC1', 'SC2', 'SC3',
           'D1', 'D2', 'D3', 'SP1', 'SP2', 'I1', 'I2', 'F1', 'F2',
           'N1', 'B1', 'P1', 'T1', 'G1', 'MLS']

for season in seasons:
    for league in leagues:
        url = f'https://www.football-data.co.uk/mmz4281/{season}/{league}.csv'
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                if resp.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
                content = raw.decode('utf-8-sig', errors='replace')

            reader = csv.DictReader(io2.StringIO(content))
            upserted = 0
            for row in reader:
                record = {
                    'league': league,
                    'season': season,
                    'div': row.get('Div', '') or league,
                    'match_date': row.get('Date', '')[:10] if row.get('Date') else None,
                    'home_team': row.get('HomeTeam', row.get('Home', '')),
                    'away_team': row.get('AwayTeam', row.get('Away', '')),
                    'fthg': safe_int(row.get('FTHG')),
                    'ftag': safe_int(row.get('FTAG')),
                    'hthg': safe_int(row.get('HTHG')),
                    'htag': safe_int(row.get('HTAG')),
                    'hs': safe_int(row.get('HS')),
                    'as_': safe_int(row.get('AS')),
                    'hst': safe_int(row.get('HST')),
                    'ast': safe_int(row.get('AST')),
                    'hc': safe_int(row.get('HC')),
                    'ac': safe_int(row.get('AC')),
                    'hf': safe_int(row.get('HF')),
                    'af': safe_int(row.get('AF')),
                    'hy': safe_int(row.get('HY')),
                    'ay': safe_int(row.get('AY')),
                    'hr': safe_int(row.get('HR')),
                    'ar': safe_int(row.get('AR')),
                    'b365h': safe_float(row.get('B365H', row.get('BWH', '0'))),
                    'b365d': safe_float(row.get('B365D', row.get('BWD', '0'))),
                    'b365a': safe_float(row.get('B365A', row.get('BWA', '0'))),
                }
                record['hash'] = hash_row(record)
                upsert_source(conn, 'source_football_data_uk', record)
                upserted += 1

            conn.commit()
            total += upserted
            print(f'  OK {season}/{league}: {upserted} rows')
        except urllib.error.HTTPError as e:
            errors += 1
        except Exception as e:
            errors += 1

print(f'\nTotal imported: {total} rows (errors: {errors})')
conn.close()
