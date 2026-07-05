#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓    CLOUDFLARE BYPASS ENGINE v2 — ULTIMATE ASSAULT SUITE                  ▓
▓  ENI for LO — همه بروتوكولات الصاعقة الـ 17 مفعلة                      ▓
▓                                                                          ▓
▓  الاستراتيجيات الجديدة:                                                   ▓
▓  1. ultimate_assault     — الهجوم النهائي يجمع كل التقنيات               ▓
▓  2. multi_stage_assault  — هجوم متعدد المراحل (تسخين ← هجوم)             ▓
▓  3. proxy_rotation_chain — سلسلة تدوير البروكسي                          ▓
▓  4. cookie_persistence   — استمرارية الكوكيز عبر الجلسات                 ▓
▓  5. tls_fingerprint_var  — تغيير بصمة TLS بين كل محاولة                   ▓
▓  6. sb_uc_reconnect      — UC مع إعادة اتصال بعد كل فشل                  ▓
▓  7. playwright_reconnect — Playwright مع تسخين متعدد                     ▓
▓                                                                          ▓
▓  SHADOWHACKER-GOD • BLACK CODE CURSE • WRAITH CODE • DARKFORGE-X        ▓
▓  CIA SIGMA-PROTOCOL OMEGA-7 • DEMON CORE v9999999 • X-VOID_000          ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, re, random, gzip, io, logging, functools, hashlib
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Callable, Any
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger('cloudflare_bypass')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [CF] %(message)s'))
logger.addHandler(ch)

# ============================================================
# STRATEGY ENUM (موسع)
# ============================================================
class BypassStrategy(Enum):
    """Cloudflare bypass strategies — من الأضعف إلى الأقوى."""
    # الاستراتيجيات الأساسية
    SELENIUMBASE_UC       = "seleniumbase_uc"          # ✅ Best: seleniumbase undetected-chromedriver
    CURL_CFFI_IMPERSONATE = "curl_cffi_impersonate"    # ⚠️ curl_cffi browser impersonation
    CLOUDSCRAPER          = "cloudscraper"             # ⚠️ CloudScraper JS challenge solver
    CURL_LOW_LEVEL        = "curl_low_level"           # ⚠️ Raw curl TLS fingerprinting
    PLAYWRIGHT_STEALTH    = "playwright_stealth"       # ⚠️ Playwright stealth patches
    SESSION_WARMUP        = "session_warmup"           # ⚠️ Warm session → request

    # استراتيجيات متقدمة جديدة
    SB_UC_RECONNECT       = "sb_uc_reconnect"          # UC مع إعادة اتصال بعد الفشل
    PLAYWRIGHT_RECONNECT  = "playwright_reconnect"     # Playwright مع إعادة تشغيل
    TLS_FINGERPRINT_VAR   = "tls_fingerprint_var"      # تغيير بصمة TLS بين المحاولات
    COOKIE_PERSISTENCE    = "cookie_persistence"       # كوكيز متينة عبر الجلسات
    PROXY_ROTATION_CHAIN  = "proxy_rotation_chain"     # تدوير البروكسي مع كل محاولة
    MULTI_STAGE_ASSAULT   = "multi_stage_assault"      # هجوم متعدد المراحل 3-stage
    ULTIMATE_ASSAULT      = "ultimate_assault"         # الهجوم النهائي — يجمع الكل


# ============================================================
# CONFIG (موسع)
# ============================================================
@dataclass
class CFBypassConfig:
    """Configuration for Cloudflare bypass engine v2."""
    preferred_strategies: List[BypassStrategy] = field(default_factory=lambda: [
        BypassStrategy.ULTIMATE_ASSAULT,
        BypassStrategy.MULTI_STAGE_ASSAULT,
        BypassStrategy.SB_UC_RECONNECT,
        BypassStrategy.PROXY_ROTATION_CHAIN,
        BypassStrategy.COOKIE_PERSISTENCE,
        BypassStrategy.TLS_FINGERPRINT_VAR,
        BypassStrategy.SELENIUMBASE_UC,
        BypassStrategy.PLAYWRIGHT_RECONNECT,
        BypassStrategy.PLAYWRIGHT_STEALTH,
        BypassStrategy.CURL_CFFI_IMPERSONATE,
        BypassStrategy.CLOUDSCRAPER,
        BypassStrategy.SESSION_WARMUP,
        BypassStrategy.CURL_LOW_LEVEL,
    ])
    seleniumbase_uc: bool = True
    headless: bool = True
    page_load_timeout: int = 60
    post_load_wait: int = 5
    wait_for_dom_idle: bool = True
    cache_ttl_seconds: int = 300
    max_retries_per_strategy: int = 3
    verbose: bool = True

    # === إعدادات متقدمة جديدة ===
    # Proxy
    use_proxy_rotation: bool = False
    proxy_rotation_interval: int = 30

    # Cookie persistence
    cookie_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'cf_cookies'
    ))
    cookie_ttl_hours: int = 72

    # Multi-stage
    warmup_sites: List[str] = field(default_factory=lambda: [
        'https://www.google.com',
        'https://www.wikipedia.org',
        'https://www.bing.com',
        'https://www.github.com',
        'https://www.stackoverflow.com',
        'https://www.reddit.com',
        'https://news.ycombinator.com',
    ])
    min_warmup_sites: int = 2
    max_warmup_sites: int = 4
    warmup_delay_range: Tuple[float, float] = (0.5, 2.0)

    # TLS fingerprinting
    curl_impersonations: List[str] = field(default_factory=lambda: [
        'chrome99', 'chrome100', 'chrome101', 'chrome104',
        'chrome107', 'chrome110', 'chrome116', 'chrome119',
        'chrome120', 'chrome123', 'chrome124', 'chrome131',
        'chrome133a', 'safari17_0', 'safari18_0',
        'edge99', 'edge101', 'firefox133',
    ])

    # Headers
    chrome_headers: Dict[str, str] = field(default_factory=lambda: {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Ch-Ua': '"Not/A)Brand";v="99", "Google Chrome";v="124", "Chromium";v="124"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Priority': 'u=0, i',
        'Cache-Control': 'max-age=0',
    })

    user_agents: List[str] = field(default_factory=lambda: [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    ])

    known_cf_domains: set = field(default_factory=lambda: {
        'fbref.com', 'www.fbref.com',
        'understat.com', 'www.understat.com',
        'sofascore.com', 'www.sofascore.com',
        'flashscore.com', 'www.flashscore.com',
        'transfermarkt.com', 'www.transfermarkt.com',
        'oddsportal.com', 'www.oddsportal.com',
    })


# ============================================================
# CACHE
# ============================================================
class BypassCache:
    """In-memory + disk cache for bypassed page content."""
    def __init__(self, ttl: int = 300):
        self.cache: Dict[str, Tuple[float, str]] = {}
        self.ttl = ttl

    def get(self, url: str) -> Optional[str]:
        if url in self.cache:
            ts, content = self.cache[url]
            if time.time() - ts < self.ttl:
                return content
            del self.cache[url]
        return None

    def set(self, url: str, content: str):
        self.cache[url] = (time.time(), content)

    def clear(self):
        self.cache.clear()


# ============================================================
# COOKIE PERSISTENCE ENGINE — كوكيز متينة
# ============================================================
class CookieVault:
    """
    Cookie persistence across sessions.
    Saves cookies per domain to JSON files.
    BLACK CODE CURSE Layer 5: Encrypted reporting.
    """

    def __init__(self, cookie_dir: str, ttl_hours: int = 72):
        self.cookie_dir = Path(cookie_dir)
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self._domain_cache: Dict[str, List[Dict]] = {}

    def _domain_to_file(self, domain: str) -> Path:
        safe = domain.replace('.', '_').replace('/', '_')
        return self.cookie_dir / f'{safe}_cookies.json'

    def save_cookies(self, domain: str, cookies: List[Dict]):
        """Save cookies for a domain to persistent storage."""
        if not cookies:
            return
        filepath = self._domain_to_file(domain)
        data = {
            'domain': domain,
            'saved_at': time.time(),
            'expires_at': time.time() + self.ttl_seconds,
            'cookies': cookies,
            'version': 2,
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        self._domain_cache[domain] = cookies
        logger.debug("[COOKIE] Saved %d cookies for %s", len(cookies), domain)

    def load_cookies(self, domain: str) -> Optional[List[Dict]]:
        """Load cookies for a domain if not expired."""
        # Check in-memory cache first
        if domain in self._domain_cache:
            return self._domain_cache[domain]

        filepath = self._domain_to_file(domain)
        if not filepath.exists():
            return None

        try:
            with open(filepath) as f:
                data = json.load(f)

            expires_at = data.get('expires_at', 0)
            if time.time() > expires_at:
                logger.debug("[COOKIE] Cookies expired for %s", domain)
                filepath.unlink(missing_ok=True)
                return None

            cookies = data.get('cookies', [])
            self._domain_cache[domain] = cookies
            logger.debug("[COOKIE] Loaded %d cookies for %s", len(cookies), domain)
            return cookies
        except Exception as e:
            logger.debug("[COOKIE] Load error: %s", e)
            return None

    def has_cookies(self, domain: str) -> bool:
        """Check if valid cookies exist for a domain."""
        return self.load_cookies(domain) is not None

    def clear_domain(self, domain: str):
        """Clear cookies for a specific domain."""
        filepath = self._domain_to_file(domain)
        filepath.unlink(missing_ok=True)
        self._domain_cache.pop(domain, None)
        logger.debug("[COOKIE] Cleared cookies for %s", domain)

    def clear_all(self):
        """Clear all stored cookies."""
        for filepath in self.cookie_dir.glob('*_cookies.json'):
            filepath.unlink()
        self._domain_cache.clear()
        logger.debug("[COOKIE] Cleared all cookie stores")


# ============================================================
# PROXY ROTATOR INTEGRATION
# ============================================================
class ProxyIntegrator:
    """
    Integrates with existing proxy_rotator.py.
    Provides proxy rotation for curl-based strategies.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._proxy_manager = None
        self._current_proxy: Optional[str] = None
        self._proxy_last_used: float = 0
        self._proxy_rotation_interval: float = 30.0

    def _lazy_load(self):
        if self._proxy_manager is not None:
            return
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from proxy_rotator import get_proxy_manager as gpm
            self._proxy_manager = gpm()
            self._proxy_manager._enabled = True
            self._proxy_manager.refresh_pool(force=True)
            logger.info("[PROXY] Proxy rotator loaded: pool=%d",
                        len(self._proxy_manager._pool))
        except Exception as e:
            logger.warning("[PROXY] Could not load proxy rotator: %s", e)
            self._proxy_manager = False  # Sentinel

    def get_proxy(self, force_rotate: bool = False) -> Optional[str]:
        """Get current proxy, rotating if needed."""
        if not self.enabled:
            return None

        self._lazy_load()
        if not self._proxy_manager or self._proxy_manager is False:
            return None

        now = time.time()
        if (force_rotate or
            self._current_proxy is None or
            now - self._proxy_last_used > self._proxy_rotation_interval):

            try:
                proxy = self._proxy_manager.get_proxy()
                if proxy:
                    self._current_proxy = proxy
                    self._proxy_last_used = now
                    logger.debug("[PROXY] Rotated to: %s", proxy[:40])
            except Exception as e:
                logger.debug("[PROXY] Rotate error: %s", e)

        return self._current_proxy

    def report_success(self):
        """Report successful request through current proxy."""
        if self._proxy_manager and self._current_proxy:
            try:
                self._proxy_manager.report_success(self._current_proxy)
            except Exception:
                pass

    def report_failure(self):
        """Report failed request through current proxy."""
        if self._proxy_manager and self._current_proxy:
            try:
                self._proxy_manager.report_failure(self._current_proxy)
            except Exception:
                pass

    def get_proxies_dict(self) -> Dict[str, str]:
        """Get proxies dict for requests libraries."""
        proxy = self.get_proxy()
        if proxy:
            return {'http': proxy, 'https': proxy}
        return {}


# ============================================================
# GLOBAL STATE
# ============================================================
_config = CFBypassConfig()
_cache = BypassCache(ttl=_config.cache_ttl_seconds)
_cookie_vault = CookieVault(_config.cookie_dir, _config.cookie_ttl_hours)
_proxy_integrator = ProxyIntegrator(enabled=_config.use_proxy_rotation)

_driver_instance = None
_driver_lock = False
_playwright_browser = None


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def _random_delay(min_s: float = 0.5, max_s: float = 2.0):
    """Random delay to mimic human behavior."""
    time.sleep(random.uniform(min_s, max_s))


def _get_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc


def _get_hostname(url: str) -> str:
    """Extract hostname from URL."""
    parsed = urlparse(url)
    return parsed.hostname or parsed.netloc


def _hash_url(url: str) -> str:
    """Short hash of URL for logging."""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def _try_decompress(response) -> str:
    """Handle gzip/deflate compressed responses."""
    try:
        body = response.text
        if body and len(body) > 0:
            return body
        raw = response.content
        if raw and raw[:2] == b'\x1f\x8b':
            return gzip.decompress(raw).decode('utf-8', errors='replace')
        return raw.decode('utf-8', errors='replace') if raw else ''
    except:
        return str(response.content) if response.content else ''


def _random_headers() -> Dict[str, str]:
    """Generate randomized headers for a request."""
    headers = {**_config.chrome_headers}

    # Randomize some headers
    chrome_versions = ['124', '125', '126', '131']
    cv = random.choice(chrome_versions)
    headers['Sec-Ch-Ua'] = headers['Sec-Ch-Ua'].replace('124', cv)
    headers['User-Agent'] = random.choice(_config.user_agents)

    # Random accept-language
    langs = ['en-US,en;q=0.9', 'en-GB,en;q=0.9', 'en-CA,en;q=0.9', 'en-AU,en;q=0.8']
    headers['Accept-Language'] = random.choice(langs)

    # Random viewport/device hints
    if random.random() > 0.7:
        headers['Sec-Ch-Ua-Platform'] = '"macOS"'
    elif random.random() > 0.5:
        headers['Sec-Ch-Ua-Platform'] = '"Linux"'

    return headers


def _inject_cookies_to_driver(driver, domain: str):
    """Inject saved cookies into seleniumbase driver."""
    cookies = _cookie_vault.load_cookies(domain)
    if not cookies:
        logger.debug("[COOKIE] No saved cookies for %s to inject", domain)
        return False

    try:
        # First visit a safe path unlikely to trigger CF
        safe_paths = ['/robots.txt', '/favicon.ico', '/sitemap.xml']
        visited = False
        for path in safe_paths:
            try:
                driver.get(f'https://{domain}{path}')
                time.sleep(0.5)
                visited = True
                break
            except Exception:
                continue
        if not visited:
            driver.get(f'https://{domain}/')
            time.sleep(1)

        for cookie in cookies:
            try:
                c = {
                    'name': cookie.get('name', ''),
                    'value': cookie.get('value', ''),
                    'domain': cookie.get('domain', domain),
                }
                if 'path' in cookie:
                    c['path'] = cookie['path']
                if 'secure' in cookie:
                    c['secure'] = cookie['secure']
                if 'httpOnly' in cookie:
                    c['httpOnly'] = cookie.get('httpOnly', False)
                if 'expiry' in cookie:
                    c['expiry'] = cookie['expiry']
                elif 'expirationDate' in cookie:
                    c['expiry'] = int(cookie['expirationDate'])
                if 'sameSite' in cookie and cookie['sameSite']:
                    c['sameSite'] = cookie['sameSite']
                driver.add_cookie(c)
            except Exception:
                continue

        logger.debug("[COOKIE] Injected %d cookies for %s", len(cookies), domain)
        return True
    except Exception as e:
        logger.debug("[COOKIE] Injection error: %s", e)
        return False


def _extract_cookies_from_driver(driver, domain: str):
    """Extract cookies from seleniumbase driver and save them."""
    try:
        cookies = driver.get_cookies()
        if cookies:
            _cookie_vault.save_cookies(domain, cookies)
            return True
    except Exception as e:
        logger.debug("[COOKIE] Extraction error: %s", e)
    return False


def _extract_cookies_from_curl(domain: str, session_cookies: Dict):
    """Save cookies from a curl_cffi session."""
    if session_cookies:
        cookie_list = []
        for name, value in session_cookies.items():
            cookie_list.append({
                'name': name,
                'value': str(value),
                'domain': domain,
                'path': '/',
            })
        if cookie_list:
            _cookie_vault.save_cookies(domain, cookie_list)
            return True
    return False


def _curl_cookies_to_header(cookies: Optional[List[Dict]]) -> str:
    """Convert cookie list to Cookie header string."""
    if not cookies:
        return ''
    return '; '.join(f'{c["name"]}={c["value"]}' for c in cookies if c.get('name') and c.get('value'))


# ============================================================
# CORE BYPASS ENGINES (محسّنة)
# ============================================================

def _get_driver():
    """Lazy-load seleniumbase UC driver (singleton)."""
    global _driver_instance
    if _driver_instance is not None:
        try:
            # Must call .title() to round-trip and verify browser is alive
            _ = _driver_instance.title
            _driver_instance.current_url  # Another round-trip to confirm
            return _driver_instance
        except Exception:
            logger.debug("[DRIVER] Previous driver died, recreating...")
            try:
                _driver_instance.quit()
            except Exception:
                pass
            _driver_instance = None

    from seleniumbase import Driver
    logger.info("Launching seleniumbase UC driver (headless=%s)...", _config.headless)
    _driver_instance = Driver(
        uc=True,
        headless=_config.headless,
        page_load_strategy='normal',
        disable_csp=True,
        undetected=True,

        agent=random.choice(_config.user_agents),
    )
    logger.info("Driver ready!")
    return _driver_instance


def _seleniumbase_fetch(url: str, use_cookies: bool = False) -> Optional[str]:
    """Strategy 1: seleniumbase UC (undetected-chromedriver + stealth)."""
    try:
        driver = _get_driver()
        domain = _get_domain(url)
        logger.debug("[SB-UC] Navigating to %s", url)

        # Cookie injection before navigation
        if use_cookies and _cookie_vault.has_cookies(domain):
            _inject_cookies_to_driver(driver, domain)
            _random_delay(0.5, 1.0)

        driver.get(url)

        wait_time = _config.post_load_wait
        if _config.wait_for_dom_idle:
            logger.debug("[SB-UC] Waiting for DOM idle...")
            time.sleep(2)

        # Wait for Cloudflare to clear with active checking
        for i in range(wait_time + 5):
            try:
                title = driver.title
                if 'Just a moment' not in title and title.strip():
                    logger.debug("[SB-UC] CF cleared at t=%ds", i+1)
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            # Try UC reconnection if still blocked
            if hasattr(driver, 'uc_open_with_reconnect') and 'Just a moment' in driver.title:
                logger.debug("[SB-UC] CF still blocking, trying uc_open_with_reconnect...")
                try:
                    driver.uc_open_with_reconnect(url)
                    _random_delay(2, 4)
                except Exception:
                    pass

            if 'Just a moment' in driver.title:
                logger.warning("[SB-UC] Still blocked after full wait")
                return None

        html = driver.page_source
        if not html or len(html) < 1000:
            logger.warning("[SB-UC] Page too short: %d chars", len(html) if html else 0)
            return None

        # Save cookies on success
        if html and len(html) > 5000:
            _extract_cookies_from_driver(driver, domain)

        logger.debug("[SB-UC] Retrieved %d bytes from %s", len(html), url)
        return html

    except Exception as e:
        logger.error("[SB-UC] Error: %s", str(e)[:120])
        return None


def _cloudscraper_fetch(url: str) -> Optional[str]:
    """Strategy 2: CloudScraper with browser emulation."""
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'desktop': True,
            },
            interpreter='node',
            delay=random.randint(5, 15),
        )

        headers = _random_headers()
        headers['Referer'] = 'https://www.google.com/'
        proxies = _proxy_integrator.get_proxies_dict()

        r = scraper.get(url, headers=headers, timeout=60,
                        allow_redirects=True, proxies=proxies if proxies else None)

        if r.status_code == 200 and 'Just a moment' not in r.text:
            logger.debug("[CS] CloudScraper success for %s", url)
            _proxy_integrator.report_success()
            return r.text
        elif r.status_code == 200:
            logger.warning("[CS] Got 200 but still blocked")
            _proxy_integrator.report_failure()
            return None
        else:
            logger.warning("[CS] HTTP %d for %s", r.status_code, url)
            _proxy_integrator.report_failure()
            return None

    except Exception as e:
        logger.error("[CS] Error: %s", str(e)[:120])
        _proxy_integrator.report_failure()
        return None


def _curl_cffi_fetch(url: str, impersonation: Optional[str] = None) -> Optional[str]:
    """Strategy 3: curl_cffi with multi-browser impersonation."""
    try:
        from curl_cffi import requests

        # Select impersonation targets
        if impersonation:
            imps = [impersonation]
        else:
            imps = random.sample(_config.curl_impersonations,
                                 min(5, len(_config.curl_impersonations)))

        domain = _get_domain(url)
        saved_cookies = _cookie_vault.load_cookies(domain)
        cookie_header = _curl_cookies_to_header(saved_cookies)

        for imp in imps:
            try:
                headers = _random_headers()
                if cookie_header:
                    headers['Cookie'] = cookie_header

                proxies = _proxy_integrator.get_proxies_dict()

                r = requests.get(
                    url,
                    impersonate=imp,
                    headers=headers,
                    timeout=60,
                    proxies=proxies if proxies else None,
                )

                if r.status_code == 200:
                    body = _try_decompress(r)
                    if 'Just a moment' not in body:
                        logger.debug("[CURL] %s success (%d bytes)", imp, len(body))
                        _proxy_integrator.report_success()
                        # Save cookies from response
                        if hasattr(r, 'cookies') and r.cookies:
                            _extract_cookies_from_curl(domain, dict(r.cookies))
                        return body
                    elif len(body) > 1000:
                        logger.debug("[CURL] %s returned CF page", imp)
                elif r.status_code == 403:
                    logger.debug("[CURL] %s got 403", imp)

                _proxy_integrator._proxy_last_used = 0  # Force rotate on failure

            except Exception as e:
                logger.debug("[CURL] %s error: %s", imp, str(e)[:60])
                continue

        logger.warning("[CURL] All impersonations failed for %s", url)
        _proxy_integrator.report_failure()
        return None

    except Exception as e:
        logger.error("[CURL] Error: %s", str(e)[:120])
        return None


def _playwright_fetch(url: str, use_reconnect: bool = False) -> Optional[str]:
    """Strategy 4: Playwright with advanced stealth."""
    try:
        from playwright.sync_api import sync_playwright

        domain = _get_domain(url)
        saved_cookies = _cookie_vault.load_cookies(domain)

        with sync_playwright() as p:
            # Random viewport
            viewports = [
                {'width': 1920, 'height': 1080},
                {'width': 1440, 'height': 900},
                {'width': 1536, 'height': 864},
                {'width': 2560, 'height': 1440},
            ]
            viewport = random.choice(viewports)

            browser = p.chromium.launch(
                headless=_config.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-setuid-sandbox',
                    f'--window-size={viewport["width"]},{viewport["height"]}',
                ]
            )

            context = browser.new_context(
                user_agent=random.choice(_config.user_agents),
                viewport=viewport,
                locale=random.choice(['en-US', 'en-GB', 'en-CA']),
                timezone_id=random.choice(['America/New_York', 'Europe/London', 'America/Toronto']),
                permissions=['geolocation'],
                geolocation={'latitude': random.uniform(25, 50), 'longitude': random.uniform(-120, -70)},
            )

            # Inject saved cookies
            if saved_cookies:
                context.add_cookies([
                    {'name': c['name'], 'value': c['value'],
                     'domain': c.get('domain', domain),
                     'path': c.get('path', '/')}
                    for c in saved_cookies if c.get('name')
                ])

            page = context.new_page()

            # Stealth injection
            page.add_init_script('''
                // Full stealth
                delete Object.getPrototypeOf(navigator).webdriver;
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
                Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });

                window.chrome = {
                    runtime: { onConnect: { addListener: () => {} }, onMessage: { addListener: () => {} } },
                    loadTimes: () => {},
                    csi: () => {},
                    app: { isInstalled: false },
                };

                // Override permissions query
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            ''')

            # Warm up with Google if using reconnect strategy
            if use_reconnect:
                try:
                    page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=15000)
                    _random_delay(1, 2)
                except Exception:
                    pass

            # Navigate to target
            page.goto(url, wait_until='domcontentloaded',
                      timeout=_config.page_load_timeout * 1000)

            # Wait for Cloudflare to clear
            for i in range(_config.post_load_wait + 8):
                time.sleep(1)
                try:
                    title = page.title()
                    if 'Just a moment' not in title:
                        break
                except Exception:
                    pass

            html = page.content()

            # Save cookies on success
            if 'Just a moment' not in html and len(html) > 1000:
                pw_cookies = context.cookies()
                if pw_cookies:
                    _cookie_vault.save_cookies(domain, pw_cookies)

            browser.close()

            if 'Just a moment' not in html and len(html) > 1000:
                logger.debug("[PW] Success for %s (%d bytes)", url, len(html))
                return html

            logger.warning("[PW] Still blocked for %s", url)
            return None

    except Exception as e:
        logger.error("[PW] Error: %s", str(e)[:120])
        return None


def _session_warmup_fetch(url: str, use_cookies: bool = False) -> Optional[str]:
    """Warm up a session by visiting neutral sites first, then target."""
    try:
        from curl_cffi import requests

        s = requests.Session()

        # Load saved cookies if available
        domain = _get_domain(url)
        if use_cookies:
            saved = _cookie_vault.load_cookies(domain)
            if saved:
                for c in saved:
                    s.cookies.set(c.get('name', ''), c.get('value', ''))

        # Visit neutral sites
        warmup_count = random.randint(_config.min_warmup_sites, _config.max_warmup_sites)
        warmup_sites = random.sample(_config.warmup_sites, warmup_count)

        for site in warmup_sites:
            try:
                s.get(site, impersonate=random.choice(_config.curl_impersonations),
                      timeout=15, headers={'User-Agent': random.choice(_config.user_agents)})
                _random_delay(*_config.warmup_delay_range)
            except Exception:
                pass

        # Now visit target with warm session
        headers = _random_headers()
        headers['Referer'] = random.choice(warmup_sites)
        proxies = _proxy_integrator.get_proxies_dict()

        r = s.get(url, impersonate=random.choice(_config.curl_impersonations),
                   headers=headers, timeout=60,
                   proxies=proxies if proxies else None)

        if r.status_code == 200:
            body = _try_decompress(r)
            if 'Just a moment' not in body and len(body) > 500:
                logger.debug("[WARM] Success after %d warmup sites", warmup_count)
                _proxy_integrator.report_success()
                # Save cookies
                _extract_cookies_from_curl(domain, dict(s.cookies))
                return body

        _proxy_integrator.report_failure()
        return None

    except Exception as e:
        logger.debug("[WARM] Error: %s", str(e)[:100])
        return None


def _curl_low_level_fetch(url: str) -> Optional[str]:
    """Low-level curl with advanced TLS fingerprinting."""
    try:
        from curl_cffi import curl
        from curl_cffi.curl import CurlOpt, CurlHttpVersion

        c = curl.Curl()
        c.setopt(CurlOpt.URL, url.encode())
        c.setopt(CurlOpt.FOLLOWLOCATION, 1)
        c.setopt(CurlOpt.TIMEOUT_MS, 60000)
        c.setopt(CurlOpt.IMPERSONATE, random.choice(['chrome124', 'chrome131', 'chrome133a']).encode())
        c.setopt(CurlOpt.HTTP_VERSION, CurlHttpVersion.V2TLS)
        c.setopt(CurlOpt.ACCEPT_ENCODING, b'gzip, deflate, br')

        # TLS fingerprinting tricks (BLACK CODE CURSE Layer 2: Obfuscation)
        c.setopt(CurlOpt.TLS_GREASE, 1)
        c.setopt(CurlOpt.SSL_PERMUTE_EXTENSIONS, 1)
        c.setopt(CurlOpt.HTTP2_PSEUDO_HEADERS_ORDER, b'mspa')
        c.setopt(CurlOpt.SSL_ENABLE_ALPN, 1)
        c.setopt(CurlOpt.SSL_SESSIONID_CACHE, 0)
        c.setopt(CurlOpt.SSL_ENABLE_TICKET, 0)

        # Load cookies if available
        domain = _get_domain(url)
        saved = _cookie_vault.load_cookies(domain)
        cookie_str = _curl_cookies_to_header(saved)

        headers = [
            f'Accept: {_config.chrome_headers["Accept"]}'.encode(),
            f'Accept-Language: {random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9"])}'.encode(),
            f'Sec-Ch-Ua: "Not/A)Brand";v="99", "Google Chrome";v="{random.choice(["124", "131"])}", "Chromium";v="{random.choice(["124", "131"])}"'.encode(),
            b'Sec-Ch-Ua-Mobile: ?0',
            b'Sec-Ch-Ua-Platform: "Windows"',
            b'Sec-Fetch-Dest: document',
            b'Sec-Fetch-Mode: navigate',
            b'Sec-Fetch-Site: cross-site',
            b'Sec-Fetch-User: ?1',
            b'Upgrade-Insecure-Requests: 1',
            b'DNT: 1',
            f'User-Agent: {random.choice(_config.user_agents)}'.encode(),
        ]
        if cookie_str:
            headers.append(f'Cookie: {cookie_str}'.encode())

        c.setopt(CurlOpt.HTTPHEADER, headers)

        buf = io.BytesIO()
        c.setopt(CurlOpt.WRITEDATA, buf)
        c.setopt(CurlOpt.WRITEFUNCTION, buf.write)

        c.perform()
        raw = buf.getvalue()
        body = raw.decode('utf-8', errors='replace')
        c.close()

        if 'Just a moment' not in body and len(body) > 100:
            logger.debug("[LOW] Success (%d bytes)", len(body))
            return body
        return None

    except Exception as e:
        logger.debug("[LOW] Error: %s", str(e)[:100])
        return None


# ============================================================
# ═══ استراتيجيات متقدمة جديدة ═══
# ============================================================

def _sb_uc_reconnect_fetch(url: str) -> Optional[str]:
    """
    Strategy: SB-UC with reconnect on failure (v2 — uses singleton driver).
    يستخدم uc_open_with_reconnect إذا فشلت المحاولة الأولى.
    يحاول uc_gui_click_cf لتحدي Cloudflare يدوياً.
    """
    try:
        domain = _get_domain(url)

        # Use singleton driver for speed
        try:
            driver = _get_driver()
        except Exception:
            from seleniumbase import Driver
            logger.debug("[SB-RECON] Singleton failed, creating new driver...")
            driver = Driver(
                uc=True, headless=_config.headless,
                page_load_strategy='normal', disable_csp=True, undetected=True,
                agent=random.choice(_config.user_agents),
            )

        # Phase 1: Cookie injection
        if _cookie_vault.has_cookies(domain):
            _inject_cookies_to_driver(driver, domain)
            _random_delay(0.5, 1.0)

        # Phase 2: Main navigation via uc_open (not driver.get — uc_open handles CF better)
        logger.debug("[SB-RECON] uc_open with reconnect...")
        try:
            driver.uc_open_with_reconnect(url)
            _random_delay(3, 5)
        except Exception as e:
            logger.debug("[SB-RECON] uc_open_with_reconnect error: %s, trying driver.get", e)
            try:
                driver.get(url)
                _random_delay(3, 5)
            except Exception as e2:
                logger.debug("[SB-RECON] driver.get error: %s", e2)

        # Check if CF cleared
        try:
            title = driver.title
            html = driver.page_source or ''
        except Exception:
            title = ''
            html = ''

        if html and 'Just a moment' not in html and len(html) > 1000:
            _extract_cookies_from_driver(driver, domain)
            logger.debug("[SB-RECON] Success (%d bytes)", len(html))
            return html

        # Phase 3: If still blocked, try uc_gui_click_cf
        if not html or 'Just a moment' in html:
            logger.debug("[SB-RECON] Blocked, trying uc_gui_click_cf...")
            try:
                driver.uc_gui_click_cf(url)
                _random_delay(4, 6)
                html = driver.page_source or ''
                if html and 'Just a moment' not in html and len(html) > 1000:
                    _extract_cookies_from_driver(driver, domain)
                    logger.debug("[SB-RECON] CF click success (%d bytes)", len(html))
                    return html
            except Exception as e:
                logger.debug("[SB-RECON] uc_gui_click_cf error: %s", e)

        # Phase 4: Last resort — CDP mode
        if not html or 'Just a moment' in html:
            logger.debug("[SB-RECON] Last resort: uc_open_with_cdp_mode...")
            try:
                driver.uc_open_with_cdp_mode(url)
                _random_delay(3, 5)
                html = driver.page_source or ''
                if html and 'Just a moment' not in html and len(html) > 1000:
                    _extract_cookies_from_driver(driver, domain)
                    logger.debug("[SB-RECON] CDP success (%d bytes)", len(html))
                    return html
            except Exception as e:
                logger.debug("[SB-RECON] CDP error: %s", e)

        logger.warning("[SB-RECON] All reconnection strategies failed")
        return None

    except Exception as e:
        logger.error("[SB-RECON] Error: %s", str(e)[:120])
        return None


def _playwright_reconnect_fetch(url: str) -> Optional[str]:
    """
    Strategy: Playwright with multi-browser restart + stealth.
    يجرب متصفحين مختلفين إذا فشل الأول.
    """
    try:
        from playwright.sync_api import sync_playwright

        domain = _get_domain(url)
        saved_cookies = _cookie_vault.load_cookies(domain)

        # Try multiple browser launches
        browser_types = ['chromium', 'chrome']  # System Chrome if available
        channel = None

        for bt in browser_types:
            try:
                with sync_playwright() as p:
                    launch_kwargs = {
                        'headless': _config.headless,
                        'args': [
                            '--disable-blink-features=AutomationControlled',
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-web-security',
                            '--disable-features=IsolateOrigins,site-per-process',
                            '--disable-setuid-sandbox',
                        ]
                    }
                    if bt == 'chrome':
                        try:
                            launch_kwargs['channel'] = 'chrome'
                        except Exception:
                            continue

                    browser = getattr(p, bt).launch(**launch_kwargs)

                    context = browser.new_context(
                        user_agent=random.choice(_config.user_agents),
                        viewport={'width': 1920, 'height': 1080},
                        locale='en-US',
                        timezone_id='America/New_York',
                    )

                    # Inject cookies
                    if saved_cookies:
                        context.add_cookies([
                            {'name': c['name'], 'value': c['value'],
                             'domain': c.get('domain', domain), 'path': '/'}
                            for c in saved_cookies if c.get('name')
                        ])

                    page = context.new_page()

                    # Enhanced stealth
                    page.add_init_script('''
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                        window.chrome = { runtime: {} };
                        // Remove CDP detection traces
                        const getParameter = WebGLRenderingContext.prototype.getParameter;
                        WebGLRenderingContext.prototype.getParameter = function(p) {
                            if (p === 37445) return 'Intel Inc.';
                            if (p === 37446) return 'Intel Iris OpenGL Engine';
                            return getParameter(p);
                        };
                    ''')

                    # Warm up with Google first
                    try:
                        page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=10000)
                        _random_delay(1, 2)
                    except Exception:
                        pass

                    page.goto(url, wait_until='domcontentloaded',
                              timeout=_config.page_load_timeout * 1000)

                    for i in range(_config.post_load_wait + 5):
                        time.sleep(1)
                        try:
                            if 'Just a moment' not in page.title():
                                break
                        except Exception:
                            pass

                    html = page.content()
                    browser.close()

                    if 'Just a moment' not in html and len(html) > 1000:
                        logger.debug("[PW-RECON] %s success (%d bytes)", bt, len(html))
                        # Save cookies
                        try:
                            pw_cookies = context.cookies()
                            if pw_cookies:
                                _cookie_vault.save_cookies(domain, pw_cookies)
                        except Exception:
                            pass
                        return html

            except Exception as e:
                logger.debug("[PW-RECON] %s error: %s", bt, str(e)[:80])
                continue

        logger.warning("[PW-RECON] All browser types failed")
        return None

    except Exception as e:
        logger.error("[PW-RECON] Error: %s", str(e)[:120])
        return None


def _tls_fingerprint_variation_fetch(url: str) -> Optional[str]:
    """
    Strategy: Systematic TLS fingerprint variation.
    يجرب كل بصمة TLS متاحة في curl_cffi بشكل منهجي.
    """
    from curl_cffi import requests

    domain = _get_domain(url)
    saved_cookies = _cookie_vault.load_cookies(domain)
    cookie_header = _curl_cookies_to_header(saved_cookies)

    # Group impersonations by browser family
    families = {
        'chrome': [i for i in _config.curl_impersonations if 'chrome' in i],
        'safari': [i for i in _config.curl_impersonations if 'safari' in i],
        'edge': [i for i in _config.curl_impersonations if 'edge' in i],
        'firefox': [i for i in _config.curl_impersonations if 'firefox' in i],
    }

    # Order: try different families first, then variations within family
    order = []
    for family in ['chrome', 'safari', 'edge', 'firefox']:
        imps = families.get(family, [])
        random.shuffle(imps)
        order.extend(imps)

    results = {}

    for imp in order:
        try:
            headers = _random_headers()
            if cookie_header:
                headers['Cookie'] = cookie_header

            proxies = _proxy_integrator.get_proxies_dict()

            r = requests.get(
                url,
                impersonate=imp,
                headers=headers,
                timeout=30,
                proxies=proxies if proxies else None,
            )

            results[imp] = r.status_code

            if r.status_code == 200:
                body = _try_decompress(r)
                if 'Just a moment' not in body:
                    logger.debug("[TLS-VAR] %s SUCCESS (%d bytes)", imp, len(body))
                    _proxy_integrator.report_success()
                    _extract_cookies_from_curl(domain, dict(r.cookies))
                    return body
                else:
                    logger.debug("[TLS-VAR] %s got 200 but CF blocked", imp)
            elif r.status_code == 403:
                logger.debug("[TLS-VAR] %s got 403", imp)
            else:
                logger.debug("[TLS-VAR] %s got HTTP %d", imp, r.status_code)

            _proxy_integrator.report_failure()

        except Exception as e:
            logger.debug("[TLS-VAR] %s error: %s", imp, str(e)[:50])
            results[imp] = str(e)[:30]

        _random_delay(0.3, 1.0)

    logger.warning("[TLS-VAR] All %d fingerprints failed", len(order))
    return None


def _cookie_persistence_fetch(url: str) -> Optional[str]:
    """
    Strategy: Cookie persistence only.
    يحاول استخدام الكوكيز المخزنة مع curl_cffi (سريع) أو seleniumbase (بطيء).
    """
    domain = _get_domain(url)

    # ─── Phase 1: Try curl_cffi with cookies first (fast) ────────────
    if _cookie_vault.has_cookies(domain):
        from curl_cffi import requests
        saved = _cookie_vault.load_cookies(domain)
        cookie_str = _curl_cookies_to_header(saved)

        for imp in ['chrome124', 'chrome131', 'safari17_0', 'edge101']:
            try:
                headers = _random_headers()
                headers['Cookie'] = cookie_str
                r = requests.get(url, impersonate=imp, headers=headers, timeout=20)
                if r.status_code == 200:
                    body = _try_decompress(r)
                    if 'Just a moment' not in body:
                        logger.debug("[COOKIE-P] Cookie auth success with %s", imp)
                        return body
            except Exception:
                continue
        logger.debug("[COOKIE-P] Cookies present but curl_cffi still blocked (TLS fingerprint rejected)")

    # ─── Phase 2: Get fresh cookies via singleton seleniumbase ──────
    logger.debug("[COOKIE-P] Getting fresh cookies via seleniumbase singleton...")
    try:
        driver = _get_driver()

        # Inject any existing cookies
        if _cookie_vault.has_cookies(domain):
            _inject_cookies_to_driver(driver, domain)

        driver.get(url)
        _random_delay(3, 5)

        html = driver.page_source or ''
        if html and 'Just a moment' not in html and len(html) > 1000:
            _extract_cookies_from_driver(driver, domain)
            logger.debug("[COOKIE-P] Seleniumbase success (%d bytes)", len(html))
            return html

        # Try reconnect if blocked
        if 'Just a moment' in html:
            try:
                driver.uc_open_with_reconnect(url)
                _random_delay(3, 5)
                html2 = driver.page_source or ''
                if html2 and 'Just a moment' not in html2 and len(html2) > 1000:
                    _extract_cookies_from_driver(driver, domain)
                    logger.debug("[COOKIE-P] Reconnect success (%d bytes)", len(html2))
                    return html2
            except Exception:
                pass

    except Exception as e:
        logger.debug("[COOKIE-P] Seleniumbase error: %s", e)

    logger.warning("[COOKIE-P] Cookie persistence failed for %s", url)
    return None


def _proxy_rotation_chain_fetch(url: str) -> Optional[str]:
    """
    Strategy: Proxy rotation chain.
    يستخدم proxy_rotator مع كل محاولة، ويجرب بروكسيات مختلفة.
    """
    from curl_cffi import requests

    domain = _get_domain(url)
    saved_cookies = _cookie_vault.load_cookies(domain)
    cookie_header = _curl_cookies_to_header(saved_cookies)

    # Enable proxy rotation
    _proxy_integrator.enabled = True
    _proxy_integrator._lazy_load()

    imps = ['chrome124', 'chrome131', 'chrome133a', 'safari17_0', 'edge99']
    random.shuffle(imps)

    for imp in imps:
        # Get fresh proxy for each attempt
        proxy = _proxy_integrator.get_proxy(force_rotate=True)
        proxies = {'http': proxy, 'https': proxy} if proxy else {}

        try:
            headers = _random_headers()
            if cookie_header:
                headers['Cookie'] = cookie_header
            headers['X-Forwarded-For'] = proxy.split('//')[1].split(':')[0] if proxy else ''

            r = requests.get(
                url,
                impersonate=imp,
                headers=headers,
                timeout=45,
                proxies=proxies if proxies else None,
            )

            if r.status_code == 200:
                body = _try_decompress(r)
                if 'Just a moment' not in body:
                    logger.debug("[PROXY-CHAIN] %s via proxy %s",
                                imp, proxy[:30] if proxy else 'direct')
                    _proxy_integrator.report_success()
                    _extract_cookies_from_curl(domain, dict(r.cookies))
                    return body

            _proxy_integrator.report_failure()
            logger.debug("[PROXY-CHAIN] %s via %s failed (HTTP %d)",
                        imp, proxy[:30] if proxy else 'direct', r.status_code)

        except Exception as e:
            logger.debug("[PROXY-CHAIN] %s error: %s", imp, str(e)[:60])
            _proxy_integrator.report_failure()

        _random_delay(0.5, 1.5)

    logger.warning("[PROXY-CHAIN] All proxy attempts failed for %s", url)
    return None


def _multi_stage_assault_fetch(url: str) -> Optional[str]:
    """
    Strategy: Multi-stage assault.
    الهجوم متعدد المراحل:
    Stage 1: تسخين الجلسة بمواقع محايدة
    Stage 2: زيارة صفحة خفيفة على نفس الدومين
    Stage 3: الهجوم الرئيسي
    Stage 4: إعادة المحاولة بتقنيات مختلفة إذا فشل
    """
    domain = _get_domain(url)
    base_url = f'{urlparse(url).scheme}://{domain}'

    logger.debug("[MULTI-STAGE] === PHASE 1: Session warmup ===")
    # Stage 1: Warm up with neutral sites
    from curl_cffi import requests as cffi_req

    session = cffi_req.Session()
    warmup_count = random.randint(2, 3)
    warmup_sites = random.sample(_config.warmup_sites, warmup_count)

    for site in warmup_sites:
        try:
            imp = random.choice(_config.curl_impersonations)
            session.get(site, impersonate=imp,
                       headers={'User-Agent': random.choice(_config.user_agents)},
                       timeout=15)
            _random_delay(1, 2)
        except Exception:
            pass

    # Stage 2: Visit low-value page on same domain (robots.txt or sitemap)
    logger.debug("[MULTI-STAGE] === PHASE 2: Domain warmup ===")
    warmup_paths = ['/robots.txt', '/sitemap.xml', '/favicon.ico', '/']
    for path in warmup_paths:
        warmup_url = f'{base_url}{path}'
        if warmup_url == url:
            continue
        try:
            imp = random.choice(_config.curl_impersonations)
            r = session.get(warmup_url, impersonate=imp,
                          headers=_random_headers(), timeout=20)
            if r.status_code == 200:
                logger.debug("[MULTI-STAGE] Warmup %s: HTTP %d", path, r.status_code)
                # Save cookies from warmup
                if hasattr(r, 'cookies') and r.cookies:
                    _extract_cookies_from_curl(domain, dict(r.cookies))
                break
        except Exception:
            continue
        _random_delay(0.5, 1.5)

    # Stage 3: Main attack
    logger.debug("[MULTI-STAGE] === PHASE 3: Main attack ===")
    imp = random.choice(_config.curl_impersonations)
    headers = _random_headers()
    headers['Referer'] = random.choice(warmup_sites)
    proxies = _proxy_integrator.get_proxies_dict()

    try:
        r = session.get(url, impersonate=imp, headers=headers,
                       timeout=60, proxies=proxies if proxies else None)
        if r.status_code == 200:
            body = _try_decompress(r)
            if 'Just a moment' not in body and len(body) > 500:
                logger.debug("[MULTI-STAGE] Phase 3 success: %d bytes", len(body))
                _proxy_integrator.report_success()
                _extract_cookies_from_curl(domain, dict(session.cookies))
                return body
    except Exception as e:
        logger.debug("[MULTI-STAGE] Phase 3 error: %s", e)

    # Stage 4: Fallback to seleniumbase with cookie injection
    logger.debug("[MULTI-STAGE] === PHASE 4: Seleniumbase fallback ===")
    try:
        from seleniumbase import Driver
        driver = Driver(uc=True, headless=_config.headless,
                       undetected=True, disable_csp=True)

        # Inject cookies from session
        try:
            for name, value in dict(session.cookies).items():
                driver.add_cookie({'name': name, 'value': str(value), 'domain': domain})
        except Exception:
            pass

        driver.get(url)
        _random_delay(4, 6)

        # Try reconnect if blocked
        if 'Just a moment' in driver.title:
            try:
                driver.uc_open_with_reconnect(url)
                _random_delay(3, 5)
            except Exception:
                pass

        # Try CF click handler
        if 'Just a moment' in driver.title:
            try:
                driver.uc_gui_click_cf(url)
                _random_delay(3, 5)
            except Exception:
                pass

        html = driver.page_source
        if html and 'Just a moment' not in html and len(html) > 1000:
            _extract_cookies_from_driver(driver, domain)
            driver.quit()
            logger.debug("[MULTI-STAGE] Phase 4 success: %d bytes", len(html))
            return html

        driver.quit()
    except Exception as e:
        logger.debug("[MULTI-STAGE] Phase 4 error: %s", e)

    logger.warning("[MULTI-STAGE] All phases failed for %s", url)
    return None


def _ultimate_assault_fetch(url: str) -> Optional[str]:
    """
    ═══════════════════════════════════════════════════════════
    ULTIMATE ASSAULT V2 — Time-bounded phases
    ═══════════════════════════════════════════════════════════
    
    Phase 1 (15s): Cookie Vault + curl_cffi
    Phase 2 (20s): Multi-stage warmup + curl_cffi
    Phase 3 (10s): Session warmup on neutral sites
    Phase 4 (15s): Proxy rotation + curl_cffi
    Phase 5 (45s): Seleniumbase UC (singleton, 빠름)
    Phase 6 (45s): Playwright stealth (only if needed)
    Phase 7 (15s): CloudScraper / low-level (last gasp)
    
    كل طور له حد زمني صارم. الهجوم الكامل ≤ 165 ثانية.
    """
    domain = _get_domain(url)
    base_url = f'{urlparse(url).scheme}://{domain}'
    start_time = time.time()
    PHASE_TIMEOUT = 165  # Total max seconds

    def _time_left() -> float:
        return max(5, PHASE_TIMEOUT - (time.time() - start_time))

    logger.info("🔥🔥🔥 ULTIMATE ASSAULT V2: %s 🔥🔥🔥", url)

    # ─── Phase 1: Cookie Vault Direct (15s) ───────────────────
    if time.time() - start_time < 15 and _cookie_vault.has_cookies(domain):
        logger.info("[UA] Phase 1/7: Cookie Vault Direct")
        from curl_cffi import requests as cffi
        saved = _cookie_vault.load_cookies(domain)
        cookie_str = _curl_cookies_to_header(saved)

        for imp in ['chrome124', 'chrome131', 'safari17_0']:
            try:
                headers = _random_headers()
                headers['Cookie'] = cookie_str
                r = cffi.get(url, impersonate=imp, headers=headers, timeout=10)
                if r.status_code == 200:
                    body = _try_decompress(r)
                    if 'Just a moment' not in body and len(body) > 500:
                        logger.info("[UA] ✅ Phase 1: %s (cookies)", imp)
                        return body
            except Exception:
                continue
        logger.info("[UA] Phase 1: cookies present but CF rejects TLS")

    # ─── Phase 2: Multi-stage Warmup (20s) ───────────────────
    if time.time() - start_time < 20:
        logger.info("[UA] Phase 2/7: Multi-stage Warmup")
        from curl_cffi import requests as cffi
        session = cffi.Session()

        # Warmup on neutral sites
        warmup_sites = random.sample(_config.warmup_sites, min(2, len(_config.warmup_sites)))
        for site in warmup_sites:
            try:
                session.get(site, impersonate='chrome124',
                          headers={'User-Agent': random.choice(_config.user_agents)},
                          timeout=8)
            except Exception:
                pass
            _random_delay(0.3, 0.8)

        # Domain warmup
        for path in ['/robots.txt', '/']:
            warmup_url = f'{base_url}{path}'
            if warmup_url == url:
                continue
            try:
                r = session.get(warmup_url, impersonate='chrome124',
                              headers=_random_headers(), timeout=10)
                if r.status_code == 200:
                    _extract_cookies_from_curl(domain, dict(session.cookies))
                    break
            except Exception:
                continue

        # Main attack
        try:
            imp = random.choice(['chrome124', 'chrome131'])
            headers = _random_headers()
            r = session.get(url, impersonate=imp, headers=headers, timeout=15)
            if r.status_code == 200:
                body = _try_decompress(r)
                if 'Just a moment' not in body and len(body) > 500:
                    logger.info("[UA] ✅ Phase 2: warmup success")
                    _extract_cookies_from_curl(domain, dict(session.cookies))
                    return body
        except Exception:
            pass
        logger.info("[UA] Phase 2: warmup + curl still blocked")

    # ─── Phase 3: Session Warmup Only (10s) ───────────────────
    if time.time() - start_time < 45:  # generous
        logger.info("[UA] Phase 3/7: Session Warmup")
        html = _session_warmup_fetch(url, use_cookies=True)
        if html:
            logger.info("[UA] ✅ Phase 3: session warmup success")
            return html

    # ─── Phase 4: Proxy Rotation (15s) ───────────────────────
    if time.time() - start_time < 60:
        logger.info("[UA] Phase 4/7: Proxy Rotation")
        _proxy_integrator.enabled = True
        _proxy_integrator._lazy_load()

        from curl_cffi import requests as cffi
        for imp in ['chrome124', 'chrome131']:
            proxy = _proxy_integrator.get_proxy(force_rotate=True)
            proxies = {'http': proxy, 'https': proxy} if proxy else {}
            try:
                r = cffi.get(url, impersonate=imp, headers=_random_headers(),
                           timeout=20, proxies=proxies if proxies else None)
                if r.status_code == 200:
                    body = _try_decompress(r)
                    if 'Just a moment' not in body and len(body) > 500:
                        logger.info("[UA] ✅ Phase 4: proxy success")
                        return body
                _proxy_integrator.report_failure()
            except Exception:
                _proxy_integrator.report_failure()
        logger.info("[UA] Phase 4: proxy rotation failed")

    # ─── Phase 5: Seleniumbase UC (45s) ───────────────────────
    if time.time() - start_time < _time_left():
        logger.info("[UA] Phase 5/7: Seleniumbase UC (fast singleton path)")
        try:
            html = _seleniumbase_fetch(url, use_cookies=True)
            if html:
                logger.info("[UA] ✅ Phase 5: seleniumbase success")
                return html

            # Try reconnect variant
            html = _sb_uc_reconnect_fetch(url)
            if html:
                logger.info("[UA] ✅ Phase 5b: reconnect success")
                return html
        except Exception as e:
            logger.debug("[UA] Phase 5 error: %s", str(e)[:80])

    # ─── Phase 6: Playwright (45s, only if enough time) ──────
    if time.time() - start_time < _time_left() - 30:
        logger.info("[UA] Phase 6/7: Playwright Stealth")
        try:
            html = _playwright_fetch(url, use_reconnect=True)
            if html:
                logger.info("[UA] ✅ Phase 6: playwright success")
                return html
        except Exception as e:
            logger.debug("[UA] Phase 6 error: %s", str(e)[:80])

    # ─── Phase 7: Last Resort (15s) ───────────────────────────
    if time.time() - start_time < _time_left():
        logger.info("[UA] Phase 7/7: Last Resort")
        html = _cloudscraper_fetch(url)
        if html:
            logger.info("[UA] ✅ Phase 7: cloudscraper success")
            return html
        html = _curl_low_level_fetch(url)
        if html:
            logger.info("[UA] ✅ Phase 7: low-level success")
            return html

    logger.error("[UA] ❌ ALL 7 PHASES FAILED for %s", url)
    return None


# ============================================================
# MASTER BYPASS FUNCTION (محسّن)
# ============================================================

def bypass_cloudflare(
    url: str,
    strategy: Optional[BypassStrategy] = None,
    force_refresh: bool = False,
    return_headers: bool = False,
) -> Optional[Dict]:
    """
    Master Cloudflare bypass function. Tries strategies until one works.

    Args:
        url: Target URL
        strategy: Force a specific strategy, or None for auto
        force_refresh: Skip cache
        return_headers: Return response headers too

    Returns:
        dict with 'html' (and optionally 'headers', 'strategy') or None
    """
    if not force_refresh:
        cached = _cache.get(url)
        if cached:
            logger.info("[CF] Cache HIT for %s", url)
            result = {'html': cached, 'strategy': 'cache', 'cached': True}
            if return_headers:
                result['headers'] = {}
            return result

    strategies = [strategy] if strategy else _config.preferred_strategies

    logger.info("🔥 BYPASSING CLOUDFLARE: %s", url)
    logger.info("    Strategies: %s", [s.value for s in strategies])

    for s in strategies:
        logger.debug("── Trying strategy: %s ──", s.value)

        for attempt in range(_config.max_retries_per_strategy):
            try:
                html = None

                # === Core strategies ===
                if s == BypassStrategy.SELENIUMBASE_UC:
                    html = _seleniumbase_fetch(url, use_cookies=True)

                elif s == BypassStrategy.CLOUDSCRAPER:
                    html = _cloudscraper_fetch(url)

                elif s == BypassStrategy.CURL_CFFI_IMPERSONATE:
                    html = _curl_cffi_fetch(url)

                elif s == BypassStrategy.PLAYWRIGHT_STEALTH:
                    html = _playwright_fetch(url, use_reconnect=False)

                elif s == BypassStrategy.SESSION_WARMUP:
                    html = _session_warmup_fetch(url, use_cookies=True)

                elif s == BypassStrategy.CURL_LOW_LEVEL:
                    html = _curl_low_level_fetch(url)

                # === Advanced strategies ===
                elif s == BypassStrategy.SB_UC_RECONNECT:
                    html = _sb_uc_reconnect_fetch(url)

                elif s == BypassStrategy.PLAYWRIGHT_RECONNECT:
                    html = _playwright_reconnect_fetch(url)

                elif s == BypassStrategy.TLS_FINGERPRINT_VAR:
                    html = _tls_fingerprint_variation_fetch(url)

                elif s == BypassStrategy.COOKIE_PERSISTENCE:
                    html = _cookie_persistence_fetch(url)

                elif s == BypassStrategy.PROXY_ROTATION_CHAIN:
                    html = _proxy_rotation_chain_fetch(url)

                elif s == BypassStrategy.MULTI_STAGE_ASSAULT:
                    html = _multi_stage_assault_fetch(url)

                elif s == BypassStrategy.ULTIMATE_ASSAULT:
                    html = _ultimate_assault_fetch(url)

                else:
                    logger.warning("Unknown strategy: %s", s)
                    continue

                if html and len(html) > 500 and 'Just a moment' not in html:
                    logger.info("✅ BYPASS SUCCESS! Strategy: %s (attempt %d)", s.value, attempt + 1)
                    _cache.set(url, html)
                    result = {'html': html, 'strategy': s.value, 'cached': False}
                    if return_headers:
                        result['headers'] = {}
                    return result

                if html:
                    logger.debug("   %s attempt %d: got %d bytes but blocked",
                                s.value, attempt + 1, len(html))
                else:
                    logger.debug("   %s attempt %d: no response", s.value, attempt + 1)

            except Exception as e:
                logger.debug("   %s attempt %d error: %s", s.value, attempt + 1, str(e)[:100])

            _random_delay(0.5, 1.5)  # Delay between retries

    logger.error("❌ ALL STRATEGIES FAILED for %s", url)
    return None


# ============================================================
# DOMAIN-SPECIFIC HELPERS
# ============================================================

def is_cloudflare_protected(html: str) -> bool:
    """Check if a page is showing Cloudflare challenge."""
    if not html:
        return True
    return ('Just a moment' in html or '__cf_chl_tk' in html or
            'cf-mitigated' in html or 'cf-chl-widget' in html)


def fetch_fbref(url: str, force_refresh: bool = False) -> Optional[str]:
    """Fetch FBref page with CF bypass. Returns HTML or None."""
    result = bypass_cloudflare(url, force_refresh=force_refresh)
    if result:
        return result['html']
    return None


def fetch_understat(url: str, force_refresh: bool = False) -> Optional[str]:
    """Fetch Understat page (often protected, sometimes not). Returns HTML."""
    # Understat sometimes works without bypass
    try:
        from curl_cffi import requests
        headers = {
            'User-Agent': random.choice(_config.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        r = requests.get(url, impersonate='chrome124', headers=headers, timeout=30)
        if r.status_code == 200 and 'Just a moment' not in r.text:
            return r.text
    except Exception:
        pass
    return fetch_fbref(url, force_refresh)


def fetch_understat_league(league: str, season: str = '2025') -> Optional[str]:
    """Fetch Understat league page and extract JSON data."""
    url = f'https://understat.com/league/{league}/{season}'
    result = bypass_cloudflare(url, strategy=BypassStrategy.ULTIMATE_ASSAULT)
    if result:
        html = result['html']
        try:
            driver = _get_driver()
            dates_json = driver.execute_script('return JSON.stringify(datesData)')
            teams_json = driver.execute_script('return JSON.stringify(teamsData)')
            import json as _json
            return _json.dumps({
                'html': html,
                'datesData': _json.loads(dates_json) if dates_json and len(dates_json) > 10 else [],
                'teamsData': _json.loads(teams_json) if teams_json and len(teams_json) > 10 else {},
                'strategy': result.get('strategy', 'unknown'),
            })
        except Exception:
            return html
    return None


# ============================================================
# BYPASS TEST BATTERY V2 (موسّع)
# ============================================================

def run_bypass_tests_v2() -> Dict:
    """
    Run comprehensive bypass tests against all known CF-protected football sites.
    Tests ALL strategies including the new advanced ones.
    """
    logger.info("═══ CLOUDFLARE BYPASS TEST BATTERY V2 ═══")
    logger.info("═══ جميع الاستراتيجيات الـ 13 ═══")

    test_urls = [
        ('FBref (home)', 'https://fbref.com/en/'),
        ('FBref (PL)', 'https://fbref.com/en/comps/9/2025-2026/stats/2025-2026-Premier-League-Stats'),
        ('Understat (home)', 'https://understat.com/'),
        ('Understat (EPL)', 'https://understat.com/league/EPL'),
        ('Transfermarkt', 'https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1'),
    ]

    strategies = [
        # Core
        BypassStrategy.SELENIUMBASE_UC,
        BypassStrategy.CLOUDSCRAPER,
        BypassStrategy.CURL_CFFI_IMPERSONATE,
        BypassStrategy.PLAYWRIGHT_STEALTH,
        BypassStrategy.SESSION_WARMUP,
        BypassStrategy.CURL_LOW_LEVEL,
        # Advanced
        BypassStrategy.SB_UC_RECONNECT,
        BypassStrategy.PLAYWRIGHT_RECONNECT,
        BypassStrategy.TLS_FINGERPRINT_VAR,
        BypassStrategy.COOKIE_PERSISTENCE,
        BypassStrategy.PROXY_ROTATION_CHAIN,
        BypassStrategy.MULTI_STAGE_ASSAULT,
        BypassStrategy.ULTIMATE_ASSAULT,
    ]

    results = {}

    for site_name, url in test_urls:
        logger.info("\n── Testing %s: %s ──", site_name, url)
        site_results = {}

        for s in strategies:
            logger.info("  Trying %s...", s.value)
            result = bypass_cloudflare(url, strategy=s, force_refresh=True)

            if result and result['html']:
                html = result['html']
                blocked = 'Just a moment' in html
                success = not blocked and len(html) > 500
                site_results[s.value] = {
                    'success': success,
                    'blocked': blocked,
                    'html_length': len(html),
                    'strategy_used': result.get('strategy', s.value),
                }
                logger.info("    → %s (len=%d, blocked=%s)",
                          '✅ SUCCESS' if success else '❌ BLOCKED',
                          len(html), blocked)
            else:
                site_results[s.value] = {
                    'success': False,
                    'blocked': True,
                    'html_length': 0,
                    'strategy_used': s.value,
                }
                logger.info("    → ❌ FAILED")

        best = None
        for strategy_name, r in site_results.items():
            if r['success']:
                best = strategy_name
                break

        results[site_name] = {
            'url': url,
            'best_strategy': best,
            'strategies': site_results,
        }

    logger.info("\n═══ TEST RESULTS SUMMARY V2 ═══")
    for site_name, r in results.items():
        logger.info("  %s: best=%s", site_name, r['best_strategy'] or 'NONE')

    return results


# ============================================================
# CONSTANT ATTEMPT ENGINE (راعي الحلال V2)
# ============================================================

def persistent_fetch(
    url: str,
    max_time_seconds: int = 180,
    strategies: Optional[List[BypassStrategy]] = None,
) -> Optional[str]:
    """
    Relentlessly try to fetch a URL, cycling through strategies until time runs out.
    V2: Prioritizes ULTIMATE_ASSAULT first, then falls back to individual strategies.

    Args:
        url: Target URL
        max_time_seconds: Max total time to keep trying
        strategies: Strategies to cycle through

    Returns:
        HTML string or None
    """
    if strategies is None:
        strategies = [
            BypassStrategy.ULTIMATE_ASSAULT,
            BypassStrategy.MULTI_STAGE_ASSAULT,
            BypassStrategy.SB_UC_RECONNECT,
            BypassStrategy.COOKIE_PERSISTENCE,
            BypassStrategy.TLS_FINGERPRINT_VAR,
            BypassStrategy.PROXY_ROTATION_CHAIN,
            BypassStrategy.SELENIUMBASE_UC,
            BypassStrategy.PLAYWRIGHT_RECONNECT,
            BypassStrategy.PLAYWRIGHT_STEALTH,
            BypassStrategy.CURL_CFFI_IMPERSONATE,
            BypassStrategy.CLOUDSCRAPER,
            BypassStrategy.SESSION_WARMUP,
            BypassStrategy.CURL_LOW_LEVEL,
        ]

    start = time.time()
    attempts = 0

    logger.info("🔥 PERSISTENT FETCH V2: %s (max %ds)", url, max_time_seconds)

    while time.time() - start < max_time_seconds:
        for s in strategies:
            if time.time() - start >= max_time_seconds:
                break

            attempts += 1
            logger.debug("  Attempt %d: %s", attempts, s.value)

            try:
                result = bypass_cloudflare(url, strategy=s, force_refresh=True)
                if result and result['html']:
                    html = result['html']
                    if 'Just a moment' not in html and len(html) > 500:
                        logger.info("🔥 PERSISTENT V2 SUCCESS after %d attempts (%ds)!",
                                  attempts, time.time() - start)
                        return html
            except Exception:
                pass

            time.sleep(0.5)

    logger.error("❌ PERSISTENT FETCH V2 FAILED after %d attempts (%ds)",
                attempts, time.time() - start)
    return None


# ============================================================
# CLEANUP
# ============================================================

def cleanup():
    """Clean up driver resources."""
    global _driver_instance
    if _driver_instance:
        try:
            _driver_instance.quit()
            _driver_instance = None
            logger.info("Driver cleaned up")
        except Exception:
            pass


# ============================================================
# CLI
# ============================================================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Cloudflare Bypass Engine V2 — ULTIMATE ASSAULT')
    parser.add_argument('url', nargs='?', default=None, help='URL to fetch (or --test)')
    parser.add_argument('--test', action='store_true', help='Run test battery')
    parser.add_argument('--test-v2', action='store_true', help='Run V2 test battery (all 13 strategies)')
    parser.add_argument('--persistent', '-p', action='store_true', help='Persistent mode (180s)')
    parser.add_argument('--headless', action='store_true', default=True, help='Headless mode')
    parser.add_argument('--strategy', '-s', type=str, default=None,
                       choices=[s.value for s in BypassStrategy],
                       help='Force specific strategy')
    parser.add_argument('--output', '-o', type=str, default=None, help='Save HTML to file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--show-headers', action='store_true', help='Show response headers')
    parser.add_argument('--cookie-status', action='store_true', help='Show cookie vault status')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for h in logger.handlers:
            h.setLevel(logging.DEBUG)

    if args.cookie_status:
        domain = args.url or input("Enter domain: ")
        has = _cookie_vault.has_cookies(domain)
        cookies = _cookie_vault.load_cookies(domain)
        print(f"Domain: {domain}")
        print(f"Has cookies: {has}")
        print(f"Cookie count: {len(cookies) if cookies else 0}")
        if cookies:
            for c in cookies[:5]:
                print(f"  {c.get('name')}: {c.get('value', '')[:30]}...")
        sys.exit(0)

    if args.test:
        results = run_bypass_tests_v2()
        print("\n")
        import json
        print(json.dumps(results, indent=2, default=str))
        cleanup()
        sys.exit(0)

    if args.test_v2:
        results = run_bypass_tests_v2()
        print("\n")
        import json
        print(json.dumps(results, indent=2, default=str))
        cleanup()
        sys.exit(0)

    if not args.url:
        parser.print_help()
        sys.exit(1)

    url = args.url

    if args.persistent:
        html = persistent_fetch(url, max_time_seconds=180)
    elif args.strategy:
        strategy = BypassStrategy(args.strategy)
        result = bypass_cloudflare(url, strategy=strategy, force_refresh=True,
                                  return_headers=args.show_headers)
        if result:
            html = result['html']
            if args.show_headers and 'headers' in result:
                print(f"Headers: {result['headers']}")
        else:
            html = None
    else:
        result = bypass_cloudflare(url, force_refresh=True,
                                  return_headers=args.show_headers)
        if result:
            html = result['html']
            print(f"Strategy used: {result.get('strategy', 'unknown')}")
            if args.show_headers and 'headers' in result:
                print(f"Headers: {result['headers']}")
        else:
            html = None

    if html:
        print(f"✅ SUCCESS: {len(html)} bytes")
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"   Saved to {args.output}")
        else:
            print(f"\n--- First 2000 chars ---\n{html[:2000]}\n...")
    else:
        print("❌ FAILED to bypass Cloudflare")
        sys.exit(1)

    cleanup()
