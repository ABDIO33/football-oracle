#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█  AGENT 4 — SeleniumBase UC BetExplorer Historical Odds Scraper           █
█  Uses seleniumbase Driver with uc=True to bypass Cloudflare/UAM           █
█  Extracts 1X2 odds from betexplorer.com for given leagues/seasons         █
██████████████████████████████████████████████████████████████████████████████
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, sys, json, re, time, csv, io
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# IMPORTS WITH FALLBACKS
# ═══════════════════════════════════════════════════════════════════════

try:
    from seleniumbase import Driver
    SELENIUMBASE_OK = True
except ImportError as e:
    SELENIUMBASE_OK = False
    print(f"[!] seleniumbase not available: {e}")

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


# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BetExplorerConfig:
    base_url: str = "https://www.betexplorer.com"
    headless: bool = False  # Set True for production, False for debug
    timeout: int = 30
    max_retries: int = 3
    output_dir: str = "heist_output"
    
    # Available leagues shortcuts
    leagues: Dict[str, str] = None
    
    def __post_init__(self):
        if self.leagues is None:
            self.leagues = {
                "epl": "england/premier-league",
                "laliga": "spain/la-liga",
                "seriea": "italy/serie-a",
                "bundesliga": "germany/bundesliga",
                "ligue1": "france/ligue-1",
                "eredivisie": "netherlands/eredivisie",
                "primeira": "portugal/primeira-liga",
                "championship": "england/championship",
                "mls": "usa/mls",
                "worldcup": "international/world-cup",
                "euro": "international/european-championship",
                "copa": "international/copa-america",
            }


# ═══════════════════════════════════════════════════════════════════════
# CORE SCRAPER
# ═══════════════════════════════════════════════════════════════════════

class BetExplorerScraper:
    """
    BetExplorer historical odds scraper using SeleniumBase UC (undetected Chromium).
    
    Targets:
      - /soccer/{league}/ → list of seasons
      - /soccer/{league}/{season}/results/ → match results with odds
      - /soccer/{league}/{season}/{match}/ → detailed match odds
    
    Handles:
      - Cloudflare UAM protection via uc=True
      - Dynamic content loading
      - Rate limiting and retry logic
    """
    
    def __init__(self, config: Optional[BetExplorerConfig] = None):
        self.config = config or BetExplorerConfig()
        self.driver: Optional[Driver] = None
        self.results: List[Dict] = []
        self.session_stats = {
            "requests": 0,
            "success": 0,
            "failed": 0,
            "retries": 0,
            "start_time": datetime.now().isoformat(),
        }
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def _get_driver(self) -> Driver:
        """Create or reuse a SeleniumBase UC Driver."""
        if self.driver is None:
            print("[*] Launching SeleniumBase UC Driver (undetected Chromium)...")
            self.driver = Driver(
                uc=True,                    # Undetected Chrome mode
                headless=self.config.headless,
                browser="chrome",
                incognito=True,
                disable_csp=True,
                agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                user_data_dir=None,
                log_cdp=True,
            )
            self.driver.set_page_load_timeout(self.config.timeout)
            print("[+] Driver launched successfully")
        return self.driver
    
    def _safe_get(self, url: str, retries: int = None) -> bool:
        """Navigate to URL with retry logic and Cloudflare wait."""
        retries = retries or self.config.max_retries
        self.session_stats["requests"] += 1
        
        for attempt in range(retries):
            try:
                driver = self._get_driver()
                driver.get(url)
                time.sleep(2)
                
                # Wait for Cloudflare challenge to pass (if present)
                try:
                    driver.wait_for_element_not_present(
                        "div#challenge-running", timeout=10
                    )
                except Exception:
                    pass
                
                # Check if we got a real page (not a challenge)
                page_text = driver.get_text("body")
                if "Just a moment" in page_text and len(page_text) < 500:
                    print(f"[!] Cloudflare challenge detected, retrying... ({attempt+1}/{retries})")
                    time.sleep(3 * (attempt + 1))
                    self.session_stats["retries"] += 1
                    continue
                
                # Additional wait for dynamic content
                time.sleep(1)
                self.session_stats["success"] += 1
                return True
                
            except Exception as e:
                print(f"[!] Error loading {url}: {e}")
                self.session_stats["retries"] += 1
                # Refresh driver if it's stuck
                if attempt < retries - 1:
                    self._recreate_driver()
        
        self.session_stats["failed"] += 1
        return False
    
    def _recreate_driver(self):
        """Kill and recreate the driver to reset state."""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
        time.sleep(2)
    
    def get_seasons(self, league_slug: str) -> List[Dict]:
        """Get list of available seasons for a league.
        BetExplorer uses /football/ paths and a season dropdown.
        """
        # Normalize to BetExplorer's /football/ URL format
        if league_slug.startswith("soccer/"):
            league_slug = league_slug.replace("soccer/", "football/", 1)
        elif not league_slug.startswith("football/"):
            league_slug = f"football/{league_slug}"
        
        url = f"{self.config.base_url}/{league_slug}/"
        print(f"[*] Fetching seasons from: {url}")
        
        if not self._safe_get(url):
            return []
        
        # Parse the seasons dropdown/table
        seasons = []
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            # Method 1: Check select/dropdown for seasons (primary method for BetExplorer)
            for select in soup.select('select'):
                season_count = 0
                for opt in select.select("option"):
                    val = opt.get("value", "")
                    txt = opt.get_text(strip=True)
                    # BetExplorer season values: /football/england/premier-league-2025-2026/
                    if val and re.search(r'\d{4}', val) and re.search(r'\d{4}', txt):
                        season_name = txt
                        season_url = f"{self.config.base_url}{val}" if val.startswith("/") else val
                        seasons.append({
                            "name": season_name,
                            "url": season_url,
                            "value": val,
                        })
                        season_count += 1
                if season_count > 3:
                    break  # Found the season dropdown
            
            # Method 2: Find season links (fallback)
            if not seasons:
                for a in soup.select('a[href*="/football/"]'):
                    href = a.get("href", "")
                    text = a.get_text(strip=True)
                    if href.count("/") >= 4 and re.search(r'\d{4}', text):
                        seasons.append({
                            "name": text,
                            "url": f"{self.config.base_url}{href}" if href.startswith("/") else href,
                            "href": href,
                        })
            
            print(f"[+] Found {len(seasons)} seasons")
        except Exception as e:
            print(f"[!] Error parsing seasons: {e}")
        
        return seasons
    
    def get_matches_with_odds(self, league_slug: str, season_val: str) -> List[Dict]:
        """
        Get all matches with odds for a given league+season.
        
        betexplorer.com pattern:
          /football/{league}-{season}/results/
        """
        # If season_val is already a path (e.g., /football/england/premier-league-2025-2026/)
        if season_val.startswith("/"):
            base_path = season_val.rstrip("/")
            url = f"{self.config.base_url}{base_path}/results/"
            alt_urls = [
                f"{self.config.base_url}{base_path}/",
                f"{self.config.base_url}{base_path}/?type=results",
            ]
        else:
            # Normalize league slug to football format
            if league_slug.startswith("soccer/"):
                league_slug = league_slug.replace("soccer/", "football/", 1)
            elif not league_slug.startswith("football/"):
                league_slug = f"football/{league_slug}"
            season_path = season_val.replace("/", "-").replace(" ", "-")
            url = f"{self.config.base_url}/{league_slug}-{season_path}/results/"
            alt_urls = [
                f"{self.config.base_url}/{league_slug}-{season_path}/",
                f"{self.config.base_url}/{league_slug}-{season_path}/?type=results",
            ]
        
        all_matches = []
        
        for target_url in [url] + alt_urls:
            print(f"[*] Fetching matches from: {target_url}")
            
            if not self._safe_get(target_url):
                continue
            
            # Check pagination
            page = 1
            while True:
                matches = self._parse_matches_page()
                all_matches.extend(matches)
                print(f"[+] Page {page}: {len(matches)} matches (total: {len(all_matches)})")
                
                # Try next page
                next_url = self._get_next_page_url()
                if not next_url:
                    break
                
                if not self._safe_get(next_url):
                    break
                page += 1
                time.sleep(1)
            
            if all_matches:
                break  # Got matches, no need for alt URLs
        
        return all_matches
    
    def _parse_matches_page(self) -> List[Dict]:
        """Parse the current page for match rows with odds from BetExplorer."""
        matches = []
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            # BetExplorer uses table with class 'table-main'
            table = soup.select_one("table.table-main")
            if not table:
                # Try any table with match odds structure
                table = soup.select_one("table:has(td.h-text-left):has(td:has(span.odds))")
            
            if not table:
                # Try finding rows directly
                rows = soup.select("tr:has(td.h-text-left):has(a.in-match)")
            else:
                rows = table.select("tr:has(td.h-text-left):has(a.in-match)")
            
            current_date = ""
            current_round = ""
            
            # First pass: collect all rows including date headers
            all_rows_in_table = table.select("tr") if table else rows
            
            for row in (table.select("tr") if table else rows):
                row_text = row.get_text(" ", strip=True)
                
                # Check if this is a date/round header
                if not row.select("td.h-text-left"):
                    # Could be a date header
                    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', row_text)
                    round_match = re.search(r'(\d+\.\s*Round)', row_text)
                    if date_match:
                        current_date = date_match.group(1)
                    if round_match:
                        current_round = round_match.group(1)
                    continue
                
                try:
                    match = self._parse_match_row(row, current_date, current_round)
                    if match and match.get("home_team") and match.get("away_team"):
                        matches.append(match)
                except Exception:
                    continue
            
        except Exception as e:
            print(f"[!] Error parsing matches page: {e}")
        
        return matches
    
    def _parse_match_row(self, row, current_date="", current_round="") -> Optional[Dict]:
        """Parse a single match row from BetExplorer table."""
        try:
            cells = row.select("td")
            # BetExplorer structure: [teams, score, odds_1, odds_X, odds_2, date]
            if len(cells) < 6:
                return None
            
            # Team names from the <a class="in-match"> element in cell[0]
            match_link = cells[0].select_one("a.in-match")
            if not match_link:
                return None
            
            # Team names are in <span> elements inside the link
            spans = match_link.select("span")
            home_team = spans[0].get_text(strip=True) if len(spans) > 0 else ""
            away_team = spans[-1].get_text(strip=True) if len(spans) > 1 else ""
            
            # Match URL
            href = match_link.get("href", "")
            match_url = f"{self.config.base_url}{href}" if href.startswith("/") else href
            
            # Score: cell[1] has h-text-center class
            score_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            
            # Date: cell[5] has h-text-right h-text-no-wrap
            date_text = cells[5].get_text(strip=True) if len(cells) > 5 else current_date
            
            # Odds: cells[2]=home, cells[3]=draw, cells[4]=away
            odds = {"1": None, "X": None, "2": None}
            for i, idx in enumerate([2, 3, 4]):
                if idx < len(cells):
                    cell_text = cells[idx].get_text(strip=True)
                    if cell_text and cell_text != "-":
                        try:
                            key = ["1", "X", "2"][i]
                            odds[key] = float(cell_text.replace(",", "."))
                        except ValueError:
                            pass
            
            # Score parsing
            score_parts = re.findall(r'(\d+)', score_text)
            home_goals = int(score_parts[0]) if len(score_parts) > 0 else None
            away_goals = int(score_parts[1]) if len(score_parts) > 1 else None
            
            match = {
                "date": date_text,
                "round": current_round,
                "home_team": home_team,
                "away_team": away_team,
                "score": score_text,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "odds_1": odds["1"],
                "odds_X": odds["X"],
                "odds_2": odds["2"],
                "url": match_url,
            }
            
            return match
            
        except Exception as e:
            return None
    
    def _get_next_page_url(self) -> Optional[str]:
        """
        Get the URL for the next page of results.
        BetExplorer loads all matches on one page - no pagination needed.
        Returns None to stop pagination attempts.
        """
        return None
    
    def get_detailed_match_odds(self, match_url: str) -> Optional[Dict]:
        """Get detailed odds for a single match (over/under, both to score, etc.)."""
        print(f"  [*] Fetching detailed odds: {match_url}")
        
        if not self._safe_get(match_url):
            return None
        
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            details = {}
            
            # Find all odds tables
            for table in soup.select("table:has(tr)"):
                header = table.select_one("th, thead tr th")
                if not header:
                    continue
                header_text = header.get_text(strip=True).lower()
                
                # 1X2 odds
                if "1" in header_text and ("x" in header_text or "2" in header_text):
                    for row in table.select("tr:has(td)"):
                        cells = row.select("td")
                        if len(cells) >= 4:
                            bookie = cells[0].get_text(strip=True)
                            odds = []
                            for c in cells[1:4]:
                                t = c.get_text(strip=True)
                                try:
                                    odds.append(float(t) if t != "-" else None)
                                except ValueError:
                                    odds.append(None)
                            details[f"odds_{bookie}"] = {
                                "1": odds[0] if len(odds) > 0 else None,
                                "X": odds[1] if len(odds) > 1 else None,
                                "2": odds[2] if len(odds) > 2 else None,
                            }
                
                # Over/Under
                elif "over" in header_text:
                    ou = {}
                    for row in table.select("tr:has(td)"):
                        cells = row.select("td")
                        if len(cells) >= 3:
                            line = cells[0].get_text(strip=True)
                            over_t = cells[1].get_text(strip=True)
                            under_t = cells[2].get_text(strip=True)
                            try:
                                ou[line] = {
                                    "over": float(over_t) if over_t != "-" else None,
                                    "under": float(under_t) if under_t != "-" else None,
                                }
                            except ValueError:
                                pass
                    if ou:
                        details["over_under"] = ou
                
                # Both teams to score
                elif "both" in header_text or "bts" in header_text:
                    bts = {}
                    for row in table.select("tr:has(td)"):
                        cells = row.select("td")
                        if len(cells) >= 3:
                            bookie = cells[0].get_text(strip=True)
                            try:
                                bts[bookie] = {
                                    "yes": float(cells[1].get_text(strip=True)),
                                    "no": float(cells[2].get_text(strip=True)),
                                }
                            except ValueError:
                                pass
                    if bts:
                        details["bts"] = bts
            
            return details if details else None
            
        except Exception as e:
            print(f"  [!] Error parsing detailed odds: {e}")
            return None
    
    def scrape_league(self, league_slug: str, season: str = None, limit: int = 0) -> List[Dict]:
        """Scrape all historical odds for a league, optionally limiting matches."""
        # Get seasons if not specified
        if not season:
            seasons = self.get_seasons(league_slug)
            if not seasons:
                print(f"[!] No seasons found for {league_slug}")
                return []
            # Use the latest complete season (value is the path, name is display)
            latest = seasons[-1]
            season = latest.get("value", latest["name"])
            print(f"[*] Auto-selected season: {latest['name']} (value: {season})")
        
        # Get matches
        matches = self.get_matches_with_odds(league_slug, season)
        
        if limit > 0:
            matches = matches[:limit]
        
        print(f"[+] Total matches collected: {len(matches)}")
        
        # Save results
        league_name = league_slug.replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            self.config.output_dir,
            f"betexplorer_{league_name}_{season.replace('/', '_')}_{timestamp}.json"
        )
        
        result = {
            "source": "betexplorer.com",
            "scraper": "SeleniumBase UC v4.49",
            "league": league_slug,
            "season": season,
            "timestamp": timestamp,
            "match_count": len(matches),
            "session_stats": self.session_stats,
            "matches": matches,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"[+] Saved {len(matches)} matches to {output_path}")
        
        return matches
    
    def close(self):
        """Clean up driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# ═══════════════════════════════════════════════════════════════════════
# MAIN — Test & Demo
# ═══════════════════════════════════════════════════════════════════════

def test_scraper():
    """Quick test of BetExplorer scraper."""
    config = BetExplorerConfig(headless=True)
    scraper = BetExplorerScraper(config)
    
    try:
        # Test 1: Get seasons for EPL
        print("=" * 70)
        print("[TEST 1] Getting seasons for English Premier League")
        print("=" * 70)
        seasons = scraper.get_seasons("england/premier-league")
        print(f"  → Seasons found: {len(seasons)}")
        for s in seasons[:5]:
            print(f"    - {s['name']}: {s['url']}")
        
        # Test 2: Get limited matches
        print("\n" + "=" * 70)
        print("[TEST 2] Getting recent EPL matches")
        print("=" * 70)
        matches = scraper.scrape_league(
            "england/premier-league",
            season=None,  # Auto-select latest
            limit=10
        )
        print(f"  → Matches collected: {len(matches)}")
        for m in matches[:5]:
            print(f"    {m.get('date', '?'):12s} | {m.get('home_team','?'):25s} vs {m.get('away_team','?'):25s} | "
                  f"{m.get('score','?')} | "
                  f"{m.get('odds_1','-'):>5s} {m.get('odds_X','-'):>5s} {m.get('odds_2','-'):>5s}")
        
        # Test 3: Another league
        print("\n" + "=" * 70)
        print("[TEST 3] Getting La Liga matches")
        print("=" * 70)
        matches2 = scraper.scrape_league(
            "spain/la-liga",
            season=None,
            limit=5
        )
        print(f"  → Matches collected: {len(matches2)}")
        
    finally:
        scraper.close()
    
    print("\n[✓] BetExplorer scraper test complete")


if __name__ == "__main__":
    test_scraper()
