# FOOTBALL ORACLE — MASTER PLAN: #1 IN THE WORLD
# =====================================================
# This document is for ANY AI agent. Read it fully before starting.
# =====================================================

## MISSION
Build the world's most accurate football exact-score prediction system
(25 classes: 0-0 to 4-4+) for value betting at World Cup 2026.
Target: >=25% exact score, >=75% 1X2, positive ROI.

## CURRENT STATE (Jun 25, 2026)
- Database: 887,041 matches, 1,101,520 walkforward states, 9,093 teams
- 81 features per match, date range 1983-2026
- V5 trained: 18.51% exact (177K realistic test set)
- V3 trained: 25.89% exact (29K easy test set) — production model
- V5 ensemble: M5_deep=56%, M5_small=24%, xgb=12%, M5_medium=8%
- V5 betting @30%: 21.1% accuracy (not profitable enough)
- NO real-money test yet. NO GPU. CPU-only (17s/epoch).
- Lineup coverage: 8.9%. Weather: 7.5%. Referee: 0%.

## WHAT'S MISSING (ranked by impact)
1. Lineup data (8.9% -> need 50%+) = +3-5% accuracy
2. Poisson/Dixon-Coles base model = +2-3% accuracy
3. Stacking meta-learner (vs weighted avg) = +1-2% accuracy
4. Calibration (isotonic + temperature) = +1-2% betting ROI
5. Weather data (7.5% -> need 40%+) = +1% accuracy
6. Referee data (0% -> need 30%+) = +0.5% accuracy
7. GPU training (200 epochs vs 120) = +1-2% accuracy
8. League-specific models = +1% accuracy

## 7-DAY INTENSIVE PLAN (168 hours, 24/7 AI work)

### DAY 1: DATA MAXIMALISM (0-24h)
1A. Fetch lineups from SofaScore API (0-6h)
    - Endpoint: https://www.sofascore.com/api/v1/event/{id}/lineups
    - Fetch for 50,000+ matches with event IDs
    - Store in match_lineups table
    - Script: football_predictor/fetch_lineups_bulk.py

1B. Fetch weather from Open-Meteo (6-10h)
    - URL: https://archive-api.open-meteo.com/v1/archive
    - Free, no API key needed
    - Get temp, precip, wind, humidity for all match dates
    - Script: football_predictor/fetch_weather_bulk.py

1C. Fetch referee data from SofaScore (10-14h)
    - Endpoint: https://www.sofascore.com/api/v1/event/{id}
    - Build referee profiles (fouls, cards, home bias)
    - Script: football_predictor/fetch_referees.py

1D. Feature engineering: 81 -> 120+ features (14-20h)
    - Add: referee stats (3), weather (4), formation strength (2)
    - Add: H2H (3), league context (2), tournament importance (1)
    - Add: Poisson probabilities as features (25)
    - Script: football_predictor/expand_features.py

1E. Data quality audit (20-24h)
    - Remove pre-2000 matches, verify no leakage
    - Chronological 80/20 split
    - Save: models/v6_preprocessed.npz

### DAY 2: MODEL ARCHITECTURE (24-48h)
2A. Poisson/Dixon-Coles model (24-30h)
    - Team attack/defense via MLE, exponential decay
    - Generate 25-class probability matrix
    - Script: football_predictor/poisson_model.py

2B. League-specific models (30-36h)
    - Top 20 leagues, separate Poisson per league
    - League embedding for DeepNN
    - Script: football_predictor/league_models.py

2C. Stacking meta-learner (36-42h)
    - OOF predictions from all base models
    - LightGBM meta-learner (learns optimal combination)
    - Script: football_predictor/stacking_meta.py

2D. Calibration (42-48h)
    - Isotonic regression per class
    - Temperature scaling
    - Script: football_predictor/calibrate.py

### DAY 3: TRAIN V6 (48-72h)
3A. Prepare data (48-50h) — 120+ features + Poisson probs
3B. Train 7 architectures, 200 epochs each (50-66h)
    - M5_small/medium/big/wide/deep + 2 new (ultra, tower)
    - Cosine annealing LR, mixup, label smoothing 0.1
    - Script: football_predictor/train_v6.py
3C. Ensemble + stacking + calibration (66-72h)

### DAY 4: BACKTESTING & BETTING (72-96h)
4A. Backtesting engine (72-78h)
    - Test 5 betting strategies on 177K historical matches
    - Track ROI, drawdown, Sharpe ratio
    - Script: football_predictor/backtest.py
4B. Betting pipeline enhancement (78-84h)
4C. Paper trading setup (84-96h)

### DAY 5: WORLD CUP (96-120h)
5A. World Cup-specific model (96-102h)
5B. Tournament simulation (102-108h)
5C. Live prediction pipeline (108-120h)

### DAY 6: OPTIMIZATION (120-144h)
6A. Optuna hyperparameter search (120-132h)
6B. Feature selection with SHAP (132-138h)
6C. Final model build (138-144h)

### DAY 7: DEPLOYMENT (144-168h)
7A. Production pipeline (144-150h)
7B. First real-money bets (150-168h)

## SUCCESS CRITERIA
- MINIMUM: 20% exact, 70% 1X2, RPS <= 0.070, positive ROI after 50 bets
- TARGET: 25% exact, 75% 1X2, RPS <= 0.058, 10% monthly ROI
- STRETCH: 28% exact, 78% 1X2, RPS <= 0.052, 15% monthly ROI

## AI AGENT RULES
1. Read this document fully before starting
2. Check current state: models/v5_log.txt, models/v5_results.json
3. Never break working code — test before and after changes
4. UTF-8 encoding for all files on Windows
5. No emojis in Python files (causes UnicodeEncodeError)
6. Save checkpoints after every step
7. Log to models/v6_log.txt with timestamps

## KEY FILES
- football_predictor/direct_predictor.py — prediction engine
- football_predictor/train_v5.py — V5 trainer (completed)
- football_predictor/betting_pipeline.py — betting predictions
- football_predictor/models/ — all model files
- football_predictor/database.db — SQLite, 887K matches
- football_predictor/models/v3_model.pkl — V3 production (25.89%)
- football_predictor/models/v5_results.json — V5 results (18.51%)

## ENVIRONMENT
- Windows 11, Python 3.14, no GPU
- PyTorch 2.12.0+cpu, XGBoost, scikit-learn
- SofaScore API (chrome124 user-agent, works)
- OpenRouter API: 26 free models (Nemotron Ultra 550B, Qwen3 Coder 480B, GPT-OSS 120B)
- Open-Meteo API: free weather data
