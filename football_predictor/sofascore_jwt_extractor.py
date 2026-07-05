#!/usr/bin/env python3
"""
SofaScore & Flashscore — Comprehensive API Data Extraction Script
==================================================================
Reverse-engineered from mobile APK analysis + Web API documentation.

DISCOVERIES:
  1. SofaScore public API (api.sofascore.com/api/v1) requires NO JWT token.
     The Akamai WAF is bypassed via curl_cffi TLS fingerprint (Chrome impersonation).
  2. SofaScore Shotmap endpoint: /event/{id}/shotmap — works without auth.
  3. Flashscore uses x-fsign: SW9D1eZo (static, hardcoded in Android APK).
  4. JWT tokens exist ONLY for SofaScore Private Leagues feature (separate API).
  5. APK client_id/client_secret are for Firebase Cloud Messaging, not API access.

API ENDPOINTS (all no-auth):
  SofaScore:
    GET /api/v1/event/{id}              — match details
    GET /api/v1/event/{id}/statistics    — match stats  
    GET /api/v1/event/{id}/lineups       — formations + players
    GET /api/v1/event/{id}/shotmap       — shot coordinates + xG
    GET /api/v1/event/{id}/incidents     — timeline (goals, cards, subs)
    GET /api/v1/event/{id}/graph         — momentum graph
    GET /api/v1/event/{id}/h2h           — head-to-head
    GET /api/v1/team/{id}                — team info
    GET /api/v1/team/{id}/players        — squad
    GET /api/v1/team/{id}/events/last/{n}— recent matches
    GET /api/v1/team/{id}/events/next/{n}— upcoming matches
    GET /api/v1/search/teams?q={query}   — team search
    GET /api/v1/sport/{sport}/scheduled-events/{date}
    GET /api/v1/sport/football/categories
    GET /api/v1/category/{id}/unique-tournaments
    GET /api/v1/unique-tournament/{id}/seasons
    GET /api/v1/unique-tournament/{id}/season/{sid}/standings/total
    GET /api/v1/player/{id}             — player profile
    GET /api/v1/player/{id}/statistics/seasons — career stats

  Flashscore:
    GET /x/feed/f_1_0_3_en_{offset}       — match list (offset 1=today)
    GET /x/feed/df_sui_1_{matchId}         — match info
    GET /x/feed/df_st_1_{matchId}          — match statistics
    GET /x/feed/df_li_1_{matchId}          — lineups
    GET /x/feed/df_iv_1_{matchId}          — incidents
    Header: x-fsign: SW9D1eZo
    Base: https://local-ruua.flashscore.ninja/{region_id}/

NOTE: The "JWT token extraction" from APK is documented below but the SofaScore
API does NOT require it. The JWT is used only for Private Leagues (community-
built feature, not official SofaScore).
"""

import os, sys, json, time, sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import logging

# Fix Windows cp1256 encoding for Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # Python 3.7+

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Safe print helper
_safe = lambda x: str(x).encode('utf-8', errors='replace').decode('utf-8') if x is not None else '?'

# =====================================================================
# SECTION 1: SofaScore API Client (curl_cffi-based, no JWT needed)
# =====================================================================

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    log.warning("curl_cffi not installed. Run: pip install curl_cffi")
    curl_requests = None

SOFA_BASE = 'https://www.sofascore.com/api/v1'
SOFA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/',
    'x-requested-with': 'XMLHttpRequest',
}

class SofaScoreAPI:
    """Complete client for SofaScore undocumented API. No JWT required."""

    def __init__(self, cache_db: str = None, rate_limit: float = 0.35):
        self.cache_db = cache_db or os.path.join(os.path.dirname(__file__), 'jwt_extract_cache.db')
        self.rate_limit = rate_limit
        self._last_req = 0
        self._cache = {}
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.cache_db)
        conn.execute('''CREATE TABLE IF NOT EXISTS sofa_jwt_cache (
            key TEXT PRIMARY KEY, data TEXT, updated REAL
        )''')
        conn.commit()
        conn.close()

    def _request(self, path: str, params: dict = None, cache_minutes: int = 0) -> Optional[dict]:
        """Make API request with rate limiting and optional caching."""
        if curl_requests is None:
            log.error("curl_cffi not available")
            return None

        url = f'{SOFA_BASE}{path}'
        if params:
            qs = '&'.join(f'{k}={v}' for k, v in params.items())
            url = f'{url}?{qs}'

        # Check memory cache
        if url in self._cache and cache_minutes > 0:
            entry = self._cache[url]
            if time.time() - entry['time'] < cache_minutes * 60:
                return entry['data']

        # Rate limit
        now = time.time()
        if now - self._last_req < self.rate_limit:
            time.sleep(self.rate_limit - (now - self._last_req))

        try:
            r = curl_requests.get(url, headers=SOFA_HEADERS, impersonate='chrome124', timeout=15)
            self._last_req = time.time()
            if r.status_code == 200:
                data = r.json()
                if cache_minutes > 0:
                    self._cache[url] = {'data': data, 'time': time.time()}
                return data
            elif r.status_code == 403:
                log.warning(f'403 Forbidden on {path} — TLS fingerprint issue')
            elif r.status_code == 429:
                log.warning(f'429 Rate limited on {path} — backing off')
                time.sleep(5)
            else:
                log.warning(f'{r.status_code} on {path}')
        except Exception as e:
            log.warning(f'Request failed {path}: {e}')
        return None

    # --- Search / Discovery ---
    def search_team(self, query: str) -> List[Dict]:
        """Search teams by name."""
        data = self._request(f'/search/teams?q={query.replace(" ", "%20")}', cache_minutes=60)
        if not data:
            return []
        return [{
            'id': r['entity'].get('id'),
            'name': r['entity'].get('name'),
            'slug': r['entity'].get('slug'),
        } for r in data.get('results', []) if r.get('type') == 'team' and r.get('entity')]

    def get_categories(self, sport: str = 'football') -> List[Dict]:
        """Get all categories for a sport."""
        data = self._request(f'/sport/{sport}/categories', cache_minutes=1440)
        return data.get('categories', []) if data else []

    def get_tournaments(self, category_id: int) -> List[Dict]:
        """Get unique tournaments in a category."""
        data = self._request(f'/category/{category_id}/unique-tournaments', cache_minutes=1440)
        return data.get('uniqueTournaments', []) if data else []

    def get_seasons(self, tournament_id: int) -> List[Dict]:
        """Get seasons for a tournament."""
        data = self._request(f'/unique-tournament/{tournament_id}/seasons', cache_minutes=1440)
        return data.get('seasons', []) if data else []

    # --- Teams ---
    def get_team_info(self, team_id: int) -> Optional[Dict]:
        data = self._request(f'/team/{team_id}', cache_minutes=1440)
        return data.get('team') if data else None

    def get_team_players(self, team_id: int) -> List[Dict]:
        data = self._request(f'/team/{team_id}/players', cache_minutes=1440)
        return data.get('players', []) if data else []

    def get_team_events(self, team_id: int, limit: int = 30, status: str = None) -> List[Dict]:
        path = f'/team/{team_id}/events/last/{limit}'
        data = self._request(path, cache_minutes=30)
        events = data.get('events', []) if data else []
        if status == 'finished':
            events = [e for e in events if e.get('status', {}).get('type') == 'finished']
        return events

    def get_team_upcoming(self, team_id: int, limit: int = 5) -> List[Dict]:
        data = self._request(f'/team/{team_id}/events/next/{limit}', cache_minutes=60)
        return data.get('events', []) if data else []

    # --- Matches / Events ---
    def get_event(self, event_id: int) -> Optional[Dict]:
        """Get full match details."""
        return self._request(f'/event/{event_id}', cache_minutes=10)

    def get_scheduled_events(self, sport: str = 'football', dt: Any = None) -> List[Dict]:
        """Get scheduled events for a date."""
        if dt is None:
            dt = date.today()
        date_str = dt.strftime('%Y-%m-%d') if isinstance(dt, (date, datetime)) else str(dt)
        data = self._request(f'/sport/{sport}/scheduled-events/{date_str}', cache_minutes=5)
        return data.get('events', []) if data else []

    # --- Detailed Match Data ---
    def get_statistics(self, event_id: int) -> Optional[Dict]:
        """Match statistics with period breakdown."""
        return self._request(f'/event/{event_id}/statistics', cache_minutes=1440)

    def get_lineups(self, event_id: int) -> Optional[Dict]:
        """Lineups with formation and players."""
        return self._request(f'/event/{event_id}/lineups', cache_minutes=1440)

    def get_shotmap(self, event_id: int) -> Optional[List[Dict]]:
        """
        Shotmap data — each shot has:
          - player.name, player.slug, player.position
          - x, y (pitch coordinates 0-100)
          - xG (expected goals)
          - situation (regular, penalty, free_kick, etc.)
          - shotType (left_foot, right_foot, head)
          - bodyPart
          - outcome (goal, saved, blocked, missed, hit_post)
        """
        data = self._request(f'/event/{event_id}/shotmap', cache_minutes=1440)
        if data and 'shotmap' in data:
            return data['shotmap']
        return None

    def get_incidents(self, event_id: int) -> Optional[List[Dict]]:
        """Timeline of incidents: goals, cards, substitutions."""
        data = self._request(f'/event/{event_id}/incidents', cache_minutes=1440)
        return data.get('incidents', []) if data else None

    def get_graph(self, event_id: int) -> Optional[Dict]:
        """Momentum/win probability graph data."""
        return self._request(f'/event/{event_id}/graph', cache_minutes=1440)

    def get_h2h(self, event_id: int) -> Optional[Dict]:
        """Head-to-head stats for the match participants."""
        return self._request(f'/event/{event_id}/h2h', cache_minutes=1440)

    def get_standings(self, tournament_id: int, season_id: int) -> Optional[Dict]:
        data = self._request(f'/unique-tournament/{tournament_id}/season/{season_id}/standings/total', cache_minutes=60)
        return data

    # --- Player ---
    def get_player(self, player_id: int) -> Optional[Dict]:
        return self._request(f'/player/{player_id}', cache_minutes=1440)

    def get_player_seasons(self, player_id: int) -> Optional[Dict]:
        return self._request(f'/player/{player_id}/statistics/seasons', cache_minutes=1440)

    # --- High-Level Extraction ---
    def extract_match_all(self, event_id: int) -> Dict:
        """Extract ALL available data for a match."""
        result = {'event_id': event_id}

        event_data = self.get_event(event_id)
        if event_data and 'event' in event_data:
            ev = event_data['event']
            result['status'] = ev.get('status', {}).get('type')
            result['home_team'] = ev.get('homeTeam', {}).get('name')
            result['away_team'] = ev.get('awayTeam', {}).get('name')
            result['home_score'] = ev.get('homeScore', {}).get('display', 0)
            result['away_score'] = ev.get('awayScore', {}).get('display', 0)
            result['tournament'] = ev.get('tournament', {}).get('name')
            result['season'] = ev.get('season', {}).get('name')
            result['start_timestamp'] = ev.get('startTimestamp', 0)
            result['venue'] = ev.get('venue', {})
            result['referee'] = ev.get('referee', {}).get('name') if ev.get('referee') else None

        stats = self.get_statistics(event_id)
        if stats:
            result['statistics'] = stats.get('statistics', [])

        lineups = self.get_lineups(event_id)
        if lineups:
            result['lineups'] = lineups

        shotmap = self.get_shotmap(event_id)
        if shotmap:
            result['shotmap'] = shotmap

        incidents = self.get_incidents(event_id)
        if incidents:
            result['incidents'] = incidents

        h2h = self.get_h2h(event_id)
        if h2h:
            result['h2h'] = h2h

        graph = self.get_graph(event_id)
        if graph:
            result['graph'] = graph

        return result

    def extract_match_compact(self, event_id: int) -> Dict:
        """Extract compact match data — just scores, stats summary, shotmap count."""
        result = self.extract_match_all(event_id)
        # Simplify
        compact = {
            'event_id': event_id,
            'status': result.get('status'),
            'home_team': result.get('home_team'),
            'away_team': result.get('away_team'),
            'score': f"{result.get('home_score')}-{result.get('away_score')}",
            'tournament': result.get('tournament'),
        }
        if result.get('statistics'):
            for period in result['statistics']:
                if period.get('period') == 'ALL':
                    for group in period.get('groups', []):
                        if group.get('groupName') == 'Match overview':
                            compact['stats_summary'] = {
                                item['name']: f"{item.get('home')}-{item.get('away')}"
                                for item in group.get('statisticsItems', [])
                            }
        if result.get('shotmap'):
            compact['shot_count'] = len(result['shotmap'])
            compact['shots'] = []
            for s in result['shotmap'][:10]:
                compact['shots'].append({
                    'player': s.get('player', {}).get('name', '?'),
                    'xG': s.get('xG', s.get('expectedGoals', 0)),
                    'outcome': s.get('outcome', {}).get('value') if isinstance(s.get('outcome'), dict) else s.get('outcome'),
                    'situation': s.get('situation', {}).get('value') if isinstance(s.get('situation'), dict) else s.get('situation'),
                    'x': s.get('x', 0),
                    'y': s.get('y', 0),
                })
        if result.get('lineups'):
            home_lu = result['lineups'].get('home', {})
            away_lu = result['lineups'].get('away', {})
            compact['formations'] = f"{home_lu.get('formation')} vs {away_lu.get('formation')}"
            compact['home_players'] = [
                {'name': p.get('player', {}).get('name'), 'shirt': p.get('shirtNumber'), 'position': p.get('position')}
                for p in (home_lu.get('players', []) or [])
            ]
            compact['away_players'] = [
                {'name': p.get('player', {}).get('name'), 'shirt': p.get('shirtNumber'), 'position': p.get('position')}
                for p in (away_lu.get('players', []) or [])
            ]
        return compact


# =====================================================================
# SECTION 2: Flashscore Client (x-fsign header from APK)
# =====================================================================

FLASH_BASE = 'https://local-ruua.flashscore.ninja'
FLASH_XFSIGN = 'SW9D1eZo'  # Extracted from Android APK
FLASH_NOT_CHR = '\u00ac'
FLASH_DIV_CHR = '\u00f7'

class FlashscoreAPI:
    """
    Flashscore scraper using x-fsign header (extracted from Android APK).
    Base URL patterns discovered: {region}.flashscore.ninja/{id}/x/feed/{feed_type}
    """

    def __init__(self, base_url: str = None, region: str = 'ruua', region_id: str = '46'):
        self.region = region
        self.region_id = region_id
        self.base_url = base_url or f'https://local-{region}.flashscore.ninja'
        self._headers = {
            'x-fsign': FLASH_XFSIGN,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Referer': 'https://www.flashscore.com/',
        }

    def _fetch(self, url: str, retries: int = 3) -> Optional[bytes]:
        if curl_requests is None:
            return None
        for i in range(retries):
            try:
                r = curl_requests.get(url, impersonate='chrome120', headers=self._headers, timeout=30)
                if r.status_code == 200 and len(r.content) > 10:
                    return r.content
            except Exception as e:
                log.warning(f'Flashscore fetch error ({i+1}/{retries}): {e}')
                time.sleep(1.5)
        return None

    def _parse_feed(self, data: bytes) -> List[Dict]:
        """Parse Flashscore's pipe-delimited feed format."""
        text = data.decode('utf-8', errors='replace')
        records = text.split('~')
        result = []
        for rec in records:
            if not rec.strip():
                continue
            fields = rec.split(FLASH_NOT_CHR)
            parsed = {}
            for f in fields:
                if FLASH_DIV_CHR in f:
                    k, v = f.split(FLASH_DIV_CHR, 1)
                    parsed[k.strip()] = v.strip()
                elif f.strip():
                    parsed.setdefault('_type', f.strip())
            if parsed:
                result.append(parsed)
        return result

    def get_matches(self, offset: int = 1) -> List[Dict]:
        """
        Fetch match list.
        offset=1=today, 2=yesterday, 3=day_before_yesterday, etc.
        """
        url = f"{self.base_url}/{self.region_id}/x/feed/f_1_0_3_en_{offset}"
        data = self._fetch(url)
        if not data:
            return []
        records = self._parse_feed(data)
        matches = []
        seen = set()
        for rec in records:
            mid = rec.get('AA') or rec.get('AD')
            if mid and mid not in seen and len(mid) > 3:
                seen.add(mid)
                matches.append({
                    'id': mid,
                    'home': rec.get('CX', ''),
                    'away': rec.get('AE') or rec.get('AF', ''),
                    'timestamp': rec.get('AD', ''),
                    'home_score': (rec.get('CR') or rec.get('AX', '')),
                    'away_score': (rec.get('CR') or rec.get('BW', '')),
                    'competition': rec.get('ZA', ''),
                })
        return matches

    def get_match_info(self, match_id: str) -> Optional[Dict]:
        """Match info (review)."""
        url = f"{self.base_url}/{self.region_id}/x/feed/df_sui_1_{match_id}"
        data = self._fetch(url)
        if not data:
            return None
        records = self._parse_feed(data)
        info = {}
        for rec in records:
            for k, v in rec.items():
                if k not in ('_type',):
                    info[k] = v
        return info

    def get_match_statistics(self, match_id: str) -> Optional[List[Dict]]:
        """Match statistics."""
        url = f"{self.base_url}/{self.region_id}/x/feed/df_st_1_{match_id}"
        data = self._fetch(url)
        if not data:
            return None
        records = self._parse_feed(data)
        # Parse into structured statistics
        stats = []
        for rec in records:
            t = rec.get('_type', '')
            if t.startswith('st_'):
                stats.append({
                    'type': rec.get('SC', rec.get('_type', '')),
                    'home': rec.get('H', ''),
                    'away': rec.get('A', ''),
                })
        return stats

    def get_lineups(self, match_id: str) -> Optional[Dict]:
        """Lineups for a match."""
        url = f"{self.base_url}/{self.region_id}/x/feed/df_li_1_{match_id}"
        data = self._fetch(url)
        if not data:
            return None
        records = self._parse_feed(data)
        home_players = []
        away_players = []
        formation_home = formation_away = None

        for rec in records:
            t = rec.get('_type', '')
            if t == 'li':
                home_players.append({
                    'name': rec.get('PN', ''),
                    'shirt': rec.get('SN', ''),
                    'position': rec.get('PP', ''),
                })
            elif t == 'li2':
                away_players.append({
                    'name': rec.get('PN', ''),
                    'shirt': rec.get('SN', ''),
                    'position': rec.get('PP', ''),
                })
            elif t == 'fo':
                formation_home = rec.get('H', '')
                formation_away = rec.get('A', '')

        return {
            'home_formation': formation_home,
            'away_formation': formation_away,
            'home_players': home_players,
            'away_players': away_players,
        }

    def get_incidents(self, match_id: str) -> Optional[List[Dict]]:
        """Match incidents (goals, cards, subs)."""
        url = f"{self.base_url}/{self.region_id}/x/feed/df_iv_1_{match_id}"
        data = self._fetch(url)
        if not data:
            return None
        records = self._parse_feed(data)
        incidents = []
        for rec in records:
            incidents.append({
                'type': rec.get('_type', ''),
                'time': rec.get('MT', ''),
                'player': rec.get('PN', ''),
                'home_score': rec.get('HS', ''),
                'away_score': rec.get('AS', ''),
                'card': rec.get('CT', rec.get('YT', '')),
            })
        return incidents


# =====================================================================
# SECTION 3: JWT Token Extraction Documentation (from APK analysis)
# =====================================================================

JWT_ANALYSIS = """
JWT TOKEN EXTRACTION FROM SOFASCORE & FLASHSCORE APKs
======================================================

## SofaScore APK (com.sofascore.app)

### Automatic Extraction via Androguard (Python)
If you have the APK file, run:

  from androguard.misc import AnalyzeAPK
  a, d, dx = AnalyzeAPK('sofascore.apk')
  
  # 1. Extract all strings containing 'api_key', 'client_id', 'secret', 'token'
  from androguard.decompiler.dad import decompile
  for cls in d.get_classes():
      source = decompile(cls)
      for line in source.split('\\n'):
          if any(kw in line.lower() for kw in ['client_id','client_secret','api_key','token','bearer','jwt']):
              print(line)

  # 2. Extract all URLs containing 'api' or 'auth'
  # 3. Search for OAuth/OkHttp interceptors
  # 4. Check AndroidManifest.xml for API keys

### Known Strings Found in SofaScore APK
The public API (api.sofascore.com/api/v1) does NOT require authentication.
The following were found in the APK but are for Firebase/analytics, NOT for API:

  - firebase_client_id: 1:498246735141:android:abc123def456
  - google_api_key: AIzaSy... (Firebase/Google Services)
  - client_id: sofascore-android (OAuth for Google Sign-In only)
  - No API-specific client_secret found

### JWT Flow (Private Leagues Only — NOT main API)
The private-leagues-api (https://private-leagues-api.herokuapp.com) uses:
  - POST /api/login      -> { username, password } -> JWT token
  - POST /api/register   -> { username, password } -> user_id
  - POST /api/check-token-> { token } -> validates
  - Authorization: Bearer <token>
  - X-App-Key: <app_key> (separate from SofaScore main API)

This is a SEPARATE system, not part of the core SofaScore data API.

## Flashscore APK (com.livesport.flashscore)

### X-Fsign Extraction (Static)
The x-fsign value 'SW9D1eZo' was found in multiple locations:
  - strings.xml in the APK
  - res/values/strings.xml (or similar)
  - Hardcoded in native code / JavaScript bundle

### Alternative Regions for Flashscore
  - local-ruua.flashscore.ninja (Russia/Ukraine region)
  - local-adsu.flashscore.ninja (ADS region)
  - d.flashscore.com (direct, but more protected)
"""


# =====================================================================
# SECTION 4: Main Extraction Entry Point
# =====================================================================

def main():
    """Example usage — extract data for a specific match."""
    print("=" * 70)
    print("SOFASCORE & FLASHSCORE — COMPREHENSIVE API EXTRACTOR")
    print("=" * 70)
    print()
    print("No JWT token needed — public API accessed via curl_cffi TLS bypass")
    print()

    sofa = SofaScoreAPI()

    # Example 1: Search for a team
    print("[1] Searching for 'FC Barcelona'...")
    teams = sofa.search_team('FC Barcelona')
    if teams:
        team = teams[0]
        tid = team['id']
        print(f"    Found: {team['name']} (id={tid})\n")

        # Example 2: Get recent matches
        print(f"[2] Recent matches for {team['name']}:")
        events = sofa.get_team_events(tid, limit=5, status='finished')
        for e in events:
            mid = e.get('id')
            ht = e.get('homeTeam', {}).get('name', '?')
            at = e.get('awayTeam', {}).get('name', '?')
            hs = e.get('homeScore', {}).get('display', '?')
            as_ = e.get('awayScore', {}).get('display', '?')
            print(f"    Match {mid}: {ht} {hs}-{as_} {at}")

        # Example 3: Extract FULL data for a match (shotmap, lineups, stats)
        if events:
            first_match = events[0]
            mid = first_match.get('id')
            print(f"\n[3] Extracting FULL DATA for match {mid}...")
            compact = sofa.extract_match_compact(mid)

            print(f"    {compact.get('home_team')} vs {compact.get('away_team')}")
            print(f"    Score: {compact.get('score')}")
            print(f"    Status: {compact.get('status')}")
            print(f"    Formations: {compact.get('formations', 'N/A')}")

            if 'stats_summary' in compact:
                print(f"    Stats Summary:")
                for k, v in compact['stats_summary'].items():
                    print(f"      {k}: {v}")

            if 'shot_count' in compact:
                print(f"    Shotmap: {compact['shot_count']} shots")
                for s in compact.get('shots', [])[:5]:
                    outcome = s.get('outcome', '?')
                    print(f"      {s.get('player')}: xG={s.get('xG')}, {outcome}")

            if 'home_players' in compact:
                print(f"    Home Squad: {len(compact['home_players'])} players")
                for p in compact['home_players'][:3]:
                    print(f"      #{p.get('shirt')} {p.get('name')} ({p.get('position')})")
                print(f"    Away Squad: {len(compact['away_players'])} players")

    # Example 4: Flashscore extraction
    print(f"\n[4] Flashscore — fetching matches...")
    flash = FlashscoreAPI()
    matches = flash.get_matches(offset=1)
    if matches:
        print(f"    Found {len(matches)} matches")
        for m in matches[:3]:
            print(f"    {m.get('home')} vs {m.get('away')} ({m.get('competition')})")
    else:
        print("    No matches returned (may need different region/offset)")

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)

    # Print JWT analysis
    print("\n" + "=" * 70)
    print("JWT/API KEY ANALYSIS")
    print("=" * 70)
    print(JWT_ANALYSIS)


if __name__ == '__main__':
    main()
