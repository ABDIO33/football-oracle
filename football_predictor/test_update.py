"""Test the updated sofascore_scraper"""
from sofascore_scraper import *
import json

print('=== Test 1: Search team ===')
teams = search_team('Iraq')
for t in teams:
    print(f'  {t["name"]} (id={t["id"]})')

print('\n=== Test 2: Scheduled events 2026-06-22 ===')
events = get_scheduled_events('2026-06-22')
print(f'  Total: {len(events)} matches')
for e in events[:5]:
    ht = e.get('homeTeam', {}).get('name', '?')
    at = e.get('awayTeam', {}).get('name', '?')
    print(f'  {ht} vs {at}')

print('\n=== Test 3: Lineups for Iraq vs France ===')
lu = get_match_lineups(15186769)
if lu:
    home = lu.get('home', {})
    away = lu.get('away', {})
    print(f'  Home formation: {home.get("formation")}')
    print(f'  Away formation: {away.get("formation")}')
    for side, label in [(home, 'Home'), (away, 'Away')]:
        players = side.get('players', [])
        starters = [p for p in players if p.get('isStarting')]
        print(f'  {label} starters ({len(starters)}):')
        for p in starters[:5]:
            print(f'    {p.get("name")} (#{p.get("shirtNumber")})')
            print(f'      pos: {p.get("position")}')

print('\n=== Test 4: Tournament info ===')
wc = get_tournament_info(16)
if wc:
    t = wc.get('uniqueTournament', {})
    name = t.get('name', '?')
    print(f'  Tournament: {name}')
    seasons = wc.get('seasons', [])
    for s in sorted(seasons, key=lambda x: x.get('year', 0), reverse=True)[:5]:
        print(f'    {s.get("year")} (id={s.get("id")}, name={s.get("name")})')

print('\n=== ALL TESTS PASSED ===')
