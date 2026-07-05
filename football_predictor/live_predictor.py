"""
live_predictor.py - predict all SofaScore live/upcoming matches
"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

from curl_cffi import requests as curl
from datetime import datetime
from ultimate_predictor import UltimatePredictor

def fetch_live_matches():
    url = 'https://api.sofascore.com/api/v1/sport/football/events/live'
    r = curl.get(url, impersonate='chrome120', timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    matches = []
    for e in data.get('events', []):
        ht = e.get('homeTeam', {}).get('name', '')
        at = e.get('awayTeam', {}).get('name', '')
        if not ht or not at:
            continue
        ts = e.get('startTimestamp', 0)
        tour = e.get('tournament', {}).get('name', '')
        matches.append({
            'home_team': ht, 'away_team': at,
            'date': datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts else None,
            'time': datetime.fromtimestamp(ts).strftime('%H:%M') if ts else '?',
            'tournament': tour,
            'startTimestamp': ts,
        })
    return matches

def predict_and_save():
    print('LIVE PREDICTOR')
    print('='*55)
    
    matches = fetch_live_matches()
    print(f'Matches: {len(matches)}')
    if not matches:
        print('No matches found.')
        return
    
    # Show tournaments
    tours = {}
    for m in matches:
        tours.setdefault(m['tournament'], []).append(m)
    for t, ms in sorted(tours.items(), key=lambda x: -len(x[1]))[:10]:
        print(f'  {t}: {len(ms)}')
    
    print('Loading predictor...')
    pred = UltimatePredictor()
    
    print(f'Predicting {len(matches)} matches...')
    results = []
    
    for i, m in enumerate(matches):
        r = pred.predict(m['home_team'], m['away_team'], m['tournament'], m['date'])
        r['time'] = m['time']
        r['startTimestamp'] = m['startTimestamp']
        results.append(r)
        
        e = r.get('ensemble')
        if e:
            print(f'  [{i+1}/{len(matches)}] {m["home_team"][:22]:22s} vs {m["away_team"][:22]:22s} -> {e["predicted_score"]:>5s} ({e["confidence"]*100:.0f}%)')
        else:
            print(f'  [{i+1}/{len(matches)}] {m["home_team"][:22]:22s} vs {m["away_team"][:22]:22s} -> ERROR')
    
    # Save
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            import numpy as np
            if isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)
    
    output = {
        'generated_at': datetime.now().isoformat(),
        'total': len(matches),
        'predictions': results
    }
    out_path = os.path.join(BASE, 'live_predictions.json')
    json.dump(output, open(out_path, 'w', encoding='utf-8'), indent=2, ensure_ascii=False, cls=NumpyEncoder)
    print(f'Saved: {out_path}')
    
    # Print best predictions
    print('\n=== BEST PREDICTIONS (by confidence) ===')
    results.sort(key=lambda x: -(x.get('ensemble', {}) or {}).get('confidence', 0))
    for r in results[:15]:
        e = r.get('ensemble')
        if not e:
            continue
        conf = e['confidence']
        bar_len = int(conf * 30)
        bar = '#' * bar_len + '-' * (30 - bar_len)
        
        pscore = e['predicted_score']
        presult = e['predicted_result']
        hname = r['home'][:22]
        aname = r['away'][:22]
        tname = r['tournament'][:30]
        dstr = r['date'] or ''
        tstr = r['time']
        
        print(f'  {hname:22s} vs {aname}')
        print(f'  {tname:30s} {dstr} {tstr}')
        print(f'  Score: {pscore:>5s} ({presult:>6s})  {bar} {conf*100:.1f}%')
        
        top3 = e.get('top3', [])
        if top3:
            parts = [f"{t['score']} ({t['prob']*100:.0f}%)" for t in top3[:3]]
            print(f'  Top3: {" | ".join(parts)}')
        print()

if __name__ == '__main__':
    predict_and_save()
