# Score Exact 100 - AI Football Prediction System

## Overview
Personal AI football (soccer) prediction web app with neon cyberpunk UI. Analyzes match URLs (Sofascore/Flashscore/Livescore), predicts exact scores via live API data + Poisson-Dixon-Coles model, auto-selects best daily bets, and saves user tickets to localStorage.

## Tech Stack
- **Backend:** Python 3.14, Flask (debug mode)
- **Frontend:** HTML5, Vanilla JS, CSS3 (RTL, Orbitron + Tajawal fonts)
- **Database:** SQLite (via Python sqlite3)
- **Server:** Flask development server on http://127.0.0.1:5000
- **Git:** Initialized, single branch

## Architecture

### File Structure
```
football_predictor/
├── app.py                          # Flask routes, env vars, caching
├── prediction_engine.py            # 815 lines - core prediction logic
├── url_parser.py                   # URL regex + API team search
├── database.py                     # SQLite schema
├── templates/
│   ├── index.html                  # Main page (URL input, ticket grid)
│   └── result.html                 # Prediction display (neon cyberpunk)
├── football_predictor.db           # SQLite file
├── start.bat                       # One-click launcher
└── .gitignore
```

### Data Flow
```
URL input → url_parser.py (regex + API search)
                  ↓
         prediction_engine.py
                  ↓
    ┌──── get_team_stats() ────┐
    │   Priority chain:       │
    │   1. BSD API (primary)  │
    │   2. API-Sports v3      │
    │   3. Sportmonks v3      │
    │   4. football-data.org  │
    │   5. ClubElo.com (ELO)  │
    │   6. Default values     │
    └─────────────────────────┘
                  ↓
    analyze_match_deep():
    - Poisson-Dixon-Coles model
    - ClubElo ELO override
    - Odds API blend (45% market + 55% model)
    - Head-to-head data
    - Rate matches (best bets)
                  ↓
    result.html → neon UI with exact score + confidence
                  ↓
    "Add to Ticket" → localStorage → ticket grid on index.html
```

## Data Sources & Limits (Free Plan)

### 1. BSD API (Bzzoiro Sports Data) ⭐ PRIMARY
- **Base:** `https://sports.bzzoiro.com/api/v2`
- **Key:** `37728ad7a9b501c47968df4fadc3e2757ab60384`
- **Endpoints used:**
  - `/teams/?name={name}` → Team search (returns `{count, results}`)
  - `/events/?team_id={id}&status=finished&limit=20` → Past matches for stats
  - `/events/{id}/` → Event details (venue_id, weather, pitch_condition, coaches)
  - `/events/{id}/lineups/` → Lineups (formation + 11 players per team)
  - `/venues/{id}/` → Stadium info (name, city, capacity, pitch dimensions)
  - `/events/live/` → Live matches (2-5 matches typical)
- **Rate limit:** Unknown (seems generous)
- **Response format:** Paginated dict `{"count": N, "results": [...]}`

### 2. API-Sports v3 (api-football)
- **Base:** `https://v3.football.api-sports.io`
- **Key:** Env var `API_SPORT_KEY`
- **Endpoints used:**
  - `/teams/statistics?team={id}&season={year}&league={id}` → Team stats
  - `/teams?search={name}` → Team search (min 5 chars)
  - `/fixtures?status=FT` → Recent results
- **Season handling:** Tries [2025, 2024, 2026, None]; free plan only supports 2022-2024
- **Rate limit:** 100 req/day (very restrictive)

### 3. Sportmonks v3
- **Base:** `https://api.sportmonks.com/v3/football`
- **Key:** Env var `SPORTMONKS_KEY`
- **Rate limit:** 1000 req/month (restrictive)

### 4. football-data.org v4
- **Base:** `https://api.football-data.org/v4`
- **Key:** Env var `FOOTBALL_DATA_API_KEY`
- **Rate limit:** 10 req/min, 1000/day

### 5. ClubElo.com (ELO only)
- **Base:** `https://api.clubelo.com/{team_name}`
- **Usage:** ELO override applied AFTER any other source's ELO
- **Coverage:** ~80% of teams (uses `CLUBELO_NAMES` mapping for non-standard names)
- **Special:** Highest quality ELO signal; `elo_source: 'clubelo'`

### 6. The Odds API v4
- **Base:** `https://api.the-odds-api.com/v4`
- **Key:** Env var `ODDS_API_KEY`
- **Usage:** Market probability blend (45% market + 55% model)
- **Regions:** `eu`, `uk`

## Prediction Model

### Poisson-Dixon-Coles
Core model with 4 factors:
1. **Attack/Defense strength** (from per-team stats data)
2. **Home advantage** (+70 ELO, toggleable via "ملعب محايد" checkbox)
3. **Head-to-head history** (recent matches)
4. **ELO factor** (ClubElo.com or computed from goal difference)

**Formula:**
```python
lambda_home = avg_home_goals * attack_home * defense_away * elo_factor * h2h_factor
lambda_away = avg_away_goals * attack_away * defense_home * elo_factor * h2h_factor
```

**Score probability:** `P(X=i, Y=j) = Poisson(i, λ₁) * Poisson(j, λ₂) * Dixon-Coles correlation`

### Output
```python
{
    'home_score': 2, 'away_score': 1,
    'confidence': 78.5,           # percentage
    'btts_probability': 45.2,     # both teams to score %
    'over_2_5_prob': 62.1,        # over 2.5 goals %
    'best_bet': 'home_win',
    'match_importance': 'balanced',
    'analysis': { home/away stats, elo, h2h, market }
}
```

### Match Importance Rating
- **super_sure** (≤2 goals total, high confidence)
- **competitive** (high confidence on winner)
- **high_goals** (≥3 total goals)
- **goalfest** (≥4 goals)
- **balanced** (everything else)

### Daily Rate System
Up to 7 matches analyzed per day. `rate_matches()` scores and ranks all matches, returns top 3 "best bets" with reasoning.

## Caching Strategy
- Team stats: 60 min
- Team searches: 1440 min (24h)
- Odds data: 1800 min (30h)
- Cache key includes `neutral_venue` flag

## Key Design Decisions
1. **Lambda headers** — All API auth headers are lambdas reading `os.environ.get()` at call time, because env vars are set in app.py AFTER prediction_engine imports
2. **BSD priority** — BSD is tried first because it has best coverage and generous rate limit
3. **Season fallback** — Tries [2025, 2024, 2026, None] since free API-Sports only supports 2022-2024
4. **Neutral venue toggle** — Passed as `neutralVenue` JSON field, affects ELO calculation
5. **Zero static data** — All team DB was deleted; everything comes from live APIs

## Recent Improvements (June 2026)
- ✅ **Friendly match detection** — `detect_competition_type()` checks BSD league name; auto-overrides confidence→LOW + warning in UI
- ✅ **Form trend momentum** — `calculate_form_trend()` analyzes last 6 matches (ascending/stable/declining), applies ±8% to Poisson lambda
- ✅ **World Cup 2026 optimization** — phase factors (group→final) reduce goal expectations in knockout rounds; draw probability boosts
- ✅ **StatsBomb xG blend** — blends 40% StatsBomb xG + 60% BSD goal averages when available
- ✅ **Kelly Criterion** — `kelly_criterion(prob, odds)` calculates optimal bet stake; shown in UI
- ✅ **Top 3 predictions** — result.html shows 1st/2nd/3rd most likely scores with percentages
- ✅ **H2H multi-source** — BSD primary, API-Sports fallback; each marked with `source` tag
- ✅ **Neutral venue** — affects `hg`/`ag` directly (0.85/0.95 factors) plus ELO, not just ELO
- ✅ **Best bet hybrid** — combines win/draw + Over/BTTS + exact score in one string
- ✅ **Match extra data** — venue name/city/capacity, weather, lineups, pitch condition from BSD
- ✅ **Evaluation database** — `evaluation.db` stores predictions, auto-evaluates after match finishes
- ✅ **Historical data collector** — `collect_historical_data.py` pulls from StatsBomb + FBref + BSD
- ✅ **No reloader** — fixed `use_reloader=False` so server stays running in background

## Known Limitations
1. Free API-Sports: 100 req/day severely limits match analysis volume
2. **No backtesting yet** — accuracy still estimated (~55-65% for league matches, lower for friendlies)
3. Development server only (not production-ready)
4. SQLite (not suitable for concurrent access)
5. Poisson model assumes goal scoring rate is constant (no form/momentum)
6. **Friendlies perform poorly** — APIs lack friendly match stats; teams use rotated squads
