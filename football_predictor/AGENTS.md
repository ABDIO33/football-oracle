# Football Oracle — Context & Key Decisions

## Project Goal
Build the world's most accurate football exact-score prediction system using free/lightweight sources.

## Architecture
- **Core**: XGBoost + M3 DeepNN Ensemble (89 features, 25 classes, 54k BSD samples)
- **Prediction Engine**: `direct_predictor.py` — `predict_match()` with 89-feature ensemble
- **Data Sources**: BSD API (sports.bzzoiro.com) — matches, odds, ref, coach, weather, xG
- **Odds Source**: **BSD API** only — unlimited, 16+ bookmakers, replaced The Odds API (500 req/mo)
- **Production model**: `EnsemblePredictor` in `models/mlp_blend.pkl` — XGB(20%) + M3
- **Data**: 54,395 BSD matches (2015-2026), 1,868 teams, 12,669 with ref data
- **Walk-forward**: 107,785 snapshots, zero-lookahead Elo + rolling xG

## Performance Evolution
| Date | Model | Exact | Brier | RPS | 1X2 | Features | Notes |
|------|-------|-------|-------|-----|------|----------|-------|
| Jun 14 | Direct Score (baseline) | 13.74% | — | 0.126 | 49.57% | 71 | SofaScore |
| Jun 16 | +Travel Distance | 16.29% | — | 0.112 | 54.58% | 81 | Old model |
| Jun 18 | Dataset expansion (159k) | **18.36%** | — | — | **61.11%** | 81 | Old champion (SofaScore) |
| Jun 19 | XGB(20%)+M3 (89 feat) | 17.08% | — | — | 53.86% | 89 | BSD ensemble baseline |
| Jun 19 | +Calibration + MetaStack | 24.82% | 0.0345 | — | — | 89 | Overfit concern |
| **Jun 19** | **+Live Stats backfill** | **25.18%** | **0.0348** | **0.0975** | **61.01%** | **89** | **🏆 NEW CHAMPION** |
| Jun 19 | +Calibration | 27.51% | 0.0336 | — | — | 89 | Calibrated champion |

**27.51% calibrated**: 7,278 matches now have real live_stats data (shots, SOT, possession, corners, fouls). The 12 stat features went from all-zeros to ~14% coverage. Result: **base accuracy jumped from 17.08% to 25.18%** — a 47% relative improvement from better features alone.

**Best ensemble**: XGB(30%) + DeepNN-M2 + DeepNN-M3 + DeepNN-M4 (3 DeepNNs)

## 89 Features
### Walkforward (25)
home_elo, away_elo, elo_diff, home_xg_for/against, away_xg_for/against,
home_form, away_form, home/away_matches_played,
home_shots_for, away_shots_for, home_shots_against, away_shots_against,
home_xg_diff, away_xg_diff, home_shot_diff, away_shot_diff,
home_days_rest, away_days_rest,
forebet_prob_h/d/a, forebet_available

### Statistics (12)
stat_h/away_xg, shots, sot, possession, corners, fouls

### Lineups + Player Impact (10)
home_formation_def, away_formation_def, formation_diff, has_lineups,
home_missing_core, away_missing_core, home_att_loss, away_att_loss, home_def_loss, away_def_loss

### Market Odds (6)
odds_b365h/d/a, odds_avgh/d/a

### Engineered (23)
elo_form_home/away, elo_xg_home/away, form_xg_home/away,
elo_diff_form_diff, fatigue_home/away,
xg_ratio, shots_ratio, form_ratio, xgf_xga_ratio_home/away, shot_eff_home/away,
elo_diff_sq, xg_diff_sq, form_diff_sq,
month, day_of_week, season_progress, is_weekend

### Weather (4)
home_temp, home_precip, home_wind, home_humidity

### Travel (1)
travel_distance (km, haversine)

### BSD Referee (2) — NEW
ref_games (career games officiated), ref_strictness (yellow+2*red)/games

### BSD Coach Profile (4) — NEW
home_coach_attacking, home_coach_defensive, away_coach_attacking, away_coach_defensive

### BSD Weather (2) — NEW
temperature_c (BSD), wind_speed (BSD)

## Key Files & Functions
- `direct_predictor.py`: 89 features, `predict_match()` handles both old (81) and new (89) model
- `bsd_api.py`: BSD client (odds, events, unlimited)
- `bsd_rich_backfill.py`: Backfilled ref/coach/xG for all 54k matches
- `prediction_engine.py`: `get_market_probabilities()` uses BSD, `analyze_match_deep()` calls dp.predict_match()
- `value_betting_pipeline.py`: **NEW BSD v3** — unlimited value bets from 16-bookmaker comparison
- `models/mlp_blend.pkl`: EnsemblePredictor (89 features) — XGB + M3
- `ensemble_results.json`: Full top-20 ensemble search results

## DB State
- `sofa_historical_results`: 54,395 BSD matches (2015-2026), 12,669 with ref data, 14,406 with coach data
- `walkforward_state`: 107,785 snapshots, 1,868 teams
- `bsd_cache`: API response cache
- `bsd_odds_cache`: Historical odds cache (multi-bookmaker)

## Value Betting Pipeline (BSD v3)
- Fetches upcoming events from BSD API (unlimited)
- Predicts with 89-feature ensemble model
- Compares model probs vs 16-bookmaker market average
- Outputs value bets with Kelly fraction + verdict
- Runs daily via github_runner.py

## Known Limitations
- Only 54k training samples vs old 159k (SofaScore data overwritten by BSD backfill)
- Statistics only available for matches that don't have live stats (always None during training)
- Ref/coach data only available for 2024-2026 matches (~23% coverage)
- Weather from BSD only for recent major competition matches (2.8% coverage)

## Next Steps
1. Collect more training data (combine BSD with other free sources)
2. Use BSD live_stats to populate match statistics during prediction
3. Train ensemble with multiple seeds to find >17.5% configuration
4. Build confidence-based betting strategy (threshold ≥0.20)
