"""
upcoming_fixtures_oddsapi.py — Fetch upcoming matches via The Odds API
"""
import sys, os, sqlite3, json
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
import curl_cffi.requests as req
from datetime import datetime

API_KEY = "1aa4dd22f7ee80b8d03c654c064c4fce"

def fetch_upcoming(regions="eu,uk", markets="h2h"):
    """Get upcoming matches with odds from The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "unix",
    }
    
    # First get available sports
    sports_url = f"https://api.the-odds-api.com/v4/sports/?apiKey={API_KEY}"
    r = req.get(sports_url, timeout=15)
    if r.status_code == 200:
        sports = r.json()
        print(f"Available sports: {len(sports)}")
        football = [s for s in sports if 'football' in s.get('title', '').lower() or 'soccer' in s.get('group', '').lower()]
        print(f"Football leagues: {len(football)}")
        for f in football[:5]:
            print(f"  {f['key']}: {f['title']}")
    
    # Get upcoming events for each football sport
    all_events = []
    for f in football[:10]:  # limit to 10 leagues to save API calls
        url = f"https://api.the-odds-api.com/v4/sports/{f['key']}/odds/"
        try:
            r = req.get(url, params=params, timeout=15)
            if r.status_code == 200:
                events = r.json()
                # Track API usage
                remaining = r.headers.get('x-requests-remaining', '?')
                print(f"  {f['title']}: {len(events)} events (remaining: {remaining})")
                
                for ev in events:
                    all_events.append({
                        'id': ev.get('id'),
                        'home_team': ev.get('home_team'),
                        'away_team': ev.get('away_team'),
                        'commence_time': ev.get('commence_time'),
                        'league': f['title'],
                        'sport_key': f['key'],
                        'odds': ev.get('bookmakers', []),
                    })
            elif r.status_code == 401:
                print(f"  {f['title']}: 401 — API key error")
                break
            else:
                print(f"  {f['title']}: {r.status_code}")
        except Exception as e:
            print(f"  {f['title']}: ERROR — {e}")
    
    return all_events

def save_events(all_events):
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS odds_upcoming (
            event_id TEXT PRIMARY KEY,
            home_team TEXT, away_team TEXT,
            commence_time INTEGER, league TEXT,
            sport_key TEXT, odds_json TEXT,
            fetched_at TEXT
        )
    """)
    conn.execute("DELETE FROM odds_upcoming")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for ev in all_events:
        try:
            # Convert commence_time to date string
            ct = ev.get('commence_time', 0)
            from datetime import datetime as dt
            date_str = dt.fromtimestamp(ct).strftime("%Y-%m-%d") if isinstance(ct, (int, float)) else str(ct)[:10]
            
            conn.execute("""
                INSERT OR REPLACE INTO odds_upcoming
                (event_id, home_team, away_team, commence_time,
                 league, sport_key, odds_json, fetched_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (ev['id'], ev['home_team'], ev['away_team'],
                  int(ct) if isinstance(ct, (int, float)) else 0,
                  ev['league'], ev['sport_key'],
                  json.dumps(ev['odds']), now))
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    print(f"\nSaved {len(all_events)} upcoming events to DB")

if __name__ == '__main__':
    print(f"Fetching upcoming matches from The Odds API...")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    events = fetch_upcoming()
    if events:
        print(f"\nTotal upcoming: {len(events)}")
        save_events(events)
        
        # Group by league
        from collections import Counter
        leagues = Counter(e['league'] for e in events)
        print("\nBy league:")
        for l, c in leagues.most_common(10):
            print(f"  {l}: {c}")
        
        # Show first few
        print("\nFirst 5 matches:")
        for ev in events[:5]:
            from datetime import datetime as dt
            ct = ev.get('commence_time', '?')
            if isinstance(ct, (int, float)):
                ct = dt.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M")
            print(f"  {ev['home_team']} vs {ev['away_team']} ({ct}) — {ev['league']}")
    else:
        print("\nNo events found! Check API key.")
