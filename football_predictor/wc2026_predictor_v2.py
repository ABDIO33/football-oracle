#!/usr/bin/env python3
"""
World Cup 2026 — Improved Predictor
يستخدم بيانات حقيقية من قاعدة البيانات (Elo, Glicko, recent form, H2H)
لتغذية موديل 36.35% بميزات دقيقة
"""
import sys, os, json, sqlite3, joblib, math, warnings
import numpy as np
from datetime import datetime
warnings.filterwarnings('ignore')

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')
MODEL_PATH = os.path.join(BASE, 'models', 'ensemble_seed42.pkl')

# WC 2026 R32 Fixtures (June 30 - July 4)
FIXTURES = [
    ('2026-06-30', 'Netherlands', 'Morocco'),
    ('2026-06-30', 'Brazil', 'Japan'),
    ('2026-06-30', 'Germany', 'Bosnia & Herzegovina'),
    ('2026-07-01', "Cote d'Ivoire", 'Norway'),
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

SCORE_LABELS = ['0-0','0-1','0-2','0-3','0-4','0-4+',
                '1-0','1-1','1-2','1-3','1-4','1-4+',
                '2-0','2-1','2-2','2-3','2-4','2-4+',
                '3-0','3-1','3-2','3-3','3-4','3-4+',
                '4-0','4-1','4-2','4-3','4-4','4-4+'][:25]

def log(m): print(f'[WC] {m}', flush=True)

def get_team_data(team, conn):
    """Get all available data for a team from DB"""
    c = conn.cursor()
    data = {'name': team, 'elo': 1500, 'glicko': 1500, 'glicko_rd': 350,
            'matches_played': 0, 'form_points': 0.5, 'rolling_xg_for': 1.5, 'rolling_xg_against': 1.3,
            'recent_gf': 0, 'recent_ga': 0, 'recent_matches': 0, 'recent_wins': 0, 'recent_draws': 0}
    
    # Try direct match first
    r = c.execute('''SELECT elo, matches_played, form_points, rolling_xg_for, rolling_xg_against 
                     FROM walkforward_state WHERE team_name = ? 
                     ORDER BY date DESC LIMIT 1''', (team,)).fetchone()
    # If not found, try Côte instead of Cote
    if not r:
        alt_team = team.replace("Cote d'Ivoire", "Côte d'Ivoire")
        r = c.execute('''SELECT elo, matches_played, form_points, rolling_xg_for, rolling_xg_against 
                         FROM walkforward_state WHERE team_name = ? 
                         ORDER BY date DESC LIMIT 1''', (alt_team,)).fetchone()
        if r: team = alt_team
    # Try partial match
    if not r:
        r = c.execute('''SELECT elo, matches_played, form_points, rolling_xg_for, rolling_xg_against 
                         FROM walkforward_state WHERE team_name LIKE ? 
                         ORDER BY date DESC LIMIT 1''', (f'%{team.split("&")[0].strip()}%',)).fetchone()
    
    if r:
        data['elo'] = float(r[0])
        data['matches_played'] = int(r[1])
        data['form_points'] = float(r[2]) if r[2] else 0.5
        data['rolling_xg_for'] = float(r[3]) if r[3] else 1.5
        data['rolling_xg_against'] = float(r[4]) if r[4] else 1.3
    
    # Glicko
    r = c.execute('''SELECT glicko_rating, glicko_rd FROM glicko_state 
                     WHERE team_name = ? ORDER BY date DESC LIMIT 1''', (team,)).fetchone()
    if r:
        data['glicko'] = float(r[0])
        data['glicko_rd'] = float(r[1])
    
    # Recent form from sofa_historical_results
    r = c.execute('''SELECT home_score, away_score, home_team FROM sofa_historical_results 
                     WHERE (home_team = ? OR away_team = ?) AND home_score IS NOT NULL
                     ORDER BY date DESC LIMIT 10''', (team, team)).fetchall()
    goals_for, goals_against, wins, draws, n = 0, 0, 0, 0, 0
    for row in r:
        if row[2] == team:  # home
            gf, ga = row[0], row[1]
        else:  # away
            gf, ga = row[1], row[0]
        goals_for += gf
        goals_against += ga
        n += 1
        if gf > ga: wins += 1
        elif gf == ga: draws += 1
    if n > 0:
        data['recent_gf'] = goals_for / n
        data['recent_ga'] = goals_against / n
        data['recent_matches'] = n
        data['recent_wins'] = wins
        data['recent_draws'] = draws
    
    return data

def build_306_features(home, away, date_str, hd, ad, conn):
    """Build 306-feature vector using real team data"""
    f = np.zeros(306, dtype=np.float32)
    c = conn.cursor()
    
    # [0-1] Elo
    f[0] = hd['elo']
    f[1] = ad['elo']
    f[2] = f[0] - f[1]  # elo_diff
    
    # [3-4] Form
    f[3] = hd['form_points'] * 100
    f[4] = ad['form_points'] * 100
    
    # [5-6] Matches played
    f[5] = min(hd['matches_played'], 1000)
    f[6] = min(ad['matches_played'], 1000)
    
    # [7-8] Days rest
    f[7] = 7.0
    f[8] = 7.0
    
    # [9-24] Derived from basics
    f[9] = f[0] * f[3] / 100.0
    f[10] = f[1] * f[4] / 100.0
    f[11] = f[0] * hd['rolling_xg_for'] / 100.0
    f[12] = f[1] * ad['rolling_xg_for'] / 100.0
    f[13] = f[3] * hd['rolling_xg_for'] / 100.0
    f[14] = f[4] * ad['rolling_xg_for'] / 100.0
    f[15] = (f[0]-f[1]) * (f[3]-f[4]) / 10000.0
    f[18] = f[3] / max(f[4], 0.1)
    f[19] = f[2] ** 2
    f[20] = (f[3] - f[4]) ** 2
    
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        f[21] = dt.month
        f[22] = dt.weekday()
        f[23] = dt.timetuple().tm_yday / 365.0
        f[24] = 1.0 if dt.weekday() >= 5 else 0.0
    except:
        f[21] = 7; f[22] = 0; f[23] = 0.5
    
    # [25] travel_distance (default 0 for neutral venue WC)
    f[25] = 0.0
    
    # [26-50] Poisson
    home_lam = max(0.5, hd['recent_gf'] if hd['recent_matches'] > 0 else f[0]/1500*1.5)
    away_lam = max(0.5, ad['recent_gf'] if ad['recent_matches'] > 0 else f[1]/1500*1.5)
    for si, hg in enumerate([0,1,2,3,4]):
        for sj, ag in enumerate([0,1,2,3,4]):
            idx = 26 + si * 5 + sj
            if idx < 51:
                p = (math.exp(-home_lam) * home_lam**hg / math.factorial(hg)) * \
                    (math.exp(-away_lam) * away_lam**ag / math.factorial(ag))
                f[idx] = float(p)
    
    # [51] is_relegation_battle
    f[51] = 0.0  # WC isn't relegation
    
    # [52-62] H2H
    part_h = home.split(' ')[0].split("'")[0].split('&')[0].strip()
    part_a = away.split(' ')[0].split("'")[0].split('&')[0].strip()
    h2h = c.execute('''SELECT COUNT(*), AVG(home_score), AVG(away_score) FROM sofa_historical_results 
        WHERE ((home_team LIKE ? AND away_team LIKE ?) OR (home_team LIKE ? AND away_team LIKE ?))
        AND home_score IS NOT NULL''',
        (f'%{part_h}%', f'%{part_a}%', f'%{part_a}%', f'%{part_h}%')).fetchone()
    if h2h and h2h[0] > 0:
        f[52] = float(h2h[1])
        f[53] = float(h2h[2])
        f[54] = min(1.0, h2h[0] / 20.0)
        f[55] = float(h2h[1]) / max(float(h2h[2]), 0.1)  # h2h_recency_home
    
    # [64-78] Player impact (defaults)
    f[64] = 0.0; f[65] = 0.0; f[66] = 0.0
    
    # [79-94] Streaks
    if hd['recent_matches'] > 0:
        f[79] = hd['recent_wins']  # home_win_streak
        f[85] = hd['recent_wins'] / max(hd['recent_matches'], 1) * 5  # home_momentum_3
        f[87] = hd['recent_wins'] / max(hd['recent_matches'], 1) * 5  # home_momentum_5
        f[93] = hd['recent_wins'] / max(hd['recent_matches'], 1)  # home_win_rate
    if ad['recent_matches'] > 0:
        f[80] = ad['recent_wins']
        f[86] = ad['recent_wins'] / max(ad['recent_matches'], 1) * 5
        f[88] = ad['recent_wins'] / max(ad['recent_matches'], 1) * 5
        f[94] = ad['recent_wins'] / max(ad['recent_matches'], 1)
    
    # [103-109] Glicko
    f[103] = hd['glicko']
    f[104] = ad['glicko']
    f[105] = f[103] - f[104]
    f[106] = hd['glicko_rd']
    f[107] = ad['glicko_rd']
    f[108] = max(0, hd['glicko'] - hd['elo']) if hd['glicko'] > 0 else 0
    f[109] = max(0, ad['glicko'] - ad['elo']) if ad['glicko'] > 0 else 0
    
    # [110-136] Quadratics
    f[110] = f[2] ** 3  # elo_diff_cubed
    f[112] = math.sqrt(abs(f[2])) if f[2] > 0 else 0
    f[114] = f[0] ** 2
    f[115] = f[1] ** 2
    f[118] = f[3] ** 2
    f[120] = f[4] ** 2
    
    # [137-208] Interaction features
    base_vars = [f[0], f[1], f[2], f[3], f[4], f[7], f[8]]
    idx = 137
    for b in base_vars:
        for m in base_vars:
            if idx < 208:
                f[idx] = b * m / 1000.0
                idx += 1
    
    # [209-238] League context (WC defaults)
    f[209] = 1.4; f[210] = 1.2; f[211] = 2.6
    f[212] = 0.43; f[213] = 0.24; f[214] = 0.33
    
    # [241-260] Home/away
    f[250] = hd['elo'] / 100.0  # home_strength
    f[258] = ad['elo'] / 100.0  # away_strength
    f[260] = f[250] - f[258]  # strength_diff
    
    # [271-295] Advanced
    f[275] = 0.05  # poisson_diag_inflation
    f[293] = f[26]  # poisson_both_cs (0-0 prob)
    f[294] = 1.0 - f[26]  # poisson_btts (not 0-0)
    
    # [296-305] Understat features (not available for WC, use defaults)
    f[296] = hd['rolling_xg_for']
    f[297] = ad['rolling_xg_for']
    f[298] = f[296] - f[297]
    
    return f

def main():
    log('Loading model...')
    model = joblib.load(MODEL_PATH)
    log(f'Model: LGBM, {model.n_features_} features, {model.n_classes_} classes')
    
    conn = sqlite3.connect(DB, timeout=30)
    predictions = []
    
    for date, home, away in FIXTURES:
        log(f'Predicting: {home} vs {away}')
        
        hd = get_team_data(home, conn)
        ad = get_team_data(away, conn)
        
        features = build_306_features(home, away, date, hd, ad, conn)
        X = features.reshape(1, -1)
        
        probs = model.predict_proba(X)[0]
        pred_class = int(model.predict(X)[0])
        top_indices = probs.argsort()[-5:][::-1]
        
        pred = {
            'date': date,
            'home': home,
            'away': away,
            'home_elo': round(hd['elo']),
            'away_elo': round(ad['elo']),
            'home_glicko': round(hd['glicko']),
            'away_glicko': round(ad['glicko']),
            'predicted_score': SCORE_LABELS[pred_class] if pred_class < len(SCORE_LABELS) else str(pred_class),
            'confidence': float(probs[pred_class]),
            'top5': [(SCORE_LABELS[i] if i < len(SCORE_LABELS) else str(i), float(probs[i])) for i in top_indices],
        }
        predictions.append(pred)
        
        top5_str = ' | '.join([f'{s}: {p*100:.1f}%' for s, p in pred['top5'][:3]])
        log(f'  {home} {pred["predicted_score"]} {away} ({pred["confidence"]*100:.1f}%)')
        log(f'    [{top5_str}]')
    
    conn.close()
    
    # Save
    with open(os.path.join(BASE, 'wc2026_predictions.json'), 'w', encoding='utf-8') as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)
    
    # Print table
    log('\n' + '=' * 80)
    log('WORLD CUP 2026 R32 — IMPROVED PREDICTIONS')
    log('=' * 80)
    log(f'{"Date":12s} {"Home":25s} {"Score":8s} {"Away":25s} {"Conf":6s} {"Elo":10s}')
    log('-' * 80)
    for p in predictions:
        log(f'{p["date"]:12s} {p["home"]:25s} {p["predicted_score"]:8s} {p["away"]:25s} {p["confidence"]*100:5.1f}% {p["home_elo"]:d}/{p["away_elo"]:d}')
    log('=' * 80)
    log('Saved to wc2026_predictions.json')

if __name__ == '__main__':
    main()
