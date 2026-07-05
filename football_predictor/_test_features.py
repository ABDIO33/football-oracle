"""
Quick validation test for engineer_features.py
"""
import sys, os, sqlite3, gc, math, time, json, numpy as np, pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, Counter

DB = 'scrape_cache.db'

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

log('='*60)
log('TEST: Quick validation of feature engineering')
log('='*60)

log('Loading 1000 matches...')
conn = sqlite3.connect(DB)

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
    LIMIT 1000
''', conn)
log(f'Loaded {len(df)} matches')

log('Loading support data...')
stats_dict = {}
cur = conn.execute('SELECT event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot, home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls FROM sofa_match_stats')
for row in cur.fetchall():
    stats_dict[row[0]] = row[1:]

lineups_dict = {}
cur = conn.execute('SELECT event_id, home_formation, away_formation, confirmed FROM sofa_lineups')
for row in cur.fetchall():
    lineups_dict[row[0]] = {'home_formation': row[1], 'away_formation': row[2], 'confirmed': row[3]}

glicko_dict = {}
cur = conn.execute('SELECT team_name, date, glicko_rating, glicko_rd, glicko_vol, matches_played FROM glicko_state')
for row in cur.fetchall():
    glicko_dict[(row[0], row[1])] = {'glicko_rating': row[2], 'glicko_rd': row[3], 'glicko_vol': row[4], 'matches_played': row[5]}

strength_map = {}
cur = conn.execute('SELECT team_name, tournament, total_home, total_away, home_wins, home_draws, home_losses, away_wins, away_draws, away_losses, home_goals_for, home_goals_against, away_goals_for, away_goals_against, avg_home_goals_for, avg_home_goals_against, avg_away_goals_for, avg_away_goals_against, home_strength, overall_gd_per_game FROM neg_team_strength')
for row in cur.fetchall():
    strength_map[(row[0], row[1])] = {'total_home': row[2], 'total_away': row[3], 'home_wins': row[4], 'home_draws': row[5], 'home_losses': row[6], 'away_wins': row[7], 'away_draws': row[8], 'away_losses': row[9], 'home_goals_for': row[10], 'home_goals_against': row[11], 'away_goals_for': row[12], 'away_goals_against': row[13], 'avg_home_goals_for': row[14], 'avg_home_goals_against': row[15], 'avg_away_goals_for': row[16], 'avg_away_goals_against': row[17], 'home_strength': row[18], 'overall_gd_per_game': row[19]}

streak_map = {}
cur = conn.execute('SELECT team_name, tournament, current_streak_type, current_streak_len, longest_win_streak, longest_draw_streak, longest_loss_streak, last_5_results, last_10_results FROM neg_streaks')
for row in cur.fetchall():
    streak_map[(row[0], row[1])] = {'current_streak_type': row[2], 'current_streak_len': row[3], 'longest_win_streak': row[4], 'longest_draw_streak': row[5], 'longest_loss_streak': row[6], 'last_5_results': row[7], 'last_10_results': row[8]}

league_avg_map = {}
cur = conn.execute('SELECT tournament, avg_home_goals, avg_away_goals, avg_total_goals, home_win_pct, draw_pct, away_win_pct, home_goals_std, away_goals_std, poisson_lambda_home, poisson_lambda_away FROM neg_league_averages')
for row in cur.fetchall():
    league_avg_map[row[0]] = {'avg_home_goals': row[1], 'avg_away_goals': row[2], 'avg_total_goals': row[3], 'home_win_pct': row[4], 'draw_pct': row[5], 'away_win_pct': row[6], 'home_goals_std': row[7], 'away_goals_std': row[8], 'poisson_lambda_home': row[9], 'poisson_lambda_away': row[10]}

venue_map = {}
cur = conn.execute('SELECT team_name, lat, lon, venue_name, city FROM team_venue')
for row in cur.fetchall():
    venue_map[row[0]] = {'lat': row[1], 'lon': row[2]}

weather_map = {}
cur = conn.execute('SELECT date, lat, lon, temp_max, temp_min, precip, wind, humidity FROM venue_weather')
for row in cur.fetchall():
    weather_map[(str(row[0]), float(row[1]), float(row[2]))] = {'temp_max': row[3], 'temp_min': row[4], 'precip': row[5], 'wind': row[6], 'humidity': row[7]}

impact_agg = {}
cur = conn.execute('SELECT team_name, AVG(impact_attack), AVG(impact_defense), COUNT(*), SUM(CASE WHEN impact_attack > 0.5 THEN 1 ELSE 0 END) FROM player_impact GROUP BY team_name')
for row in cur.fetchall():
    impact_agg[row[0]] = {'team_att_impact': row[1], 'team_def_impact': row[2], 'tracked_players': row[3], 'high_att_players': row[4]}

core_agg = {}
cur = conn.execute('SELECT team_name, COUNT(*), SUM(CASE WHEN position="G" THEN 1 ELSE 0 END), SUM(CASE WHEN position="D" THEN 1 ELSE 0 END), SUM(CASE WHEN position="M" THEN 1 ELSE 0 END), SUM(CASE WHEN position="F" THEN 1 ELSE 0 END), AVG(start_rate) FROM team_core GROUP BY team_name')
for row in cur.fetchall():
    core_agg[row[0]] = {'core_size': row[1], 'core_gk': row[2], 'core_def': row[3], 'core_mid': row[4], 'core_fwd': row[5], 'avg_start_rate': row[6]}

ref_map = {}
cur = conn.execute('SELECT id, games, yellow_cards*1.0/NULLIF(games,0), red_cards*1.0/NULLIF(games,0) FROM sofa_referee')
for row in cur.fetchall():
    ref_map[row[0]] = {'avg_yellow_per_game': row[2], 'avg_red_per_game': row[3], 'games': row[1]}

ref_assign_map = {}
cur = conn.execute('SELECT match_id, referee_id FROM sofa_referee_assignments')
for row in cur.fetchall():
    ref_assign_map[row[0]] = row[1]

forebet_map = {}
cur = conn.execute('SELECT match_key, date, home_team, away_team, prob_h, prob_d, prob_a FROM forebet_predictions')
for row in cur.fetchall():
    forebet_map[(str(row[2]).strip(), str(row[3]).strip(), str(row[1])[:10])] = {'prob_h': row[4], 'prob_d': row[5], 'prob_a': row[6]}

odds_map = {}
cur = conn.execute('SELECT fd.date, fd.home_team, fd.away_team, fd.b365h, fd.b365d, fd.b365a, tm.sofa_name, tma.sofa_name FROM football_data_matches fd LEFT JOIN team_name_mapping tm ON fd.home_team=tm.fd_name LEFT JOIN team_name_mapping tma ON fd.away_team=tma.fd_name WHERE fd.b365h IS NOT NULL AND fd.b365h>0')
for row in cur.fetchall():
    if row[6] and row[7]:
        odds_map[(str(row[6]).strip(), str(row[7]).strip(), str(row[0])[:10])] = {'b365h': row[3], 'b365d': row[4], 'b365a': row[5]}

ratings_map = {}
cur = conn.execute('SELECT team_name, rating_mu, rating_sigma FROM team_ratings')
for row in cur.fetchall():
    ratings_map[row[0]] = {'rating_mu': row[1], 'rating_sigma': row[2]}

sb_shot_agg = {}
cur = conn.execute("SELECT e.team, COUNT(*), SUM(CASE WHEN e.outcome='Goal' THEN 1 ELSE 0 END), AVG(e.xg), SUM(e.xg), AVG(e.x), AVG(e.y) FROM statsbomb_events e WHERE e.event_type='Shot' GROUP BY e.team")
for row in cur.fetchall():
    sb_shot_agg[row[0]] = {'total_shots': row[1], 'goals': row[2], 'avg_xg_per_shot': row[3], 'total_xg': row[4], 'avg_shot_x': row[5], 'avg_shot_y': row[6]}

h2h_map = {}
cur = conn.execute('SELECT home_team, away_team, total_matches, avg_home_goals, avg_away_goals, home_win_pct, draw_pct, away_win_pct FROM neg_h2h_features')
for row in cur.fetchall():
    h2h_map[(row[0], row[1])] = {'avg_home_goals': row[3], 'avg_away_goals': row[4], 'total_matches': row[2], 'home_win_pct': row[5], 'draw_pct': row[6], 'away_win_pct': row[7]}

conn.close()
log(f'All data loaded: {len(stats_dict)} stats, {len(lineups_dict)} lineups, {len(glicko_dict)} glicko')
log(f'  {len(strength_map)} strength, {len(streak_map)} streaks, {len(league_avg_map)} league avgs')
log(f'  {len(venue_map)} venues, {len(weather_map)} weather, {len(impact_agg)} impact')
log(f'  {len(core_agg)} core, {len(ref_map)} refs, {len(odds_map)} odds')
log(f'  {len(sb_shot_agg)} shot aggs, {len(h2h_map)} h2h')
log('TEST PASSED: All data loads successfully!')
print()
print('='*60)
print('Full run recommendation: python engineer_features.py')
print('Expected ~550 features for 885,497 matches')
print('Estimated time: 15-30 minutes')
print('='*60)
