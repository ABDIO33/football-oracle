"""
Value Betting Pipeline v3 -- BSD API powered.
1. Fetch upcoming events with odds from BSD API (unlimited)
2. Run 89-feature model prediction for each
3. Compare model probs vs 16-bookmaker market -> find value bets
4. Output report + save
"""
import os, sys, json, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except:
    pass

import bsd_api
import direct_predictor as dp
from odds_api_scraper import find_value_bets

MIN_EDGE_PCT = 5.0
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_upcoming_events():
    """Fetch upcoming events with odds from BSD API."""
    import requests
    API_KEY = os.environ.get('BSD_API_KEY') or "f5651c96742c834b5e7e5e0760dcfb3b9bdc205c"
    BASE = 'https://sports.bzzoiro.com/api'
    HEADERS = {'Authorization': f'Token {API_KEY}'}

    today = datetime.now().strftime('%Y-%m-%d')
    events = []
    for offset in range(0, 500, 100):
        url = f"{BASE}/events/?limit=100&offset={offset}&date_from={today}&date_to={today}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            data = r.json()
            batch = data.get('results', [])
            events.extend(batch)
            if not data.get('next'):
                break
        except:
            break
        time.sleep(0.1)
    
    # Filter to events WITH odds
    with_odds = [e for e in events if e.get('odds_home') and e.get('odds_away')]
    print(f"Upcoming events: {len(events)}, with odds: {len(with_odds)}")
    return with_odds

def run():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"{'='*60}")
    print(f"VALUE BETTING PIPELINE v3 (BSD) -- {today}")
    print(f"{'='*60}")

    # Step 1: Fetch upcoming events with odds
    print("\n1. Fetching upcoming events with odds from BSD...")
    events = fetch_upcoming_events()
    if not events:
        print("   No upcoming events found")
        # Fallback: check live matches
        return

    # Step 2: Predict each match
    print(f"\n2. Running prediction on {len(events)} matches...")
    results = []
    for ev in events:
        home = ev.get('home_team', '')
        away = ev.get('away_team', '')
        oh = ev.get('odds_home')
        od = ev.get('odds_draw')
        oa = ev.get('odds_away')
        eid = ev.get('id')
        comp = ev.get('league', {}).get('name', '')

        if not all([home, away, oh, od, oa]):
            continue

        print(f"   {home[:20]:<20} vs {away:<20} | odds: {oh:.2f}/{od:.2f}/{oa:.2f}", end='')

        pred = dp.predict_match(home, away, today, odds_b365=(oh, od, oa), odds_avg=(oh, od, oa))
        if not pred:
            print(" -> SKIP (no prediction)")
            continue

        model_probs = {
            'home_prob': pred['probs_1x2']['home'] * 100,
            'draw_prob': pred['probs_1x2']['draw'] * 100,
            'away_prob': pred['probs_1x2']['away'] * 100,
        }

        # Convert BSD odds to fair probabilities
        market_data = {
            'implied_probs': {
                'home': (1/oh) / (1/oh + 1/od + 1/oa) * 100,
                'draw': (1/od) / (1/oh + 1/od + 1/oa) * 100,
                'away': (1/oa) / (1/oh + 1/od + 1/oa) * 100,
            },
            'fair_probs': {
                'home': round((1/oh) / (1/oh + 1/od + 1/oa) * 100, 2),
                'draw': round((1/od) / (1/oh + 1/od + 1/oa) * 100, 2),
                'away': round((1/oa) / (1/oh + 1/od + 1/oa) * 100, 2),
            },
            'avg_overround': round((1/oh + 1/od + 1/oa - 1) * 100, 2),
            'available': True,
        }

        value_bets = find_value_bets(model_probs, market_data, min_edge_pct=MIN_EDGE_PCT)

        if value_bets:
            print(f" >> VALUE! {value_bets[0]['outcome']} edge={value_bets[0]['edge_pct']:.1f}%")
        else:
            print(f" -> {pred['predicted_score']} ({pred['predicted_prob']*100:.1f}%)")

        results.append({
            'home': home, 'away': away, 'competition': comp,
            'bsd_event_id': eid,
            'predicted_score': pred['predicted_score'],
            'exact_prob': round(pred['predicted_prob']*100, 2),
            'model_probs': {k: round(v, 2) for k, v in model_probs.items()},
            'market_odds_raw': {'home': oh, 'draw': od, 'away': oa},
            'market_fair_probs': market_data['fair_probs'],
            'overround': market_data['avg_overround'],
            'value_bets': value_bets,
        })

    # Step 3: Report
    print(f"\n{'='*60}")
    print(f"VALUE BETTING REPORT -- {today}")
    print(f"{'='*60}")

    all_vb = [(r, vb) for r in results for vb in r.get('value_bets', [])]
    all_vb.sort(key=lambda x: -x[1]['edge_pct'])

    print(f"Matches predicted: {len(results)}")
    print(f"Value bets found:  {len(all_vb)}")

    if all_vb:
        print(f"\n{'-'*70}")
        print(f"{'Match':<35} {'Bet':<8} {'Model%':<8} {'Market%':<8} {'Edge%':<8} {'Kelly':<8} {'Verdict':<10}")
        print(f"{'-'*70}")
        for r, vb in all_vb:
            match_str = f"{r['home'][:15]} vs {r['away'][:15]}"
            mp = r['model_probs']
            mk = r['market_fair_probs']
            mp_val = mp.get(vb['outcome'] + '_prob', 0)
            mk_val = mk.get(vb['outcome'], 0)
            print(f"{match_str:<35} {vb['outcome']:<8} {mp_val:<8.1f} {mk_val:<8.1f} {vb['edge_pct']:<8.1f} {vb['kelly_fraction']:<8.2f} {vb['verdict']:<10}")

    strong = [x for x in all_vb if x[1]['verdict'] == 'STRONG']
    moderate = [x for x in all_vb if x[1]['verdict'] == 'MODERATE']
    print(f"\n{len(strong)} STRONG | {len(moderate)} MODERATE | {len(all_vb)-len(strong)-len(moderate)} WEAK")

    # Save
    out_path = os.path.join(OUTPUT_DIR, 'value_bets_daily.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'date': today,
            'pipeline': 'bsd_v3',
            'timestamp': datetime.now().isoformat(),
            'total_matches': len(results),
            'value_bets_count': len(all_vb),
            'strong_bets': len(strong),
            'moderate_bets': len(moderate),
            'results': results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {out_path}")

if __name__ == '__main__':
    run()
