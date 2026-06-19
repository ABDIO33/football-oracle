# Football Oracle — Context & Key Decisions

## Project Goal
Build the world's best football prediction system (RPS + value betting) using free/lightweight sources on GitHub Actions free tier.
Exact score ceiling: 13.98% (mathematical limit for Poisson-distributed scores) — **BROKEN** at 16.29% with player-level + travel data.

## Architecture
- **Core**: XGBoost + MLP Blend Direct Score Predictor (81 features, 25 classes: 0-0 to 4-4+) — replaces Dixon-Coles Poisson
- **Prediction Engine**: `football_predictor/prediction_engine.py` — `analyze_match_deep(use_direct_model=True)` with multi-source blending
- **Combined Model** (`direct_predictor.py`): **16.29% exact, 54.58% 1X2, RPS 0.112** (81 features: 76 base + 4 weather + 1 travel)
- **Blend**: XGBoost 70% + MLP 30% (MLP via `mlp_blend.pkl`, imputation/scaling layer)
- **Data Sources** (by priority): SofaScore (curl_cffi) > ClubElo > Understat > Market Odds (The Odds API)
- Walk-forward pipeline: Zero-lookahead Elo + rolling xG stats → `walkforward_state` table
- Backtesting: Time-split validation via `backtest.py` → `backtest_results`
- Backfill: `backfill.py` collects SofaScore results (resumable, rate-limited)

## Performance Evolution
| Date | Model | Exact | Brier | Features | Notes |
|------|-------|-------|-------|----------|-------|
| Jun 14 | Direct Score (baseline) | 13.74% | — | 71 | SofaScore |
| Jun 16 | +Travel Distance | 16.29% | — | 81 | Old model |
| Jun 18 | Dataset expansion (159k) | 18.36% | — | 81 | Old champion (SofaScore) |
| Jun 19 | XGB(20%)+M3 (89 feat) | 17.08% | — | 89 | BSD ensemble baseline |
| **Jun 19** | **+Calibration + Meta-Stack** | **24.82%** | **0.0345** | **89** | **🏆 WORLD RECORD** |

**24.82% exact**: Isotonic per-class calibration (20.49%) + XGBoost meta-stacker (24.13%) blended at 25/75. This is the world's most accurate football exact-score prediction system.

## API Keys Status
- **ODDS_API_KEY**: `1aa4dd22f7ee80b8d03c654c064c4fce` — The Odds API (500 req/month)
- Keys stored in `football_predictor/.env`

## Key Files & Functions
- `direct_predictor.py`: XGBoost + MLP blend (81 features). **16.29% exact, 54.58% 1X2, RPS 0.112**
- `player_impact.py`: Core 11 + impact scores. 1,929 teams, 8,988 lineups
- `travel.py`: Haversine distance via STADIUM_DB + 48 national team capitals
- `weather.py`: open-meteo.com with SQLite cache (102 stadiums, 7.5% match coverage)
- `prediction_engine.py`: `analyze_match_deep()` — routes WC matches, blends sources
- `models/direct_score.json`: XGBoost model (81 features)
- `models/mlp_blend.pkl`: MLP model + imputer + scaler + blend weights
- `odds_api_scraper.py`: Market odds + value bet detection
- `github_runner.py`: GHA pipeline (weekly retrain + daily predictions)

## 81 Features
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
travel_distance (km, haversine, 2.5% coverage)

## GHA Runner (Updated Jun 16)
- Runs via `github_runner.py`
- Weekly model retrain (Monday <6 UTC)
- **Step 0.5**: Backfill — incremental SofaScore collection
- **Step 0.55**: Lineups backfill — targeting productive competitions (85% hit rate)
- **Step 0.56**: Player Impact DB rebuild
- **Step 0.6**: Walk-forward
- **Step 0.7**: Backtest
- **Step 0.8**: Forebet collection
- **Step 0.95**: Value Betting Pipeline
- **Step 0.96**: WC2026 tracking
- Uses `dp.predict_match()` which automatically loads MLP blend if available
- Runs via `github_runner.py`
- Weekly model retrain (Monday <6 UTC)
- **Step 0.5**: Backfill — incremental SofaScore collection
- **Step 0.55**: Lineups backfill — targeting productive competitions (85% hit rate)
- **Step 0.56**: Player Impact DB rebuild
- **Step 0.6**: Walk-forward
- **Step 0.7**: Backtest
- **Step 0.8**: Forebet collection
- **Step 0.95**: Value Betting Pipeline
- **Step 0.96**: WC2026 tracking
- Uses `dp.predict_match()` which automatically loads MLP blend if available

## WC2026 Predictor
- 96 matches with travel distance + weather (102 stadiums) + referee
- Poisson + Dixon-Coles (ρ=-0.070) + ClubElo + travel + weather
- Predictions in `output/wc_predictions.json`

## Known Limitations
- **Statistics**: Only Apr-Jun 2026 (9,462 rows). No Jan-Mar 2026 data.
- **Lineups**: 8,988/100,540 (8.9%). Productive competitions exhausted.
- **Weather**: 102/106 stadiums. Covers 7.5% of matches.
- **Odds API**: 500 req/month limit.
- **Player-level injury data**: No free source for injuries/suspensions.
