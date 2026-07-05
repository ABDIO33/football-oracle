"""
expand_features.py — Expand features 81 -> 120+ for Score Exact 100
Adds: Poisson probs (25), league context, H2H, tournament importance,
      formation strength, interaction features

المشروع: Score Exact 100
القائد: DeepSeek V4 Flash Free الأول
"""
import sqlite3, os, json, numpy as np, math
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# 25 score classes
SCORES = [(h,a) for h in range(5) for a in range(5)]
SCORE_PROBS = [f'poisson_p{h}_{a}' for h,a in SCORES]

# Existing features from direct_predictor.py (81 base features)
BASE_FEATURES = [
    'home_elo','away_elo','elo_diff',
    'home_xg_for','home_xg_against','away_xg_for','away_xg_against',
    'home_form','away_form','home_matches_played','away_matches_played',
    'home_shots_for','away_shots_for','home_shots_against','away_shots_against',
    'home_xg_diff','away_xg_diff','home_shot_diff','away_shot_diff',
    'home_days_rest','away_days_rest',
    'forebet_prob_h','forebet_prob_d','forebet_prob_a','forebet_available',
    'home_glicko','away_glicko','home_glicko_rd','away_glicko_rd',
    'stat_h_xg','stat_a_xg','stat_h_shots','stat_a_shots',
    'stat_h_sot','stat_a_sot','stat_h_possession','stat_a_possession',
    'stat_h_corners','stat_a_corners','stat_h_fouls','stat_a_fouls',
    'home_formation_def','away_formation_def','formation_diff','has_lineups',
    'home_missing_core','away_missing_core',
    'home_att_loss','away_att_loss','home_def_loss','away_def_loss',
    'odds_b365h','odds_b365d','odds_b365a',
    'odds_avgh','odds_avgd','odds_avga',
    'elo_form_home','elo_form_away','elo_xg_home','elo_xg_away',
    'form_xg_home','form_xg_away','elo_diff_form_diff','fatigue_home','fatigue_away',
    'xg_ratio','shots_ratio','form_ratio',
    'xgf_xga_ratio_home','xgf_xga_ratio_away',
    'shot_eff_home','shot_eff_away',
    'elo_diff_sq','xg_diff_sq','form_diff_sq',
    'month','day_of_week','season_progress','is_weekend',
    'home_temp','home_precip','home_wind','home_humidity',
    'travel_distance',
]

NEW_FEATURES = []  # will be populated dynamically

def poisson_prob(lam, k):
    """P(X=k) for Poisson(lambda)"""
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam**k) * math.exp(-lam) / math.factorial(k)

def dixon_coles_tau(h, a, lam_h=1.0, lam_a=1.0, rho=-0.07):
    """Dixon-Coles adjustment factor — CORRECT: uses lambda values not scores"""
    if h == 0 and a == 0:
        return 1.0 - rho * lam_h * lam_a
    if h == 0 and a == 1:
        return 1.0 + rho * lam_h
    if h == 1 and a == 0:
        return 1.0 + rho * lam_a
    if h == 1 and a == 1:
        return 1.0 - rho
    return 1.0

def get_league_strength(tournament):
    """Map tournament to strength tier (0-4)"""
    strong = ['Premier League','Primera Division','Serie A','Bundesliga','Ligue 1',
              'Eredivisie','Primeira Liga','Premier League 2026']
    medium = ['Championship','Serie B','Liga Profesional','MLS','J1 League',
              'K League 1','Botola Pro','Super Lig','Jupiler Pro League']
    weak = ['League One','League Two','National League','E1','E2','E3',
            'SP1','SP2','Primera B','Liga de Expansion']
    if tournament in strong: return 4
    if tournament in medium: return 3
    if tournament in weak: return 2
    return 1

def get_tournament_importance(tournament):
    """Importance score 0-5"""
    cup = ['World Cup','Champions League','Europa League','FA Cup','Copa America',
           'Euro','Africa Cup','Asian Cup','Confederations Cup']
    top_league = ['Premier League','Primera Division','Serie A','Bundesliga','Ligue 1']
    second = ['Championship','Serie B','Liga Profesional','MLS','Eredivisie']
    if any(c in str(tournament) for c in ['World Cup','Champions League']): return 5
    if any(c in str(tournament) for c in cup): return 4
    if tournament in top_league: return 3
    if tournament in second: return 2
    return 1

def compute_h2h(conn, home_team, away_team, before_date, n=5):
    """Head-to-head: last n matches between these teams"""
    cur = conn.execute('''
        SELECT home_score, away_score, home_team, away_team
        FROM sofa_historical_results
        WHERE ((home_team = ? AND away_team = ?) OR (home_team = ? AND away_team = ?))
          AND date < ?
        ORDER BY date DESC LIMIT ?
    ''', (home_team, away_team, away_team, home_team, before_date, n))
    rows = cur.fetchall()
    if not rows: return [0.5, 0.0, 0.046]  # avg goals
    total_h = sum(r[0] for r in rows)
    total_a = sum(r[1] for r in rows)
    n_actual = len(rows)
    return [total_h/n_actual, total_a/n_actual, 1.0 if n_actual >= 3 else n_actual/3.0]

def expand_features_row(conn, row, tournament):
    """
    Take a base row dict + add expanded features.
    Returns dict with all features.
    """
    f = dict(row)  # copy base features
    
    # --- League context (3) ---
    f['league_strength'] = get_league_strength(tournament)
    f['tournament_importance'] = get_tournament_importance(tournament)
    
    # --- Poisson probs for this match (25 features) ---
    # Estimate lambda_home and lambda_away from features
    elo_diff = float(f.get('elo_diff', 0))
    home_attack = float(f.get('home_xg_for', 1.2))
    away_attack = float(f.get('away_xg_for', 1.0))
    home_def = float(f.get('home_xg_against', 1.0))
    away_def = float(f.get('away_xg_against', 1.2))
    
    # Expected goals with home advantage
    lam_h = max(0.1, home_attack * away_def * 1.08 * math.exp(elo_diff * 0.0003))
    lam_a = max(0.1, away_attack * home_def * math.exp(-elo_diff * 0.0003))
    
    for idx, (h, a) in enumerate(SCORES):
        prob_h = poisson_prob(lam_h, h)
        prob_a = poisson_prob(lam_a, a)
        tau = dixon_coles_tau(h, a, lam_h, lam_a, rho=-0.07)
        f[SCORE_PROBS[idx]] = prob_h * prob_a * tau
    
    # --- H2H features (3) ---
    before = f.get('date', '2026-06-14')
    h2h = compute_h2h(conn, f.get('home_team', ''), f.get('away_team', ''), before)
    f['h2h_home_avg'] = h2h[0]
    f['h2h_away_avg'] = h2h[1]
    f['h2h_confidence'] = h2h[2]
    
    # --- Form strength (from lineups) (2) ---
    hf_def = float(f.get('home_formation_def', 4))
    af_def = float(f.get('away_formation_def', 4))
    # Convert formation to attack/defense rating
    f['home_form_att'] = 5 - hf_def  # more defenders = less attacking
    f['away_form_att'] = 5 - af_def
    
    # --- Interaction features (5) ---
    f['elo_league_home'] = float(f.get('home_elo', 1500)) * f['league_strength']
    f['elo_league_away'] = float(f.get('away_elo', 1500)) * f['league_strength']
    f['form_diff_importance'] = float(f.get('form_diff_sq', 0)) * f['tournament_importance']
    f['rest_diff_importance'] = (float(f.get('home_days_rest', 5)) - float(f.get('away_days_rest', 5))) * f['tournament_importance']
    
    # --- Rolling volatility (2) ---
    f['home_xg_volatility'] = abs(float(f.get('home_xg_for', 1.5)) - float(f.get('home_xg_against', 1.2)))
    f['away_xg_volatility'] = abs(float(f.get('away_xg_for', 1.2)) - float(f.get('away_xg_against', 1.5)))
    
    # --- Form streak (1) ---
    f['home_form_streak'] = float(f.get('home_form', 0.5)) - 0.5  # -0.5 to +0.5
    f['away_form_streak'] = float(f.get('away_form', 0.5)) - 0.5
    
    # --- Match importance interaction (1) ---
    f['importance_elo_product'] = f['tournament_importance'] * abs(float(f.get('elo_diff', 0)))
    
    # --- Shot quality / efficiency (2) — from Nemotron analysis ---
    home_shots = float(f.get('home_shots_for', 10))
    away_shots = float(f.get('away_shots_for', 10))
    home_sot = float(f.get('stat_h_sot', 3))
    away_sot = float(f.get('stat_a_sot', 3))
    f['home_sot_rate'] = home_sot / max(home_shots, 1)  # shots on target %
    f['away_sot_rate'] = away_sot / max(away_shots, 1)
    f['home_goal_conversion'] = float(f.get('home_xg_for', 1.0)) / max(home_shots, 1)  # xG per shot
    f['away_goal_conversion'] = float(f.get('away_xg_for', 0.8)) / max(away_shots, 1)
    
    # --- Form streak quality (2) — winning/losing momentum ---
    f['home_form_direction'] = float(f.get('home_form', 0.5)) * 2 - 1  # -1 to +1
    f['away_form_direction'] = float(f.get('away_form', 0.5)) * 2 - 1
    
    return f

def get_new_feature_names():
    """Return list of new features added by this module"""
    return [
        'league_strength', 'tournament_importance',
    ] + SCORE_PROBS + [
        'h2h_home_avg', 'h2h_away_avg', 'h2h_confidence',
        'home_form_att', 'away_form_att',
        'elo_league_home', 'elo_league_away',
        'form_diff_importance', 'rest_diff_importance',
        'home_xg_volatility', 'away_xg_volatility',
        'home_form_streak', 'away_form_streak',
        'importance_elo_product',
        'home_sot_rate', 'away_sot_rate',
        'home_goal_conversion', 'away_goal_conversion',
        'home_form_direction', 'away_form_direction',
    ]

def preview_league_strength(conn, limit=20):
    """Preview league strength distribution"""
    cur = conn.execute('''
        SELECT tournament, COUNT(*) as cnt
        FROM sofa_historical_results
        GROUP BY tournament ORDER BY cnt DESC LIMIT ?
    ''', (limit,))
    print('League strength preview:')
    for r in cur.fetchall():
        s = get_league_strength(r[0])
        i = get_tournament_importance(r[0])
        print(f'  [{s}][{i}] {r[0]}: {r[1]}')

if __name__ == '__main__':
    conn = sqlite3.connect(DB)
    preview_league_strength(conn)
    print(f'\nTotal new features: {len(get_new_feature_names())}')
    print(f'Total with base: {len(BASE_FEATURES) + len(get_new_feature_names())}')
    conn.close()
