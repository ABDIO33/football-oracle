"""Analyze unmatched teams from soccer-dataset"""
import sqlite3, os, pandas as pd

SD = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\soccer_dataset'
DB = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\scrape_cache.db'

soccer_teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
fixtures = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
fixtures['date'] = pd.to_datetime(fixtures['date'])
fixtures_past = fixtures[(fixtures['goals_home'].notna()) & (fixtures['date'] < '2024-06-01')]

conn = sqlite3.connect(DB)
mapped = conn.execute('SELECT id FROM sofa_historical_results').fetchall()
all_db_ids = set(r[0] for r in mapped)
sd_fixture_ids = set(fixtures['id'].unique())
mapped_ids = all_db_ids & sd_fixture_ids

unmatched = fixtures_past[~fixtures_past['id'].isin(mapped_ids) & fixtures_past['goals_home'].notna()]
home_ids = set(unmatched['home_team_id'].unique())
away_ids = set(unmatched['away_team_id'].unique())
all_ids = home_ids | away_ids
unmatched_teams = soccer_teams[soccer_teams['id'].isin(all_ids)]

# Unique leagues from unmatched fixtures
unmatched_leagues = set(unmatched['league_id'].unique())
leagues = pd.read_csv(os.path.join(SD, 'leagues.csv'))
unmatched_league_info = leagues[leagues['id'].isin(unmatched_leagues)]

print(f"Total unmatched fixtures: {len(unmatched)}")
print(f"Unmatched team IDs: {len(all_ids)}")
print(f"Unique leagues: {len(unmatched_leagues)}")
print(f"\nTop leagues by fixtures:")
for _, lrow in unmatched_league_info.sort_values('id').head(20).iterrows():
    cnt = len(unmatched[unmatched['league_id'] == lrow['id']])
    print(f"  {lrow['name']}: {cnt} fixtures")

print(f"\n--- Our DB teams ---")
our_teams = set()
for row in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results').fetchall():
    our_teams.add(row[0])
for row in conn.execute('SELECT DISTINCT away_team FROM sofa_historical_results').fetchall():
    our_teams.add(row[0])
print(f"Unique team names in DB: {len(our_teams)}")
print("Sample:", sorted(list(our_teams))[:20])

print(f"\n--- Sample soccer-dataset unmatched teams ---")
for _, r in unmatched_teams.head(40).iterrows():
    print(f"  {r['name']:40s} ({r['country']})")

conn.close()
