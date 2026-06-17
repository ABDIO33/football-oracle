"""
upcoming_fixtures_scraper.py — Fetch scheduled matches from SofaScore
Returns list of upcoming matches ready for prediction
"""
import sys, os, sqlite3, json, time, random
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
import curl_cffi.requests as req

HEADERS = {"x-requested-with": "XMLHttpRequest"}

def fetch_scheduled(days_ahead=7):
    """Fetch all scheduled football matches for next N days"""
    from datetime import datetime, timedelta
    all_matches = []
    
    today = datetime.now()
    
    for d in range(days_ahead + 1):
        date = (today + timedelta(days=d)).strftime("%Y-%m-%d")
        url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date}"
        
        try:
            r = req.get(url, impersonate="chrome120", headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                events = data.get('events', [])
                
                for ev in events:
                    status = ev.get('status', {})
                    if status.get('type') == 'notstarted':
                        tournament = ev.get('tournament', {})
                        home = ev.get('homeTeam', {})
                        away = ev.get('awayTeam', {})
                        venue = ev.get('venue', {}) or {}
                        
                        all_matches.append({
                            'sofa_id': ev['id'],
                            'home_team': home.get('name', '?'),
                            'away_team': away.get('name', '?'),
                            'date': date,
                            'kickoff_ts': ev.get('startTimestamp'),
                            'tournament': tournament.get('name', '?'),
                            'round': ev.get('roundInfo', {}).get('round', 0) if ev.get('roundInfo') else 0,
                            'venue': venue.get('name', ''),
                            'home_id': home.get('id'),
                            'away_id': away.get('id'),
                        })
                
                print(f"  {date}: {len(events)} events, {sum(1 for e in events if e.get('status',{}).get('type')=='notstarted')} not started")
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            print(f"  {date}: ERROR — {e}")
    
    return all_matches

def save_to_db(matches):
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upcoming_matches (
            sofa_id INTEGER PRIMARY KEY,
            home_team TEXT, away_team TEXT,
            date TEXT, kickoff_ts INTEGER,
            tournament TEXT, round INTEGER,
            venue TEXT, home_id INTEGER, away_id INTEGER,
            fetched_at TEXT
        )
    """)
    conn.execute("DELETE FROM upcoming_matches")
    
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for m in matches:
        conn.execute("""
            INSERT OR REPLACE INTO upcoming_matches
            (sofa_id, home_team, away_team, date, kickoff_ts,
             tournament, round, venue, home_id, away_id, fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (m['sofa_id'], m['home_team'], m['away_team'], m['date'],
              m['kickoff_ts'], m['tournament'], m['round'], m['venue'],
              m['home_id'], m['away_id'], now))
    
    conn.commit()
    conn.close()
    print(f"Saved {len(matches)} upcoming matches to DB")

def predict_all(matches):
    """Run model prediction on all upcoming matches"""
    from direct_predictor import predict_match
    results = []
    
    for i, m in enumerate(matches):
        try:
            pred = predict_match(m['home_team'], m['away_team'], m['date'])
            if pred:
                pred['sofa_id'] = m['sofa_id']
                pred['home_team'] = m['home_team']
                pred['away_team'] = m['away_team']
                pred['date'] = m['date']
                pred['tournament'] = m['tournament']
                results.append(pred)
        except Exception as e:
            pass
        
        if (i+1) % 10 == 0:
            print(f"  Predicted {i+1}/{len(matches)}")
    
    return results

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--predict', action='store_true', help='Also run predictions')
    args = parser.parse_args()
    
    print(f"Fetching matches for next {args.days} days...")
    matches = fetch_scheduled(days_ahead=args.days)
    print(f"\nTotal upcoming: {len(matches)}")
    
    if matches:
        save_to_db(matches)
        
        # Show summary by tournament
        from collections import Counter
        tourns = Counter(m['tournament'] for m in matches)
        print("\nBy tournament:")
        for t, c in tourns.most_common(10):
            print(f"  {t}: {c}")
        
        if args.predict:
            print(f"\nRunning predictions on {len(matches)} matches...")
            results = predict_all(matches)
            
            # Save predictions
            output_path = os.path.join(os.path.dirname(__file__), 'output', 'upcoming_predictions.json')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Saved {len(results)} predictions to {output_path}")
            
            # Show top confident picks
            sorted_results = sorted(results, key=lambda r: r.get('predicted_prob', 0), reverse=True)
            print("\nTop 10 most confident predictions:")
            for r in sorted_results[:10]:
                print(f"  {r['home_team']} vs {r['away_team']}: {r['predicted_score']} ({r['predicted_prob']:.1%})")
    else:
        print("No upcoming matches found!")
