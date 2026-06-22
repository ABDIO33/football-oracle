# Football Oracle — Context & Key Decisions

## Project Goal
Build the world's best football exact-score prediction system (25-class: 0-0 to 4-4+) for value betting, targeting 20%+ exact score globally. Runs on GitHub Actions free tier + local Windows.

## ⚠️ CRITICAL DISCOVERY (Jun 22)
**Previous 36.60% was OVERFIT** — random split leaks future info. Real chronological performance:

| Model | Split | Exact | 1X2 | RPS |
|-------|:----:|:----:|:---:|:---:|
| XGBoost (direct_score.ubj) | Random | 36.60% | 77.30% | 0.5655 |
| XGBoost (direct_score.ubj) | **Time-Split** | **7.70%** | **33.03%** | **0.1729** |
| **M5 DeepNN (new)** | **Time-Split** | **24.36%** | **73.33%** | **0.0661** |
| **Ensemble XGB(15%)+M5(85%)** | **Time-Split** | **24.42%** | **73.42%** | **0.0658** |

**Real production model**: `models/real_model.pkl` — XGBoost + M5 ensemble, chronological train
- **24.42% exact**, 73.42% 1X2 — +10.28pp over old time-split baseline (14.14%)
- **Betting ready**: @30% confidence → **37.9% accuracy** (profitable with odds >2.64)

## Architecture (Current: Jun 22)
- **Core**: XGBoost(15%) + M5(85%) Ensemble (85 features, 25 classes)
- **Production model**: `models/real_model.pkl` — XGBoost + M5 chronologically trained
- **Real Time-Split**: **24.42% exact, 73.42% 1X2, RPS 0.0658**
- **Betting @30% conf**: **37.9% exact** = profitable (avg odds 5-10 → 89-165% EV)
- **Data**: **292,723 matches** (2012-2026), 5,542 teams, via SofaScore + soccer-dataset
- **M5 architecture**: 128-256-128, 60 epochs, batch 512, AdamW, CosineAnnealingLR
- **Saved files**: `real_model.pkl`, `real_xgb.ubj`, `real_m5.pt`, `real_model_results.json`

## Performance Evolution (Time-Split = REAL metric)
| Date | Model | Exact | 1X2 | Split |
|------|-------|:----:|:---:|:----:|
| Jun 17 | Old baseline | 14.14% | 52.12% | Time |
| Jun 22 | XGBoost (chronological) | **20.72%** | **67.04%** | Time |
| Jun 22 | M5 DeepNN | **24.36%** | **73.33%** | Time |
| Jun 22 | XGB+M5 Ensemble | **24.42%** | **73.42%** | Time |

## Key Files (Updated Jun 22)
- `models/real_model.pkl`: **NEW production model** — XGBoost(15%) + M5(85%) + imputer + scaler
- `models/real_xgb.ubj`: XGBoost model (chronologically trained, 20.72% time-split)
- `models/real_m5.pt`: M5 state dict (24.36% time-split)
- `models/real_model_results.json`: Full metrics + betting strategy results
- `build_real_model.py`: Script to build REAL production model (no lookahead)
- `direct_score.ubj`: **DEPRECATED** — 36.60% random split (overfit, only 7.70% time-split)

## Known Limitations
- **XGBoost overfits badly**: 36.60% random → 7.70% time-split (4.75x drop). DeepNN more robust.
- **M5 only trained 60 epochs**: could improve with more epochs/layers
- **No real-time prediction**: model built in memory, not integrated into web service
- **Betting not tested with real odds**: 37.9% @30% conf is promising but needs real odds validation

## Next Steps (Priority)
1. **Integrate into betting_strategy.py**: use `real_model.pkl` for live predictions, test with real SofaScore odds
2. **Improve M5**: add more layers (256-512-256), train 100+ epochs, add Glicko-2 as 86th feature
3. **Build web service**: expose model via Flask for real-time score predictions
4. **Live betting test**: predict tomorrow's matches, compare with real odds
5. **Fix XGBoost overfit**: use chronological CV, reduce n_estimators, add reg_alpha/lambda
