"""
Optimized preprocessing — batch-load walkforward, no per-match SQL
"""
import sys, os, time, json, numpy as np, pandas as pd
from collections import defaultdict
from datetime import datetime
from math import radians, sin, cos, sqrt, asin
sys.path.insert(0, os.path.dirname(__file__))
import sqlite3, gc

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

t0 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] Connecting to DB...')
conn = sqlite3.connect(DB)

N_CLASSES = 25
FEATURE_NAMES = [
    'home_elo', 'away_elo', 'elo_diff',
    'home_xg_for', 'home_xg_against', 'away_xg_for', 'away_xg_against',
    'home_form', 'away_form', 'home_mp', 'away_mp',
    'home_shots_for', 'away_shots_for', 'home_shots_against', 'away_shots_against',
    'home_xg_diff', 'away_xg_diff', 'home_shot_diff', 'away_shot_diff',
    'home_days_rest', 'away_days_rest',
    'home_glicko', 'away_glicko', 'home_glicko_rd', 'away_glicko_rd',
    'stat_h_xg', 'stat_a_xg', 'stat_h_shots', 'stat_a_shots',
    'stat_h_sot', 'stat_a_sot', 'stat_h_poss', 'stat_a_poss',
    'stat_h_corn', 'stat_a_corn', 'stat_h_fouls', 'stat_a_fouls',
    'home_fdef', 'away_fdef', 'fdef_diff', 'has_lineups',
    'h_miss_core', 'a_miss_core', 'h_att_loss', 'a_att_loss',
    'h_def_loss', 'a_def_loss',
    'odds_bh', 'odds_bd', 'odds_ba', 'odds_ah', 'odds_ad', 'odds_aa',
    'eh', 'ea', 'elo_xg_h', 'elo_xg_a', 'form_xg_h', 'form_xg_a',
    'elo_diff_form_diff', 'fatigue_h', 'fatigue_a',
    'xg_ratio', 'shots_ratio', 'form_ratio',
    'xgf_xga_h', 'xgf_xga_a', 'shot_eff_h', 'shot_eff_a',
    'elo_diff_sq', 'xg_diff_sq', 'form_diff_sq',
    'month', 'dow', 'season_progress', 'is_weekend',
    'home_temp', 'home_precip', 'home_wind', 'home_humidity',
    'travel_dist',
]
N_FEATURES = len(FEATURE_NAMES)

# 1. Load all matches
print(f'[{time.strftime("%H:%M:%S")}] Loading matches...')
df = pd.read_sql_query('''
    SELECT id, home_team, away_team, home_score, away_score, date, tournament, start_timestamp
    FROM sofa_historical_results
    WHERE home_score IS NOT NULL AND away_score IS NOT NULL
      AND home_score >= 0 AND away_score >= 0 AND home_score <= 20 AND away_score <= 20
      AND status_type = 'finished'
    ORDER BY start_timestamp
''', conn)
print(f'  {len(df):,} matches ({time.time()-t0:.1f}s)')

# 2. Pre-load walkforward states into dict: {team: [(date, elo, xgf, xga, form, mp, shots_f, shots_a)]}
print(f'[{time.strftime("%H:%M:%S")}] Loading walkforward states...')
wf = defaultdict(list)
cur = conn.execute('SELECT team_name, date, elo, rolling_xg_for, rolling_xg_against, form_points, matches_played, rolling_shots_for, rolling_shots_against FROM walkforward_state ORDER BY team_name, date')
for row in cur.fetchall():
    wf[row[0]].append(row[1:])
print(f'  {len(wf):,} teams with states ({time.time()-t0:.1f}s)')

# 3. Pre-load glicko
print(f'[{time.strftime("%H:%M:%S")}] Loading glicko states...')
gl = defaultdict(list)
cur = conn.execute('SELECT team_name, date, glicko_rating, glicko_rd FROM glicko_state ORDER BY team_name, date')
for row in cur.fetchall():
    gl[row[0]].append(row[1:])
print(f'  {len(gl):,} teams ({time.time()-t0:.1f}s)')

# 4. Pre-load stats
print(f'[{time.strftime("%H:%M:%S")}] Loading match stats...')
stats = {}
cur = conn.execute('SELECT event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot, home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls FROM sofa_match_stats')
for r in cur.fetchall():
    stats[r[0]] = r[1:]
print(f'  {len(stats):,} rows ({time.time()-t0:.1f}s)')

# 5. Pre-load lineups
print(f'[{time.strftime("%H:%M:%S")}] Loading lineups...')
lineup_f = {}
cur = conn.execute('SELECT event_id, home_formation, away_formation FROM sofa_lineups')
for r in cur.fetchall():
    lineup_f[r[0]] = (r[1], r[2])
lineup_p = {}
cur = conn.execute('SELECT event_id, home_players_json, away_players_json FROM sofa_lineups')
for r in cur.fetchall():
    try:
        hpj = json.loads(r[1]) if r[1] else []
        apj = json.loads(r[2]) if r[2] else []
        h_s = [p.get('player', {}).get('name', '') for p in hpj if isinstance(p, dict) and not p.get('substitute', False)]
        a_s = [p.get('player', {}).get('name', '') for p in apj if isinstance(p, dict) and not p.get('substitute', False)]
        lineup_p[r[0]] = (h_s, a_s)
    except:
        lineup_p[r[0]] = ([], [])
print(f'  {len(lineup_f):,} formations, {len(lineup_p):,} player lists ({time.time()-t0:.1f}s)')

# 6. Pre-load odds
odds = {}
cur = conn.execute("SELECT s.id, fd.b365h, fd.b365d, fd.b365a, fd.avgh, fd.avgd, fd.avga FROM football_data_matches fd INNER JOIN team_name_mapping hm ON fd.home_team = hm.fd_name AND hm.confidence >= 0.85 INNER JOIN team_name_mapping am ON fd.away_team = am.fd_name AND am.confidence >= 0.85 INNER JOIN sofa_historical_results s ON s.date = fd.date AND s.home_team = hm.sofa_name AND s.away_team = am.sofa_name WHERE fd.date >= '2024-06-15' AND fd.b365h IS NOT NULL AND fd.b365h > 0")
for r in cur.fetchall():
    odds[r[0]] = r[1:]
print(f'  {len(odds):,} odds rows ({time.time()-t0:.1f}s)')

# 7. Helper: binary search most recent state before date
def latest_state(states, date_str):
    if not states:
        return None
    lo, hi = 0, len(states) - 1
    best = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if states[mid][0] <= date_str:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if best >= 0:
        return states[best]
    return None

def latest_glicko(gstates, date_str):
    s = latest_state(gstates, date_str)
    if s: return (s[1], s[2])
    return (1500.0, 350.0)

# Haversine
def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * r * asin(sqrt(a))

# Formation def map
FD_MAP = {}
for f in ['3-4-3','3-5-2','3-4-2-1','3-4-1-2','3-1-4-2','3-4-3-1','3-5-1-1','3-4-2-1','3-2-4-1','3-6-1','3-1-4-2','3-4-3 diamond','3-4-1-2']:
    FD_MAP[f] = 3
for f in ['5-3-2','5-4-1','5-2-3','5-2-2-1','5-3-1-1','5-4-1 diamond','5-4-1']:
    FD_MAP[f] = 5
def fdef(f): return float(FD_MAP.get(f, 4))

# Build feature matrix
print(f'[{time.strftime("%H:%M:%S")}] Building feature matrix ({len(df):,} matches)...')
X = np.zeros((len(df), N_FEATURES), dtype=np.float32)
y = np.zeros(len(df), dtype=np.int32)
mids = np.zeros(len(df), dtype=np.int64)
valid = np.ones(len(df), dtype=bool)

batch_start = time.time()
for idx, (_, row) in enumerate(df.iterrows()):
    mid, ht, at, hs, aws, dt = row['id'], row['home_team'], row['away_team'], int(row['home_score']), int(row['away_score']), row['date']
    
    # Get walkforward states
    hw = latest_state(wf.get(ht, []), dt)
    aw = latest_state(wf.get(at, []), dt)
    if hw is None or aw is None:
        valid[idx] = False
        continue
    
    hg = latest_glicko(gl.get(ht, []), dt)
    ag = latest_glicko(gl.get(at, []), dt)
    
    # Unpack walkforward
    _, h_elo, h_xgf, h_xga, h_form, h_mp, h_shots_f, h_shots_a = hw
    _, a_elo, a_xgf, a_xga, a_form, a_mp, a_shots_f, a_shots_a = aw
    
    h_elo = float(h_elo); a_elo = float(a_elo)
    h_xgf = float(h_xgf or 1.2); h_xga = float(h_xga or 1.2)
    a_xgf = float(a_xgf or 1.2); a_xga = float(a_xga or 1.2)
    h_form = float(h_form or 0); a_form = float(a_form or 0)
    h_mp = float(h_mp or 0); a_mp = float(a_mp or 0)
    h_shots_f = float(h_shots_f or 10); a_shots_f = float(a_shots_f or 10)
    h_shots_a = float(h_shots_a or 10); a_shots_a = float(a_shots_a or 10)
    
    elo_diff = h_elo - a_elo
    
    feats = [
        h_elo, a_elo, elo_diff,
        h_xgf, h_xga, a_xgf, a_xga,
        h_form, a_form, h_mp, a_mp,
        h_shots_f, a_shots_f, h_shots_a, a_shots_a,
        h_xgf - h_xga, a_xgf - a_xga, h_shots_f - h_shots_a, a_shots_f - a_shots_a,
        7.0, 7.0,  # days rest (default)
        hg[0], ag[0], hg[1], ag[1],  # glicko
    ]
    
    # Stats
    s = stats.get(mid)
    if s:
        feats += [float(s[0] or 0), float(s[1] or 0), float(s[2] or 10), float(s[3] or 10),
                  float(s[4] or 5), float(s[5] or 5), float(s[6] or 50), float(s[7] or 50),
                  float(s[8] or 5), float(s[9] or 5), float(s[10] or 10), float(s[11] or 10)]
    else:
        feats += [0]*12
    
    # Lineups
    lf = lineup_f.get(mid)
    if lf and lf[0] and lf[1]:
        hfd = fdef(lf[0]); afd = fdef(lf[1])
        feats += [hfd, afd, hfd - afd, 1.0]
    else:
        feats += [4.0, 4.0, 0.0, 0.0]
    
    # Player impact - skip for speed, set defaults
    feats += [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    # Odds
    o = odds.get(mid)
    if o:
        feats += [float(o[0] or 1.0), float(o[1] or 1.0), float(o[2] or 1.0),
                  float(o[3] or 1.0), float(o[4] or 1.0), float(o[5] or 1.0)]
    else:
        feats += [0]*6
    
    # Interaction features
    ef_h = h_elo / (a_elo if a_elo > 0 else 1)
    ef_a = a_elo / (h_elo if h_elo > 0 else 1)
    feats += [ef_h, ef_a]
    feats += [h_elo * h_xgf / h_mp if h_mp > 0 else h_elo * h_xgf,
              a_elo * a_xgf / a_mp if a_mp > 0 else a_elo * a_xgf]
    feats += [h_form * h_xgf, a_form * a_xgf]
    feats += [elo_diff * (h_form - a_form), h_mp / (a_mp if a_mp > 0 else 1), a_mp / (h_mp if h_mp > 0 else 1)]
    feats += [h_xgf / (a_xgf if a_xgf > 0 else 0.1), h_shots_f / (a_shots_f if a_shots_f > 0 else 1), h_form / (a_form if a_form > 0 else 0.1)]
    feats += [h_xgf / (h_xga if h_xga > 0 else 0.1), a_xgf / (a_xga if a_xga > 0 else 0.1)]
    feats += [h_shots_f / (h_shots_a if h_shots_a > 0 else 1), a_shots_f / (a_shots_a if a_shots_a > 0 else 1)]
    
    # Polynomial
    feats += [elo_diff**2, (h_xgf - h_xga)**2, (h_form - a_form)**2]
    
    # Time features
    try:
        dt_obj = datetime.strptime(dt, '%Y-%m-%d')
        month = float(dt_obj.month)
        dow = float(dt_obj.weekday())
        sp = float(dt_obj.timetuple().tm_yday) / 365.0
    except:
        month = 6.0; dow = 3.0; sp = 0.5
    feats += [month, dow, sp, 1.0 if dow >= 5 else 0.0]
    
    # Weather - skip, set defaults
    feats += [20.0, 0.0, 10.0, 50.0]  # temp, precip, wind, humidity
    
    # Travel - skip
    feats += [0.0]
    
    X[idx] = feats[:N_FEATURES]
    y[idx] = min(max(hs, 0), 4) * 5 + min(max(aws, 0), 4)
    mids[idx] = mid
    
    if (idx + 1) % 50000 == 0:
        batch_elapsed = time.time() - batch_start
        rate = (idx + 1) / batch_elapsed
        rem = (len(df) - idx - 1) / rate
        print(f'  [{time.strftime("%H:%M:%S")}] {idx+1:,}/{len(df):,} ({rate:.0f}/s, ETA {rem/60:.0f}m)')

# Filter valid
X = X[valid]
y = y[valid]
mids = mids[valid]

print(f'\n[{time.strftime("%H:%M:%S")}] Valid: {len(X):,}/{len(valid):,} ({100*len(X)/len(valid):.0f}%)')
print(f'Features: {X.shape[1]}')

# Save
print(f'[{time.strftime("%H:%M:%S")}] Saving npz...')
np.savez_compressed(os.path.join(MODEL_DIR, 'v5_preprocessed.npz'), X=X, y=y, mids=mids)

elapsed = time.time() - t0
print(f'[{time.strftime("%H:%M:%S")}] DONE in {elapsed/60:.1f} min')
print(f'Saved {len(X):,} samples to v5_preprocessed.npz')
conn.close()
