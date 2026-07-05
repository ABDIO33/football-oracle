#!/usr/bin/env python3
"""
[FIRE] MERGE UNDERSTAT xG -> training_data_v7.npz
==================================================
مدمج Understat (13,005 matches) مع training_data_v3.npz (772K, 120 features)
بطريقة SQL مباشرة للحصول على أقصى سرعة ومطابقة كاملة.

المطابقة: via sofa_historical_results
  understat.(date, home_goals, away_goals) = sofa.(date, home_score, away_score)
  AND فريق مطابقة باستخدام team mapping جدول

الـ features المضافة (11): understat_xg_home/away, xg_diff, PPDA ratio, deep_diff, npxg, xga
"""

import os, sys, sqlite3, json, re, time, warnings, unicodedata
import numpy as np
from datetime import datetime

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'scrape_cache.db')
V3_PATH = os.path.join(BASE_DIR, 'training_data_v3.npz')
V7_OUTPUT = os.path.join(BASE_DIR, 'training_data_v7.npz')
FEATURES_FULL = os.path.join(BASE_DIR, 'features_full.npz')
LOG_PATH = os.path.join(BASE_DIR, 'harvest_logs', 'merge_understat_v7.log')
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

import sys, codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

def log(msg, also_print=True):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    if also_print:
        print(line)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# ============================================================
# TEAM NAME MAPPING
# ============================================================
# Direct sofa -> understat team name mapping
SOFA_TO_UNDERSTAT = {}

# Build from the big dictionary (defined inline)
_raw_map = {
    'Manchester City': 'Manchester City', 'Manchester Utd': 'Manchester United',
    'Newcastle Utd': 'Newcastle United', 'West Ham Utd': 'West Ham United',
    'Wolves': 'Wolverhampton Wanderers', 'Wolverhampton': 'Wolverhampton Wanderers',
    'Brighton': 'Brighton', 'Brighton & Hove Albion': 'Brighton',
    'Leeds Utd': 'Leeds', 'Leeds': 'Leeds',
    'Sheffield Utd': 'Sheffield United', 'Tottenham': 'Tottenham',
    'Tottenham Hotspur': 'Tottenham', 'Leicester': 'Leicester',
    'Leicester City': 'Leicester', 'West Brom': 'West Bromwich Albion',
    'West Bromwich Albion': 'West Bromwich Albion',
    'Norwich': 'Norwich', 'Norwich City': 'Norwich',
    'Nottingham Forest': 'Nottingham Forest', "Nott'm Forest": 'Nottingham Forest',
    'Ipswich': 'Ipswich', 'Ipswich Town': 'Ipswich',
    'Bournemouth': 'Bournemouth', 'AFC Bournemouth': 'Bournemouth',
    'Huddersfield': 'Huddersfield Town', 'Huddersfield Town': 'Huddersfield Town',
    'Stoke': 'Stoke City', 'Stoke City': 'Stoke City',
    'Swansea': 'Swansea City', 'Swansea City': 'Swansea City',
    'Cardiff': 'Cardiff City', 'Cardiff City': 'Cardiff City',
    'Middlesbrough': 'Middlesbrough',
    'FC Barcelona': 'Barcelona',
    'Athletic Bilbao': 'Athletic Club',
    'RB Leipzig': 'RasenBallsport Leipzig',
    'Bayer 04 Leverkusen': 'Bayer Leverkusen',
    'VfL Wolfsburg': 'Wolfsburg',
    'Borussia Monchengladbach': 'Borussia M.Gladbach',
    "Borussia M'gladbach": 'Borussia M.Gladbach',
    'Hertha BSC': 'Hertha Berlin',
    '1. FC Union Berlin': 'Union Berlin',
    'SC Freiburg': 'Freiburg',
    'TSG 1899 Hoffenheim': 'Hoffenheim',
    '1. FSV Mainz 05': 'Mainz 05',
    'FC Augsburg': 'Augsburg',
    'FC Schalke 04': 'Schalke 04',
    'FC Koln': 'FC Cologne', 'Koln': 'FC Cologne',
    'Cologne': 'FC Cologne', '1. FC Koln': 'FC Cologne',
    'VfL Bochum': 'Bochum', 'DSC Arminia Bielefeld': 'Arminia Bielefeld',
    'SpVgg Greuther Furth': 'Greuther Fuerth', 'Greuther Furth': 'Greuther Fuerth',
    'SV Darmstadt 98': 'Darmstadt',
    '1. FC Heidenheim 1846': 'FC Heidenheim', 'Heidenheim': 'FC Heidenheim',
    'Hamburg': 'Hamburger SV', 'FC St. Pauli': 'St. Pauli',
    'Inter Milan': 'Inter',
    'AS Roma': 'Roma', 'ACF Fiorentina': 'Fiorentina',
    'Torino FC': 'Torino', 'US Sassuolo': 'Sassuolo',
    'Udinese Calcio': 'Udinese', 'UC Sampdoria': 'Sampdoria',
    'Genoa CFC': 'Genoa', 'Cagliari Calcio': 'Cagliari',
    'Hellas Verona': 'Verona', 'Empoli FC': 'Empoli',
    'Spezia Calcio': 'Spezia', 'US Salernitana': 'Salernitana',
    'Venezia FC': 'Venezia', 'AC Monza': 'Monza',
    'US Lecce': 'Lecce', 'US Cremonese': 'Cremonese',
    'Frosinone Calcio': 'Frosinone', 'Benevento Calcio': 'Benevento',
    'Parma': 'Parma Calcio 1913', 'FC Crotone': 'Crotone',
    'Pisa SC': 'Pisa',
    'Paris Saint-Germain': 'Paris Saint Germain', 'PSG': 'Paris Saint Germain',
    'Olympique Marseille': 'Marseille', 'Olympique de Marseille': 'Marseille',
    'Olympique Lyon': 'Lyon', 'Olympique Lyonnais': 'Lyon',
    'AS Monaco': 'Monaco', 'LOSC Lille': 'Lille', 'LOSC': 'Lille',
    'Stade Rennais': 'Rennes', 'OGC Nice': 'Nice', 'RC Lens': 'Lens',
    'Montpellier HSC': 'Montpellier', 'HSC Montpellier': 'Montpellier',
    'RC Strasbourg': 'Strasbourg', 'RC Strasbourg Alsace': 'Strasbourg',
    'FC Nantes': 'Nantes', 'Girondins de Bordeaux': 'Bordeaux',
    'FC Girondins Bordeaux': 'Bordeaux', 'AS Saint-Etienne': 'Saint-Etienne',
    'AS Saint-Etienne': 'Saint-Etienne', 'Stade de Reims': 'Reims',
    'Stade Reims': 'Reims', 'Toulouse FC': 'Toulouse',
    'Angers SCO': 'Angers', 'SCO Angers': 'Angers',
    'Stade Brestois': 'Brest', 'Stade Brest': 'Brest',
    'FC Lorient': 'Lorient', 'FC Metz': 'Metz',
    'Clermont': 'Clermont Foot', 'Clermont Foot 63': 'Clermont Foot',
    'AJ Auxerre': 'Auxerre', 'ESTAC Troyes': 'Troyes',
    'Dijon FCO': 'Dijon', 'Nimes Olympique': 'Nimes',
    'Le Havre AC': 'Le Havre', 'AC Ajaccio': 'Ajaccio',
}
for k, v in _raw_map.items():
    SOFA_TO_UNDERSTAT[k.lower()] = v

# Also add reverse of some mappings for Sofascore names
REVERSE_MAP = {}
for sofa_name, ud_name in list(SOFA_TO_UNDERSTAT.items()):
    REVERSE_MAP[ud_name.lower()] = sofa_name  # ud -> sofa (best guess)

def normalize_for_match(name):
    """Light normalization for comparison."""
    if not name:
        return ''
    n = name.lower().strip()
    n = unicodedata.normalize('NFKD', n).encode('ASCII', 'ignore').decode('ASCII')
    n = n.replace('.', '').replace('-', ' ').replace("'", ' ').replace('&', ' ')
    n = re.sub(r'\s+', ' ', n).strip()
    n = n.replace('fc ', '').replace(' ac ', '').replace('ssc ', '').replace('us ', '')
    n = n.replace('as ', '').replace('rc ', '').replace('sc ', '').replace('cd ', '')
    n = n.replace('ud ', '').replace('stade ', '').replace('ogc ', '').replace('sc ', '')
    return n.strip()

def sofa_to_understat_name(sofa_name):
    """Map sofa team name to Understat equivalent."""
    n = sofa_name.lower()
    if n in SOFA_TO_UNDERSTAT:
        return SOFA_TO_UNDERSTAT[n]
    return sofa_name

# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 70)
    log("[FIRE] MERGE UNDERSTAT xG -> training_data_v7.npz")
    log("=" * 70)
    
    t0 = time.time()
    
    # 1. Load training data
    log("\n[1/5] Loading training_data_v3.npz...")
    v3 = np.load(V3_PATH, allow_pickle=True)
    X, y, result_types, match_ids = v3['X'], v3['y'], v3['result_types'], v3['match_ids']
    log(f"  X: {X.shape}, y: {y.shape}, match_ids: {match_ids.shape}")
    
    # 2. Connect to DB
    log("\n[2/5] Connecting to DB & creating temporary lookup table...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-512000")
    cur = conn.cursor()
    
    # Create temp table for v3 IDs
    cur.execute('CREATE TEMP TABLE IF NOT EXISTS _v3ids (id INTEGER PRIMARY KEY)')
    cur.execute('DELETE FROM _v3ids')
    ids_list = [int(x) for x in match_ids]
    batch_size = 500
    for i in range(0, len(ids_list), batch_size):
        batch = ids_list[i:i+batch_size]
        placeholders = ','.join(['(?)'] * len(batch))
        cur.execute(f'INSERT OR IGNORE INTO _v3ids VALUES {placeholders}', batch)
    conn.commit()
    
    # 3. Match Understat -> sofa -> v3 directly in SQL
    log("\n[3/5] Matching Understat to v3 training data via SQL...")
    
    # Create temp understat_with_sofa
    cur.execute('''
        CREATE TEMP TABLE IF NOT EXISTS _ud_matched AS
        SELECT DISTINCT 
            s.id as understat_id,
            h.id as sofa_id,
            s.home_xg, s.away_xg,
            s.home_npxg, s.away_npxg,
            s.home_ppda_att, s.home_ppda_def,
            s.away_ppda_att, s.away_ppda_def,
            s.home_deep, s.away_deep,
            s.home_xga, s.away_xga,
            s.home_team, s.away_team,
            h.home_team as sofa_home, h.away_team as sofa_away,
            h.date, h.home_score, h.away_score
        FROM source_understat s
        JOIN sofa_historical_results h 
            ON h.date = s.match_date 
            AND h.home_score = s.home_goals 
            AND h.away_score = s.away_goals
        JOIN _v3ids v ON v.id = h.id
    ''')
    conn.commit()
    
    cur.execute('SELECT COUNT(*) FROM _ud_matched')
    total_matched = cur.fetchone()[0]
    log(f"  SQL-matched rows: {total_matched}")
    
    # Check for duplicates (same sofa_id with multiple understat matches)
    cur.execute('''
        SELECT sofa_id, COUNT(*) as cnt, COUNT(DISTINCT understat_id) as ud_cnt
        FROM _ud_matched
        GROUP BY sofa_id
        HAVING ud_cnt > 1
    ''')
    dups = cur.fetchall()
    log(f"  Duplicate sofa_ids (multi-Understat): {len(dups)}")
    if dups:
        log(f"  e.g. sofa_id={dups[0][0]}: {dups[0][1]} rows, {dups[0][2]} understat matches")
    
    # For duplicates, we need team name disambiguation.
    # Multiple Understat matches might share the same (date, score) 
    # We'll pick the one with matching team names.
    
    # Build dict: sofa_id -> best understat data
    log("  Resolving duplicates via team name matching...")
    
    cur.execute('SELECT * FROM _ud_matched ORDER BY sofa_id')
    cols = [c[0] for c in cur.description]
    
    sofa_ud_map = {}  # sofa_id -> understat data
    ambiguous_sofa = set()  # sofa_ids with >1 candidate
    
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        sid = d['sofa_id']
        
        if sid not in sofa_ud_map:
            sofa_ud_map[sid] = d
        else:
            ambiguous_sofa.add(sid)
            # Keep the one with matching team names
            existing = sofa_ud_map[sid]
            existing_ht = sofa_to_understat_name(existing['sofa_home'])
            existing_at = sofa_to_understat_name(existing['sofa_away'])
            new_ht = sofa_to_understat_name(d['sofa_home'])
            new_at = sofa_to_understat_name(d['sofa_away'])
            
            existing_home_ok = normalize_for_match(existing_ht) == normalize_for_match(existing['home_team'])
            existing_away_ok = normalize_for_match(existing_at) == normalize_for_match(existing['away_team'])
            new_home_ok = normalize_for_match(new_ht) == normalize_for_match(d['home_team'])
            new_away_ok = normalize_for_match(new_at) == normalize_for_match(d['away_team'])
            
            existing_score = (1 if existing_home_ok else 0) + (1 if existing_away_ok else 0)
            new_score = (1 if new_home_ok else 0) + (1 if new_away_ok else 0)
            
            if new_score > existing_score:
                sofa_ud_map[sid] = d
    
    log(f"  After resolution: {len(sofa_ud_map)} unique sofa->understat mappings")
    if ambiguous_sofa:
        log(f"  Resolved {len(ambiguous_sofa)} ambiguous mappings")
    
    # 4. Build feature matrix
    log("\n[4/5] Building Understat feature matrix...")
    
    FEATURE_NAMES = [
        'understat_xg_home', 'understat_xg_away', 'home_xg_diff_understat',
        'home_ppda_ratio', 'away_ppda_ratio', 'deep_passes_diff',
        'understat_available',
        'understat_home_npxg', 'understat_away_npxg',
        'understat_home_xga', 'understat_away_xga',
    ]
    n_features = len(FEATURE_NAMES)
    features = np.zeros((len(match_ids), n_features), dtype=np.float32)
    matched_rows = 0
    
    for i in range(len(match_ids)):
        mid = int(match_ids[i])
        ud = sofa_ud_map.get(mid)
        
        if ud is None:
            continue
        
        hxg = float(ud.get('home_xg') or 0)
        axg = float(ud.get('away_xg') or 0)
        hnpxg = float(ud.get('home_npxg') or 0)
        anpxg = float(ud.get('away_npxg') or 0)
        hxga = float(ud.get('home_xga') or 0)
        axga = float(ud.get('away_xga') or 0)
        hp_att = float(ud.get('home_ppda_att') or 0)
        hp_def = float(ud.get('home_ppda_def') or 1)
        ap_att = float(ud.get('away_ppda_att') or 0)
        ap_def = float(ud.get('away_ppda_def') or 1)
        h_deep = float(ud.get('home_deep') or 0)
        a_deep = float(ud.get('away_deep') or 0)
        
        home_ppda = min(max(hp_att / max(hp_def, 1), 0), 100)
        away_ppda = min(max(ap_att / max(ap_def, 1), 0), 100)
        
        features[i] = [
            hxg, axg, hxg - axg,
            home_ppda, away_ppda,
            h_deep - a_deep,
            1.0,
            hnpxg, anpxg, hxga, axga,
        ]
        matched_rows += 1
    
    log(f"  Matched rows: {matched_rows}/{len(match_ids)} ({100*matched_rows/len(match_ids):.2f}%)")
    if matched_rows > 0:
        mask = features[:, 6] == 1.0
        log(f"  Avg home xG: {features[mask, 0].mean():.4f}")
        log(f"  Avg away xG: {features[mask, 1].mean():.4f}")
        log(f"  Avg xG diff: {features[mask, 2].mean():.4f}")
    
    conn.close()
    
    # 5. Save
    log("\n[5/5] Saving training_data_v7.npz...")
    X_new = np.hstack([X, features]).astype(np.float32)
    
    # Feature names
    try:
        full = np.load(FEATURES_FULL, allow_pickle=True)
        orig_names = list(full['feature_names'])[:X.shape[1]]
        while len(orig_names) < X.shape[1]:
            orig_names.append(f'ft_{len(orig_names)}')
    except:
        orig_names = [f'f{i}' for i in range(X.shape[1])]
    
    all_names = np.array(orig_names + FEATURE_NAMES, dtype=object)
    
    log(f"  X: {X.shape} -> {X_new.shape}")
    log(f"  Saving...")
    np.savez_compressed(
        V7_OUTPUT,
        X=X_new, y=y, result_types=result_types,
        match_ids=match_ids, feature_names=all_names,
        understat_features_added=FEATURE_NAMES,
        matched_count=matched_rows,
    )
    
    elapsed = time.time() - t0
    log(f"\n{'=' * 70}")
    log(f"[OK] DONE in {elapsed:.1f}s ({elapsed/60:.1f} min)")
    log(f"  {V7_OUTPUT}")
    log(f"  Shape: {X_new.shape} ({X.shape[1]} base + {n_features} understat)")
    log(f"  Understat coverage: {matched_rows}/{len(match_ids)} ({100*matched_rows/len(match_ids):.2f}%)")
    log(f"{'=' * 70}")

if __name__ == '__main__':
    main()
