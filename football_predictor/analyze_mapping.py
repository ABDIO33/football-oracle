"""Analyze remaining soccer-dataset teams that need mapping"""
import sqlite3, os, sys
import pandas as pd
from collections import defaultdict

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')

conn = sqlite3.connect(DB)

# Load soccer-dataset CSVs
fix = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
teams = pd.read_csv(os.path.join(SD, 'teams.csv'))

# Date filter
fix['date_dt'] = pd.to_datetime(fix['date'])
fix_before = fix[fix['date_dt'] < '2024-06-15'].copy()
has_scores = fix_before['goals_home'].notna()
fix_before = fix_before[has_scores]
print(f"Soccer-dataset fixtures before June 2024 with scores: {len(fix_before)}")

# Already in sofa DB
sofa_ids = set(r[0] for r in conn.execute('SELECT id FROM sofa_historical_results').fetchall())
already_in_db = fix_before[fix_before['id'].isin(sofa_ids)]
not_in_db = fix_before[~fix_before['id'].isin(sofa_ids)]
print(f"Already in DB: {len(already_in_db)}")
print(f"Not in DB: {len(not_in_db)}")
print(f"Total sofa DB IDs: {len(sofa_ids)}")

# NOT in DB team analysis
print(f"\n=== Team Name Matching ===")
unmapped_home = not_in_db['home_team_id'].map(teams.set_index('id')['name'])
unmapped_away = not_in_db['away_team_id'].map(teams.set_index('id')['name'])
all_unmapped_teams = pd.concat([unmapped_home, unmapped_away]).dropna().unique()
print(f"\nUnique team names NOT in DB: {len(all_unmapped_teams)}")

# Check how many of these appear in our sofa DB
sofa_teams = set(r[0].lower().strip() for r in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results'))
sofa_teams |= set(r[0].lower().strip() for r in conn.execute('SELECT DISTINCT away_team FROM sofa_historical_results'))
print(f"SofaScore teams: {len(sofa_teams)}")

# Try direct match
matched_direct = []
unmatched = []
for name in all_unmapped_teams:
    key = str(name).lower().strip()
    if key in sofa_teams:
        matched_direct.append(name)
    else:
        unmatched.append(name)

print(f"Direct match (case-insensitive): {len(matched_direct)}")
print(f"Still unmatched: {len(unmatched)}")

# Show sample of unmatched
if unmatched:
    print(f"\nSample of unmatched teams (30 of {len(unmatched)}):")
    for name in sorted(unmatched)[:30]:
        # Check if we have partial match in sofa
        parts = str(name).lower().split()
        partials = [t for t in list(sofa_teams)[:50] if any(p in t for p in parts)]
        print(f"  '{name}'")
        if partials:
            print(f"    partial sofa matches: {partials[:3]}")

# Check leagues of unmatched matches
leagues_df = pd.read_csv(os.path.join(SD, 'leagues.csv'))
not_in_db_with_league = not_in_db.merge(
    leagues_df[['id','name']], 
    left_on='league_id', right_on='id', how='left', suffixes=('','_league')
)
# Use 'name' from merge (suffix might vary)
league_col = [c for c in not_in_db_with_league.columns if 'name' in c and c != 'name_league'][0]
print(f"\n=== Leagues of unmatched matches ===")
league_counts = not_in_db_with_league.groupby(league_col).size().sort_values(ascending=False)
for league, cnt in league_counts.head(20).items():
    print(f"  {league}: {cnt}")

# Year distribution
not_in_db['year'] = not_in_db['date_dt'].dt.year
print(f"\n=== Year distribution of unmatched ===")
for year, cnt in sorted(not_in_db['year'].value_counts().items()):
    print(f"  {year}: {cnt}")

# Estimate matches that COULD be added if we mapped the remaining unmatched teams
# Already 1043 direct matches exist
matched_direct_set = set(n.lower().strip() for n in matched_direct)
# Filter fixtures where BOTH teams have a direct match
def can_match_now(row):
    home = str(teams[teams['id']==row['home_team_id']]['name'].values[0]).lower().strip() if row['home_team_id'] in teams['id'].values else ''
    away = str(teams[teams['id']==row['away_team_id']]['name'].values[0]).lower().strip() if row['away_team_id'] in teams['id'].values else ''
    return home in matched_direct_set and away in matched_direct_set

# This would be slow for 127K rows, so sample
sample_not = not_in_db.head(5000).copy()
can_add = sample_not.apply(can_match_now, axis=1)
print(f"\n=== Quick-estimated additional matches via direct match ===")
print(f"  Sample: {can_add.sum()}/5000 ({can_add.mean()*100:.1f}%) already directly matchable")
print(f"  Estimated total: ~{int(can_add.mean() * len(not_in_db))} of {len(not_in_db)}")

conn.close()
