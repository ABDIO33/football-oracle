"""
manual_mapping_fixes.py — Remove known bad auto-mappings that are clearly wrong
"""
import json, os

REMOVE = {
    # These are WRONG: different teams
    "AFC Liverpool",  # non-league → NOT Liverpool FC
    "AVS",           # Portuguese team → NOT Maritimo
    # Reserve teams mapped to first team (can cause confusion but keep)
}

path = os.path.join(os.path.dirname(__file__), 'smart_mappings.json')
with open(path, 'r', encoding='utf-8') as f:
    mappings = json.load(f)

removed = 0
for bad in REMOVE:
    if bad in mappings:
        print(f"  REMOVE: '{bad}' -> '{mappings[bad]}'")
        del mappings[bad]
        removed += 1

print(f"Removed {removed} bad mappings")

with open(path, 'w', encoding='utf-8') as f:
    json.dump(mappings, f, ensure_ascii=False, indent=2)
print(f"Saved {len(mappings)} mappings")

# Re-estimate fixture count
import sqlite3, os
import pandas as pd
SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

soccer_teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
fixtures = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
fixtures['date'] = pd.to_datetime(fixtures['date'])
fixtures_past = fixtures[(fixtures['goals_home'].notna()) & (fixtures['date'] < '2024-06-15')]

conn = sqlite3.connect(DB)
db_ids = set(r[0] for r in conn.execute('SELECT id FROM sofa_historical_results'))
conn.close()

sd_ids = set(fixtures['id'].unique())
unmatched = fixtures_past[~fixtures_past['id'].isin(db_ids & sd_ids)]

fixture_count = 0
for _, frow in unmatched.iterrows():
    home_row = soccer_teams[soccer_teams['id'] == frow['home_team_id']]
    away_row = soccer_teams[soccer_teams['id'] == frow['away_team_id']]
    if len(home_row) > 0 and len(away_row) > 0:
        hn = str(home_row.iloc[0]['name']).strip()
        an = str(away_row.iloc[0]['name']).strip()
        if hn in mappings and an in mappings:
            fixture_count += 1

print(f"Estimated new fixtures: ~{fixture_count}")
