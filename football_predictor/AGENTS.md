# Football Oracle — Context & Key Decisions

## Project Goal
Build the world's most accurate football exact-score prediction system using free/lightweight sources on GitHub Actions free tier.

## Architecture
- **Core**: Dixon-Coles bivariate Poisson model with per-league rho fitted via MLE on 19,748 Understat matches
- **Prediction Engine**: `football_predictor/prediction_engine.py` — `analyze_match_deep()` with multi-source blending
- **Data Sources** (by priority): SofaScore (curl_cffi) > Understat (xG/PPDA) > ClubElo (soccerdata) > StatsBomb > FotMob > WhoScored (curl_cffi) > Market Odds (The Odds API)

## Per-League Rho (model_trainer)
| League | Rho |
|--------|-----|
| EPL | -0.098 |
| La Liga | -0.026 |
| Bundesliga | -0.122 |
| Serie A | -0.042 |
| Ligue 1 | -0.083 |
| Global | -0.070 |

## API Keys Status
- **ODDS_API_KEY**: `3bd0328e5215befff9d8dd41fb46ff87` — The Odds API (500 req/month, ~350 remaining)
- Keys stored in `football_predictor/.env` and `zake-v2/.env`
- All env vars loaded via `os.environ.get()` at runtime

## Key Files & Functions
- `odds_api_scraper.py`: Market odds + value bet detection (`find_value_bets()`)
- `prediction_engine.py`: `analyze_match_deep(use_market_odds=True)` for value detection
- `github_runner.py`: GHA pipeline (weekly retrain + daily predictions)
- `understat_scraper.py`: Understat data (free, no Cloudflare)
- `sofascore_scraper.py`: SofaScore client (curl_cffi + x-requested-with)
- `model_trainer.py`: Per-league rho MLE trainer

## Recent Integration (June 2026)
- The Odds API integrated → `use_market_odds=True` + value bet detection
- 26 bookmakers covered per match, overround removed
- Value detection: compares pure Dixon-Coles (pre-blend) vs market implied probabilities
- Kelly criterion for bet sizing
- League aliases map competition names to API keys

## GHA Runner
- Runs via `github_runner.py`
- Weekly model retrain (Monday <6 UTC)
- Outputs to `output/index.html` + `output/predictions.json`

## Known Limitations
- FBref blocked by Cloudflare Enterprise (only works on GHA with Chrome)
- WhoScored statistics endpoints blocked by oddschecker fingerprint
- Betfair geo-blocked in Morocco
- Sportmonks free tier too limited (abandoned)
- Realistic exact score ceiling: 12-15%
- **`_cached_or_fetch()` uses `requests` library** — blocked by SofaScore Cloudflare. All SofaScore API calls must use `curl_cffi` directly with in-memory cache (`_CACHE`/`_CACHE_TIME` dicts), not `_cached_or_fetch`. National teams (Qatar, Switzerland) return 0 events from `/team/{id}/events/last/20` endpoint — no fallback data available.
- **API-Football key dead**: Key `2064edeecfd82a209e2dca203d5ac9b6` returns 403 "Invalid API key" (error code "4xSe"). All code now uses SofaScore direct API as primary source.

## Bugs Fixed
- **`_cached_or_fetch()` + SofaScore Cloudflare block** (Jun 14 2026): Both `get_daily_matches()` and `get_live_team_data()` used `_cached_or_fetch()` for SofaScore API calls, but `_cached_or_fetch()` uses the `requests` library which cannot bypass SofaScore Cloudflare. All calls silently failed (`_cached_or_fetch` catches all exceptions). Fix: replaced all SofaScore calls with direct `curl_cffi` + `_CACHE`/`_CACHE_TIME` in-memory dicts (matched by cache key). `get_daily_matches()` now returns 205 live matches from SofaScore. `get_live_team_data()` returns `sofascore_api` source for TEAM_DB teams (Malmo FF: 1.93 attack, 15 played; BK Hacken: 2.47 attack, 15 played).
- **UnboundLocalError in `get_live_team_data()`** (Jun 14 2026): Inner `from datetime import datetime` at original line 997 inside match-processing loop made `datetime` a local var across the entire function. `datetime.now().year` at line 945 raised `UnboundLocalError` before reaching the inner import. Fix: removed the redundant inner import (module-level import at line 3 already provides `datetime`). Without this fix, `get_live_team_data()` silently returned `TEAM_DB` defaults (`source: database`) because the outer `try/except` at line 907 caught the exception. All 7 occurrences of `datetime.now()` / `datetime.strptime()` in the function now use the module-level import correctly.
