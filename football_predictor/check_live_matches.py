"""Fetch lineups and live data for today's betting matches"""
from sofascore_scraper import get_match_lineups, get_match_details, get_match_statistics
import json
from datetime import datetime

matches = {
    15186769: 'France vs Iraq (17:00) - IN PROGRESS',
    15186770: 'Norway vs Senegal (20:00)',
    15186740: 'Jordan vs Algeria (23:00)',
}

for mid, label in matches.items():
    print(f'\n{"="*60}')
    print(f'  {label} (id={mid})')
    print(f'{"="*60}')
    
    # Match details
    details = get_match_details(mid)
    if details:
        ev = details.get('event', {})
        ht = ev.get('homeTeam', {}).get('name', '?')
        at = ev.get('awayTeam', {}).get('name', '?')
        hs = ev.get('homeScore', {}).get('display', 0)
        as_ = ev.get('awayScore', {}).get('display', 0)
        status = ev.get('status', {}).get('type', '?')
        start = ev.get('startTimestamp', 0)
        dt = datetime.fromtimestamp(start) if start else '?'
        minute = ev.get('time', {}).get('current', '')
        print(f'  Score: {ht} {hs} - {as_} {at}')
        print(f'  Status: {status} (minute: {minute})')
        print(f'  Time: {dt}')
        
        tournament = ev.get('tournament', {}).get('name', '?')
        print(f'  Tournament: {tournament}')
    
    # Lineups
    lineups = get_match_lineups(mid)
    if lineups:
        home = lineups.get('home', {})
        away = lineups.get('away', {})
        hf = home.get('formation', '?')
        af = away.get('formation', '?')
        confirmed = '(confirmed)' if lineups.get('confirmed') else '(expected)'
        print(f'  Formations: {hf} vs {af} {confirmed}')
        
        for side, name, label in [(home, ht, 'HOME'), (away, at, 'AWAY')]:
            players = side.get('players', [])
            starters = [p for p in players if not p.get('substitute')]
            print(f'  {label} ({name}, {len(starters)} starters):')
            for p in starters[:11]:
                p_name = p.get('player', {}).get('name', '?')
                p_pos = p.get('position', '?')
                p_shirt = p.get('shirtNumber', '')
                p_rate = p.get('rating', '')
                rate_str = f' rating={p_rate:.1f}' if isinstance(p_rate, (int, float)) else ''
                print(f'    {p_shirt} {p_name} ({p_pos}){rate_str}')
    else:
        print(f'  No lineups available yet')

print(f'\n{"="*60}')
print('  DONE')
print(f'{"="*60}')
