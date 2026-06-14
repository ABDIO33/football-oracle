import os, json, time

KEY_PLAYERS = {
    'France':  [{'name': 'Kylian Mbappe', 'share': 0.35, 'pos': 'FW'}, {'name': 'Antoine Griezmann', 'share': 0.20, 'pos': 'FW'}, {'name': 'Eduardo Camavinga', 'share': 0.10, 'pos': 'MF'}],
    'Argentina': [{'name': 'Lionel Messi', 'share': 0.35, 'pos': 'FW'}, {'name': 'Julian Alvarez', 'share': 0.20, 'pos': 'FW'}, {'name': 'Enzo Fernandez', 'share': 0.15, 'pos': 'MF'}],
    'Brazil':  [{'name': 'Vinicius Junior', 'share': 0.30, 'pos': 'FW'}, {'name': 'Rodrygo', 'share': 0.20, 'pos': 'FW'}, {'name': 'Raphinha', 'share': 0.15, 'pos': 'FW'}],
    'England': [{'name': 'Harry Kane', 'share': 0.35, 'pos': 'FW'}, {'name': 'Jude Bellingham', 'share': 0.25, 'pos': 'MF'}, {'name': 'Bukayo Saka', 'share': 0.20, 'pos': 'FW'}],
    'Spain':   [{'name': 'Lamine Yamal', 'share': 0.25, 'pos': 'FW'}, {'name': 'Rodri', 'share': 0.25, 'pos': 'MF'}, {'name': 'Nico Williams', 'share': 0.20, 'pos': 'FW'}],
    'Germany': [{'name': 'Jamal Musiala', 'share': 0.30, 'pos': 'MF'}, {'name': 'Florian Wirtz', 'share': 0.25, 'pos': 'MF'}, {'name': 'Niclas Fullkrug', 'share': 0.15, 'pos': 'FW'}],
    'Portugal': [{'name': 'Cristiano Ronaldo', 'share': 0.30, 'pos': 'FW'}, {'name': 'Bruno Fernandes', 'share': 0.25, 'pos': 'MF'}, {'name': 'Rafael Leao', 'share': 0.15, 'pos': 'FW'}],
    'Netherlands': [{'name': 'Memphis Depay', 'share': 0.25, 'pos': 'FW'}, {'name': 'Frenkie de Jong', 'share': 0.20, 'pos': 'MF'}, {'name': 'Cody Gakpo', 'share': 0.15, 'pos': 'FW'}],
    'Belgium': [{'name': 'Kevin De Bruyne', 'share': 0.30, 'pos': 'MF'}, {'name': 'Romelu Lukaku', 'share': 0.20, 'pos': 'FW'}, {'name': 'Jeremy Doku', 'share': 0.15, 'pos': 'FW'}],
    'Italy':   [{'name': 'Nicolo Barella', 'share': 0.20, 'pos': 'MF'}, {'name': 'Federico Chiesa', 'share': 0.20, 'pos': 'FW'}, {'name': 'Gianluigi Donnarumma', 'share': 0.15, 'pos': 'GK'}],
    'Croatia': [{'name': 'Luka Modric', 'share': 0.25, 'pos': 'MF'}, {'name': 'Mateo Kovacic', 'share': 0.20, 'pos': 'MF'}, {'name': 'Andrej Kramaric', 'share': 0.15, 'pos': 'FW'}],
    'Denmark': [{'name': 'Christian Eriksen', 'share': 0.25, 'pos': 'MF'}, {'name': 'Rasmus Hojlund', 'share': 0.20, 'pos': 'FW'}, {'name': 'Pierre Hojbjerg', 'share': 0.10, 'pos': 'MF'}],
    'Switzerland': [{'name': 'Granit Xhaka', 'share': 0.20, 'pos': 'MF'}, {'name': 'Breel Embolo', 'share': 0.20, 'pos': 'FW'}, {'name': 'Manuel Akanji', 'share': 0.10, 'pos': 'DF'}],
    'Poland':  [{'name': 'Robert Lewandowski', 'share': 0.40, 'pos': 'FW'}, {'name': 'Piotr Zielinski', 'share': 0.20, 'pos': 'MF'}, {'name': 'Nicola Zalewski', 'share': 0.10, 'pos': 'MF'}],
    'Serbia':  [{'name': 'Aleksandar Mitrovic', 'share': 0.30, 'pos': 'FW'}, {'name': 'Dusan Vlahovic', 'share': 0.20, 'pos': 'FW'}, {'name': 'Sergej Milinkovic-Savic', 'share': 0.20, 'pos': 'MF'}],
    'Uruguay': [{'name': 'Federico Valverde', 'share': 0.25, 'pos': 'MF'}, {'name': 'Darwin Nunez', 'share': 0.20, 'pos': 'FW'}, {'name': 'Ronald Araujo', 'share': 0.15, 'pos': 'DF'}],
    'Colombia': [{'name': 'Luis Diaz', 'share': 0.30, 'pos': 'FW'}, {'name': 'James Rodriguez', 'share': 0.20, 'pos': 'MF'}, {'name': 'Rafael Borre', 'share': 0.15, 'pos': 'FW'}],
    'United States': [{'name': 'Christian Pulisic', 'share': 0.30, 'pos': 'FW'}, {'name': 'Weston McKennie', 'share': 0.20, 'pos': 'MF'}, {'name': 'Folarin Balogun', 'share': 0.15, 'pos': 'FW'}],
    'Mexico':  [{'name': 'Raul Jimenez', 'share': 0.25, 'pos': 'FW'}, {'name': 'Hirving Lozano', 'share': 0.20, 'pos': 'FW'}, {'name': 'Edson Alvarez', 'share': 0.15, 'pos': 'MF'}],
    'Canada':  [{'name': 'Alphonso Davies', 'share': 0.30, 'pos': 'DF'}, {'name': 'Jonathan David', 'share': 0.25, 'pos': 'FW'}, {'name': 'Stephen Eustaquio', 'share': 0.15, 'pos': 'MF'}],
    'Morocco': [{'name': 'Achraf Hakimi', 'share': 0.25, 'pos': 'DF'}, {'name': 'Hakim Ziyech', 'share': 0.20, 'pos': 'FW'}, {'name': 'Youssef En-Nesyri', 'share': 0.20, 'pos': 'FW'}],
    'Senegal': [{'name': 'Sadio Mane', 'share': 0.35, 'pos': 'FW'}, {'name': 'Idrissa Gueye', 'share': 0.15, 'pos': 'MF'}, {'name': 'Nicolas Jackson', 'share': 0.15, 'pos': 'FW'}],
    'Nigeria': [{'name': 'Victor Osimhen', 'share': 0.35, 'pos': 'FW'}, {'name': 'Samuel Chukwueze', 'share': 0.20, 'pos': 'FW'}, {'name': 'Wilfred Ndidi', 'share': 0.15, 'pos': 'MF'}],
    'Egypt':   [{'name': 'Mohamed Salah', 'share': 0.40, 'pos': 'FW'}, {'name': 'Mahmoud Trezeguet', 'share': 0.15, 'pos': 'FW'}, {'name': 'Mohamed Elneny', 'share': 0.10, 'pos': 'MF'}],
    'Algeria': [{'name': 'Riyad Mahrez', 'share': 0.30, 'pos': 'FW'}, {'name': 'Islam Slimani', 'share': 0.20, 'pos': 'FW'}, {'name': 'Ramy Bensebaini', 'share': 0.10, 'pos': 'DF'}],
    'Japan':   [{'name': 'Takefusa Kubo', 'share': 0.25, 'pos': 'FW'}, {'name': 'Daichi Kamada', 'share': 0.20, 'pos': 'MF'}, {'name': 'Wataru Endo', 'share': 0.15, 'pos': 'MF'}],
    'South Korea': [{'name': 'Son Heung-min', 'share': 0.35, 'pos': 'FW'}, {'name': 'Kang-in Lee', 'share': 0.20, 'pos': 'MF'}, {'name': 'Kim Min-jae', 'share': 0.15, 'pos': 'DF'}],
    'Australia': [{'name': 'Craig Goodwin', 'share': 0.20, 'pos': 'FW'}, {'name': 'Mathew Leckie', 'share': 0.20, 'pos': 'FW'}, {'name': 'Harry Souttar', 'share': 0.15, 'pos': 'DF'}],
    'Ecuador': [{'name': 'Enner Valencia', 'share': 0.30, 'pos': 'FW'}, {'name': 'Moises Caicedo', 'share': 0.25, 'pos': 'MF'}, {'name': 'Pervis Estupinan', 'share': 0.10, 'pos': 'DF'}],
    'Sweden':  [{'name': 'Alexander Isak', 'share': 0.30, 'pos': 'FW'}, {'name': 'Dejan Kulusevski', 'share': 0.20, 'pos': 'MF'}, {'name': 'Victor Lindelof', 'share': 0.10, 'pos': 'DF'}],
    'Austria': [{'name': 'Marcel Sabitzer', 'share': 0.25, 'pos': 'MF'}, {'name': 'Marko Arnautovic', 'share': 0.20, 'pos': 'FW'}, {'name': 'Konrad Laimer', 'share': 0.15, 'pos': 'MF'}],
    'Ghana':   [{'name': 'Mohammed Kudus', 'share': 0.30, 'pos': 'MF'}, {'name': 'Inaki Williams', 'share': 0.25, 'pos': 'FW'}, {'name': 'Thomas Partey', 'share': 0.15, 'pos': 'MF'}],
    'Ivory Coast': [{'name': 'Sebastien Haller', 'share': 0.25, 'pos': 'FW'}, {'name': 'Franck Kessie', 'share': 0.20, 'pos': 'MF'}, {'name': 'Nicolas Pepe', 'share': 0.15, 'pos': 'FW'}],
    'Cameroon': [{'name': 'Vincent Aboubakar', 'share': 0.25, 'pos': 'FW'}, {'name': 'Andre Onana', 'share': 0.15, 'pos': 'GK'}, {'name': 'Bryan Mbeumo', 'share': 0.20, 'pos': 'FW'}],
    'Paraguay': [{'name': 'Miguel Almiron', 'share': 0.25, 'pos': 'FW'}, {'name': 'Julio Enciso', 'share': 0.20, 'pos': 'FW'}, {'name': 'Gustavo Gomez', 'share': 0.10, 'pos': 'DF'}],
    'Chile':   [{'name': 'Alexis Sanchez', 'share': 0.25, 'pos': 'FW'}, {'name': 'Eduardo Vargas', 'share': 0.20, 'pos': 'FW'}, {'name': 'Arturo Vidal', 'share': 0.15, 'pos': 'MF'}],
    'Costa Rica': [{'name': 'Keysher Fuller', 'share': 0.20, 'pos': 'DF'}, {'name': 'Joel Campbell', 'share': 0.20, 'pos': 'FW'}, {'name': 'Celso Borges', 'share': 0.15, 'pos': 'MF'}],
    'Jamaica': [{'name': 'Leon Bailey', 'share': 0.30, 'pos': 'FW'}, {'name': 'Michail Antonio', 'share': 0.20, 'pos': 'FW'}, {'name': 'Demarai Gray', 'share': 0.15, 'pos': 'FW'}],
    'Iran':    [{'name': 'Mehdi Taremi', 'share': 0.30, 'pos': 'FW'}, {'name': 'Sardar Azmoun', 'share': 0.25, 'pos': 'FW'}, {'name': 'Alireza Jahanbakhsh', 'share': 0.15, 'pos': 'FW'}],
    'Saudi Arabia': [{'name': 'Salem Al-Dawsari', 'share': 0.30, 'pos': 'FW'}, {'name': 'Firas Al-Buraikan', 'share': 0.20, 'pos': 'FW'}, {'name': 'Saud Abdulhamid', 'share': 0.10, 'pos': 'DF'}],
    'Tunisia': [{'name': 'Wahbi Khazri', 'share': 0.25, 'pos': 'FW'}, {'name': 'Ellyes Skhiri', 'share': 0.20, 'pos': 'MF'}, {'name': 'Youssef Msakni', 'share': 0.15, 'pos': 'FW'}],
    'South Africa': [{'name': 'Percy Tau', 'share': 0.25, 'pos': 'FW'}, {'name': 'Lyle Foster', 'share': 0.20, 'pos': 'FW'}, {'name': 'Teboho Mokoena', 'share': 0.15, 'pos': 'MF'}],
    'New Zealand': [{'name': 'Chris Wood', 'share': 0.35, 'pos': 'FW'}, {'name': 'Liberato Cacace', 'share': 0.10, 'pos': 'DF'}, {'name': 'Joe Bell', 'share': 0.10, 'pos': 'MF'}],
    # Top clubs
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
}

def get_key_players(team_name):
    return KEY_PLAYERS.get(team_name, [])

def injury_adjustment(team_name, fixture_id=None, expected_starters=None):
    key_players = get_key_players(team_name)
    if not key_players:
        return 1.0, 'no_key_players'
    if not expected_starters:
        return 1.0, 'not_yet_announced'
    missing_attack = 0.0
    missing_names = []
    starter_names = [s.lower() for s in expected_starters]
    for kp in key_players:
        found = any(kp['name'].lower() in s or s in kp['name'].lower() for s in starter_names)
        if not found:
            missing_attack += kp['share'] * 0.6
            missing_names.append(kp['name'])
    missing_attack = min(missing_attack, 0.30)
    return 1.0 - missing_attack, ','.join(missing_names) if missing_names else 'none_missing'

def get_expected_lineup(team_name, fixture_id):
    from prediction_engine import API_FOOTBALL_BASE, _cached_or_fetch
    headers = lambda: {'x-apisports-key': os.environ.get('API_SPORT_KEY', '')}
    try:
        url = f"{API_FOOTBALL_BASE}/fixtures/lineups?fixture={fixture_id}"
        data = _cached_or_fetch(url, headers, 15)
        if data and 'response' in data:
            for entry in data['response']:
                tname = entry.get('team', {}).get('name', '').lower()
                if tname and team_name.lower() in tname:
                    starters = entry.get('startXI', [])
                    if starters:
                        return [p.get('player', {}).get('name', '') for p in starters if isinstance(p, dict)]
    except:
        pass
    return None
