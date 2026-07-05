"""Live match status + betting analysis for today's WC matches"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from sofascore_scraper import get_match_details, get_match_lineups, get_match_statistics
from direct_predictor import predict_match
from datetime import datetime, timezone

matches = {
    15186769: ('France', 'Iraq', '17:00', 'inprogress'),
    15186770: ('Norway', 'Senegal', '20:00', 'upcoming'),
    15186740: ('Jordan', 'Algeria', '23:00', 'upcoming'),
}

print('='*80)
print('  LIVE BETTING ANALYSIS — 22 June 2026')
print('='*80)

for mid, (ht, at, kickoff, status) in matches.items():
    print()
    print('-'*80)
    print(f'  {ht} vs {at}  ({kickoff})')
    print('-'*80)

    # Get live match details
    details = get_match_details(mid)
    if details:
        ev = details.get('event', {})
        hs = ev.get('homeScore', {}).get('display', 0)
        as_ = ev.get('awayScore', {}).get('display', 0)
        status_type = ev.get('status', {}).get('type', '?')
        minute = ev.get('time', {}).get('current', '?')
        start_ts = ev.get('startTimestamp', 0)
        
        print(f'  LIVE: {ht} {hs} - {as_} {at}')
        print(f'  Status: {status_type} (minute: {minute})')
    
    # Get lineups
    lu = get_match_lineups(mid)
    if lu:
        home_lu = lu.get('home', {})
        away_lu = lu.get('away', {})
        hf = home_lu.get('formation', '?')
        af = away_lu.get('formation', '?')
        
        home_starters = [p for p in home_lu.get('players', []) if not p.get('substitute')]
        away_starters = [p for p in away_lu.get('players', []) if not p.get('substitute')]
        
        print(f'  {ht} ({hf}):')
        for p in home_starters:
            pn = p.get('player', {}).get('name', '?')
            pp = p.get('position', '?')
            ps = p.get('shirtNumber', '')
            print(f'    #{ps} {pn} ({pp})')
        
        print(f'  {at} ({af}):')
        for p in away_starters:
            pn = p.get('player', {}).get('name', '?')
            pp = p.get('position', '?')
            ps = p.get('shirtNumber', '')
            print(f'    #{ps} {pn} ({pp})')
    
    # Get model prediction (use tomorrow's date since it's in progress)
    match_date = '2026-06-22'
    print(f'  --- Model Prediction ---')
    try:
        pred = predict_match(ht, at, match_date)
        if pred:
            ps = pred.get('predicted_score', '?-?')
            pp = pred.get('predicted_prob', 0)
            probs = pred.get('probs_1x2', {})
            xg = pred.get('expected_goals', {})
            top = pred.get('top_scores', [])[:5]
            
            print(f'  Predicted: {ps} (prob: {pp:.1%})')
            print(f'  1X2: {probs.get("home",0):.1%} / {probs.get("draw",0):.1%} / {probs.get("away",0):.1%}')
            print(f'  xG: {xg.get("home",0):.2f} - {xg.get("away",0):.2f}')
            print(f'  Top scores:')
            for s in top:
                sc = s.get('score', '?')
                sp = s.get('prob', 0)
                print(f'    {sc}: {sp:.1%}')
        else:
            print(f'  No prediction available')
    except Exception as e:
        print(f'  Prediction error: {e}')

print(f'\n{"="*80}')
print('  ANALYSIS COMPLETE')
print(f'{"="*80}')
