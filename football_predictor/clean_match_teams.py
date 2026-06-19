"""
clean_match_teams.py — Conservative, clean team name matching
Only auto-accepts: case-insensitive exact, prefix/suffix cleanup, substring match
No fuzzy garbage that creates false positives.
"""
import sys, os, sqlite3, json, re
import pandas as pd
from unicodedata import normalize as ucnorm

SD = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\soccer_dataset'
DB = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\scrape_cache.db'

def strip_accents(s):
    return ucnorm('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')

def clean_name(n):
    """Normalize: lowercase, strip accents, remove common suffixes/prefixes"""
    n = str(n).lower().strip()
    n = strip_accents(n)
    n = re.sub(r'[^a-z0-9\s]', '', n)  # remove punctuation
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def make_aliases(n):
    """Generate alias variants: with/without FC, SC, etc."""
    raw = n.strip()
    aliases = {raw.lower(), clean_name(n)}
    # Remove common suffixes
    for suffix in [' fc', ' f.c.', ' sc', ' s.c.', ' cf', ' ac', ' afc',
                   ' ud', ' cd', ' sd', ' ad', ' aa', ' ec', ' gr',
                   ' fc united', ' united', ' city', ' town']:
        if raw.lower().endswith(suffix):
            aliases.add(raw[:-len(suffix)].strip().lower())
    # Remove common prefixes
    for prefix in ['fc ', 'f.c. ', 'sc ', 's.c. ', 'cf ', 'ac ', 'afc ',
                   'ud ', 'cd ', 'sd ', 'ad ', 'gr ', 'ec ', 'aa ',
                   'real ', 'atletico ', 'club ', 'deportivo ', 'sporting ']:
        if raw.lower().startswith(prefix):
            aliases.add(raw[len(prefix):].strip().lower())
    # Remove double spaces
    aliases = {re.sub(r'\s+', ' ', a).strip() for a in aliases if a.strip()}
    return aliases

print("="*60)
print("CLEAN TEAM NAME MATCHER (conservative)")
print("="*60)

# 1. Load soccer-dataset teams
print("\n[1] Loading data...")
soccer_teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
fixtures = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
fixtures['date'] = pd.to_datetime(fixtures['date'])
fixtures_past = fixtures[(fixtures['goals_home'].notna()) & (fixtures['date'] < '2024-06-01')]

conn = sqlite3.connect(DB)
all_db_ids = set(r[0] for r in conn.execute('SELECT id FROM sofa_historical_results').fetchall())
sd_fixture_ids = set(fixtures['id'].unique())
mapped_ids = all_db_ids & sd_fixture_ids

unmatched = fixtures_past[~fixtures_past['id'].isin(mapped_ids)]
unmatched_team_ids = set(unmatched['home_team_id'].unique()) | set(unmatched['away_team_id'].unique())
unmatched_teams = soccer_teams[soccer_teams['id'].isin(unmatched_team_ids)]

# 2. Load our team names
print("[2] Loading SofaScore team names...")
our_teams_raw = set()
for row in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results').fetchall():
    our_teams_raw.add(str(row[0]).strip())
for row in conn.execute('SELECT DISTINCT away_team FROM sofa_historical_results').fetchall():
    our_teams_raw.add(str(row[0]).strip())
our_teams_raw = sorted([t for t in our_teams_raw if t])

# Build alias index: normalized_name -> [original_names]
our_index = {}  # alias -> set of original names
for t in our_teams_raw:
    for alias in make_aliases(t):
        if alias not in our_index:
            our_index[alias] = set()
        our_index[alias].add(t)

# Also add cleaned name as key
for t in our_teams_raw:
    cn = clean_name(t)
    if cn not in our_index:
        our_index[cn] = set()
    our_index[cn].add(t)

print(f"  Our teams: {len(our_teams_raw)}, aliases: {len(our_index)}")

# Existing mappings (to avoid duplicating effort)
existing = {}
for row in conn.execute('SELECT * FROM team_name_mapping').fetchall():
    existing[row[0].lower()] = row[1]
conn.close()

# 3. Match
print("[3] Matching teams...")
matches = {}  # sd_name -> our_name
already_in_existing = 0
no_match_found = 0

for _, srow in unmatched_teams.iterrows():
    sd_name = str(srow['name']).strip()
    sd_lower = sd_name.lower()
    
    # Skip if already in existing mappings
    if sd_lower in existing:
        already_in_existing += 1
        continue
    
    # Try exact match (case insensitive)
    found = None
    
    # 3a. Direct alias lookup
    for alias in make_aliases(sd_name):
        if alias in our_index:
            found = list(our_index[alias])[0]
            break
    
    if found is None:
        # 3b. Try cleaning + searching
        cn = clean_name(sd_name)
        if cn in our_index:
            found = list(our_index[cn])[0]
    
    if found is None:
        # 3c. Try substring: is our name entirely contained in sd_name?
        sd_clean = clean_name(sd_name)
        for our_name in our_teams_raw:
            our_clean = clean_name(our_name)
            if our_clean and (our_clean == sd_clean or 
                              sd_clean.startswith(our_clean) or 
                              our_clean.startswith(sd_clean)):
                found = our_name
                break

    if found:
        matches[sd_name] = found
    else:
        no_match_found += 1

print(f"\n  New matches: {len(matches)}")
print(f"  Already in existing: {already_in_existing}")
print(f"  No match found: {no_match_found}")

# Verify quality: show sample
print("\n--- Sample matches ---")
items = list(matches.items())
for k, v in items[:40]:
    print(f"  {k:40s} -> {v}")

# Check for potential issues
print("\n--- Quality check ---")
from collections import Counter
targets = Counter(matches.values())
multi_mapped = {t: c for t, c in targets.items() if c > 3}
if multi_mapped:
    print(f"  Teams mapped to >3 times: {len(multi_mapped)}")
    for t, c in sorted(multi_mapped.items(), key=lambda x: -x[1])[:10]:
        examples = [k for k, v in matches.items() if v == t][:5]
        print(f"    {t} ({c}x): {examples}")
else:
    print("  No multi-mapped teams. Clean!")

# Save
print(f"\n[4] Saving {len(matches)} clean mappings...")
with open(r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\clean_mappings.json', 'w', encoding='utf-8') as f:
    json.dump(matches, f, ensure_ascii=False, indent=2)

# Estimate match count
fixture_count = 0
for _, frow in unmatched.iterrows():
    home = soccer_teams[soccer_teams['id'] == frow['home_team_id']]
    away = soccer_teams[soccer_teams['id'] == frow['away_team_id']]
    if len(home) > 0 and len(away) > 0:
        hn = str(home.iloc[0]['name']).strip()
        an = str(away.iloc[0]['name']).strip()
        if hn in matches and an in matches:
            fixture_count += 1

print(f"\n{'='*60}")
print(f"Estimated new fixtures to integrate: ~{fixture_count}")
print(f"{'='*60}")
