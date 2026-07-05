#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: Betfair Exchange — liquidity & sharp money        ▓
▓  Uses Betfair API (free tier) to get exchange prices, volumes,           ▓
▓  track sharp money movement across major leagues                          ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, hmac, hashlib, base64
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlencode

from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    BETFAIR_CONFIG, BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD,
    BETFAIR_CERT_PATH, BETFAIR_CERT_PASSWORD,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db, PROJECT_ROOT,
)

# ─── Constants ───────────────────────────────────────────────────────────────
BASE = BETFAIR_CONFIG.base_url
RATE_LIMITER = get_rate_limiter('betfair', 60)
LOG_FILE = LOGS_DIR / 'betfair.log'
CHECKPOINT_KEY = 'betfair'

# Betfair API endpoints
IDENTITY_URL = 'https://identitysso.betfair.com/api/login'
LIST_EVENTS_URL = f'{BASE}/listEvents/'
LIST_MARKET_CATALOGUE = f'{BASE}/listMarketCatalogue/'
LIST_MARKET_BOOK = f'{BASE}/listMarketBook/'

# ─── Logging ─────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [betfair] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('betfair', level, msg)


# ─── Authentication ─────────────────────────────────────────────────────────
class BetfairAuth:
    """Handle Betfair API authentication with session token management."""

    def __init__(self):
        self.app_key = BETFAIR_APP_KEY or 'YOUR_APP_KEY'
        self.username = BETFAIR_USERNAME or 'YOUR_USERNAME'
        self.password = BETFAIR_PASSWORD or 'YOUR_PASSWORD'
        self.cert_path = BETFAIR_CERT_PATH if os.path.exists(BETFAIR_CERT_PATH) else None
        self.cert_password = BETFAIR_CERT_PASSWORD
        self.session_token = None
        self.token_expiry = 0

    def login(self) -> bool:
        """Login to Betfair API and get session token."""
        if time.time() < self.token_expiry:
            return True

        try:
            headers = {
                'X-Application': self.app_key,
                'Content-Type': 'application/x-www-form-urlencoded',
            }

            data = {
                'username': self.username,
                'password': self.password,
            }

            cert = None
            if self.cert_path and os.path.exists(self.cert_path):
                cert = (self.cert_path, self.cert_password if self.cert_password else '')

            r = curl_requests.post(
                IDENTITY_URL,
                headers=headers,
                data=data,
                cert=cert,
                timeout=30,
            )

            if r.status_code == 200:
                resp = r.json()
                if resp.get('loginStatus') == 'SUCCESS':
                    self.session_token = resp.get('sessionToken')
                    self.token_expiry = time.time() + 3600  # 1 hour
                    _log('Successfully logged in to Betfair API')
                    return True
                else:
                    _log(f'Betfair login failed: {resp.get("loginStatus", "UNKNOWN")}', 'ERROR')
                    return False
            else:
                _log(f'Betfair login HTTP {r.status_code}', 'ERROR')
                return False

        except Exception as e:
            _log(f'Betfair login error: {e}', 'ERROR')
            return False

    def get_headers(self) -> Dict:
        """Get API headers with auth token."""
        return {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token or '',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def ensure_auth(self) -> bool:
        """Ensure we have a valid session token."""
        if self.session_token and time.time() < self.token_expiry:
            return True
        return self.login()


# ─── Global auth instance ────────────────────────────────────────────────────
_auth = BetfairAuth()


# ─── API helpers ─────────────────────────────────────────────────────────────
def _api_post(endpoint: str, params: Dict) -> Optional[Dict]:
    """Make an authenticated POST request to Betfair API."""
    if not _auth.ensure_auth():
        return None

    with RATE_LIMITER:
        try:
            r = curl_requests.post(
                endpoint,
                headers=_auth.get_headers(),
                json=params,
                timeout=BETFAIR_CONFIG.timeout,
            )
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 401:
                # Token expired — retry once
                _log('Token expired, re-authenticating...', 'WARN')
                _auth.session_token = None
                if _auth.login():
                    # Retry this request
                    r = curl_requests.post(
                        endpoint, headers=_auth.get_headers(),
                        json=params, timeout=BETFAIR_CONFIG.timeout,
                    )
                    if r.status_code == 200:
                        return r.json()
                return None
            else:
                _log(f'API error {r.status_code} for {endpoint}', 'WARN')
                return None
        except Exception as e:
            _log(f'API request error: {e}', 'ERROR')
            return None


# ─── Betfair Event IDs (football) ────────────────────────────────────────────
FOOTBALL_EVENT_TYPE_ID = '1'  # Soccer

# Map our leagues to Betfair competition IDs (approximate)
BETFAIR_COMPETITIONS = {
    'GB1': {'id': '117', 'name': 'English Premier League'},
    'GB2': {'id': '119', 'name': 'English Championship'},
    'ES1': {'id': '129', 'name': 'Spanish La Liga'},
    'L1': {'id': '55', 'name': 'German Bundesliga'},
    'IT1': {'id': '131', 'name': 'Italian Serie A'},
    'FR1': {'id': '133', 'name': 'French Ligue 1'},
    'NL1': {'id': '135', 'name': 'Dutch Eredivisie'},
    'PO1': {'id': '137', 'name': 'Portuguese Liga NOS'},
    'TR1': {'id': '139', 'name': 'Turkish Super Lig'},
    'SC1': {'id': '143', 'name': 'Scottish Premiership'},
    'BE1': {'id': '145', 'name': 'Belgian Jupiler League'},
    'MLS1': {'id': '163', 'name': 'MLS'},
    'BR1': {'id': '225', 'name': 'Brazilian Serie A'},
    'AR1': {'id': '227', 'name': 'Argentine Primera Division'},
    'MX1': {'id': '273', 'name': 'Mexican Liga MX'},
}


# ─── Market fetching ─────────────────────────────────────────────────────────
def get_competition_markets(competition_id: str) -> Optional[List[Dict]]:
    """Get all upcoming matches for a competition with their market IDs."""
    params = {
        'filter': {
            'eventTypeIds': [FOOTBALL_EVENT_TYPE_ID],
            'competitionIds': [competition_id],
            'marketCountries': ['GB', 'ES', 'DE', 'IT', 'FR'],
            'marketTypeCodes': ['MATCH_ODDS'],
            'marketStartTime': {
                'from': datetime.now().strftime('%Y-%m-%dT00:00:00Z'),
                'to': (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%dT23:59:59Z'),
            },
        },
        'maxResults': '200',
        'marketProjection': [
            'COMPETITION',
            'EVENT',
            'MARKET_DESCRIPTION',
            'RUNNER_DESCRIPTION',
        ],
        'sort': 'FIRST_TO_START',
    }

    result = _api_post(LIST_MARKET_CATALOGUE, params)
    if not result:
        return None

    return result


def get_market_prices(market_ids: List[str]) -> Optional[List[Dict]]:
    """Get current prices for a list of market IDs.

    Returns price data including:
    - Available to back/lay
    - Total matched volume
    - Last price traded
    """
    params = {
        'marketIds': market_ids,
        'priceProjection': {
            'priceData': ['EX_BEST_OFFERS', 'EX_TRADED_VOL', 'SP_AVAILABLE'],
            'virtualise': True,
            'rolloverStakes': True,
        },
        'orderProjection': 'EXECUTABLE',
        'matchProjection': 'ROLLED_UP_BY_AVG_PRICE',
    }

    result = _api_post(LIST_MARKET_BOOK, params)
    return result


# ─── DB ─────────────────────────────────────────────────────────────────────
def _ensure_tables():
    """Ensure Betfair tables exist."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS betfair_markets (
            market_id TEXT PRIMARY KEY,
            competition_id TEXT,
            competition_name TEXT,
            event_name TEXT,
            event_date TEXT,
            home_team TEXT,
            away_team TEXT,
            market_type TEXT,
            status TEXT,
            total_matched REAL,
            fetched_at REAL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS betfair_odds_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            runner_name TEXT,
            runner_id INTEGER,
            back_price REAL,
            back_volume REAL,
            lay_price REAL,
            lay_volume REAL,
            last_traded_price REAL,
            total_matched REAL,
            timestamp REAL,
            FOREIGN KEY(market_id) REFERENCES betfair_markets(market_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS betfair_historical_prices (
            market_id TEXT,
            runner_id INTEGER,
            back_price REAL,
            lay_price REAL,
            total_matched REAL,
            timestamp REAL,
            PRIMARY KEY (market_id, runner_id, timestamp)
        )
    ''')
    conn.commit()
    conn.close()


# ─── Main harvest ──────────────────────────────────────────────────────────
def harvest_live_markets(checkpoint: bool = True) -> Dict:
    """Fetch live match odds from Betfair Exchange.

    Returns stats dict.
    """
    _ensure_tables()

    start_time = time.time()
    total_markets = 0
    total_runners = 0
    errors = 0

    if not _auth.ensure_auth():
        _log('Cannot authenticate with Betfair API', 'ERROR')
        return {'error': 'authentication_failed'}

    conn = get_db()
    conn.execute('BEGIN TRANSACTION')
    now = time.time()

    for comp_id, comp_info in BETFAIR_COMPETITIONS.items():
        _log(f'Fetching markets for {comp_info["name"]}...')

        markets = get_competition_markets(comp_id)
        if not markets:
            _log(f'No markets for {comp_info["name"]}', 'WARN')
            continue

        for market in markets:
            try:
                market_data = market.get('marketCatalogue', {})
                market_id = market_data.get('marketId')
                if not market_id:
                    continue

                event = market_data.get('event', {})
                event_name = event.get('name', '')
                event_date = event.get('openDate', '')

                # Parse teams from event name (e.g., "Arsenal vs Chelsea")
                home_team = ''
                away_team = ''
                if ' vs ' in event_name:
                    parts = event_name.split(' vs ')
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()

                # Get market description
                desc = market_data.get('description', {})
                market_type = desc.get('marketType', 'UNKNOWN')

                # Runners
                runners = market_data.get('runners', [])

                # Insert market
                conn.execute('''
                    INSERT OR REPLACE INTO betfair_markets
                        (market_id, competition_id, competition_name,
                         event_name, event_date, home_team, away_team,
                         market_type, status, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    market_id, comp_id, comp_info['name'],
                    event_name, event_date, home_team, away_team,
                    market_type, 'OPEN', now,
                ))
                total_markets += 1

                # Store runner info
                for runner in runners:
                    conn.execute('''
                        INSERT OR REPLACE INTO betfair_odds_snapshots
                            (market_id, runner_name, runner_id, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (market_id, runner.get('runnerName', ''),
                          runner.get('selectionId', 0), now))
                    total_runners += 1

            except Exception as e:
                _log(f'Error processing market: {e}', 'ERROR')
                errors += 1
                continue

    # Now fetch prices for ALL markets
    market_ids = []
    try:
        cur = conn.execute(
            'SELECT market_id FROM betfair_markets WHERE status = ?',
            ('OPEN',)
        )
        market_ids = [r[0] for r in cur.fetchall()]
    except Exception:
        pass

    if market_ids:
        _log(f'Fetching prices for {len(market_ids)} markets...')

        # Batch in groups of 25 (API limit)
        for i in range(0, len(market_ids), 25):
            batch = market_ids[i:i + 25]
            prices = get_market_prices(batch)

            if prices:
                for price_data in prices:
                    try:
                        market_id = price_data.get('marketId', '')
                        total_matched = price_data.get('totalMatched', 0)

                        conn.execute('''
                            UPDATE betfair_markets
                            SET total_matched = ?, status = ?
                            WHERE market_id = ?
                        ''', (total_matched, price_data.get('status', 'UNKNOWN'), market_id))

                        # Update runners with prices
                        for runner in price_data.get('runners', []):
                            runner_id = runner.get('selectionId', 0)
                            runner_name = runner.get('runnerName', '')
                            last_price = runner.get('lastPriceTraded')

                            # Best back/lay prices
                            ex = runner.get('ex', {})
                            available_back = ex.get('availableToBack', [])
                            available_lay = ex.get('availableToLay', [])

                            back_price = available_back[0].get('price') if available_back else None
                            back_volume = available_back[0].get('size') if available_back else None
                            lay_price = available_lay[0].get('price') if available_lay else None
                            lay_volume = available_lay[0].get('size') if available_lay else None

                            conn.execute('''
                                UPDATE betfair_odds_snapshots
                                SET back_price = ?, back_volume = ?,
                                    lay_price = ?, lay_volume = ?,
                                    last_traded_price = ?,
                                    total_matched = ?
                                WHERE market_id = ? AND runner_id = ?
                            ''', (
                                back_price, back_volume,
                                lay_price, lay_volume,
                                last_price, total_matched,
                                market_id, runner_id,
                            ))

                            # Also save to historical
                            conn.execute('''
                                INSERT OR REPLACE INTO betfair_historical_prices
                                    (market_id, runner_id, back_price, lay_price,
                                     total_matched, timestamp)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                market_id, runner_id,
                                back_price, lay_price,
                                total_matched, now,
                            ))

                    except Exception as e:
                        _log(f'Price update error: {e}', 'ERROR')
                        errors += 1

    conn.commit()
    conn.close()

    duration = time.time() - start_time
    _log(f'Betfair harvest: {total_markets} markets, {total_runners} runners, '
         f'{errors} errors, {duration:.1f}s')

    if checkpoint:
        save_checkpoint(CHECKPOINT_KEY, {
            'last_run': now,
            'markets': total_markets,
        }, total_markets + total_runners, errors)

    return {
        'source': 'betfair',
        'markets': total_markets,
        'runners': total_runners,
        'errors': errors,
        'duration_seconds': duration,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Betfair Exchange odds harvester')
    args = parser.parse_args()

    result = harvest_live_markets()
    print(json.dumps(result, indent=2))
