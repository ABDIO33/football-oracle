"""
fast_walkforward.py — Ultra-fast Elo-only walkforward
Skips expensive per-match rolling stats queries.
Tracks: Elo, matches played, basic form from scores only.
~10x faster than full walkforward.
"""
import sys, os, sqlite3, json
from collections import defaultdict, deque
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

INITIAL_ELO = 1600.0
K_FACTOR = 32.0
HOME_ELO_ADV = 50.0

def expected_score(rating_a, rating_b):
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

def ts_to_date(ts):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

print("="*60)
print("FAST WALKFORWARD (Elo + Form Only)")
print("="*60)

# 1. Load ALL matches chronologically
print("\n[1] Loading all matches...")
conn = sqlite3.connect(DB)
rows = conn.execute('''
    SELECT id, home_team, away_team, home_score, away_score, start_timestamp, date
    FROM sofa_historical_results
    WHERE status_type = 'finished' AND home_score IS NOT NULL AND away_score IS NOT NULL
    ORDER BY start_timestamp ASC
''').fetchall()
print(f"  Total matches: {len(rows)}")

# 2. Clear old state
print("[2] Clearing old walkforward state...")
conn.execute('DELETE FROM walkforward_state')
conn.execute('DELETE FROM walkforward_progress')
conn.commit()
print("  Cleared.")

# 3. Process all matches in memory
print("[3] Processing matches (in-memory Elo + form)...")

elo = defaultdict(lambda: INITIAL_ELO)
matches_played = defaultdict(int)
# Store last N results for each team: deque of (goals_for, goals_against)
recent_results = defaultdict(lambda: deque(maxlen=20))
form_points = defaultdict(lambda: deque(maxlen=20))

processed = 0
batch = []
BATCH_SIZE = 1000  # how many to commit at once

for idx, (eid, home, away, hs, aws, ts, date_str) in enumerate(rows):
    hs, aws = int(hs), int(aws)
    
    # Compute expected scores
    home_adv = HOME_ELO_ADV
    exp_h = expected_score(elo[home] + home_adv, elo[away])
    exp_a = 1.0 - exp_h
    
    # Actual results
    if hs > aws:
        act_h, act_a = 1.0, 0.0
    elif hs == aws:
        act_h, act_a = 0.5, 0.5
    else:
        act_h, act_a = 0.0, 1.0
    
    # Update Elo
    elo[home] = elo[home] + K_FACTOR * (act_h - exp_h)
    elo[away] = elo[away] + K_FACTOR * (act_a - exp_a)
    matches_played[home] += 1
    matches_played[away] += 1
    
    # Track recent results for form computation
    recent_results[home].append((hs, aws))
    recent_results[away].append((aws, hs))
    form_points[home].append(1 if hs > aws else 0.5 if hs == aws else 0)
    form_points[away].append(1 if aws > hs else 0.5 if aws == hs else 0)
    
    # Compute rolling form from in-memory recent results
    def compute_form(team):
        rr = list(recent_results[team])
        if not rr:
            return 0.5, 0, 0, 0, 0, 0
        gf = sum(r[0] for r in rr)
        ga = sum(r[1] for r in rr)
        pts = sum(form_points[team])
        n = len(rr)
        return pts / (n * 3) if n else 0.5, pts, n, gf, ga, gf - ga
    
    h_form, h_pts, h_n, h_gf, h_ga, h_gd = compute_form(home)
    a_form, a_pts, a_n, a_gf, a_ga, a_gd = compute_form(away)
    
    # Build state snapshot
    batch.append((home, date_str, round(elo[home], 2), matches_played[home],
                  round(h_form, 4), round(h_pts, 1), h_n, h_gf, h_ga, h_gd))
    batch.append((away, date_str, round(elo[away], 2), matches_played[away],
                  round(a_form, 4), round(a_pts, 1), a_n, a_gf, a_ga, a_gd))
    
    batch.append((eid,))
    
    if len(batch) >= BATCH_SIZE * 3:  # 2 state + 1 progress per match
        conn.executemany('''
            INSERT OR REPLACE INTO walkforward_state
            (team_name, date, elo, matches_played,
             rolling_xg_for, rolling_xg_against,
             rolling_shots_for, rolling_shots_against,
             form_points, form_raw)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', [(b[0], b[1], b[2], b[3],
               1.2, 1.2, 10, 10,
               b[4], f"W{int(b[5])}"
              ) for b in batch if len(b) >= 10])
        
        conn.executemany('INSERT OR IGNORE INTO walkforward_progress VALUES (?, ?)',
                         [(b[0], datetime.now().isoformat()) for b in batch if len(b) == 1])
        conn.commit()
        batch = []
        processed += BATCH_SIZE
        print(f"  {processed}/{len(rows)}")

# Final batch
if batch:
    conn.executemany('''
        INSERT OR REPLACE INTO walkforward_state
        (team_name, date, elo, matches_played,
         rolling_xg_for, rolling_xg_against,
         rolling_shots_for, rolling_shots_against,
         form_points, form_raw)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    ''', [(b[0], b[1], b[2], b[3],
           1.2, 1.2, 10, 10,
           b[4], f"W{int(b[5])}"
          ) for b in batch if len(b) >= 10])
    
    conn.executemany('INSERT OR IGNORE INTO walkforward_progress VALUES (?, ?)',
                     [(b[0], datetime.now().isoformat()) for b in batch if len(b) == 1])
    conn.commit()

# Verify
state_count = conn.execute('SELECT COUNT(*) FROM walkforward_state').fetchone()[0]
progress_count = conn.execute('SELECT COUNT(*) FROM walkforward_progress').fetchone()[0]
min_date = conn.execute('SELECT MIN(date) FROM walkforward_state').fetchone()[0]
max_date = conn.execute('SELECT MAX(date) FROM walkforward_state').fetchone()[0]
team_count = conn.execute('SELECT COUNT(DISTINCT team_name) FROM walkforward_state').fetchone()[0]
conn.close()

print(f"\n{'='*60}")
print(f"DONE: {state_count} snapshots")
print(f"  Teams: {team_count}")
print(f"  Dates: {min_date} to {max_date}")
print(f"  Progress: {progress_count}/{len(rows)}")
print(f"{'='*60}")
