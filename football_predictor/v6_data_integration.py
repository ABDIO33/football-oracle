"""
v6_data_integration.py — Integrate expanded features into V6 training data
Loads base 85 features from DB, runs expand_features_row(), saves v6_preprocessed.npz
"""
import sys, os, sqlite3, json, math, time
import numpy as np
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
OUT_DIR = os.path.join(os.path.dirname(__file__), 'models')

from expand_features import expand_features_row, get_new_feature_names, BASE_FEATURES
from direct_predictor import FEATURES, score_to_class

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def load_base_data(limit_years=10):
    """Load base training data from DB with enhanced features"""
    conn = sqlite3.connect(DB)
    log('Loading matches from DB...')
    
    cutoff = f'{2026 - limit_years}-01-01'
    rows = conn.execute("""
        SELECT r.id, r.home_team, r.away_team, r.home_score, r.away_score,
               r.tournament, r.date, r.start_timestamp,
               w.elo as home_elo,
               (SELECT elo FROM walkforward_state WHERE team_name = r.away_team AND date <= r.date ORDER BY date DESC LIMIT 1) as away_elo
        FROM sofa_historical_results r
        LEFT JOIN walkforward_state w ON w.team_name = r.home_team AND w.date = r.date
        WHERE r.status_type = 'finished'
        AND r.date >= ?
        AND r.home_score IS NOT NULL AND r.away_score IS NOT NULL
        AND r.home_score >= 0 AND r.away_score >= 0
        AND r.home_score <= 4 AND r.away_score <= 4
        ORDER BY r.id
    """, (cutoff,))
    
    data = rows.fetchall()
    conn.close()
    log(f'Loaded {len(data):,} matches from {cutoff}')
    return data

def build_feature_matrix(rows):
    """Build full feature matrix with expanded features"""
    conn = sqlite3.connect(DB)
    
    X_list = []
    y_list = []
    match_ids = []
    errors = 0
    total = len(rows)
    new_feat_names = get_new_feature_names()
    all_feat_names = FEATURES + new_feat_names
    
    log(f'Total features: {len(FEATURES)} base + {len(new_feat_names)} new = {len(all_feat_names)}')
    
    for i, row in enumerate(rows):
        if i % 10000 == 0 and i > 0:
            log(f'  [{i:,}/{total:,}] errors={errors}')
        
        try:
            mid, ht, at, hs, aws, tmt, dt, ts = row[:8]
            
            y = score_to_class(hs, aws)
            
            base_row = {}
            for feat in FEATURES:
                base_row[feat] = 0.0
            
            base_row['home_team'] = ht
            base_row['away_team'] = at
            base_row['date'] = dt
            base_row['home_elo'] = float(row[8] or 1500)
            base_row['away_elo'] = float(row[9] or 1500)
            
            expanded = expand_features_row(conn, base_row, tmt)
            
            X_row = []
            for feat in all_feat_names:
                X_row.append(float(expanded.get(feat, 0.0)))
            
            X_list.append(X_row)
            y_list.append(y)
            match_ids.append(mid)
            
        except Exception as e:
            errors += 1
            if errors <= 5:
                log(f'  Error row {i}: {e}')
    
    conn.close()
    
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    
    log(f'\nFeature matrix: {X.shape}')
    log(f'Labels: {y.shape}')
    log(f'Errors: {errors}')
    
    return X, y, match_ids, all_feat_names

def save_dataset(X, y, match_ids, feat_names):
    """Save preprocessed dataset"""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, 'v6_preprocessed.npz')
    np.savez_compressed(path, X=X, y=y, match_ids=match_ids, feat_names=feat_names)
    log(f'Saved: {path} ({os.path.getsize(path)/1024/1024:.1f} MB)')

def check_class_distribution(y):
    """Print class distribution"""
    unique, counts = np.unique(y, return_counts=True)
    scores = [(h,a) for h in range(5) for a in range(5)]
    log('\nClass distribution:')
    for cls, cnt in sorted(zip(unique, counts), key=lambda x: -x[1]):
        h, a = scores[cls]
        log(f'  {h}-{a}: {cnt:>6,} ({cnt/len(y)*100:.2f}%)')

if __name__ == '__main__':
    log('=' * 50)
    log('V6 DATA INTEGRATION STARTED')
    log('=' * 50)
    
    start = time.time()
    
    data = load_base_data(limit_years=10)
    X, y, match_ids, feat_names = build_feature_matrix(data)
    check_class_distribution(y)
    save_dataset(X, y, match_ids, feat_names)
    
    elapsed = time.time() - start
    log(f'\nDone! Elapsed: {elapsed/60:.1f} minutes')
