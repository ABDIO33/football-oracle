# Football Oracle — Context & Key Decisions

## Project Goal
Build the world's most accurate football exact-score prediction system using free/lightweight sources.

## Architecture
- **Core**: XGBoost + 4 DeepNN Ensemble Direct Score Predictor (81 features, 25 classes: 0-0 to 4-4+)
- **Prediction Engine**: `direct_predictor.py` — `predict_match()` with multi-model ensemble
- **Data Sources**: SofaScore (curl_cffi) > ClubElo > Understat > Market Odds
- **All-time best**: **17.97% exact score** (lucky seed), **17.60%** (stable seed=42), **56.11% 1X2** (M5 single)
- **Production model**: `EnsemblePredictor` in `models/mlp_blend.pkl` — XGBoost (5%) + 2 DeepNN (M2, M5)
- **Data**: 100,540 matches, 1,067 tournaments, 4,949 teams, worldwide
- **Walk-forward pipeline**: Zero-lookahead Elo + rolling xG stats → `walkforward_state` table

## Performance Evolution
| Date | Model | Exact | 1X2 | RPS | Notes |
|------|-------|-------|-----|-----|-------|
| Jun 14 | Direct Score (baseline) | 13.74% | 49.57% | 0.126 | 71 features |
| Jun 15 | +Player Impact (6 feat) | 15.56% | 53.27% | 0.114 | 76 features |
| Jun 15 | +Weather (4 feat) | 15.68% | 53.14% | 0.113 | 80 features |
| Jun 15 | +Tuning (subsample=0.9) | 15.82% | 53.29% | 0.113 | 80 features |
| Jun 16 | +Travel Distance (+1 feat) | 16.29% | 54.58% | 0.112 | 81 features |
| Jun 16 | DeepNN-M5 (128-256-128) | **17.53%** | **56.11%** | 0.1125 | Best single model |
| Jun 16 | Ensemble XGB(5%)+M2+M5 | **17.60%** | — | — | Seed=42, production ready |

## 81 Features
### Walkforward (25)
home_elo, away_elo, elo_diff, home_xg_for/against, away_xg_for/against, home_form, away_form, home/away_matches_played, home_shots_for, away_shots_for, home_shots_against, away_shots_against, home_xg_diff, away_xg_diff, home_shot_diff, a_shot_diff, home_days_rest, away_days_rest, forebet_prob_h/d/a, forebet_available

### Statistics (12)
stat_h/away_xg, shots, sot, possession, corners, fouls

### Lineups + Player Impact (10)
home_formation_def, away_formation_def, formation_diff, has_lineups, home_missing_core, away_missing_core, home_att_loss, away_att_loss, home_def_loss, away_def_loss

### Market Odds (6)
odds_b365h/d/a, odds_avgh/d/a

### Engineered (23)
elo_form_home/away, elo_xg_home/away, form_xg_home/away, elo_diff_form_diff, fatigue_home/away, xg_ratio, shots_ratio, form_ratio, xgf_xga_ratio_home/away, shot_eff_home/away, elo_diff_sq, xg_diff_sq, form_diff_sq, month, day_of_week, season_progress, is_weekend

### Weather (4)
home_temp, home_precip, home_wind, home_humidity

### Travel (1)
travel_distance (km, haversine)

## Ensemble Architecture
- **5 architectures trained**: M2 (512-1024-512), M3 (256-512-256-128), M4 (512-1024-512-256), M5 (128-256-128), M6 (1024-512-256)
- **Best ensemble (seed=42, production)**: XGBoost (5%) + M2 + M5 = **17.60% exact**
- **All-time best (lucky seed)**: 17.97% (XGB + M2+M3+M4+M6)
- **Seed sensitivity**: ~0.4% variance between runs — M5 appears in top ensembles most consistently
- **Saved as**: `models/mlp_blend.pkl` (single file, joblib, 2 DeepNN + XGBoost + imputer + scaler)

## Key Files & Functions
- `direct_predictor.py`: `predict_match()`, `build_feature_vector()`, `load_model()`, `EnsemblePredictor`, `TorchMLPWrapper`
- `ensemble_trainer.py`: Full pipeline — loads data, trains 5 architectures, searches blends, saves `mlp_blend.pkl`
- `models/mlp_blend.pkl`: **EnsemblePredictor** — XGBoost + 4 DeepNN + imputer + scaler + weights
- `models/direct_score.json`: XGBoost model (saved separately for compatibility)
- `models/ensemble_results.json`: Full search results (top 20 blends)
- `premier_league_data.py`: Data fetching/parsing with 500+ feature engineering
- `player_impact.py`: Core 11 + impact scores (1,929 teams, 8,988 lineups cached)

## Known Limitations
- Statistics only Apr-Jun 2026 (9,462 rows). No Jan-Mar data.
- Lineups: 8,988 / 100,540 (8.9%)
- Weather: 102 stadiums, 7.5% coverage
- Odds API: 500 req/month limit
- Ensemble has 4 DeepNN models + XGBoost → ~5x slower than single model

## Next Steps
1. Fetch upcoming/scheduled matches via SofaScore API for live predictions
2. Build prediction pipeline: auto-fetch fixtures → predict → output
3. Evaluate World Cup-specific accuracy (1,098 matches in training data)
4. Collect more data to push beyond 18% (expand date range, more leagues)
5. Add weighted ensemble learning (learn optimal blend weights)
6. Build confidence-based betting strategy (≥0.20 threshold → 23% exact historically)

## Training Configs
| Name | Hidden Layers | Dropout | LR | Exact |
|------|--------------|---------|----|-------|
| M2 | 512-1024-512 | 0.2 | 0.001 | 16.62% |
| M3 | 256-512-256-128 | 0.2 | 0.001 | 17.01% |
| M4 | 512-1024-512-256 | 0.2 | 0.001 | 17.09% |
| M5 | 128-256-128 | 0.3 | 0.001 | **17.53%** |
| M6 | 1024-512-256 | 0.2 | 0.001 | 16.33% |
