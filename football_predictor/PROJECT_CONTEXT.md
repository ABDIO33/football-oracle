# Football Oracle - Project Context

## Architecture
- **System**: 100% Serverless, $0 budget (no VPS)
- **Engine**: GitHub Actions wakes 5x/day, runs 3 min per cycle, then shuts down
- **Frontend**: GitHub Pages static HTML site, open 24/7 with zero compute cost
- **Data flow cycle**: Fetch data → Analyze → Predict → Update files → Shut down

## File Map (latest commit: `5cc74ee`)

### 1. `calibration.py`
- ML calibration model for 1X2 probability correction
- Trained after 10+ resolved matches
- Exports function: `calibrate_probabilities(raw_probs)` → returns calibrated probabilities

### 2. `prediction_engine.py`
- Core prediction algorithms: Poisson Distribution + AI Ensemble
- Calls `calibration.calibrate_probabilities()` immediately after normalization
- Input: match data → Output: 1X2 probabilities + predicted scores

### 3. `github_runner.py`
- Orchestrates the entire GitHub Actions workflow
- One cycle: fetch → analyze → predict → update files
- Prints final Calibration Report at end of each run

### 4. `scrape_cache.db` (SQLite)
- Local database for 24-hour data caching
- Avoids duplicate API requests within same day

## Current Technical Challenge
- **Problem**: Sofascore API blocked by Cloudflare (403 Forbidden) due to Python Requests TLS fingerprint
- **Solution**: Replaced `requests` + `selenium` with `curl_cffi`
- **Implementation**: `curl_cffi` with `impersonate="chrome120"` bypasses Cloudflare by mimicking real Chrome browser TLS fingerprint
- **Performance**: Fast, lightweight, no browser overhead

## Dependencies (requirements.txt)
- `curl_cffi` (primary HTTP client)
- `numpy`, `scipy` (statistical computations)
- `scikit-learn` (calibration model)
- `aio-sqlite3` or `sqlite3` (cache DB)

## Notes
- Never revert to `requests` or Selenium/WebDriver
- All probability outputs pass through calibration before final storage
- Cache invalidates every 24h (TTL based on match date)