import sys, os
sys.path.insert(0, 'C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor')

from dotenv import load_dotenv
load_dotenv()

from prediction_engine import (
    get_club_elo, get_market_probabilities, get_team_stats, analyze_match_deep
)

tests = [
    ("Real Madrid", "Barcelona"),
    ("Bayern Munich", "Borussia Dortmund"),
    ("Manchester City", "Crystal Palace"),
]

for home, away in tests:
    print(f"\n{'='*60}")
    print(f"  {home} vs {away}")
    print(f"{'='*60}")

    elo_h = get_club_elo(home)
    elo_a = get_club_elo(away)
    print(f"\n  ClubElo: {home}={elo_h}, {away}={elo_a}")

    stats_h = get_team_stats(home)
    stats_a = get_team_stats(away)
    print(f"  Stats: {home} gs={stats_h.get('goals_scored_avg')} gc={stats_h.get('goals_conceded_avg')} elo={stats_h.get('elo')} src={stats_h.get('elo_source')}")
    print(f"  Stats: {away} gs={stats_a.get('goals_scored_avg')} gc={stats_a.get('goals_conceded_avg')} elo={stats_a.get('elo')} src={stats_a.get('elo_source')}")

    pred = analyze_match_deep(home, away)
    print(f"\n  Score: {pred['most_likely_score']}  conf: {pred['analysis']['confidence']}")
    print(f"  H: {pred['home_win_prob']}%  D: {pred['draw_prob']}%  A: {pred['away_win_prob']}%")
    print(f"  Top: {[s['score'] for s in pred.get('top_scores', [])[:3]]}")
    print(f"  Best: {pred['analysis']['best_bet_type']}")
    print(f"  Market odds: {pred.get('market_available', 'N/A')}")
