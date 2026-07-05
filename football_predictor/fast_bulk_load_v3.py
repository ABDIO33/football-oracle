"""
fast_bulk_load_v3.py — SQL-based bulk extraction (أسرع بمراحل)
يستخدم SQL subqueries بدلاً من Python iteration
"""

import sqlite3, os, time, gc
import numpy as np
import pandas as pd

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
NUM_CLASSES = 25

def score_to_class(home_score, away_score):
    h = max(0, min(int(home_score), 4))
    a = max(0, min(int(away_score), 4))
    return h * 5 + a

def extract_by_sql(min_date='2010-01-01'):
    t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA cache_size = -800000")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    
    print("="*60)
    print("BULK SQL EXTRACTION V3")
    print("="*60)
    
    # Step 1: Create temp table with latest walkforward per team per date
    print("[1] Creating index for fast lookups...")
    
    # Indexes - ensure they exist
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_team_date ON walkforward_state(team_name, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_glicko_team_date ON glicko_state(team_name, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_date ON sofa_historical_results(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_id ON sofa_historical_results(id)")
    
    print(f"  Indexes ready: {time.time()-t0:.1f}s")
    
    # Step 2: Extract matches with walkforward via SQL JOIN
    # Using correlated subquery to get latest walkforward before each match
    print("[2] Extracting match data with SQL JOINs...")
    
    query = f"""
    SELECT 
        r.id,
        r.home_team,
        r.away_team,
        r.home_score,
        r.away_score,
        r.date,
        r.tournament,
        -- Home walkforward
        hwf.elo AS home_elo,
        hwf.rolling_xg_for AS home_xg_for,
        hwf.rolling_xg_against AS home_xg_against,
        hwf.form_points AS home_form,
        hwf.matches_played AS home_mp,
        hwf.rolling_shots_for AS home_shots_for,
        hwf.rolling_shots_against AS home_shots_against,
        -- Away walkforward
        awf.elo AS away_elo,
        awf.rolling_xg_for AS away_xg_for,
        awf.rolling_xg_against AS away_xg_against,
        awf.form_points AS away_form,
        awf.matches_played AS away_mp,
        awf.rolling_shots_for AS away_shots_for,
        awf.rolling_shots_against AS away_shots_against,
        -- Home Glicko
        hg.glicko_rating AS home_glicko,
        hg.glicko_rd AS home_glicko_rd,
        -- Away Glicko
        ag.glicko_rating AS away_glicko,
        ag.glicko_rd AS away_glicko_rd
    FROM sofa_historical_results r
    -- Home walkforward (most recent before match)
    LEFT JOIN walkforward_state hwf ON hwf.team_name = r.home_team 
        AND hwf.date = (
            SELECT MAX(wf2.date) FROM walkforward_state wf2 
            WHERE wf2.team_name = r.home_team AND wf2.date <= r.date
        )
    -- Away walkforward
    LEFT JOIN walkforward_state awf ON awf.team_name = r.away_team 
        AND awf.date = (
            SELECT MAX(wf2.date) FROM walkforward_state wf2 
            WHERE wf2.team_name = r.away_team AND wf2.date <= r.date
        )
    -- Home Glicko
    LEFT JOIN glicko_state hg ON hg.team_name = r.home_team 
        AND hg.date = (
            SELECT MAX(g2.date) FROM glicko_state g2 
            WHERE g2.team_name = r.home_team AND g2.date <= r.date
        )
    -- Away Glicko
    LEFT JOIN glicko_state ag ON ag.team_name = r.away_team 
        AND ag.date = (
            SELECT MAX(g2.date) FROM glicko_state g2 
            WHERE g2.team_name = r.away_team AND g2.date <= r.date
        )
    WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL
      AND r.home_score >= 0 AND r.away_score >= 0
      AND r.status_type = 'finished'
      AND r.date >= '{min_date}'
    ORDER BY r.start_timestamp
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    n_total = len(df)
    print(f"  Extracted {n_total:,} rows in {time.time()-t0:.1f}s")
    
    if n_total == 0:
        return None, None, None, None
    
    # Step 3: Handle NaN/Nulls
    print("[3] Cleaning data...")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = df[col].fillna(0)
    
    # Step 4: Build features (vectorized numpy)
    print("[4] Engineering 120 features...")
    
    # Extract numpy arrays
    home_elo = df['home_elo'].values.astype(np.float32)
    away_elo = df['away_elo'].values.astype(np.float32)
    home_xgf = df['home_xg_for'].values.astype(np.float32)
    home_xga = df['home_xg_against'].values.astype(np.float32)
    away_xgf = df['away_xg_for'].values.astype(np.float32)
    away_xga = df['away_xg_against'].values.astype(np.float32)
    home_form = df['home_form'].values.astype(np.float32)
    away_form = df['away_form'].values.astype(np.float32)
    home_shots_f = df['home_shots_for'].values.astype(np.float32)
    home_shots_a = df['home_shots_against'].values.astype(np.float32)
    away_shots_f = df['away_shots_for'].values.astype(np.float32)
    away_shots_a = df['away_shots_against'].values.astype(np.float32)
    home_mp = df['home_mp'].values.astype(np.float32)
    away_mp = df['away_mp'].values.astype(np.float32)
    home_glicko = df['home_glicko'].values.astype(np.float32)
    away_glicko = df['away_glicko'].values.astype(np.float32)
    home_grd = df['home_glicko_rd'].values.astype(np.float32)
    away_grd = df['away_glicko_rd'].values.astype(np.float32)
    dates = pd.to_datetime(df['date'])
    
    n = n_total
    X = np.zeros((n, 120), dtype=np.float32)
    
    # Base features
    X[:, 0] = home_elo
    X[:, 1] = away_elo
    X[:, 2] = home_elo - away_elo  # elo_diff
    X[:, 3] = X[:, 2] ** 2  # elo_diff_sq
    X[:, 4] = np.sign(X[:, 2])  # elo_diff_sign
    X[:, 5] = home_elo + away_elo  # elo_total
    
    X[:, 6] = home_form
    X[:, 7] = away_form
    X[:, 8] = home_form - away_form  # form_diff
    X[:, 9] = X[:, 8] ** 2  # form_diff_sq
    X[:, 10] = X[:, 0] * X[:, 6]  # elo_form_home
    X[:, 11] = X[:, 1] * X[:, 7]  # elo_form_away
    X[:, 12] = X[:, 2] * X[:, 8]  # elo_diff_form_diff
    
    X[:, 13] = home_xgf
    X[:, 14] = home_xga
    X[:, 15] = away_xgf
    X[:, 16] = away_xga
    X[:, 17] = home_xgf - home_xga  # home_xg_diff
    X[:, 18] = away_xgf - away_xga  # away_xg_diff
    X[:, 19] = X[:, 0] * X[:, 13]  # elo_xg_home
    X[:, 20] = X[:, 1] * X[:, 15]  # elo_xg_away
    X[:, 21] = X[:, 6] * X[:, 13]  # form_xg_home
    X[:, 22] = X[:, 7] * X[:, 15]  # form_xg_away
    X[:, 23] = home_xgf / (away_xgf + 0.01)  # xg_ratio
    X[:, 24] = home_xgf / (home_xga + 0.01)  # xgf_xga_home
    X[:, 25] = away_xgf / (away_xga + 0.01)  # xgf_xga_away
    X[:, 26] = home_xgf + away_xgf  # combined_xg
    
    X[:, 27] = home_shots_f
    X[:, 28] = home_shots_a
    X[:, 29] = away_shots_f
    X[:, 30] = away_shots_a
    X[:, 31] = home_shots_f / (away_shots_f + 0.01)  # shots_ratio
    X[:, 32] = home_xgf / (home_shots_f + 0.01)  # shot_eff_home
    X[:, 33] = away_xgf / (away_shots_f + 0.01)  # shot_eff_away
    X[:, 34] = home_mp / 38.0  # fatigue_home
    X[:, 35] = away_mp / 38.0  # fatigue_away
    X[:, 36] = home_mp - away_mp  # matches_diff
    
    X[:, 37] = home_glicko
    X[:, 38] = away_glicko
    X[:, 39] = home_glicko - away_glicko  # glicko_diff
    X[:, 40] = 1.0 / (home_grd + 1)  # home_glicko_confidence
    X[:, 41] = 1.0 / (away_grd + 1)  # away_glicko_confidence
    X[:, 42] = home_grd + away_grd  # glicko_rd_sum
    
    # Polynomial transforms of key features
    key_feat_indices = [2, 8, 39, 23]  # elo_diff, form_diff, glicko_diff, xg_ratio
    for i, ki in enumerate(key_feat_indices):
        vals = X[:, ki]
        base = 43 + i * 3
        X[:, base] = np.sqrt(np.abs(vals) + 0.01) * np.sign(vals)
        X[:, base + 1] = np.log(np.abs(vals) + 0.01 + 1e-10)
        X[:, base + 2] = np.abs(vals)
    
    # Time features
    months = dates.dt.month.values.astype(np.float32)
    days = dates.dt.dayofweek.values.astype(np.float32)
    doy = dates.dt.dayofyear.values.astype(np.float32)
    X[:, 55] = months
    X[:, 56] = np.sin(2 * np.pi * months / 12)
    X[:, 57] = np.cos(2 * np.pi * months / 12)
    X[:, 58] = days
    X[:, 59] = (days >= 5).astype(np.float32)
    X[:, 60] = doy / 365.0
    
    # Interaction features (key features × each other)
    ki_indices = [2, 8, 39, 23, 17, 18]  # elo_diff, form_diff, glicko_diff, xg_ratio, home_xg_diff, away_xg_diff
    inter_idx = 61
    for i, fi in enumerate(ki_indices):
        for fj in ki_indices[i+1:]:
            if inter_idx < 100:
                X[:, inter_idx] = X[:, fi] * X[:, fj]
                inter_idx += 1
    
    # Elo × Poisson (using xG as proxy)
    X[:, 100] = X[:, 0] * X[:, 13]  # home
    X[:, 101] = X[:, 1] * X[:, 15]  # away
    X[:, 102] = X[:, 6] * X[:, 13]  # form_xg
    X[:, 103] = X[:, 7] * X[:, 15]
    X[:, 104] = X[:, 2] * np.abs(X[:, 17])  # elo_x_home_xg
    X[:, 105] = -X[:, 2] * np.abs(X[:, 18])  # elo_x_away_xg
    
    # Momentum features
    X[:, 106] = X[:, 6] * np.clip(X[:, 2], -200, 200)  # momentum_home
    X[:, 107] = X[:, 7] * np.clip(-X[:, 2], -200, 200)  # momentum_away
    X[:, 108] = X[:, 106] - X[:, 107]  # momentum_diff
    
    # Ratio features
    X[:, 109] = X[:, 0] / (X[:, 1] + 1)
    X[:, 110] = X[:, 13] / (X[:, 16] + 0.01)
    X[:, 111] = X[:, 15] / (X[:, 14] + 0.01)
    X[:, 112] = X[:, 17] - X[:, 18]
    X[:, 113] = X[:, 34] - X[:, 35]
    
    # Target
    home_scores = df['home_score'].values.astype(int)
    away_scores = df['away_score'].values.astype(int)
    y = np.array([score_to_class(h, a) for h, a in zip(home_scores, away_scores)], dtype=np.int32)
    result_types = np.array([0 if h > a else 1 if h == a else 2 
                            for h, a in zip(home_scores, away_scores)], dtype=np.int32)
    
    print(f"  Features: {X.shape}, classes: {len(np.unique(y))}")
    print(f"  Time: {time.time()-t0:.1f}s")
    
    return X, y, result_types, df['id'].values


def save_data(X, y, rt, ids):
    out_path = os.path.join(os.path.dirname(__file__), 'training_data_v3.npz')
    np.savez_compressed(out_path, X=X, y=y, result_types=rt, match_ids=ids)
    print(f"\nSaved: {out_path}")
    print(f"  X: {X.shape} ({X.nbytes/1024/1024:.0f} MB)")
    print(f"  y: {y.shape}")
    return out_path


if __name__ == '__main__':
    t0 = time.time()
    X, y, rt, ids = extract_by_sql(min_date='2010-01-01')
    if X is not None and len(y) > 0:
        print(f"\nDataset: {len(y):,} matches, {X.shape[1]} features")
        print(f"Home wins: {(rt==0).sum():,} | Draws: {(rt==1).sum():,} | Away wins: {(rt==2).sum():,}")
        save_data(X, y, rt, ids)
    print(f"\nTotal time: {(time.time()-t0)/60:.1f} minutes")
