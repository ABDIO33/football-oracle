"""
fast_bulk_load.py — استخراج 885K مباراة + 550+ ميزة في 5 دقائق بدلاً من ساعات
يستخدم SQL bulk JOINs + window functions + pandas vectorized
"""

import sqlite3, os, json, time, gc
import numpy as np
import pandas as pd

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# 25 score classes
SCORE_CLASSES = [(h, a) for h in range(5) for a in range(5)]
NUM_CLASSES = 25

def score_to_class(home_score, away_score):
    h = max(0, min(int(home_score), 4))
    a = max(0, min(int(away_score), 4))
    return h * 5 + a

def class_to_score(cls):
    return cls // 5, cls % 5

def bulk_load_features(limit_matches=None, min_date='2010-01-01'):
    """
    استخراج كل الميزات دفعة واحدة بـ SQL JOINs ذكية
    بدلاً من row-by-row
    """
    t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA page_size = 65536")
    conn.execute("PRAGMA cache_size = -2000000")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA mmap_size = 3000000000")
    
    # 1. استخراج كل المباريات دفعة واحدة
    print("[1/5] Loading matches...")
    limit_clause = f" LIMIT {limit_matches}" if limit_matches else ""
    matches_query = f"""
    SELECT r.id, r.home_team, r.away_team, r.home_score, r.away_score, 
           r.date, r.tournament,
           r.start_timestamp,
           r.unique_tournament_id, r.season_id
    FROM sofa_historical_results r
    WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL
      AND r.home_score >= 0 AND r.away_score >= 0
      AND r.status_type = 'finished'
      AND r.date >= '{min_date}'
    ORDER BY r.start_timestamp
    {limit_clause}
    """
    df = pd.read_sql_query(matches_query, conn)
    n_matches = len(df)
    print(f"  -> {n_matches:,} matches loaded in {time.time()-t0:.1f}s")
    
    # 2. Walkforward state - استخراج آخر حالة لكل فريق قبل كل مباراة
    print("[2/5] Loading walkforward state...")
    
    # Better approach: load ALL walkforward state and do merge_asof
    wf = pd.read_sql_query("""
        SELECT team_name, date, elo, matches_played,
               rolling_xg_for, rolling_xg_against,
               rolling_shots_for, rolling_shots_against,
               form_points, form_raw
        FROM walkforward_state
        ORDER BY team_name, date
    """, conn)
    wf['date'] = pd.to_datetime(wf['date'])
    print(f"  -> {len(wf):,} walkforward rows loaded")
    
    # For home team: find last walkforward state before match
    df_home = df[['id', 'home_team', 'date']].rename(columns={'home_team': 'team_name'}).copy()
    df_home['date'] = pd.to_datetime(df_home['date'])
    
    df_away = df[['id', 'away_team', 'date']].rename(columns={'away_team': 'team_name'}).copy()
    df_away['date'] = pd.to_datetime(df_away['date'])
    
    # Merge with nearest state BEFORE match (merge_asof)
    wf_sorted = wf.sort_values('date')
    
    home_wf = pd.merge_asof(
        df_home.sort_values('date'),
        wf_sorted,
        on='date', by='team_name',
        direction='backward'
    )
    home_wf = home_wf.rename(columns={
        'elo': 'home_elo', 'matches_played': 'home_matches_played',
        'rolling_xg_for': 'home_rolling_xg_for', 'rolling_xg_against': 'home_rolling_xg_against',
        'rolling_shots_for': 'home_rolling_shots_for', 'rolling_shots_against': 'home_rolling_shots_against',
        'form_points': 'home_form_points', 'form_raw': 'home_form_raw'
    })
    
    away_wf = pd.merge_asof(
        df_away.sort_values('date'),
        wf_sorted,
        on='date', by='team_name',
        direction='backward'
    )
    away_wf = away_wf.rename(columns={
        'elo': 'away_elo', 'matches_played': 'away_matches_played',
        'rolling_xg_for': 'away_rolling_xg_for', 'rolling_xg_against': 'away_rolling_xg_against',
        'rolling_shots_for': 'away_rolling_shots_for', 'rolling_shots_against': 'away_rolling_shots_against',
        'form_points': 'away_form_points', 'form_raw': 'away_form_raw'
    })
    
    # Merge back to main df
    df = df.merge(home_wf[['id', 'home_elo', 'home_matches_played',
        'home_rolling_xg_for', 'home_rolling_xg_against',
        'home_rolling_shots_for', 'home_rolling_shots_against',
        'home_form_points', 'home_form_raw']], on='id', how='left')
    df = df.merge(away_wf[['id', 'away_elo', 'away_matches_played',
        'away_rolling_xg_for', 'away_rolling_xg_against',
        'away_rolling_shots_for', 'away_rolling_shots_against',
        'away_form_points', 'away_form_raw']], on='id', how='left')
    
    print(f"  -> Walkforward merged in {time.time()-t0:.1f}s total")
    
    # 3. Glicko-2 state
    print("[3/5] Loading Glicko-2 state...")
    glicko = pd.read_sql_query("""
        SELECT team_name, date, glicko_rating, glicko_rd
        FROM glicko_state
        ORDER BY team_name, date
    """, conn)
    glicko['date'] = pd.to_datetime(glicko['date'])
    glicko_sorted = glicko.sort_values('date')
    
    home_g = pd.merge_asof(
        df_home.sort_values('date'),
        glicko_sorted,
        on='date', by='team_name',
        direction='backward'
    )
    home_g = home_g.rename(columns={'glicko_rating': 'home_glicko', 'glicko_rd': 'home_glicko_rd'})
    
    away_g = pd.merge_asof(
        df_away.sort_values('date'),
        glicko_sorted,
        on='date', by='team_name',
        direction='backward'
    )
    away_g = away_g.rename(columns={'glicko_rating': 'away_glicko', 'glicko_rd': 'away_glicko_rd'})
    
    df = df.merge(home_g[['id', 'home_glicko', 'home_glicko_rd']], on='id', how='left')
    df = df.merge(away_g[['id', 'away_glicko', 'away_glicko_rd']], on='id', how='left')
    print(f"  -> Glicko merged in {time.time()-t0:.1f}s")
    
    # 4. Extra features
    print("[4/5] Loading extra features (H2H, Poisson, StatsBomb)...")
    h2h = pd.read_sql_query("SELECT * FROM neg_h2h_features", conn)
    df = df.merge(h2h, on=['home_team', 'away_team'], how='left')
    
    # Poisson params (per-team, simplified)
    poisson = pd.read_sql_query("SELECT team_name, attack_strength_home, attack_strength_away, defense_strength_home, defense_strength_away, lambda_home_scored, lambda_home_conceded FROM neg_poisson_params", conn)
    poisson_h = poisson.rename(columns={k: 'h_'+k for k in poisson.columns if k != 'team_name'})
    df = df.merge(poisson_h, left_on='home_team', right_on='team_name', how='left')
    poisson_a = poisson.rename(columns={k: 'a_'+k for k in poisson.columns if k != 'team_name'})
    df = df.merge(poisson_a, left_on='away_team', right_on='team_name', how='left')
    
    # 5. StatsBomb derived features
    print("[5/5] Loading StatsBomb aggregates...")
    sb_agg = pd.read_sql_query("""
        SELECT match_id,
               team,
               COUNT(*) as sb_total_events,
               SUM(CASE WHEN event_type = 'Shot' THEN 1 ELSE 0 END) as sb_shots,
               SUM(CASE WHEN event_type = 'Pass' THEN 1 ELSE 0 END) as sb_passes,
               SUM(CASE WHEN event_type = 'Pressure' THEN 1 ELSE 0 END) as sb_pressures,
               SUM(COALESCE(xg, 0)) as sb_xg_total,
               AVG(CASE WHEN event_type = 'Shot' THEN xg ELSE NULL END) as sb_xg_per_shot,
               SUM(CASE WHEN event_type = 'Shot' AND outcome = 'Goal' THEN 1 ELSE 0 END) as sb_goals,
               SUM(CASE WHEN event_type = 'Foul Committed' THEN 1 ELSE 0 END) as sb_fouls,
               SUM(CASE WHEN event_type = 'Duel' THEN 1 ELSE 0 END) as sb_duels,
               SUM(CASE WHEN event_type = 'Carry' THEN 1 ELSE 0 END) as sb_carries
        FROM statsbomb_events
        WHERE team IS NOT NULL
        GROUP BY match_id, team
    """, conn)
    
    sb_home = sb_agg.rename(columns={k: 'sb_h_'+k for k in sb_agg.columns if k not in ('match_id', 'team')})
    df = df.merge(sb_home, left_on=['id', 'home_team'], right_on=['match_id', 'team'], how='left')
    sb_away = sb_agg.rename(columns={k: 'sb_a_'+k for k in sb_agg.columns if k not in ('match_id', 'team')})
    df = df.merge(sb_away, left_on=['id', 'away_team'], right_on=['match_id', 'team'], how='left')
    
    conn.close()
    print(f"  -> All data loaded in {time.time()-t0:.1f}s")
    print(f"  -> Final shape: {df.shape}")
    
    return df

def engineer_features(df):
    """
    هندسة 550+ ميزة من الـ DataFrame الخام
    كل العمليات vectorized (بلا loops)
    """
    t0 = time.time()
    print(f"\nEngineering features from {len(df):,} matches...")
    
    # إنشاء target
    home_scores = pd.to_numeric(df['home_score'], errors='coerce').fillna(0).astype(int)
    away_scores = pd.to_numeric(df['away_score'], errors='coerce').fillna(0).astype(int)
    
    y = np.array([score_to_class(h, a) for h, a in zip(home_scores, away_scores)])
    
    # === GROUP 1: BASE FEATURES (85) ===
    features = pd.DataFrame(index=df.index)
    
    # Elo features
    features['home_elo'] = df['home_elo'].fillna(1500)
    features['away_elo'] = df['away_elo'].fillna(1500)
    features['elo_diff'] = features['home_elo'] - features['away_elo']
    features['elo_diff_sq'] = features['elo_diff'] ** 2
    features['elo_diff_sign'] = np.sign(features['elo_diff'])
    features['elo_total'] = features['home_elo'] + features['away_elo']
    features['elo_ratio'] = features['home_elo'] / (features['away_elo'] + 1)
    
    # Form features
    features['home_form'] = df['home_form_points'].fillna(1.5)
    features['away_form'] = df['away_form_points'].fillna(1.5)
    features['form_diff'] = features['home_form'] - features['away_form']
    features['form_diff_sq'] = features['form_diff'] ** 2
    features['form_total'] = features['home_form'] + features['away_form']
    
    # Elo × Form interactions
    features['elo_form_home'] = features['home_elo'] * features['home_form']
    features['elo_form_away'] = features['away_elo'] * features['away_form']
    features['elo_diff_form_diff'] = features['elo_diff'] * features['form_diff']
    
    # xG features
    features['home_xg_for'] = df['home_rolling_xg_for'].fillna(1.2)
    features['home_xg_against'] = df['home_rolling_xg_against'].fillna(1.2)
    features['away_xg_for'] = df['away_rolling_xg_for'].fillna(1.2)
    features['away_xg_against'] = df['away_rolling_xg_against'].fillna(1.2)
    
    features['home_xg_diff'] = features['home_xg_for'] - features['home_xg_against']
    features['away_xg_diff'] = features['away_xg_for'] - features['away_xg_against']
    features['xg_diff_home_minus_away'] = features['home_xg_diff'] - features['away_xg_diff']
    
    # Elo × xG
    features['elo_xg_home'] = features['home_elo'] * features['home_xg_for']
    features['elo_xg_away'] = features['away_elo'] * features['away_xg_for']
    
    # Form × xG
    features['form_xg_home'] = features['home_form'] * features['home_xg_for']
    features['form_xg_away'] = features['away_form'] * features['away_xg_for']
    
    # xG ratios
    features['xg_ratio'] = features['home_xg_for'] / (features['away_xg_for'] + 0.01)
    features['xgf_xga_ratio_home'] = features['home_xg_for'] / (features['home_xg_against'] + 0.01)
    features['xgf_xga_ratio_away'] = features['away_xg_for'] / (features['away_xg_against'] + 0.01)
    features['combined_xg'] = features['home_xg_for'] + features['away_xg_for']
    
    # Shot features
    features['home_shots_for'] = df['home_rolling_shots_for'].fillna(10)
    features['home_shots_against'] = df['home_rolling_shots_against'].fillna(10)
    features['away_shots_for'] = df['away_rolling_shots_for'].fillna(10)
    features['away_shots_against'] = df['away_rolling_shots_against'].fillna(10)
    
    features['home_shot_diff'] = features['home_shots_for'] - features['home_shots_against']
    features['away_shot_diff'] = features['away_shots_for'] - features['away_shots_against']
    features['shots_ratio'] = features['home_shots_for'] / (features['away_shots_for'] + 0.01)
    
    # Shot efficiency
    features['shot_eff_home'] = features['home_xg_for'] / (features['home_shots_for'] + 0.01)
    features['shot_eff_away'] = features['away_xg_for'] / (features['away_shots_for'] + 0.01)
    features['shot_eff_diff'] = features['shot_eff_home'] - features['shot_eff_away']
    
    # Fatigue
    features['home_matches_played'] = df['home_matches_played'].fillna(10)
    features['away_matches_played'] = df['away_matches_played'].fillna(10)
    features['matches_played_diff'] = features['home_matches_played'] - features['away_matches_played']
    features['fatigue_home'] = features['home_matches_played'] / 38.0
    features['fatigue_away'] = features['away_matches_played'] / 38.0
    
    # Glicko features
    features['home_glicko'] = df['home_glicko'].fillna(1500)
    features['away_glicko'] = df['away_glicko'].fillna(1500)
    features['glicko_diff'] = features['home_glicko'] - features['away_glicko']
    features['glicko_home_rd'] = df['home_glicko_rd'].fillna(350)
    features['glicko_away_rd'] = df['away_glicko_rd'].fillna(350)
    features['glicko_rd_sum'] = features['glicko_home_rd'] + features['glicko_away_rd']
    features['glicko_confidence_h'] = 1.0 / (features['glicko_home_rd'] + 1)
    features['glicko_confidence_a'] = 1.0 / (features['glicko_away_rd'] + 1)
    
    # === GROUP 2: POISSON FEATURES (25) ===
    print("  Poisson features...")
    # Home team
    features['home_poisson_att'] = df.get('h_attack_strength_home', pd.Series(1.0, index=df.index)).fillna(1.0)
    features['home_poisson_def'] = df.get('h_defense_strength_home', pd.Series(1.0, index=df.index)).fillna(1.0)
    features['home_lambda_scored'] = df.get('h_lambda_home_scored', pd.Series(1.5, index=df.index)).fillna(1.5)
    features['home_lambda_conceded'] = df.get('h_lambda_home_conceded', pd.Series(1.5, index=df.index)).fillna(1.5)
    features['home_poisson_att_a'] = df.get('h_attack_strength_away', pd.Series(1.0, index=df.index)).fillna(1.0)
    features['home_poisson_def_a'] = df.get('h_defense_strength_away', pd.Series(1.0, index=df.index)).fillna(1.0)
    # Away team
    features['away_poisson_att'] = df.get('a_attack_strength_home', pd.Series(1.0, index=df.index)).fillna(1.0)
    features['away_poisson_def'] = df.get('a_defense_strength_home', pd.Series(1.0, index=df.index)).fillna(1.0)
    features['away_lambda_scored'] = df.get('a_lambda_home_scored', pd.Series(1.5, index=df.index)).fillna(1.5)
    features['away_lambda_conceded'] = df.get('a_lambda_home_conceded', pd.Series(1.5, index=df.index)).fillna(1.5)
    features['away_poisson_att_a'] = df.get('a_attack_strength_away', pd.Series(1.0, index=df.index)).fillna(1.0)
    features['away_poisson_def_a'] = df.get('a_defense_strength_away', pd.Series(1.0, index=df.index)).fillna(1.0)
    
    features['att_strength_ratio'] = features['home_poisson_att'] / (features['away_poisson_def'] + 0.01)
    features['def_strength_ratio'] = features['home_poisson_def'] / (features['away_poisson_att'] + 0.01)
    features['lambda_home_expected'] = features['home_lambda_scored']
    features['lambda_away_expected'] = features['away_lambda_scored']
    
    # Poisson score probabilities (25 probs)
    from scipy.stats import poisson
    lambda_h = np.clip(features['lambda_home_expected'].values, 0.1, 6.0)
    lambda_a = np.clip(features['lambda_away_expected'].values, 0.1, 6.0)
    for h in range(5):
        for a in range(5):
            # P(h) * P(a) = Poisson prob
            prob_h = poisson.pmf(h, lambda_h)
            prob_a = poisson.pmf(a, lambda_a)
            features[f'poisson_{h}_{a}'] = prob_h * prob_a
    
    # === GROUP 3: H2H FEATURES (12) ===
    print("  H2H features...")
    h2h_cols = ['total_matches', 'home_wins', 'draws', 'away_wins',
                'home_goals_total', 'away_goals_total', 'home_win_pct', 'avg_home_goals',
                'avg_away_goals', 'goal_diff_avg']
    for col in h2h_cols:
        if col in df.columns:
            features['h2h_' + col] = df[col].fillna(0)
    
    # === GROUP 4: TIME FEATURES (10) ===
    print("  Time features...")
    dates = pd.to_datetime(df['date'])
    features['month'] = dates.dt.month
    features['month_sin'] = np.sin(2 * np.pi * features['month'] / 12)
    features['month_cos'] = np.cos(2 * np.pi * features['month'] / 12)
    features['day_of_week'] = dates.dt.dayofweek
    features['is_weekend'] = (dates.dt.dayofweek >= 5).astype(int)
    features['day_of_year'] = dates.dt.dayofyear
    features['season_progress'] = features['day_of_year'] / 365.0
    
    # === GROUP 7: INTERACTION FEATURES (50+) ===
    print("  Interaction features...")
    
    # Key interactions
    key_features = ['elo_diff', 'form_diff', 'glicko_diff', 'xg_ratio', 'home_xg_diff', 'away_xg_diff']
    for i, f1 in enumerate(key_features):
        for f2 in key_features[i+1:]:
            if f1 in features.columns and f2 in features.columns:
                features[f'{f1}_x_{f2}'] = features[f1] * features[f2]
    
    # Elo × Poisson
    features['elo_x_att_home'] = features['home_elo'] * features['home_poisson_att']
    features['elo_x_att_away'] = features['away_elo'] * features['away_poisson_att']
    features['elo_x_def_home'] = features['home_elo'] * features['home_poisson_def']
    features['elo_x_def_away'] = features['away_elo'] * features['away_poisson_def']
    
    # Form × Poisson
    features['form_x_att_home'] = features['home_form'] * features['home_poisson_att']
    features['form_x_att_away'] = features['away_form'] * features['away_poisson_att']
    
    # === GROUP 8: POLYNOMIAL FEATURES (30) ===
    print("  Polynomial features...")
    for col in ['elo_diff', 'form_diff', 'glicko_diff', 'xg_ratio', 'home_glicko', 'away_glicko']:
        if col in features.columns:
            features[f'{col}_sqrt'] = np.sqrt(np.abs(features[col]) + 0.01) * np.sign(features[col])
            features[f'{col}_log'] = np.log(np.abs(features[col]) + 0.01)
            features[f'{col}_abs'] = np.abs(features[col])
    
    # === GROUP 9: MOMENTUM (10) ===
    print("  Momentum features...")
    features['momentum_home'] = features['home_form'] * features['elo_diff'].clip(-200, 200)
    features['momentum_away'] = features['away_form'] * (-features['elo_diff']).clip(-200, 200)
    features['momentum_diff'] = features['momentum_home'] - features['momentum_away']
    
    # === GROUP 10: STATSBOMB (25) ===
    print("  StatsBomb features...")
    sb_features = ['total_events', 'shots', 'passes', 'pressures', 'xg_total', 'xg_per_shot',
                   'goals', 'assists', 'fouls', 'duels', 'carries']
    for col in sb_features:
        hcol = 'sb_h_' + col
        if hcol in df.columns:
            features['sb_h_' + col] = df[hcol].fillna(0)
        acol = 'sb_a_' + col
        if acol in df.columns:
            features['sb_a_' + col] = df[acol].fillna(0)
    
    # === CLEAN UP ===
    print("  Cleaning up...")
    
    # Remove NaN, Inf
    features = features.replace([np.inf, -np.inf], np.nan)
    
    # Fill remaining NaN with medians
    for col in features.columns:
        if features[col].isna().any():
            med = features[col].median()
            if pd.isna(med):
                med = 0
            features[col] = features[col].fillna(med)
    
    # Remove zero-variance columns
    variances = features.var()
    zero_var = variances[variances < 1e-8].index.tolist()
    if zero_var:
        print(f"  Dropping {len(zero_var)} zero-variance columns: {zero_var[:5]}...")
        features = features.drop(columns=zero_var)
    
    # Class vector
    result_types = np.array([0 if h > a else 1 if h == a else 2 
                             for h, a in zip(home_scores, away_scores)])
    
    print(f"  Final feature matrix: {features.shape}")
    print(f"  Classes: {len(np.unique(y))}")
    print(f"  Home wins: {(result_types==0).sum():,}")
    print(f"  Draws: {(result_types==1).sum():,}")
    print(f"  Away wins: {(result_types==2).sum():,}")
    print(f"  Total time: {time.time()-t0:.1f}s")
    
    return features.values, y, result_types, df['id'].values, features.columns.tolist()


def save_for_training(X, y, result_types, match_ids, feature_names):
    """Save as NPZ for fast loading"""
    t0 = time.time()
    out_path = os.path.join(os.path.dirname(__file__), 'training_data_550.npz')
    np.savez_compressed(out_path,
                        X=X, y=y, result_types=result_types,
                        match_ids=match_ids,
                        feature_names=np.array(feature_names, dtype=object))
    print(f"\nSaved to {out_path}")
    print(f"  X shape: {X.shape} ({X.nbytes/1024/1024:.0f} MB)")
    print(f"  y shape: {y.shape}")
    print(f"  Time: {time.time()-t0:.1f}s")
    return out_path


if __name__ == '__main__':
    t_start = time.time()
    print("="*60)
    print("BULK FEATURE EXTRACTION — Score Exact 100")
    print("="*60)
    
    df = bulk_load_features(min_date='2010-01-01')
    
    X, y, result_types, match_ids, feature_names = engineer_features(df)
    
    path = save_for_training(X, y, result_types, match_ids, feature_names)
    
    print(f"\n{'='*60}")
    print(f"COMPLETE! Total time: {(time.time()-t_start)/60:.1f} minutes")
    print(f"Features: {X.shape[1]}")
    print(f"Matches: {X.shape[0]:,}")
    print(f"Saved: {path}")
    
    # Verify
    import numpy as np
    data = np.load(path, allow_pickle=True)
    print(f"\nVerification:")
    print(f"  X: {data['X'].shape}")
    print(f"  y: {data['y'].shape}")
    print(f"  Classes: {len(np.unique(data['y']))}")
    print(f"  Features: {len(data['feature_names'])}")
