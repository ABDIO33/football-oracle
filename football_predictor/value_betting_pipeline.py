"""
Value Betting Pipeline v2 — optimized
1. Fetch ALL odds from Odds API first (one call per league)
2. Match SofaScore matches to odds
3. Only run expensive prediction for matches WITH odds
4. Find value bets, output report
"""
import os, sys, json, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except:
    pass
import prediction_engine as pe
import odds_api_scraper as oas

MIN_EDGE_PCT = 5.0
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')

# Active soccer leagues (summer 2026 — EPL etc. return in Aug)
ODDS_LEAGUES = [
    'soccer_fifa_world_cup',
    'soccer_brazil_serie_b',
    'soccer_chile_campeonato',
    'soccer_china_superleague',
    'soccer_conmebol_copa_libertadores',
    'soccer_conmebol_copa_sudamericana',
    'soccer_finland_veikkausliiga',
    'soccer_germany_dfb_pokal',
    'soccer_league_of_ireland',
    'soccer_norway_eliteserien',
    'soccer_spain_segunda_division',
    'soccer_sweden_allsvenskan',
    'soccer_sweden_superettan',
]

def fetch_all_odds():
    """Fetch odds for all supported leagues. Returns dict: (home, away) -> event."""
    match_map = {}
    calls_made = 0
    for sk in ODDS_LEAGUES:
        url = (f"{oas.ODDS_API_BASE}/sports/{sk}/odds/"
               f"?apiKey={oas.ODDS_API_KEY}&regions=uk,eu,us&markets=h2h&oddsFormat=decimal")
        events = oas._cached_or_fetch(url, 10)
        calls_made += 1
        if not events:
            continue
        for event in events:
            home = event.get('home_team', '').lower().strip()
            away = event.get('away_team', '').lower().strip()
            match_map[(home, away)] = event
            match_map[(away, home)] = event  # reversed too
    print(f'Odds API calls: {calls_made}, matches with odds: {len(set(id(e) for e in match_map.values()))}')
    return match_map

def predict_and_find_value(home, away, comp, date_str, odds_event):
    """Run prediction + value bet analysis for a single match."""
    result = pe.analyze_match_deep(
        home, away, competition=comp,
        use_direct_model=True, use_market_odds=False,
        use_forebet=False, neutral_venue=False,
    )
    if not result:
        return None
    
    pred = {
        'home_prob': result.get('home_win_prob', 50),
        'draw_prob': result.get('draw_prob', 25),
        'away_prob': result.get('away_win_prob', 25),
        'predicted_score': result.get('most_likely_score', '0-0'),
        'confidence': result.get('exact_score_prob', 0),
    }
    
    market_probs = oas.extract_market_probabilities(odds_event)
    if not market_probs:
        return None
    
    mp = market_probs['fair_probs']
    match_preds = {
        'home_prob': pred['home_prob'],
        'draw_prob': pred['draw_prob'],
        'away_prob': pred['away_prob'],
    }
    value_bets = oas.find_value_bets(match_preds, market_probs, min_edge_pct=MIN_EDGE_PCT)
    
    return {
        'home': home, 'away': away, 'competition': comp, 'date': date_str,
        'prediction': pred,
        'market_odds': {
            'home_prob': mp.get('home'), 'draw_prob': mp.get('draw'), 'away_prob': mp.get('away'),
            'bookmaker_count': market_probs['bookmaker_count'], 'overround': market_probs['avg_overround'],
        },
        'value_bets': value_bets,
    }

def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    print(f'Value Betting Pipeline v2 — {today}')
    
    # Step 1: Get all odds
    print('\nFetching odds from Odds API...')
    odds_map = fetch_all_odds()
    print(f'Total unique events with odds: {len(set(json.dumps(v, default=str) for v in odds_map.values()))}')
    
    # Step 2: Get today's matches
    print('\nFetching today\'s matches from SofaScore...')
    matches = pe.get_daily_matches(date=today)
    if not matches:
        print('No matches found')
        return
    print(f'Today: {len(matches)} matches')
    
    # Step 3: Cross-reference
    results = []
    for match in matches:
        home = match.get('home_team', '')
        away = match.get('away_team', '')
        comp = match.get('competition', '')
        date_str = match.get('date', today)
        
        h_key = home.lower().strip()
        a_key = away.lower().strip()
        odds_event = odds_map.get((h_key, a_key)) or odds_map.get((a_key, h_key))
        
        if not odds_event:
            continue
        
        print(f'\n{match.get("date","")[:10]} {home} vs {away} ({comp})')
        r = predict_and_find_value(home, away, comp, date_str, odds_event)
        if not r:
            continue
        
        vb = r.get('value_bets', [])
        if vb:
            print(f'  VALUE BETS:')
            for v in vb:
                print(f'    {v["outcome"].upper()}: edge {v["edge_pct"]:.1f}% | Kelly {v["kelly_fraction"]:.2f} | {v["verdict"]}')
        else:
            print(f'  No value bets')
        results.append(r)
    
    # Step 4: Report
    all_vb = [(r, vb) for r in results for vb in r.get('value_bets', [])]
    all_vb.sort(key=lambda x: -x[1]['edge_pct'])
    
    print(f'\n{"="*60}')
    print(f'VALUE BETTING REPORT — {today}')
    print(f'{"="*60}')
    print(f'Matches with odds: {len(results)}')
    print(f'Value bets: {len(all_vb)}')
    
    if all_vb:
        print(f'\n{"─"*60}')
        print(f'{"Match":<35} {"Bet":<8} {"Edge%":<8} {"Kelly":<8} {"Verdict":<10}')
        print(f'{"─"*60}')
        for r, vb in all_vb:
            match_str = f'{r["home"][:15]} vs {r["away"][:15]}'
            print(f'{match_str:<35} {vb["outcome"]:<8} {vb["edge_pct"]:<8.1f} {vb["kelly_fraction"]:<8.2f} {vb["verdict"]:<10}')
    
    strong = [x for x in all_vb if x[1]['verdict'] == 'STRONG']
    moderate = [x for x in all_vb if x[1]['verdict'] == 'MODERATE']
    print(f'\n{len(strong)} STRONG | {len(moderate)} MODERATE | {len(all_vb)-len(strong)-len(moderate)} WEAK')
    
    # Save
    out_path = os.path.join(OUTPUT_DIR, 'value_bets_daily.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'date': today, 'timestamp': datetime.now().isoformat(),
            'total_matches_with_odds': len(results),
            'value_bets_count': len(all_vb),
            'results': results,
        }, f, ensure_ascii=False, indent=2)
    print(f'\nSaved to {out_path}')

if __name__ == '__main__':
    run()
