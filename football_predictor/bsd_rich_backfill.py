"""
bsd_rich_backfill.py — Fetch rich BSD data (ref, coach, xG) for ALL matches via list endpoint.
~160 pages for 2025-2026, ~80 seconds total. Then process remaining years.
"""
import sys, os, time, json, requests

API_KEY = os.environ.get('BSD_API_KEY') or "f5651c96742c834b5e7e5e0760dcfb3b9bdc205c"
BASE = 'https://sports.bzzoiro.com/api'
HEADERS = {'Authorization': f'Token {API_KEY}'}

import sqlite3
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def fetch_page(url):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
        except:
            time.sleep(1)
    return None

def extract_rich_data(event):
    """Extract ref/coach/xG/weather from a BSD event dict."""
    ref = event.get('referee') or {}
    hc = event.get('home_coach') or {}
    ac = event.get('away_coach') or {}
    return {
        'odds_home': event.get('odds_home'),
        'odds_draw': event.get('odds_draw'),
        'odds_away': event.get('odds_away'),
        'referee_name': ref.get('name'),
        'ref_games': ref.get('career_games'),
        'ref_yellow': ref.get('career_yellow_cards'),
        'ref_red': ref.get('career_red_cards'),
        'home_coach_name': hc.get('name'),
        'home_coach_profile': hc.get('profile'),
        'home_coach_formation': hc.get('preferred_formation'),
        'away_coach_name': ac.get('name'),
        'away_coach_profile': ac.get('profile'),
        'away_coach_formation': ac.get('preferred_formation'),
        'weather_code': event.get('weather_code'),
        'wind_speed': event.get('wind_speed'),
        'temperature': event.get('temperature_c'),
        'pitch_condition': event.get('pitch_condition'),
        'actual_home_xg': event.get('actual_home_xg'),
        'actual_away_xg': event.get('actual_away_xg'),
    }

def backfill_rich_data():
    conn = sqlite3.connect(DB)
    
    # Add columns if needed
    for col in ['odds_home REAL', 'odds_draw REAL', 'odds_away REAL',
                'referee_name TEXT', 'ref_games INTEGER', 'ref_yellow INTEGER', 'ref_red INTEGER',
                'home_coach_name TEXT', 'home_coach_profile TEXT', 'home_coach_formation TEXT',
                'away_coach_name TEXT', 'away_coach_profile TEXT', 'away_coach_formation TEXT',
                'weather_code INTEGER', 'wind_speed REAL', 'temperature REAL', 'pitch_condition INTEGER',
                'actual_home_xg REAL', 'actual_away_xg REAL', 'venue_name_full TEXT']:
        try:
            conn.execute(f'ALTER TABLE sofa_historical_results ADD COLUMN {col}')
        except:
            pass
    conn.commit()
    
    # Get existing count to know what we need
    existing = conn.execute("SELECT COUNT(*) FROM sofa_historical_results WHERE referee_name IS NOT NULL").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM sofa_historical_results").fetchone()[0]
    print(f"Already have rich data: {existing}/{total}")
    
    years = list(range(2015, 2027))
    
    for year in years:
        offset = 0
        limit = 100
        fetched_year = 0
        
        while True:
            url = f"{BASE}/events/?limit={limit}&offset={offset}&date_from={year}-01-01&date_to={year}-12-31"
            data = fetch_page(url)
            if not data or not data.get('results'):
                break
            
            events = data['results']
            if not events:
                break
            
            for ev in events:
                eid = ev['id']
                rich = extract_rich_data(ev)
                
                # Skip events that aren't in our DB
                cur = conn.execute("SELECT 1 FROM sofa_historical_results WHERE id=?", (eid,))
                if not cur.fetchone():
                    continue
                
                conn.execute('''UPDATE sofa_historical_results SET
                    odds_home=?, odds_draw=?, odds_away=?,
                    referee_name=?, ref_games=?, ref_yellow=?, ref_red=?,
                    home_coach_name=?, home_coach_profile=?, home_coach_formation=?,
                    away_coach_name=?, away_coach_profile=?, away_coach_formation=?,
                    weather_code=?, wind_speed=?, temperature=?, pitch_condition=?,
                    actual_home_xg=?, actual_away_xg=?
                    WHERE id=?''', (
                    rich['odds_home'], rich['odds_draw'], rich['odds_away'],
                    rich['referee_name'], rich['ref_games'], rich['ref_yellow'], rich['ref_red'],
                    rich['home_coach_name'], rich['home_coach_profile'], rich['home_coach_formation'],
                    rich['away_coach_name'], rich['away_coach_profile'], rich['away_coach_formation'],
                    rich['weather_code'], rich['wind_speed'], rich['temperature'], rich['pitch_condition'],
                    rich['actual_home_xg'], rich['actual_away_xg'],
                    eid
                ))
                fetched_year += 1
            
            conn.commit()
            offset += limit
            
            if offset >= data.get('count', 0):
                break
            
            time.sleep(0.1)  # Polite delay
        
        print(f"  {year}: {fetched_year} matches updated")
    
    conn.close()
    print(f"\nDone! Total matches: {total}")

if __name__ == '__main__':
    backfill_rich_data()
