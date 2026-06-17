"""
direct_predictor.py — XGBoost Direct Score Predictor (25 classes)
بدلاً من λ_home/λ_away → Poisson → distribution
نتوقع الـ score مباشرة كـ multi-class (0-0, 0-1, ..., 4-4+)
"""

import sqlite3, os, json
import numpy as np
import pandas as pd

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# 25 score classes: [0-0, 0-1, 0-2, 0-3, 0-4+, 1-0, 1-1, ..., 4-3, 4-4+]
SCORE_CLASSES = []
for h in range(5):
    for a in range(5):
        SCORE_CLASSES.append((h, a))
# Total: 25 classes
NUM_CLASSES = len(SCORE_CLASSES)

def score_to_class(home_score, away_score):
    h = max(0, min(int(home_score), 4))
    a = max(0, min(int(away_score), 4))
    return h * 5 + a

def class_to_score(cls):
    h = cls // 5
    a = cls % 5
    return h, a

def result(h, a):
    if h > a: return 0  # home win
    if h == a: return 1 # draw
    return 2            # away win

FEATURES = [
    # Base walkforward
    'home_elo', 'away_elo', 'elo_diff',
    'home_xg_for', 'home_xg_against', 'away_xg_for', 'away_xg_against',
    'home_form', 'away_form', 'home_matches_played', 'away_matches_played',
    'home_shots_for', 'away_shots_for', 'home_shots_against', 'away_shots_against',
    'home_xg_diff', 'away_xg_diff', 'home_shot_diff', 'away_shot_diff',
    'home_days_rest', 'away_days_rest',
    'forebet_prob_h', 'forebet_prob_d', 'forebet_prob_a', 'forebet_available',
    # Match statistics
    'stat_h_xg', 'stat_a_xg', 'stat_h_shots', 'stat_a_shots',
    'stat_h_sot', 'stat_a_sot', 'stat_h_possession', 'stat_a_possession',
    'stat_h_corners', 'stat_a_corners', 'stat_h_fouls', 'stat_a_fouls',
    # Lineups
    'home_formation_def', 'away_formation_def', 'formation_diff', 'has_lineups',
    # Player Impact (missing core starters)
    'home_missing_core', 'away_missing_core',
    'home_att_loss', 'away_att_loss',
    'home_def_loss', 'away_def_loss',
    # Market odds
    'odds_b365h', 'odds_b365d', 'odds_b365a',
    'odds_avgh', 'odds_avgd', 'odds_avga',
    # Interaction features
    'elo_form_home', 'elo_form_away',
    'elo_xg_home', 'elo_xg_away',
    'form_xg_home', 'form_xg_away',
    'elo_diff_form_diff', 'fatigue_home', 'fatigue_away',
    # Ratio features
    'xg_ratio', 'shots_ratio', 'form_ratio',
    'xgf_xga_ratio_home', 'xgf_xga_ratio_away',
    'shot_eff_home', 'shot_eff_away',
    # Polynomial
    'elo_diff_sq', 'xg_diff_sq', 'form_diff_sq',
    # Time features
    'month', 'day_of_week', 'season_progress', 'is_weekend',
    # Weather
    'home_temp', 'home_precip', 'home_wind', 'home_humidity',
    # Travel
    'travel_distance',
]

FORMATION_DEF_MAP = {}
for f in ['3-4-3','3-5-2','3-4-2-1','3-4-1-2','3-1-4-2','3-4-3-1','3-5-1-1','3-4-2-1','3-2-4-1','3-6-1','3-1-4-2','3-4-3 diamond','3-4-1-2']:
    FORMATION_DEF_MAP[f] = 3
for f in ['5-3-2','5-4-1','5-2-3','5-2-2-1','5-3-1-1','5-4-1 diamond','5-4-1']:
    FORMATION_DEF_MAP[f] = 5
# Everything else defaults to 4

def formation_defenders(f):
    if not f:
        return 4.0
    return float(FORMATION_DEF_MAP.get(f, 4))

def _load_training_data():
    """Load match data with walkforward features + actual scores."""
    conn = sqlite3.connect(DB)

    # Get all historical matches with walkforward data
    query = '''
    SELECT r.id, r.home_team, r.away_team, r.home_score, r.away_score, r.date
    FROM sofa_historical_results r
    WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL
      AND r.home_score >= 0 AND r.away_score >= 0
    AND r.home_score IS NOT NULL AND r.away_score IS NOT NULL
    AND r.status_type = 'finished'
    ORDER BY r.start_timestamp
    '''

    df = pd.read_sql_query(query, conn)

    if len(df) == 0:
        conn.close()
        return np.array([]), np.array([]), np.array([])

    features_list = []
    labels = []
    match_ids = []

    # Pre-load all match statistics
    stats = {}
    try:
        cur = conn.execute('SELECT event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot, home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls FROM sofa_match_stats')
        for row in cur.fetchall():
            stats[row[0]] = row[1:]
    except:
        pass

    # Pre-load lineups (formations)
    lineups = {}
    try:
        cur = conn.execute('SELECT event_id, home_formation, away_formation FROM sofa_lineups')
        for row in cur.fetchall():
            lineups[row[0]] = (row[1], row[2])
    except:
        pass

    # Pre-load lineup player data for missing impact features
    lineup_players = {}
    try:
        cur = conn.execute('SELECT event_id, home_players_json, away_players_json FROM sofa_lineups')
        for row in cur.fetchall():
            eid = row[0]
            try:
                hpj = json.loads(row[1]) if row[1] else []
                apj = json.loads(row[2]) if row[2] else []
            except:
                continue
            h_starters = []
            for p in hpj:
                if isinstance(p, dict) and not p.get('substitute', False):
                    pl = p.get('player', {})
                    name = pl.get('name', '')
                    if name:
                        h_starters.append(name)
            a_starters = []
            for p in apj:
                if isinstance(p, dict) and not p.get('substitute', False):
                    pl = p.get('player', {})
                    name = pl.get('name', '')
                    if name:
                        a_starters.append(name)
            lineup_players[eid] = (h_starters, a_starters)
    except:
        pass

    # Pre-load player impact cache
    _player_impact_loaded = False
    try:
        from player_impact import _load_cache, get_missing_impact
        _load_cache()
        _player_impact_loaded = True
    except:
        pass

    # Pre-load market odds (FD overlap via team_name_mapping + corrected date)
    odds = {}
    try:
        cur = conn.execute('''
            SELECT s.id, fd.b365h, fd.b365d, fd.b365a, fd.avgh, fd.avgd, fd.avga
            FROM football_data_matches fd
            INNER JOIN team_name_mapping hm ON fd.home_team = hm.fd_name AND hm.confidence >= 0.85
            INNER JOIN team_name_mapping am ON fd.away_team = am.fd_name AND am.confidence >= 0.85
            INNER JOIN sofa_historical_results s
                ON s.date = fd.date
                AND s.home_team = hm.sofa_name
                AND s.away_team = am.sofa_name
            WHERE fd.date >= '2024-06-15' AND fd.date <= '2026-06-14'
            AND fd.b365h IS NOT NULL AND fd.b365h > 0
        ''')
        for row in cur.fetchall():
            odds[row[0]] = row[1:]
    except:
        pass

    # Pre-load venue weather
    venue_weather = {}
    try:
        cur = conn.execute('SELECT date, lat, lon, temp_max, temp_min, precip, wind, humidity FROM venue_weather')
        for row in cur.fetchall():
            venue_weather[(row[0], row[1], row[2])] = (row[3], row[4], row[5], row[6], row[7])
    except:
        pass

    # Pre-load team→venue mapping
    team_venue = {}
    try:
        cur = conn.execute('SELECT team_name, lat, lon FROM team_venue')
        for row in cur.fetchall():
            team_venue[row[0]] = (row[1], row[2])
    except:
        pass

    def haversine(lat1, lon1, lat2, lon2):
        from math import radians, sin, cos, sqrt, asin
        r = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        return 2 * r * asin(sqrt(a))

    for _, row in df.iterrows():
        mid = row['id']
        home_team = row['home_team']
        away_team = row['away_team']
        match_date = row['date']
        try:
            home_score = int(row['home_score'])
            away_score = int(row['away_score'])
        except (ValueError, TypeError):
            continue
        if home_score < 0 or away_score < 0 or home_score > 20 or away_score > 20:
            continue

        # Get walkforward features for home team
        cur = conn.execute('''
            SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                   wf.form_points, wf.matches_played, wf.rolling_shots_for,
                   wf.rolling_shots_against
            FROM walkforward_state wf
            WHERE wf.team_name = ? AND wf.date <= ?
            ORDER BY wf.date DESC LIMIT 1
        ''', (home_team, match_date))
        h = cur.fetchone()

        # Same for away
        cur.execute('''
            SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                   wf.form_points, wf.matches_played, wf.rolling_shots_for,
                   wf.rolling_shots_against
            FROM walkforward_state wf
            WHERE wf.team_name = ? AND wf.date <= ?
            ORDER BY wf.date DESC LIMIT 1
        ''', (away_team, match_date))
        a = cur.fetchone()

        if not h or not a:
            continue

        h_elo, h_xgf, h_xga, h_f, h_mp, h_shots, h_shots_a = h
        a_elo, a_xgf, a_xga, a_f, a_mp, a_shots, a_shots_a = a

        elo_diff = h_elo - a_elo
        h_xg_diff = (h_xgf or 1.2) - (h_xga or 1.2)
        a_xg_diff = (a_xgf or 1.2) - (a_xga or 1.2)
        h_shot_diff = (h_shots or 10) - (h_shots_a or 10)
        a_shot_diff = (a_shots or 10) - (a_shots_a or 10)

        home_days_rest = 7
        away_days_rest = 7
        try:
            cur = conn.execute('''
                SELECT start_timestamp FROM sofa_historical_results
                WHERE (home_team = ? OR away_team = ?)
                  AND id < ?
                  AND start_timestamp IS NOT NULL
                ORDER BY start_timestamp DESC LIMIT 1
            ''', (home_team, home_team, mid))
            h_last = cur.fetchone()
            cur.execute('''
                SELECT start_timestamp FROM sofa_historical_results
                WHERE (home_team = ? OR away_team = ?)
                  AND id < ?
                  AND start_timestamp IS NOT NULL
                ORDER BY start_timestamp DESC LIMIT 1
            ''', (away_team, away_team, mid))
            a_last = cur.fetchone()
            from datetime import datetime
            match_ts = int(datetime.strptime(match_date, '%Y-%m-%d').timestamp()) if isinstance(match_date, str) and match_date.count('-') == 2 else 0
            if h_last and h_last[0] and match_ts:
                home_days_rest = max(1, int((match_ts - h_last[0]) / 86400))
            if a_last and a_last[0] and match_ts:
                away_days_rest = max(1, int((match_ts - a_last[0]) / 86400))
        except:
            pass

        # Forebet
        fp_h = fp_d = fp_a = 0.0
        fp_avail = 0
        try:
            cur = conn.execute('''
                SELECT prob_h, prob_d, prob_a FROM forebet_predictions
                WHERE date = ? AND (home_team LIKE ? OR ? LIKE home_team)
                LIMIT 1
            ''', (match_date, '%' + home_team + '%', home_team))
            fp = cur.fetchone()
            if fp:
                fp_h = (fp[0] or 0) / 100.0
                fp_d = (fp[1] or 0) / 100.0
                fp_a = (fp[2] or 0) / 100.0
                fp_avail = 1
        except:
            pass

        # ── Engineered features (interaction, ratio, polynomial, time) ──
        he = h_elo or 1600; ae = a_elo or 1600; ed = elo_diff
        hxgf = h_xgf or 1.2; hxga = h_xga or 1.2
        axgf = a_xgf or 1.2; axga = a_xga or 1.2
        hf = h_f or 0.5; af = a_f or 0.5
        hmp = h_mp or 0; amp = a_mp or 0
        hsh = h_shots or 10; ash = a_shots or 10
        hsha = h_shots_a or 10; asha = a_shots_a or 10
        hdr = home_days_rest; adr = away_days_rest
        eps = 1e-6

        elo_form_home = he * hf
        elo_form_away = ae * af
        elo_xg_home = he * hxgf
        elo_xg_away = ae * axgf
        form_xg_home = hf * hxgf
        form_xg_away = af * axgf
        elo_diff_form_diff = ed * (hf - af)
        fatigue_home = hmp / (hdr + 1)
        fatigue_away = amp / (adr + 1)
        xg_ratio = hxgf / (axgf + eps)
        shots_ratio = hsh / (ash + eps)
        form_ratio = hf / (af + eps)
        xgf_xga_ratio_home = hxgf / (hxga + eps)
        xgf_xga_ratio_away = axgf / (axga + eps)
        shot_eff_home = hxgf / (hsh + eps)
        shot_eff_away = axgf / (ash + eps)
        elo_diff_sq = ed ** 2
        xg_diff_sq = (hxgf - hxga) ** 2
        form_diff_sq = (hf - af) ** 2
        month = 6; dow = 0; season_prog = 0.5; is_wknd = 0
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(match_date, '%Y-%m-%d') if isinstance(match_date, str) else _dt.now()
            month = dt.month
            dow = dt.weekday()
            is_wknd = 1 if dow >= 5 else 0
            season_prog = min(1.0, hmp / 50.0)
        except: pass

        # Player impact features
        if _player_impact_loaded and mid in lineup_players:
            h_miss, h_att, h_def, a_miss, a_att, a_def = get_missing_impact(
                home_team, away_team,
                lineup_players[mid][0], lineup_players[mid][1]
            )
        else:
            h_miss = h_att = h_def = a_miss = a_att = a_def = 0

        # Travel distance
        tv_home = team_venue.get(home_team)
        tv_away = team_venue.get(away_team)
        travel_dist = None
        if tv_home and tv_away:
            travel_dist = haversine(tv_home[0], tv_home[1], tv_away[0], tv_away[1])

        # Weather features
        tv = tv_home
        if tv:
            wkey = (match_date, tv[0], tv[1])
            wd = venue_weather.get(wkey)
            if wd:
                home_temp = (wd[0] + wd[1]) / 2.0 if wd[0] is not None and wd[1] is not None else None
                home_precip = wd[2]
                home_wind = wd[3]
                home_humidity = wd[4]
            else:
                home_temp = home_precip = home_wind = home_humidity = None
        else:
            home_temp = home_precip = home_wind = home_humidity = None

        features_list.append([
            he, ae, ed,
            hxgf, hxga, axgf, axga,
            hf, af, hmp, amp,
            hsh, ash, hsha, asha,
            h_xg_diff, a_xg_diff, h_shot_diff, a_shot_diff,
            hdr, adr,
            fp_h, fp_d, fp_a, fp_avail,
            stats[mid][0] if mid in stats else None,
            stats[mid][1] if mid in stats else None,
            stats[mid][2] if mid in stats else None,
            stats[mid][3] if mid in stats else None,
            stats[mid][4] if mid in stats else None,
            stats[mid][5] if mid in stats else None,
            stats[mid][6] if mid in stats else None,
            stats[mid][7] if mid in stats else None,
            stats[mid][8] if mid in stats else None,
            stats[mid][9] if mid in stats else None,
            stats[mid][10] if mid in stats else None,
            stats[mid][11] if mid in stats else None,
            formation_defenders(lineups[mid][0]) if mid in lineups else 4.0,
            formation_defenders(lineups[mid][1]) if mid in lineups else 4.0,
            formation_defenders(lineups[mid][0]) - formation_defenders(lineups[mid][1]) if mid in lineups else 0.0,
            1.0 if mid in lineups else 0.0,
            h_miss, h_att, h_def, a_miss, a_att, a_def,
            odds[mid][0] if mid in odds else None,
            odds[mid][1] if mid in odds else None,
            odds[mid][2] if mid in odds else None,
            odds[mid][3] if mid in odds else None,
            odds[mid][4] if mid in odds else None,
            odds[mid][5] if mid in odds else None,
            # Interaction
            elo_form_home, elo_form_away,
            elo_xg_home, elo_xg_away,
            form_xg_home, form_xg_away,
            elo_diff_form_diff, fatigue_home, fatigue_away,
            # Ratio
            xg_ratio, shots_ratio, form_ratio,
            xgf_xga_ratio_home, xgf_xga_ratio_away,
            shot_eff_home, shot_eff_away,
            # Polynomial
            elo_diff_sq, xg_diff_sq, form_diff_sq,
            # Time
            month, dow, season_prog, is_wknd,
            # Weather
            home_temp, home_precip, home_wind, home_humidity,
            # Travel
            travel_dist,
        ])
        labels.append(score_to_class(home_score, away_score))
        match_ids.append(mid)

    conn.close()

    if not features_list:
        return np.array([]), np.array([]), np.array([])

    X = np.array(features_list, dtype=float)
    y = np.array(labels)
    return X, y, np.array(match_ids)

def train(save=True):
    """Train XGBoost multi-class model."""
    import xgboost as xgb

    X, y, match_ids = _load_training_data()
    if len(X) == 0:
        print("[Direct] No training data")
        return

    print(f"[Direct] Loaded {len(X)} samples, {len(FEATURES)} features, {NUM_CLASSES} classes")
    print(f"[Direct] Class distribution:")

    from collections import Counter
    dist = Counter(y)
    for cls_idx in sorted(dist.keys()):
        h, a = class_to_score(cls_idx)
        pct = 100 * dist[cls_idx] / len(y)
        print(f"  {h}-{a}: {dist[cls_idx]} ({pct:.1f}%)")

    # Time-split: last 10% as test
    split = int(len(X) * 0.9)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        objective='multi:softprob',
        num_class=NUM_CLASSES,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        eval_metric='mlogloss',
        early_stopping_rounds=20,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    # Evaluate
    y_pred_proba = model.predict_proba(X_test)
    y_pred = np.argmax(y_pred_proba, axis=1)

    exact = np.mean(y_pred == y_test)
    exact_count = np.sum(y_pred == y_test)

    # 1X2 accuracy
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in y_pred])
    acc_1x2 = np.mean(actual_1x2 == pred_1x2)

    # RPS
    n_test = len(y_test)
    rps_total = 0.0
    for i in range(n_test):
        ah, aa = class_to_score(y_test[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        pred_probs_i = y_pred_proba[i]
        p_h = sum(pred_probs_i[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pred_probs_i[h*5 + h] for h in range(5))
        p_a = sum(pred_probs_i[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    rps = rps_total / n_test

    print(f"\n[Direct] Results ({n_test} matches):")
    print(f"  Exact score: {exact*100:.2f}% ({exact_count}/{n_test})")
    print(f"  1X2: {acc_1x2*100:.2f}%")
    print(f"  RPS: {rps:.3f}")

    if save:
        model_dir = os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(model_dir, exist_ok=True)
        model.save_model(os.path.join(model_dir, 'direct_score.json'))
        # Save model info
        with open(os.path.join(model_dir, 'direct_model_info.json'), 'w') as f:
            json.dump({
                'features': FEATURES,
                'num_classes': NUM_CLASSES,
                'classes': [f'{h}-{a}' for h, a in SCORE_CLASSES],
                'train_samples': len(X_train),
                'test_samples': n_test,
                'exact_pct': round(exact * 100, 2),
                'acc_1x2_pct': round(acc_1x2 * 100, 2),
                'rps': round(rps, 3),
            }, f, indent=2)
        print(f"[Direct] Saved to models/direct_score.json")

def train_lightgbm(save=True):
    """Train LightGBM multi-class model for comparison."""
    import lightgbm as lgb

    X, y, match_ids = _load_training_data()
    if len(X) == 0:
        print("[LightGBM] No training data")
        return

    print(f"[LightGBM] Loaded {len(X)} samples, {len(FEATURES)} features, {NUM_CLASSES} classes")

    split = int(len(X) * 0.9)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = lgb.LGBMClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        objective='multiclass',
        num_class=NUM_CLASSES,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=0.1,
        min_child_samples=20,
        random_state=42,
        metric='multi_logloss',
        verbose=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)

    exact_count = sum(int(y_pred[i]) == int(y_test[i]) for i in range(len(y_test)))
    exact = exact_count / len(y_test)
    actual_1x2 = [result(*class_to_score(y_test[i])) for i in range(len(y_test))]
    pred_1x2 = [result(*class_to_score(int(y_pred[i]))) for i in range(len(y_pred))]
    acc_1x2 = sum(1 for a, p in zip(actual_1x2, pred_1x2) if a == p) / len(y_test)

    n_test = len(y_test)
    rps_total = 0.0
    for i in range(n_test):
        ah, aa = class_to_score(y_test[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        pred_probs_i = y_pred_proba[i]
        p_h = sum(pred_probs_i[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pred_probs_i[h*5 + h] for h in range(5))
        p_a = sum(pred_probs_i[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    rps = rps_total / n_test

    print(f"\n[LightGBM] Results ({n_test} matches):")
    print(f"  Exact score: {exact*100:.2f}% ({exact_count}/{n_test})")
    print(f"  1X2: {acc_1x2*100:.2f}%")
    print(f"  RPS: {rps:.3f}")

    if save:
        model_dir = os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(model_dir, exist_ok=True)
        model.booster_.save_model(os.path.join(model_dir, 'lgbm_direct.txt'))
        with open(os.path.join(model_dir, 'lgbm_model_info.json'), 'w') as f:
            json.dump({
                'features': FEATURES,
                'num_classes': NUM_CLASSES,
                'classes': [f'{h}-{a}' for h, a in SCORE_CLASSES],
                'train_samples': len(X_train),
                'test_samples': n_test,
                'exact_pct': round(exact * 100, 2),
                'acc_1x2_pct': round(acc_1x2 * 100, 2),
                'rps': round(rps, 3),
            }, f, indent=2)
        print(f"[LightGBM] Saved to models/lgbm_direct.txt")

class TorchMLPWrapper:
    """Picklable wrapper around PyTorch model with sklearn-compatible API."""
    def __init__(self, model, device='cpu'):
        self.model = model
        self.device = device
        self.model.eval()
        self.model.to(device)
    def predict_proba(self, X):
        import torch
        self.model.eval()
        with torch.no_grad():
            X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
            return torch.softmax(self.model(X_t), dim=1).cpu().numpy()

class EnsemblePredictor:
    """Multi-model ensemble: XGBoost + multiple DeepNNs."""
    def __init__(self, models, model_weights, xgb_model, xgb_weight, imp, scaler):
        self.models = models
        self.model_weights = model_weights
        self.xgb_model = xgb_model
        self.xgb_weight = xgb_weight
        self.imp = imp
        self.scaler = scaler

    def predict_proba(self, X):
        nn_total = 1.0 - self.xgb_weight
        proba = self.xgb_weight * self.xgb_model.predict_proba(X)
        if nn_total > 0 and len(self.models) > 0:
            X_imp = self.imp.transform(X)
            X_s = self.scaler.transform(X_imp)
            w_each = nn_total / len(self.models)
            for m in self.models:
                proba += w_each * m.predict_proba(X_s)
        return proba

_BLEND_CACHE = None
def load_model():
    global _BLEND_CACHE
    path = os.path.join(os.path.dirname(__file__), 'models', 'direct_score.json')
    if not os.path.exists(path):
        return None
    import xgboost as xgb
    blend_path = os.path.join(os.path.dirname(__file__), 'models', 'mlp_blend.pkl')
    try:
        import joblib
        _BLEND_CACHE = joblib.load(blend_path)
        # New EnsemblePredictor format — use it directly
        if hasattr(_BLEND_CACHE, 'xgb_model'):
            return _BLEND_CACHE
    except:
        pass
    # Fallback: load plain XGBoost
    model = xgb.XGBClassifier()
    model.load_model(path)
    # Try loading old-format MLP blend (imp, scaler, wrapper, w_xgb, w_mlp)
    try:
        import joblib
        _BLEND_CACHE = joblib.load(blend_path)
    except:
        pass
    return model

def build_feature_vector(home_team, away_team, match_date, odds_b365=None, odds_avg=None):
    """Build the 47-feature vector for a single match.
    odds_b365 = (h, d, a) tuple from B365 odds (e.g. 1.5, 3.4, 6.0)
    odds_avg = (h, d, a) tuple from average odds
    Both optional — None means feature is missing (XGBoost handles it).
    """
    conn = sqlite3.connect(DB)
    try:
        from lambda_predictor import _resolve_team_name_sql as resolve
        home_r = resolve(conn, home_team, match_date)
        away_r = resolve(conn, away_team, match_date)
        if not home_r or not away_r:
            return None

        cur = conn.execute('''
            SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                   wf.form_points, wf.matches_played, wf.rolling_shots_for,
                   wf.rolling_shots_against
            FROM walkforward_state wf
            WHERE wf.team_name = ? AND wf.date <= ?
            ORDER BY wf.date DESC LIMIT 1
        ''', (home_r, match_date))
        h = cur.fetchone()
        cur.execute('''
            SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                   wf.form_points, wf.matches_played, wf.rolling_shots_for,
                   wf.rolling_shots_against
            FROM walkforward_state wf
            WHERE wf.team_name = ? AND wf.date <= ?
            ORDER BY wf.date DESC LIMIT 1
        ''', (away_r, match_date))
        a = cur.fetchone()
        if not h or not a:
            return None
    finally:
        conn.close()

    h_elo, h_xgf, h_xga, h_f, h_mp, h_shots, h_shots_a = h
    a_elo, a_xgf, a_xga, a_f, a_mp, a_shots, a_shots_a = a
    elo_diff = h_elo - a_elo
    h_xg_diff = (h_xgf or 1.2) - (h_xga or 1.2)
    a_xg_diff = (a_xgf or 1.2) - (a_xga or 1.2)
    h_shot_diff = (h_shots or 10) - (h_shots_a or 10)
    a_shot_diff = (a_shots or 10) - (a_shots_a or 10)

    h_days_rest = 7
    a_days_rest = 7
    try:
        conn2 = sqlite3.connect(DB)
        from datetime import datetime
        match_ts = int(datetime.strptime(match_date, '%Y-%m-%d').timestamp())
        cur = conn2.execute('''
            SELECT MAX(start_timestamp) FROM sofa_historical_results
            WHERE (home_team = ? OR away_team = ?) AND date < ?
        ''', (home_r, home_r, match_date))
        h_last = cur.fetchone()[0]
        cur.execute('''
            SELECT MAX(start_timestamp) FROM sofa_historical_results
            WHERE (home_team = ? OR away_team = ?) AND date < ?
        ''', (away_r, away_r, match_date))
        a_last = cur.fetchone()[0]
        conn2.close()
        if h_last: h_days_rest = max(1, int((match_ts - h_last) / 86400))
        if a_last: a_days_rest = max(1, int((match_ts - a_last) / 86400))
    except:
        pass

    fp_h = fp_d = fp_a = 0.0
    fp_avail = 0
    try:
        conn3 = sqlite3.connect(DB)
        cur = conn3.execute('''
            SELECT prob_h, prob_d, prob_a FROM forebet_predictions
            WHERE date = ? AND (home_team LIKE ? OR ? LIKE home_team)
            LIMIT 1
        ''', (match_date, '%' + home_team + '%', home_team))
        fp = cur.fetchone()
        conn3.close()
        if fp:
            fp_h = (fp[0] or 0) / 100.0
            fp_d = (fp[1] or 0) / 100.0
            fp_a = (fp[2] or 0) / 100.0
            fp_avail = 1
    except:
        pass

    # Match statistics (for historical matches only — future matches will be None)
    st_h_xg = st_a_xg = st_h_shots = st_a_shots = None
    st_h_sot = st_a_sot = st_h_poss = st_a_poss = None
    st_h_corners = st_a_corners = st_h_fouls = st_a_fouls = None
    try:
        conn4 = sqlite3.connect(DB)
        cur = conn4.execute('''
            SELECT home_xg, away_xg, home_shots, away_shots,
                   home_sot, away_sot, home_possession, away_possession,
                   home_corners, away_corners, home_fouls, away_fouls
            FROM sofa_match_stats
            WHERE event_id = (
                SELECT id FROM sofa_historical_results
                WHERE home_team = ? AND away_team = ? AND date = ?
                LIMIT 1
            )
        ''', (home_team, away_team, match_date))
        row = cur.fetchone()
        conn4.close()
        if row:
            st_h_xg, st_a_xg = row[0], row[1]
            st_h_shots, st_a_shots = row[2], row[3]
            st_h_sot, st_a_sot = row[4], row[5]
            st_h_poss, st_a_poss = row[6], row[7]
            st_h_corners, st_a_corners = row[8], row[9]
            st_h_fouls, st_a_fouls = row[10], row[11]
    except:
        pass

    # Lineups formations
    lu_h_def = lu_a_def = 4.0
    has_lu = 0.0
    lu_h_starters = lu_a_starters = None
    try:
        conn5 = sqlite3.connect(DB)
        cur = conn5.execute('''
            SELECT home_formation, away_formation, home_players_json, away_players_json FROM sofa_lineups
            WHERE event_id = (
                SELECT id FROM sofa_historical_results
                WHERE home_team = ? AND away_team = ? AND date = ?
                LIMIT 1
            )
        ''', (home_team, away_team, match_date))
        row = cur.fetchone()
        conn5.close()
        if row:
            lu_h_def = formation_defenders(row[0])
            lu_a_def = formation_defenders(row[1])
            has_lu = 1.0
            try:
                hpj = json.loads(row[2]) if row[2] else []
                apj = json.loads(row[3]) if row[3] else []
                lu_h_starters = [p.get('player', {}).get('name', '') for p in hpj if isinstance(p, dict) and not p.get('substitute', False)]
                lu_a_starters = [p.get('player', {}).get('name', '') for p in apj if isinstance(p, dict) and not p.get('substitute', False)]
            except:
                pass
    except:
        pass

    # Player impact features
    h_miss = h_att = h_def = a_miss = a_att = a_def = 0
    try:
        from player_impact import _load_cache, get_missing_impact
        _load_cache()
        if has_lu and lu_h_starters and lu_a_starters:
            h_miss, h_att, h_def, a_miss, a_att, a_def = get_missing_impact(
                home_r, away_r, lu_h_starters, lu_a_starters
            )
    except:
        pass

    # Market odds (optional — from The Odds API at prediction time)
    ob_h = ob_d = ob_a = oa_h = oa_d = oa_a = None
    if odds_b365 and len(odds_b365) == 3:
        ob_h, ob_d, ob_a = odds_b365
    if odds_avg and len(odds_avg) == 3:
        oa_h, oa_d, oa_a = odds_avg

    # ── Engineered features (same as training) ──
    he = h_elo or 1600; ae = a_elo or 1600; ed = elo_diff
    hxgf = h_xgf or 1.2; hxga = h_xga or 1.2
    axgf = a_xgf or 1.2; axga = a_xga or 1.2
    hf = h_f or 0.5; af = a_f or 0.5
    hmp = h_mp or 0; amp = a_mp or 0
    hsh = h_shots or 10; ash = a_shots or 10
    hsha = h_shots_a or 10; asha = a_shots_a or 10
    hdr = h_days_rest; adr = a_days_rest
    eps = 1e-6

    elo_form_home = he * hf
    elo_form_away = ae * af
    elo_xg_home = he * hxgf
    elo_xg_away = ae * axgf
    form_xg_home = hf * hxgf
    form_xg_away = af * axgf
    elo_diff_form_diff = ed * (hf - af)
    fatigue_home = hmp / (hdr + 1)
    fatigue_away = amp / (adr + 1)
    xg_ratio = hxgf / (axgf + eps)
    shots_ratio = hsh / (ash + eps)
    form_ratio = hf / (af + eps)
    xgf_xga_ratio_home = hxgf / (hxga + eps)
    xgf_xga_ratio_away = axgf / (axga + eps)
    shot_eff_home = hxgf / (hsh + eps)
    shot_eff_away = axgf / (ash + eps)
    elo_diff_sq = ed ** 2
    xg_diff_sq = (hxgf - hxga) ** 2
    form_diff_sq = (hf - af) ** 2
    month = 6; dow = 0; season_prog = 0.5; is_wknd = 0
    try:
        from datetime import datetime as _dt
        dt = _dt.strptime(match_date, '%Y-%m-%d') if isinstance(match_date, str) else _dt.now()
        month = dt.month; dow = dt.weekday()
        is_wknd = 1 if dow >= 5 else 0
        season_prog = min(1.0, hmp / 50.0)
    except: pass

    # Weather + Travel features
    home_temp = home_precip = home_wind = home_humidity = travel_dist = None
    try:
        conn_w = sqlite3.connect(DB)
        cur = conn_w.execute('SELECT lat, lon FROM team_venue WHERE team_name = ?', (home_team,))
        tv_h = cur.fetchone()
        cur = conn_w.execute('SELECT lat, lon FROM team_venue WHERE team_name = ?', (away_team,))
        tv_a = cur.fetchone()
        if tv_h and tv_a:
            from math import radians, sin, cos, sqrt, asin
            r = 6371.0
            dlat = radians(tv_a[0] - tv_h[0])
            dlon = radians(tv_a[1] - tv_h[1])
            a = sin(dlat/2)**2 + cos(radians(tv_h[0])) * cos(radians(tv_a[0])) * sin(dlon/2)**2
            travel_dist = 2 * r * asin(sqrt(a))
        if tv_h:
            cur = conn_w.execute('SELECT temp_max, temp_min, precip, wind, humidity FROM venue_weather WHERE date=? AND lat=? AND lon=?',
                               (match_date, tv_h[0], tv_h[1]))
            wd = cur.fetchone()
            if wd:
                home_temp = (wd[0] + wd[1]) / 2.0 if wd[0] is not None and wd[1] is not None else None
                home_precip = wd[2]
                home_wind = wd[3]
                home_humidity = wd[4]
        conn_w.close()
    except:
        pass

    return np.array([[
        he, ae, ed,
        hxgf, hxga, axgf, axga,
        hf, af, hmp, amp,
        hsh, ash, hsha, asha,
        h_xg_diff, a_xg_diff, h_shot_diff, a_shot_diff,
        hdr, adr,
        fp_h, fp_d, fp_a, fp_avail,
        st_h_xg, st_a_xg,
        st_h_shots, st_a_shots,
        st_h_sot, st_a_sot,
        st_h_poss, st_a_poss,
        st_h_corners, st_a_corners,
        st_h_fouls, st_a_fouls,
        lu_h_def, lu_a_def, lu_h_def - lu_a_def,
        has_lu,
        h_miss, h_att, h_def, a_miss, a_att, a_def,
        ob_h, ob_d, ob_a,
        oa_h, oa_d, oa_a,
        elo_form_home, elo_form_away,
        elo_xg_home, elo_xg_away,
        form_xg_home, form_xg_away,
        elo_diff_form_diff, fatigue_home, fatigue_away,
        xg_ratio, shots_ratio, form_ratio,
        xgf_xga_ratio_home, xgf_xga_ratio_away,
        shot_eff_home, shot_eff_away,
        elo_diff_sq, xg_diff_sq, form_diff_sq,
        month, dow, season_prog, is_wknd,
        home_temp, home_precip, home_wind, home_humidity,
        travel_dist,
    ]], dtype=float)

def predict_match(home_team, away_team, match_date, odds_b365=None, odds_avg=None):
    """Predict probabilities for a single match. Returns dict with probs per score + marginal.
    odds_b365 = (h, d, a) tuple from B365 odds
    odds_avg = (h, d, a) tuple from average odds
    """
    model_or_ensemble = load_model()
    if model_or_ensemble is None:
        return None
    feat = build_feature_vector(home_team, away_team, match_date, odds_b365, odds_avg)
    if feat is None:
        return None

    global _BLEND_CACHE
    is_ensemble = hasattr(_BLEND_CACHE, 'xgb_model') if _BLEND_CACHE is not None else False
    if is_ensemble:
        proba = model_or_ensemble.predict_proba(feat)[0]
    else:
        proba = model_or_ensemble.predict_proba(feat)[0]
        if _BLEND_CACHE is not None:
            try:
                imp, scaler, mlp, w_xgb, w_mlp = _BLEND_CACHE
                feat_imp = imp.transform(feat)
                feat_s = scaler.transform(feat_imp)
                mlp_proba = mlp.predict_proba(feat_s)[0]
                proba = w_xgb * proba + w_mlp * mlp_proba
            except:
                pass

    result = {}
    score_probs = {}
    home_marginal = np.zeros(5)
    away_marginal = np.zeros(5)
    for cls_idx in range(NUM_CLASSES):
        h, a = class_to_score(cls_idx)
        p = float(proba[cls_idx])
        score_probs[f'{h}-{a}'] = p
        home_marginal[h] += p
        away_marginal[a] += p

    result['score_probs'] = score_probs

    # Most likely scores
    sorted_scores = sorted(score_probs.items(), key=lambda x: -x[1])
    result['top_scores'] = [(s, round(p, 4)) for s, p in sorted_scores[:10]]

    # 1X2
    p_home = sum(proba[h * 5 + a] for h in range(5) for a in range(5) if h > a)
    p_draw = sum(proba[h * 5 + h] for h in range(5))
    p_away = sum(proba[h * 5 + a] for h in range(5) for a in range(5) if a > h)
    result['probs_1x2'] = {
        'home': round(float(p_home), 4),
        'draw': round(float(p_draw), 4),
        'away': round(float(p_away), 4),
    }

    # Expected goals
    result['expected_goals'] = {
        'home': round(float(sum(h * home_marginal[h] for h in range(5))), 3),
        'away': round(float(sum(a * away_marginal[a] for a in range(5))), 3),
    }

    # Correct score prediction (most likely single score)
    best_score = sorted_scores[0][0]
    h_best, a_best = best_score.split('-')
    result['predicted_score'] = f'{h_best}-{a_best}'
    result['predicted_prob'] = sorted_scores[0][1]

    return result

if __name__ == '__main__':
    train(save=True)
    train_lightgbm(save=True)
