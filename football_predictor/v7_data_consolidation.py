"""
v7_data_consolidation.py — Merge StatsBomb events → match features for V7 training
"""
import sqlite3, json, os, sys
import numpy as np
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

def load_statsbomb_features():
    conn = sqlite3.connect(DB)
    matches = conn.execute("""
        SELECT m.* FROM statsbomb_matches m
        ORDER BY m.match_date
    """).fetchall()
    mcols = [d[1] for d in conn.execute("PRAGMA table_info(statsbomb_matches)").fetchall()]

    all_features = []
    for row in matches:
        md = dict(zip(mcols, row))
        mid = md['match_id']
        ht, at = md['home_team'], md['away_team']
        hscr, ascr = md['home_score'], md['away_score']

        events = conn.execute(
            "SELECT * FROM statsbomb_events WHERE match_id=? ORDER BY minute, second", (mid,)
        ).fetchall()
        ecols = [d[1] for d in conn.execute("PRAGMA table_info(statsbomb_events)").fetchall()]

        home_events = [dict(zip(ecols, e)) for e in events if dict(zip(ecols, e))['team'] == ht]
        away_events = [dict(zip(ecols, e)) for e in events if dict(zip(ecols, e))['team'] == at]
        all_ev = [dict(zip(ecols, e)) for e in events]

        home_shots = [e for e in home_events if e.get('event_type') == 'Shot']
        away_shots = [e for e in away_events if e.get('event_type') == 'Shot']
        home_passes = [e for e in home_events if e.get('event_type') == 'Pass']
        away_passes = [e for e in away_events if e.get('event_type') == 'Pass']

        h_xg = sum(e.get('xg', 0) or 0 for e in home_shots)
        a_xg = sum(e.get('xg', 0) or 0 for e in away_shots)
        h_shots_on = sum(1 for e in home_shots if e.get('outcome') in ['Goal', 'Saved', 'SavedToPost'])
        a_shots_on = sum(1 for e in away_shots if e.get('outcome') in ['Goal', 'Saved', 'SavedToPost'])
        h_passes_complete = sum(1 for e in home_passes if e.get('outcome') == 'Complete')
        a_passes_complete = sum(1 for e in away_passes if e.get('outcome') == 'Complete')

        h_pressures = sum(1 for e in home_events if e.get('event_type') == 'Pressure')
        a_pressures = sum(1 for e in away_events if e.get('event_type') == 'Pressure')
        h_touches = sum(1 for e in home_events if e.get('event_type') in ['Ball Receipt', 'Carry'])
        a_touches = sum(1 for e in away_events if e.get('event_type') in ['Ball Receipt', 'Carry'])
        h_duels_won = sum(1 for e in home_events if e.get('event_type') == 'Duel' and e.get('outcome') == 'Won')
        a_duels_won = sum(1 for e in away_events if e.get('event_type') == 'Duel' and e.get('outcome') == 'Won')

        feat = {
            'match_id': mid, 'home_team': ht, 'away_team': at,
            'home_score': hscr, 'away_score': ascr,
            'competition': md.get('competition_name', ''),
            'match_date': md.get('match_date', ''),
            'home_formation': md.get('home_formation', ''),
            'away_formation': md.get('away_formation', ''),
            'referee': md.get('referee', ''),
            'venue': md.get('venue', ''),
            'h_xg': h_xg, 'a_xg': a_xg,
            'h_shots': len(home_shots), 'a_shots': len(away_shots),
            'h_shots_on_target': h_shots_on, 'a_shots_on_target': a_shots_on,
            'h_passes': len(home_passes), 'a_passes': len(away_passes),
            'h_passes_complete': h_passes_complete, 'a_passes_complete': a_passes_complete,
            'h_pressures': h_pressures, 'a_pressures': a_pressures,
            'h_touches': h_touches, 'a_touches': a_touches,
            'h_duels_won': h_duels_won, 'a_duels_won': a_duels_won,
            'h_xg_diff': h_xg - a_xg,
            'total_events': len(all_ev),
        }
        feat['h_pass_pct'] = (h_passes_complete / max(len(home_passes), 1)) * 100
        feat['a_pass_pct'] = (a_passes_complete / max(len(away_passes), 1)) * 100
        if h_xg + a_xg > 0:
            feat['h_xg_share'] = h_xg / (h_xg + a_xg)
        else:
            feat['h_xg_share'] = 0.5
        all_features.append(feat)

    conn.close()
    return all_features

def save_v7_dataset(features):
    out = os.path.join(BASE, 'models', 'v7_statsbomb_features.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(features, f, indent=2, default=str)
    log(f'Saved {len(features)} matches with StatsBomb features to {out}')

    feature_names = [k for k in features[0].keys() if k not in (
        'match_id','home_team','away_team','competition','match_date',
        'referee','venue','home_formation','away_formation'
    )]
    arr = np.array([[float(f[k]) if f[k] not in (None, '', 'N/A') else 0.0 for k in feature_names] for f in features], dtype=np.float32)
    np.save(os.path.join(BASE, 'models', 'v7_statsbomb_X.npy'), arr)
    y = np.array([f['home_score'] * 5 + f['away_score'] for f in features], dtype=np.int64)
    np.save(os.path.join(BASE, 'models', 'v7_statsbomb_y.npy'), y)
    log(f'Shapes: X={arr.shape}, y={y.shape}')
    log(f'Features ({len(feature_names)}): {feature_names}')

if __name__ == '__main__':
    log('Loading StatsBomb event features...')
    features = load_statsbomb_features()
    log(f'Found {len(features)} matches with event data')
    if features:
        save_v7_dataset(features)
        log('Done! V7 StatsBomb dataset ready for training')
