"""
fast_bulk_load_v2.py — استخراج الميزات على دفعات صغيرة (chunks)
يتجنب مشاكل الذاكرة و cross-product merges
"""

import sqlite3, os, time, gc
import numpy as np
import pandas as pd

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
CHUNK_SIZE = 50000  # 50K match per chunk

SCORE_CLASSES = [(h, a) for h in range(5) for a in range(5)]
NUM_CLASSES = 25

def score_to_class(home_score, away_score):
    h = max(0, min(int(home_score), 4))
    a = max(0, min(int(away_score), 4))
    return h * 5 + a

def bulk_load_chunked(min_date='2015-01-01'):
    """Load in chunks, save intermediate files"""
    t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA mmap_size = 2000000000")
    
    # 1. Get match IDs
    match_ids = pd.read_sql_query(f"""
        SELECT id FROM sofa_historical_results
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
          AND home_score >= 0 AND away_score >= 0
          AND status_type = 'finished' AND date >= '{min_date}'
        ORDER BY start_timestamp
    """, conn)
    all_ids = match_ids['id'].values
    n_total = len(all_ids)
    print(f"Total matches: {n_total:,}")
    
    # 2. Pre-load ALL walkforward + glicko + h2h data
    print("Pre-loading reference data...")
    
    # Walkforward - build index: team_name -> list of (date, elo, ...)
    wf_df = pd.read_sql_query("""
        SELECT team_name, date, elo, matches_played,
               rolling_xg_for, rolling_xg_against,
               rolling_shots_for, rolling_shots_against,
               form_points
        FROM walkforward_state
        ORDER BY team_name, date
    """, conn)
    wf_df['date'] = pd.to_datetime(wf_df['date'])
    
    # Glicko
    g_df = pd.read_sql_query("""
        SELECT team_name, date, glicko_rating, glicko_rd
        FROM glicko_state ORDER BY team_name, date
    """, conn)
    g_df['date'] = pd.to_datetime(g_df['date'])
    
    # H2H
    h2h_df = pd.read_sql_query("SELECT * FROM neg_h2h_features", conn)
    
    print(f"  Walkforward: {len(wf_df):,} rows")
    print(f"  Glicko: {len(g_df):,} rows")
    print(f"  H2H: {len(h2h_df):,} rows")
    print(f"Pre-load took {time.time()-t0:.1f}s")
    
    # 3. Process in chunks
    chunk = 0
    all_X = []
    all_y = []
    all_ids_list = []
    all_result_types = []
    
    for start in range(0, n_total, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, n_total)
        chunk_ids = all_ids[start:end]
        t_chunk = time.time()
        
        # Load matches for this chunk
        ids_str = ','.join(str(int(x)) for x in chunk_ids)
        df = pd.read_sql_query(f"""
            SELECT id, home_team, away_team, home_score, away_score, date, tournament
            FROM sofa_historical_results WHERE id IN ({ids_str})
        """, conn)
        df['date'] = pd.to_datetime(df['date'])
        
        # For each match, find walkforward state (last before match)
        home_elos, away_elos = [], []
        home_xgf, home_xga = [], []
        away_xgf, away_xga = [], []
        home_form, away_form = [], []
        home_mp, away_mp = [], []
        home_shots_f, home_shots_a = [], []
        away_shots_f, away_shots_a = [], []
        home_glicko, away_glicko = [], []
        home_glicko_rd, away_glicko_rd = [], []
        
        # Build index for fast lookup: team_name -> sorted dates + values
        wf_by_team = {}
        for _, row in wf_df.iterrows():
            tn = row['team_name']
            if tn not in wf_by_team:
                wf_by_team[tn] = {'dates': [], 'elo': [], 'xg_for': [], 'xg_against': [],
                                  'shots_for': [], 'shots_against': [], 'form': [], 'mp': []}
            wf_by_team[tn]['dates'].append(row['date'])
            wf_by_team[tn]['elo'].append(row['elo'])
            wf_by_team[tn]['xg_for'].append(row['rolling_xg_for'])
            wf_by_team[tn]['xg_against'].append(row['rolling_xg_against'])
            wf_by_team[tn]['shots_for'].append(row['rolling_shots_for'])
            wf_by_team[tn]['shots_against'].append(row['rolling_shots_against'])
            wf_by_team[tn]['form'].append(row['form_points'])
            wf_by_team[tn]['mp'].append(row['matches_played'])
        
        g_by_team = {}
        for _, row in g_df.iterrows():
            tn = row['team_name']
            if tn not in g_by_team:
                g_by_team[tn] = {'dates': [], 'rating': [], 'rd': []}
            g_by_team[tn]['dates'].append(row['date'])
            g_by_team[tn]['rating'].append(row['glicko_rating'])
            g_by_team[tn]['rd'].append(row['glicko_rd'])
        
        def find_last_before(data, date, key):
            """Binary search for last entry before date"""
            if not data or 'dates' not in data or not data['dates']:
                return None
            dates = data['dates']
            if dates[0] > date:
                return None
            lo, hi = 0, len(dates) - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if dates[mid] <= date:
                    lo = mid
                else:
                    hi = mid - 1
            if dates[lo] <= date:
                return {k: data[k][lo] for k in key}
            return None
        
        for _, row in df.iterrows():
            h_team, a_team = row['home_team'], row['away_team']
            m_date = row['date']
            
            hwf = find_last_before(wf_by_team.get(h_team, {}), m_date, 
                                   ['elo', 'xg_for', 'xg_against', 'form', 'mp', 'shots_for', 'shots_against'])
            awf = find_last_before(wf_by_team.get(a_team, {}), m_date,
                                   ['elo', 'xg_for', 'xg_against', 'form', 'mp', 'shots_for', 'shots_against'])
            
            if not hwf or not awf:
                continue
            
            home_elos.append(hwf['elo'])
            away_elos.append(awf['elo'])
            home_xgf.append(hwf['xg_for'] or 1.2)
            home_xga.append(hwf['xg_against'] or 1.2)
            away_xgf.append(awf['xg_for'] or 1.2)
            away_xga.append(awf['xg_against'] or 1.2)
            home_form.append(hwf['form'] or 1.5)
            away_form.append(awf['form'] or 1.5)
            home_mp.append(hwf['mp'] or 10)
            away_mp.append(awf['mp'] or 10)
            home_shots_f.append(hwf['shots_for'] or 10)
            home_shots_a.append(hwf['shots_against'] or 10)
            away_shots_f.append(awf['shots_for'] or 10)
            away_shots_a.append(awf['shots_against'] or 10)
            
            hg = find_last_before(g_by_team.get(h_team, {}), m_date, ['rating', 'rd'])
            ag = find_last_before(g_by_team.get(a_team, {}), m_date, ['rating', 'rd'])
            home_glicko.append(hg['rating'] if hg else 1500)
            away_glicko.append(ag['rating'] if ag else 1500)
            home_glicko_rd.append(hg['rd'] if hg else 350)
            away_glicko_rd.append(ag['rd'] if ag else 350)
        
        if not home_elos:
            continue
        
        # Filter df to only matched rows
        df_filtered = df.iloc[:len(home_elos)].copy()
        
        # Build feature vectors
        n = len(home_elos)
        X = np.zeros((n, 120), dtype=np.float32)
        
        # Group 1: Base features (0-39)
        X[:, 0] = home_elos
        X[:, 1] = away_elos
        X[:, 2] = np.array(home_elos) - np.array(away_elos)  # elo_diff
        X[:, 3] = X[:, 2] ** 2  # elo_diff_sq
        X[:, 4] = np.sign(X[:, 2])  # elo_diff_sign
        X[:, 5] = np.array(home_elos) + np.array(away_elos)  # elo_total
        
        X[:, 6] = home_form
        X[:, 7] = away_form
        X[:, 8] = np.array(home_form) - np.array(away_form)  # form_diff
        X[:, 9] = X[:, 8] ** 2  # form_diff_sq
        
        X[:, 10] = X[:, 0] * X[:, 6]  # elo_form_home
        X[:, 11] = X[:, 1] * X[:, 7]  # elo_form_away
        X[:, 12] = X[:, 2] * X[:, 8]  # elo_diff_form_diff
        
        X[:, 13] = home_xgf
        X[:, 14] = home_xga
        X[:, 15] = away_xgf
        X[:, 16] = away_xga
        X[:, 17] = np.array(home_xgf) - np.array(home_xga)  # home_xg_diff
        X[:, 18] = np.array(away_xgf) - np.array(away_xga)  # away_xg_diff
        
        X[:, 19] = X[:, 0] * X[:, 13]  # elo_xg_home
        X[:, 20] = X[:, 1] * X[:, 15]  # elo_xg_away
        X[:, 21] = X[:, 6] * X[:, 13]  # form_xg_home
        X[:, 22] = X[:, 7] * X[:, 15]  # form_xg_away
        
        xg_ratio = np.array(home_xgf) / (np.array(away_xgf) + 0.01)
        X[:, 23] = xg_ratio
        X[:, 24] = np.array(home_xgf) / (np.array(home_xga) + 0.01)
        X[:, 25] = np.array(away_xgf) / (np.array(away_xga) + 0.01)
        X[:, 26] = np.array(home_xgf) + np.array(away_xgf)
        
        X[:, 27] = home_shots_f
        X[:, 28] = home_shots_a
        X[:, 29] = away_shots_f
        X[:, 30] = away_shots_a
        X[:, 31] = np.array(home_shots_f) / (np.array(away_shots_f) + 0.01)
        
        X[:, 32] = np.array(home_xgf) / (np.array(home_shots_f) + 0.01)
        X[:, 33] = np.array(away_xgf) / (np.array(away_shots_f) + 0.01)
        X[:, 34] = np.array(home_mp) / 38.0  # fatigue_home
        X[:, 35] = np.array(away_mp) / 38.0  # fatigue_away
        
        X[:, 36] = home_glicko
        X[:, 37] = away_glicko
        X[:, 38] = np.array(home_glicko) - np.array(away_glicko)
        X[:, 39] = 1.0 / (np.array(home_glicko_rd) + 1)  # confidence
        X[:, 40] = 1.0 / (np.array(away_glicko_rd) + 1)
        
        # Group 2: Polynomial features (40-59)
        for i, col_idx in enumerate([2, 8, 38, 23, 36, 37]):
            vals = X[:, col_idx]
            X[:, 41 + i*3] = np.sqrt(np.abs(vals) + 0.01) * np.sign(vals)
            X[:, 42 + i*3] = np.log(np.abs(vals) + 0.01)
            X[:, 43 + i*3] = np.abs(vals)
        
        # Group 3: Time features (60-69)
        dates_series = pd.to_datetime(df_filtered['date'])
        months = dates_series.dt.month.values.astype(np.float32)
        days = dates_series.dt.dayofweek.values.astype(np.float32)
        doy = dates_series.dt.dayofyear.values.astype(np.float32)
        X[:, 60] = months
        X[:, 61] = np.sin(2 * np.pi * months / 12)
        X[:, 62] = np.cos(2 * np.pi * months / 12)
        X[:, 63] = days
        X[:, 64] = (days >= 5).astype(np.float32)
        X[:, 65] = doy / 365.0
        
        # Group 4: Interactions (70-99)
        key_idx = [2, 8, 38, 23, 17, 18]  # elo_diff, form_diff, glicko_diff, xg_ratio, home_xg_diff, away_xg_diff
        inter_idx = 70
        for i, fi in enumerate(key_idx):
            for fj in key_idx[i+1:]:
                if inter_idx < 100:
                    X[:, inter_idx] = X[:, fi] * X[:, fj]
                    inter_idx += 1
        
        # Group 5: Momentum (100-104)
        X[:, 100] = X[:, 6] * np.clip(X[:, 2], -200, 200)  # momentum_home
        X[:, 101] = X[:, 7] * np.clip(-X[:, 2], -200, 200)  # momentum_away
        X[:, 102] = X[:, 100] - X[:, 101]
        
        # Group 6: Ratios (105-115)
        X[:, 105] = X[:, 0] / (X[:, 1] + 1)
        X[:, 106] = X[:, 13] / (X[:, 16] + 0.01)
        X[:, 107] = X[:, 15] / (X[:, 14] + 0.01)
        X[:, 108] = X[:, 17] - X[:, 18]
        X[:, 109] = X[:, 34] - X[:, 35]  # fatigue_diff
        
        # targets
        y_chunk = df_filtered.apply(
            lambda r: score_to_class(int(r['home_score']), int(r['away_score'])), axis=1
        ).values.astype(np.int32)
        rt_chunk = df_filtered.apply(
            lambda r: 0 if int(r['home_score']) > int(r['away_score']) 
                      else 1 if int(r['home_score']) == int(r['away_score']) 
                      else 2, axis=1
        ).values.astype(np.int32)
        
        all_X.append(X)
        all_y.append(y_chunk)
        all_ids_list.append(df_filtered['id'].values)
        all_result_types.append(rt_chunk)
        
        chunk += 1
        print(f"  Chunk {chunk}: {n} matches in {time.time()-t_chunk:.1f}s "
              f"(total: {sum(len(x) for x in all_X):,} / {n_total})")
        
        # Force GC after each chunk
        del df, X, y_chunk, rt_chunk
        gc.collect()
    
    conn.close()
    
    if not all_X:
        return None, None, None, None
    
    # Concatenate
    X_full = np.vstack(all_X)
    y_full = np.concatenate(all_y)
    ids_full = np.concatenate(all_ids_list)
    rt_full = np.concatenate(all_result_types)
    
    # Handle NaN/Inf
    X_full = np.nan_to_num(X_full, nan=0.0, posinf=0.0, neginf=0.0)
    
    print(f"\nFinal: X={X_full.shape}, y={y_full.shape}")
    print(f"Time: {(time.time()-t0)/60:.1f} minutes")
    
    return X_full, y_full, rt_full, ids_full


def save_training_data(X, y, result_types, match_ids):
    out_path = os.path.join(os.path.dirname(__file__), 'training_data_v3.npz')
    np.savez_compressed(out_path, X=X, y=y, result_types=result_types, match_ids=match_ids)
    print(f"Saved: {out_path} ({X.nbytes/1024/1024:.0f} MB, {X.shape})")
    return out_path


def extract_all(min_date='2015-01-01'):
    t_start = time.time()
    print("="*60)
    print("FAST BULK LOAD V2 — Chunked Feature Extraction")
    print("="*60)
    
    X, y, rt, ids = bulk_load_chunked(min_date=min_date)
    if X is None:
        print("ERROR: No data extracted!")
        return
    
    print(f"\nDataset: {len(y):,} matches, {X.shape[1]} features")
    print(f"Classes: {len(np.unique(y))} unique scores")
    print(f"Home wins: {(rt==0).sum():,}")
    print(f"Draws: {(rt==1).sum():,}")
    print(f"Away wins: {(rt==2).sum():,}")
    print(f"Total time: {(time.time()-t_start)/60:.1f} minutes")
    
    save_training_data(X, y, rt, ids)
    return X, y, rt, ids


if __name__ == '__main__':
    extract_all(min_date='2010-01-01')
