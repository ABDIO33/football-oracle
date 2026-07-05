#!/usr/bin/env python3
"""Phase 1c: StatsBomb - Full integration into source_statsbomb_enhanced."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
print('PHASE 1c: StatsBomb - Full Integration')
print('=' * 60)

import sqlite3, os, json, hashlib

BASE = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor'
DB_PATH = os.path.join(BASE, 'scrape_cache.db')


def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')
    return conn


def safe_int(v):
    if v is None: return None
    try: return int(float(str(v)))
    except: return None


def safe_float(v):
    if v is None: return None
    try: return float(str(v))
    except: return None


def hash_row(d):
    return hashlib.md5(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:16]


def upsert_source(conn, table, data, conflict_col='hash'):
    cols = list(data.keys())
    placeholders = ','.join(['?'] * len(cols))
    update_cols = ','.join([f'{c}=excluded.{c}' for c in cols if c != conflict_col])
    try:
        conn.execute(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({placeholders}) ON CONFLICT({conflict_col}) DO UPDATE SET {update_cols}',
                     [data[c] for c in cols])
    except:
        pass


conn = db_conn()

# Check what we have
match_count = conn.execute('SELECT COUNT(*) FROM statsbomb_matches').fetchone()[0]
event_count = conn.execute('SELECT COUNT(*) FROM statsbomb_events').fetchone()[0]
source_count = conn.execute('SELECT COUNT(*) FROM source_statsbomb_enhanced').fetchone()[0]

print(f'  StatsBomb matches: {match_count}')
print(f'  StatsBomb events: {event_count}')
print(f'  Already in source table: {source_count}')

if source_count >= match_count or match_count == 0:
    print('  Already integrated or no matches. Skipping.')
    conn.close()
    exit(0)

matches = conn.execute('''
    SELECT m.match_id, m.competition_name, m.season_name, m.match_date,
           m.home_team, m.away_team, m.home_score, m.away_score
    FROM statsbomb_matches m
    ORDER BY m.match_id
''').fetchall()

total = 0
errors = 0

for m in matches:
    mid = m[0]
    try:
        # Get home/away team names
        h_team, a_team = m[4], m[5]
        
        # Aggregate home events
        h_row = conn.execute('''
            SELECT 
                SUM(xg) as total_xg,
                SUM(CASE WHEN event_type = 'Shot' THEN 1 ELSE 0 END) as shots,
                SUM(CASE WHEN event_type = 'Shot' AND outcome IN ('Goal') THEN 1 ELSE 0 END) as goals,
                SUM(CASE WHEN event_type = 'Shot' AND outcome IN ('Saved','Saved To Post','Saved to Post','Wayward','Blocked') THEN 1 ELSE 0 END) as shots_ot,
                SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END) as passes,
                SUM(CASE WHEN event_type = 'Foul' OR event_type = 'Foul Committed' THEN 1 ELSE 0 END) as fouls,
                SUM(CASE WHEN event_type = 'Corner' THEN 1 ELSE 0 END) as corners,
                SUM(CASE WHEN event_type = 'Card' AND outcome IN ('Yellow','Second Yellow') THEN 1 ELSE 0 END) as yellows,
                SUM(CASE WHEN event_type = 'Card' AND outcome = 'Red' THEN 1 ELSE 0 END) as reds,
                SUM(CASE WHEN event_type = 'Offside' THEN 1 ELSE 0 END) as offsides,
                SUM(CASE WHEN event_type = 'Clearance' THEN 1 ELSE 0 END) as clearances,
                SUM(CASE WHEN event_type = 'Interception' THEN 1 ELSE 0 END) as interceptions,
                SUM(CASE WHEN event_type = 'Tackle' THEN 1 ELSE 0 END) as tackles,
                SUM(CASE WHEN event_type = 'Dribble' THEN 1 ELSE 0 END) as dribbles,
                SUM(CASE WHEN event_type = 'Goal Keeper' OR event_type = 'Goalkeeper' THEN 1 ELSE 0 END) as goal_kicks
            FROM statsbomb_events 
            WHERE match_id = ? AND team = ?
        ''', (mid, h_team)).fetchone()
        
        a_row = conn.execute('''
            SELECT 
                SUM(xg) as total_xg,
                SUM(CASE WHEN event_type = 'Shot' THEN 1 ELSE 0 END) as shots,
                SUM(CASE WHEN event_type = 'Shot' AND outcome IN ('Goal') THEN 1 ELSE 0 END) as goals,
                SUM(CASE WHEN event_type = 'Shot' AND outcome IN ('Saved','Saved To Post','Saved to Post','Wayward','Blocked') THEN 1 ELSE 0 END) as shots_ot,
                SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END) as passes,
                SUM(CASE WHEN event_type = 'Foul' OR event_type = 'Foul Committed' THEN 1 ELSE 0 END) as fouls,
                SUM(CASE WHEN event_type = 'Corner' THEN 1 ELSE 0 END) as corners,
                SUM(CASE WHEN event_type = 'Card' AND outcome IN ('Yellow','Second Yellow') THEN 1 ELSE 0 END) as yellows,
                SUM(CASE WHEN event_type = 'Card' AND outcome = 'Red' THEN 1 ELSE 0 END) as reds,
                SUM(CASE WHEN event_type = 'Offside' THEN 1 ELSE 0 END) as offsides,
                SUM(CASE WHEN event_type = 'Clearance' THEN 1 ELSE 0 END) as clearances,
                SUM(CASE WHEN event_type = 'Interception' THEN 1 ELSE 0 END) as interceptions,
                SUM(CASE WHEN event_type = 'Tackle' THEN 1 ELSE 0 END) as tackles,
                SUM(CASE WHEN event_type = 'Dribble' THEN 1 ELSE 0 END) as dribbles,
                SUM(CASE WHEN event_type = 'Goal Keeper' OR event_type = 'Goalkeeper' THEN 1 ELSE 0 END) as goal_kicks
            FROM statsbomb_events 
            WHERE match_id = ? AND team = ?
        ''', (mid, a_team)).fetchone()
        
        if h_row is None and a_row is None:
            errors += 1
            continue
        
        h_data = h_row if h_row else tuple([None]*15)
        a_data = a_row if a_row else tuple([None]*15)
        
        record = {
            'match_id': mid,
            'competition': str(m[1])[:100],
            'season': str(m[2])[:50],
            'match_date': str(m[3])[:10] if m[3] else None,
            'home_team': str(h_team)[:100],
            'away_team': str(a_team)[:100],
            'home_score': safe_int(m[6]),
            'away_score': safe_int(m[7]),
            'home_xg_total': safe_float(h_data[0]),
            'home_shots': safe_int(h_data[1]),
            'home_shots_ot': safe_int(h_data[3]),
            'home_passes': safe_int(h_data[4]),
            'home_fouls': safe_int(h_data[5]),
            'home_corners': safe_int(h_data[6]),
            'home_yellows': safe_int(h_data[7]),
            'home_reds': safe_int(h_data[8]),
            'home_offsides': safe_int(h_data[9]),
            'home_clearances': safe_int(h_data[10]),
            'home_interceptions': safe_int(h_data[11]),
            'home_tackles': safe_int(h_data[12]),
            'home_dribbles': safe_int(h_data[13]),
            'home_goal_kicks': safe_int(h_data[14]),
            'away_xg_total': safe_float(a_data[0]),
            'away_shots': safe_int(a_data[1]),
            'away_shots_ot': safe_int(a_data[3]),
            'away_passes': safe_int(a_data[4]),
            'away_fouls': safe_int(a_data[5]),
            'away_corners': safe_int(a_data[6]),
            'away_yellows': safe_int(a_data[7]),
            'away_reds': safe_int(a_data[8]),
            'away_offsides': safe_int(a_data[9]),
            'away_clearances': safe_int(a_data[10]),
            'away_interceptions': safe_int(a_data[11]),
            'away_tackles': safe_int(a_data[12]),
            'away_dribbles': safe_int(a_data[13]),
            'away_goal_kicks': safe_int(a_data[14]),
            'statsbomb_match_id': str(mid),
        }
        record['hash'] = hash_row(record)
        upsert_source(conn, 'source_statsbomb_enhanced', record)
        total += 1
        
        if total % 200 == 0:
            conn.commit()
            print(f'  Integrated {total}/{match_count} matches...')
        
    except Exception as e:
        errors += 1
        if errors % 50 == 1:
            print(f'  Error on match {mid}: {e}')

conn.commit()
conn.close()

print(f'\nStatsBomb integrated: {total} matches (errors: {errors})')
