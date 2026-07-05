"""Diagnose _load_training_data performance"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import sqlite3

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)

t0 = time.time()

# 1. Count matches
n = conn.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE home_score IS NOT NULL').fetchone()[0]
print(f'[1] Matches: {n:,} ({time.time()-t0:.1f}s)')

# 2. Load matches into DataFrame
import pandas as pd
query = '''
SELECT r.id, r.home_team, r.away_team, r.home_score, r.away_score, r.date
FROM sofa_historical_results r
WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL
  AND r.home_score >= 0 AND r.away_score >= 0
  AND r.status_type = 'finished'
ORDER BY r.start_timestamp
'''
t1 = time.time()
df = pd.read_sql_query(query, conn)
print(f'[2] DataFrame: {len(df):,} ({time.time()-t1:.1f}s)')

# 3. Pre-load stats
t2 = time.time()
stats = {}
cur = conn.execute('SELECT event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot, home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls FROM sofa_match_stats')
for row in cur.fetchall():
    stats[row[0]] = row[1:]
print(f'[3] Stats: {len(stats):,} ({time.time()-t2:.1f}s)')

# 4. Pre-load lineups
t3 = time.time()
lineups = {}
cur = conn.execute('SELECT event_id, home_formation, away_formation FROM sofa_lineups')
for row in cur.fetchall():
    lineups[row[0]] = (row[1], row[2])
print(f'[4] Lineups (formations): {len(lineups):,} ({time.time()-t3:.1f}s)')

# 5. Pre-load lineup players + JSON parse
t4 = time.time()
lineup_players = {}
import json
cur = conn.execute('SELECT event_id, home_players_json, away_players_json FROM sofa_lineups')
for row in cur.fetchall():
    eid = row[0]
    try:
        hpj = json.loads(row[1]) if row[1] else []
        apj = json.loads(row[2]) if row[2] else []
    except:
        continue
    h_starters = []
    for p in hpj:
        if isinstance(p, dict) and not p.get('substitute', False):
            pl = p.get('player', {})
            name = pl.get('name', '')
            if name: h_starters.append(name)
    a_starters = []
    for p in apj:
        if isinstance(p, dict) and not p.get('substitute', False):
            pl = p.get('player', {})
            name = pl.get('name', '')
            if name: a_starters.append(name)
    lineup_players[eid] = (h_starters, a_starters)
print(f'[5] Lineup players: {len(lineup_players):,} ({time.time()-t4:.1f}s)')

# 6. Pre-load odds
t5 = time.time()
odds = {}
cur = conn.execute('''
    SELECT s.id, fd.b365h, fd.b365d, fd.b365a, fd.avgh, fd.avgd, fd.avga
    FROM football_data_matches fd
    INNER JOIN team_name_mapping hm ON fd.home_team = hm.fd_name AND hm.confidence >= 0.85
    INNER JOIN team_name_mapping am ON fd.away_team = am.fd_name AND am.confidence >= 0.85
    INNER JOIN sofa_historical_results s
        ON s.date = fd.date
        AND s.home_team = hm.sofa_name
        AND s.away_team = am.sofa_name
    WHERE fd.date >= '2024-06-15' AND fd.date <= '2026-06-14'
    AND fd.b365h IS NOT NULL AND fd.b365h > 0
')
for row in cur.fetchall():
    odds[row[0]] = row[1:]
print(f'[6] Odds: {len(odds):,} ({time.time()-t5:.1f}s)')

# 7. Forebet
t6 = time.time()
forebet = {}
cur = conn.execute('SELECT date, home_team, prob_h, prob_d, prob_a FROM forebet_predictions')
for row in cur.fetchall():
    forebet[(row[0], row[1].upper())] = (row[2], row[3], row[4])
print(f'[7] Forebet: {len(forebet):,} ({time.time()-t6:.1f}s)')

# 8. Vehicle weather, team venue
t7 = time.time()
venue_weather = {}
try:
    cur = conn.execute('SELECT date, lat, lon, temp_max, temp_min, precip, wind, humidity FROM venue_weather')
    for row in cur.fetchall():
        venue_weather[(row[0], row[1], row[2])] = (row[3], row[4], row[5], row[6], row[7])
except: pass
print(f'[8] Weather: {len(venue_weather):,} ({time.time()-t7:.1f}s)')

team_venue = {}
cur = conn.execute('SELECT team_name, lat, lon FROM team_venue')
for row in cur.fetchall():
    team_venue[row[0]] = (row[1], row[2])
print(f'[9] Team venue: {len(team_venue):,} ({time.time()-t8:.1f}s)' if 't8' in dir() else f'[9] Team venue: {len(team_venue):,}')

# 10. Quick benchmark: 100 matches from main loop
t9 = time.time()
sample = 0
for _, row in df.iterrows():
    mid = row['id']; ht = row['home_team']; at = row['away_team']; dt = row['date']
    hs = row['home_score']; aws = row['away_score']
    
    # walkforward query
    cur = conn.execute('SELECT elo, rolling_xg_for, rolling_xg_against, form_points, matches_played, rolling_shots_for, rolling_shots_against FROM walkforward_state WHERE team_name=? AND date<=? ORDER BY date DESC LIMIT 1', (ht, dt))
    h = cur.fetchone()
    cur.execute('SELECT elo, rolling_xg_for, rolling_xg_against, form_points, matches_played, rolling_shots_for, rolling_shots_against FROM walkforward_state WHERE team_name=? AND date<=? ORDER BY date DESC LIMIT 1', (at, dt))
    a = cur.fetchone()
    if not h or not a: continue
    
    sample += 1
    if sample >= 100:
        break

elapsed = time.time() - t9
print(f'[10] 100 matches processed: {elapsed:.2f}s ({elapsed/100*1000:.1f}ms/match)')

total_est = elapsed / 100 * n / 60
print(f'    Estimated total: {total_est:.0f} minutes')

conn.close()
print(f'\nTotal time: {time.time()-t0:.1f}s')
