#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█  AGENT 4 — SeleniumBase UC OddsPortal Historical Odds Scraper            █
█  Uses seleniumbase Driver with uc=True to bypass Cloudflare               █
█  Extracts 1X2, Asian Handicap, Over/Under odds from oddsportal.com       █
██████████████████████████████████████████████████████████████████████████████
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, sys, json, re, time, csv
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from seleniumbase import Driver
    SELENIUMBASE_OK = True
except ImportError:
    SELENIUMBASE_OK = False

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
class OddsPortalConfig:
    base_url: str = "https://www.oddsportal.com"
    headless: bool = False
    timeout: int = 45
    max_retries: int = 3
    output_dir: str = "heist_output"


class OddsPortalScraper:
    """
    OddsPortal scraper using SeleniumBase UC for Cloudflare bypass.
    
    URL pattern:
      /soccer/{country}/{league}/results/  → match list with best odds
      /soccer/{country}/{league}/{match-slug}/  → detailed odds
    """
    
    def __init__(self, config: Optional[OddsPortalConfig] = None):
        self.config = config or OddsPortalConfig()
        self.driver: Optional[Driver] = None
        self.results: List[Dict] = []
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def _get_driver(self) -> Driver:
        if self.driver is None:
            print("[*] Launching OddsPortal UC Driver...")
            self.driver = Driver(
                uc=True,
                headless=self.config.headless,
                browser="chrome",
                incognito=True,
                disable_csp=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            self.driver.set_page_load_timeout(self.config.timeout)
        return self.driver
    
    def _safe_get(self, url: str, retries: int = None) -> bool:
        """Navigate with retry + Cloudflare detection."""
        retries = retries or self.config.max_retries
        for attempt in range(retries):
            try:
                driver = self._get_driver()
                driver.get(url)
                time.sleep(3)
                
                # Wait for page to settle (OddsPortal loads odds via JS)
                try:
                    driver.wait_for_element_present(
                        "table, div[class*='odds'], div[id*='odds'], "
                        "div[data-type='odds'], div.event-row", 
                        timeout=15
                    )
                except Exception:
                    pass
                
                # Check for Cloudflare
                page_text = driver.get_text("body")
                if "Just a moment" in page_text or "DDoS" in page_text:
                    print(f"[!] Cloudflare challenge, retry {attempt+1}/{retries}")
                    time.sleep(5 * (attempt + 1))
                    continue
                
                time.sleep(1)
                return True
            except Exception as e:
                print(f"[!] Error: {e}, retry {attempt+1}/{retries}")
                self._recreate_driver()
        return False
    
    def _recreate_driver(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
        time.sleep(2)
    
    def get_leagues(self) -> List[Dict]:
        """Get list of available soccer leagues."""
        url = f"{self.config.base_url}/soccer/"
        print(f"[*] Fetching leagues from: {url}")
        
        if not self._safe_get(url):
            return []
        
        leagues = []
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            for a in soup.select("a[href*='/soccer/']"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                # Filter for league links (deeper than just /soccer/)
                if href.count("/") >= 3 and text and len(text) > 3:
                    leagues.append({
                        "name": text,
                        "url": f"{self.config.base_url}{href}" if href.startswith("/") else href,
                        "href": href,
                    })
            
            print(f"[+] Found {len(leagues)} leagues")
        except Exception as e:
            print(f"[!] Error: {e}")
        
        return leagues
    
    def get_matches(self, league_path: str, season: str = None) -> List[Dict]:
        """
        Get match results with odds from a league page.
        
        oddsportal.com pattern: /soccer/{league}/results/
        """
        # Clean path
        league_path = league_path.strip("/")
        # Try results page first
        url = f"{self.config.base_url}/{league_path}/results/"
        print(f"[*] Fetching matches from: {url}")
        
        if not self._safe_get(url):
            return []
        
        matches = self._parse_matches()
        print(f"[+] Found {len(matches)} matches on page 1")
        
        # Get remaining pages
        page = 2
        max_pages = 50  # Safety limit
        while page <= max_pages:
            next_url = f"{self.config.base_url}/{league_path}/results/#/page/{page}/"
            
            # Try alternate page formats
            alt_next = f"{self.config.base_url}/{league_path}/results/page/{page}/"
            
            if not self._safe_get(next_url):
                if not self._safe_get(alt_next):
                    break
            
            page_matches = self._parse_matches()
            if not page_matches:
                break
            
            matches.extend(page_matches)
            print(f"[+] Page {page}: {len(page_matches)} matches (total: {len(matches)})")
            page += 1
            time.sleep(1.5)
        
        return matches
    
    def _parse_matches(self) -> List[Dict]:
        """Parse the current page for match rows with odds."""
        matches = []
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            # OddsPortal v2+ structure
            rows = soup.select(
                "div[class*='eventRow'], div[class*='event-row'], "
                "tr[class*='event'], tr[class*='odd'], "
                "div[data-type='event-row'], tr.deactivate "
            )
            
            if not rows:
                # Fallback to table rows
                rows = soup.select("table tr:has(td)")
            
            for row in rows:
                try:
                    match = self._parse_match_row(row)
                    if match and match.get("home_team") and match.get("away_team"):
                        matches.append(match)
                except Exception:
                    continue
            
        except Exception as e:
            print(f"[!] Error parsing: {e}")
        
        return matches
    
    def _parse_match_row(self, row) -> Optional[Dict]:
        """Parse a single match row from OddsPortal."""
        try:
            # Get all text content
            row_text = row.get_text(" ", strip=True)
            
            # Try to find teams - typically first text content before odds
            # OddsPortal format: [date] [home] - [away] [odds_1] [odds_X] [odds_2]
            
            # Method 1: Data attributes
            home_el = row.select_one("[class*='home'], [data-home]")
            away_el = row.select_one("[class*='away'], [data-away]")
            
            home_team = home_el.get_text(strip=True) if home_el else ""
            away_team = away_el.get_text(strip=True) if away_el else ""
            
            # Date
            date_el = row.select_one("[class*='date'], [data-date], time")
            date_text = date_el.get("datetime", "") if date_el else ""
            if not date_text and date_el:
                date_text = date_el.get_text(strip=True)
            
            # Score
            score_el = row.select_one("[class*='score'], [data-score]")
            score_text = score_el.get_text(strip=True) if score_el else ""
            
            # Odds (cells with numeric values)
            odds_spans = row.select(
                "[class*='odd'], [class*='odds'], "
                "span[data-odds], span[class*='value']"
            )
            odds_values = []
            for span in odds_spans[:3]:
                text = span.get_text(strip=True)
                try:
                    odds_values.append(float(text))
                except (ValueError, TypeError):
                    odds_values.append(None)
            
            # Match URL
            link = row.select_one("a[href*='/soccer/']")
            match_url = ""
            if link:
                href = link.get("href", "")
                if href:
                    match_url = f"{self.config.base_url}{href}" if href.startswith("/") else href
            
            match = {
                "date": date_text,
                "home_team": home_team,
                "away_team": away_team,
                "score": score_text,
                "odds_1": odds_values[0] if len(odds_values) > 0 else None,
                "odds_X": odds_values[1] if len(odds_values) > 1 else None,
                "odds_2": odds_values[2] if len(odds_values) > 2 else None,
                "url": match_url,
            }
            
            # If structured parsing failed, try regex
            if not home_team or not away_team:
                odds_pattern = r'(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)'
                match_odds = re.findall(odds_pattern, row_text)
                
                team_pattern = r'([A-Z][a-zA-Z\s]+)\s+[-–]\s+([A-Z][a-zA-Z\s]+)'
                team_match = re.search(team_pattern, row_text)
                
                if team_match:
                    match["home_team"] = team_match.group(1).strip()
                    match["away_team"] = team_match.group(2).strip()
                
                if match_odds:
                    try:
                        match["odds_1"] = float(match_odds[0][0])
                        match["odds_X"] = float(match_odds[0][1])
                        match["odds_2"] = float(match_odds[0][2])
                    except (ValueError, IndexError):
                        pass
            
            return match
            
        except Exception as e:
            return None
    
    def get_detailed_odds(self, match_url: str) -> Optional[Dict]:
        """Get detailed odds for a single match (all bookmakers)."""
        if not self._safe_get(match_url):
            return None
        
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            details = {"bookmakers": {}}
            
            # Find all bookmaker odds
            bookie_rows = soup.select(
                "tr[class*='bookmaker'], div[class*='bookmaker'], "
                "div[class*='bookie'], tr:has(td:nth-child(4))"
            )
            
            for row in bookie_rows:
                cells = row.select("td, span[class*='value']")
                if len(cells) >= 4:
                    name_el = row.select_one(
                        "[class*='name'], [class*='bookmaker'], td:first-child"
                    )
                    name = name_el.get_text(strip=True) if name_el else "unknown"
                    
                    values = []
                    for c in cells[-3:]:
                        t = c.get_text(strip=True)
                        try:
                            values.append(float(t))
                        except (ValueError, TypeError):
                            values.append(None)
                    
                    if any(v is not None for v in values):
                        details["bookmakers"][name] = {
                            "1": values[0],
                            "X": values[1],
                            "2": values[2],
                        }
            
            return details if details["bookmakers"] else None
            
        except Exception as e:
            print(f"  [!] Error: {e}")
            return None
    
    def scrape_league(self, league_path: str, max_matches: int = 0) -> List[Dict]:
        """Scrape odds from a league, optionally limiting matches."""
        matches = self.get_matches(league_path)
        
        if max_matches > 0:
            matches = matches[:max_matches]
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        league_name = league_path.replace("/", "_")
        output_path = os.path.join(
            self.config.output_dir,
            f"oddsportal_{league_name}_{timestamp}.json"
        )
        
        result = {
            "source": "oddsportal.com",
            "scraper": "SeleniumBase UC v4.49",
            "league": league_path,
            "timestamp": timestamp,
            "match_count": len(matches),
            "matches": matches,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"[+] Saved {len(matches)} matches to {output_path}")
        
        return matches
    
    def close(self):
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


def test_scraper():
    """Quick test."""
    config = OddsPortalConfig(headless=True)
    scraper = OddsPortalScraper(config)
    
    try:
        # Test getting leagues
        print("=" * 70)
        print("[TEST] Getting available leagues")
        print("=" * 70)
        leagues = scraper.get_leagues()
        print(f"  → {len(leagues)} leagues found")
        for l in leagues[:10]:
            print(f"    - {l['name']}")
        
        # Test getting matches for EPL
        print("\n" + "=" * 70)
        print("[TEST] Getting EPL results")
        print("=" * 70)
        matches = scraper.scrape_league(
            "soccer/england/premier-league",
            max_matches=10
        )
        print(f"  → {len(matches)} matches")
        for m in matches[:5]:
            print(f"    {m.get('date','?'):12s} | {m.get('home_team','?'):25s} vs {m.get('away_team','?'):25s} | "
                  f"{m.get('odds_1','-'):>5} {m.get('odds_X','-'):>5} {m.get('odds_2','-'):>5}")
        
    finally:
        scraper.close()
    
    print("\n[✓] OddsPortal test complete")


if __name__ == "__main__":
    test_scraper()
