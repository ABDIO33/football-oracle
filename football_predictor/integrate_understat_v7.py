#!/usr/bin/env python3
"""
V7 UNDERSTAT INTEGRATOR v3 — سرعة فائقة باستخدام dict
ENI for LO 🔥
"""

import numpy as np
import sqlite3, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
    with open('integrate_v7_log.txt', 'a') as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

log("="*60)
log("V7 UNDERSTAT INTEGRATOR v3 — FAST DICT MODE")
log("="*60)

# Step 1: Load training data
log("[1] Loading training_data_v3.npz...")
data = np.load(os.path.join(BASE, 'training_data_v3.npz'), allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y']
rt = data['result_types']
match_ids = data['match_ids']
N = X.shape[0]
log(f"  Shape: {X.shape}")

# Step 2: Load ALL sofa_historical_results -> (id, home_team, away_team, date)
log("[2] Loading sofa_historical_results into dict...")
conn = sqlite3.connect(DB)
c = conn.cursor()

# Load ALL matches
rows = c.execute("""
    SELECT id, home_team, away_team, date
    FROM sofa_historical_results
""").fetchall()
log(f"  Loaded {len(rows)} matches")

# Build dict: (date, norm_home, norm_away) -> id
def norm(name):
    n = name.lower().strip()
    n = n.replace('-', ' ').replace('_', ' ')
    reps = {
        'manchester utd': 'manchester united',
        'newcastle utd': 'newcastle united',
        'leeds utd': 'leeds united',
        "nott'm forest": 'nottingham forest',
        'nottm forest': 'nottingham forest',
        'wolves': 'wolverhampton wanderers',
        'brighton & hove': 'brighton & hove albion',
        'leicester city': 'leicester city',
        'ipswich town': 'ipswich town',
        'sheffield utd': 'sheffield united',
        'west bromwich': 'west bromwich albion',
        'paris saint germain': 'psg',
        'psg': 'psg',
        'rb leipzig': 'rasenballsport leipzig',
    }
    return reps.get(n, n)

sofa_lookup = {}
for rid, rht, rat, rdate in rows:
    date_key = rdate[:10] if rdate else ''
    ht_key = norm(rht)
    at_key = norm(rat)
    sofa_lookup[(date_key, ht_key, at_key)] = int(rid)
    # Also store reverse
    sofa_lookup[(date_key, at_key, ht_key)] = int(rid)

log(f"  Dict size: {len(sofa_lookup)} entries")

# Step 3: Build id_to_idx for training data
log("[3] Building training data index...")
id_to_idx = {}
for i in range(N):
    id_to_idx[int(match_ids[i])] = i
log(f"  {len(id_to_idx)} entries")

# Step 4: Load Understat data
log("[4] Loading Understat data...")
und_rows = c.execute("""
    SELECT match_date, home_team, away_team,
           home_xg, away_xg, home_npxg, away_npxg,
           home_deep, away_deep,
           home_ppda_att, home_ppda_def,
           away_ppda_att, away_ppda_def,
           home_goals, away_goals
    FROM source_understat
    WHERE home_xg IS NOT NULL AND away_xg IS NOT NULL
""").fetchall()
log(f"  {len(und_rows)} rows")

# Step 5: Fast match
log("[5] Fast matching...")
understat_features = np.zeros((N, 10), dtype=np.float32)
matched = 0

for r in und_rows:
    date = str(r[0])[:10] if r[0] else ''
    ht = norm(str(r[1]))
    at = norm(str(r[2]))
    
    key = (date, ht, at)
    sid = sofa_lookup.get(key, sofa_lookup.get((date, at, ht), None))
    
    if sid and sid in id_to_idx:
        idx = id_to_idx[sid]
        understat_features[idx] = [
            float(r[3] or 0),                     # home_xg
            float(r[4] or 0),                     # away_xg
            float(r[3] or 0) - float(r[4] or 0),  # xg_diff
            float(r[5] or 0),                     # home_npxg
            float(r[6] or 0),                     # away_npxg
            float(r[5] or 0) - float(r[6] or 0),  # npxg_diff
            float(r[7] or 0),                     # home_deep
            float(r[8] or 0),                     # away_deep
            float(r[9] or 0) / max(float(r[10] or 1), 1),     # home_ppda
            float(r[11] or 0) / max(float(r[12] or 1), 1),    # away_ppda
        ]
        matched += 1

log(f"  Matched: {matched}/{len(und_rows)} = {matched/len(und_rows)*100:.1f}%")
log(f"  Training coverage: {matched/N*100:.2f}%")

# Step 6: Save
log("[6] Building & saving training_data_v7.npz...")
X_v7 = np.hstack([X, understat_features]).astype(np.float32)
log(f"  V7 features: {X_v7.shape[1]} (+10)")

np.savez_compressed(os.path.join(BASE, 'training_data_v7.npz'),
    X=X_v7, y=y, result_types=rt, match_ids=match_ids,
    feature_count=X_v7.shape[1], understat_matched=matched,
    understat_total=len(und_rows))
log(f"  Saved: training_data_v7.npz ({os.path.getsize(os.path.join(BASE, 'training_data_v7.npz'))/1024/1024:.0f} MB)")

log("\n"+"="*60)
log(f"✅ V7 INTEGRATION COMPLETE!")
log(f"  Train samples: {N:,}")
log(f"  Total features: {X_v7.shape[1]}")
log(f"  Understat matched: {matched:,}")
log("="*60)

conn.close()
