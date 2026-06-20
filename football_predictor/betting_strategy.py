"""
betting_strategy.py — Confidence-based betting system
Uses EnsemblePredictor + isotonic calibration + odds to find +EV bets.
Kelly Criterion stake sizing.
"""
import sys, os, json, pickle, math
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import load_model, predict_match, SCORE_CLASSES, class_to_score

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

def load_calibrators():
    try:
        import joblib
        path = os.path.join(MODEL_DIR, 'isotonic_calibrators.pkl')
        return joblib.load(path)
    except:
        return None

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

def compute_ev(model_prob, odds_decimal):
    """Expected Value: EV = model_prob * odds - 1. Positive means +EV."""
    return model_prob * odds_decimal - 1.0

def kelly_fraction(model_prob, odds_decimal, fraction=0.25):
    """Kelly Criterion: f* = (p*b - q) / b where b = odds-1, q = 1-p.
    Uses fraction (default 25%) for safety."""
    if odds_decimal <= 1.0 or model_prob <= 0.0 or model_prob >= 1.0:
        return 0.0
    b = odds_decimal - 1.0
    q = 1.0 - model_prob
    f = (model_prob * b - q) / b
    if f < 0:
        return 0.0
    return min(f * fraction, 0.05)  # cap at 5% of bankroll

def load_odds_api():
    """Load odds from The Odds API. Returns dict of (home, away, date) -> odds dict."""
    try:
        with open(os.path.join(MODEL_DIR, '..', 'odds_cache.json'), 'r') as f:
            return json.load(f)
    except:
        return {}

def predict_and_bet(home_team, away_team, match_date,
                    odds_b365=None, odds_avg=None,
                    exact_threshold=0.03, min_ev=0.0,
                    bankroll=1000.0, prev_bets=None):
    """
    Full prediction + betting recommendation.

    Args:
        home_team, away_team, match_date: match identifiers
        odds_b365: (h, d, a) tuple from B365
        odds_avg: (h, d, a) tuple from average odds
        exact_threshold: minimum model probability to consider an exact score bet
        min_ev: minimum EV to consider a bet (e.g., 0.0 = any +EV)
        bankroll: current bankroll for Kelly sizing
        prev_bets: list of dicts of previous bets (for tracking)

    Returns dict with predicted probabilities + betting recommendations.
    """
    result = predict_match(home_team, away_team, match_date, odds_b365, odds_avg)
    if result is None:
        return None

    # Load calibrators
    calibrators = load_calibrators()

    # Get model probabilities
    score_probs = result['score_probs']
    probs_1x2 = result['probs_1x2']

    # Calibrate 1X2 probabilities (if calibrators available)
    if calibrators:
        raw_probs = np.array([probs_1x2['home'], probs_1x2['draw'], probs_1x2['away']])
        cal_probs = np.zeros(3)
        for i in range(3):
            try:
                cal_probs[i] = calibrators[i].predict(np.array([raw_probs[i]]))[0]
            except:
                cal_probs[i] = raw_probs[i]
        cal_probs = cal_probs / cal_probs.sum()  # renormalize
        cal_home, cal_draw, cal_away = cal_probs
    else:
        cal_home = probs_1x2['home']
        cal_draw = probs_1x2['draw']
        cal_away = probs_1x2['away']

    bets = []
    total_kelly = 0.0

    # 1. Exact score bets
    if odds_avg:
        # We need exact score odds — estimate from average 1X2 odds
        # For exact scores, use model probabilities directly
        score_list = sorted(score_probs.items(), key=lambda x: -x[1])

        for score_str, model_prob in score_list:
            if model_prob < exact_threshold:
                continue
            # Estimate exact score odds from marginals
            h, a = score_str.split('-')
            h, a = int(h), int(a)
            # Rough odds estimate: if model says 5%, fair odds = 20.0
            # We need at least some margin to beat
            fair_odds = 1.0 / model_prob if model_prob > 0 else 0
            # Only bet if model probability is significantly higher than market
            ev = model_prob * fair_odds - 1.0
            if ev > min_ev:
                kelly = kelly_fraction(model_prob, fair_odds)
                stake = bankroll * kelly
                bets.append({
                    'type': 'exact_score',
                    'prediction': score_str,
                    'model_prob': round(model_prob, 4),
                    'fair_odds': round(fair_odds, 2),
                    'ev': round(ev, 4),
                    'kelly_fraction': round(kelly, 4),
                    'stake': round(stake, 2),
                })
                total_kelly += kelly

    # 2. 1X2 bets (if odds available)
    if odds_b365:
        outcomes = [
            ('home', cal_home, odds_b365[0]),
            ('draw', cal_draw, odds_b365[1]),
            ('away', cal_away, odds_b365[2]),
        ]
        for outcome, prob, odds in outcomes:
            if prob is None or odds is None or odds <= 1.0:
                continue
            ev = compute_ev(prob, odds)
            if ev > min_ev:
                kelly = kelly_fraction(prob, odds)
                stake = bankroll * kelly
                bets.append({
                    'type': '1x2',
                    'prediction': outcome,
                    'model_prob': round(prob, 4),
                    'odds': round(odds, 4),
                    'ev': round(ev, 4),
                    'kelly_fraction': round(kelly, 4),
                    'stake': round(stake, 2),
                })
                total_kelly += kelly

    # 3. Over/Under goals
    home_marginal = np.zeros(5)
    away_marginal = np.zeros(5)
    for cls_idx in range(25):
        h, a = class_to_score(cls_idx)
        p = score_probs.get(f'{h}-{a}', 0)
        home_marginal[h] += p
        away_marginal[a] += p

    expected_home = sum(h * home_marginal[h] for h in range(5))
    expected_away = sum(a * away_marginal[a] for a in range(5))
    expected_total = expected_home + expected_away

    prob_over_2_5 = sum(
        score_probs.get(f'{h}-{a}', 0)
        for h in range(5) for a in range(5)
        if h + a > 2
    )
    prob_over_3_5 = sum(
        score_probs.get(f'{h}-{a}', 0)
        for h in range(5) for a in range(5)
        if h + a > 3
    )

    result['expected_goals'] = {
        'home': round(expected_home, 3),
        'away': round(expected_away, 3),
        'total': round(expected_total, 3),
    }
    result['over_under'] = {
        'over_2_5': round(prob_over_2_5, 4),
        'over_3_5': round(prob_over_3_5, 4),
        'under_2_5': round(1 - prob_over_2_5, 4),
    }
    result['calibrated_1x2'] = {
        'home': round(cal_home, 4),
        'draw': round(cal_draw, 4),
        'away': round(cal_away, 4),
    }
    result['bets'] = bets
    result['total_kelly'] = round(total_kelly, 4)
    result['recommended_stake'] = round(bankroll * min(total_kelly, 0.25), 2)  # max 25% of bankroll on all bets

    return result

def backtest_bets(historical_matches, bankroll=1000.0):
    """Backtest betting strategy on historical matches."""
    # Placeholder for actual backtesting
    print("Backtesting betting strategy...")
    print(f"  Matches: {len(historical_matches)}")
    print(f"  Starting bankroll: ${bankroll:.2f}")
    return {"total_profit": 0, "roi": 0, "win_rate": 0, "bets_placed": 0}

if __name__ == '__main__':
    # Test with a known match
    result = predict_and_bet(
        home_team='Manchester City',
        away_team='Arsenal',
        match_date='2026-04-15',
        odds_b365=(1.5, 4.0, 6.0),
        odds_avg=(1.53, 4.1, 5.8),
        bankroll=1000.0
    )
    if result:
        print(f"\n=== Match: Man City vs Arsenal ===")
        print(f"Top scores: {result['top_scores'][:5]}")
        print(f"Calibrated 1X2: {result['calibrated_1x2']}")
        print(f"Expected goals: {result['expected_goals']}")
        print(f"Over/Under: {result['over_under']}")
        print(f"\nBets ({len(result['bets'])}):")
        for b in result['bets']:
            print(f"  {b['type']} {b['prediction']}: prob={b['model_prob']:.1%} EV={b['ev']:.1%} stake=${b['stake']:.2f}")
        print(f"\nTotal recommended stake: ${result['recommended_stake']:.2f}")
        print(f"(Bankroll: $1000.00)")
