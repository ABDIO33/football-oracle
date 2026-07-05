"""
v7_data_consolidation_v2.py — StatsBomb event features v2 (FIXED)
"""
import sqlite3, json, os, sys
import numpy as np
from datetime import datetime
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

def extract_json_field(raw_json, *path):
    """Safely traverse a nested JSON path. Returns None if any level missing."""
    try:
        obj = json.loads(raw_json)
        for key in path:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                return None
        if isinstance(obj, dict):
            return obj.get('name', str(obj))
        return str(obj)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None

def load_statsbomb_features_v2():
    conn = sqlite3.connect(DB)
    
    # Fetch all matches
    matches = conn.execute("""
        SELECT m.* FROM statsbomb_matches m
        ORDER BY m.match_date
    """).fetchall()
    mcols = [d[1] for d in conn.execute("PRAGMA table_info(statsbomb_matches)").fetchall()]
    
    # Pre-fetch all events grouped by match_id for efficiency
    log('Loading all events from DB (6.7M rows)...')
    all_events = conn.execute("""
        SELECT match_id, event_type, team, player, minute, second, 
               outcome, xg, raw_json
        FROM statsbomb_events 
        ORDER BY match_id, minute, second
    """).fetchall()
    log(f'Loaded {len(all_events):,} events')
    
    # Group events by match_id
    from collections import defaultdict
    match_events = defaultdict(list)
    for row in all_events:
        match_events[row[0]].append(row)
    
    ecols = ['match_id', 'event_type', 'team', 'player', 'minute', 'second', 'outcome', 'xg', 'raw_json']
    
    all_features = []
    processed = 0
    
    for row in matches:
        md = dict(zip(mcols, row))
        mid = md['match_id']
        ht, at = md['home_team'], md['away_team']
        hscr, ascr = md['home_score'], md['away_score']
        
        events = match_events.get(mid, [])
        
        # Separate home/away events
        home_ev = []
        away_ev = []
        for e in events:
            ev = dict(zip(ecols, e))
            team = ev.get('team', '')
            if team == ht:
                home_ev.append(ev)
            elif team == at:
                away_ev.append(ev)
        
        # ---- Shots ----
        home_shots = [e for e in home_ev if e.get('event_type') == 'Shot']
        away_shots = [e for e in away_ev if e.get('event_type') == 'Shot']
        
        h_xg = sum(e.get('xg', 0) or 0 for e in home_shots)
        a_xg = sum(e.get('xg', 0) or 0 for e in away_shots)
        
        # Shot on target: Goal, Saved, Saved to Post, Saved Off Target
        sot_outcomes = {'Goal', 'Saved', 'Saved to Post', 'Saved Off Target', 'SavedToPost'}
        h_shots_on = sum(1 for e in home_shots if e.get('outcome') in sot_outcomes)
        a_shots_on = sum(1 for e in away_shots if e.get('outcome') in sot_outcomes)
        
        # ---- Passes (from raw_json) ----
        home_passes = [e for e in home_ev if e.get('event_type') == 'Pass']
        away_passes = [e for e in away_ev if e.get('event_type') == 'Pass']
        
        def is_complete_pass(ev):
            """Complete if no pass.outcome.name or it's something other than Incomplete/Out"""
            rj = ev.get('raw_json')
            if not rj:
                return True  # assume complete
            outcome = extract_json_field(rj, 'pass', 'outcome')
            if outcome is None:
                return True  # no outcome = complete pass
            return outcome.lower() not in ('incomplete', 'out', 'pass offside')
        
        h_passes_complete = sum(1 for e in home_passes if is_complete_pass(e))
        a_passes_complete = sum(1 for e in away_passes if is_complete_pass(e))
        
        # ---- Pressures ----
        h_pressures = sum(1 for e in home_ev if e.get('event_type') == 'Pressure')
        a_pressures = sum(1 for e in away_ev if e.get('event_type') == 'Pressure')
        
        # ---- Touches (Ball Receipt + Carry) ----
        h_touches = sum(1 for e in home_ev if e.get('event_type') in ('Ball Receipt*', 'Carry'))
        a_touches = sum(1 for e in away_ev if e.get('event_type') in ('Ball Receipt*', 'Carry'))
        
        # ---- Duels won (from raw_json) ----
        home_duels = [e for e in home_ev if e.get('event_type') == 'Duel']
        away_duels = [e for e in away_ev if e.get('event_type') == 'Duel']
        
        def is_duel_won(ev):
            rj = ev.get('raw_json')
            if not rj:
                return False
            outcome = extract_json_field(rj, 'duel', 'outcome')
            return outcome in ('Won', 'Success In Play', 'Success Out')
        
        h_duels_won = sum(1 for e in home_duels if is_duel_won(e))
        a_duels_won = sum(1 for e in away_duels if is_duel_won(e))
        
        # ---- Additional features from raw_json ----
        
        # Dribbles completed (Dribble event with outcome=Complete/Won)
        home_dribbles = [e for e in home_ev if e.get('event_type') == 'Dribble']
        away_dribbles = [e for e in away_ev if e.get('event_type') == 'Dribble']
        
        def is_dribble_complete(ev):
            rj = ev.get('raw_json')
            if not rj:
                return False
            outcome = extract_json_field(rj, 'dribble', 'outcome')
            return outcome in ('Complete', 'Won')
        
        h_dribbles_complete = sum(1 for e in home_dribbles if is_dribble_complete(e))
        a_dribbles_complete = sum(1 for e in away_dribbles if is_dribble_complete(e))
        
        # Ball recoveries
        h_ball_recoveries = sum(1 for e in home_ev if e.get('event_type') == 'Ball Recovery')
        a_ball_recoveries = sum(1 for e in away_ev if e.get('event_type') == 'Ball Recovery')
        
        # Interceptions
        h_interceptions = sum(1 for e in home_ev if e.get('event_type') == 'Interception')
        a_interceptions = sum(1 for e in away_ev if e.get('event_type') == 'Interception')
        
        # Clearances
        h_clearances = sum(1 for e in home_ev if e.get('event_type') == 'Clearance')
        a_clearances = sum(1 for e in away_ev if e.get('event_type') == 'Clearance')
        
        # Fouls
        h_fouls = sum(1 for e in home_ev if e.get('event_type') == 'Foul Committed')
        a_fouls = sum(1 for e in away_ev if e.get('event_type') == 'Foul Committed')
        h_fouls_won = sum(1 for e in home_ev if e.get('event_type') == 'Foul Won')
        a_fouls_won = sum(1 for e in away_ev if e.get('event_type') == 'Foul Won')
        
        # Blocks
        h_blocks = sum(1 for e in home_ev if e.get('event_type') == 'Block')
        a_blocks = sum(1 for e in away_ev if e.get('event_type') == 'Block')
        
        # Miscontrols
        h_miscontrols = sum(1 for e in home_ev if e.get('event_type') == 'Miscontrol')
        a_miscontrols = sum(1 for e in away_ev if e.get('event_type') == 'Miscontrol')
        
        # Dispossessed
        h_dispossessed = sum(1 for e in home_ev if e.get('event_type') == 'Dispossessed')
        a_dispossessed = sum(1 for e in away_ev if e.get('event_type') == 'Dispossessed')
        
        # Pass types (from raw_json pass.height)
        def count_pass_type(events, height_name):
            cnt = 0
            for e in events:
                if e.get('event_type') != 'Pass':
                    continue
                rj = e.get('raw_json')
                if not rj:
                    continue
                h = extract_json_field(rj, 'pass', 'height')
                if h == height_name:
                    cnt += 1
            return cnt
        
        h_ground_passes = count_pass_type(home_passes, 'Ground Pass')
        a_ground_passes = count_pass_type(away_passes, 'Ground Pass')
        h_high_passes = count_pass_type(home_passes, 'High Pass')
        a_high_passes = count_pass_type(away_passes, 'High Pass')
        
        # Pass distance (average length)
        def avg_pass_length(events):
            total_len = 0.0
            count = 0
            for e in events:
                if e.get('event_type') != 'Pass':
                    continue
                rj = e.get('raw_json')
                if not rj:
                    continue
                try:
                    obj = json.loads(rj)
                    length = obj.get('pass', {}).get('length', 0)
                    if length:
                        total_len += length
                        count += 1
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
            return total_len / count if count > 0 else 0.0
        
        h_avg_pass_length = avg_pass_length(home_passes)
        a_avg_pass_length = avg_pass_length(away_passes)
        
        # Shot locations (average x,y for shot locations)
        def avg_shot_location(events):
            x_vals, y_vals = [], []
            for e in events:
                rj = e.get('raw_json')
                if not rj:
                    continue
                try:
                    obj = json.loads(rj)
                    loc = obj.get('location', [])
                    if len(loc) >= 2:
                        x_vals.append(loc[0])
                        y_vals.append(loc[1])
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
            return (np.mean(x_vals) if x_vals else 0.0,
                    np.mean(y_vals) if y_vals else 0.0)
        
        h_avg_shot_x, h_avg_shot_y = avg_shot_location(home_shots)
        a_avg_shot_x, a_avg_shot_y = avg_shot_location(away_shots)
        
        # Pass completion rate
        h_pass_pct = (h_passes_complete / max(len(home_passes), 1)) * 100
        a_pass_pct = (a_passes_complete / max(len(away_passes), 1)) * 100
        
        # xG share
        if h_xg + a_xg > 0:
            h_xg_share = h_xg / (h_xg + a_xg)
        else:
            h_xg_share = 0.5
        
        # Build feature dict (EXCLUDING home_score/away_score to prevent data leakage)
        feat = {
            # Match identifiers (not used as features)
            'match_id': mid, 'home_team': ht, 'away_team': at,
            'home_score': hscr, 'away_score': ascr,  # Targets
            'competition': md.get('competition_name', ''),
            'match_date': md.get('match_date', ''),
            
            # Shooting
            'h_xg': round(h_xg, 4), 'a_xg': round(a_xg, 4),
            'h_shots': len(home_shots), 'a_shots': len(away_shots),
            'h_shots_on_target': h_shots_on, 'a_shots_on_target': a_shots_on,
            'h_xg_per_shot': round(h_xg / max(len(home_shots), 1), 4),
            'a_xg_per_shot': round(a_xg / max(len(away_shots), 1), 4),
            'h_shot_accuracy': round(h_shots_on / max(len(home_shots), 1) * 100, 2),
            'a_shot_accuracy': round(a_shots_on / max(len(away_shots), 1) * 100, 2),
            'h_avg_shot_x': round(h_avg_shot_x, 2),
            'h_avg_shot_y': round(h_avg_shot_y, 2),
            'a_avg_shot_x': round(a_avg_shot_x, 2),
            'a_avg_shot_y': round(a_avg_shot_y, 2),
            
            # Passing
            'h_passes': len(home_passes), 'a_passes': len(away_passes),
            'h_passes_complete': h_passes_complete, 'a_passes_complete': a_passes_complete,
            'h_pass_pct': round(h_pass_pct, 2), 'a_pass_pct': round(a_pass_pct, 2),
            'h_ground_passes': h_ground_passes, 'a_ground_passes': a_ground_passes,
            'h_high_passes': h_high_passes, 'a_high_passes': a_high_passes,
            'h_avg_pass_length': round(h_avg_pass_length, 2),
            'a_avg_pass_length': round(a_avg_pass_length, 2),
            
            # Possession / Control
            'h_touches': h_touches, 'a_touches': a_touches,
            'h_pressures': h_pressures, 'a_pressures': a_pressures,
            'h_ball_recoveries': h_ball_recoveries, 'a_ball_recoveries': a_ball_recoveries,
            'h_interceptions': h_interceptions, 'a_interceptions': a_interceptions,
            'h_clearances': h_clearances, 'a_clearances': a_clearances,
            'h_blocks': h_blocks, 'a_blocks': a_blocks,
            
            # Duels
            'h_duels_won': h_duels_won, 'a_duels_won': a_duels_won,
            'h_duels': len(home_duels), 'a_duels': len(away_duels),
            'h_duel_win_pct': round(h_duels_won / max(len(home_duels), 1) * 100, 2),
            'a_duel_win_pct': round(a_duels_won / max(len(away_duels), 1) * 100, 2),
            
            # Dribbling
            'h_dribbles_complete': h_dribbles_complete, 'a_dribbles_complete': a_dribbles_complete,
            'h_dribbles': len(home_dribbles), 'a_dribbles': len(away_dribbles),
            'h_dribble_success': round(h_dribbles_complete / max(len(home_dribbles), 1) * 100, 2),
            'a_dribble_success': round(a_dribbles_complete / max(len(away_dribbles), 1) * 100, 2),
            
            # Fouls / Discipline
            'h_fouls': h_fouls, 'a_fouls': a_fouls,
            'h_fouls_won': h_fouls_won, 'a_fouls_won': a_fouls_won,
            'h_miscontrols': h_miscontrols, 'a_miscontrols': a_miscontrols,
            'h_dispossessed': h_dispossessed, 'a_dispossessed': a_dispossessed,
            
            # Derived
            'h_xg_diff': round(h_xg - a_xg, 4),
            'h_xg_share': round(h_xg_share, 4),
            'total_events': len(events),
        }
        
        all_features.append(feat)
        processed += 1
        if processed % 200 == 0:
            log(f'  Processed {processed}/{len(matches)} matches...')
    
    conn.close()
    return all_features

def save_v7_dataset(features):
    # Save full JSON
    out = os.path.join(BASE, 'models', 'v7_statsbomb_features_v2.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(features, f, indent=2, default=str)
    log(f'Saved {len(features)} matches to {out}')
    
    # Identify feature columns (exclude identifiers + targets for X)
    exclude = set([
        'match_id', 'home_team', 'away_team', 'competition', 'match_date',
        'home_score', 'away_score',  # These are targets, not features
    ])
    feature_names = [k for k in features[0].keys() if k not in exclude]
    
    # Build X matrix — handle None/empty safely
    arr = np.array([
        [float(f[k]) if f[k] not in (None, '', 'N/A') else 0.0 
         for k in feature_names] 
        for f in features
    ], dtype=np.float32)
    
    np.save(os.path.join(BASE, 'models', 'v7_statsbomb_X_v2.npy'), arr)
    
    # Build y as encoded score: home*5 + away (same encoding as main model)
    y = np.array([f['home_score'] * 5 + f['away_score'] for f in features], dtype=np.int64)
    np.save(os.path.join(BASE, 'models', 'v7_statsbomb_y_v2.npy'), y)
    
    log(f'X shape: {arr.shape}')
    log(f'y shape: {y.shape}')
    log(f'Features ({len(feature_names)}): {feature_names}')
    
    # Quick stats
    from collections import Counter
    y_dist = Counter(y)
    log(f'y distribution (top 10):')
    for val, cnt in y_dist.most_common(10):
        hs = val // 5
        aw = val % 5
        log(f'  {int(hs)}-{int(aw)}: {cnt} ({cnt/len(y)*100:.1f}%)')

if __name__ == '__main__':
    log('V2 — Loading StatsBomb event features (FIXED outcomes, expanded features)...')
    features = load_statsbomb_features_v2()
    log(f'Found {len(features)} matches with event data')
    if features:
        save_v7_dataset(features)
        log('Done! V2 StatsBomb dataset ready for training')
