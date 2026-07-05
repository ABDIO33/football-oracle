"""
fast_bulk_load_v4.py — SQL Pure Join (أسرع 1000x)
يجمع 120 base features + 100+ new features من neg_* tables
"""
import sqlite3, os, time
import numpy as np
import pandas as pd

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
NUM_CLASSES = 25

def score_to_class(home_score, away_score):
    h = max(0, min(int(home_score), 4))
    a = max(0, min(int(away_score), 4))
    return h * 5 + a

def extract_by_sql_v4(min_date='2010-01-01'):
    t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA cache_size = -800000")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    
    print("="*60)
    print("BULK SQL EXTRACTION V4 — 220+ Features")
    print("="*60)
    
    # Ensure indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_team_date ON walkforward_state(team_name, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_glicko_team_date ON glicko_state(team_name, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_date ON sofa_historical_results(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_id ON sofa_historical_results(id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_poisson_team ON neg_poisson_params(team_name, tournament)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_strength_team ON neg_team_strength(team_name, tournament)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_streaks_team ON neg_streaks(team_name, tournament)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h2h_pair ON neg_h2h_features(home_team, away_team)")
    
    print(f"  Indexes: {time.time()-t0:.1f}s")
    
    # Step 2: Single massive query
    print("[2] Extracting 220+ features via SQL joins...")
    
    query = f"""
    SELECT 
        r.id, r.home_team, r.away_team, r.home_score, r.away_score, r.date, r.tournament,
        
        -- BASE: Walkforward (16)
        hwf.elo AS home_elo, hwf.rolling_xg_for AS home_xg_for,
        hwf.rolling_xg_against AS home_xg_against, hwf.form_points AS home_form,
        hwf.matches_played AS home_mp, hwf.rolling_shots_for AS home_shots_for,
        hwf.rolling_shots_against AS home_shots_against,
        awf.elo AS away_elo, awf.rolling_xg_for AS away_xg_for,
        awf.rolling_xg_against AS away_xg_against, awf.form_points AS away_form,
        awf.matches_played AS away_mp, awf.rolling_shots_for AS away_shots_for,
        awf.rolling_shots_against AS away_shots_against,
        
        -- Glicko (4)
        hg.glicko_rating AS home_glicko, hg.glicko_rd AS home_glicko_rd,
        ag.glicko_rating AS away_glicko, ag.glicko_rd AS away_glicko_rd,
        
        -- POISSON PARAMS (10 per team = 20)
        hp.attack_strength_home AS h_att_h, hp.attack_strength_away AS h_att_a,
        hp.defense_strength_home AS h_def_h, hp.defense_strength_away AS h_def_a,
        hp.lambda_home_scored AS h_lambda_hs, hp.lambda_home_conceded AS h_lambda_hc,
        hp.lambda_away_scored AS h_lambda_as, hp.lambda_away_conceded AS h_lambda_ac,
        ap.attack_strength_home AS a_att_h, ap.attack_strength_away AS a_att_a,
        ap.defense_strength_home AS a_def_h, ap.defense_strength_away AS a_def_a,
        ap.lambda_home_scored AS a_lambda_hs, ap.lambda_home_conceded AS a_lambda_hc,
        ap.lambda_away_scored AS a_lambda_as, ap.lambda_away_conceded AS a_lambda_ac,
        
        -- TEAM STRENGTH (8 per team = 16)
        hs.avg_home_goals_for AS h_avg_hgf, hs.avg_home_goals_against AS h_avg_hga,
        hs.avg_away_goals_for AS h_avg_agf, hs.avg_away_goals_against AS h_avg_aga,
        hs.home_strength AS h_strength, hs.overall_gd_per_game AS h_gd_pg,
        as_s.avg_home_goals_for AS a_avg_hgf, as_s.avg_home_goals_against AS a_avg_hga,
        as_s.avg_away_goals_for AS a_avg_agf, as_s.avg_away_goals_against AS a_avg_aga,
        as_s.home_strength AS a_strength, as_s.overall_gd_per_game AS a_gd_pg,
        
        -- STREAKS (7 per team = 14)
        hst.current_streak_type AS h_streak_type, hst.current_streak_len AS h_streak_len,
        hst.longest_win_streak AS h_long_win, hst.longest_loss_streak AS h_long_loss,
        hst.last_5_results AS h_last5,
        ast.current_streak_type AS a_streak_type, ast.current_streak_len AS a_streak_len,
        ast.longest_win_streak AS a_long_win, ast.longest_loss_streak AS a_long_loss,
        ast.last_5_results AS a_last5,
        
        -- LEAGUE AVERAGES (9)
        la.avg_home_goals AS l_avg_hg, la.avg_away_goals AS l_avg_ag,
        la.avg_total_goals AS l_avg_tg, la.home_win_pct AS l_hw_pct,
        la.draw_pct AS l_d_pct, la.away_win_pct AS l_aw_pct,
        la.poisson_lambda_home AS l_lambda_h, la.poisson_lambda_away AS l_lambda_a,
        
        -- H2H (11)
        h2h.total_matches AS h2h_total, h2h.home_wins AS h2h_hw, h2h.draws AS h2h_d,
        h2h.away_wins AS h2h_aw, h2h.avg_home_goals AS h2h_avg_hg,
        h2h.avg_away_goals AS h2h_avg_ag, h2h.home_win_pct AS h2h_hw_pct,
        h2h.away_win_pct AS h2h_aw_pct, h2h.draw_pct AS h2h_d_pct
        
    FROM sofa_historical_results r
    
    -- Walkforward
    LEFT JOIN walkforward_state hwf ON hwf.team_name = r.home_team 
        AND hwf.date = (SELECT MAX(wf2.date) FROM walkforward_state wf2 WHERE wf2.team_name = r.home_team AND wf2.date <= r.date)
    LEFT JOIN walkforward_state awf ON awf.team_name = r.away_team 
        AND awf.date = (SELECT MAX(wf2.date) FROM walkforward_state wf2 WHERE wf2.team_name = r.away_team AND wf2.date <= r.date)
    
    -- Glicko
    LEFT JOIN glicko_state hg ON hg.team_name = r.home_team 
        AND hg.date = (SELECT MAX(g2.date) FROM glicko_state g2 WHERE g2.team_name = r.home_team AND g2.date <= r.date)
    LEFT JOIN glicko_state ag ON ag.team_name = r.away_team 
        AND ag.date = (SELECT MAX(g2.date) FROM glicko_state g2 WHERE g2.team_name = r.away_team AND g2.date <= r.date)
    
    -- Poisson (direct team+tournament join)
    LEFT JOIN neg_poisson_params hp ON hp.team_name = r.home_team AND hp.tournament = r.tournament
    LEFT JOIN neg_poisson_params ap ON ap.team_name = r.away_team AND ap.tournament = r.tournament
    
    -- Team Strength
    LEFT JOIN neg_team_strength hs ON hs.team_name = r.home_team AND hs.tournament = r.tournament
    LEFT JOIN neg_team_strength as_s ON as_s.team_name = r.away_team AND as_s.tournament = r.tournament
    
    -- Streaks
    LEFT JOIN neg_streaks hst ON hst.team_name = r.home_team AND hst.tournament = r.tournament
    LEFT JOIN neg_streaks ast ON ast.team_name = r.away_team AND ast.tournament = r.tournament
    
    -- League Averages
    LEFT JOIN neg_league_averages la ON la.tournament = r.tournament
    
    -- H2H (try both directions)
    LEFT JOIN neg_h2h_features h2h ON h2h.home_team = r.home_team AND h2h.away_team = r.away_team
    
    WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL
      AND r.home_score >= 0 AND r.away_score >= 0
      AND r.status_type = 'finished'
      AND r.date >= '{min_date}'
    ORDER BY r.start_timestamp
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    n_total = len(df)
    print(f"  Raw rows: {n_total:,}")
    print(f"  Time: {time.time()-t0:.1f}s")
    
    if n_total == 0:
        return None, None, None, None
    
    # Fill NaN
    print("[3] Cleaning...", flush=True)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = df[col].fillna(0)
    
    # Build features
    print("[4] Engineering 220+ features...", flush=True)
    
    n = n_total
    X = np.zeros((n, 220), dtype=np.float32)
    
    # === BASE FEATURES (120) — first 52 are original base ===
    home_elo = df['home_elo'].values.astype(np.float32)
    away_elo = df['away_elo'].values.astype(np.float32)
    home_form = df['home_form'].values.astype(np.float32)
    away_form = df['away_form'].values.astype(np.float32)
    home_xgf = df['home_xg_for'].values.astype(np.float32)
    home_xga = df['home_xg_against'].values.astype(np.float32)
    away_xgf = df['away_xg_for'].values.astype(np.float32)
    away_xga = df['away_xg_against'].values.astype(np.float32)
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
    
    # Elo core
    X[:, 0] = home_elo; X[:, 1] = away_elo
    X[:, 2] = home_elo - away_elo; X[:, 3] = X[:, 2] ** 2
    X[:, 4] = np.sign(X[:, 2]); X[:, 5] = home_elo + away_elo
    
    # Form
    X[:, 6] = home_form; X[:, 7] = away_form; X[:, 8] = home_form - away_form
    X[:, 9] = X[:, 8] ** 2
    X[:, 10] = X[:, 0] * X[:, 6]; X[:, 11] = X[:, 1] * X[:, 7]
    X[:, 12] = X[:, 2] * X[:, 8]
    
    # xG
    X[:, 13] = home_xgf; X[:, 14] = home_xga; X[:, 15] = away_xgf; X[:, 16] = away_xga
    X[:, 17] = home_xgf - home_xga; X[:, 18] = away_xgf - away_xga
    X[:, 19] = X[:, 0] * X[:, 13]; X[:, 20] = X[:, 1] * X[:, 15]
    X[:, 21] = X[:, 6] * X[:, 13]; X[:, 22] = X[:, 7] * X[:, 15]
    X[:, 23] = home_xgf / (away_xgf + 0.01); X[:, 24] = home_xgf / (home_xga + 0.01)
    X[:, 25] = away_xgf / (away_xga + 0.01); X[:, 26] = home_xgf + away_xgf
    
    # Shots
    X[:, 27] = home_shots_f; X[:, 28] = home_shots_a
    X[:, 29] = away_shots_f; X[:, 30] = away_shots_a
    X[:, 31] = home_shots_f / (away_shots_f + 0.01)
    X[:, 32] = home_xgf / (home_shots_f + 0.01)
    X[:, 33] = away_xgf / (away_shots_f + 0.01)
    
    # Fatigue
    X[:, 34] = home_mp / 38.0; X[:, 35] = away_mp / 38.0
    X[:, 36] = home_mp - away_mp
    
    # Glicko
    X[:, 37] = home_glicko; X[:, 38] = away_glicko
    X[:, 39] = home_glicko - away_glicko
    X[:, 40] = 1.0 / (home_grd + 1); X[:, 41] = 1.0 / (away_grd + 1)
    X[:, 42] = home_grd + away_grd
    
    # Polynomial transforms
    key_feat_indices = [2, 8, 39, 23]
    for i, ki in enumerate(key_feat_indices):
        vals = X[:, ki]
        base = 43 + i * 3
        X[:, base] = np.sqrt(np.abs(vals) + 0.01) * np.sign(vals)
        X[:, base + 1] = np.log(np.abs(vals) + 0.01 + 1e-10)
        X[:, base + 2] = np.abs(vals)
    
    # Time
    months = dates.dt.month.values.astype(np.float32)
    days = dates.dt.dayofweek.values.astype(np.float32)
    doy = dates.dt.dayofyear.values.astype(np.float32)
    X[:, 55] = months; X[:, 56] = np.sin(2*np.pi*months/12)
    X[:, 57] = np.cos(2*np.pi*months/12); X[:, 58] = days
    X[:, 59] = (days >= 5).astype(np.float32); X[:, 60] = doy / 365.0
    
    # Interactions (key feat × key feat)
    ki_idx = [2, 8, 39, 23, 17, 18]
    inter_idx = 61
    for i, fi in enumerate(ki_idx):
        for fj in ki_idx[i+1:]:
            if inter_idx < 100:
                X[:, inter_idx] = X[:, fi] * X[:, fj]
                inter_idx += 1
    
    # Extra interactions
    X[:, 100] = X[:, 0] * X[:, 13]; X[:, 101] = X[:, 1] * X[:, 15]
    X[:, 102] = X[:, 6] * X[:, 13]; X[:, 103] = X[:, 7] * X[:, 15]
    X[:, 104] = X[:, 2] * np.abs(X[:, 17]); X[:, 105] = -X[:, 2] * np.abs(X[:, 18])
    X[:, 106] = X[:, 6] * np.clip(X[:, 2], -200, 200)
    X[:, 107] = X[:, 7] * np.clip(-X[:, 2], -200, 200)
    X[:, 108] = X[:, 106] - X[:, 107]
    X[:, 109] = X[:, 0] / (X[:, 1] + 1)
    X[:, 110] = X[:, 13] / (X[:, 16] + 0.01); X[:, 111] = X[:, 15] / (X[:, 14] + 0.01)
    X[:, 112] = X[:, 17] - X[:, 18]; X[:, 113] = X[:, 34] - X[:, 35]
    # Fill 114-119 with zeros for now (or expand)
    X[:, 114] = X[:, 2] * X[:, 39]; X[:, 115] = X[:, 8] * X[:, 39]
    X[:, 116] = np.tanh(X[:, 2] / 200)  # sigmoid-like elo_diff
    X[:, 117] = np.tanh(X[:, 8] / 10)   # sigmoid-like form_diff
    X[:, 118] = X[:, 0] * X[:, 40]  # elo × confidence
    X[:, 119] = X[:, 1] * X[:, 41]
    
    # === NEW FEATURES (100) — cols 120-219 ===
    # Poisson (20 from DB already, add derived)
    h_att_h = df['h_att_h'].values.astype(np.float32)
    h_att_a = df['h_att_a'].values.astype(np.float32)
    h_def_h = df['h_def_h'].values.astype(np.float32)
    h_def_a = df['h_def_a'].values.astype(np.float32)
    h_lambda_hs = df['h_lambda_hs'].values.astype(np.float32)
    h_lambda_hc = df['h_lambda_hc'].values.astype(np.float32)
    h_lambda_as = df['h_lambda_as'].values.astype(np.float32)
    h_lambda_ac = df['h_lambda_ac'].values.astype(np.float32)
    a_att_h = df['a_att_h'].values.astype(np.float32)
    a_att_a = df['a_att_a'].values.astype(np.float32)
    a_def_h = df['a_def_h'].values.astype(np.float32)
    a_def_a = df['a_def_a'].values.astype(np.float32)
    a_lambda_hs = df['a_lambda_hs'].values.astype(np.float32)
    a_lambda_hc = df['a_lambda_hc'].values.astype(np.float32)
    a_lambda_as = df['a_lambda_as'].values.astype(np.float32)
    a_lambda_ac = df['a_lambda_ac'].values.astype(np.float32)
    
    # Store raw Poisson
    X[:, 120:128] = np.column_stack([h_att_h, h_att_a, h_def_h, h_def_a, h_lambda_hs, h_lambda_hc, h_lambda_as, h_lambda_ac])
    X[:, 128:136] = np.column_stack([a_att_h, a_att_a, a_def_h, a_def_a, a_lambda_hs, a_lambda_hc, a_lambda_as, a_lambda_ac])
    
    # Poisson derived
    h_exp_for = h_att_h / np.maximum(a_def_h, 0.01)
    h_exp_against = h_def_a / np.maximum(a_att_a, 0.01)
    a_exp_for = a_att_a / np.maximum(h_def_a, 0.01)
    a_exp_against = a_def_h / np.maximum(h_att_h, 0.01)
    
    h_exp_for2 = h_lambda_hs * (a_lambda_hc / np.mean(a_lambda_hc[a_lambda_hc > 0] + 1)) if np.any(a_lambda_hc > 0) else h_lambda_hs
    a_exp_for2 = a_lambda_as * (h_lambda_ac / np.mean(h_lambda_ac[h_lambda_ac > 0] + 1)) if np.any(h_lambda_ac > 0) else a_lambda_as
    
    X[:, 136] = h_exp_for; X[:, 137] = h_exp_against
    X[:, 138] = a_exp_for; X[:, 139] = a_exp_against
    X[:, 140] = h_exp_for - a_exp_for  # expected_goal_diff
    X[:, 141] = h_exp_for / (a_exp_for + 0.01)  # expected_goal_ratio
    X[:, 142] = h_exp_for * a_exp_for * 0.1  # Dixon-Coles tau
    X[:, 143] = np.exp(-(h_exp_for + a_exp_for))  # P(0-0)
    
    # Team Strength (16 from DB, add derived)
    h_avg_hgf = df['h_avg_hgf'].values.astype(np.float32)
    h_avg_hga = df['h_avg_hga'].values.astype(np.float32)
    h_avg_agf = df['h_avg_agf'].values.astype(np.float32)
    h_avg_aga = df['h_avg_aga'].values.astype(np.float32)
    h_strength = df['h_strength'].values.astype(np.float32)
    h_gd_pg = df['h_gd_pg'].values.astype(np.float32)
    h_mp = df['home_mp'].values.astype(np.float32)
    away_mp = df['away_mp'].values.astype(np.float32)
    a_avg_hgf = df['a_avg_hgf'].values.astype(np.float32)
    a_avg_hga = df['a_avg_hga'].values.astype(np.float32)
    a_avg_agf = df['a_avg_agf'].values.astype(np.float32)
    a_avg_aga = df['a_avg_aga'].values.astype(np.float32)
    a_strength = df['a_strength'].values.astype(np.float32)
    a_gd_pg = df['a_gd_pg'].values.astype(np.float32)
    
    X[:, 144:150] = np.column_stack([h_avg_hgf, h_avg_hga, h_avg_agf, h_avg_aga, h_strength, h_gd_pg])
    X[:, 150:156] = np.column_stack([a_avg_hgf, a_avg_hga, a_avg_agf, a_avg_aga, a_strength, a_gd_pg])
    
    # Strength difference
    X[:, 156] = h_avg_hgf - a_avg_agf; X[:, 157] = h_avg_hga - a_avg_aga
    X[:, 158] = h_strength - a_strength; X[:, 159] = h_gd_pg - a_gd_pg
    a_avg_agf_safe = np.maximum(a_avg_agf, 0.01)
    a_strength_safe = np.maximum(a_strength, 0.01)
    X[:, 160] = h_avg_hgf / a_avg_agf_safe; X[:, 161] = h_strength / a_strength_safe
    
    # Streaks
    h_streak_type = pd.to_numeric(df['h_streak_type'].map({'W':0,'D':1,'L':2}).fillna(-1), downcast='float').values.astype(np.float32)
    h_streak_len = df['h_streak_len'].values.astype(np.float32)
    h_long_win = df['h_long_win'].values.astype(np.float32)
    h_long_loss = df['h_long_loss'].values.astype(np.float32)
    a_streak_type = pd.to_numeric(df['a_streak_type'].map({'W':0,'D':1,'L':2}).fillna(-1), downcast='float').values.astype(np.float32)
    a_streak_len = df['a_streak_len'].values.astype(np.float32)
    a_long_win = df['a_long_win'].values.astype(np.float32)
    a_long_loss = df['a_long_loss'].values.astype(np.float32)
    
    X[:, 162] = h_streak_type; X[:, 163] = h_streak_len
    X[:, 164] = h_long_win; X[:, 165] = h_long_loss
    X[:, 166] = a_streak_type; X[:, 167] = a_streak_len
    X[:, 168] = a_long_win; X[:, 169] = a_long_loss
    
    # Last5 parsing
    h_last5 = df['h_last5'].fillna('').values
    a_last5 = df['a_last5'].fillna('').values
    h_last5_w = np.array([s[:5].count('W') for s in h_last5], np.float32)
    h_last5_d = np.array([s[:5].count('D') for s in h_last5], np.float32)
    a_last5_w = np.array([s[:5].count('W') for s in a_last5], np.float32)
    a_last5_d = np.array([s[:5].count('D') for s in a_last5], np.float32)
    
    X[:, 170] = h_last5_w; X[:, 171] = h_last5_d
    X[:, 172] = a_last5_w; X[:, 173] = a_last5_d
    X[:, 174] = h_streak_len - a_streak_len; X[:, 175] = h_last5_w - a_last5_w
    
    # League averages (9 from DB)
    l_avg_hg = df['l_avg_hg'].values.astype(np.float32)
    l_avg_ag = df['l_avg_ag'].values.astype(np.float32)
    l_avg_tg = df['l_avg_tg'].values.astype(np.float32)
    l_hw_pct = df['l_hw_pct'].values.astype(np.float32)
    l_d_pct = df['l_d_pct'].values.astype(np.float32)
    l_aw_pct = df['l_aw_pct'].values.astype(np.float32)
    l_lambda_h = df['l_lambda_h'].values.astype(np.float32)
    l_lambda_a = df['l_lambda_a'].values.astype(np.float32)
    
    X[:, 176:184] = np.column_stack([l_avg_hg, l_avg_ag, l_avg_tg, l_hw_pct, l_d_pct, l_aw_pct, l_lambda_h, l_lambda_a])
    
    # League-derived
    X[:, 184] = h_avg_hgf - l_avg_hg  # home attack vs league avg
    X[:, 185] = h_avg_hga - l_avg_ag  # home defense vs league avg
    X[:, 186] = a_avg_agf - l_avg_ag  # away attack vs league avg
    X[:, 187] = a_avg_aga - l_avg_hg  # away defense vs league avg
    X[:, 188] = h_exp_for / (l_lambda_h + 0.01)  # expected attack / league lambda
    X[:, 189] = a_exp_for / (l_lambda_a + 0.01)
    
    # H2H (11 from DB)
    h2h_total = df['h2h_total'].values.astype(np.float32)
    h2h_hw = df['h2h_hw'].values.astype(np.float32)
    h2h_d = df['h2h_d'].values.astype(np.float32)
    h2h_aw = df['h2h_aw'].values.astype(np.float32)
    h2h_avg_hg = df['h2h_avg_hg'].values.astype(np.float32)
    h2h_avg_ag = df['h2h_avg_ag'].values.astype(np.float32)
    h2h_hw_pct = df['h2h_hw_pct'].values.astype(np.float32)
    h2h_aw_pct = df['h2h_aw_pct'].values.astype(np.float32)
    h2h_d_pct = df['h2h_d_pct'].values.astype(np.float32)
    
    X[:, 190:199] = np.column_stack([h2h_total, h2h_hw, h2h_d, h2h_aw, h2h_avg_hg, h2h_avg_ag, h2h_hw_pct, h2h_aw_pct, h2h_d_pct])
    
    # H2H derived
    has_h2h = h2h_total > 0
    h2h_hw_rate = np.divide(h2h_hw, h2h_total, out=np.zeros_like(h2h_hw), where=has_h2h)
    h2h_d_rate = np.divide(h2h_d, h2h_total, out=np.zeros_like(h2h_d), where=has_h2h)
    h2h_aw_rate = np.divide(h2h_aw, h2h_total, out=np.zeros_like(h2h_aw), where=has_h2h)
    
    X[:, 199] = h2h_avg_hg - h2h_avg_ag  # H2H goal diff
    X[:, 200] = h2h_hw_rate - h2h_aw_rate  # H2H win diff
    X[:, 201] = h2h_hw_rate  # home win rate in H2H
    X[:, 202] = h2h_d_rate  # draw rate in H2H
    X[:, 203] = h2h_hw_rate / (h2h_aw_rate + 0.01)  # H2H dominance ratio
    
    # Hybrid features: cross-product of old × new
    X[:, 204] = X[:, 2] * X[:, 140]  # elo_diff × expected_goal_diff
    X[:, 205] = X[:, 39] * X[:, 140]  # glicko_diff × expected_goal_diff
    X[:, 206] = X[:, 23] * X[:, 141]  # xg_ratio × expected_goal_ratio
    X[:, 207] = X[:, 12] * X[:, 174]  # elo_diff_form_diff × streak_len_diff
    X[:, 208] = X[:, 140] * X[:, 200]  # expected_goal_diff × H2H_win_diff
    X[:, 209] = X[:, 2] * np.tanh(X[:, 174])  # elo × streak_diff
    
    # Advanced Poisson (Dixon-Coles full)
    tau = 0.2  # Dixon-Coles dependence parameter
    X[:, 210] = h_exp_for  # λ_home
    X[:, 211] = a_exp_for  # λ_away
    X[:, 212] = 1 + tau * (h_exp_for - 1) * (a_exp_for - 1) / np.sqrt(h_exp_for * a_exp_for + 0.01)
    
    # Tournament class (encoded)
    tour = df['tournament'].fillna('UNKNOWN').values
    unique_tours = np.unique(tour)
    tour_to_idx = {t: i for i, t in enumerate(unique_tours)}
    X[:, 213] = np.array([tour_to_idx.get(t, 0) % 10 for t in tour], np.float32)
    
    # Match count (how many times teams have played this season)
    X[:, 214] = home_mp; X[:, 215] = away_mp
    X[:, 216] = np.log(home_mp + 1) - np.log(away_mp + 1)  # experience diff
    X[:, 217] = X[:, 0] * X[:, 144]  # elo × avg_home_goals_for
    X[:, 218] = X[:, 1] * X[:, 150]  # away_elo × avg_away_goals_for
    X[:, 219] = X[:, 136] - X[:, 17]  # Poisson expected - actual xG diff
    
    # Target
    home_scores = df['home_score'].values.astype(int)
    away_scores = df['away_score'].values.astype(int)
    y = np.array([score_to_class(h, a) for h, a in zip(home_scores, away_scores)], dtype=np.int32)
    result_types = np.array([0 if h > a else 1 if h == a else 2 
                            for h, a in zip(home_scores, away_scores)], dtype=np.int32)
    
    print(f"  Final: {X.shape}, nan: {np.isnan(X).sum()}, classes: {len(np.unique(y))}")
    print(f"  Time: {time.time()-t0:.1f}s")
    
    return X, y, result_types, df['id'].values


def save_data(X, y, rt, ids):
    out_path = os.path.join(os.path.dirname(__file__), 'training_data_v4.npz')
    np.savez_compressed(out_path, X=X, y=y, result_types=rt, match_ids=ids)
    print(f"\nSaved: {out_path}")
    print(f"  X: {X.shape} ({X.nbytes/1024/1024:.0f} MB)")
    print(f"  y: {y.shape}")
    return out_path


if __name__ == '__main__':
    t0 = time.time()
    X, y, rt, ids = extract_by_sql_v4(min_date='2010-01-01')
    if X is not None and len(y) > 0:
        print(f"\nDataset: {len(y):,} matches, {X.shape[1]} features")
        print(f"Home wins: {(rt==0).sum():,} | Draws: {(rt==1).sum():,} | Away wins: {(rt==2).sum():,}")
        save_data(X, y, rt, ids)
    print(f"\nTotal time: {(time.time()-t0)/60:.1f} minutes")
