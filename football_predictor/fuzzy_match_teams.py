"""
fuzzy_match_teams.py — Match soccer-dataset teams to SofaScore teams using fuzzy string matching
Uses rapidfuzz for fast C-accelerated fuzzy matching
"""
import sys, os, sqlite3, json
import pandas as pd
from rapidfuzz import fuzz

SD = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\soccer_dataset'
DB = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\scrape_cache.db'

print("="*60)
print("FUZZY TEAM NAME MATCHER")
print("="*60)

# 1. Load soccer-dataset teams that appear in unmatched fixtures
print("\n[1/5] Loading soccer-dataset data...")
soccer_teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
fixtures = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
fixtures['date'] = pd.to_datetime(fixtures['date'])
fixtures_past = fixtures[(fixtures['goals_home'].notna()) & (fixtures['date'] < '2024-06-01')]

# Get already-mapped fixture IDs
conn = sqlite3.connect(DB)
all_ids = set(r[0] for r in conn.execute('SELECT id FROM sofa_historical_results').fetchall())
sd_ids = set(fixtures['id'].unique())
mapped_ids = all_ids & sd_ids

# Unmatched fixtures
unmatched = fixtures_past[~fixtures_past['id'].isin(mapped_ids)]
unmatched_team_ids = set(unmatched['home_team_id'].unique()) | set(unmatched['away_team_id'].unique())
unmatched_teams = soccer_teams[soccer_teams['id'].isin(unmatched_team_ids)]
print(f"  Unmatched team IDs: {len(unmatched_team_ids)}/{len(soccer_teams)}")
print(f"  Unmatched fixtures: {len(unmatched)}")

# Add name aliases (strip common suffixes for better matching)
def normalize(name):
    n = str(name).lower().strip()
    n = n.replace('fc ', '').replace(' fc', '').replace('f.c.', '')
    n = n.replace('afc ', '').replace(' afc', '')
    n = n.replace('sc ', '').replace(' sc', '')
    n = n.replace('cf ', '').replace(' cf', '')
    n = n.replace('ac ', '').replace(' ac', '')
    n = n.replace('cd ', '').replace(' cd', '')
    n = n.replace('ud ', '').replace(' ud', '')
    n = n.replace('ad ', '').replace(' ad', '')
    n = n.replace('sd ', '').replace(' sd', '')
    n = n.replace('real ', '').replace(' real', '')
    n = n.replace('atletico ', '').replace(' atletico', '')
    n = n.replace('club ', '').replace(' club', '')
    n = n.replace('deportivo ', '').replace(' deportivo', '')
    n = n.replace('sporting ', '').replace(' sporting', '')
    n = n.replace('-', ' ').replace("'", '')
    return n.strip()

# 2. Load SofaScore team names from DB
print("\n[2/5] Loading SofaScore team names...")
our_teams = set()
for row in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results').fetchall():
    our_teams.add(str(row[0]).strip())
for row in conn.execute('SELECT DISTINCT away_team FROM sofa_historical_results').fetchall():
    our_teams.add(str(row[0]).strip())
conn.close()
our_teams = sorted([t for t in our_teams if t])
print(f"  SofaScore team names: {len(our_teams)}")

# Also load existing mappings to avoid duplicates
existing_mappings = {}
conn2 = sqlite3.connect(DB)
for row in conn2.execute('SELECT * FROM team_name_mapping').fetchall():
    existing_mappings[row[0]] = row[1]
conn2.close()
print(f"  Existing mappings: {len(existing_mappings)}")

# 3. Fuzzy match each soccer-dataset team to SofaScore teams
print("\n[3/5] Fuzzy matching teams...")

AUTO_THRESHOLD = 88  # auto-accept if score >= this
BORDERLINE_MIN = 75  # include borderline matches

matches = []  # (sd_name, sd_id, our_name, score, is_auto)

for idx, srow in unmatched_teams.iterrows():
    sd_name = str(srow['name']).strip()
    sd_id = int(srow['id'])
    
    # Skip if already mapped
    if sd_name in existing_mappings:
        continue
    
    # Already mapped by the original integration
    # Check if any existing mapping value matches
    already_mapped = False
    for k, v in existing_mappings.items():
        if k.lower() == sd_name.lower() or v.lower() == sd_name.lower():
            already_mapped = True
            break
    if already_mapped:
        continue
    
    # Normalize for comparison
    sd_norm = normalize(sd_name)
    
    best_score = 0
    best_our = None
    
    # Compare to our team names
    for our_name in our_teams:
        our_norm = normalize(our_name)
        
        # Use token_sort_ratio for word-order tolerance, WRatio for comprehensive
        score1 = fuzz.token_sort_ratio(sd_norm, our_norm)
        score2 = fuzz.partial_ratio(sd_norm, our_norm)
        score = max(score1, score2)
        
        if score > best_score:
            best_score = score
            best_our = our_name
    
    if best_score >= BORDERLINE_MIN:
        is_auto = best_score >= AUTO_THRESHOLD
        matches.append((sd_name, sd_id, best_our, best_score, is_auto))
        if len(matches) % 100 == 0:
            print(f"  Processed {len(matches)} matches...")

print(f"\n  Total fuzzy matches found: {len(matches)}")
auto = [m for m in matches if m[4]]
border = [m for m in matches if not m[4]]
print(f"  Auto-accept (>{AUTO_THRESHOLD}): {len(auto)}")
print(f"  Borderline ({BORDERLINE_MIN}-{AUTO_THRESHOLD}): {len(border)}")

# 4. Display borderline matches for review
print("\n[4/5] Borderline matches (needs review):")
border_sorted = sorted(border, key=lambda x: x[3], reverse=True)
for sd_name, sd_id, our_name, score, _ in border_sorted[:50]:
    print(f"  [{score}%] '{sd_name}' -> '{our_name}'")

# 5. Save mappings
print("\n[5/5] Saving mapping files...")
output_dir = os.path.dirname(__file__)

# Auto mappings
auto_mappings = {}
for sd_name, sd_id, our_name, score, _ in auto:
    auto_mappings[sd_name] = our_name

with open(os.path.join(output_dir, 'auto_mappings.json'), 'w', encoding='utf-8') as f:
    json.dump(auto_mappings, f, ensure_ascii=False, indent=2)
print(f"  Saved {len(auto_mappings)} auto-mappings to auto_mappings.json")

# Borderline
border_mappings = {}
for sd_name, sd_id, our_name, score, _ in border:
    border_mappings[sd_name] = {'mapped_to': our_name, 'score': score}

with open(os.path.join(output_dir, 'borderline_mappings.json'), 'w', encoding='utf-8') as f:
    json.dump(border_mappings, f, ensure_ascii=False, indent=2)
print(f"  Saved {len(border_mappings)} borderline to borderline_mappings.json")

print(f"\n{'='*60}")
print(f"RESULTS")
print(f"{'='*60}")
print(f"  Auto-accept: {len(auto)} teams -> integrates ~{len(auto) * 20}K matches")
print(f"  Borderline:  {len(border)} teams (review needed)")
print(f"  Total:       {len(auto) + len(border)} teams")
print(f"{'='*60}")
