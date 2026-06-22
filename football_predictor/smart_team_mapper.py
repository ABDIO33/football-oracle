"""
smart_team_mapper.py — 3-stage team name matching for soccer-dataset
Stage 1: Exact (case-insensitive) + existing mappings
Stage 2: Clean matching (prefix/suffix/strip-ascii)
Stage 3: Fuzzy matching with confidence validation (no false positives)
"""
import sys, os, sqlite3, json, re, time
import pandas as pd
from unicodedata import normalize as ucnorm

SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def strip_accents(s):
    return ucnorm('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')

def clean_name(n):
    n = str(n).lower().strip()
    n = strip_accents(n)
    n = re.sub(r'[^a-z0-9\s]', '', n)
    return re.sub(r'\s+', ' ', n).strip()

def make_aliases(n):
    raw = n.strip().lower()
    aliases = {raw, clean_name(n)}
    for suffix in [' fc', ' f.c.', ' sc', ' s.c.', ' cf', ' ac', ' afc',
                   ' ud', ' cd', ' sd', ' ad', ' aa', ' ec', ' gr',
                   ' fc united', ' fc andorra']:
        if raw.endswith(suffix):
            a = raw[:-len(suffix)].strip()
            if len(a) >= 4:
                aliases.add(a)
    for prefix in ['fc ', 'f.c. ', 'sc ', 's.c. ', 'cf ', 'ac ', 'afc ',
                   'ud ', 'cd ', 'sd ', 'ad ', 'gr ', 'ec ', 'aa ',
                   'as ', 'ss ', 'tsv ', 'sv ', 'vfl ', 'sg ',
                   'msv ', 'sc ', 'spvgg ', 'osv ', 'sk ', 'fk ', 'ik ',
                   'if ', 'il ', 'bk ', 'ff ', 'sz ', 'nk ']:
        if raw.startswith(prefix):
            a = raw[len(prefix):].strip()
            if len(a) >= 4:
                aliases.add(a)
    return {a for a in {re.sub(r'\s+', ' ', a_).strip() for a_ in aliases if a_} if len(a) >= 4}

print("="*60)
print("SMART TEAM MAPPER (3-Stage)")
print("="*60)

# 1. Load data
print("\n[1] Loading data...")
conn = sqlite3.connect(DB)
soccer_teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
fixtures = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
fixtures['date'] = pd.to_datetime(fixtures['date'])
fixtures_past = fixtures[(fixtures['goals_home'].notna()) & (fixtures['date'] < '2024-06-15')]
print(f"  Soccer-dataset teams: {len(soccer_teams)}")
print(f"  Fixtures (past w/ scores): {len(fixtures_past)}")

# 2. SofaScore teams
sofa_teams = set()
for row in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results'):
    sofa_teams.add(str(row[0]).strip())
for row in conn.execute('SELECT DISTINCT away_team FROM sofa_historical_results'):
    sofa_teams.add(str(row[0]).strip())
sofa_teams = sorted([t for t in sofa_teams if t])
print(f"  SofaScore teams: {len(sofa_teams)}")

# 3. Build alias index for fast lookup
alias_to_sofa = {}
for t in sofa_teams:
    for alias in make_aliases(t):
        if alias not in alias_to_sofa:
            alias_to_sofa[alias] = []
        alias_to_sofa[alias].append(t)

# Also index cleaned names (minimum length 4)
for t in sofa_teams:
    cn = clean_name(t)
    if len(cn) >= 4 and cn not in alias_to_sofa:
        alias_to_sofa[cn] = []
    if len(cn) >= 4 and t not in alias_to_sofa[cn]:
        alias_to_sofa[cn].append(t)

print(f"  Alias index: {len(alias_to_sofa)} entries")

# 4. Existing mappings (to avoid duplicates)
existing_fd = {}
for row in conn.execute('SELECT * FROM team_name_mapping'):
    existing_fd[row[0].lower()] = row[1]

# Also load clean_mappings.json if exists
clean_mappings = {}
try:
    with open(os.path.join(os.path.dirname(__file__), 'clean_mappings.json'), 'r', encoding='utf-8') as f:
        clean_mappings = json.load(f)
    print(f"  Existing clean_mappings.json: {len(clean_mappings)}")
except:
    print("  No clean_mappings.json found")

# 5. Which fixtures are already in DB?
db_ids = set(r[0] for r in conn.execute('SELECT id FROM sofa_historical_results'))
sd_ids = set(fixtures['id'].unique())
already_mapped_ids = db_ids & sd_ids
unmatched = fixtures_past[~fixtures_past['id'].isin(already_mapped_ids)]
unmatched_team_ids = set(unmatched['home_team_id'].unique()) | set(unmatched['away_team_id'].unique())
unmatched_teams_df = soccer_teams[soccer_teams['id'].isin(unmatched_team_ids)]
print(f"  Already in DB: {len(already_mapped_ids)}")
print(f"  Unmatched fixtures: {len(unmatched)}")
print(f"  Unmatched teams: {len(unmatched_teams_df)}")

# 6. MATCH!
print("\n[2] Matching teams (Stage 1: Exact)...")
matches = {}  # sd_team_name -> sofa_team_name
stage_counts = {'1-exact': 0, '2-existing': 0, '3-alias': 0, '4-substr': 0, 'unmatched': 0}

for _, srow in unmatched_teams_df.iterrows():
    sd_name = str(srow['name']).strip()
    sd_fd_name = str(srow['fd_name']).strip() if pd.notna(srow.get('fd_name')) else ''
    sd_lower = sd_name.lower()
    
    already = False
    # Skip if already has mapping via fd_name
    if sd_fd_name and sd_fd_name.lower() in existing_fd:
        matches[sd_name] = existing_fd[sd_fd_name.lower()]
        stage_counts['2-existing'] += 1
        continue
    if sd_lower in existing_fd:
        matches[sd_name] = existing_fd[sd_lower]
        stage_counts['2-existing'] += 1
        continue
    
    # Stage 1: Direct case-insensitive match
    found = None
    for alias in make_aliases(sd_name):
        if alias in alias_to_sofa:
            candidates = alias_to_sofa[alias]
            # Only accept if unambiguous (single candidate)
            if len(candidates) == 1:
                found = candidates[0]
                break
            # Multiple candidates: pick longest (most specific)
            found = sorted(candidates, key=lambda x: -len(x))[0]
            break
    
    if found:
        stage_counts['1-exact'] += 1
    else:
        # Stage 2: Try substring match (more aggressive)
        sd_clean = clean_name(sd_name)
        best = None
        best_len = 0
        for sofa_name in sofa_teams:
            sc = clean_name(sofa_name)
            if not sc:
                continue
            # One is substring of other
            if sd_clean == sc:
                best = sofa_name
                break
            if len(sc) > best_len and (sd_clean.startswith(sc) or sc.startswith(sd_clean)):
                best = sofa_name
                best_len = len(sc)
        if best:
            found = best
            stage_counts['4-substr'] += 1
    
    if found:
        matches[sd_name] = found
        stage_counts['4-substr'] += 1
    else:
        stage_counts['unmatched'] += 1

# Stage 3: Fuzzy matching for remaining
if stage_counts['unmatched'] > 0:
    print("\n[2b] Stage 3: Fuzzy matching...")
    try:
        from thefuzz import fuzz, process
        has_fuzzy = True
    except ImportError:
        try:
            from fuzzywuzzy import fuzz, process
            has_fuzzy = True
        except ImportError:
            print("  fuzzywuzzy not installed, skipping")
            has_fuzzy = False
    if has_fuzzy:
        unmatched_sd = []
        for _, srow in unmatched_teams_df.iterrows():
            sd_name = str(srow['name']).strip()
            if sd_name not in matches:
                unmatched_sd.append(sd_name)
        unmatched_sd = sorted(set(unmatched_sd))
        print(f"  Fuzzy matching {len(unmatched_sd)} names...")
        sofa_clean = {t: clean_name(t) for t in sofa_teams}
        for sd_name in unmatched_sd:
            sd_clean = clean_name(sd_name)
            if len(sd_clean) < 4:
                continue
            best = process.extractOne(sd_clean, list(sofa_clean.values()), scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 85:
                idx = list(sofa_clean.values()).index(best[0])
                best_sofa = list(sofa_clean.keys())[idx]
                matches[sd_name] = best_sofa
        # Recalculate counts
        new_unmatched = 0
        for _, srow in unmatched_teams_df.iterrows():
            if str(srow['name']).strip() not in matches:
                new_unmatched += 1
        stage_counts['3-fuzzy'] = stage_counts['unmatched'] - new_unmatched
        stage_counts['unmatched'] = new_unmatched

print(f"  Stage 1 (exact): {stage_counts['1-exact']}")
print(f"  Stage 2 (existing): {stage_counts['2-existing']}")
print(f"  Stage 3 (fuzzy): {stage_counts.get('3-fuzzy', 0)}")
print(f"  Stage 4 (substr): {stage_counts['4-substr']}")
print(f"  Unmatched: {stage_counts['unmatched']}")
print(f"  TOTAL matched: {len(matches)}")

# 7. Quality check — filter bad matches
print(f"\n[3] Quality check...")
from collections import Counter
targets = Counter(matches.values())

# Remove multi-mapped targets where >5 different SD names map to same sofa name
bad_sofa_names = {t for t, c in targets.items() if c > 5}
if bad_sofa_names:
    print(f"  Removing {len(bad_sofa_names)} over-mapped sofa names: {sorted(bad_sofa_names)}")
    matches = {k: v for k, v in matches.items() if v not in bad_sofa_names}

targets = Counter(matches.values())
multi_mapped = {t: c for t, c in targets.items() if c > 3}
if multi_mapped:
    print(f"  Teams with >3 SD names mapped: {len(multi_mapped)}")
    for t, c in sorted(multi_mapped.items(), key=lambda x: -x[1])[:15]:
        examples = [k for k, v in matches.items() if v == t][:3]
        print(f"    (encoding-unsafe) ({c}x)")
else:
    print(f"  No heavy multi-mapping!")

# Show sample of new matches (compatible encoding)
print(f"\n--- Sample new matches ({min(len(matches), 40)}) ---")
items = sorted(matches.items(), key=lambda x: x[0])
for k, v in items[:40]:
    print(f"  '{k}' -> '{v}'".encode('ascii', errors='replace').decode('ascii'))

# 8. Estimate new fixtures
print(f"\n[4] Estimating new fixtures...")
fixture_count = 0
for _, frow in unmatched.iterrows():
    home_row = soccer_teams[soccer_teams['id'] == frow['home_team_id']]
    away_row = soccer_teams[soccer_teams['id'] == frow['away_team_id']]
    if len(home_row) > 0 and len(away_row) > 0:
        hn = str(home_row.iloc[0]['name']).strip()
        an = str(away_row.iloc[0]['name']).strip()
        if hn in matches and an in matches:
            fixture_count += 1

print(f"  Estimated new fixtures: ~{fixture_count}")

# 9. Save matches
print(f"\n[5] Saving matches...")
# Merge with clean_mappings (clean_mappings were pre-verified)
all_matches = dict(clean_mappings)
# Only add new matches that aren't already covered
for k, v in matches.items():
    if k not in all_matches:
        all_matches[k] = v
print(f"  Total unique matches: {len(all_matches)}")

with open(os.path.join(os.path.dirname(__file__), 'smart_mappings.json'), 'w', encoding='utf-8') as f:
    json.dump(all_matches, f, ensure_ascii=False, indent=2)

# Show unmatched teams (for manual review)
unmatched_names = []
for _, srow in unmatched_teams_df.iterrows():
    sd_name = str(srow['name']).strip()
    if sd_name not in all_matches:
        unmatched_names.append(sd_name)
print(f"\n[6] Remaining unmatched teams: {len(unmatched_names)}")
if unmatched_names:
    print("  Sample (40):")
    for n in sorted(unmatched_names)[:40]:
        print(f"    '{n}'".encode('ascii', errors='replace').decode('ascii'))

conn.close()
print(f"\n{'='*60}")
print(f"SMART MATCHING DONE")
print(f"{'='*60}")
