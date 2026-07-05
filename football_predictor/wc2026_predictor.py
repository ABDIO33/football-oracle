#!/usr/bin/env python3
"""
World Cup 2026 Predictor — يستخدم موديل 36.35% (306 features)
يبني feature vector لكل مباراة من بيانات قاعدة البيانات
"""
import sys, os, json, sqlite3, pickle, joblib, warnings, math
import numpy as np
from datetime import datetime
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')
MODELS_DIR = os.path.join(BASE, 'models')

# World Cup R32 fixtures
FIXTURES = [
    ('2026-06-30', 'Netherlands', 'Morocco'),
    ('2026-06-30', 'Brazil', 'Japan'),
    ('2026-06-30', 'Germany', 'Bosnia & Herzegovina'),
    ('2026-07-01', 'Cote d\'Ivoire', 'Norway'),
    ('2026-07-01', 'France', 'Paraguay'),
    ('2026-07-01', 'Mexico', 'Ecuador'),
    ('2026-07-02', 'USA', 'Bosnia & Herzegovina'),
    ('2026-07-02', 'Belgium', 'Ecuador'),
    ('2026-07-02', 'England', 'Ecuador'),
    ('2026-07-03', 'Portugal', 'Croatia'),
    ('2026-07-03', 'Spain', 'Austria'),
    ('2026-07-03', 'Switzerland', 'Ecuador'),
    ('2026-07-04', 'Argentina', 'Cabo Verde'),
    ('2026-07-04', 'Colombia', 'Paraguay'),
    ('2026-07-04', 'Australia', 'Egypt'),
]

SCORE_LABELS = [
    '0-0','0-1','0-2','0-3','0-4','0-4+',
    '1-0','1-1','1-2','1-3','1-4','1-4+',
    '2-0','2-1','2-2','2-3','2-4','2-4+',
    '3-0','3-1','3-2','3-3','3-4','3-4+',
    '4-0','4-1','4-2','4-3','4-4','4-4+'
][:25]  # 25 classes

def log(m): print(f'[WC Predictor] {m}', flush=True)

# ========== BUILD FEATURES ==========
def build_306_features(home, away, date, conn):
    """Build 306-feature vector for a match using DB data"""
    c = conn.cursor()
    
    # Default feature vector (zeros)
    f = np.zeros(306, dtype=np.float32)
    
    # === Basic features (0-24) ===
    # Get Elo from walkforward_state
    h_elo = c.execute('''
        SELECT elo FROM walkforward_state 
        WHERE team_name LIKE ? ORDER BY date DESC LIMIT 1
    ''', (f'%{home.split()[0]}%',)).fetchone()
    a_elo = c.execute('''
        SELECT elo FROM walkforward_state 
        WHERE team_name LIKE ? ORDER BY date DESC LIMIT 1
    ''', (f'%{away.split()[0]}%',)).fetchone()
    
    f[0] = float(h_elo[0]) if h_elo else 1500.0  # home_elo
    f[1] = float(a_elo[0]) if a_elo else 1500.0  # away_elo
    f[2] = f[0] - f[1]  # elo_diff
    
    # Form (last 5 matches points)
    f[3] = 50.0  # home_form (default)
    f[4] = 50.0  # away_form (default)
    f[5] = 0.0   # home_matches_played
    f[6] = 0.0   # away_matches_played
    
    # Days rest
    f[7] = 7.0   # home_days_rest
    f[8] = 7.0   # away_days_rest
    
    # === Derived features (9-24) ===
    f[9] = f[0] * f[3] / 100.0  # elo_form_home
    f[10] = f[1] * f[4] / 100.0 # elo_form_away
    f[11] = f[0] * 1.5 / 100.0  # elo_xg_home
    f[12] = f[1] * 1.5 / 100.0  # elo_xg_away
    f[13] = f[3] * 1.5 / 100.0  # form_xg_home
    f[14] = f[4] * 1.5 / 100.0  # form_xg_away
    f[15] = (f[0]-f[1]) * (f[3]-f[4]) / 10000.0  # elo_diff_form_diff
    f[16] = max(0, 7.0 - f[7])  # fatigue_home
    f[17] = max(0, 7.0 - f[8])  # fatigue_away
    f[18] = f[3] / max(f[4], 0.1)  # form_ratio
    f[19] = f[2] ** 2  # elo_diff_sq
    f[20] = (f[3] - f[4]) ** 2  # form_diff_sq
    
    try:
        dt = datetime.strptime(date, '%Y-%m-%d')
        f[21] = dt.month  # month
        f[22] = dt.weekday()  # day_of_week
        f[23] = (dt.timetuple().tm_yday) / 365.0  # season_progress
        f[24] = 1.0 if dt.weekday() >= 5 else 0.0  # is_weekend
    except:
        f[21] = 7; f[22] = 0; f[23] = 0.5; f[24] = 0
    
    # === Poisson features (25-50) ===
    # Use default Poisson probabilities
    home_lam = f[0] / 1500.0 * 1.5  # lambda from elo
    away_lam = f[1] / 1500.0 * 1.2
    for si, hg in enumerate([0,1,2,3,4]):
        for sj, ag in enumerate([0,1,2,3,4]):
            idx = 26 + si * 5 + sj
            if idx < 51:
                p = (math.exp(-home_lam) * home_lam**hg / math.factorial(hg)) * \
                    (math.exp(-away_lam) * away_lam**ag / math.factorial(ag))
                f[idx] = float(p)
    
    # === H2H features (51-62) ===
    # Try to get H2H from DB
    h2h = c.execute('''
        SELECT COUNT(*), AVG(home_score), AVG(away_score) FROM sofa_historical_results
        WHERE (home_team LIKE ? AND away_team LIKE ?)
        OR (home_team LIKE ? AND away_team LIKE ?)
    ''', (f'%{home.split()[0]}%', f'%{away.split()[0]}%',
          f'%{away.split()[0]}%', f'%{home.split()[0]}%')).fetchone()
    
    if h2h and h2h[0] > 0:
        f[52] = h2h[1]  # h2h_home_avg
        f[53] = h2h[2]  # h2h_away_avg
        f[54] = min(1.0, h2h[0] / 20.0)  # h2h_confidence
    
    # === Interaction features (137-208) ===
    # Generate from basic features
    idx = 137
    for base in [f[0], f[1], f[2], f[3], f[4], f[7], f[8]]:
        for mul in [f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8]]:
            if idx < 208:
                f[idx] = base * mul / 1000.0
                idx += 1
    
    # === Quadratics (110-136) ===
    for i in range(0, 24):
        val = f[i]
        idx = 110 + i
        if idx <= 136:
            if i == 1:
                f[110] = f[2] ** 3  # elo_diff_cubed
            elif i == 2:
                f[111] = f[2] ** 3  
            elif i == 3:
                f[113] = math.log10(abs(f[2]) + 1) * (1 if f[2] >= 0 else -1)  # elo_diff_logabs
            elif i == 5:
                f[114] = f[0] ** 2  # home_elo_sq
            elif i == 6:
                f[115] = f[1] ** 2  # away_elo_sq
            elif i == 7:
                f[116] = abs(f[2]) ** (1/3)  # elo_diff_cuberoot
            elif i == 8:
                f[117] = f[3] ** 2  # home_form_sq
            elif i == 9:
                f[120] = f[4] ** 2  # away_form_sq
    
    # === League context (209-238) ===
    f[209] = 1.5  # league_avg_h_goals
    f[210] = 1.2  # league_avg_a_goals
    f[211] = 2.7  # league_avg_total
    f[212] = 0.45  # league_h_win_pct
    f[213] = 0.24  # league_draw_pct
    f[214] = 0.31  # league_a_win_pct
    f[216] = 1.5   # league_lambda_h
    f[217] = 1.2   # league_lambda_a
    
    # === Home/Away split (241-270) ===
    f[241] = 10   # home_total_home
    f[250] = 0.0  # home_strength
    f[260] = 0.0  # strength_diff
    
    # === Advanced metrics (271-295) ===
    f[275] = 0.05  # poisson_diag_inflation
    f[294] = 0.5   # poisson_btts
    
    # === Understat (296-305) ===
    # Try to get from DB
    us_home = c.execute('''
        SELECT AVG(home_xg) FROM source_understat 
        WHERE home_team LIKE ? LIMIT 10
    ''', (f'%{home.split()[0]}%',)).fetchone()
    us_away = c.execute('''
        SELECT AVG(away_xg) FROM source_understat 
        WHERE away_team LIKE ? LIMIT 10
    ''', (f'%{away.split()[0]}%',)).fetchone()
    
    if us_home and us_home[0]:
        f[296] = float(us_home[0])
    if us_away and us_away[0]:
        f[297] = float(us_away[0])
    f[298] = f[296] - f[297]  # understat_xg_diff
    
    return f

# ========== MAKE PREDICTIONS ==========
log('Loading model...')
model = joblib.load(os.path.join(MODELS_DIR, 'ensemble_seed42.pkl'))
log(f'Model: LGBMClassifier, {model.n_features_} features, {model.n_classes_} classes')

conn = sqlite3.connect(DB, timeout=30)

predictions = []
for date, home, away in FIXTURES:
    log(f'Predicting: {home} vs {away} ({date})')
    features = build_306_features(home, away, date, conn)
    
    # Model expects 2D array
    X = features.reshape(1, -1)
    
    # Predict
    probs = model.predict_proba(X)[0]
    pred_class = model.predict(X)[0]
    
    # Get top predictions
    top3 = probs.argsort()[-3:][::-1]
    
    pred_result = {
        'date': date,
        'home': home,
        'away': away,
        'predicted_score': SCORE_LABELS[pred_class] if pred_class < len(SCORE_LABELS) else f'{pred_class}',
        'confidence': float(probs[pred_class]),
        'top3_scores': [(SCORE_LABELS[i] if i < len(SCORE_LABELS) else str(i), float(probs[i])) for i in top3],
        'all_probs': [float(p) for p in probs],
    }
    predictions.append(pred_result)
    log(f'  → {home} {SCORE_LABELS[pred_class]} {away} ({float(probs[pred_class])*100:.1f}%)')
    for i in top3[:3]:
        label = SCORE_LABELS[i] if i < len(SCORE_LABELS) else str(i)
        log(f'     Top: {label} ({float(probs[i])*100:.1f}%)')

conn.close()

# Save predictions
with open(os.path.join(BASE, 'wc2026_predictions.json'), 'w') as f:
    json.dump(predictions, f, ensure_ascii=False, indent=2)
log(f'Saved to wc2026_predictions.json')

# Summary
log('')
log('='*60)
log('WORLD CUP 2026 PREDICTIONS')
log('='*60)
for p in predictions:
    top3_str = ', '.join([f'{s}({c*100:.0f}%)' for s,c in p['top3_scores']])
    log(p['date'] + ' | ' + p['home'] + ' vs ' + p['away'] + ' | ' + p['predicted_score'] + ' (' + str(round(p['confidence']*100,1)) + '%) | [' + top3_str + ']')
