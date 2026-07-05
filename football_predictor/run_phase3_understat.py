#!/usr/bin/env python3
"""Phase 3: Understat - Complete Coverage (All leagues, all seasons)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
print('PHASE 3: Understat - Complete Coverage')
print('=' * 60)

import os, time, json, hashlib, sqlite3, re, urllib.request, urllib.error, gzip
from datetime import datetime

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
    except Exception as e:
        pass


def understat_fetch(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://understat.com/',
        'Accept-Encoding': 'gzip',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            try:
                return gzip.decompress(raw).decode('utf-8')
            except:
                return raw.decode('utf-8')
    except:
        return None


conn = db_conn()
total = 0

leagues = ['EPL', 'La_Liga', 'Bundesliga', 'Serie_A', 'Ligue_1', 'RFPL']
seasons = [str(y) for y in range(2014, 2027)]

for league in leagues:
    for season in seasons:
        url = f'https://understat.com/getLeagueData/{league}/{season}'
        html = understat_fetch(url)

        if not html:
            print(f'  NO {league}/{season}: no response')
            time.sleep(1.5)
            continue

        try:
            data = json.loads(html)
        except:
            print(f'  NO {league}/{season}: invalid JSON')
            time.sleep(1.5)
            continue

        match_count = 0

        # Get matches from 'dates' array (primary format)
        matches_list = data.get('dates', [])

        # If no dates, try from teams dict
        if not matches_list:
            teams_dict = data.get('teams', {})
            if isinstance(teams_dict, dict):
                for tid, tdata in teams_dict.items():
                    if isinstance(tdata, dict):
                        for hist_key in ['history', 'matches']:
                            hist = tdata.get(hist_key, [])
                            if isinstance(hist, list):
                                matches_list.extend(hist)

        # If still nothing, try direct list
        if not matches_list:
            if isinstance(data, list):
                matches_list = data

        for match in matches_list:
            if not isinstance(match, dict):
                continue

            try:
                # h/a dict format
                h_data = match.get('h', {}) if isinstance(match.get('h'), dict) else {}
                a_data = match.get('a', {}) if isinstance(match.get('a'), dict) else {}

                home_team = str(h_data.get('title', match.get('h_title', '')))
                away_team = str(a_data.get('title', match.get('a_title', '')))

                if not home_team:
                    continue

                # Goals
                goals_data = match.get('goals', {})
                if isinstance(goals_data, dict):
                    home_goals = safe_int(goals_data.get('h', match.get('goals_h')))
                    away_goals = safe_int(goals_data.get('a', match.get('goals_a')))
                else:
                    home_goals = safe_int(match.get('goals_h'))
                    away_goals = safe_int(match.get('goals_a'))

                # xG
                xg_data = match.get('xG', {})
                if isinstance(xg_data, dict):
                    home_xg = safe_float(xg_data.get('h', match.get('xG_h')))
                    away_xg = safe_float(xg_data.get('a', match.get('xG_a')))
                else:
                    home_xg = safe_float(match.get('xG_h'))
                    away_xg = safe_float(match.get('xG_a'))

                record = {
                    'league': league,
                    'season': safe_int(season),
                    'match_date': str(match.get('datetime', match.get('date', '')))[:10],
                    'home_team': home_team[:100],
                    'away_team': away_team[:100],
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                    'home_xg': home_xg,
                    'away_xg': away_xg,
                }

                # Determine result
                if home_goals is not None and away_goals is not None:
                    if home_goals > away_goals:
                        record['result'] = 'H'
                    elif home_goals < away_goals:
                        record['result'] = 'A'
                    else:
                        record['result'] = 'D'

                record['hash'] = hash_row(record)
                upsert_source(conn, 'source_understat', record)
                match_count += 1
                total += 1

            except Exception as e:
                continue

        conn.commit()
        if match_count > 0:
            print(f'  OK {league}/{season}: {match_count} matches')
        else:
            print(f'  -- {league}/{season}: 0 matches')

        time.sleep(1.5)

conn.close()
print(f'\nTotal Understat matches: {total}')
