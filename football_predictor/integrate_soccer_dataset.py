"""
integrate_soccer_dataset.py — Merge 291K historical matches (2012-2024) into our DB
from eatpizzanot/soccer-dataset (API-Football + Football-Data.co.uk)
"""
import sqlite3, os, json, sys, time
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')

print("="*60)
print("INTEGRATE SOCCER DATASET (291K MATCHES 2012-2024)")
print("="*60)

# 1. Load soccer-dataset files
print("\n[1/6] Loading soccer-dataset files...")
fix = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
stats = pd.read_csv(os.path.join(SD, 'match_stats.csv'))
teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
leagues_df = pd.read_csv(os.path.join(SD, 'leagues.csv'))
lineups = pd.read_csv(os.path.join(SD, 'fixture_lineups.csv'))
print(f"  fixtures: {len(fix)} rows")
print(f"  stats: {len(stats)} rows ({stats['home_xg'].notna().mean()*100:.0f}% with xG)")
print(f"  teams: {len(teams)} rows")
print(f"  leagues: {len(leagues_df)} rows")
print(f"  lineups: {len(lineups)} rows")

# 2. Filter to matches before our cutoff (June 2024)
print("\n[2/6] Filtering to matches before June 2024...")
fix['date_dt'] = pd.to_datetime(fix['date'])
fix_before = fix[fix['date_dt'] < '2024-06-15'].copy()
has_scores = fix_before['goals_home'].notna()
fix_before = fix_before[has_scores]
print(f"  Matches before June 2024 with scores: {len(fix_before)}")

# 3. Load team name mapping from our DB
print("\n[3/6] Loading team name mapping...")
conn = sqlite3.connect(DB)
try:
    mapping_rows = conn.execute('SELECT fd_name, sofa_name, confidence FROM team_name_mapping WHERE confidence >= 0.85').fetchall()
    fd_to_sofa = {r[0].lower().strip(): r[1] for r in mapping_rows}
    print(f"  Mappings loaded: {len(fd_to_sofa)}")
except:
    fd_to_sofa = {}
    print("  No team_name_mapping found, using direct names")

# Build team name map from soccer-dataset teams.csv
# teams.csv has: id, name, api_football_id, fd_name
team_id_to_name = dict(zip(teams['id'], teams['name']))
team_id_to_fd_name = dict(zip(teams['id'], teams['fd_name']))
print(f"  Team registry: {len(team_id_to_name)} teams")

# 4. Map team names and build insert data
print("\n[4/6] Mapping teams and preparing insert data...")
import difflib

def get_sofa_name(team_name, fd_name):
    """Try to find sofa_name for this team."""
    # Try fd_name first
    if fd_name and isinstance(fd_name, str):
        key = fd_name.lower().strip()
        if key in fd_to_sofa:
            return fd_to_sofa[key]
    # Try direct match
    key = str(team_name).lower().strip()
    if key in fd_to_sofa:
        return fd_to_sofa[key]
    # Not found
    return None

conn2 = sqlite3.connect(DB)
all_sofa_teams = set(r[0] for r in conn2.execute('SELECT DISTINCT home_team FROM sofa_historical_results').fetchall())
all_sofa_teams |= set(r[0] for r in conn2.execute('SELECT DISTINCT away_team FROM sofa_historical_results').fetchall())
conn2.close()

# Build league name map
league_id_to_name = dict(zip(leagues_df['id'], leagues_df['name']))
# Add league_name to fixtures via merge
fix_before = fix_before.merge(leagues_df[['id', 'name']], left_on='league_id', right_on='id', how='left', suffixes=('', '_league'))
league_col = 'name' if 'name' in fix_before.columns else 'league_name'
fix_before['league_name'] = fix_before['name'].fillna('Unknown')

# Pre-merge stats
stats_cols = ['fixture_id', 'home_xg', 'away_xg', 'home_shots_total', 'away_shots_total',
              'home_shots_on_goal', 'away_shots_on_goal', 'home_possession', 'away_possession',
              'home_corners', 'away_corners', 'home_fouls', 'away_fouls']
stats_clean = stats[stats_cols].copy()
stats_clean.columns = ['fixture_id'] + [f'stat_{c}' for c in stats_cols[1:]]
fix_before = fix_before.merge(stats_clean, left_on='id', right_on='fixture_id', how='left')

# Batch team name mapping
def vectorized_map(team_ids, team_map, fd_map, name_map):
    names = team_ids.map(team_map).fillna('')
    fd_names = team_ids.map(fd_map).fillna('')
    results = []
    for i in range(len(names)):
        n = str(names.iloc[i])
        f = str(fd_names.iloc[i])
        key_f = f.lower().strip()
        key_n = n.lower().strip()
        if key_f in name_map:
            results.append(name_map[key_f])
        elif key_n in name_map:
            results.append(name_map[key_n])
        else:
            results.append(None)
    return results

# Mem optimize: sample 10K to estimate match rate
sample = fix_before.head(10000).copy()
sample['home_sofa'] = vectorized_map(sample['home_team_id'], team_id_to_name, team_id_to_fd_name, fd_to_sofa)
sample['away_sofa'] = vectorized_map(sample['away_team_id'], team_id_to_name, team_id_to_fd_name, fd_to_sofa)
match_rate = (sample['home_sofa'].notna() & sample['away_sofa'].notna()).mean()
print(f"  Estimated team match rate: {match_rate*100:.1f}%")

# Apply mapping to all data
fix_before['home_sofa'] = vectorized_map(fix_before['home_team_id'], team_id_to_name, team_id_to_fd_name, fd_to_sofa)
fix_before['away_sofa'] = vectorized_map(fix_before['away_team_id'], team_id_to_name, team_id_to_fd_name, fd_to_sofa)

matched = fix_before[fix_before['home_sofa'].notna() & fix_before['away_sofa'].notna()].copy()
unmatched = fix_before[fix_before['home_sofa'].isna() | fix_before['away_sofa'].isna()]
print(f"  Matched: {len(matched)}, Unmatched: {len(unmatched)}")
if len(unmatched) > 0:
    sample_unmapped = set(unmatched['home_team_id'].map(team_id_to_name).dropna().unique())
    print(f"  Sample unmapped teams: {list(sample_unmapped)[:10]}")

# Build final insert data
fixtures_to_insert = []
stats_to_insert = []
for _, row in matched.iterrows():
    fid = row['id']
    date_str = str(row['date'])[:10]
    ts = int(row['date_dt'].timestamp())
    fixtures_to_insert.append((
        fid, row['home_sofa'], row['away_sofa'],
        int(row['goals_home']), int(row['goals_away']),
        row['league_name'], date_str, ts
    ))
    if pd.notna(row.get('stat_home_xg')):
        stats_to_insert.append((
            fid,
            float(row['stat_home_xg']) if pd.notna(row['stat_home_xg']) else None,
            float(row['stat_away_xg']) if pd.notna(row['stat_away_xg']) else None,
            int(row['stat_home_shots_total']) if pd.notna(row['stat_home_shots_total']) else None,
            int(row['stat_away_shots_total']) if pd.notna(row['stat_away_shots_total']) else None,
            int(row['stat_home_shots_on_goal']) if pd.notna(row['stat_home_shots_on_goal']) else None,
            int(row['stat_away_shots_on_goal']) if pd.notna(row['stat_away_shots_on_goal']) else None,
            float(row['stat_home_possession']) if pd.notna(row['stat_home_possession']) else None,
            float(row['stat_away_possession']) if pd.notna(row['stat_away_possession']) else None,
            int(row['stat_home_corners']) if pd.notna(row['stat_home_corners']) else None,
            int(row['stat_away_corners']) if pd.notna(row['stat_away_corners']) else None,
            int(row['stat_home_fouls']) if pd.notna(row['stat_home_fouls']) else None,
            int(row['stat_away_fouls']) if pd.notna(row['stat_away_fouls']) else None,
        ))

# Build lineups data
lineup_data = []
for _, lrow in lineups.iterrows():
    lineup_data.append((
        lrow['fixture_id'],
        lrow['team_id'],
        lrow['formation'],
    ))

# Group by fixture_id to get home/away formations
from collections import defaultdict
fixture_formations = defaultdict(lambda: [None, None])  # fid -> [home, away]
for fid, tid, form in lineup_data:
    # Determine if this is home or away
    match_row = matched[matched['id'] == fid]
    if len(match_row) == 0:
        continue
    mr = match_row.iloc[0]
    home_id = mr['home_team_id']
    if tid == home_id:
        fixture_formations[fid][0] = form
    else:
        fixture_formations[fid][1] = form

lineups_to_insert = []
for fid, (hf, af) in fixture_formations.items():
    if hf or af:
        lineups_to_insert.append((fid, hf, af))

print(f"\n  Total fixtures to insert: {len(fixtures_to_insert)}")
print(f"  With stats: {len(stats_to_insert)}")
print(f"  With lineups: {len(lineups_to_insert)}")

# 5. Insert into DB (batch)
print("\n[5/6] Inserting into database (batch)...")
conn3 = sqlite3.connect(DB)
cursor = conn3.cursor()

# Insert fixtures in batches of 500
BATCH = 500
inserted = 0
for i in range(0, len(fixtures_to_insert), BATCH):
    batch = fixtures_to_insert[i:i+BATCH]
    rows_for_insert = [(fid, ht, at, hs, aws, league, date_str, ts, 'finished') 
                       for fid, ht, at, hs, aws, league, date_str, ts in batch]
    try:
        cursor.executemany('''
            INSERT OR IGNORE INTO sofa_historical_results
            (id, home_team, away_team, home_score, away_score, tournament, date, start_timestamp, status_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows_for_insert)
        inserted += cursor.rowcount
    except:
        pass
    if (i // BATCH) % 20 == 0:
        conn3.commit()
        print(f"  Inserting fixtures: {min(i+BATCH, len(fixtures_to_insert))}/{len(fixtures_to_insert)}")

conn3.commit()
print(f"  Inserted {inserted} new fixtures")

# Insert stats in batches
stats_inserted = 0
for i in range(0, len(stats_to_insert), BATCH):
    batch = stats_to_insert[i:i+BATCH]
    try:
        cursor.executemany('''
            INSERT OR IGNORE INTO sofa_match_stats
            (event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot,
             home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch)
        stats_inserted += cursor.rowcount
    except:
        pass

conn3.commit()
print(f"  Inserted {stats_inserted} match stats")

# Insert lineups in batches
lineups_inserted = 0
for i in range(0, len(lineups_to_insert), BATCH):
    batch = lineups_to_insert[i:i+BATCH]
    try:
        cursor.executemany('''
            INSERT OR IGNORE INTO sofa_lineups
            (event_id, home_formation, away_formation, confirmed)
            VALUES (?, ?, ?, 1)
        ''', [(fid, hf or '', af or '') for fid, hf, af in batch])
        lineups_inserted += cursor.rowcount
    except:
        pass
conn3.commit()
print(f"  Inserted {lineups_inserted} lineups")

# 6. Add Glicko-2 ratings as new columns
print("\n[6/6] Adding Glicko-2 ratings...")
# Add a simple table for team ratings
cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_ratings (
        team_name TEXT PRIMARY KEY,
        rating_mu REAL,
        rating_sigma REAL,
        source TEXT
    )
''')
rating_count = 0
for _, team_row in teams.iterrows():
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO team_ratings (team_name, rating_mu, rating_sigma, source)
            VALUES (?, ?, ?, 'soccer-dataset')
        ''', (team_row['name'], team_row['rating_mu'], team_row['rating_sigma']))
        rating_count += 1
    except:
        pass
conn3.commit()
print(f"  Added {rating_count} team ratings")

conn3.close()
print("\n" + "="*60)
print(f"INTEGRATION COMPLETE: {inserted} new matches")
print("="*60)
print("\nNext steps:")
print("  1. python reindex.py  (reassign IDs + rebuild walkforward)")
print("  2. python ensemble_trainer.py  (train on ALL data now)")
print("  3. Track exact score target: 20%+")
