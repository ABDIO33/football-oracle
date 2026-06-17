"""
player_impact.py — Player Impact Model
Builds player database from existing lineups, calculates impact scores per team.
"""

import sqlite3, json, os, sys
from collections import defaultdict
import numpy as np

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
_IMPACT_CACHE = None  # {team: [{'pid':..., 'name':..., 'pos':..., 'rate':..., 'att':..., 'def':...}]}

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS player_roster (
            player_id INTEGER, player_name TEXT, team_name TEXT,
            position TEXT, starts INTEGER DEFAULT 0, subs INTEGER DEFAULT 0,
            last_seen TEXT,
            PRIMARY KEY (player_id, team_name)
        );
        CREATE TABLE IF NOT EXISTS player_impact (
            player_id INTEGER, team_name TEXT, position TEXT,
            matches_with INTEGER DEFAULT 0, matches_without INTEGER DEFAULT 0,
            avg_gf_with REAL DEFAULT 0, avg_ga_with REAL DEFAULT 0,
            avg_gf_without REAL DEFAULT 0, avg_ga_without REAL DEFAULT 0,
            impact_attack REAL DEFAULT 0, impact_defense REAL DEFAULT 0,
            PRIMARY KEY (player_id, team_name)
        );
        CREATE TABLE IF NOT EXISTS team_core (
            team_name TEXT, player_id INTEGER, player_name TEXT,
            position TEXT, start_rate REAL DEFAULT 0,
            impact_attack REAL DEFAULT 0, impact_defense REAL DEFAULT 0,
            PRIMARY KEY (team_name, player_id)
        );
    ''')
    conn.commit()
    return conn

def build():
    """Parse all lineups → player roster + core 11 + impact scores."""
    conn = init_db()
    cur = conn.execute('''
        SELECT l.event_id, l.home_players_json, l.away_players_json,
               r.home_team, r.away_team, r.home_score, r.away_score, r.date
        FROM sofa_lineups l
        JOIN sofa_historical_results r ON l.event_id = r.id
    ''')
    rows = cur.fetchall()
    print(f"[PlayerImpact] Processing {len(rows)} lineups...")

    team_starters = defaultdict(dict)
    team_results = defaultdict(list)
    team_starts_cnt = defaultdict(lambda: defaultdict(int))
    player_info = {}
    team_player_teams = defaultdict(dict)

    for row in rows:
        eid, hpj, apj, ht, at, hs, aws, date = row
        if not ht or not at:
            continue
        try:
            home_ps = json.loads(hpj) if hpj else []
            away_ps = json.loads(apj) if apj else []
        except:
            continue

        def parse_players(players, team):
            starters = set()
            for p in players:
                if not isinstance(p, dict):
                    continue
                pl = p.get('player', {})
                pid = pl.get('id')
                if pid is None:
                    continue
                pname = pl.get('name', f'p{pid}')
                pos = p.get('position', pl.get('position', 'U'))
                is_sub = p.get('substitute', False)
                player_info[pid] = (pname, pos)
                team_player_teams[team][pid] = True
                if not is_sub:
                    starters.add(pid)
                    team_starts_cnt[team][pid] += 1
            return starters

        hs_starters = parse_players(home_ps, ht)
        team_starters[ht][eid] = hs_starters
        team_results[ht].append((eid, hs, aws, date))

        as_starters = parse_players(away_ps, at)
        team_starters[at][eid] = as_starters
        team_results[at].append((eid, aws, hs, date))

    print(f"[PlayerImpact] {len(player_info)} unique players, {len(team_starts_cnt)} teams")

    for pid, (pname, pos) in player_info.items():
        conn.execute('INSERT OR IGNORE INTO player_roster (player_id, player_name, position) VALUES (?, ?, ?)',
                     (pid, pname, pos))
    conn.commit()

    for team, pstarts in team_starts_cnt.items():
        total = len(team_results.get(team, []))
        if total < 3:
            continue
        team_lineup_eids = set(team_starters.get(team, {}).keys())
        sorted_ps = sorted(pstarts.items(), key=lambda x: -x[1])
        for pid, starts in sorted_ps:
            start_rate = starts / max(total, 1)
            pname, pos = player_info.get(pid, (f'p{pid}', 'U'))
            matches_with = [r for r in team_results[team] if r[0] in team_lineup_eids and pid in team_starters[team][r[0]]]
            matches_with_ids = {r[0] for r in matches_with}
            gf_with = [r[1] for r in matches_with]
            ga_with = [r[2] for r in matches_with]
            gf_without = [r[1] for r in team_results[team] if r[0] in team_lineup_eids and r[0] not in matches_with_ids]
            ga_without = [r[2] for r in team_results[team] if r[0] in team_lineup_eids and r[0] not in matches_with_ids]

            imp_att = 0.0
            imp_def = 0.0
            if len(gf_with) >= 2 and len(gf_without) >= 2:
                imp_att = float(np.mean(gf_with) - np.mean(gf_without))
                imp_def = float(np.mean(ga_without) - np.mean(ga_with))

            conn.execute('''INSERT OR REPLACE INTO player_impact
                (player_id, team_name, position, matches_with, matches_without,
                 avg_gf_with, avg_ga_with, avg_gf_without, avg_ga_without,
                 impact_attack, impact_defense)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (pid, team, pos, len(gf_with), len(gf_without),
                 float(np.mean(gf_with)) if gf_with else 0,
                 float(np.mean(ga_with)) if ga_with else 0,
                 float(np.mean(gf_without)) if gf_without else 0,
                 float(np.mean(ga_without)) if ga_without else 0,
                 imp_att, imp_def))

            conn.execute('''INSERT OR REPLACE INTO team_core
                (team_name, player_id, player_name, position, start_rate, impact_attack, impact_defense)
                VALUES (?,?,?,?,?,?,?)''',
                (team, pid, pname, pos, start_rate, imp_att, imp_def))

        conn.commit()

    cnt = conn.execute('SELECT COUNT(DISTINCT team_name) FROM team_core').fetchone()[0]
    print(f"[PlayerImpact] Done: {cnt} teams with core starters")
    conn.close()

def _load_cache():
    global _IMPACT_CACHE
    if _IMPACT_CACHE is not None:
        return
    conn = sqlite3.connect(DB)
    cur = conn.execute('SELECT team_name, player_id, player_name, position, start_rate, impact_attack, impact_defense FROM team_core')
    _IMPACT_CACHE = defaultdict(list)
    for row in cur.fetchall():
        _IMPACT_CACHE[row[0]].append({
            'pid': row[1], 'name': row[2], 'pos': row[3],
            'rate': row[4], 'att': row[5], 'def': row[6]
        })
    conn.close()
    print(f"[PlayerImpact] Cached {len(_IMPACT_CACHE)} teams")

def get_missing_impact(home_team, away_team, home_starters=None, away_starters=None):
    """Calculate missing player impact features.
    Returns: (h_missing, h_att_loss, h_def_loss, a_missing, a_att_loss, a_def_loss)
    """
    _load_cache()
    if _IMPACT_CACHE is None:
        return 0, 0, 0, 0, 0, 0
    h_core = _IMPACT_CACHE.get(home_team, [])
    a_core = _IMPACT_CACHE.get(away_team, [])
    if not h_core and not a_core:
        return 0, 0, 0, 0, 0, 0
    h_starter_names = set(s.lower() if s else '' for s in (home_starters or []))
    a_starter_names = set(s.lower() if s else '' for s in (away_starters or []))
    h_missing = h_att_loss = h_def_loss = 0
    a_missing = a_att_loss = a_def_loss = 0

    for p in h_core:
        if p['rate'] < 0.5:
            continue  # Only count regular starters
        if not h_starter_names:
            continue
        found = any(p['name'].lower() in sn or sn in p['name'].lower() for sn in h_starter_names)
        if not found:
            h_missing += 1
            if p['att'] > 0:
                h_att_loss += p['att']
            if p['def'] > 0:
                h_def_loss += p['def']

    for p in a_core:
        if p['rate'] < 0.5:
            continue
        if not a_starter_names:
            continue
        found = any(p['name'].lower() in sn or sn in p['name'].lower() for sn in a_starter_names)
        if not found:
            a_missing += 1
            if p['att'] > 0:
                a_att_loss += p['att']
            if p['def'] > 0:
                a_def_loss += p['def']

    return h_missing, h_att_loss, h_def_loss, a_missing, a_att_loss, a_def_loss

def get_missing_from_lineup_id(home_team, away_team, match_id):
    """Get missing impact from DB-stored lineups using match_id."""
    conn = sqlite3.connect(DB)
    cur = conn.execute('SELECT home_players_json, away_players_json FROM sofa_lineups WHERE event_id = ?', (match_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return 0, 0, 0, 0, 0, 0

    def extract_starter_names(players_json):
        try:
            ps = json.loads(players_json) if players_json else []
        except:
            return []
        names = []
        for p in ps:
            if isinstance(p, dict) and not p.get('substitute', False):
                pl = p.get('player', {})
                names.append(pl.get('name', ''))
        return names

    home_starters = extract_starter_names(row[0])
    away_starters = extract_starter_names(row[1])
    return get_missing_impact(home_team, away_team, home_starters, away_starters)

if __name__ == '__main__':
    build()
    print("[PlayerImpact] Build complete")
    _load_cache()
    print(f"[PlayerImpact] {len(_IMPACT_CACHE)} teams cached")
