#!/usr/bin/env python3
"""Phase 1b: ClubElo download via soccerdata + direct CSV."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
print('PHASE 1b: ClubElo - Downloading Elo Ratings')
print('=' * 60)

import sqlite3, os, time, json, hashlib
from datetime import datetime

BASE = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor'
DB_PATH = os.path.join(BASE, 'scrape_cache.db')


def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')
    return conn


def hash_row(row_dict):
    raw = json.dumps(row_dict, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def upsert_source(conn, table, data, conflict_col='hash'):
    cols = list(data.keys())
    placeholders = ','.join(['?'] * len(cols))
    update_cols = ','.join([f'{c}=excluded.{c}' for c in cols if c != conflict_col])
    try:
        conn.execute(f'''INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT({conflict_col}) DO UPDATE SET {update_cols}''', [data[c] for c in cols])
    except:
        pass


# Method 1: Try soccerdata.ClubElo
try:
    import soccerdata as sd
    elo = sd.ClubElo()
    
    conn = db_conn()
    total = 0
    
    # Fetch multiple dates to get historical trends
    dates = ['2024-01-01', '2024-06-01', '2025-01-01', '2025-06-01', '2026-01-01', '2026-06-01']
    
    for date_str in dates:
        try:
            ratings = elo.read_by_date(date_str)
            if ratings is None or ratings.empty:
                continue
            
            upserted = 0
            for team_name, row in ratings.iterrows():
                rank_val = row.get('rank', row.get('elo_rank', 0))
                if rank_val is None or (isinstance(rank_val, float) and str(rank_val) == 'nan'):
                    rank_val = 0
                record = {
                    'team': str(team_name)[:100],
                    'country': str(row.get('country', row.get('league', '')))[:50],
                    'match_date': date_str,
                    'elo': float(row.get('elo', 1500)),
                    'elo_rank': int(float(rank_val)),
                }
                record['hash'] = hash_row(record)
                upsert_source(conn, 'source_clubelo_enhanced', record)
                upserted += 1
            
            conn.commit()
            total += upserted
            print(f'  OK {date_str}: {upserted} teams')
        except Exception as e:
            print(f'  WARN {date_str}: {e}')
    
    print(f'\nTotal ClubElo: {total} ratings')
    conn.close()
    
except ImportError:
    print('soccerdata not available, trying direct CSV...')
    
    # Method 2: Direct CSV download
    import urllib.request, csv
    
    url = 'http://clubelo.com/Data/ClubElo.csv'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            content = raw.decode('utf-8', errors='replace')
        
        conn = db_conn()
        reader = csv.DictReader(io.StringIO(content))
        total = 0
        for row in reader:
            record = {
                'team': row.get('Team', row.get('Club', row.get('team', '')))[:100],
                'country': row.get('Country', row.get('country', ''))[:50],
                'match_date': row.get('Date', row.get('date', datetime.now().strftime('%Y-%m-%d')))[:10],
                'elo': float(row.get('Elo', row.get('elo', '1500'))),
                'elo_rank': int(row.get('Rank', row.get('rank', '0'))),
            }
            record['hash'] = hash_row(record)
            upsert_source(conn, 'source_clubelo_enhanced', record)
            total += 1
        
        conn.commit()
        conn.close()
        print(f'\nTotal ClubElo (direct CSV): {total} teams')
    except Exception as e:
        print(f'ERROR: {e}')
