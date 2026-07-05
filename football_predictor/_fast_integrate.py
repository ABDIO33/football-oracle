"""
FAST INTEGRATION v2 — Insert ALL soccer dataset matches (no mapping required)
We insert with original API-Football names. If a mapping exists, we use it.
Otherwise we keep the original name. Walkforward will connect within same naming.
"""
import sqlite3, os, sys, time, re
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')

t0 = time.time()
print("=" * 60)
print("FAST INTEGRATION V2 — Add ALL soccer dataset matches")
print("=" * 60)

# Load data
print("\n[1/4] Loading...")
fix = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
leagues_df = pd.read_csv(os.path.join(SD, 'leagues.csv'))

# Filter to scored matches
has_scores = fix['goals_home'].notna() & fix['goals_away'].notna()
fix = fix[has_scores].copy()
print(f"  Fixtures with scores: {len(fix):,}")

# Load team mappings from DB
conn = sqlite3.connect(DB)
mappings = {}
try:
    for r in conn.execute('SELECT fd_name, sofa_name FROM team_name_mapping WHERE confidence >= 0.85').fetchall():
        mappings[r[0].lower().strip()] = r[1]
except:
    pass
print(f"  Team mappings loaded: {len(mappings)}")

# Also get all existing sofa team names for fuzzy matching
sofa_teams = set()
for r in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results').fetchall():
    sofa_teams.add(r[0])
for r in conn.execute('SELECT DISTINCT away_team FROM sofa_historical_results').fetchall():
    sofa_teams.add(r[0])
print(f"  Existing sofa teams: {len(sofa_teams):,}")

# Build name: id mapping for teams
team_id_to_name = dict(zip(teams['id'], teams['name']))
team_id_to_fd = dict(zip(teams['id'], teams['fd_name']))

# Build fuzzy index
def norm(s):
    s = str(s).lower().strip()
    s = re.sub(r'[^a-z0-9\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    for w in ['fc', 'afc', 'sc', 'cf', 'ac', 'ssc', 'as', 'us', 'real', 'club', 'deportivo',
              'football', 'club', 'association', 'athletic', 'atletico', 'sport', 'sporting']:
        s = s.replace(w, '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

fuzzy_index = {}
for t in sofa_teams:
    n = norm(t)
    if len(n) > 2:
        fuzzy_index[n] = t
for k, v in mappings.items():
    n = norm(k)
    if len(n) > 2 and n not in fuzzy_index:
        fuzzy_index[n] = v

def map_team(tid):
    name = str(team_id_to_name.get(tid, ''))
    fd = str(team_id_to_fd.get(tid, ''))
    
    # 1. Try fd_name in mappings
    k = fd.lower().strip()
    if k in mappings:
        return mappings[k]
    
    # 2. Try direct name in mappings
    k = name.lower().strip()
    if k in mappings:
        return mappings[k]
    
    # 3. Fuzzy match fd_name
    n = norm(fd)
    if n in fuzzy_index:
        return fuzzy_index[n]
    
    # 4. Fuzzy match name
    n = norm(name)
    if n in fuzzy_index:
        return fuzzy_index[n]
    
    # 5. Return original name
    return name

# Map ALL teams
name_cache = {}
for tid in teams['id'].unique():
    name_cache[tid] = map_team(tid)

mapped_count = sum(1 for v in name_cache.values() if v.lower().strip() != str(team_id_to_name.get([k for k, val in team_id_to_name.items() if val == v][0] if v in team_id_to_name.values() else -1, v)).lower().strip())
print(f"  Teams mapped to sofa names: {sum(1 for v in name_cache.values() if v in sofa_teams)}/{len(name_cache)}")

# Apply to fixtures
print("\n[2/4] Applying team mapping...")
fix['home_name_final'] = fix['home_team_id'].map(name_cache)
fix['away_name_final'] = fix['away_team_id'].map(name_cache)

# Add league names
fix = fix.merge(leagues_df[['id', 'name']], left_on='league_id', right_on='id', how='left', suffixes=('', '_league'))
fix['league_name'] = fix['name'].fillna('Unknown')

# Build insert data
print("\n[3/4] Preparing insert data...")
insert_rows = []
for _, row in fix.iterrows():
    fid = row['id']
    date_str = str(row['date'])[:10] if pd.notna(row['date']) else ''
    ts = 0
    try:
        ts = int(datetime.strptime(date_str, '%Y-%m-%d').timestamp())
    except:
        pass
    insert_rows.append((
        -fid,  # negative to avoid SofaScore ID conflicts
        str(row['home_name_final']),
        str(row['away_name_final']),
        int(row['goals_home']),
        int(row['goals_away']),
        str(row['league_name']),
        ts,
        date_str,
    ))

print(f"  Total fixtures to insert: {len(insert_rows):,}")

# Batch insert
print("\n[4/4] Inserting into DB...")
BATCH = 2000
inserted = 0
total = len(insert_rows)

for i in range(0, total, BATCH):
    batch = insert_rows[i:i+BATCH]
    try:
        cur = conn.cursor()
        cur.executemany('''
            INSERT OR IGNORE INTO sofa_historical_results
            (id, home_team, away_team, home_score, away_score, tournament, start_timestamp, date, status_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'finished')
        ''', batch)
        inserted += cur.rowcount
        conn.commit()
    except Exception as e:
        print(f"  Error at batch {i}: {e}")
        conn.rollback()
    
    if (i // BATCH) % 10 == 0:
        print(f"  Progress: {min(i+BATCH, total):,}/{total:,} ({inserted:,} new)")

# Final
total_now = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
conn.close()

elapsed = time.time() - t0
print(f"\n{'=' * 60}")
print(f"INTEGRATION COMPLETE in {elapsed/60:.1f} min")
print(f"  Inserted: {inserted:,} new matches")
print(f"  Total DB: {total_now:,}")
print(f"{'=' * 60}")
print(f"\nNEXT: Rebuild walkforward + train on {total_now:,} matches")
print(f"Run: python fast_walkforward.py  (then)  python train_v4.py")
