"""
MASSIVE DATA INTEGRATOR — Phase 1: Soccer Dataset (378K matches)
دمج 378K مباراة من soccer dataset مع تحسين team mapping
"""
import sqlite3, os, json, sys, time, re
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')

print("=" * 60)
print("MASSIVE DATA INTEGRATOR — Phase 1")
print("=" * 60)

# 1. Load soccer-dataset files
print("\n[1/5] Loading soccer-dataset files...")
fix = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
stats = pd.read_csv(os.path.join(SD, 'match_stats.csv'))
teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
leagues_df = pd.read_csv(os.path.join(SD, 'leagues.csv'))
lineups = pd.read_csv(os.path.join(SD, 'fixture_lineups.csv'))
odds = pd.read_csv(os.path.join(SD, 'odds.csv'))
print(f"  Fixtures: {len(fix):,}")
print(f"  With scores: {fix['goals_home'].notna().sum():,}")
print(f"  Stats: {len(stats):,}")
print(f"  Teams: {len(teams):,}")
print(f"  Leagues: {len(leagues_df)}")
print(f"  Lineups: {len(lineups):,}")
print(f"  Odds: {len(odds):,}")

# 2. Connect to DB and check existing data
conn = sqlite3.connect(DB)

# Check existing sofa names
sofa_teams = set(r[0] for r in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results').fetchall())
print(f"\n[2/5] Existing SofaScore teams: {len(sofa_teams):,}")

# Check existing team_name_mapping
mappings = {}
for r in conn.execute('SELECT fd_name, sofa_name FROM team_name_mapping WHERE confidence >= 0.85').fetchall():
    mappings[r[0].lower().strip()] = r[1]
print(f"  Team mappings (high conf): {len(mappings)}")

# Build quick fuzzy matcher for remaining teams
def normalize(name):
    name = str(name).lower().strip()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    # Common abbreviations
    name = name.replace('fc', '').replace('afc', '').replace('sc', '').replace('cf', '')
    name = name.replace('ac', '').replace('ssc', '').replace('as', '').replace('us', '')
    name = name.replace('real', '').replace('club', '').replace('deportivo', '')
    name = name.strip()
    return name

# Build fuzzy index from sofa teams
sofa_normalized = {}
for t in sofa_teams:
    n = normalize(t)
    if n:
        sofa_normalized[n] = t

# Also add existing mappings directly
for k, v in mappings.items():
    n = normalize(k)
    if n and n not in sofa_normalized:
        sofa_normalized[n] = v

print(f"  Normalized sofa names: {len(sofa_normalized)}")

# 3. Build team mapping for soccer dataset
print("\n[3/5] Building team mapping for soccer dataset...")
team_id_to_name = dict(zip(teams['id'], teams['name']))
team_id_to_fd_name = dict(zip(teams['id'], teams['fd_name']))

def map_team(team_id, team_name, fd_name):
    """Map a soccer-dataset team to sofa name"""
    # Strategy 1: via fd_name → mapping table
    if fd_name and isinstance(fd_name, str):
        key = fd_name.lower().strip()
        if key in mappings:
            return mappings[key], 'mapping_fd'
    
    # Strategy 2: via API-Football name → mapping table
    if team_name and isinstance(team_name, str):
        key = str(team_name).lower().strip()
        if key in mappings:
            return mappings[key], 'mapping_api'
    
    # Strategy 3: via fd_name → fuzzy match
    if fd_name and isinstance(fd_name, str):
        n = normalize(fd_name)
        if n in sofa_normalized:
            return sofa_normalized[n], 'fuzzy_fd'
    
    # Strategy 4: via API-Football name → fuzzy match
    if team_name and isinstance(team_name, str):
        n = normalize(str(team_name))
        if n in sofa_normalized:
            return sofa_normalized[n], 'fuzzy_api'
    
    return None, 'unmatched'

# Test mapping on all teams
matched_count = 0
team_map_cache = {}
for _, trow in teams.iterrows():
    tid = trow['id']
    tname = trow['name']
    fd = trow.get('fd_name', '')
    result, method = map_team(tid, tname, fd)
    if result:
        matched_count += 1
        team_map_cache[tid] = result

print(f"  Teams with sofa match: {matched_count:,} / {len(teams):,} ({matched_count/len(teams)*100:.1f}%)")
print(f"  Unmatched teams: {len(teams) - matched_count:,}")

# Show sample of unmatched
if len(teams) - matched_count > 0:
    unmapped = []
    for _, trow in teams.iterrows():
        if trow['id'] not in team_map_cache:
            unmapped.append(trow['name'])
    print(f"  Sample unmapped: {unmapped[:10]}")

# 4. Map fixtures
print("\n[4/5] Mapping fixtures...")
fix['date_dt'] = pd.to_datetime(fix['date'])
has_scores = fix['goals_home'].notna() & fix['goals_away'].notna()
fix_scored = fix[has_scores].copy()
print(f"  Fixtures with scores: {len(fix_scored):,}")

# Map home/away teams
fix_scored['home_sofa'] = fix_scored['home_team_id'].map(team_map_cache)
fix_scored['away_sofa'] = fix_scored['away_team_id'].map(team_map_cache)

mapped_fix = fix_scored[
    fix_scored['home_sofa'].notna() & 
    fix_scored['away_sofa'].notna()
].copy()
print(f"  Both teams mapped: {len(mapped_fix):,} / {len(fix_scored):,}")

# 5. Insert into DB
print("\n[5/5] Inserting into database...")

# Merge league names
mapped_fix = mapped_fix.merge(
    leagues_df[['id', 'name']], 
    left_on='league_id', 
    right_on='id', 
    how='left', 
    suffixes=('', '_league')
)
mapped_fix['league_name'] = mapped_fix['name'].fillna('Unknown')

# Insert in batches
BATCH = 1000
inserted = 0
total_fixtures = len(mapped_fix)
batch_count = 0

for i in range(0, total_fixtures, BATCH):
    batch = mapped_fix.iloc[i:i+BATCH]
    rows = []
    for _, row in batch.iterrows():
        fid = row['id']
        date_str = str(row['date'])[:10] if pd.notna(row['date']) else ''
        ts = int(datetime.strptime(date_str, '%Y-%m-%d').timestamp()) if date_str.count('-') == 2 else 0
        rows.append((
            -fid,  # negative to avoid ID conflicts with SofaScore
            row['home_sofa'],
            row['away_sofa'],
            int(row['goals_home']),
            int(row['goals_away']),
            row['league_name'],
            ts,
            date_str,
        ))
    
    try:
        cur = conn.cursor()
        cur.executemany('''
            INSERT OR IGNORE INTO sofa_historical_results
            (id, home_team, away_team, home_score, away_score, tournament, start_timestamp, date, status_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'finished')
        ''', rows)
        inserted += cur.rowcount
    except Exception as e:
        print(f'  Batch error: {e}')
    
    batch_count += 1
    if batch_count % 10 == 0:
        conn.commit()
        print(f'  Progress: {min(i+BATCH, total_fixtures):,}/{total_fixtures:,} ({inserted:,} new)')

conn.commit()
print(f'  TOTAL INSERTED: {inserted:,} new fixtures')

# Also add match stats for the inserted matches
print('\n  Inserting match stats...')
stats_inserted = 0
for i in range(0, total_fixtures, BATCH):
    batch = mapped_fix.iloc[i:i+BATCH]
    stat_rows = []
    for _, row in batch.iterrows():
        fid = -row['id']
        # Get stats for this fixture
        srow = stats[stats['fixture_id'] == row['id']]
        if len(srow) == 0:
            continue
        s = srow.iloc[0]
        stat_rows.append((
            fid,
            float(s['home_xg']) if pd.notna(s.get('home_xg')) else None,
            float(s['away_xg']) if pd.notna(s.get('away_xg')) else None,
            int(s['home_shots_total']) if pd.notna(s.get('home_shots_total')) else None,
            int(s['away_shots_total']) if pd.notna(s.get('away_shots_total')) else None,
            int(s['home_shots_on_goal']) if pd.notna(s.get('home_shots_on_goal')) else None,
            int(s['away_shots_on_goal']) if pd.notna(s.get('away_shots_on_goal')) else None,
            float(s['home_possession']) if pd.notna(s.get('home_possession')) else None,
            float(s['away_possession']) if pd.notna(s.get('away_possession')) else None,
            int(s['home_corners']) if pd.notna(s.get('home_corners')) else None,
            int(s['away_corners']) if pd.notna(s.get('away_corners')) else None,
            int(s['home_fouls']) if pd.notna(s.get('home_fouls')) else None,
            int(s['away_fouls']) if pd.notna(s.get('away_fouls')) else None,
        ))
    
    if stat_rows:
        try:
            cur = conn.cursor()
            cur.executemany('''
                INSERT OR IGNORE INTO sofa_match_stats
                (event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot,
                 home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', stat_rows)
            stats_inserted += cur.rowcount
        except:
            pass
    
    if batch_count % 20 == 0:
        conn.commit()

conn.commit()
print(f'  Stats inserted: {stats_inserted:,}')

# Final summary
total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
conn.close()

print(f'\n{"=" * 60}')
print(f'MASSIVE INTEGRATION COMPLETE')
print(f'  Inserted: {inserted:,} new fixtures')
print(f'  Stats: {stats_inserted:,}')
print(f'  Total DB: {total:,}')
print(f'  From {matched_count:,}/{len(teams):,} mapped teams')
print(f'{"=" * 60}')
print(f'\nNEXT: Run rebuild walkforward + train on {total:,} matches')
