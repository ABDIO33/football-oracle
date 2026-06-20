"""
integrate_new_fixtures.py — Insert ~28K newly matched soccer-dataset fixtures
Uses smart_mappings.json to map soccer-dataset team names → sofa team names
"""
import sqlite3, os, json, sys, time
from datetime import datetime
import pandas as pd
from collections import defaultdict

SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

print("="*60)
print("INTEGRATE NEW FIXTURES (~28K)")
print("="*60)

# 1. Load mappings
print("\n[1] Loading mappings...")
with open(os.path.join(os.path.dirname(__file__), 'smart_mappings.json'), 'r', encoding='utf-8') as f:
    mappings = json.load(f)
print(f"  Total mappings: {len(mappings)}")

# 2. Load soccer-dataset
print("\n[2] Loading soccer-dataset files...")
fix = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
stats = pd.read_csv(os.path.join(SD, 'match_stats.csv'))
teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
leagues_df = pd.read_csv(os.path.join(SD, 'leagues.csv'))
print(f"  Fixtures: {len(fix)}")
print(f"  Stats: {len(stats)}")
print(f"  Teams: {len(teams)}")

# 3. Filter to past matches before June 2024, not already in DB
print("\n[3] Filtering to new matches...")
fix['date_dt'] = pd.to_datetime(fix['date'])
fix_past = fix[(fix['goals_home'].notna()) & (fix['date_dt'] < '2024-06-15')].copy()

conn = sqlite3.connect(DB)
db_ids = set(r[0] for r in conn.execute('SELECT id FROM sofa_historical_results'))
sd_ids = set(fix['id'].unique())

new_fix = fix_past[~fix_past['id'].isin(db_ids & sd_ids)].copy()
print(f"  New fixtures available: {len(new_fix)}")

# 4. Map team names
print("\n[4] Mapping team names...")
team_id_to_name = dict(zip(teams['id'], teams['name']))

def map_team(team_id):
    name = team_id_to_name.get(team_id, '')
    return mappings.get(str(name).strip())

new_fix['home_sofa'] = new_fix['home_team_id'].apply(map_team)
new_fix['away_sofa'] = new_fix['away_team_id'].apply(map_team)

matched = new_fix[new_fix['home_sofa'].notna() & new_fix['away_sofa'].notna()].copy()
unmatched = new_fix[new_fix['home_sofa'].isna() | new_fix['away_sofa'].isna()]
print(f"  Matched: {len(matched)}")
print(f"  Unmatched (no mapping): {len(unmatched)}")

if len(unmatched) > 0:
    # Show why some aren't matched
    home_unmapped = unmatched['home_team_id'].map(team_id_to_name).dropna().unique()
    away_unmapped = unmatched['away_team_id'].map(team_id_to_name).dropna().unique()
    print(f"  Unmapped home teams: {len(home_unmapped)}, away teams: {len(away_unmapped)}")

# 5. Insert fixtures into DB
print("\n[5] Inserting fixtures...")
league_id_to_name = dict(zip(leagues_df['id'], leagues_df['name']))
new_fix_with_league = matched.merge(leagues_df[['id', 'name']], left_on='league_id', right_on='id', how='left')
league_col = 'name' if 'name' in new_fix_with_league.columns else 'name_y'

fixtures_to_insert = []
for _, row in matched.iterrows():
    league_name = league_id_to_name.get(row['league_id'], 'Unknown')
    date_str = str(row['date'])[:10]
    ts = int(row['date_dt'].timestamp())
    fixtures_to_insert.append((
        int(row['id']), row['home_sofa'], row['away_sofa'],
        int(row['goals_home']), int(row['goals_away']),
        league_name, date_str, ts
    ))

BATCH = 500
inserted = 0
cursor = conn.cursor()
for i in range(0, len(fixtures_to_insert), BATCH):
    batch = fixtures_to_insert[i:i+BATCH]
    rows = [(fid, ht, at, hs, aws, league, date_str, ts, 'finished') 
            for fid, ht, at, hs, aws, league, date_str, ts in batch]
    try:
        cursor.executemany('''
            INSERT OR IGNORE INTO sofa_historical_results
            (id, home_team, away_team, home_score, away_score, tournament, date, start_timestamp, status_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows)
        inserted += cursor.rowcount
    except Exception as e:
        print(f"  Error at batch {i}: {e}")
    conn.commit()

conn.commit()
print(f"  Inserted {inserted} new fixtures")

# 6. Update team_name_mapping with new mappings
print("\n[6] Updating team_name_mapping table...")
existing = set(r[0].lower() for r in conn.execute('SELECT fd_name FROM team_name_mapping'))
new_entries = 0
for sd_name, sofa_name in mappings.items():
    key = sd_name.lower().strip()
    if key not in existing:
        try:
            cursor.execute('INSERT OR IGNORE INTO team_name_mapping (fd_name, sofa_name, confidence) VALUES (?, ?, ?)',
                         (sd_name, sofa_name, 0.95))
            new_entries += 1
        except:
            pass
conn.commit()
print(f"  Added {new_entries} new mapping entries")

# 7. Insert stats where available
print("\n[7] Inserting match stats...")
matched_ids = set(matched['id'].values)
stats_to_insert = []
stats_cols = ['fixture_id', 'home_xg', 'away_xg', 'home_shots_total', 'away_shots_total',
              'home_shots_on_goal', 'away_shots_on_goal', 'home_possession', 'away_possession',
              'home_corners', 'away_corners', 'home_fouls', 'away_fouls']
stats_filtered = stats[stats['fixture_id'].isin(matched_ids)]
print(f"  Stats available for new fixtures: {len(stats_filtered)}")

for _, srow in stats_filtered.iterrows():
    stats_to_insert.append((
        int(srow['fixture_id']),
        float(srow['home_xg']) if pd.notna(srow['home_xg']) else None,
        float(srow['away_xg']) if pd.notna(srow['away_xg']) else None,
        int(srow['home_shots_total']) if pd.notna(srow['home_shots_total']) else None,
        int(srow['away_shots_total']) if pd.notna(srow['away_shots_total']) else None,
        int(srow['home_shots_on_goal']) if pd.notna(srow['home_shots_on_goal']) else None,
        int(srow['away_shots_on_goal']) if pd.notna(srow['away_shots_on_goal']) else None,
        float(srow['home_possession']) if pd.notna(srow['home_possession']) else None,
        float(srow['away_possession']) if pd.notna(srow['away_possession']) else None,
        int(srow['home_corners']) if pd.notna(srow['home_corners']) else None,
        int(srow['away_corners']) if pd.notna(srow['away_corners']) else None,
        int(srow['home_fouls']) if pd.notna(srow['home_fouls']) else None,
        int(srow['away_fouls']) if pd.notna(srow['away_fouls']) else None,
    ))

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
    conn.commit()

print(f"  Inserted {stats_inserted} match stats")

# 8. Final count
total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
print(f"\n=== TOTAL FIXTURES IN DB: {total} ===")

conn.close()
print("\nDONE - Now rebuild walkforward + Glicko-2 + retrain")
