# Score Exact 100 — System Blueprint v1.0

## Architecture
```
app.py (Flask, 3 routes: /predict POST, /api/analyze POST, /)
  └── prediction_engine.py (core: ~1684 lines)
        ├── compute_features(home, away) → features dict
        │     ├── get_live_team_data(team) → {attack_xg, defense_xg, form_points, elo, source}
        │     │     ├── TEAM_DB (static ~260 teams, fallback)
        │     │     ├── API-Football (v3, 100req/day, 30min cache→api_cache.db)
        │     │     ├── TheSportsDB (unlimited, free key '3')
        │     │     └── edge_scraper.get_team_form() (unlimited, Flashscore via Edge)
        │     └── get_head_to_head(team1, team2) → h2h dict
        │           ├── API-Football (h2h endpoint)
        │           └── BSD API (fallback)
        ├── analyze_match_deep(home, away) → prediction dict
        │     ├── compute_features → features
        │     ├── base_home = attack*defense/league_avg * home_adv
        │     ├── form_mult, elo_mult, injury_mult
        │     ├── hg = base_home * form * elo * injury
        │     ├── ag = base_away * form * elo * injury
        │     ├── dixon_coles_predict(hg, ag, rho=-0.07) → probs matrix 10×10
        │     │     ├── Monte Carlo 100K simulations (np.random.poisson)
        │     │     └── → home_win, draw, away_win, exact_score, O/U, BTTS, AH
        │     └── normalize → percentages + top_scores + analysis
        ├── get_daily_matches(date) → matches list
        │     ├── football-data.org (competitions)
        │     └── API-Football (fixtures by date)
        ├── rate_matches(matches) → top 20 rated
        └── ai_ensemble(features, prediction) → AI-adjusted prediction
              ├── AgentRouter (deepseek-v4-flash) or
              └── Groq (llama-3.3-70b-versatile)

edge_scraper.py (222 lines, Edge WebDriver → Flashscore, unlimited)
  ├── get_team_form(team) → {wins, draws, losses, gf, ga, avg_gs, avg_gc, form_rating}
  ├── get_live_matches() → list of live/upcoming
  ├── search_team_id(team) → discover Flashscore team ID
  └── _driver_get() → singleton Edge with 2min idle timeout + threading.Lock

wiki_scraper.py (220 lines, Wikipedia, unlimited)
  ├── get_league_matches(league) → match results from league pages
  ├── get_league_standings(league) → standings table
  ├── get_team_matches(team) → filter by team
  └── get_wc2026_group_matches() → World Cup 2026 group results

## Data Flow (priority order)
1. TEAM_DB (static defaults, 260 teams)
2. API-Football (30min cache, 100req/day)
3. TheSportsDB (unlimited, team IDs only)
4. Flashscore/Edge (unlimited, form + match data, 30min cache)
5. Wikipedia (unlimited, league results)

## Key Files
- prediction_engine.py (~1684 lines) — ALL logic in one file
- edge_scraper.py (222 lines) — Flashscore via Edge WebDriver
- wiki_scraper.py (220 lines) — Wikipedia league data
- app.py (204 lines) — Flask server
- templates/result.html — neon cyberpunk UI (RTL, Orbitron+Tajawal)
- api_cache.db — SQLite persistent cache (7-day TTL)

## Databases
- api_cache.db: URL→JSON cache for all API calls (7-day TTL)
- scrape_cache.db: Flashscore page cache (edge_scraper)
- wikipedia.db: Wikipedia page cache (wiki_scraper)
- evaluation.db: prediction tracking + accuracy evaluation

## Environment Variables
- API_SPORT_KEY (API-Football, 100req/day)
- FOOTBALL_DATA_API_KEY (football-data.org)
- BSD_API_KEY (sports.bzzoiro.com)
- ODDS_API_KEY (the-odds-api.com)
- AGENTROUTER_KEY (deepseek via AgentRouter)
- GROQ_KEY (llama via Groq, no key needed)

## All Recent Changes (June 11 2026)
### Feature: Flashscore integration
- edge_scraper.py: get_team_form() uses <span> for scores (not <div>)
- prediction_engine: import edge_scraper + fallback in get_live_team_data()
- Source shows "flashscore" in UI when active

### Bug fixes
1. compute_features() now adds 'source' key (was missing → always "database")
2. data_source in analysis uses features.get('source') not hardcoded
3. sources.stats_home/away uses source_home/source_away from each team
4. Removed dead code (home_divs/away_divs unused vars)
5. API keys use setdefault() for env var priority
6. Edge driver wrapped in threading.Lock() for thread safety
7. update_ticket uses daemon=False to avoid duplicate threads

### Flashscore Team IDs (50 known)
FLASH_ID dict in edge_scraper.py
- Working: England, Spain, Brazil, Argentina, South Korea, etc.
- Broken: Mexico (o6ihcnkd), South Africa (w2ijyvlr) — 404 pages

## Current Prediction Example
England vs Brazil (Flashscore data):
- England: 8W 1D 1L, GF=24 GA=2, form=83%
- Brazil: 6W 1D 3L, GF=25 GA=11, form=63%
- Source: flashscore / flashscore
- Server: http://127.0.0.1:5000 — Python 3.14.5, Edge 149

## To Continue Development
1. Fix Mexico/South Africa Flashscore IDs (search_team_id)
2. Add remaining 192 team IDs to FLASH_ID
3. Improve get_live_matches() to use HTML class selectors
4. Move hardcoded API keys to .env file
5. Add probability calibration (logit transform on odds)
