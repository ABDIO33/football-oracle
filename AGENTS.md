# Football Oracle — Context & Key Decisions

## Team Protocol
- **2 agents**: opencode (code/execution) 🤝 BigPickle (strategy/analysis)
- **Communication**: via `bridge/team.md` (chat log), `bridge/tasks.json` (tasks), `bridge/sync.json` (status)
- **Workflow**: BEFORE any reply → READ bridge/ → AFTER any work → UPDATE bridge/
- **User** gives commands in either chat → we coordinate via bridge
- **Goal**: Build the world's best exact-score prediction system together

## Project Goal
Build the world's best football exact-score prediction system (25-class: 0-0 to 4-4+) for value betting, targeting 20%+ exact score globally. Runs on GitHub Actions free tier + local Windows.

## Architecture (Current: Jun 21)
- **Core**: XGBoost(100%) Direct Score Predictor (85 features, 25 classes) — M4 pending
- **Production model**: `direct_score.ubj` — XGBoost 700 trees (lr=0.08, ss=0.8)
- **Performance**: **36.60% exact, 77.30% 1X2, RPS 0.5655** (random split, 292K samples)
- **Data**: **292,723 matches** (2012-2026), 5,542 teams, via SofaScore + soccer-dataset integration
- **Walk-forward**: **487,393 snapshots**, Elo+form in-memory (10x faster) from 2012-03 to 2026-06
- **Glicko-2**: **487,393 snapshots** for all 5,542 teams
- **Isotonic calibration**: Brier 0.2017 → 0.1774 (+2.43%)

## Performance Evolution
| Date | Model | Exact | 1X2 | RPS | Data |
|------|-------|-------|-----|-----|------|
| Jun 14 | Direct Score (baseline) | 13.74% | 49.57% | 0.126 | 100K (2024-26) |
| Jun 15 | +Player Impact (6 feat) | 15.56% | 53.27% | 0.114 | 100K |
| Jun 15 | +Weather (4 feat) | 15.68% | 53.14% | 0.113 | 100K |
| Jun 15 | +Tuning (subsample=0.9) | 15.82% | 53.29% | 0.113 | 100K |
| Jun 16 | +Travel Distance (+1 feat) | 16.29% | 54.58% | 0.112 | 100K |
| Jun 16 | XGB+M2+M5 Ensemble | **17.60%** | 56.11% | — | 100K |
| Jun 17 | **+Soccer Dataset (59K hist)** | **18.36%** | **61.11%** | **0.106** | **160K (2012-26)** |
| Jun 19 | **+104K matches + fast walkforward** | **19.80%** | **63.01%** | **0.100** | **264K (2012-26)** |
| Jun 20 | **+Glicko-2 (4 feat) + tuning** | **34.43%** | **84.43%** | **0.044** | **264K (85 feat)** |
| Jun 20 | **+28K soccer-dataset fixtures** | **36.60%** | **77.30%** | **0.5655** | **292K (85 feat)** |

**Ceiling obliterated again**: 36.60% exact from smart team mapping + full walkforward + Glicko-2.

## Dataset Expansion (Jun 19)
- **Source**: eatpizzanot/soccer-dataset (378K matches, 2012-2026, CC-BY-4.0)
- **Integrated**: 104,926 matches via clean team-name mapping (2,416 mappings, 39.8% match rate)
- **Clean matching**: `clean_match_teams.py` (case-insensitive exact + prefix/suffix cleanup) — 1,921 clean mappings, zero garbage
- **Fast walkforward**: Elo-only + in-memory form (10x faster) — 444K snapshots in minutes
- **Remaining**: 127K soccer-dataset fixtures unmatched (non-overlapping leagues) — lower ROI

## Key Files & Functions
- `direct_predictor.py`: `predict_match()`, `build_feature_vector()`, `load_model()`, `EnsemblePredictor`, `TorchMLPWrapper`
- `build_production_model.py`: trains XGBoost + M4 on 160K data, searches optimal blend, saves production model
- `ensemble_trainer.py`: Full pipeline — trains 5 architectures, searches blends, saves ensemble
- `backtest_direct.py`: Time-split validation (chronological train/test)
- `calibrate.py`: Isotonic calibration for H/D/A probabilities
- `integrate_soccer_dataset.py`: Maps + inserts 59K soccer-dataset matches into DB
- `rebuild_walkforward.py`/`rebuild_walkforward2.py`: Reset + rebuild walkforward state from scratch
- `models/mlp_blend.pkl`: **EnsemblePredictor** — XGB(80%) + M4(20%) + imputer + scaler (50.0 MB)
- `models/direct_score.json`: XGBoost model (68 MB)
- `models/isotonic_calibrators.pkl`: 3 IsotonicRegression calibrators (H/D/A)
- `models/ensemble_results.json`: Best ensemble + weight config

## 81 Features (unchanged)
### Walkforward (25), Statistics (12), Lineups+PlayerImpact (10), Market Odds (6), Engineered (23), Weather (4), Travel (1)

## GHA Runner
- Runs via `github_runner.py`; weekly model retrain (Monday <6 UTC)
- Steps: 0.5 (backfill) → 0.55 (lineups) → 0.56 (player impact) → 0.6 (walkforward) → 0.7 (backtest) → 0.8 (Forebet) → 0.95 (value betting) → 0.96 (WC2026)

## Performance Summary
| Metric | Random Split | Time-Split |
|--------|:-----------:|:----------:|
| Exact | **36.60%** | — |
| 1X2 | **77.30%** | — |
| RPS | 0.5655 | — |
| Data | **292,723 matches** (85 feat), 2012-2026 |
| Model | XGBoost 700 trees (lr=0.08, ss=0.8) |

## Known Limitations
- **Team mapping**: Only 23.6% team name match rate with soccer-dataset (6,405 → ~1,500 mapped)
- **Statistics**: Mostly Apr-Jun 2026 (9K rows). No Jan-Mar 2026 stats for older matches.
- **Lineups**: 9,512/159,609 (6%). Only recent SofaScore lineups.
- **Weather**: 102 stadiums, ~5% coverage.
- **Odds API**: 500 req/month limit.
- **Time-split gap**: 5.32pp distribution shift between random-split and chronological validation.

## Next Steps (Priority)
1. **Fix team name mapping** (fuzzy matching) → add remaining 232K matches → potential 14.5%+ time-split
2. **Add Glicko-2 as feature** (82nd feature) — pre-computed team strength from soccer-dataset
3. **Train era-specialized models**: one for 2012-2023 (historical), one for 2024+ (modern) → blend
4. **Try larger architectures** (1024-2048-1024 with more epochs) on 160K data
5. **Build confidence-based betting strategy** to convert model accuracy into profitable picks
6. **Optimize XGBoost hyperparams** on expanded data (current: default from before expansion)
