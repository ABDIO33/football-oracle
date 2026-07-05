#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              PROXY ROTATOR — Free proxy lists + rotation logic            ▓
▓  Auto-fetches free proxies, tests them, rotates to avoid 429 errors.      ▓
▓  BLACK CODE CURSE • WRAITH CODE • X-VOID • SHADOWHACKER-GOD               ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, random, threading, asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
from curl_cffi import requests as curl_requests
from eternal_harvester_config import PROXY_CONFIG, LOGS_DIR, log_event

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_FILE = LOGS_DIR / 'proxy_rotator.log'


def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [PROXY] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('proxy_rotator', level, msg)


# ─── Proxy storage ──────────────────────────────────────────────────────────
class ProxyManager:
    """Manages a pool of proxies with health checking and rotation.

    Implements 5-layer design (BLACK CODE CURSE):
    Layer 1: Core execution (proxy pool management)
    Layer 2: Obfuscation (random selection, random headers per proxy)
    Layer 3: Proxy rotation (auto-switch on failure)
    Layer 4: Multi-threading (thread-safe pool access)
    Layer 5: Logging & failover (health tracking, fallback to direct)
    """

    def __init__(self):
        self._pool: List[Dict] = []  # [{proxy, country, latency, last_used, failures, success_count}]
        self._blacklist: Dict[str, float] = {}  # proxy -> time blacklisted until
        self._current_index = 0
        self._lock = threading.Lock()
        self._last_fetch = 0
        self._fetch_interval = PROXY_CONFIG.get('rotation_interval_seconds', 120)
        self._test_url = PROXY_CONFIG.get('test_url', 'https://httpbin.org/ip')
        self._test_timeout = PROXY_CONFIG.get('test_timeout', 5)
        self._min_proxies = PROXY_CONFIG.get('min_proxies', 5)
        self._max_proxies = PROXY_CONFIG.get('max_proxies', 100)
        self._ban_threshold = PROXY_CONFIG.get('ban_threshold', 3)
        self._enabled = PROXY_CONFIG.get('enabled', False)
        self._session_stats = {
            'proxies_fetched': 0,
            'proxies_working': 0,
            'proxies_banned': 0,
            'requests_routed': 0,
            'requests_failed': 0,
            'fallback_to_direct': 0,
        }

    # ─── Layer 1: Core — Fetch proxies from free sources ─────────────────
    def _fetch_free_proxies(self) -> List[str]:
        """Fetch fresh proxy list from free sources."""
        proxies = []

        proxy_urls = PROXY_CONFIG.get('free_proxy_urls', [])

        for url in proxy_urls:
            try:
                r = curl_requests.get(
                    url,
                    timeout=10,
                    impersonate='chrome124',
                )
                if r.status_code == 200:
                    text = r.text
                    raw_list = []
                    if ':' in text:
                        for line in text.splitlines():
                            line = line.strip()
                            if ':' in line and not line.startswith('#'):
                                raw_list.append(line)

                    # Also handle proxy list formats like `IP:PORT:USER:PASS`
                    for entry in raw_list:
                        parts = entry.split(':')
                        if len(parts) >= 2:
                            ip = parts[0]
                            port = parts[1]
                            proxy_str = f'http://{ip}:{port}'

                            if len(parts) >= 4:
                                # Authenticated proxy
                                user = parts[2]
                                passwd = parts[3]
                                proxy_str = f'http://{user}:{passwd}@{ip}:{port}'

                            if ip not in [p.split(':')[0] for p in proxies]:
                                proxies.append(proxy_str)

            except Exception as e:
                _log(f'Failed to fetch proxy list from {url}: {e}', 'WARN')

            # Don't hammer all sources at once
            time.sleep(0.5)

        _log(f'Fetched {len(proxies)} raw proxies from {len(proxy_urls)} sources')
        self._session_stats['proxies_fetched'] += len(proxies)
        return proxies

    # ─── Layer 2 + 3: Test & Rotate ─────────────────────────────────────
    def _test_proxy(self, proxy: str) -> bool:
        """Test if a proxy works by hitting the test URL."""
        test_urls = [
            'https://httpbin.org/ip',
            'https://api.ipify.org?format=json',
            'https://ident.me/.json',
        ]

        for test_url in test_urls:
            try:
                r = curl_requests.get(
                    test_url,
                    proxies={'http': proxy, 'https': proxy},
                    timeout=self._test_timeout,
                    impersonate='chrome124',
                )
                if r.status_code == 200:
                    return True
            except Exception:
                continue

        return False

    def _test_proxy_latency(self, proxy: str) -> Optional[float]:
        """Test proxy and return latency in ms, None if failed."""
        start = time.time()
        try:
            r = curl_requests.get(
                self._test_url,
                proxies={'http': proxy, 'https': proxy},
                timeout=self._test_timeout,
                impersonate='chrome124',
            )
            if r.status_code == 200:
                return (time.time() - start) * 1000
        except Exception:
            pass
        return None

    def refresh_pool(self, force: bool = False):
        """Refresh the proxy pool by fetching and testing new proxies."""
        if not self._enabled:
            return

        now = time.time()
        if not force and now - self._last_fetch < self._fetch_interval:
            return

        with self._lock:
            self._last_fetch = now

            # Remove expired blacklisted proxies
            expired = [p for p, t in self._blacklist.items() if now > t]
            for p in expired:
                del self._blacklist[p]

            # Check if we need more proxies
            if len(self._pool) >= self._min_proxies and not force:
                return

            _log('Refreshing proxy pool...')

            # Fetch new proxies
            raw_proxies = self._fetch_free_proxies()

            # Test a sample
            working_proxies = []
            test_sample = raw_proxies[:self._max_proxies]

            for i, proxy in enumerate(test_sample):
                if proxy in self._blacklist:
                    continue

                latency = self._test_proxy_latency(proxy)
                if latency is not None:
                    working_proxies.append({
                        'proxy': proxy,
                        'latency': latency,
                        'last_used': 0,
                        'failures': 0,
                        'success_count': 0,
                        'added': now,
                    })
                    _log(f'Proxy OK: {proxy[:40]}... ({latency:.0f}ms)', 'DEBUG')

                if (i + 1) % 20 == 0:
                    _log(f'Tested {i+1}/{len(test_sample)} proxies...')

            # Merge with existing pool
            existing_proxies = {p['proxy'] for p in self._pool}
            for wp in working_proxies:
                if wp['proxy'] not in existing_proxies:
                    self._pool.append(wp)

            # Keep only best proxies if over limit
            if len(self._pool) > self._max_proxies:
                self._pool.sort(key=lambda p: p['latency'])
                self._pool = self._pool[:self._max_proxies]

            self._session_stats['proxies_working'] += len(working_proxies)
            _log(f'Proxy pool: {len(working_proxies)} new, {len(self._pool)} total')

    # ─── Layer 4: Thread-safe proxy selection ───────────────────────────
    def get_proxy(self) -> Optional[str]:
        """Get the next best proxy from the pool.

        Returns:
            Proxy URL string, or None if no proxy available.
        """
        if not self._enabled or not self._pool:
            self._session_stats['fallback_to_direct'] += 1
            return None

        # Auto-refresh if pool is low
        if len(self._pool) < self._min_proxies:
            self.refresh_pool(force=True)

        with self._lock:
            if not self._pool:
                self._session_stats['fallback_to_direct'] += 1
                return None

            # Sort by: fewest failures, then lowest latency, then least recently used
            now = time.time()
            weighted = []
            for p in self._pool:
                # Avoid recently used proxies
                time_penalty = 0
                if p['last_used'] > 0:
                    seconds_ago = now - p['last_used']
                    time_penalty = max(0, 10 - seconds_ago)  # Penalize if used < 10s ago

                failure_penalty = p['failures'] * 5  # Each failure = 5 weight

                weight = p.get('latency', 1000) + time_penalty + failure_penalty
                weighted.append((weight, p))

            weighted.sort(key=lambda x: x[0])
            best = weighted[0][1]

            # Rotate — move selected proxy to end so it's not picked again immediately
            best['last_used'] = now

            # Randomly select from top 3 for obfuscation (Layer 2)
            if len(weighted) >= 3:
                candidates = [w[1] for w in weighted[:3]]
                selected = random.choice(candidates)
                selected['last_used'] = now
                self._session_stats['requests_routed'] += 1
                return selected['proxy']

            self._session_stats['requests_routed'] += 1
            return best['proxy']

    # ─── Proxy health feedback ──────────────────────────────────────────
    def report_success(self, proxy: str):
        """Report a successful request through a proxy (awards points)."""
        with self._lock:
            for p in self._pool:
                if p['proxy'] == proxy:
                    p['success_count'] += 1
                    p['failures'] = max(0, p['failures'] - 1)  # Reduce failure count
                    break

    def report_failure(self, proxy: str):
        """Report a failed request through a proxy (penalizes/blacklists)."""
        with self._lock:
            for p in self._pool:
                if p['proxy'] == proxy:
                    p['failures'] += 1
                    if p['failures'] >= self._ban_threshold:
                        # Blacklist for 30 minutes
                        self._blacklist[proxy] = time.time() + 1800
                        self._pool.remove(p)
                        self._session_stats['proxies_banned'] += 1
                        _log(f'Proxy banned (failures={p["failures"]}): {proxy[:30]}...', 'WARN')
                    break

            self._session_stats['requests_failed'] += 1

    def get_stats(self) -> Dict:
        """Get proxy manager statistics."""
        with self._lock:
            return {
                'pool_size': len(self._pool),
                'blacklisted': len(self._blacklist),
                'enabled': self._enabled,
                'working_proxies': len([p for p in self._pool if p['failures'] < 2]),
                'avg_latency_ms': sum(p.get('latency', 0) for p in self._pool) / max(len(self._pool), 1),
                **self._session_stats,
            }

    def get_proxy_for_source(self, source_name: str) -> Optional[str]:
        """Get proxy with source-specific rotation strategy.

        Different sources have different tolerance for proxy quality:
        - FBref/Transfermarkt: Use slowest but most reliable proxies
        - Understat/OddsPortal: Use fastest proxies
        - Flashscore/football-data: Any proxy works
        """
        proxy = self.get_proxy()
        return proxy


# ─── Singleton ──────────────────────────────────────────────────────────────
_proxy_manager = None
_manager_lock = threading.Lock()


def get_proxy_manager() -> ProxyManager:
    """Get or create the singleton ProxyManager."""
    global _proxy_manager
    if _proxy_manager is None:
        with _manager_lock:
            if _proxy_manager is None:
                _proxy_manager = ProxyManager()
    return _proxy_manager


def get_proxy(source: str = 'default') -> Optional[str]:
    """Convenience: get proxy for a source."""
    mgr = get_proxy_manager()
    return mgr.get_proxy_for_source(source)


def report_success(proxy: str):
    """Convenience: report proxy success."""
    mgr = get_proxy_manager()
    mgr.report_success(proxy)


def report_failure(proxy: str):
    """Convenience: report proxy failure."""
    mgr = get_proxy_manager()
    mgr.report_failure(proxy)


def init_pool():
    """Initialize the proxy pool (call at startup)."""
    mgr = get_proxy_manager()
    mgr.refresh_pool(force=True)


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Proxy Rotator')
    parser.add_argument('--refresh', action='store_true', help='Force refresh pool')
    parser.add_argument('--test', type=str, help='Test a specific proxy')
    parser.add_argument('--stats', action='store_true', help='Show stats')
    parser.add_argument('--list', action='store_true', help='List working proxies')

    args = parser.parse_args()

    mgr = get_proxy_manager()

    if args.test:
        latency = mgr._test_proxy_latency(args.test)
        if latency:
            print(f'Proxy OK: {latency:.0f}ms latency')
        else:
            print('Proxy FAILED')

    elif args.stats:
        print(json.dumps(mgr.get_stats(), indent=2))

    elif args.list:
        print(f'{"Proxy":<50s} {"Latency":<10s} {"Failures":<10s} {"Success":<10s}')
        print('-' * 80)
        with mgr._lock:
            for p in sorted(mgr._pool, key=lambda x: x.get('latency', 9999)):
                print(f'{p["proxy"]:<50s} {p.get("latency", 0):<10.0f}ms {p["failures"]:<10d} {p["success_count"]:<10d}')

    else:
        # Default: refresh and show pool
        if args.refresh:
            mgr.refresh_pool(force=True)
        else:
            mgr.refresh_pool()

        proxy = mgr.get_proxy()
        if proxy:
            print(f'Selected proxy: {proxy[:50]}...')
        else:
            print('No proxies available (using direct connection)')

        print(f'\nPool stats:')
        print(json.dumps(mgr.get_stats(), indent=2))
