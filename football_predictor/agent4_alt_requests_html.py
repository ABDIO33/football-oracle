#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█  AGENT 4 — Requests-HTML Fallback Scraper (Alt Agent)                    █
█  Uses requests-html with JavaScript render() for sites that need JS      █
█  Primary fallback when Selenium/Playwright/tls_client fail                █
█  Can render JS-heavy pages, execute embedded scripts, wait for elements  █
██████████████████████████████████████████████████████████████████████████████
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, sys, json, re, time, random, asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

try:
    from requests_html import HTMLSession, AsyncHTMLSession
    REQUESTS_HTML_OK = True
except ImportError:
    REQUESTS_HTML_OK = False

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


@dataclass
class AltScraperConfig:
    output_dir: str = "heist_output"
    timeout: int = 30
    retries: int = 3
    render_timeout: int = 15  # seconds for JS rendering
    delay_between: float = 1.5
    
    # Proxies for rotation (empty = no proxy)
    proxies: List[str] = None
    
    # User agents to rotate
    user_agents: List[str] = None
    
    def __post_init__(self):
        if self.proxies is None:
            self.proxies = []
        if self.user_agents is None:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            ]


class RequestsHTMLFallbackScraper:
    """
    Fallback scraper using requests-html with JavaScript rendering.
    
    Use when:
      - SeleniumBase UC fails due to detection
      - Playwright is unavailable
      - tls_client can't bypass Cloudflare
      - Sites require basic JS rendering
    
    Capabilities:
      - JavaScript rendering with Chromium (via render())
      - Full page interaction (scroll, click, wait)
      - Cookie management and session persistence
      - Proxy rotation
      - Smart retry with backoff
    """
    
    def __init__(self, config: Optional[AltScraperConfig] = None):
        self.config = config or AltScraperConfig()
        self.session: Optional[HTMLSession] = None
        self.results: Dict[str, Any] = {}
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def _get_session(self) -> HTMLSession:
        """Get or create an HTML session."""
        if self.session is None:
            print("[*] Creating requests-html session...")
            self.session = HTMLSession()
            
            if not REQUESTS_HTML_OK:
                print("[!] requests-html not available!")
                return self.session
        return self.session
    
    def _random_headers(self) -> Dict[str, str]:
        """Generate randomized headers for a request."""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.8"]),
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "DNT": "1",
            "User-Agent": random.choice(self.config.user_agents),
            "Referer": random.choice([
                "https://www.google.com/",
                "https://www.bing.com/",
                "https://duckduckgo.com/",
            ]),
        }
    
    def fetch(self, url: str, render_js: bool = False, **kwargs) -> Optional[str]:
        """
        Fetch a URL, optionally rendering JavaScript.
        
        Args:
            url: The URL to fetch
            render_js: If True, render JavaScript (uses Chromium)
            **kwargs: Additional arguments for render()
                - sleep: seconds to wait after render (default: 2)
                - wait: selector to wait for
                - scroll: whether to scroll the page
                - timeout: render timeout in seconds
        
        Returns:
            HTML string or None on failure
        """
        if not REQUESTS_HTML_OK:
            print("[!] requests-html not installed. Run: pip install requests-html")
            return None
        
        session = self._get_session()
        
        for attempt in range(self.config.retries):
            try:
                headers = self._random_headers()
                
                # Add proxy if configured
                proxies = None
                if self.config.proxies:
                    proxy = random.choice(self.config.proxies)
                    proxies = {"http": proxy, "https": proxy}
                
                print(f"  [*] GET {url[:80]}...")
                response = session.get(
                    url,
                    headers=headers,
                    proxies=proxies,
                    timeout=self.config.timeout,
                )
                
                if response.status_code != 200:
                    print(f"  [!] HTTP {response.status_code}, retry {attempt+1}/{self.config.retries}")
                    time.sleep(2 * (attempt + 1))
                    continue
                
                html = response.text
                
                # Render JavaScript if requested
                if render_js and hasattr(response, 'html'):
                    render_kwargs = {
                        "timeout": kwargs.get("timeout", self.config.render_timeout),
                    }
                    
                    # Optional: sleep after render
                    sleep_time = kwargs.get("sleep", 2)
                    if sleep_time:
                        render_kwargs["sleep"] = sleep_time
                    
                    # Optional: wait for a specific selector
                    wait_selector = kwargs.get("wait")
                    if wait_selector:
                        render_kwargs["wait"] = wait_selector
                    
                    print(f"  [*] Rendering JS ({self.config.render_timeout}s timeout)...")
                    response.html.render(**render_kwargs)
                    
                    html = response.html.html
                    print(f"  [+] JS rendered, got {len(html):,} bytes of HTML")
                else:
                    print(f"  [+] Got {len(html):,} bytes (no JS render)")
                
                return html
                
            except Exception as e:
                print(f"  [!] Attempt {attempt+1} failed: {type(e).__name__}: {e}")
                time.sleep(3 * (attempt + 1))
        
        return None
    
    async def fetch_async(self, url: str, render_js: bool = False) -> Optional[str]:
        """Async version of fetch."""
        if not REQUESTS_HTML_OK:
            print("[!] requests-html not installed")
            return None
        
        try:
            session = AsyncHTMLSession()
            
            headers = self._random_headers()
            response = await session.get(
                url,
                headers=headers,
                timeout=self.config.timeout,
            )
            
            if response.status_code != 200:
                return None
            
            html = response.text
            
            if render_js:
                print(f"  [*] Rendering JS (async)...")
                await response.html.arender(
                    timeout=self.config.render_timeout,
                    sleep=2,
                )
                html = response.html.html
            
            await session.close()
            return html
            
        except Exception as e:
            print(f"  [!] Async fetch error: {e}")
            return None
    
    def fetch_with_selenium_fallback(self, url: str, **kwargs) -> Optional[str]:
        """
        Try requests-html first, fall back to JS rendering.
        
        This is the main entry point for "try everything" approach.
        """
        print(f"\n[*] Alt Agent: {url[:80]}")
        
        # Try 1: Plain request (fastest)
        print("  [Attempt 1] Plain HTTP request...")
        html = self.fetch(url, render_js=False)
        if html and self._validate_content(html, url):
            print("  [✓] Plain request succeeded!")
            return html
        
        # Try 2: JS rendering
        print("  [Attempt 2] With JS rendering...")
        html = self.fetch(url, render_js=True, **kwargs)
        if html and self._validate_content(html, url):
            print("  [✓] JS render succeeded!")
            return html
        
        # Try 3: Async JS rendering
        print("  [Attempt 3] Async JS rendering...")
        try:
            html = asyncio.run(self.fetch_async(url, render_js=True))
            if html and self._validate_content(html, url):
                print("  [✓] Async render succeeded!")
                return html
        except Exception as e:
            print(f"  [!] Async failed: {e}")
        
        print("  [✗] All fallback attempts failed")
        return None
    
    def _validate_content(self, html: str, url: str) -> bool:
        """Check if the response contains real content (not a captcha/block page)."""
        if not html or len(html) < 200:
            return False
        
        indicators = ["just a moment", "captcha", "access denied", "ddos protection"]
        if any(ind in html.lower() for ind in indicators):
            return False
        
        # Require some meaningful HTML structure
        if "<html" not in html.lower() and "<!" not in html[:500]:
            return False
        
        return True
    
    def auto_extract(self, url: str, render_js: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Fetch a page and extract structured data.
        
        Returns dict with:
          - html: raw HTML
          - soup: BeautifulSoup object
          - title: page title
          - tables: list of HTML tables found
          - links: extracted links
          - text: cleaned text content
        """
        html = self.fetch_with_selenium_fallback(url, render_js=render_js, **kwargs)
        
        if not html:
            return {"success": False}
        
        soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
        
        result = {
            "success": True,
            "html": html,
            "soup": soup,
            "title": soup.title.get_text(strip=True) if soup.title else "",
            "url": url,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Extract tables
        tables = []
        for table in soup.select("table"):
            rows = []
            for row in table.select("tr"):
                cells = [cell.get_text(strip=True) for cell in row.select("td, th")]
                if cells:
                    rows.append(cells)
            if rows:
                table_name = table.get("id", "") or table.select_one("caption")
                table_name = table_name.get_text(strip=True) if hasattr(table_name, 'get_text') else table_name
                tables.append({
                    "name": table_name if table_name else f"table_{len(tables)}",
                    "rows": len(rows),
                    "data": rows,
                })
        result["tables"] = tables
        
        # Extract links
        links = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href and text and not href.startswith("#"):
                links.append({
                    "text": text[:100],
                    "href": href,
                    "url": urljoin(url, href),
                })
        result["links"] = links[:50]  # Cap at 50
        
        # Clean text
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        result["text"] = soup.get_text(separator="\n", strip=True)[:5000]
        
        return result
    
    def save_result(self, data: Any, name: str):
        """Save result to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            self.config.output_dir,
            f"altscraper_{name}_{timestamp}.json"
        )
        
        # If data contains soup or other non-serializable, strip it
        if isinstance(data, dict):
            save_data = {k: v for k, v in data.items() if k != "soup" and k != "html"}
        else:
            save_data = data
        
        with open(output_path, "w", encoding="utf-8") as f:
            if isinstance(save_data, dict):
                json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump({"data": str(save_data)}, f, indent=2)
        
        print(f"[+] Saved to {output_path}")


# ═══════════════════════════════════════════════════════════════════════
# TARGET-SPECIFIC SCRAPERS
# ═══════════════════════════════════════════════════════════════════════

def scrape_fbref_fallback():
    """Try FBref with requests-html fallback."""
    scraper = RequestsHTMLFallbackScraper()
    
    urls = [
        "https://fbref.com/en/comps/9/Premier-League-Stats",
        "https://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures",
    ]
    
    for url in urls:
        result = scraper.auto_extract(url, render_js=False)
        if result["success"]:
            scraper.save_result({
                "url": url,
                "title": result["title"],
                "table_count": len(result["tables"]),
                "text_preview": result["text"][:500],
            }, "fbref_fallback")
            return result
    
    # If plain failed, try JS render (FBref is mostly static)
    return None


def scrape_transfermarkt_fallback():
    """Try Transfermarkt with requests-html fallback."""
    scraper = RequestsHTMLFallbackScraper()
    
    url = "https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1"
    result = scraper.auto_extract(url, render_js=False)
    
    if result["success"]:
        scraper.save_result({
            "url": url,
            "title": result["title"],
            "table_count": len(result["tables"]),
        }, "transfermarkt_fallback")
    
    return result


def scrape_betexplorer_fallback():
    """Try BetExplorer with requests-html fallback."""
    scraper = RequestsHTMLFallbackScraper()
    
    url = "https://www.betexplorer.com/soccer/england/premier-league/results/"
    result = scraper.auto_extract(url, render_js=False)
    
    if result["success"]:
        scraper.save_result({
            "url": url,
            "title": result["title"],
            "table_count": len(result["tables"]),
            "links": result["links"][:10],
        }, "betexplorer_fallback")
    
    return result


def test_fallback():
    """Test the fallback scraper on multiple sources."""
    print("=" * 70)
    print("REQUESTS-HTML FALLBACK SCRAPER — Multi-Source Test")
    print("=" * 70)
    
    results = {}
    
    # Test 1: FBref
    print("\n" + "-" * 50)
    print("[TEST 1] FBref")
    print("-" * 50)
    results["fbref"] = scrape_fbref_fallback()
    
    # Test 2: Transfermarkt
    print("\n" + "-" * 50)
    print("[TEST 2] Transfermarkt")
    print("-" * 50)
    results["transfermarkt"] = scrape_transfermarkt_fallback()
    
    # Test 3: BetExplorer
    print("\n" + "-" * 50)
    print("[TEST 3] BetExplorer")
    print("-" * 50)
    results["betexplorer"] = scrape_betexplorer_fallback()
    
    # Summary
    print("\n" + "=" * 70)
    print("FALLBACK TEST SUMMARY")
    print("=" * 70)
    for source, result in results.items():
        if result and result.get("success"):
            print(f"  [✓] {source}: {result.get('title', '?')[:50]} - {result.get('table_count', 0)} tables")
        else:
            print(f"  [✗] {source}: FAILED")


if __name__ == "__main__":
    test_fallback()
