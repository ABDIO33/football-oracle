#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█  AGENT 4 — Playwright Stealth Soccerway + Flashscore Scraper              █
█  Uses Playwright with playwright-stealth plugin for bot detection bypass █
█  Extracts match stats, odds, and results from soccerway.com & flashscore █
██████████████████████████████████████████████████████████████████████████████
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, sys, json, re, time, asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False

try:
    from playwright_stealth import Stealth
    STEALTH_OK = True
except ImportError:
    STEALTH_OK = False

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
class PlaywrightStealthConfig:
    headless: bool = False
    timeout: int = 60000  # ms
    max_retries: int = 3
    output_dir: str = "heist_output"
    viewport: Dict = None
    
    def __post_init__(self):
        if self.viewport is None:
            self.viewport = {"width": 1920, "height": 1080}


class PlaywrightStealthScraper:
    """
    Playwright-based scraper with stealth plugin for sites with strong bot detection.
    
    Targets:
      - Soccerway: /matches/ → match results, stats
      - Flashscore: /match/{id}/ → live scores, odds, statistics
    """
    
    def __init__(self, config: Optional[PlaywrightStealthConfig] = None):
        self.config = config or PlaywrightStealthConfig()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    async def _init_browser(self):
        """Initialize Playwright browser with stealth."""
        if self.browser is None:
            print("[*] Launching Playwright with stealth plugin...")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                ],
            )
            
            self.context = await self.browser.new_context(
                viewport=self.config.viewport,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="Europe/London",
                permissions=[],
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            
            # Hook stealth into context for auto-application
            if STEALTH_OK:
                Stealth.hook_playwright_context(self.context)
            
            print("[+] Browser launched with stealth")
    
    async def _stealth_page(self, page: Page):
        """Apply stealth techniques to a page."""
        if STEALTH_OK:
            await Stealth.apply_stealth_async(page)
            print("  [*] Stealth plugin applied")
        
        # Additional evasion
        await page.add_init_script("""
            // Override navigator properties
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Override chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {},
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
            );
        """)
    
    async def _safe_get(self, page: Page, url: str, retries: int = None) -> bool:
        """Navigate with retry + stealth."""
        retries = retries or self.config.max_retries
        
        for attempt in range(retries):
            try:
                await page.goto(url, wait_until="networkidle", timeout=self.config.timeout)
                await page.wait_for_timeout(2000)
                
                # Check for bot detection
                content = await page.content()
                if any(phrase in content.lower() for phrase in [
                    "just a moment", "ddos", "captcha", "access denied",
                    "please wait", "verify you are human", "automated access"
                ]) and len(content) < 2000:
                    print(f"[!] Bot detection, retry {attempt+1}/{retries}")
                    await page.wait_for_timeout(5000 * (attempt + 1))
                    continue
                
                return True
            except Exception as e:
                print(f"[!] Error: {e}, retry {attempt+1}/{retries}")
                await page.wait_for_timeout(2000)
        
        return False
    
    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML with best available parser."""
        if LXML_OK:
            return BeautifulSoup(html, "lxml")
        return BeautifulSoup(html, "html.parser")
    
    # ═══════════════════════════════════════════════════════════════════
    # SOCCERWAY
    # ═══════════════════════════════════════════════════════════════════
    
    async def soccerway_matches(self, league_path: str = None) -> List[Dict]:
        """Scrape match results from soccerway.com."""
        if not league_path:
            league_path = "england/premier-league"
        
        url = f"https://us.soccerway.com/national/{league_path}/20252026/regular-season/r81177/matches/"
        print(f"[*] Soccerway: {url}")
        
        await self._init_browser()
        page = await self.context.new_page()
        await self._stealth_page(page)
        
        try:
            if not await self._safe_get(page, url):
                return []
            
            await page.wait_for_timeout(3000)
            html = await page.content()
            soup = self._parse_html(html)
            
            matches = []
            
            # Soccerway match table
            table = soup.select_one("table.matches, table:has(tr.match)") 
            if not table:
                # Try the common structure
                table = soup.select_one("table[id*='matches']")
            
            if table:
                rows = table.select("tr.match, tr:has(td.match-date), tr:has(td.team)") 
                
                current_date = ""
                for row in rows:
                    try:
                        # Date row
                        date_cell = row.select_one("td.match-date, th.date")
                        if date_cell:
                            current_date = date_cell.get_text(strip=True)
                            continue
                        
                        cells = row.select("td")
                        if len(cells) < 6:
                            continue
                        
                        home_el = row.select_one("td.team-home, td.team-a")
                        away_el = row.select_one("td.team-away, td.team-b")
                        score_el = row.select_one("td.score, td:has(a)")
                        
                        home = home_el.get_text(strip=True) if home_el else ""
                        away = away_el.get_text(strip=True) if away_el else ""
                        
                        score_text = score_el.get_text(strip=True) if score_el else ""
                        score_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', score_text)
                        
                        # Link to match details
                        link = row.select_one("a[href*='/matches/']")
                        match_url = ""
                        if link:
                            href = link.get("href", "")
                            match_url = f"https://us.soccerway.com{href}" if href.startswith("/") else href
                        
                        match = {
                            "date": current_date,
                            "home_team": home,
                            "away_team": away,
                            "score": score_text,
                            "home_goals": int(score_match.group(1)) if score_match else None,
                            "away_goals": int(score_match.group(2)) if score_match else None,
                            "url": match_url,
                            "source": "soccerway",
                        }
                        matches.append(match)
                        
                    except Exception:
                        continue
            
            # Fallback: find all match links
            if not matches:
                for a in soup.select("a[href*='/matches/']"):
                    text = a.get_text(strip=True)
                    if " vs " in text or " - " in text:
                        score_link = a.select_one("span.score, span:has(span)")
                        matches.append({
                            "text": text,
                            "url": a.get("href", ""),
                            "source": "soccerway",
                        })
            
            print(f"[+] Soccerway: {len(matches)} matches found")
            return matches
            
        finally:
            await page.close()
    
    async def soccerway_match_stats(self, match_url: str) -> Optional[Dict]:
        """Get detailed match statistics from Soccerway."""
        print(f"[*] Soccerway match details: {match_url}")
        
        page = await self.context.new_page()
        await self._stealth_page(page)
        
        try:
            if not await self._safe_get(page, match_url):
                return None
            
            await page.wait_for_timeout(3000)
            html = await page.content()
            soup = self._parse_html(html)
            
            stats = {"source": "soccerway"}
            
            # Statistics tables
            for table in soup.select("table:has(th), table.stats"):
                rows = table.select("tr")
                for row in rows:
                    cells = row.select("td, th")
                    if len(cells) >= 3:
                        stat_name = cells[1].get_text(strip=True) if len(cells) >= 2 else ""
                        home_val = cells[0].get_text(strip=True)
                        away_val = cells[2].get_text(strip=True)
                        stats[stat_name.lower().replace(" ", "_")] = {
                            "home": home_val,
                            "away": away_val,
                        }
            
            return stats if len(stats) > 1 else None
            
        finally:
            await page.close()
    
    # ═══════════════════════════════════════════════════════════════════
    # FLASHSCORE
    # ═══════════════════════════════════════════════════════════════════
    
    async def flashscore_matches(self, league_id: str = None) -> List[Dict]:
        """
        Scrape match data from flashscore.com.
        
        Note: Flashscore heavily uses WebSockets and JS rendering.
        We need to intercept XHR requests for the data.
        """
        if not league_id:
            league_id = "1"  # Premier League on flashscore
        
        url = f"https://www.flashscore.com/football/england/premier-league/results/"
        print(f"[*] Flashscore: {url}")
        
        await self._init_browser()
        page = await self.context.new_page()
        await self._stealth_page(page)
        
        # Intercept XHR for JSON data
        api_responses = []
        
        async def intercept_response(response):
            if "/x/feed/" in response.url or ".json" in response.url:
                try:
                    body = await response.text()
                    if len(body) > 100 and len(body) < 500000:
                        api_responses.append({
                            "url": response.url,
                            "body": body[:50000],  # Cap size
                        })
                except Exception:
                    pass
        
        page.on("response", intercept_response)
        
        try:
            if not await self._safe_get(page, url):
                return []
            
            await page.wait_for_timeout(5000)
            
            # Try to click "Show more matches" if present
            try:
                show_more = page.locator("a:has-text('Show more'), button:has-text('Show more')")
                if await show_more.count() > 0:
                    await show_more.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass
            
            html = await page.content()
            soup = self._parse_html(html)
            
            matches = []
            
            # Flashscore event rows
            for row in soup.select("div[class*='event__match']"):
                try:
                    home_el = row.select_one("div[class*='event__homeParticipant']")
                    away_el = row.select_one("div[class*='event__awayParticipant']")
                    score_el = row.select_one("div[class*='event__score']")
                    
                    home = home_el.get_text(strip=True) if home_el else ""
                    away = away_el.get_text(strip=True) if away_el else ""
                    score = score_el.get_text(strip=True) if score_el else ""
                    
                    # Time/status
                    time_el = row.select_one("div[class*='event__time']")
                    match_time = time_el.get_text(strip=True) if time_el else ""
                    
                    # Match ID from link
                    link = row.select_one("a[href*='/match/']")
                    match_id = ""
                    if link:
                        href = link.get("href", "")
                        match_id = href.split("/")[-2] if href.count("/") >= 3 else ""
                    
                    score_match = re.search(r'(\d+)\s*[-:]\s*(\d+)', score)
                    
                    match = {
                        "home_team": home,
                        "away_team": away,
                        "score": score,
                        "home_goals": int(score_match.group(1)) if score_match else None,
                        "away_goals": int(score_match.group(2)) if score_match else None,
                        "time": match_time,
                        "match_id": match_id,
                        "source": "flashscore",
                    }
                    matches.append(match)
                except Exception:
                    continue
            
            print(f"[+] Flashscore: {len(matches)} matches found")
            print(f"  [*] Also captured {len(api_responses)} API responses")
            
            result = {
                "matches": matches,
                "api_responses": api_responses[:5] if api_responses else [],
            }
            
            return result
            
        finally:
            await page.close()
    
    async def save_results(self, data: Any, name: str):
        """Save scraped data to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            self.config.output_dir,
            f"playwright_{name}_{timestamp}.json"
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            if isinstance(data, list):
                json.dump({
                    "source": "playwright-stealth",
                    "site": name,
                    "timestamp": timestamp,
                    "count": len(data),
                    "results": data,
                }, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"[+] Saved to {output_path}")
    
    async def close(self):
        """Clean up browser resources."""
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None
        if hasattr(self, 'playwright') and self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.close()


# ═══════════════════════════════════════════════════════════════════════
# MAIN — Test
# ═══════════════════════════════════════════════════════════════════════

async def test_scraper():
    """Test both Soccerway and Flashscore."""
    config = PlaywrightStealthConfig(headless=True)
    scraper = PlaywrightStealthScraper(config)
    
    try:
        # Test Soccerway
        print("=" * 70)
        print("[TEST 1] Soccerway — EPL matches")
        print("=" * 70)
        matches = await scraper.soccerway_matches("england/premier-league")
        print(f"  → {len(matches)} matches")
        for m in matches[:5]:
            print(f"    {m.get('date','?'):12s} | {m.get('home_team','?'):25s} vs {m.get('away_team','?'):25s} | {m.get('score','?')}")
        
        await scraper.save_results(matches, "soccerway_epl")
        
        # Test Flashscore
        print("\n" + "=" * 70)
        print("[TEST 2] Flashscore — EPL results")
        print("=" * 70)
        fs_data = await scraper.flashscore_matches()
        matches2 = fs_data.get("matches", [])
        print(f"  → {len(matches2)} matches")
        for m in matches2[:5]:
            print(f"    {m.get('home_team','?'):25s} vs {m.get('away_team','?'):25s} | {m.get('score','?')} | {m.get('time','?')}")
        
        await scraper.save_results(matches2, "flashscore_epl")
        
    finally:
        await scraper.close()
    
    print("\n[✓] Playwright Stealth test complete")


if __name__ == "__main__":
    asyncio.run(test_scraper())
