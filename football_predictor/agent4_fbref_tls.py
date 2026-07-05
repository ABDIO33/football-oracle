#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█  AGENT 4 — tls_client FBref Scraper (Multi-Fingerprint)                  █
█  Uses tls-client with Chrome 131, OkHttp4, Safari 17 fingerprints        █
█  Attempts to bypass FBref/Cloudflare TLS fingerprinting                  █
██████████████████████████████████████████████████████████████████████████████
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, sys, json, re, time, random
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import tls_client
    TLS_CLIENT_OK = True
except ImportError:
    TLS_CLIENT_OK = False

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import lxml
    LXML_OK = True
except ImportError:
    LXML_OK = False

try:
    from curl_cffi import requests as curl_requests
    CURL_OK = True
except ImportError:
    CURL_OK = False


@dataclass
class FBrefTLSConfig:
    output_dir: str = "heist_output"
    max_retries_per_fingerprint: int = 2
    delay_between_requests: float = 1.5
    
    # Target URLs for different data types
    urls = {
        "results": "https://fbref.com/en/comps/9/Premier-League-Stats",
        "scores_fixtures": "https://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures",
        "player_stats": "https://fbref.com/en/comps/9/stats/Premier-League-Stats",
        "shooting": "https://fbref.com/en/comps/9/shooting/Premier-League-Stats",
        "passing": "https://fbref.com/en/comps/9/passing/Premier-League-Stats",
        "defense": "https://fbref.com/en/comps/9/defense/Premier-League-Stats",
        "possession": "https://fbref.com/en/comps/9/possession/Premier-League-Stats",
        "big5": "https://fbref.com/en/comps/Big5/Big-5-European-Leagues-Stats",
    }


class FBrefTLSScraper:
    """
    FBref scraper using tls-client with multiple TLS fingerprints.
    
    Fingerprints tested:
      - chrome_131 (latest Chrome)
      - okhttp4 (Android)
      - safari_17 (macOS)
      - chrome_124 (fallback)
      - firefox_120 (fallback)
    
    Strategy:
      1. Try each fingerprint in rotation
      2. Add randomized headers per request
      3. Parse HTML tables with BeautifulSoup
    """
    
    # All TLS fingerprints to try
    FINGERPRINTS = [
        "chrome_131",
        "chrome_130",
        "chrome_124",
        "chrome_120",
        "chrome_110",
        "okhttp4",
        "okhttp3",
        "safari_17",
        "safari_16_5",
        "safari_15_6_1",
        "safari_ios_17",
        "firefox_120",
        "firefox_117",
        "opera_90",
    ]
    
    def __init__(self, config: Optional[FBrefTLSConfig] = None):
        self.config = config or FBrefTLSConfig()
        self.session_cache: Dict[str, tls_client.Session] = {}
        self.results: Dict[str, Any] = {}
        self.fingerprint_success: Dict[str, bool] = {}
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def _make_session(self, fingerprint: str) -> tls_client.Session:
        """Create a tls-client session with a specific fingerprint."""
        try:
            session = tls_client.Session(
                client_identifier=fingerprint,
                random_tls_extension_order=True,
            )
            
            # Randomized headers
            session.headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": random.choice([
                    "en-US,en;q=0.9",
                    "en-GB,en;q=0.8",
                    "en,fr;q=0.7",
                ]),
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Ch-Ua": f'"Chromium";v="{fingerprint.split("_")[1] if "_" in fingerprint else "131"}", "Google Chrome";v="{fingerprint.split("_")[1] if "_" in fingerprint else "131"}"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": random.choice(['"Windows"', '"macOS"', '"Linux"']),
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": self._random_ua(fingerprint),
            }
            
            # Add cookies
            session.cookies.set("fbref_cache", "1")
            
            return session
            
        except Exception as e:
            print(f"  [!] Failed to create session for {fingerprint}: {e}")
            return None
    
    def _random_ua(self, fingerprint: str) -> str:
        """Generate a matching User-Agent for the fingerprint."""
        uas = {
            "chrome_131": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "chrome_130": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "chrome_124": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "safari_17": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "safari_16_5": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            "okhttp4": "okhttp/4.12.0",
            "okhttp3": "okhttp/3.14.9",
            "firefox_120": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        }
        return uas.get(fingerprint, uas["chrome_131"])
    
    # Wayback Machine / Google Cache fallback URLs
    WAYBACK_BASE = "https://web.archive.org/web/20250601000000/"
    GOOGLE_CACHE = "https://webcache.googleusercontent.com/search?q=cache:"
    
    def fetch_via_wayback(self, url: str) -> Tuple[Optional[str], str, Dict]:
        """Fetch FBref via Wayback Machine as fallback."""
        print(f"  [*] Trying Wayback Machine...")
        wayback_url = f"{self.WAYBACK_BASE}{url}"
        try:
            import requests as std_requests
            resp = std_requests.get(wayback_url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code == 200 and len(resp.text) > 5000 and "fbref" in resp.text.lower():
                print(f"  [✓] Wayback Machine SUCCESS ({len(resp.text):,} bytes)")
                return resp.text, "wayback_machine", dict(resp.headers)
        except Exception as e:
            print(f"  [!] Wayback Machine failed: {e}")
        return None, "wayback_failed", {}
    
    def fetch_via_google_cache(self, url: str) -> Tuple[Optional[str], str, Dict]:
        """Fetch FBref via Google Cache."""
        print(f"  [*] Trying Google Cache...")
        cache_url = f"{self.GOOGLE_CACHE}{url}"
        try:
            import requests as std_requests
            resp = std_requests.get(cache_url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code == 200 and len(resp.text) > 5000 and "fbref" in resp.text.lower():
                print(f"  [✓] Google Cache SUCCESS ({len(resp.text):,} bytes)")
                return resp.text, "google_cache", dict(resp.headers)
        except Exception as e:
            print(f"  [!] Google Cache failed: {e}")
        return None, "google_cache_failed", {}
    
    def fetch_via_curl_cffi(self, url: str) -> Tuple[Optional[str], str, Dict]:
        """Fetch FBref via curl_cffi with Chrome 120 impersonation."""
        if not CURL_OK:
            return None, "curl_not_available", {}
        print(f"  [*] Trying curl_cffi Chrome120...")
        try:
            resp = curl_requests.get(url, impersonate="chrome120", timeout=30)
            if resp.status_code == 200 and len(resp.text) > 5000 and "fbref" in resp.text.lower():
                print(f"  [✓] curl_cffi SUCCESS ({len(resp.text):,} bytes)")
                return resp.text, "curl_cffi_chrome120", dict(resp.headers)
            print(f"  [✗] curl_cffi HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [!] curl_cffi failed: {e}")
        return None, "curl_cffi_failed", {}
    
    def try_fetch(self, url: str, fingerprint: str = None) -> Tuple[Optional[str], str, Dict]:
        """
        Try to fetch a URL with the given fingerprint.
        
        Returns: (html_content, fingerprint_used, response_headers)
        """
        if fingerprint:
            fingerprints_to_try = [fingerprint]
        else:
            # Try primary fingerprints first, then fallbacks
            fingerprints_to_try = self.FINGERPRINTS[:3] + self.FINGERPRINTS[3:]
        
        last_error = None
        
        for fp in fingerprints_to_try:
            try:
                print(f"  [*] Trying {fp}...")
                
                session = self._make_session(fp)
                if not session:
                    continue
                
                resp = session.get(url, timeout_seconds=30)
                
                if resp.status_code == 200:
                    text = resp.text
                    
                    # Check if it's real FBref content
                    if "fbref" in text.lower() and len(text) > 5000:
                        print(f"  [✓] {fp} SUCCESS! ({len(text):,} bytes)")
                        self.fingerprint_success[fp] = True
                        return text, fp, dict(resp.headers)
                    elif "cloudflare" in text.lower() or "just a moment" in text.lower():
                        print(f"  [✗] {fp} Blocked by Cloudflare")
                    else:
                        print(f"  [✗] {fp} Unexpected response ({len(text)} bytes)")
                
                elif resp.status_code == 403:
                    print(f"  [✗] {fp} 403 Forbidden")
                elif resp.status_code == 429:
                    print(f"  [✗] {fp} 429 Rate Limited")
                    time.sleep(5)
                else:
                    print(f"  [✗] {fp} HTTP {resp.status_code}")
                
                last_error = resp.status_code
                
            except Exception as e:
                print(f"  [!] {fp} Error: {type(e).__name__}: {e}")
                last_error = e
            
            time.sleep(self.config.delay_between_requests * random.uniform(0.8, 1.5))
        
        return None, "all_failed", {"error": str(last_error)}
    
    def fetch_multiple(self, url_keys: List[str] = None) -> Dict[str, Any]:
        """Fetch multiple FBref pages and try different fingerprints."""
        if url_keys is None:
            url_keys = list(self.config.urls.keys())[:3]  # First 3 by default
        
        results = {}
        
        for key in url_keys:
            url = self.config.urls.get(key)
            if not url:
                print(f"[!] Unknown URL key: {key}")
                continue
            
            print(f"\n{'='*60}")
            print(f"[*] Fetching: {key}")
            print(f"[*] URL: {url}")
            print(f"{'='*60}")
            
            html, fingerprint, headers = self.try_fetch(url)
            
            if html:
                tables = self.parse_fbref_tables(html)
                results[key] = {
                    "url": url,
                    "success": True,
                    "fingerprint": fingerprint,
                    "html_size": len(html),
                    "tables": tables,
                    "table_count": len(tables),
                }
                print(f"[+] Got {len(tables)} tables from {key}")
            else:
                results[key] = {
                    "url": url,
                    "success": False,
                    "error": "All fingerprints failed",
                    "last_fingerprint": fingerprint,
                }
                print(f"[✗] Failed to fetch {key}")
        
        # Save results
        self.results.update(results)
        self._save_results()
        
        return results
    
    def parse_fbref_tables(self, html: str) -> Dict[str, List[Dict]]:
        """Parse FBref HTML tables into structured data."""
        soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
        tables = {}
        
        # Find all stat tables
        for table in soup.select("table.stats_table, table[id*='stats'], table[id*='sched'], table[id*='results']"):
            # Get table caption/ID
            caption = table.select_one("caption")
            table_id = table.get("id", "")
            table_name = caption.get_text(strip=True) if caption else table_id
            
            if not table_name:
                continue
            
            # Parse header
            headers = []
            thead = table.select_one("thead")
            if thead:
                header_row = thead.select_one("tr")
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.select("th")]
            
            if not headers:
                # Try data attributes
                first_row = table.select_one("tbody tr")
                if first_row:
                    headers = [f"col_{i}" for i in range(len(first_row.select("td, th")))]
            
            # Parse rows
            rows_data = []
            for row in table.select("tbody tr:not(.thead)"):
                cells = row.select("td, th")
                
                row_dict = {}
                for i, cell in enumerate(cells):
                    col_name = headers[i] if i < len(headers) else f"col_{i}"
                    
                    # Get text and links
                    text = cell.get_text(strip=True)
                    link = cell.select_one("a")
                    href = link.get("href", "") if link else ""
                    
                    # Try to parse numeric value
                    try:
                        num_val = float(text.replace(",", "").replace("—", "0").replace("", "0"))
                        if "." in text or num_val != int(num_val) if "." in text else True:
                            row_dict[col_name] = {
                                "text": text,
                                "value": num_val,
                                "url": href,
                            }
                        else:
                            row_dict[col_name] = {
                                "text": text,
                                "value": int(num_val),
                                "url": href,
                            }
                    except (ValueError, AttributeError):
                        row_dict[col_name] = {
                            "text": text,
                            "url": href,
                            "value": None,
                        }
                
                if row_dict:
                    rows_data.append(row_dict)
            
            if rows_data:
                tables[table_name] = {
                    "headers": headers,
                    "rows": len(rows_data),
                    "data": rows_data,
                }
        
        return tables
    
    def _save_results(self):
        """Save all scraped results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save structured data
        data_path = os.path.join(
            self.config.output_dir,
            f"fbref_tls_data_{timestamp}.json"
        )
        
        # Strip HTML from output to keep file manageable
        stripped_results = {}
        for key, val in self.results.items():
            if isinstance(val, dict):
                stripped = {k: v for k, v in val.items() if k != "html"}
                stripped_results[key] = stripped
            else:
                stripped_results[key] = val
        
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump({
                "source": "fbref.com via tls-client",
                "timestamp": timestamp,
                "fingerprints_tested": self.FINGERPRINTS,
                "fingerprint_success": self.fingerprint_success,
                "results": stripped_results,
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n[+] Data saved to {data_path}")
        
        # Save success report
        report_path = os.path.join(
            self.config.output_dir,
            f"fbref_tls_report_{timestamp}.json"
        )
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "fingerprint_success": self.fingerprint_success,
                "working_fingerprints": [k for k, v in self.fingerprint_success.items() if v],
                "failed_fingerprints": [k for k in self.FINGERPRINTS if k not in self.fingerprint_success],
            }, f, indent=2)
        
        print(f"[+] Report saved to {report_path}")
    
    def get_summary(self) -> Dict:
        """Get summary of all scraping attempts."""
        return {
            "fingerprints_tested": len(self.FINGERPRINTS),
            "fingerprints_successful": sum(1 for v in self.fingerprint_success.values() if v),
            "working_fingerprints": [k for k, v in self.fingerprint_success.items() if v],
            "failed_fingerprints": [k for k in self.FINGERPRINTS if k not in self.fingerprint_success],
            "pages_fetched": sum(1 for v in self.results.values() if isinstance(v, dict) and v.get("success")),
            "pages_failed": sum(1 for v in self.results.values() if isinstance(v, dict) and not v.get("success")),
        }


# ═══════════════════════════════════════════════════════════════════════
# MAIN — Test
# ═══════════════════════════════════════════════════════════════════════

def test_scraper():
    """Test tls_client FBref scraper with all fingerprints."""
    if not TLS_CLIENT_OK:
        print("[!] tls_client not installed. Run: pip install tls-client")
        return
    
    # First try curl_cffi (more likely to work)
    scraper = FBrefTLSScraper(FBrefTLSConfig())
    print("\n[PHASE 0] Trying curl_cffi first (best chance)...")
    html, method, _ = scraper.fetch_via_curl_cffi(scraper.config.urls["scores_fixtures"])
    if html:
        print(f"[✓] curl_cffi succeeded! Method: {method}")
        tables = scraper.parse_fbref_tables(html)
        print(f"  Tables found: {len(tables)}")
        return
    
    # Try Wayback Machine
    print("\n[PHASE 0b] Trying Wayback Machine...")
    html, method, _ = scraper.fetch_via_wayback(scraper.config.urls["scores_fixtures"])
    if html:
        print(f"[✓] Wayback Machine succeeded!")
        tables = scraper.parse_fbref_tables(html)
        print(f"  Tables found: {len(tables)}")
        return
    
    config = FBrefTLSConfig()
    scraper = FBrefTLSScraper(config)
    
    print("=" * 70)
    print("FBref TLS-Fingerprint Scraper — Multi-Fingerprint Test")
    print("=" * 70)
    print(f"\nFingerprints to test ({len(scraper.FINGERPRINTS)}):")
    for fp in scraper.FINGERPRINTS:
        print(f"  - {fp}")
    print()
    
    # Test with the scores/fixtures page
    results = scraper.fetch_multiple(["scores_fixtures"])
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    summary = scraper.get_summary()
    
    for key, val in summary.items():
        if isinstance(val, list):
            print(f"  {key}: {', '.join(val) if val else 'none'}")
        else:
            print(f"  {key}: {val}")
    
    # If we got tables, show first one
    for key, data in results.items():
        if data.get("success"):
            tables = data.get("tables", {})
            for table_name, table_data in list(tables.items())[:2]:
                print(f"\n  Table: {table_name}")
                print(f"  Rows: {table_data['rows']}")
                print(f"  Headers: {table_data['headers'][:10]}...")
                if table_data["data"]:
                    first = table_data["data"][0]
                    print(f"  First row sample: {dict(list(first.items())[:5])}")


if __name__ == "__main__":
    test_scraper()
