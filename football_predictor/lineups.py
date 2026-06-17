import os, json, time
from sofascore_scraper import get_match_lineups

KEY_PLAYERS = {
    'Manchester City':  [{'name': 'Erling Haaland', 'share': 0.35, 'pos': 'FW'}, {'name': 'Kevin De Bruyne', 'share': 0.25, 'pos': 'MF'}, {'name': 'Phil Foden', 'share': 0.20, 'pos': 'MF'}],
    'Arsenal':          [{'name': 'Martin Odegaard', 'share': 0.25, 'pos': 'MF'}, {'name': 'Bukayo Saka', 'share': 0.25, 'pos': 'FW'}, {'name': 'Gabriel Jesus', 'share': 0.15, 'pos': 'FW'}],
    'Liverpool':        [{'name': 'Mohamed Salah', 'share': 0.35, 'pos': 'FW'}, {'name': 'Darwin Nunez', 'share': 0.20, 'pos': 'FW'}, {'name': 'Trent Alexander-Arnold', 'share': 0.15, 'pos': 'DF'}],
    'Bayern Munich':    [{'name': 'Harry Kane', 'share': 0.35, 'pos': 'FW'}, {'name': 'Jamal Musiala', 'share': 0.25, 'pos': 'MF'}, {'name': 'Leroy Sane', 'share': 0.15, 'pos': 'FW'}],
    'Real Madrid':      [{'name': 'Vinicius Junior', 'share': 0.30, 'pos': 'FW'}, {'name': 'Jude Bellingham', 'share': 0.25, 'pos': 'MF'}, {'name': 'Rodrygo', 'share': 0.20, 'pos': 'FW'}],
    'Barcelona':        [{'name': 'Lamine Yamal', 'share': 0.30, 'pos': 'FW'}, {'name': 'Robert Lewandowski', 'share': 0.25, 'pos': 'FW'}, {'name': 'Pedri', 'share': 0.15, 'pos': 'MF'}],
    'Inter Milan':      [{'name': 'Lautaro Martinez', 'share': 0.30, 'pos': 'FW'}, {'name': 'Nicolo Barella', 'share': 0.20, 'pos': 'MF'}, {'name': 'Marcus Thuram', 'share': 0.15, 'pos': 'FW'}],
    'AC Milan':         [{'name': 'Rafael Leao', 'share': 0.30, 'pos': 'FW'}, {'name': 'Tijjani Reijnders', 'share': 0.15, 'pos': 'MF'}, {'name': 'Christian Pulisic', 'share': 0.15, 'pos': 'FW'}],
    'Juventus':         [{'name': 'Dusan Vlahovic', 'share': 0.25, 'pos': 'FW'}, {'name': 'Federico Chiesa', 'share': 0.20, 'pos': 'FW'}, {'name': 'Manuel Locatelli', 'share': 0.10, 'pos': 'MF'}],
    'Paris Saint Germain': [{'name': 'Ousmane Dembele', 'share': 0.25, 'pos': 'FW'}, {'name': 'Randal Kolo Muani', 'share': 0.20, 'pos': 'FW'}, {'name': 'Warren Zaire-Emery', 'share': 0.15, 'pos': 'MF'}],
    'Bayer Leverkusen': [{'name': 'Florian Wirtz', 'share': 0.30, 'pos': 'MF'}, {'name': 'Victor Boniface', 'share': 0.25, 'pos': 'FW'}, {'name': 'Jeremie Frimpong', 'share': 0.15, 'pos': 'DF'}],
    'Chelsea':          [{'name': 'Cole Palmer', 'share': 0.30, 'pos': 'MF'}, {'name': 'Nicolas Jackson', 'share': 0.20, 'pos': 'FW'}, {'name': 'Enzo Fernandez', 'share': 0.15, 'pos': 'MF'}],
    'Tottenham':        [{'name': 'Son Heung-min', 'share': 0.30, 'pos': 'FW'}, {'name': 'James Maddison', 'share': 0.25, 'pos': 'MF'}, {'name': 'Cristian Romero', 'share': 0.10, 'pos': 'DF'}],
    'Newcastle':        [{'name': 'Alexander Isak', 'share': 0.30, 'pos': 'FW'}, {'name': 'Bruno Guimaraes', 'share': 0.25, 'pos': 'MF'}, {'name': 'Anthony Gordon', 'share': 0.15, 'pos': 'FW'}],
    'Aston Villa':      [{'name': 'Ollie Watkins', 'share': 0.30, 'pos': 'FW'}, {'name': 'John McGinn', 'share': 0.15, 'pos': 'MF'}, {'name': 'Youri Tielemans', 'share': 0.15, 'pos': 'MF'}],
    'Manchester United': [{'name': 'Bruno Fernandes', 'share': 0.30, 'pos': 'MF'}, {'name': 'Marcus Rashford', 'share': 0.25, 'pos': 'FW'}, {'name': 'Kobbie Mainoo', 'share': 0.15, 'pos': 'MF'}],
}

def get_key_players(team_name):
    for key, players in KEY_PLAYERS.items():
        if key.lower() in team_name.lower() or team_name.lower() in key.lower():
            return players
    return []

def get_expected_lineup(team_name, fixture_id):
    try:
        lu = get_match_lineups(fixture_id)
        if not lu or not lu.get('confirmed'):
            return None
        home_team = (lu.get('home') or {}).get('players', [])
        away_team = (lu.get('away') or {}).get('players', [])
        if not home_team and not away_team:
            return None
        team_lower = team_name.lower()
        for side_data in [lu.get('home'), lu.get('away')]:
            if not side_data:
                continue
            players = side_data.get('players', [])
            if not players:
                continue
            first = players[0]
            player_team = ((first.get('player') or {}).get('team') or {}).get('name', '')
            if player_team and (team_lower in player_team.lower() or player_team.lower() in team_lower):
                return [p.get('player', {}).get('name', '') for p in players[:11] if isinstance(p, dict) and p.get('player')]
        starter_names = []
        for p in home_team[:11]:
            starter_names.append(p.get('player', {}).get('name', ''))
        return starter_names
    except:
        pass
    return None

def get_lineup_formations(fixture_id):
    try:
        lu = get_match_lineups(fixture_id)
        if not lu or not lu.get('confirmed'):
            return None, None
        home_f = (lu.get('home') or {}).get('formation')
        away_f = (lu.get('away') or {}).get('formation')
        return home_f, away_f
    except:
        return None, None

def injury_adjustment(team_name, fixture_id=None, expected_starters=None):
    key_players = get_key_players(team_name)
    if not key_players:
        return 1.0, 'no_key_players'
    if not expected_starters:
        try:
            expected_starters = get_expected_lineup(team_name, fixture_id)
        except:
            pass
    if not expected_starters:
        return 1.0, 'not_yet_announced'
    missing_attack = 0.0
    missing_names = []
    starter_names = [s.lower() for s in expected_starters if s]
    for kp in key_players:
        found = any(kp['name'].lower() in s or s in kp['name'].lower() for s in starter_names)
        if not found:
            missing_attack += kp['share'] * 0.6
            missing_names.append(kp['name'])
    missing_attack = min(missing_attack, 0.30)
    return 1.0 - missing_attack, ','.join(missing_names) if missing_names else 'none_missing'
