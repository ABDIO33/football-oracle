#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█  AGENT 4 — SeleniumBase UC Transfermarkt Player Values Scraper           █
█  Uses seleniumbase Driver with uc=True for Cloudflare/bypass              █
█  Extracts market values, squad info, and player data from transfermarkt   █
██████████████████████████████████████████████████████████████████████████████
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, sys, json, re, time
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
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
class TransfermarktConfig:
    base_url: str = "https://www.transfermarkt.com"
    headless: bool = False
    timeout: int = 30
    max_retries: int = 3
    output_dir: str = "heist_output"


class TransfermarktScraper:
    """
    Transfermarkt scraper using SeleniumBase UC.
    
    Targets:
      - /{league}/startseite/wettbewerb/{league_id}/  → teams
      - /{team}/startseite/verein/{team_id}/  → squad
      - /{player}/profil/spieler/{player_id}/  → player details + market value
      - /{team}/leistungsdaten/verein/{team_id}/  → performance data
      - /marktwerte/  → market value rankings
    """
    
    # Known league IDs
    LEAGUES = {
        "epl": {"id": "GB1", "slug": "premier-league"},
        "laliga": {"id": "ES1", "slug": "la-liga"},
        "seriea": {"id": "IT1", "slug": "serie-a"},
        "bundesliga": {"id": "L1", "slug": "bundesliga"},
        "ligue1": {"id": "FR1", "slug": "ligue-1"},
        "eredivisie": {"id": "NL1", "slug": "eredivisie"},
        "primeira": {"id": "PO1", "slug": "liga-portugal"},
        "championship": {"id": "GB2", "slug": "championship"},
        "mls": {"id": "MLS1", "slug": "major-league-soccer"},
        "worldcup": {"id": "WCH", "slug": "world-cup"},
    }
    
    def __init__(self, config: Optional[TransfermarktConfig] = None):
        self.config = config or TransfermarktConfig()
        self.driver: Optional[Driver] = None
        self.results: List[Dict] = []
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def _get_driver(self) -> Driver:
        if self.driver is None:
            print("[*] Launching Transfermarkt UC Driver...")
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
        retries = retries or self.config.max_retries
        for attempt in range(retries):
            try:
                driver = self._get_driver()
                driver.get(url)
                time.sleep(2)
                
                page_text = driver.get_text("body")
                if "Just a moment" in page_text and len(page_text) < 500:
                    print(f"[!] Cloudflare, retry {attempt+1}/{retries}")
                    time.sleep(4 * (attempt + 1))
                    continue
                time.sleep(1)
                return True
            except Exception as e:
                print(f"[!] Error: {e}")
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
    
    def get_league_market_values(self, league_key: str) -> List[Dict]:
        """Get market values for all players in a league."""
        league = self.LEAGUES.get(league_key)
        if not league:
            print(f"[!] Unknown league: {league_key}")
            return []
        
        # Transfermarkt market value table URL
        url = f"{self.config.base_url}/{league['slug']}/marktwerte/wettbewerb/{league['id']}/plus/1"
        print(f"[*] Fetching market values: {url}")
        
        if not self._safe_get(url):
            return []
        
        players = self._parse_market_value_table()
        print(f"[+] Found {len(players)} players")
        return players
    
    def _parse_market_value_table(self) -> List[Dict]:
        """Parse the market value table on the current page."""
        players = []
        
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            # Find the main table
            table = soup.select_one(
                "table.items, table.wettbewerb, "
                "table[class*='marktwert'], div.table-wrapper table, "
                "table:has(th:contains('Market value'))"
            )
            
            if not table:
                # Try any large table
                tables = soup.select("table")
                for t in tables:
                    if "marktwert" in str(t).lower() or "market" in str(t).lower():
                        table = t
                        break
            
            if not table:
                # Try div-based layout
                player_cards = soup.select(
                    "div[class*='player'], div[class*='kader'], "
                    "tr:has(td[class*='pos'])"
                )
                for card in player_cards:
                    player = self._parse_player_card(card)
                    if player:
                        players.append(player)
                return players
            
            # Parse table
            rows = table.select("tr:has(td)")
            for row in rows:
                try:
                    player = self._parse_market_value_row(row)
                    if player and player.get("name"):
                        players.append(player)
                except Exception:
                    continue
            
        except Exception as e:
            print(f"[!] Error parsing market values: {e}")
        
        return players
    
    def _parse_market_value_row(self, row) -> Optional[Dict]:
        """Parse a single market value table row."""
        try:
            cells = row.select("td")
            if len(cells) < 4:
                return None
            
            # Name & profile link
            name_el = row.select_one(
                "td[class*='name'], td.hauptlink a, "
                "a[href*='/profil/spieler/']"
            )
            name = name_el.get_text(strip=True) if name_el else ""
            profile_url = ""
            if name_el and name_el.name == "a":
                profile_url = name_el.get("href", "")
            elif name_el:
                link = name_el.select_one("a")
                if link:
                    profile_url = link.get("href", "")
            
            if profile_url and not profile_url.startswith("http"):
                profile_url = f"{self.config.base_url}{profile_url}"
            
            # Position
            pos_el = row.select_one("td[class*='pos'], td:nth-child(1)")
            position = pos_el.get_text(strip=True) if pos_el else ""
            
            # Age
            age_el = row.select_one("td[class*='alter'], td:nth-child(3)")
            age = None
            if age_el:
                try:
                    age = int(age_el.get_text(strip=True))
                except ValueError:
                    pass
            
            # Market value
            value_el = row.select_one(
                "td[class*='marktwert'], td.rechts, "
                "td:has(span[class*='mw'])"
            )
            market_value = value_el.get_text(strip=True) if value_el else ""
            
            # Nationality
            nat_el = row.select_one("td[class*='flagge'], td:nth-child(2) img")
            nationality = nat_el.get("alt", "") if nat_el else ""
            if not nationality and nat_el:
                nationality = nat_el.get("title", "")
            
            # Club
            club_el = row.select_one("td[class*='verein'], td:has(img[class*='wappen'])")
            club = club_el.get_text(strip=True) if club_el else ""
            
            player = {
                "name": name,
                "position": position,
                "age": age,
                "nationality": nationality,
                "market_value": market_value,
                "market_value_parsed": self._parse_value(market_value),
                "club": club,
                "profile_url": profile_url,
            }
            
            return player
            
        except Exception as e:
            return None
    
    def _parse_player_card(self, card) -> Optional[Dict]:
        """Parse a player card (div-based layout)."""
        try:
            name_el = card.select_one(
                "[class*='name'] a, [class*='spieler'] a, "
                "a[href*='/profil/spieler/']"
            )
            if not name_el:
                return None
            
            name = name_el.get_text(strip=True)
            profile_url = name_el.get("href", "")
            if profile_url and not profile_url.startswith("http"):
                profile_url = f"{self.config.base_url}{profile_url}"
            
            # Market value
            value_el = card.select_one("[class*='marktwert'], [class*='mw']")
            value_text = value_el.get_text(strip=True) if value_el else ""
            
            # Position
            pos_el = card.select_one("[class*='position']")
            position = pos_el.get_text(strip=True) if pos_el else ""
            
            player = {
                "name": name,
                "position": position,
                "market_value": value_text,
                "market_value_parsed": self._parse_value(value_text),
                "profile_url": profile_url,
            }
            
            return player
            
        except Exception:
            return None
    
    def _parse_value(self, value_text: str) -> Optional[float]:
        """Parse market value string to float (in millions of euros)."""
        if not value_text:
            return None
        
        try:
            value_text = value_text.strip()
            # Format: €1.23m, €500k, €10.5m
            multiplier = 1_000_000  # Default to millions
            
            if "k" in value_text.lower():
                multiplier = 1_000
            elif "m" in value_text.lower():
                multiplier = 1_000_000
            elif "bn" in value_text.lower() or "b" in value_text.lower():
                multiplier = 1_000_000_000
            
            # Extract number
            num_match = re.search(r'[\d.,]+', value_text)
            if num_match:
                num_str = num_match.group().replace(",", ".")
                return float(num_str) * multiplier / 1_000_000  # Return in millions
            
        except (ValueError, TypeError):
            pass
        return None
    
    def get_squad(self, team_id: str, team_name: str = None) -> List[Dict]:
        """Get full squad with market values for a team."""
        team_slug = team_name.lower().replace(" ", "-") if team_name else "team"
        url = f"{self.config.base_url}/{team_slug}/startseite/verein/{team_id}/saison_id/2025"
        print(f"[*] Fetching squad: {url}")
        
        if not self._safe_get(url):
            return []
        
        players = []
        try:
            html = self.driver.get_page_source()
            soup = BeautifulSoup(html, "lxml" if LXML_OK else "html.parser")
            
            # Find squad table
            table = soup.select_one(
                "table:has(tr:contains('Market value')), "
                "table.items, div[class*='kader'] table"
            )
            
            if not table:
                # Try finding player rows directly
                player_rows = soup.select(
                    "tr:has(td[class*='pos'])" 
                )
                for row in player_rows:
                    player = self._parse_market_value_row(row)
                    if player:
                        players.append(player)
                return players
            
            rows = table.select("tr:has(td)")
            for row in rows:
                player = self._parse_market_value_row(row)
                if player:
                    players.append(player)
            
        except Exception as e:
            print(f"[!] Error parsing squad: {e}")
        
        print(f"[+] Found {len(players)} players in squad")
        return players
    
    def get_all_leagues(self, max_players_per_league: int = 200) -> Dict[str, List[Dict]]:
        """Scrape market values for all known leagues."""
        all_data = {}
        
        for league_key in self.LEAGUES:
            print(f"\n{'='*60}")
            print(f"[*] Scraping {league_key}...")
            print(f"{'='*60}")
            
            players = self.get_league_market_values(league_key)
            if max_players_per_league > 0:
                players = players[:max_players_per_league]
            
            all_data[league_key] = players
            
            # Save per league
            self._save_league_data(league_key, players)
            
            time.sleep(2)
        
        # Save all
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            self.config.output_dir,
            f"transfermarkt_all_leagues_{timestamp}.json"
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n[+] All data saved to {output_path}")
        
        return all_data
    
    def _save_league_data(self, league_key: str, players: List[Dict]):
        """Save league data to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            self.config.output_dir,
            f"transfermarkt_{league_key}_{timestamp}.json"
        )
        
        # Calculate league-level stats
        values = [p.get("market_value_parsed") for p in players if p.get("market_value_parsed") is not None]
        
        data = {
            "source": "transfermarkt.com",
            "scraper": "SeleniumBase UC v4.49",
            "league": league_key,
            "timestamp": timestamp,
            "player_count": len(players),
            "stats": {
                "total_market_value_m": sum(values) if values else 0,
                "avg_market_value_m": round(sum(values) / len(values), 2) if values else 0,
                "max_market_value_m": max(values) if values else 0,
            },
            "players": players,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"[+] Saved {len(players)} players to {output_path}")
    
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
    config = TransfermarktConfig(headless=True)
    scraper = TransfermarktScraper(config)
    
    try:
        # Test EPL market values
        print("=" * 70)
        print("[TEST] Scraping EPL market values (top 10)")
        print("=" * 70)
        players = scraper.get_league_market_values("epl")
        players = players[:10]
        print(f"  → {len(players)} players")
        for p in players:
            print(f"    {p.get('name', '?'):30s} | {p.get('position', '?'):5s} | "
                  f"{p.get('age', '?'):3} | {p.get('market_value', '?'):15s} "
                  f"| {p.get('nationality', '?'):15s}")
        
        # Values analysis
        values = [p.get("market_value_parsed") for p in players if p.get("market_value_parsed")]
        if values:
            print(f"\n  Market value stats:")
            print(f"    Total: €{sum(values):.1f}M")
            print(f"    Average: €{sum(values)/len(values):.1f}M")
            print(f"    Max: €{max(values):.1f}M")
        
    finally:
        scraper.close()
    
    print("\n[✓] Transfermarkt test complete")


if __name__ == "__main__":
    test_scraper()
