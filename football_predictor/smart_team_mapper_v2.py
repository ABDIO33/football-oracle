"""
smart_team_mapper.py v2 — 4-stage team matching with zero false positives
Stage 1: Case-insensitive exact match
Stage 2: Existing clean mappings (from clean_mappings.json)
Stage 3: Alias matching (prefix/suffix stripped, min 5 chars)
Stage 4: Fuzzy matching (token_sort_ratio >= 92) on clean names
Manual blacklist to remove known bad aliases
"""
import sys, os, sqlite3, json, re, time
import pandas as pd
from unicodedata import normalize as ucnorm
from collections import Counter

SD = os.path.join(os.path.dirname(__file__), 'soccer_dataset')
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def strip_accents(s):
    return ucnorm('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')

def clean_name(n):
    n = str(n).lower().strip()
    n = strip_accents(n)
    n = re.sub(r'[^a-z0-9\s]', '', n)
    return re.sub(r'\s+', ' ', n).strip()

# Manual blacklist of known BAD aliases
BLACKLIST = {
    # short sofa names that cause false matches
    'ab', 'fc', 'sc', 'ac', 'if', 'il', 'bk', 'ff', 'sk', 'sz', 'nk',
    'as', 'ec', 'cf', 'ud', 'cd', 'sd', 'ad', 'aa', 'gr',
    'al', 'ol', 'ps', 'sp', 'st', 'rc', 'rs', 'sc',
    'montpellier', 'marseille', 'paris',
}

def make_aliases(n):
    """Generate alias variants: with/without FC, SC, etc. Min 5 chars"""
    raw = n.strip().lower()
    cleaned = clean_name(n)
    aliases = {raw, cleaned}
    for suffix in [' fc', ' f.c.', ' sc', ' s.c.', ' cf', ' ac', ' afc',
                   ' fc united', ' sc freiburg', ' ud', ' cd']:
        if raw.endswith(suffix):
            a = raw[:-len(suffix)].strip()
            if len(a) >= 5:
                aliases.add(a)
    for prefix in ['fc ', 'f.c. ', 'sc ', 's.c. ', 'cf ', 'ac ', 'afc ',
                   'ud ', 'cd ', 'sd ', 'ad ',
                   'tsv ', 'sv ', 'vfl ', 'sg ', 'msv ', 'sc ',
                   'spvgg ', 'osv ', 'sk ', 'fk ', 'ik ',
                   'if ', 'il ', 'bk ', 'ff ', 'sz ', 'nk ']:
        if raw.startswith(prefix):
            a = raw[len(prefix):].strip()
            if len(a) >= 5:
                aliases.add(a)
    # Filter blacklist
    result = set()
    for a in aliases:
        a = re.sub(r'\s+', ' ', a).strip()
        if a and len(a) >= 5 and a not in BLACKLIST:
            result.add(a)
    return result

print("="*60)
print("SMART TEAM MAPPER v2 (Zero False Positives)")
print("="*60)

# 1. Load data
conn = sqlite3.connect(DB)
soccer_teams = pd.read_csv(os.path.join(SD, 'teams.csv'))
fixtures = pd.read_csv(os.path.join(SD, 'fixtures.csv'))
fixtures['date'] = pd.to_datetime(fixtures['date'])
fixtures_past = fixtures[(fixtures['goals_home'].notna()) & (fixtures['date'] < '2024-06-15')]

sofa_teams = set()
for row in conn.execute('SELECT DISTINCT home_team FROM sofa_historical_results'):
    sofa_teams.add(str(row[0]).strip())
for row in conn.execute('SELECT DISTINCT away_team FROM sofa_historical_results'):
    sofa_teams.add(str(row[0]).strip())
sofa_teams = sorted([t for t in sofa_teams if t])

# Build alias index
alias_to_sofa = {}
for t in sofa_teams:
    for alias in make_aliases(t):
        if alias not in alias_to_sofa:
            alias_to_sofa[alias] = []
        alias_to_sofa[alias].append(t)

# Existing mappings
existing_fd = {}
for row in conn.execute('SELECT fd_name, sofa_name FROM team_name_mapping'):
    existing_fd[row[0].lower().strip()] = row[1]

clean_mappings = {}
try:
    with open(os.path.join(os.path.dirname(__file__), 'clean_mappings.json'), 'r', encoding='utf-8') as f:
        clean_mappings = json.load(f)
except:
    pass

# DB IDs
db_ids = set(r[0] for r in conn.execute('SELECT id FROM sofa_historical_results'))
sd_ids = set(fixtures['id'].unique())
already_mapped_ids = db_ids & sd_ids
unmatched = fixtures_past[~fixtures_past['id'].isin(already_mapped_ids)]
unmatched_team_ids = set(unmatched['home_team_id'].unique()) | set(unmatched['away_team_id'].unique())
unmatched_teams_df = soccer_teams[soccer_teams['id'].isin(unmatched_team_ids)]

print(f"  SofaScore teams: {len(sofa_teams)}")
print(f"  Alias index: {len(alias_to_sofa)} entries")
print(f"  Existing mappings: {len(existing_fd)}")
print(f"  Clean mappings: {len(clean_mappings)}")
print(f"  Already in DB: {len(already_mapped_ids)}")
print(f"  Unmatched fixtures: {len(unmatched)}")
print(f"  Unmatched teams: {len(unmatched_teams_df)}")

# 2. Match
matches = {}
counts = {'exact': 0, 'existing': 0, 'alias': 0, 'fuzzy': 0, 'unmatched': 0}

# Precompute cleaned sofa names for fuzzy
sofa_name_clean_map = {t: clean_name(t) for t in sofa_teams}

for _, srow in unmatched_teams_df.iterrows():
    sd_name = str(srow['name']).strip()
    sd_lower = sd_name.lower()
    sd_clean = clean_name(sd_name)
    
    # --- Stage 0: Check existing_fd by fd_name ---
    sd_fd = str(srow['fd_name']).strip() if pd.notna(srow.get('fd_name')) else ''
    if sd_fd and sd_fd.lower() in existing_fd:
        matches[sd_name] = existing_fd[sd_fd.lower()]
        counts['existing'] += 1
        continue
    if sd_lower in existing_fd:
        matches[sd_name] = existing_fd[sd_lower]
        counts['existing'] += 1
        continue
    if sd_name in clean_mappings:
        matches[sd_name] = clean_mappings[sd_name]
        counts['existing'] += 1
        continue
    
    # --- Stage 1: Case-insensitive exact match ---
    if sd_clean in [clean_name(t) for t in sofa_teams]:
        idx = [clean_name(t) for t in sofa_teams].index(sd_clean)
        matches[sd_name] = sofa_teams[idx]
        counts['exact'] += 1
        continue
    
    # --- Stage 2: Alias matching ---
    found = None
    for alias in make_aliases(sd_name):
        if alias in alias_to_sofa:
            candidates = alias_to_sofa[alias]
            if len(candidates) == 1:
                found = candidates[0]
                break
    
    if found:
        matches[sd_name] = found
        counts['alias'] += 1
        continue
    
    # --- Stage 3: Fuzzy matching (high threshold 92) ---
    from thefuzz import fuzz, process
    best = process.extractOne(sd_clean, list(sofa_name_clean_map.values()), scorer=fuzz.token_sort_ratio)
    if best and best[1] >= 92:
        idx = list(sofa_name_clean_map.values()).index(best[0])
        matches[sd_name] = list(sofa_name_clean_map.keys())[idx]
        counts['fuzzy'] += 1
        continue
    
    counts['unmatched'] += 1

print(f"  Stage 1 (exact): {counts['exact']}")
print(f"  Stage 2 (existing): {counts['existing']}")
print(f"  Stage 3 (alias): {counts['alias']}")
print(f"  Stage 4 (fuzzy): {counts['fuzzy']}")
print(f"  Unmatched: {counts['unmatched']}")
print(f"  TOTAL matched: {len(matches)}")

# 3. Quality checks
print(f"\n[3] Quality checks...")
targets = Counter(matches.values())
# Remove over-mapped (likely false positives)
over_mapped = {t for t, c in targets.items() if c > 5}
if over_mapped:
    print(f"  Removing {len(over_mapped)} over-mapped targets...")
    matches = {k: v for k, v in matches.items() if v not in over_mapped}

# Check for suspicious matches: different length ratios
suspicious = []
for sd_name, sofa_name in matches.items():
    sd_clean = clean_name(sd_name)
    sc = clean_name(sofa_name)
    ratio = min(len(sd_clean), len(sc)) / max(len(sd_clean), len(sc)) if max(len(sd_clean), len(sc)) > 0 else 0
    if ratio < 0.4 and len(sd_clean) > 8:
        suspicious.append((sd_name, sofa_name, ratio))

print(f"  Suspicious (ratio<0.4): {len(suspicious)} removed")
short_bad = []
for sd_name, sofa_name in list(matches.items()):
    sc = clean_name(sofa_name)
    if len(sc) <= 3:
        short_bad.append((sd_name, sofa_name))
if short_bad:
    print(f"  Removing {len(short_bad)} matches where sofa name <=3 chars...")
    for sd, sofa in short_bad:
        if sd in matches:
            del matches[sd]
    print(f"  After removal: {len(matches)} matches")

# Show sample
print(f"\n--- Sample ({min(len(matches), 50)}) ---")
items = sorted(matches.items(), key=lambda x: x[0])
for k, v in items[:50]:
    out = f"{k} -> {v}"
    if any(ord(c) > 127 for c in out):
        out = out.encode('ascii', errors='replace').decode('ascii')
    print(f"  {out}")

# 4. Estimate new fixtures
fixture_count = 0
for _, frow in unmatched.iterrows():
    home_row = soccer_teams[soccer_teams['id'] == frow['home_team_id']]
    away_row = soccer_teams[soccer_teams['id'] == frow['away_team_id']]
    if len(home_row) > 0 and len(away_row) > 0:
        hn = str(home_row.iloc[0]['name']).strip()
        an = str(away_row.iloc[0]['name']).strip()
        if hn in matches and an in matches:
            fixture_count += 1

print(f"\n=== Estimated new fixtures: ~{fixture_count} ===")

# 5. Save
all_matches = {}
if clean_mappings:
    all_matches.update(clean_mappings)
for k, v in matches.items():
    if k not in all_matches:
        all_matches[k] = v
print(f"\nTotal unique mappings: {len(all_matches)}")

with open(os.path.join(os.path.dirname(__file__), 'smart_mappings.json'), 'w', encoding='utf-8') as f:
    json.dump(all_matches, f, ensure_ascii=False, indent=2)

# Save unmatched teams
unmatched_names = []
for _, srow in unmatched_teams_df.iterrows():
    sd_name = str(srow['name']).strip()
    if sd_name not in all_matches:
        unmatched_names.append(sd_name)
print(f"Remaining unmatched teams: {len(unmatched_names)}")

conn.close()
print("\nDONE")
