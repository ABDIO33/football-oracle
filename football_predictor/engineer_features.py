"""
engineer_features.py — مهندس البيانات العملاق
يستخرج 500+ ميزة من scrape_cache.db (7.7 GB)
ويحفظها كـ features.npz و features_full.csv

الميزات في 19 مجموعة = 550 ميزة إجمالاً
"""
import sqlite3, os, json, gc, math, time, sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, Counter

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
OUTPUT = os.path.join(os.path.dirname(__file__), 'features_full.npz')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'features_full.csv')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'engineer_features_log.txt')

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# Helpers
def poisson_prob(lam, k):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def dixon_coles_tau(h, a, lam_h=1.0, lam_a=1.0, rho=-0.07):
    if h == 0 and a == 0: return 1.0 - rho * lam_h * lam_a
    if h == 0 and a == 1: return 1.0 + rho * lam_h
    if h == 1 and a == 0: return 1.0 + rho * lam_a
    if h == 1 and a == 1: return 1.0 - rho
    return 1.0

def safe_div(a, b):
    return a / b if abs(b) > 1e-10 else 0.0

def parse_form_raw(form_raw):
    if not form_raw or not isinstance(form_raw, str):
        return 0, 0, 0
    wins = form_raw.count('W')
    draws = form_raw.count('D')
    losses = form_raw.count('L')
    return wins, draws, losses

TOP5 = {'Premier League','Primera Division','Serie A','Bundesliga','Ligue 1','Premier League 2026'}
SECOND = {'Championship','Serie B','Liga Profesional','MLS','Eredivisie','Primeira Liga','J1 League','K League 1','Botola Pro','Super Lig','Jupiler Pro League','Süper Lig'}
THIRD = {'League One','League Two','National League','E1','E2','E3','SP1','SP2'}

def get_league_strength(t):
    if not t: return 1
    if any(c in str(t) for c in ['World Cup','Champions League','Euro','Copa America']): return 5
    if t in TOP5: return 5
    if t in SECOND: return 3
    if t in THIRD: return 2
    if any(c in str(t) for c in ['Cup','Copa','FA Cup','DFB']): return 4
    return 2

def get_importance(t):
    if not t: return 1
    if any(c in str(t) for c in ['World Cup','Champions League']): return 5
    if any(c in str(t) for c in ['Euro','Copa America','Africa Cup']): return 5
    if t in TOP5: return 4
    if any(c in str(t) for c in ['Cup','Europa','Conference']): return 4
    if t in SECOND: return 3
    return 2

FORMATION_DEF_MAP = {}
for form in ['3-4-3','3-5-2','3-4-2-1','3-4-1-2','3-1-4-2','3-4-3-1','3-5-1-1','3-2-4-1','3-6-1']:
    FORMATION_DEF_MAP[form] = 3
for form in ['5-3-2','5-4-1','5-2-3','5-2-2-1','5-3-1-1','5-4-1 diamond','5-4-1']:
    FORMATION_DEF_MAP[form] = 5

log('=' * 70)
log('مهندس البيانات العملاق — 550+ Feature Extraction Engine')
log('=' * 70)

t_start = time.time()

# ═══════════════════════════════════════════════════════════
# PHASE 0: Load all data
# ═══════════════════════════════════════════════════════════

log('PHASE 0: Loading all data from database...')
conn = sqlite3.connect(DB)

# 0a. Main matches with walkforward state
log('Loading matches...')
df = pd.read_sql_query('''
    SELECT r.id, r.home_team, r.away_team, r.home_score, r.away_score,
           r.date, r.tournament, r.start_timestamp,
           r.status_type, r.unique_tournament_id, r.season_id,
           wf_h.elo as home_elo, wf_a.elo as away_elo,
           wf_h.rolling_xg_for as home_xg_for, wf_h.rolling_xg_against as home_xg_against,
           wf_a.rolling_xg_for as away_xg_for, wf_a.rolling_xg_against as away_xg_against,
           wf_h.form_points as home_form, wf_a.form_points as away_form,
           wf_h.matches_played as home_matches_played, wf_a.matches_played as away_matches_played,
           wf_h.rolling_shots_for as home_shots_for, wf_a.rolling_shots_for as away_shots_for,
           wf_h.rolling_shots_against as home_shots_against, wf_a.rolling_shots_against as away_shots_against,
           wf_h.form_raw as home_form_raw, wf_a.form_raw as away_form_raw
    FROM sofa_historical_results r
    JOIN walkforward_state wf_h ON r.home_team = wf_h.team_name AND r.date = wf_h.date
    JOIN walkforward_state wf_a ON r.away_team = wf_a.team_name AND r.date = wf_a.date
    WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL
      AND r.home_score >= 0 AND r.away_score >= 0
      AND r.status_type = 'finished'
    ORDER BY r.start_timestamp
''', conn)
n = len(df)
if n == 0:
    log('ERROR: No matches loaded!')
    conn.close()
    sys.exit(1)
log(f'Loaded {n:,} matches')

# Target variables
df['home_score_c'] = df['home_score'].fillna(0).clip(0, 4).astype(int)
df['away_score_c'] = df['away_score'].fillna(0).clip(0, 4).astype(int)
df['score_class'] = df['home_score_c'] * 5 + df['away_score_c']
df['home_win'] = (df['home_score'] > df['away_score']).astype(float)
df['draw'] = (df['home_score'] == df['away_score']).astype(float)
df['away_win'] = (df['home_score'] < df['away_score']).astype(float)

# 0b. Match stats
log('Loading match stats...')
stats_dict = {}
cur = conn.execute('SELECT event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot, home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls FROM sofa_match_stats')
for row in cur.fetchall():
    stats_dict[row[0]] = row[1:]
log(f'Loaded {len(stats_dict):,} stats')

# 0c. Lineups
log('Loading lineups...')
lineups_dict = {}
cur = conn.execute('SELECT event_id, home_formation, away_formation, confirmed FROM sofa_lineups')
for row in cur.fetchall():
    lineups_dict[row[0]] = row[1:]
log(f'Loaded {len(lineups_dict):,} lineups')

# 0d. Glicko
log('Loading Glicko...')
glicko_dict = {}
cur = conn.execute('SELECT team_name, date, glicko_rating, glicko_rd, glicko_vol, matches_played FROM glicko_state')
for row in cur.fetchall():
    glicko_dict[(row[0], row[1])] = (row[2] or 1500, row[3] or 350, row[4] or 0.06, row[5] or 0)
log(f'Loaded {len(glicko_dict):,} glicko')

# 0e. Poisson params
log('Loading Poisson params...')
poisson_map = {}
cur = conn.execute('SELECT team_name, tournament, attack_strength_home, attack_strength_away, defense_strength_home, defense_strength_away, lambda_home_scored, lambda_home_conceded, lambda_away_scored, lambda_away_conceded FROM neg_poisson_params')
for row in cur.fetchall():
    poisson_map[(row[0], row[1])] = row[2:]
log(f'Loaded {len(poisson_map):,} poisson params')

# 0f. H2H
log('Loading H2H...')
h2h_map = {}
cur = conn.execute('SELECT home_team, away_team, total_matches, avg_home_goals, avg_away_goals, home_win_pct, draw_pct, away_win_pct, home_goals_total, away_goals_total FROM neg_h2h_features')
for row in cur.fetchall():
    h2h_map[(row[0], row[1])] = row[2:]
log(f'Loaded {len(h2h_map):,} H2H')

# 0g. Team strength
log('Loading team strength...')
strength_map = {}
cur = conn.execute('SELECT team_name, tournament, total_home, home_wins, home_draws, home_losses, home_goals_for, home_goals_against, total_away, away_wins, away_draws, away_losses, away_goals_for, away_goals_against, home_strength, overall_gd_per_game FROM neg_team_strength')
for row in cur.fetchall():
    strength_map[(row[0], row[1])] = row[2:]
log(f'Loaded {len(strength_map):,} strength')

# 0h. Streaks
log('Loading streaks...')
streak_map = {}
cur = conn.execute('SELECT team_name, tournament, current_streak_type, current_streak_len, longest_win_streak, longest_draw_streak, longest_loss_streak, last_5_results, last_10_results FROM neg_streaks')
for row in cur.fetchall():
    streak_map[(row[0], row[1])] = row[2:]
log(f'Loaded {len(streak_map):,} streaks')

# 0i. League averages
log('Loading league averages...')
league_avg_map = {}
cur = conn.execute('SELECT tournament, avg_home_goals, avg_away_goals, avg_total_goals, home_win_pct, draw_pct, away_win_pct, home_goals_std, away_goals_std, poisson_lambda_home, poisson_lambda_away FROM neg_league_averages')
for row in cur.fetchall():
    league_avg_map[row[0]] = row[1:]
log(f'Loaded {len(league_avg_map):,} league averages')

# 0j. Team ratings
log('Loading team ratings...')
ratings_map = {}
cur = conn.execute('SELECT team_name, rating_mu, rating_sigma FROM team_ratings')
for row in cur.fetchall():
    ratings_map[row[0]] = (row[1] or 0, row[2] or 1)
log(f'Loaded {len(ratings_map):,} ratings')

# 0k. Venue & weather
log('Loading venues...')
venue_map = {}
cur = conn.execute('SELECT team_name, lat, lon, venue_name, city FROM team_venue')
for row in cur.fetchall():
    venue_map[row[0]] = (row[1], row[2])
log(f'Loaded {len(venue_map):,} venues')

log('Loading weather...')
weather_map = {}
cur = conn.execute('SELECT date, lat, lon, temp_max, temp_min, precip, wind, humidity FROM venue_weather')
for row in cur.fetchall():
    weather_map[(str(row[0]), float(row[1]), float(row[2]))] = row[3:]
log(f'Loaded {len(weather_map):,} weather')

# 0l. Player impact agg
log('Loading player impact...')
impact_agg = {}
cur = conn.execute('SELECT team_name, AVG(impact_attack), AVG(impact_defense), COUNT(*), SUM(CASE WHEN impact_attack>0.5 THEN 1 ELSE 0 END), SUM(CASE WHEN impact_defense>0.5 THEN 1 ELSE 0 END) FROM player_impact GROUP BY team_name')
for row in cur.fetchall():
    impact_agg[row[0]] = row[1:]
log(f'Loaded {len(impact_agg):,} impacts')

# 0m. Team core
log('Loading team core...')
core_agg = {}
cur = conn.execute('SELECT team_name, COUNT(*), AVG(start_rate), SUM(CASE WHEN position="G" THEN 1 ELSE 0 END), SUM(CASE WHEN position="D" THEN 1 ELSE 0 END), SUM(CASE WHEN position="M" THEN 1 ELSE 0 END), SUM(CASE WHEN position="F" THEN 1 ELSE 0 END), AVG(impact_attack), AVG(impact_defense) FROM team_core GROUP BY team_name')
for row in cur.fetchall():
    core_agg[row[0]] = row[1:]
log(f'Loaded {len(core_agg):,} cores')

# 0n. Referee
log('Loading referees...')
ref_map = {}
cur = conn.execute('SELECT id, games, yellow_cards*1.0/NULLIF(games,0), red_cards*1.0/NULLIF(games,0) FROM sofa_referee')
for row in cur.fetchall():
    ref_map[row[0]] = (row[1] or 0, row[2] or 4.0, row[3] or 0.15)
log(f'Loaded {len(ref_map):,} referees')

ref_assign_map = {}
cur = conn.execute('SELECT match_id, referee_id FROM sofa_referee_assignments')
for row in cur.fetchall():
    ref_assign_map[row[0]] = row[1]
log(f'Loaded {len(ref_assign_map):,} assignments')

# 0o. Forebet
log('Loading forebet...')
forebet_map = {}
cur = conn.execute('SELECT match_key, date, home_team, away_team, prob_h, prob_d, prob_a FROM forebet_predictions')
for row in cur.fetchall():
    forebet_map[(str(row[2]).strip(), str(row[3]).strip(), str(row[1])[:10])] = (row[4] or 0, row[5] or 0, row[6] or 0)
log(f'Loaded {len(forebet_map):,} forebet')

# 0p. Odds
log('Loading odds...')
odds_map = {}
cur = conn.execute('SELECT fd.date, fd.home_team, fd.away_team, fd.b365h, fd.b365d, fd.b365a, fd.avgh, fd.avgd, fd.avga, fd.maxh, fd.maxd, fd.maxa, tm.sofa_name, tma.sofa_name FROM football_data_matches fd LEFT JOIN team_name_mapping tm ON fd.home_team=tm.fd_name LEFT JOIN team_name_mapping tma ON fd.away_team=tma.fd_name WHERE fd.b365h IS NOT NULL AND fd.b365h>0')
for row in cur.fetchall():
    if row[12] and row[13]:
        odds_map[(str(row[12]).strip(), str(row[13]).strip(), str(row[0])[:10])] = row[3:12]
log(f'Loaded {len(odds_map):,} odds')

# 0q. StatsBomb shot aggregates
log('Loading StatsBomb shot data...')
sb_shot_agg = {}
cur = conn.execute("SELECT e.team, COUNT(*), SUM(CASE WHEN e.outcome='Goal' THEN 1 ELSE 0 END), AVG(e.xg), SUM(e.xg), AVG(e.x), AVG(e.y), AVG(CASE WHEN e.outcome='Goal' THEN e.xg ELSE NULL END) FROM statsbomb_events e WHERE e.event_type='Shot' GROUP BY e.team")
for row in cur.fetchall():
    sb_shot_agg[row[0]] = row[1:]
log(f'Loaded {len(sb_shot_agg):,} shot aggregates')

conn.close()
log(f'All data loaded in {time.time()-t_start:.0f}s')
log('=' * 70)

# ═══════════════════════════════════════════════════════════
# PHASE 1: Build pre-computed arrays for speed
# ═══════════════════════════════════════════════════════════

log('PHASE 1: Pre-computing date/time features and rest days...')

months = np.zeros(n)
days_of_week = np.zeros(n)
season_progress = np.zeros(n)
is_weekend = np.zeros(n)
day_of_season = np.zeros(n)
season_year = np.zeros(n)
is_early = np.zeros(n)
is_late = np.zeros(n)

rest_days_h = np.full(n, 7.0)
rest_days_a = np.full(n, 7.0)
last_match = {}

for idx in range(n):
    dt_str = str(df.iloc[idx]['date'])[:10]
    ht = str(df.iloc[idx]['home_team'])
    at = str(df.iloc[idx]['away_team'])
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d')
        months[idx] = dt.month
        days_of_week[idx] = dt.weekday()
        is_weekend[idx] = 1.0 if dt.weekday() >= 5 else 0.0
        ss = datetime(dt.year, 8, 1)
        se = datetime(dt.year + 1, 7, 31)
        dos = (dt - ss).days
        season_progress[idx] = max(0, min(1, dos / max((se - ss).days, 1)))
        day_of_season[idx] = dos
        season_year[idx] = dt.year if dt.month >= 8 else dt.year - 1
        is_early[idx] = 1.0 if season_progress[idx] < 0.25 else 0.0
        is_late[idx] = 1.0 if season_progress[idx] >= 0.75 else 0.0
        
        if ht in last_match:
            rest_days_h[idx] = (dt - last_match[ht]).days
        if at in last_match:
            rest_days_a[idx] = (dt - last_match[at]).days
        last_match[ht] = dt
        last_match[at] = dt
    except:
        pass

log('Pre-computing match density...')
team_date_list = defaultdict(list)
for idx in range(n):
    dt_str = str(df.iloc[idx]['date'])[:10]
    try:
        dt = datetime.strptime(dt_str, '%Y-%m-%d')
    except:
        continue
    team_date_list[df.iloc[idx]['home_team']].append((idx, dt))
    team_date_list[df.iloc[idx]['away_team']].append((idx, dt))

for team in team_date_list:
    team_date_list[team].sort(key=lambda x: x[1])

match_density_3 = np.zeros(n)
match_density_7 = np.zeros(n)
match_density_14 = np.zeros(n)

for team, td_list in team_date_list.items():
    for pos, (idx, dt) in enumerate(td_list):
        c3 = c7 = c14 = 0
        for j in range(pos - 1, -1, -1):
            delta = (dt - td_list[j][1]).days
            if delta <= 14:
                c14 += 1
                if delta <= 7:
                    c7 += 1
                    if delta <= 3:
                        c3 += 1
            else:
                break
        match_density_3[idx] += c3
        match_density_7[idx] += c7
        match_density_14[idx] += c14

log(f'Pre-computation done in {time.time()-t_start:.0f}s')

# ═══════════════════════════════════════════════════════════
# PHASE 2: Define and build all features
# ═══════════════════════════════════════════════════════════

log('PHASE 2: Building 550 features...')

# Allocate big matrix
FEATURES = []
n_feat_est = 570  # room to grow
fmat = np.zeros((n, n_feat_est), dtype=np.float32)

def FEAT(name):
    """Register a new feature name and return its index"""
    idx = len(FEATURES)
    FEATURES.append(name)
    return idx

# ─── GROUP 1: BASE (85 features, indices 0-84) ───
log('  Group 1/19: Base features...')

g1 = {
    'home_elo': FEAT('home_elo'),
    'away_elo': FEAT('away_elo'),
    'elo_diff': FEAT('elo_diff'),
    'home_xg_for': FEAT('home_xg_for'),
    'home_xg_against': FEAT('home_xg_against'),
    'away_xg_for': FEAT('away_xg_for'),
    'away_xg_against': FEAT('away_xg_against'),
    'home_form': FEAT('home_form'),
    'away_form': FEAT('away_form'),
    'home_matches_played': FEAT('home_matches_played'),
    'away_matches_played': FEAT('away_matches_played'),
    'home_shots_for': FEAT('home_shots_for'),
    'away_shots_for': FEAT('away_shots_for'),
    'home_shots_against': FEAT('home_shots_against'),
    'away_shots_against': FEAT('away_shots_against'),
    'home_xg_diff': FEAT('home_xg_diff'),
    'away_xg_diff': FEAT('away_xg_diff'),
    'home_shot_diff': FEAT('home_shot_diff'),
    'away_shot_diff': FEAT('away_shot_diff'),
    'home_days_rest': FEAT('home_days_rest'),
    'away_days_rest': FEAT('away_days_rest'),
    'forebet_prob_h': FEAT('forebet_prob_h'),
    'forebet_prob_d': FEAT('forebet_prob_d'),
    'forebet_prob_a': FEAT('forebet_prob_a'),
    'forebet_available': FEAT('forebet_available'),
    'home_glicko': FEAT('home_glicko'),
    'away_glicko': FEAT('away_glicko'),
    'home_glicko_rd': FEAT('home_glicko_rd'),
    'away_glicko_rd': FEAT('away_glicko_rd'),
    'stat_h_xg': FEAT('stat_h_xg'),
    'stat_a_xg': FEAT('stat_a_xg'),
    'stat_h_shots': FEAT('stat_h_shots'),
    'stat_a_shots': FEAT('stat_a_shots'),
    'stat_h_sot': FEAT('stat_h_sot'),
    'stat_a_sot': FEAT('stat_a_sot'),
    'stat_h_possession': FEAT('stat_h_possession'),
    'stat_a_possession': FEAT('stat_a_possession'),
    'stat_h_corners': FEAT('stat_h_corners'),
    'stat_a_corners': FEAT('stat_a_corners'),
    'stat_h_fouls': FEAT('stat_h_fouls'),
    'stat_a_fouls': FEAT('stat_a_fouls'),
    'home_formation_def': FEAT('home_formation_def'),
    'away_formation_def': FEAT('away_formation_def'),
    'formation_diff': FEAT('formation_diff'),
    'has_lineups': FEAT('has_lineups'),
    'home_missing_core': FEAT('home_missing_core'),
    'away_missing_core': FEAT('away_missing_core'),
    'home_att_loss': FEAT('home_att_loss'),
    'away_att_loss': FEAT('away_att_loss'),
    'home_def_loss': FEAT('home_def_loss'),
    'away_def_loss': FEAT('away_def_loss'),
    'odds_b365h': FEAT('odds_b365h'),
    'odds_b365d': FEAT('odds_b365d'),
    'odds_b365a': FEAT('odds_b365a'),
    'odds_avgh': FEAT('odds_avgh'),
    'odds_avgd': FEAT('odds_avgd'),
    'odds_avga': FEAT('odds_avga'),
    'elo_form_home': FEAT('elo_form_home'),
    'elo_form_away': FEAT('elo_form_away'),
    'elo_xg_home': FEAT('elo_xg_home'),
    'elo_xg_away': FEAT('elo_xg_away'),
    'form_xg_home': FEAT('form_xg_home'),
    'form_xg_away': FEAT('form_xg_away'),
    'elo_diff_form_diff': FEAT('elo_diff_form_diff'),
    'fatigue_home': FEAT('fatigue_home'),
    'fatigue_away': FEAT('fatigue_away'),
    'xg_ratio': FEAT('xg_ratio'),
    'shots_ratio': FEAT('shots_ratio'),
    'form_ratio': FEAT('form_ratio'),
    'xgf_xga_ratio_home': FEAT('xgf_xga_ratio_home'),
    'xgf_xga_ratio_away': FEAT('xgf_xga_ratio_away'),
    'shot_eff_home': FEAT('shot_eff_home'),
    'shot_eff_away': FEAT('shot_eff_away'),
    'elo_diff_sq': FEAT('elo_diff_sq'),
    'xg_diff_sq': FEAT('xg_diff_sq'),
    'form_diff_sq': FEAT('form_diff_sq'),
    'month': FEAT('month'),
    'day_of_week': FEAT('day_of_week'),
    'season_progress': FEAT('season_progress'),
    'is_weekend': FEAT('is_weekend'),
    'home_temp': FEAT('home_temp'),
    'home_precip': FEAT('home_precip'),
    'home_wind': FEAT('home_wind'),
    'home_humidity': FEAT('home_humidity'),
    'travel_distance': FEAT('travel_distance'),
}

# ─── GROUP 2: POISSON V3 (25 features, indices 85-109) ───
log('  Group 2/19: Poisson V3...')
g2 = {}
for hg in range(5):
    for ag in range(5):
        g2[f'poisson_p{hg}_{ag}'] = FEAT(f'poisson_p{hg}_{ag}')

# ─── GROUP 3: LEAGUE CONTEXT (10 features, indices 110-119) ───
log('  Group 3/19: League context...')
g3 = {name: FEAT(name) for name in [
    'league_strength', 'tournament_importance', 'league_strength_diff',
    'importance_x_strength', 'match_importance_index',
    'is_group_stage', 'is_knockout', 'is_promotion_battle',
    'is_relegation_battle', 'tournament_round_depth',
]}

# ─── GROUP 4: H2H ADVANCED (12 features, indices 120-131) ───
log('  Group 4/19: H2H advanced...')
g4 = {name: FEAT(name) for name in [
    'h2h_home_avg', 'h2h_away_avg', 'h2h_confidence',
    'h2h_recency_home', 'h2h_recency_away', 'h2h_recency_draw',
    'h2h_recency_strength', 'h2h_total_goals_avg', 'h2h_home_win_pct',
    'h2h_draw_pct', 'h2h_away_win_pct', 'h2h_goal_diff_avg',
]}

# ─── GROUP 5: REFEREE BIAS (8 features, indices 132-139) ───
log('  Group 5/19: Referee...')
g5 = {name: FEAT(name) for name in [
    'ref_avg_yellow', 'ref_avg_red', 'ref_card_rate',
    'ref_home_win_bias', 'ref_foul_rate_proxy', 'ref_experience',
    'ref_strictness', 'ref_matches_count',
]}

# ─── GROUP 6: WEATHER ADVANCED (10 features, indices 140-149) ───
log('  Group 6/19: Weather...')
g6 = {name: FEAT(name) for name in [
    'temp_min', 'temp_max', 'temp_range', 'temp_avg',
    'precip', 'wind_speed', 'humidity',
    'weather_extreme_precip', 'weather_extreme_wind', 'weather_comfort',
]}

# ─── GROUP 7: PLAYER IMPACT DEEP (15 features, indices 150-164) ───
log('  Group 7/19: Player impact...')
g7 = {name: FEAT(name) for name in [
    'home_att_impact', 'home_def_impact', 'home_tracked_players',
    'home_high_att', 'home_high_def', 'home_att_def_diff',
    'home_core_size', 'home_avg_start_rate',
    'home_core_gk', 'home_core_def', 'home_core_mid', 'home_core_fwd',
    'home_core_balance', 'home_core_att_impact', 'att_impact_diff',
]}

# ─── GROUP 8: FORM/STREAK/MOMENTUM (20 features, indices 165-184) ───
log('  Group 8/19: Form/streak...')
g8 = {name: FEAT(name) for name in [
    'home_win_streak', 'away_win_streak',
    'home_loss_streak', 'away_loss_streak',
    'home_unbeaten_streak', 'away_unbeaten_streak',
    'home_momentum_3', 'away_momentum_3',
    'home_momentum_5', 'away_momentum_5',
    'home_momentum_trend', 'away_momentum_trend',
    'home_form_direction', 'away_form_direction',
    'home_xg_volatility', 'away_xg_volatility',
    'home_draw_rate_recent', 'away_draw_rate_recent',
    'home_win_rate_recent', 'away_win_rate_recent',
]}

# ─── GROUP 9: STATSBOMB SHOT MODELS (25 features, indices 185-209) ───
log('  Group 9/19: StatsBomb...')
g9 = {name: FEAT(name) for name in [
    'sb_total_shots', 'sb_goals', 'sb_saved', 'sb_off_target', 'sb_blocked',
    'sb_shot_conversion', 'sb_avg_xg_per_shot', 'sb_total_xg',
    'sb_avg_shot_x', 'sb_avg_shot_y', 'sb_xg_overperformance',
    'sb_passes', 'sb_duels', 'sb_duel_win_rate',
    'sb_dribbles', 'sb_dribble_success', 'sb_fouls_committed',
    'sb_fouls_won', 'sb_interceptions', 'sb_clearances',
    'sb_shots_diff', 'sb_goals_diff', 'sb_xg_diff',
    'sb_conversion_diff', 'sb_match_shots',
]}

# ─── GROUP 10: GLICKO/ELO COMBINED (10 features, indices 210-219) ───
log('  Group 10/19: Glicko/Elo...')
g10 = {name: FEAT(name) for name in [
    'elo_glicko_home', 'elo_glicko_away', 'elo_glicko_diff',
    'glicko_rd_combined', 'glicko_vol_combined',
    'elo_uncertainty_home', 'elo_uncertainty_away',
    'glicko_below_elo_home', 'glicko_below_elo_away', 'team_strength_rating',
]}

# ─── GROUP 11: EFFICIENCY RATIOS (15 features, indices 220-234) ───
log('  Group 11/19: Efficiency...')
g11 = {name: FEAT(name) for name in [
    'home_xg_per_shot', 'away_xg_per_shot',
    'home_goal_per_xg', 'away_goal_per_xg',
    'home_sot_rate', 'away_sot_rate',
    'home_goal_conversion', 'away_goal_conversion',
    'goal_efficiency_diff',
    'home_xg_consistency', 'away_xg_consistency', 'xg_consistency_diff',
    'home_form_efficiency', 'away_form_efficiency', 'strength_x_efficiency',
]}

# ─── GROUP 12: POLYNOMIAL/SQRT/LOG (50 features, indices 235-284) ───
log('  Group 12/19: Polynomial...')
g12 = {name: FEAT(name) for name in [
    'elo_diff_cubed', 'elo_diff_sqrt', 'elo_diff_logabs',
    'home_elo_sq', 'away_elo_sq', 'elo_diff_cuberoot',
    'xg_ratio_sq', 'xg_ratio_sqrt', 'xg_ratio_log',
    'home_xg_sq', 'away_xg_sq', 'home_xg_log', 'away_xg_log',
    'form_ratio_sq', 'form_ratio_sqrt',
    'home_form_sq', 'away_form_sq', 'form_diff_cubed',
    'shots_ratio_sq', 'shots_ratio_sqrt', 'home_shot_sq', 'away_shot_sq',
    'rest_diff_sq', 'rest_diff_sqrt', 'home_rest_sq', 'away_rest_sq',
    'elo_xg_home_sq', 'elo_xg_away_sq', 'form_xg_home_sq', 'form_xg_away_sq',
    'possession_diff_sq', 'possession_diff_sqrt',
    'home_poss_sq', 'away_poss_sq',
    'possession_logit_home', 'possession_logit_away',
    'travel_distance_sq', 'travel_distance_sqrt', 'travel_distance_log',
    'xg_product', 'xg_product_sqrt',
    'elo_product', 'elo_product_sqrt',
    'form_product', 'form_product_sqrt',
    'odds_implied_h', 'odds_implied_d', 'odds_implied_a',
    'implied_margin', 'odds_ratio_hd',
]}

# ─── GROUP 13: INTERACTIONS (120 features, indices 285-404) ───
log('  Group 13/19: Interactions...')
g13 = {name: FEAT(name) for name in [
    'elo_x_home_xg', 'elo_x_away_xg',
    'elo_x_home_form', 'elo_x_away_form',
    'elo_x_home_rest', 'elo_x_away_rest',
    'elo_x_league_str', 'elo_x_importance',
    'elo_x_travel', 'elo_x_ref_exp',
    'home_elo_x_home_xg', 'away_elo_x_away_xg',
    'home_elo_x_home_form', 'away_elo_x_away_form',
    'home_elo_x_poss', 'away_elo_x_poss',
    'home_elo_x_league', 'away_elo_x_league',
    'elo_x_home_mom5', 'elo_x_away_mom5',
    'elo_x_home_att_imp', 'elo_x_away_def_imp_proxy',
    'home_elo_x_glicko', 'away_elo_x_glicko',
    'elo_x_home_shot_eff', 'elo_x_away_shot_eff',
    'elo_x_home_goal_conv', 'elo_x_away_goal_conv',
    'home_elo_x_sot_rate', 'away_elo_x_sot_rate',
    'xg_diff_x_home_form', 'xg_diff_x_away_form',
    'xg_diff_x_league', 'xg_diff_x_importance',
    'xg_diff_x_travel', 'xg_diff_x_ref_foul',
    'home_xg_x_rest', 'away_xg_x_rest',
    'home_xg_x_mom5', 'away_xg_x_mom5',
    'home_xg_x_att_imp', 'away_xg_x_def_imp_proxy',
    'xg_ratio_x_form_home', 'xg_ratio_x_form_away',
    'xg_ratio_x_league', 'xg_ratio_x_importance',
    'home_xg_x_poss', 'away_xg_x_poss',
    'home_xg_x_sot_rate', 'away_xg_x_sot_rate',
    'home_xg_x_goal_conv', 'away_xg_x_goal_conv',
    'xg_diff_x_win_streak_h', 'xg_diff_x_win_streak_a',
    'home_xg_x_form_att', 'away_xg_x_form_att',
    'xg_ratio_x_shot_eff_h', 'xg_ratio_x_shot_eff_a',
    'home_xg_x_core_size', 'away_xg_x_core_size',
    'form_diff_x_league', 'form_diff_x_importance',
    'form_diff_x_travel', 'form_diff_x_comfort',
    'home_form_x_rest', 'away_form_x_rest',
    'home_form_x_mom5', 'away_form_x_mom5',
    'home_form_x_poss', 'away_form_x_poss',
    'home_form_x_sot_rate', 'away_form_x_sot_rate',
    'home_form_x_core', 'away_form_x_core',
    'form_ratio_x_league', 'form_ratio_x_importance',
    'home_form_x_att_imp', 'away_form_x_def_imp_proxy',
    'home_form_x_win_streak', 'away_form_x_win_streak',
    'home_form_x_glicko', 'away_form_x_glicko',
    'form_diff_x_mom_trend_h', 'form_diff_x_mom_trend_a',
    'form_diff_x_form_eff',
    'rest_diff_x_league', 'rest_diff_x_importance',
    'rest_diff_x_travel', 'rest_diff_x_form_home',
    'rest_diff_x_form_away', 'rest_diff_x_mom5_home',
    'rest_diff_x_mom5_away',
    'home_rest_x_matches', 'away_rest_x_matches',
    'home_rest_x_density', 'away_rest_x_density',
    'rest_diff_x_win_streak_h', 'rest_diff_x_win_streak_a',
    'home_rest_x_glicko_rd', 'away_rest_x_glicko_rd',
    'temp_x_poss_home', 'temp_x_poss_away',
    'precip_x_form_home', 'precip_x_form_away',
    'wind_x_shot_eff_h', 'wind_x_shot_eff_a',
    'humidity_x_goal_h', 'humidity_x_goal_a',
    'temp_range_x_elo_h', 'temp_range_x_elo_a',
    'comfort_x_form_home', 'comfort_x_form_away',
    'temp_x_league', 'precip_x_league',
    'wind_x_importance', 'extreme_x_form_home',
    'extreme_x_form_away', 'temp_x_travel',
    'precip_x_travel', 'wind_x_elo_diff',
]}

# ─── GROUP 14: LEAGUE SPECIFIC (30 features, indices 405-434) ───
log('  Group 14/19: League specific...')
g14 = {name: FEAT(name) for name in [
    'league_avg_h_goals', 'league_avg_a_goals', 'league_avg_total',
    'league_h_win_pct', 'league_draw_pct', 'league_a_win_pct',
    'league_goal_var', 'league_lambda_h', 'league_lambda_a',
    'home_better_att_vs_league', 'away_better_att_vs_league',
    'home_better_def_vs_league', 'away_better_def_vs_league',
    'league_strength_pair', 'league_tier_pair',
    'tourn_familiarity_home', 'tourn_familiarity_away',
    'home_goal_diff_vs_league', 'away_goal_diff_vs_league',
    'is_top5', 'is_cup', 'is_international',
    'is_derby_proxy', 'same_country',
    'is_league_match', 'is_cup_match',
    'season_games_remaining', 'season_phase_start',
    'season_phase_mid', 'season_phase_end',
]}

# ─── GROUP 15: TIME SEASON CYCLE (15 features, indices 435-449) ───
log('  Group 15/19: Time/season...')
g15 = {name: FEAT(name) for name in [
    'days_since_season_start', 'match_density_7days', 'match_density_3days',
    'match_density_14days', 'home_midweek', 'away_midweek',
    'month_sin', 'month_cos', 'dayofweek_sin', 'dayofweek_cos',
    'is_early_season', 'is_late_season', 'season_year',
    'rest_advantage', 'total_density',
]}

# ─── GROUP 16: TEAM STRENGTH COMPOSITE (30 features, indices 450-479) ───
log('  Group 16/19: Team strength...')
g16 = {name: FEAT(name) for name in [
    'home_total_home', 'home_home_wins', 'home_home_draws', 'home_home_losses',
    'home_home_gd', 'home_total_away', 'home_away_wins', 'home_away_losses',
    'home_away_gd', 'home_strength', 'home_gd_per_game',
    'away_total_home', 'away_away_wins', 'away_away_draws', 'away_away_losses',
    'away_away_gd', 'away_away_win_rate', 'away_strength', 'away_gd_per_game',
    'strength_diff', 'home_streak_type', 'away_streak_type',
    'home_curr_streak_len', 'away_curr_streak_len',
    'home_max_win_streak', 'away_max_win_streak',
    'home_max_loss_streak', 'away_max_loss_streak',
    'home_last5_wins', 'away_last5_wins',
]}

# ─── GROUP 17: MARKET ODDS IMPLIED (15 features, indices 480-494) ───
log('  Group 17/19: Market odds...')
g17 = {name: FEAT(name) for name in [
    'implied_h_prob', 'implied_d_prob', 'implied_a_prob',
    'book_margin', 'norm_h_prob', 'norm_d_prob', 'norm_a_prob',
    'odds_hd_ratio', 'odds_ha_ratio', 'odds_da_ratio',
    'max_vs_avg_h', 'max_vs_avg_d', 'max_vs_avg_a',
    'odds_home_adv', 'odds_exp_goals',
]}

# ─── GROUP 18: DEFENSIVE/OFFENSIVE PATTERNS (20 features, indices 495-514) ───
log('  Group 18/19: Def/Off patterns...')
g18 = {name: FEAT(name) for name in [
    'home_cs_prob', 'away_cs_prob', 'home_btsp', 'away_btsp',
    'poisson_diag_inflation', 'poisson_under_over',
    'home_late_goal_ratio', 'away_late_goal_ratio',
    'home_early_goal_ratio', 'away_early_goal_ratio',
    'home_def_solidity', 'away_def_solidity',
    'home_off_fluidity', 'away_off_fluidity',
    'match_openness', 'exp_cards',
    'style_diff', 'home_form_att', 'away_form_att', 'form_att_power_diff',
]}

# ─── GROUP 19: BONUS ADVANCED (35 features, indices 515-549) ───
log('  Group 19/19: Bonus advanced...')
g19 = {name: FEAT(name) for name in [
    'elo_form_home_norm', 'elo_form_away_norm',
    'momentum_elo_home', 'momentum_elo_away',
    'fatigue_index_home', 'fatigue_index_away',
    'team_value_diff', 'stability_diff',
    'home_att_loss_rate', 'away_att_loss_rate',
    'home_def_loss_rate', 'away_def_loss_rate',
    'core_missing_home', 'core_missing_away',
    'home_adv_composite', 'away_adv_composite',
    'match_symmetry',
    'form_wins_home', 'form_draws_home', 'form_losses_home',
    'form_wins_away', 'form_draws_away', 'form_losses_away',
    'form_pts_home', 'form_pts_away',
    'form_str_home', 'form_str_away',
    'h2h_recency_trend',
    'form_elo_interact_home', 'form_elo_interact_away',
    'xg_form_combined_home', 'xg_form_combined_away',
    'poisson_both_cs', 'poisson_btts', 'h2h_strength_rating',
]}

n_features = len(FEATURES)
log(f'Total features: {n_features}')

# Trim matrix
fmat = fmat[:, :n_features]

# ═══════════════════════════════════════════════════════════
# PHASE 3: Fill all features for each match
# ═══════════════════════════════════════════════════════════

log('PHASE 3: Computing features for all matches...')
t_phase3 = time.time()

for idx in range(n):
    if idx % 50000 == 0 and idx > 0:
        elapsed = time.time() - t_phase3
        rate = idx / elapsed
        remaining = (n - idx) / rate
        log(f'  Row {idx:,}/{n:,} ({idx*100/n:.0f}%) ~{remaining:.0f}s remaining')
    
    r = df.iloc[idx]
    f = fmat[idx]
    
    # ── Parse match data ──
    home_elo = float(r['home_elo']) if pd.notna(r['home_elo']) else 1500
    away_elo = float(r['away_elo']) if pd.notna(r['away_elo']) else 1500
    home_xg_f = float(r['home_xg_for']) if pd.notna(r['home_xg_for']) else 1.2
    home_xg_a = float(r['home_xg_against']) if pd.notna(r['home_xg_against']) else 1.0
    away_xg_f = float(r['away_xg_for']) if pd.notna(r['away_xg_for']) else 1.0
    away_xg_a = float(r['away_xg_against']) if pd.notna(r['away_xg_against']) else 1.2
    home_form = float(r['home_form']) if pd.notna(r['home_form']) else 0.5
    away_form = float(r['away_form']) if pd.notna(r['away_form']) else 0.5
    home_matches = float(r['home_matches_played']) if pd.notna(r['home_matches_played']) else 0
    away_matches = float(r['away_matches_played']) if pd.notna(r['away_matches_played']) else 0
    home_shots_f = float(r['home_shots_for']) if pd.notna(r['home_shots_for']) else 10
    away_shots_f = float(r['away_shots_for']) if pd.notna(r['away_shots_for']) else 10
    home_shots_a = float(r['home_shots_against']) if pd.notna(r['home_shots_against']) else 10
    away_shots_a = float(r['away_shots_against']) if pd.notna(r['away_shots_against']) else 10
    
    elo_diff = home_elo - away_elo
    match_id = int(r['id'])
    ht = str(r['home_team'])
    at = str(r['away_team'])
    dt_str = str(r['date'])[:10]
    tourn = str(r['tournament']) if pd.notna(r['tournament']) else ''
    home_xg_diff = home_xg_f - home_xg_a
    away_xg_diff = away_xg_f - away_xg_a
    home_shot_diff = home_shots_f - home_shots_a
    away_shot_diff = away_shots_f - away_shots_a
    
    league_str = get_league_strength(tourn)
    imp = get_importance(tourn)
    rest_h = rest_days_h[idx]
    rest_a = rest_days_a[idx]
    month = months[idx]
    dow = days_of_week[idx]
    
    # ═══ GROUP 1: Base features ═══
    f[g1['home_elo']] = home_elo
    f[g1['away_elo']] = away_elo
    f[g1['elo_diff']] = elo_diff
    f[g1['home_xg_for']] = home_xg_f
    f[g1['home_xg_against']] = home_xg_a
    f[g1['away_xg_for']] = away_xg_f
    f[g1['away_xg_against']] = away_xg_a
    f[g1['home_form']] = home_form
    f[g1['away_form']] = away_form
    f[g1['home_matches_played']] = home_matches
    f[g1['away_matches_played']] = away_matches
    f[g1['home_shots_for']] = home_shots_f
    f[g1['away_shots_for']] = away_shots_f
    f[g1['home_shots_against']] = home_shots_a
    f[g1['away_shots_against']] = away_shots_a
    f[g1['home_xg_diff']] = home_xg_diff
    f[g1['away_xg_diff']] = away_xg_diff
    f[g1['home_shot_diff']] = home_shot_diff
    f[g1['away_shot_diff']] = away_shot_diff
    f[g1['home_days_rest']] = rest_h
    f[g1['away_days_rest']] = rest_a
    f[g1['month']] = month
    f[g1['day_of_week']] = dow
    f[g1['season_progress']] = season_progress[idx]
    f[g1['is_weekend']] = is_weekend[idx]
    
    # ── Interaction features ──
    f[g1['elo_form_home']] = home_form * home_elo / 1500
    f[g1['elo_form_away']] = away_form * away_elo / 1500
    f[g1['elo_xg_home']] = home_xg_f * home_elo / 1500
    f[g1['elo_xg_away']] = away_xg_f * away_elo / 1500
    f[g1['form_xg_home']] = home_form * home_xg_f
    f[g1['form_xg_away']] = away_form * away_xg_f
    f[g1['elo_diff_form_diff']] = elo_diff * (home_form - away_form)
    f[g1['fatigue_home']] = (7 - min(home_matches, 7)) / 7
    f[g1['fatigue_away']] = (7 - min(away_matches, 7)) / 7
    f[g1['xg_ratio']] = safe_div(home_xg_f, max(away_xg_a, 0.1))
    f[g1['shots_ratio']] = safe_div(home_shots_f, max(away_shots_a, 1))
    f[g1['form_ratio']] = safe_div(home_form, max(away_form, 0.01))
    f[g1['xgf_xga_ratio_home']] = safe_div(home_xg_f, max(home_xg_a, 0.1))
    f[g1['xgf_xga_ratio_away']] = safe_div(away_xg_f, max(away_xg_a, 0.1))
    f[g1['shot_eff_home']] = safe_div(home_xg_f, max(home_shots_f, 1))
    f[g1['shot_eff_away']] = safe_div(away_xg_f, max(away_shots_f, 1))
    f[g1['elo_diff_sq']] = elo_diff ** 2
    f[g1['xg_diff_sq']] = (home_xg_f - away_xg_a) ** 2
    f[g1['form_diff_sq']] = (home_form - away_form) ** 2
    
    # ── Match Stats ──
    stat_h_xg = stat_a_xg = 0.0
    stat_h_shots = stat_a_shots = 0.0
    stat_h_sot = stat_a_sot = 0.0
    stat_h_poss = stat_a_poss = 50.0
    stat_h_corners = stat_a_corners = 0.0
    stat_h_fouls = stat_a_fouls = 0.0
    
    if match_id in stats_dict:
        s = stats_dict[match_id]
        stat_h_xg = float(s[0] or 0) if s[0] is not None else 0
        stat_a_xg = float(s[1] or 0) if s[1] is not None else 0
        stat_h_shots = float(s[2] or 0) if s[2] is not None else 0
        stat_a_shots = float(s[3] or 0) if s[3] is not None else 0
        stat_h_sot = float(s[4] or 0) if s[4] is not None else 0
        stat_a_sot = float(s[5] or 0) if s[5] is not None else 0
        stat_h_poss = float(s[6] or 50) if s[6] is not None else 50
        stat_a_poss = float(s[7] or 50) if s[7] is not None else 50
        stat_h_corners = float(s[8] or 0) if s[8] is not None else 0
        stat_a_corners = float(s[9] or 0) if s[9] is not None else 0
        stat_h_fouls = float(s[10] or 0) if s[10] is not None else 0
        stat_a_fouls = float(s[11] or 0) if s[11] is not None else 0
    
    f[g1['stat_h_xg']] = stat_h_xg
    f[g1['stat_a_xg']] = stat_a_xg
    f[g1['stat_h_shots']] = stat_h_shots
    f[g1['stat_a_shots']] = stat_a_shots
    f[g1['stat_h_sot']] = stat_h_sot
    f[g1['stat_a_sot']] = stat_a_sot
    f[g1['stat_h_possession']] = stat_h_poss
    f[g1['stat_a_possession']] = stat_a_poss
    f[g1['stat_h_corners']] = stat_h_corners
    f[g1['stat_a_corners']] = stat_a_corners
    f[g1['stat_h_fouls']] = stat_h_fouls
    f[g1['stat_a_fouls']] = stat_a_fouls
    
    # ── Formations ──
    h_formation = 4
    a_formation = 4
    has_lu = 0
    if match_id in lineups_dict:
        lu = lineups_dict[match_id]
        hf = str(lu[0]) if lu[0] else ''
        af = str(lu[1]) if lu[1] else ''
        h_formation = float(FORMATION_DEF_MAP.get(hf, 4))
        a_formation = float(FORMATION_DEF_MAP.get(af, 4))
        has_lu = 1.0 if (hf or af) else 0
    f[g1['home_formation_def']] = h_formation
    f[g1['away_formation_def']] = a_formation
    f[g1['formation_diff']] = h_formation - a_formation
    f[g1['has_lineups']] = has_lu
    
    # ── Forebet ──
    fore_key = (ht, at, dt_str)
    if fore_key in forebet_map:
        fb = forebet_map[fore_key]
        f[g1['forebet_prob_h']] = float(fb[0] or 0) / 100
        f[g1['forebet_prob_d']] = float(fb[1] or 0) / 100
        f[g1['forebet_prob_a']] = float(fb[2] or 0) / 100
        f[g1['forebet_available']] = 1.0
    
    # ── Glicko ──
    home_glicko = 1500; away_glicko = 1500
    home_glicko_rd = 350; away_glicko_rd = 350
    if (ht, dt_str) in glicko_dict:
        g = glicko_dict[(ht, dt_str)]
        home_glicko = g[0]; home_glicko_rd = g[1]
    if (at, dt_str) in glicko_dict:
        g = glicko_dict[(at, dt_str)]
        away_glicko = g[0]; away_glicko_rd = g[1]
    f[g1['home_glicko']] = home_glicko
    f[g1['away_glicko']] = away_glicko
    f[g1['home_glicko_rd']] = home_glicko_rd
    f[g1['away_glicko_rd']] = away_glicko_rd
    
    # ── Weather ──
    home_lat = None; home_lon = None
    if ht in venue_map:
        v = venue_map[ht]
        home_lat = v[0]; home_lon = v[1]
    
    temp = 15.0; precip = 0.0; wind = 10.0; humidity = 60.0
    temp_min = 10.0; temp_max = 15.0
    
    if home_lat is not None and home_lon is not None:
        wkey = (dt_str, float(home_lat), float(home_lon))
        if wkey in weather_map:
            w = weather_map[wkey]
            temp_max = float(w[0] or 15); temp_min = float(w[1] or 10)
            precip = float(w[2] or 0); wind = float(w[3] or 10); humidity = float(w[4] or 60)
            temp = temp_max
    
    f[g1['home_temp']] = temp
    f[g1['home_precip']] = precip
    f[g1['home_wind']] = wind
    f[g1['home_humidity']] = humidity
    
    # ── Travel distance ──
    travel = 0.0
    if home_lat is not None and at in venue_map:
        av = venue_map[at]
        away_lat = av[0]; away_lon = av[1]
        if away_lat is not None and away_lon is not None:
            from math import radians, sin, cos, sqrt, asin
            lat1, lon1 = radians(float(home_lat)), radians(float(home_lon))
            lat2, lon2 = radians(float(away_lat)), radians(float(away_lon))
            dlat, dlon = lat2 - lat1, lon2 - lon1
            ha = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(min(1, ha)))
            travel = 6371 * c
    f[g1['travel_distance']] = travel
    
    # ── Market odds ──
    odds_h = odds_d = odds_a = 0.0
    odds_avgh = odds_avgd = odds_avga = 0.0
    odds_key = (ht, at, dt_str)
    if odds_key in odds_map:
        od = odds_map[odds_key]
        odds_h = float(od[0] or 0); odds_d = float(od[1] or 0); odds_a = float(od[2] or 0)
        odds_avgh = float(od[3] or 0); odds_avgd = float(od[4] or 0); odds_avga = float(od[5] or 0)
    f[g1['odds_b365h']] = odds_h
    f[g1['odds_b365d']] = odds_d
    f[g1['odds_b365a']] = odds_a
    f[g1['odds_avgh']] = odds_avgh
    f[g1['odds_avgd']] = odds_avgd
    f[g1['odds_avga']] = odds_avga
    
    # ── Missing core (from lineups - not available in this simplified version) ──
    for key in ['home_missing_core', 'away_missing_core', 'home_att_loss', 'away_att_loss', 'home_def_loss', 'away_def_loss']:
        f[g1[key]] = 0.0
    
    # ═══ GROUP 2: Poisson V3 ═══
    lam_h = max(0.05, home_xg_f * away_xg_a * 1.08 * math.exp(elo_diff * 0.0003) * (1 + (imp - 3) * 0.03))
    lam_a = max(0.05, away_xg_f * home_xg_a * math.exp(-elo_diff * 0.0003) * (1 + (imp - 3) * 0.03))
    
    for hg in range(5):
        for ag in range(5):
            p_h = poisson_prob(lam_h, hg)
            p_a = poisson_prob(lam_a, ag)
            tau = dixon_coles_tau(hg, ag, lam_h, lam_a, -0.07)
            f[g2[f'poisson_p{hg}_{ag}']] = p_h * p_a * tau
    
    # ═══ GROUP 3: League context ═══
    is_cup = any(c in tourn for c in ['Cup','Champions','Europa','World Cup','Euro','Copa','FA Cup','DFB'])
    is_group = is_cup and month in [9,10,11,2,3]
    is_ko = is_cup and month in [3,4,5]
    is_prom = (tourn in SECOND and month >= 3)
    is_rel = (month >= 3 and month <= 5)
    
    f[g3['league_strength']] = league_str
    f[g3['tournament_importance']] = imp
    f[g3['league_strength_diff']] = 0.0
    f[g3['importance_x_strength']] = imp * league_str
    f[g3['match_importance_index']] = imp * (1.3 if is_ko else 1.0)
    f[g3['is_group_stage']] = 1.0 if is_group else 0.0
    f[g3['is_knockout']] = 1.0 if is_ko else 0.0
    f[g3['is_promotion_battle']] = 1.0 if is_prom else 0.0
    f[g3['is_relegation_battle']] = 1.0 if is_rel else 0.0
    f[g3['tournament_round_depth']] = float(imp)
    
    # ═══ GROUP 4: H2H ═══
    h2h_key = (ht, at)
    if h2h_key in h2h_map:
        hh = h2h_map[h2h_key]
        total_m = int(hh[0] or 0)
        avg_hg = float(hh[1] or 0); avg_ag = float(hh[2] or 0)
        hpct = float(hh[3] or 0); dpct = float(hh[4] or 0); apct = float(hh[5] or 0)
        hg_total = float(hh[6] or 0); ag_total = float(hh[7] or 0)
        f[g4['h2h_home_avg']] = avg_hg
        f[g4['h2h_away_avg']] = avg_ag
        f[g4['h2h_confidence']] = min(1.0, total_m / 5)
        f[g4['h2h_recency_home']] = avg_hg / max(avg_hg + avg_ag, 0.1)
        f[g4['h2h_recency_away']] = avg_ag / max(avg_hg + avg_ag, 0.1)
        f[g4['h2h_recency_draw']] = dpct / 100
        f[g4['h2h_recency_strength']] = min(1.0, total_m / 10)
        f[g4['h2h_total_goals_avg']] = avg_hg + avg_ag
        f[g4['h2h_home_win_pct']] = hpct / 100
        f[g4['h2h_draw_pct']] = dpct / 100
        f[g4['h2h_away_win_pct']] = apct / 100
        f[g4['h2h_goal_diff_avg']] = avg_hg - avg_ag
    
    # ═══ GROUP 5: Referee ═══
    ref_id = ref_assign_map.get(match_id, None)
    if ref_id and ref_id in ref_map:
        rf = ref_map[ref_id]
        games, avg_y, avg_r = rf
        f[g5['ref_avg_yellow']] = avg_y
        f[g5['ref_avg_red']] = avg_r
        f[g5['ref_card_rate']] = (avg_y + 3 * avg_r) / 10
        f[g5['ref_home_win_bias']] = 0.45
        f[g5['ref_foul_rate_proxy']] = avg_y / 8
        f[g5['ref_experience']] = min(1.0, games / 500)
        f[g5['ref_strictness']] = avg_y * 0.25 + avg_r
        f[g5['ref_matches_count']] = float(games)
    
    # ═══ GROUP 6: Weather advanced ═══
    f[g6['temp_min']] = temp_min
    f[g6['temp_max']] = temp_max
    f[g6['temp_range']] = temp_max - temp_min
    f[g6['temp_avg']] = (temp_max + temp_min) / 2
    f[g6['precip']] = precip
    f[g6['wind_speed']] = wind
    f[g6['humidity']] = humidity
    f[g6['weather_extreme_precip']] = 1.0 if precip > 5 else 0.0
    f[g6['weather_extreme_wind']] = 1.0 if wind > 30 else 0.0
    comfort = 0.5
    if temp_max > 30: comfort -= 0.15
    elif temp_max < 5: comfort -= 0.1
    if precip > 3: comfort -= 0.1
    if wind > 25: comfort -= 0.1
    f[g6['weather_comfort']] = max(0, comfort)
    
    # ═══ GROUP 7: Player impact ═══
    if ht in impact_agg:
        ia = impact_agg[ht]
        f[g7['home_att_impact']] = float(ia[0] or 0)
        f[g7['home_def_impact']] = float(ia[1] or 0)
        f[g7['home_tracked_players']] = float(ia[2] or 0)
        f[g7['home_high_att']] = float(ia[3] or 0)
        f[g7['home_high_def']] = float(ia[4] or 0)
        f[g7['home_att_def_diff']] = float(ia[0] or 0) - float(ia[1] or 0)
    if ht in core_agg:
        ca = core_agg[ht]
        f[g7['home_core_size']] = float(ca[0] or 0)
        f[g7['home_avg_start_rate']] = float(ca[1] or 0.5)
        f[g7['home_core_gk']] = float(ca[2] or 0)
        f[g7['home_core_def']] = float(ca[3] or 0)
        f[g7['home_core_mid']] = float(ca[4] or 0)
        f[g7['home_core_fwd']] = float(ca[5] or 0)
        total_pos = max(1, float(ca[2] or 0) + float(ca[3] or 0) + float(ca[4] or 0) + float(ca[5] or 0))
        f[g7['home_core_balance']] = (float(ca[3] or 0) * 0.25 + float(ca[4] or 0) * 0.5 + float(ca[5] or 0) * 0.75) / total_pos
        f[g7['home_core_att_impact']] = float(ca[7] or 0)
    
    if at in impact_agg:
        ia = impact_agg[at]
        f[g7['att_impact_diff']] = f[g7['home_att_impact']] - float(ia[0] or 0)
    
    # ═══ GROUP 8: Form/Streak ═══
    tourn_key = (ht, tourn) if tourn else None
    if tourn_key and tourn_key in streak_map:
        sk = streak_map[tourn_key]
        st = str(sk[0] or '')
        sl = float(sk[1] or 0)
        f[g8['home_win_streak']] = sl if st == 'W' else 0
        f[g8['home_loss_streak']] = sl if st == 'L' else 0
        f[g8['home_unbeaten_streak']] = 0 if st == 'L' else sl
        # max win/loss streaks are in g16
        l5 = str(sk[6] or '')
        f[g8['home_win_rate_recent']] = l5.count('W') / max(len(l5), 1)
        f[g8['home_draw_rate_recent']] = l5.count('D') / max(len(l5), 1)
    
    atourn_key = (at, tourn) if tourn else None
    if atourn_key and atourn_key in streak_map:
        sk = streak_map[atourn_key]
        st = str(sk[0] or '')
        sl = float(sk[1] or 0)
        f[g8['away_win_streak']] = sl if st == 'W' else 0
        f[g8['away_loss_streak']] = sl if st == 'L' else 0
        f[g8['away_unbeaten_streak']] = 0 if st == 'L' else sl
        l5 = str(sk[6] or '')
        f[g8['away_win_rate_recent']] = l5.count('W') / max(len(l5), 1)
        f[g8['away_draw_rate_recent']] = l5.count('D') / max(len(l5), 1)
    
    # Momentum proxy
    f[g8['home_momentum_3']] = home_form
    f[g8['away_momentum_3']] = away_form
    f[g8['home_momentum_5']] = home_form
    f[g8['away_momentum_5']] = away_form
    f[g8['home_momentum_trend']] = 0.0
    f[g8['away_momentum_trend']] = 0.0
    f[g8['home_form_direction']] = home_form * 2 - 1
    f[g8['away_form_direction']] = away_form * 2 - 1
    f[g8['home_xg_volatility']] = abs(home_xg_f - home_xg_a)
    f[g8['away_xg_volatility']] = abs(away_xg_f - away_xg_a)
    
    # ═══ GROUP 9: StatsBomb ═══
    if ht in sb_shot_agg:
        sb = sb_shot_agg[ht]
        f[g9['sb_total_shots']] = float(sb[0] or 0)
        f[g9['sb_goals']] = float(sb[1] or 0)
        f[g9['sb_avg_xg_per_shot']] = float(sb[3] or 0)
        f[g9['sb_total_xg']] = float(sb[4] or 0)
        f[g9['sb_avg_shot_x']] = float(sb[5] or 0)
        f[g9['sb_avg_shot_y']] = float(sb[6] or 0)
        f[g9['sb_xg_overperformance']] = safe_div(float(sb[1] or 0), max(float(sb[4] or 0.01), 0.01))
        f[g9['sb_shot_conversion']] = safe_div(float(sb[1] or 0), max(float(sb[0] or 1), 1))
    
    # ═══ GROUP 10: Glicko/Elo ═══
    f[g10['elo_glicko_home']] = home_elo * home_glicko / 1500
    f[g10['elo_glicko_away']] = away_elo * away_glicko / 1500
    f[g10['elo_glicko_diff']] = (home_elo * home_glicko - away_elo * away_glicko) / 1500
    f[g10['glicko_rd_combined']] = home_glicko_rd + away_glicko_rd
    f[g10['glicko_vol_combined']] = 300.0
    f[g10['elo_uncertainty_home']] = safe_div(home_glicko_rd, max(home_elo, 1))
    f[g10['elo_uncertainty_away']] = safe_div(away_glicko_rd, max(away_elo, 1))
    f[g10['glicko_below_elo_home']] = 1.0 if home_glicko < home_elo else 0.0
    f[g10['glicko_below_elo_away']] = 1.0 if away_glicko < away_elo else 0.0
    if ht in ratings_map:
        f[g10['team_strength_rating']] = float(ratings_map[ht][0] or 0)
    
    # ═══ GROUP 11: Efficiency ═══
    f[g11['home_xg_per_shot']] = safe_div(home_xg_f, max(home_shots_f, 1))
    f[g11['away_xg_per_shot']] = safe_div(away_xg_f, max(away_shots_f, 1))
    f[g11['home_goal_per_xg']] = safe_div(home_xg_f, max(home_xg_f + home_xg_a, 0.01))
    f[g11['away_goal_per_xg']] = safe_div(away_xg_f, max(away_xg_f + away_xg_a, 0.01))
    f[g11['home_sot_rate']] = safe_div(stat_h_sot, max(stat_h_shots, 1))
    f[g11['away_sot_rate']] = safe_div(stat_a_sot, max(stat_a_shots, 1))
    f[g11['home_goal_conversion']] = safe_div(home_xg_f, max(home_shots_f, 1))
    f[g11['away_goal_conversion']] = safe_div(away_xg_f, max(away_shots_f, 1))
    f[g11['goal_efficiency_diff']] = f[g11['home_goal_per_xg']] - f[g11['away_goal_per_xg']]
    f[g11['home_xg_consistency']] = abs(home_xg_f - home_xg_a)
    f[g11['away_xg_consistency']] = abs(away_xg_f - away_xg_a)
    f[g11['xg_consistency_diff']] = f[g11['home_xg_consistency']] - f[g11['away_xg_consistency']]
    f[g11['home_form_efficiency']] = home_form * f[g11['home_sot_rate']]
    f[g11['away_form_efficiency']] = away_form * f[g11['away_sot_rate']]
    f[g11['strength_x_efficiency']] = league_str * f[g11['home_xg_per_shot']]
    
    # ═══ GROUP 12: Polynomial ═══
    f[g12['elo_diff_cubed']] = elo_diff ** 3
    f[g12['elo_diff_sqrt']] = math.sqrt(abs(elo_diff)) * (-1 if elo_diff < 0 else 1)
    f[g12['elo_diff_logabs']] = math.log1p(abs(elo_diff)) * (-1 if elo_diff < 0 else 1)
    f[g12['home_elo_sq']] = home_elo ** 2
    f[g12['away_elo_sq']] = away_elo ** 2
    f[g12['elo_diff_cuberoot']] = abs(elo_diff) ** (1/3) * (-1 if elo_diff < 0 else 1)
    
    xg_r = safe_div(home_xg_f, max(away_xg_a, 0.01))
    f[g12['xg_ratio_sq']] = xg_r ** 2
    f[g12['xg_ratio_sqrt']] = math.sqrt(xg_r)
    f[g12['xg_ratio_log']] = math.log1p(xg_r)
    f[g12['home_xg_sq']] = home_xg_f ** 2
    f[g12['away_xg_sq']] = away_xg_a ** 2
    f[g12['home_xg_log']] = math.log1p(home_xg_f)
    f[g12['away_xg_log']] = math.log1p(away_xg_f)
    
    form_r = safe_div(home_form, max(away_form, 0.01))
    f[g12['form_ratio_sq']] = form_r ** 2
    f[g12['form_ratio_sqrt']] = math.sqrt(form_r)
    f[g12['home_form_sq']] = home_form ** 2
    f[g12['away_form_sq']] = away_form ** 2
    f[g12['form_diff_cubed']] = (home_form - away_form) ** 3
    
    sr = safe_div(home_shots_f, max(away_shots_a, 1))
    f[g12['shots_ratio_sq']] = sr ** 2
    f[g12['shots_ratio_sqrt']] = math.sqrt(sr)
    f[g12['home_shot_sq']] = home_shots_f ** 2
    f[g12['away_shot_sq']] = away_shots_a ** 2
    
    rd = rest_h - rest_a
    f[g12['rest_diff_sq']] = rd ** 2
    f[g12['rest_diff_sqrt']] = math.sqrt(abs(rd))
    f[g12['home_rest_sq']] = rest_h ** 2
    f[g12['away_rest_sq']] = rest_a ** 2
    
    f[g12['elo_xg_home_sq']] = (home_elo * home_xg_f / 1500) ** 2
    f[g12['elo_xg_away_sq']] = (away_elo * away_xg_f / 1500) ** 2
    f[g12['form_xg_home_sq']] = (home_form * home_xg_f) ** 2
    f[g12['form_xg_away_sq']] = (away_form * away_xg_f) ** 2
    
    poss_diff = stat_h_poss - stat_a_poss
    f[g12['possession_diff_sq']] = poss_diff ** 2
    f[g12['possession_diff_sqrt']] = math.sqrt(abs(poss_diff))
    f[g12['home_poss_sq']] = stat_h_poss ** 2
    f[g12['away_poss_sq']] = stat_a_poss ** 2
    f[g12['possession_logit_home']] = math.log(stat_h_poss / max(100 - stat_h_poss, 0.1))
    f[g12['possession_logit_away']] = math.log(stat_a_poss / max(100 - stat_a_poss, 0.1))
    
    f[g12['travel_distance_sq']] = travel ** 2
    f[g12['travel_distance_sqrt']] = math.sqrt(travel + 1)
    f[g12['travel_distance_log']] = math.log1p(travel)
    
    f[g12['xg_product']] = home_xg_f * away_xg_f
    f[g12['xg_product_sqrt']] = math.sqrt(home_xg_f * away_xg_f)
    f[g12['elo_product']] = home_elo * away_elo
    f[g12['elo_product_sqrt']] = math.sqrt(home_elo * away_elo)
    f[g12['form_product']] = home_form * away_form
    f[g12['form_product_sqrt']] = math.sqrt(home_form * away_form)
    
    if odds_h > 0 and odds_d > 0 and odds_a > 0:
        inv_h = 1.0 / odds_h; inv_d = 1.0 / odds_d; inv_a = 1.0 / odds_a
        margin = inv_h + inv_d + inv_a
        f[g12['odds_implied_h']] = inv_h
        f[g12['odds_implied_d']] = inv_d
        f[g12['odds_implied_a']] = inv_a
        f[g12['implied_margin']] = margin - 1.0
        f[g12['odds_ratio_hd']] = safe_div(inv_h, max(inv_d, 0.001))
    
    # ═══ GROUP 13: Interactions ═══
    interactions = {
        'elo_x_home_xg': elo_diff * home_xg_f,
        'elo_x_away_xg': elo_diff * away_xg_f,
        'elo_x_home_form': elo_diff * home_form,
        'elo_x_away_form': elo_diff * away_form,
        'elo_x_home_rest': elo_diff * rest_h,
        'elo_x_away_rest': elo_diff * rest_a,
        'elo_x_league_str': elo_diff * league_str,
        'elo_x_importance': elo_diff * imp,
        'elo_x_travel': elo_diff * travel,
        'elo_x_ref_exp': elo_diff * f[g5.get('ref_experience', 0)],
        'home_elo_x_home_xg': home_elo * home_xg_f,
        'away_elo_x_away_xg': away_elo * away_xg_f,
        'home_elo_x_home_form': home_elo * home_form,
        'away_elo_x_away_form': away_elo * away_form,
        'home_elo_x_poss': home_elo * stat_h_poss,
        'away_elo_x_poss': away_elo * stat_a_poss,
        'home_elo_x_league': home_elo * league_str,
        'away_elo_x_league': away_elo * league_str,
        'elo_x_home_mom5': elo_diff * f[g8.get('home_momentum_5', 0)],
        'elo_x_away_mom5': elo_diff * f[g8.get('away_momentum_5', 0)],
        'elo_x_home_att_imp': elo_diff * f[g7.get('home_att_impact', 0)],
        'elo_x_away_def_imp_proxy': elo_diff * (f[g5.get('ref_strictness', 0)]),
        'home_elo_x_glicko': home_elo * home_glicko,
        'away_elo_x_glicko': away_elo * away_glicko,
        'elo_x_home_shot_eff': elo_diff * f[g11.get('home_xg_per_shot', 0)],
        'elo_x_away_shot_eff': elo_diff * f[g11.get('away_xg_per_shot', 0)],
        'elo_x_home_goal_conv': elo_diff * f[g11.get('home_goal_conversion', 0)],
        'elo_x_away_goal_conv': elo_diff * f[g11.get('away_goal_conversion', 0)],
        'home_elo_x_sot_rate': home_elo * f[g11.get('home_sot_rate', 0)],
        'away_elo_x_sot_rate': away_elo * f[g11.get('away_sot_rate', 0)],
        # XG interactions
        'xg_diff_x_home_form': (home_xg_diff - away_xg_diff) * home_form,
        'xg_diff_x_away_form': (home_xg_diff - away_xg_diff) * away_form,
        'xg_diff_x_league': (home_xg_diff - away_xg_diff) * league_str,
        'xg_diff_x_importance': (home_xg_diff - away_xg_diff) * imp,
        'xg_diff_x_travel': (home_xg_diff - away_xg_diff) * travel,
        'xg_diff_x_ref_foul': (home_xg_diff - away_xg_diff) * f[g5.get('ref_foul_rate_proxy', 0)],
        'home_xg_x_rest': home_xg_f * rest_h,
        'away_xg_x_rest': away_xg_f * rest_a,
        'home_xg_x_mom5': home_xg_f * f[g8.get('home_momentum_5', 0)],
        'away_xg_x_mom5': away_xg_f * f[g8.get('away_momentum_5', 0)],
        'home_xg_x_att_imp': home_xg_f * f[g7.get('home_att_impact', 0)],
        'away_xg_x_def_imp_proxy': away_xg_f * (f[g5.get('ref_strictness', 0)]),
        'xg_ratio_x_form_home': xg_r * home_form,
        'xg_ratio_x_form_away': xg_r * away_form,
        'xg_ratio_x_league': xg_r * league_str,
        'xg_ratio_x_importance': xg_r * imp,
        'home_xg_x_poss': home_xg_f * stat_h_poss,
        'away_xg_x_poss': away_xg_f * stat_a_poss,
        'home_xg_x_sot_rate': home_xg_f * f[g11.get('home_sot_rate', 0)],
        'away_xg_x_sot_rate': away_xg_f * f[g11.get('away_sot_rate', 0)],
        'home_xg_x_goal_conv': home_xg_f * f[g11.get('home_goal_conversion', 0)],
        'away_xg_x_goal_conv': away_xg_f * f[g11.get('away_goal_conversion', 0)],
        # Form interactions
        'form_diff_x_league': (home_form - away_form) * league_str,
        'form_diff_x_importance': (home_form - away_form) * imp,
        'form_diff_x_travel': (home_form - away_form) * travel,
        'form_diff_x_comfort': (home_form - away_form) * f[g6.get('weather_comfort', 0)],
        'home_form_x_rest': home_form * rest_h,
        'away_form_x_rest': away_form * rest_a,
        'home_form_x_mom5': home_form * f[g8.get('home_momentum_5', 0)],
        'away_form_x_mom5': away_form * f[g8.get('away_momentum_5', 0)],
        'home_form_x_poss': home_form * stat_h_poss,
        'away_form_x_poss': away_form * stat_a_poss,
        'home_form_x_sot_rate': home_form * f[g11.get('home_sot_rate', 0)],
        'away_form_x_sot_rate': away_form * f[g11.get('away_sot_rate', 0)],
        'home_form_x_core': home_form * f[g7.get('home_core_size', 0)],
        'away_form_x_core': away_form * f[g7.get('home_core_size', 0)],
        'form_ratio_x_league': form_r * league_str,
        'form_ratio_x_importance': form_r * imp,
        'home_form_x_att_imp': home_form * f[g7.get('home_att_impact', 0)],
        'away_form_x_def_imp_proxy': away_form * (f[g5.get('ref_strictness', 0)]),
        'home_form_x_win_streak': home_form * f[g8.get('home_win_streak', 0)],
        'away_form_x_win_streak': away_form * f[g8.get('away_win_streak', 0)],
        'home_form_x_glicko': home_form * home_glicko,
        'away_form_x_glicko': away_form * away_glicko,
        'form_diff_x_mom_trend_h': (home_form - away_form) * f[g8.get('home_momentum_trend', 0)],
        'form_diff_x_mom_trend_a': (home_form - away_form) * f[g8.get('away_momentum_trend', 0)],
        'form_diff_x_form_eff': (home_form - away_form) * f[g11.get('home_form_efficiency', 0)],
        # Rest interactions
        'rest_diff_x_league': rd * league_str,
        'rest_diff_x_importance': rd * imp,
        'rest_diff_x_travel': rd * travel,
        'rest_diff_x_form_home': rd * home_form,
        'rest_diff_x_form_away': rd * away_form,
        'rest_diff_x_mom5_home': rd * f[g8.get('home_momentum_5', 0)],
        'rest_diff_x_mom5_away': rd * f[g8.get('away_momentum_5', 0)],
        'home_rest_x_matches': rest_h * home_matches,
        'away_rest_x_matches': rest_a * away_matches,
        'home_rest_x_density': rest_h * match_density_7[idx],
        'away_rest_x_density': rest_a * match_density_7[idx],
        'rest_diff_x_win_streak_h': rd * f[g8.get('home_win_streak', 0)],
        'rest_diff_x_win_streak_a': rd * f[g8.get('away_win_streak', 0)],
        'home_rest_x_glicko_rd': rest_h * home_glicko_rd,
        'away_rest_x_glicko_rd': rest_a * away_glicko_rd,
        # Weather interactions
        'temp_x_poss_home': temp * stat_h_poss / 100,
        'temp_x_poss_away': temp * stat_a_poss / 100,
        'precip_x_form_home': precip * home_form,
        'precip_x_form_away': precip * away_form,
        'wind_x_shot_eff_h': wind * f[g11.get('home_xg_per_shot', 0)],
        'wind_x_shot_eff_a': wind * f[g11.get('away_xg_per_shot', 0)],
        'humidity_x_goal_h': humidity * f[g11.get('home_goal_conversion', 0)],
        'humidity_x_goal_a': humidity * f[g11.get('away_goal_conversion', 0)],
        'temp_range_x_elo_h': (temp_max - temp_min) * home_elo,
        'temp_range_x_elo_a': (temp_max - temp_min) * away_elo,
        'comfort_x_form_home': f[g6.get('weather_comfort', 0)] * home_form,
        'comfort_x_form_away': f[g6.get('weather_comfort', 0)] * away_form,
        'temp_x_league': temp * league_str,
        'precip_x_league': precip * league_str,
        'wind_x_importance': wind * imp,
        'extreme_x_form_home': f[g6.get('weather_extreme_precip', 0)] * home_form,
        'extreme_x_form_away': f[g6.get('weather_extreme_precip', 0)] * away_form,
        'temp_x_travel': temp * travel,
        'precip_x_travel': precip * travel,
        'wind_x_elo_diff': wind * elo_diff,
    }
    for name, val in interactions.items():
        if name in g13:
            f[g13[name]] = val
    
    # ═══ GROUP 14: League specific ═══
    if tourn in league_avg_map:
        la = league_avg_map[tourn]
        avg_h_goals = float(la[0] or 1.4)
        avg_a_goals = float(la[1] or 1.2)
        avg_total = float(la[2] or 2.6)
        h_win_pct = float(la[3] or 45) / 100
        d_pct = float(la[4] or 25) / 100
        a_win_pct = float(la[5] or 30) / 100
        h_std = float(la[6] or 1.2)
        a_std = float(la[7] or 1.2)
        lam_league_h = float(la[8] or 1.4)
        lam_league_a = float(la[9] or 1.2)
        
        f[g14['league_avg_h_goals']] = avg_h_goals
        f[g14['league_avg_a_goals']] = avg_a_goals
        f[g14['league_avg_total']] = avg_total
        f[g14['league_h_win_pct']] = h_win_pct
        f[g14['league_draw_pct']] = d_pct
        f[g14['league_a_win_pct']] = a_win_pct
        f[g14['league_goal_var']] = safe_div(h_std, max(avg_h_goals, 0.1))
        f[g14['league_lambda_h']] = lam_league_h
        f[g14['league_lambda_a']] = lam_league_a
        f[g14['home_better_att_vs_league']] = safe_div(home_xg_f, max(avg_h_goals, 0.1))
        f[g14['away_better_att_vs_league']] = safe_div(away_xg_f, max(avg_a_goals, 0.1))
        f[g14['home_better_def_vs_league']] = safe_div(home_xg_a, max(avg_h_goals, 0.1))
        f[g14['away_better_def_vs_league']] = safe_div(away_xg_a, max(avg_a_goals, 0.1))
        f[g14['home_goal_diff_vs_league']] = home_xg_f - avg_h_goals
        f[g14['away_goal_diff_vs_league']] = away_xg_f - avg_a_goals
    
    f[g14['league_strength_pair']] = league_str
    f[g14['league_tier_pair']] = league_str
    f[g14['tourn_familiarity_home']] = 0.5
    f[g14['tourn_familiarity_away']] = 0.5
    f[g14['is_top5']] = 1.0 if tourn in TOP5 else 0.0
    f[g14['is_cup']] = 1.0 if is_cup else 0.0
    f[g14['is_international']] = 1.0 if any(c in tourn for c in ['World Cup','Euro','Copa America','Africa Cup','Asian Cup']) else 0.0
    f[g14['is_derby_proxy']] = 0.0
    f[g14['same_country']] = 1.0
    f[g14['is_league_match']] = 1.0 if not is_cup else 0.0
    f[g14['is_cup_match']] = 1.0 if is_cup else 0.0
    f[g14['season_games_remaining']] = 1.0 - season_progress[idx]
    f[g14['season_phase_start']] = is_early[idx]
    f[g14['season_phase_mid']] = 1.0 if 0.25 <= season_progress[idx] < 0.65 else 0.0
    f[g14['season_phase_end']] = is_late[idx]
    
    # ═══ GROUP 15: Time ═══
    f[g15['days_since_season_start']] = day_of_season[idx]
    f[g15['match_density_7days']] = match_density_7[idx]
    f[g15['match_density_3days']] = match_density_3[idx]
    f[g15['match_density_14days']] = match_density_14[idx]
    f[g15['home_midweek']] = 1.0 if dow in [1,2,3] else 0.0
    f[g15['away_midweek']] = 1.0 if dow in [1,2,3] else 0.0
    f[g15['month_sin']] = math.sin(2 * math.pi * month / 12)
    f[g15['month_cos']] = math.cos(2 * math.pi * month / 12)
    f[g15['dayofweek_sin']] = math.sin(2 * math.pi * dow / 7)
    f[g15['dayofweek_cos']] = math.cos(2 * math.pi * dow / 7)
    f[g15['is_early_season']] = is_early[idx]
    f[g15['is_late_season']] = is_late[idx]
    f[g15['season_year']] = season_year[idx]
    f[g15['rest_advantage']] = rest_h - rest_a
    f[g15['total_density']] = match_density_7[idx]
    
    # ═══ GROUP 16: Team strength ═══
    if tourn_key and tourn_key in strength_map:
        ts = strength_map[tourn_key]
        f[g16['home_total_home']] = float(ts[0] or 0)
        f[g16['home_home_wins']] = float(ts[1] or 0)
        f[g16['home_home_draws']] = float(ts[2] or 0)
        f[g16['home_home_losses']] = float(ts[3] or 0)
        f[g16['home_home_gd']] = float(ts[4] or 0) - float(ts[5] or 0) if len(ts) > 5 else 0
        f[g16['home_total_away']] = float(ts[6] or 0) if len(ts) > 6 else 0
        f[g16['home_away_wins']] = float(ts[7] or 0) if len(ts) > 7 else 0
        f[g16['home_away_losses']] = float(ts[8] or 0) if len(ts) > 8 else 0
        f[g16['home_away_gd']] = (float(ts[9] or 0) - float(ts[10] or 0)) if len(ts) > 10 else 0
        f[g16['home_strength']] = float(ts[12] or 0) if len(ts) > 12 else 0
        f[g16['home_gd_per_game']] = float(ts[13] or 0) if len(ts) > 13 else 0
    
    if atourn_key and atourn_key in strength_map:
        ts = strength_map[atourn_key]
        f[g16['away_total_home']] = float(ts[0] or 0)
        f[g16['away_away_wins']] = float(ts[7] or 0) if len(ts) > 7 else 0
        f[g16['away_away_draws']] = float(ts[8] or 0) if len(ts) > 8 else 0
        f[g16['away_away_losses']] = float(ts[9] or 0) if len(ts) > 9 else 0
        f[g16['away_away_gd']] = (float(ts[9] or 0) - float(ts[10] or 0)) if len(ts) > 10 else 0
        f[g16['away_away_win_rate']] = safe_div(float(ts[7] or 0), max(float(ts[6] or 1), 1)) if len(ts) > 7 else 0
        f[g16['away_strength']] = float(ts[12] or 0) if len(ts) > 12 else 0
        f[g16['away_gd_per_game']] = float(ts[13] or 0) if len(ts) > 13 else 0
    
    if tourn_key and tourn_key in streak_map:
        sk = streak_map[tourn_key]
        f[g16['home_streak_type']] = 1.0 if str(sk[0] or '') == 'W' else (-1.0 if str(sk[0] or '') == 'L' else 0.0)
        f[g16['home_curr_streak_len']] = float(sk[1] or 0)
        f[g16['home_max_win_streak']] = float(sk[2] or 0) if len(sk) > 2 else 0
        f[g16['home_max_loss_streak']] = float(sk[4] or 0) if len(sk) > 4 else 0
        l5 = str(sk[6] or '') if len(sk) > 6 else ''
        f[g16['home_last5_wins']] = l5.count('W')
    
    if atourn_key and atourn_key in streak_map:
        sk = streak_map[atourn_key]
        f[g16['away_streak_type']] = 1.0 if str(sk[0] or '') == 'W' else (-1.0 if str(sk[0] or '') == 'L' else 0.0)
        f[g16['away_curr_streak_len']] = float(sk[1] or 0)
        f[g16['away_max_win_streak']] = float(sk[2] or 0) if len(sk) > 2 else 0
        f[g16['away_max_loss_streak']] = float(sk[4] or 0) if len(sk) > 4 else 0
        l5 = str(sk[6] or '') if len(sk) > 6 else ''
        f[g16['away_last5_wins']] = l5.count('W')
    
    f[g16['strength_diff']] = f[g16.get('home_strength', 0)] - f[g16.get('away_strength', 0)]
    
    # ═══ GROUP 17: Market odds ═══
    if odds_h > 0 and odds_d > 0 and odds_a > 0:
        inv_h = 1.0 / odds_h; inv_d = 1.0 / odds_d; inv_a = 1.0 / odds_a
        margin = inv_h + inv_d + inv_a
        f[g17['implied_h_prob']] = inv_h
        f[g17['implied_d_prob']] = inv_d
        f[g17['implied_a_prob']] = inv_a
        f[g17['book_margin']] = margin - 1.0
        f[g17['norm_h_prob']] = inv_h / margin
        f[g17['norm_d_prob']] = inv_d / margin
        f[g17['norm_a_prob']] = inv_a / margin
        f[g17['odds_hd_ratio']] = safe_div(inv_h, max(inv_d, 0.001))
        f[g17['odds_ha_ratio']] = safe_div(inv_h, max(inv_a, 0.001))
        f[g17['odds_da_ratio']] = safe_div(inv_d, max(inv_a, 0.001))
        if odds_avgh > 0:
            f[g17['max_vs_avg_h']] = odds_h - odds_avgh
            f[g17['max_vs_avg_d']] = odds_d - odds_avgd
            f[g17['max_vs_avg_a']] = odds_a - odds_avga
        f[g17['odds_home_adv']] = f[g17['norm_h_prob']] - f[g17['norm_a_prob']]
        f[g17['odds_exp_goals']] = (f[g17['norm_h_prob']] + f[g17['norm_d_prob']]/2) + (f[g17['norm_a_prob']] + f[g17['norm_d_prob']]/2)
    
    # ═══ GROUP 18: Def/Off patterns ═══
    f[g18['home_cs_prob']] = poisson_prob(lam_a, 0)
    f[g18['away_cs_prob']] = poisson_prob(lam_h, 0)
    f[g18['home_btsp']] = 1.0 - f[g18['home_cs_prob']]
    f[g18['away_btsp']] = 1.0 - f[g18['away_cs_prob']]
    
    draw_prob_sum = sum(poisson_prob(lam_h, hg) * poisson_prob(lam_a, hg) * dixon_coles_tau(hg, hg, lam_h, lam_a, -0.07) for hg in range(5))
    f[g18['poisson_diag_inflation']] = draw_prob_sum * (1 + (league_str - 3) * 0.05)
    f[g18['poisson_under_over']] = (lam_h + lam_a) / 2.5
    
    f[g18['home_late_goal_ratio']] = 0.5 if stat_h_poss <= 50 else 0.6
    f[g18['away_late_goal_ratio']] = 0.5 if stat_a_poss <= 50 else 0.6
    f[g18['home_early_goal_ratio']] = 0.5
    f[g18['away_early_goal_ratio']] = 0.5
    f[g18['home_def_solidity']] = safe_div(1.0, max(home_xg_a, 0.1))
    f[g18['away_def_solidity']] = safe_div(1.0, max(away_xg_a, 0.1))
    f[g18['home_off_fluidity']] = home_xg_f * max(1, f[g11.get('home_sot_rate', 0.3)])
    f[g18['away_off_fluidity']] = away_xg_f * max(1, f[g11.get('away_sot_rate', 0.3)])
    f[g18['match_openness']] = safe_div(home_xg_f + away_xg_f, max(home_xg_a + away_xg_a, 0.1))
    f[g18['exp_cards']] = (f[g5.get('ref_avg_yellow', 4)] + f[g5.get('ref_avg_red', 0.15)] * 3)
    f[g18['style_diff']] = stat_h_poss - stat_a_poss
    f[g18['home_form_att']] = 5 - h_formation
    f[g18['away_form_att']] = 5 - a_formation
    f[g18['form_att_power_diff']] = (5 - h_formation) - (5 - a_formation)
    
    # ═══ GROUP 19: Bonus ═══
    f[g19['elo_form_home_norm']] = home_form * home_elo / 1500
    f[g19['elo_form_away_norm']] = away_form * away_elo / 1500
    f[g19['momentum_elo_home']] = f[g8.get('home_momentum_5', home_form)] * home_elo / 1500
    f[g19['momentum_elo_away']] = f[g8.get('away_momentum_5', away_form)] * away_elo / 1500
    f[g19['fatigue_index_home']] = safe_div(1, max(home_matches, 1)) * 7
    f[g19['fatigue_index_away']] = safe_div(1, max(away_matches, 1)) * 7
    
    if ht in ratings_map and at in ratings_map:
        f[g19['team_value_diff']] = float(ratings_map[ht][0] or 0) - float(ratings_map[at][0] or 0)
    f[g19['stability_diff']] = abs(f[g19.get('elo_form_home_norm', 0)] - f[g19.get('elo_form_away_norm', 0)])
    f[g19['home_att_loss_rate']] = 0.0
    f[g19['away_att_loss_rate']] = 0.0
    f[g19['home_def_loss_rate']] = 0.0
    f[g19['away_def_loss_rate']] = 0.0
    f[g19['core_missing_home']] = 0.0
    f[g19['core_missing_away']] = 0.0
    f[g19['home_adv_composite']] = (home_elo/1500 + home_xg_f/2 + home_form + stat_h_poss/100) / 4
    f[g19['away_adv_composite']] = (away_elo/1500 + away_xg_f/2 + away_form + stat_a_poss/100) / 4
    f[g19['match_symmetry']] = 1.0 - abs(f[g19['home_adv_composite']] - f[g19['away_adv_composite']])
    
    hfw, hfd, hfl = parse_form_raw(str(r['home_form_raw']) if pd.notna(r['home_form_raw']) else '')
    afw, afd, afl = parse_form_raw(str(r['away_form_raw']) if pd.notna(r['away_form_raw']) else '')
    f[g19['form_wins_home']] = float(hfw)
    f[g19['form_draws_home']] = float(hfd)
    f[g19['form_losses_home']] = float(hfl)
    f[g19['form_wins_away']] = float(afw)
    f[g19['form_draws_away']] = float(afd)
    f[g19['form_losses_away']] = float(afl)
    f[g19['form_pts_home']] = hfw * 3 + hfd
    f[g19['form_pts_away']] = afw * 3 + afd
    f[g19['form_str_home']] = safe_div(float(hfw*3 + hfd), max(5, 1)) / 3
    f[g19['form_str_away']] = safe_div(float(afw*3 + afd), max(5, 1)) / 3
    f[g19['h2h_recency_trend']] = f[g4.get('h2h_home_avg', 0.5)] - f[g4.get('h2h_away_avg', 0.5)]
    f[g19['form_elo_interact_home']] = home_form * home_elo / 1500 * stat_h_poss / 50
    f[g19['form_elo_interact_away']] = away_form * away_elo / 1500 * stat_a_poss / 50
    f[g19['xg_form_combined_home']] = home_xg_f * (0.5 + home_form / 2)
    f[g19['xg_form_combined_away']] = away_xg_f * (0.5 + away_form / 2)
    f[g19['poisson_both_cs']] = f[g18['home_cs_prob']] * f[g18['away_cs_prob']]
    f[g19['poisson_btts']] = (1 - f[g18['home_cs_prob']]) * (1 - f[g18['away_cs_prob']])
    f[g19['h2h_strength_rating']] = f[g4.get('h2h_confidence', 0)] * f[g10.get('team_strength_rating', 0)]

n_features = len(FEATURES)
fmat = fmat[:, :n_features]

t_fill = time.time() - t_phase3
log(f'Features filled in {t_fill:.0f}s ({n/t_fill:.0f} rows/s)')

# ═══════════════════════════════════════════════════════════
# PHASE 4: Clean and Save
# ═══════════════════════════════════════════════════════════

log('PHASE 4: Cleaning NaNs and saving...')

# Clean
fmat = np.nan_to_num(fmat, nan=0.0, posinf=0.0, neginf=0.0)

# Stats
nnz = np.count_nonzero(fmat, axis=0)
log(f'Shape: {fmat.shape[0]:,} x {fmat.shape[1]:,} = {fmat.shape[0]*fmat.shape[1]:,} total values')
log(f'Non-zero per feature: min={nnz.min():,} max={nnz.max():,} avg={nnz.mean():.0f}')

# Save
log(f'Saving as NPZ to {OUTPUT}...')
np.savez_compressed(OUTPUT,
    features=fmat,
    feature_names=FEATURES,
    scores=df['score_class'].values,
    home_score=df['home_score'].values,
    away_score=df['away_score'].values,
    home_win=df['home_win'].values,
    match_ids=df['id'].values,
    dates=df['date'].values)

# Save feature names
names_path = os.path.join(os.path.dirname(__file__), 'feature_names_550.txt')
with open(names_path, 'w', encoding='utf-8') as f:
    for i, name in enumerate(FEATURES):
        f.write(f'{i:3d}: {name}\n')

# CSV sample (first 2000 rows)
log(f'Saving sample CSV to {CSV_PATH}...')
sample_n = min(2000, n)
cols = ['home_team', 'away_team', 'home_score', 'away_score'] + FEATURES
sample_df = pd.DataFrame(index=range(sample_n))
sample_df['home_team'] = df['home_team'].values[:sample_n]
sample_df['away_team'] = df['away_team'].values[:sample_n]
sample_df['home_score'] = df['home_score_c'].values[:sample_n]
sample_df['away_score'] = df['away_score_c'].values[:sample_n]
for i, name in enumerate(FEATURES):
    sample_df[name] = fmat[:sample_n, i]
sample_df.to_csv(CSV_PATH, index=False)

file_size = os.path.getsize(OUTPUT) / 1024 / 1024
t_total = time.time() - t_start

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
log('=' * 70)
log('EXTRACTION COMPLETE')
log('=' * 70)
log(f'  Matches: {n:,}')
log(f'  Features: {n_features}')
log(f'  NPZ file: {OUTPUT} ({file_size:.1f} MB)')
log(f'  CSV sample: {CSV_PATH}')
log(f'  Feature names: {names_path}')
log(f'  Total time: {t_total:.0f}s ({t_total/60:.1f} min)')
log(f'  Speed: {n/t_fill:.0f} rows/s')
log(f'  Memory: {fmat.nbytes/1024/1024:.0f} MB')

log('')
log('  TOP 20 FEATURES BY NON-ZERO COUNT:')
top_feat = np.argsort(nnz)[::-1][:20]
for fi in top_feat:
    log(f'    [{fi:3d}] {FEATURES[fi]:40s} = {nnz[fi]:>8d} ({nnz[fi]/n*100:5.1f}%)')

log('')
log('  FEATURE GROUPS:')
groups = [
    ('G1 Base', 0, 85), ('G2 Poisson', 85, 25), ('G3 League', 110, 10),
    ('G4 H2H', 120, 12), ('G5 Referee', 132, 8), ('G6 Weather', 140, 10),
    ('G7 Player', 150, 15), ('G8 Form', 165, 20), ('G9 StatsBomb', 185, 25),
    ('G10 Glicko', 210, 10), ('G11 Efficiency', 220, 15),
    ('G12 Poly', 235, 50), ('G13 Interact', 285, 120),
    ('G14 League', 405, 30), ('G15 Time', 435, 15),
    ('G16 Strength', 450, 30), ('G17 Odds', 480, 15),
    ('G18 Patterns', 495, 20), ('G19 Bonus', 515, 35),
]
for gname, gstart, gcount in groups:
    if gstart + gcount <= n_features:
        gnnz = nnz[gstart:gstart+gcount]
        log(f'    {gname}: indices {gstart}-{gstart+gcount-1} = {gcount} feats, avg nnz={gnnz.mean():.0f}')

log('')
log('Done!')
print()
print(f'Feature matrix: {n:,} matches x {n_features} features')
print(f'Saved to: {OUTPUT} ({file_size:.1f} MB)')
print(f'Feature names: {names_path}')
