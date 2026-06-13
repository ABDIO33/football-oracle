import sqlite3, os, json, numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

_EVAL_DB = os.path.join(os.path.dirname(__file__), 'evaluation.db')

def _load_data(min_samples=10):
    try:
        conn = sqlite3.connect(_EVAL_DB)
        cur = conn.execute(
            "SELECT prediction_json, actual_result FROM eval_predictions WHERE status='resolved'"
        )
        rows = cur.fetchall()
        conn.close()
    except:
        return None
    if len(rows) < min_samples:
        return None
    records = []
    for row in rows:
        pred = json.loads(row[0])
        records.append({
            'hp': float(pred.get('home_win_prob', 33.33)) / 100,
            'dp': float(pred.get('draw_prob', 33.33)) / 100,
            'ap': float(pred.get('away_win_prob', 33.33)) / 100,
            'actual': row[1]
        })
    return records

def _bin_calibration(records, n_bins=10):
    bins = defaultdict(lambda: {'count': 0, 'h_wins': 0, 'd_wins': 0, 'a_wins': 0})
    for r in records:
        for outcome, prob_key in [('H', 'hp'), ('D', 'dp'), ('A', 'ap')]:
            pct = int(r[prob_key] * 100 / (100 / n_bins)) * (100 / n_bins)
            bin_key = f"{outcome}_{pct:.0f}"
            bins[bin_key]['count'] += 1
            if r['actual'] == outcome:
                bins[bin_key][f'{outcome.lower()}_wins'] += 1
    cal = {'H': {}, 'D': {}, 'A': {}}
    for outcome in ['H', 'D', 'A']:
        pts = []
        for pct in range(0, 100, int(100 / n_bins)):
            bk = f"{outcome}_{pct}"
            b = bins.get(bk, {'count': 0})
            if b['count'] >= 2:
                actual_rate = b[f'{outcome.lower()}_wins'] / b['count']
                pts.append({'bin': pct, 'predicted': pct/100, 'actual': actual_rate, 'count': b['count']})
        cal[outcome] = pts
    return cal

def _fit_isotonic(records):
    try:
        from sklearn.isotonic import IsotonicRegression
    except ImportError:
        return None
    models = {}
    for outcome, prob_key in [('H', 'hp'), ('D', 'dp'), ('A', 'ap')]:
        X = np.array([r[prob_key] for r in records])
        y = np.array([1.0 if r['actual'] == outcome else 0.0 for r in records])
        model = IsotonicRegression(out_of_bounds='clip')
        model.fit(X, y)
        models[outcome] = model
    return models

def calibrate_probabilities(home_prob, draw_prob, away_prob, method='isotonic'):
    if not hasattr(calibrate_probabilities, '_models'):
        calibrate_probabilities._models = None
    if calibrate_probabilities._models is None:
        calibrate_probabilities._models = _fit_isotonic(_load_data() or [])
        if calibrate_probabilities._models is None:
            calibrate_probabilities._models = False
    if calibrate_probabilities._models is False:
        return home_prob, draw_prob, away_prob
    try:
        hp = float(calibrate_probabilities._models['H'].predict([[home_prob/100]])[0])
        dp = float(calibrate_probabilities._models['D'].predict([[draw_prob/100]])[0])
        ap = float(calibrate_probabilities._models['A'].predict([[away_prob/100]])[0])
        total = hp + dp + ap
        if total > 0:
            hp, dp, ap = hp/total*100, dp/total*100, ap/total*100
        return round(hp, 2), round(dp, 2), round(ap, 2)
    except:
        return home_prob, draw_prob, away_prob

def calibrate_bin(home_prob, draw_prob, away_prob):
    records = _load_data()
    if not records:
        return home_prob, draw_prob, away_prob
    cal = _bin_calibration(records, n_bins=10)
    def _adjust(prob, outcome):
        for entry in cal[outcome]:
            if abs(prob - entry['predicted']) <= 0.05:
                return entry['actual'] * 100
        return prob
    hp = _adjust(home_prob, 'H')
    dp = _adjust(draw_prob, 'D')
    ap = _adjust(away_prob, 'A')
    total = hp + dp + ap
    if total > 0:
        hp, dp, ap = hp/total*100, dp/total*100, ap/total*100
    return round(hp, 2), round(dp, 2), round(ap, 2)

def calibration_report():
    records = _load_data()
    if not records:
        return "Not enough data (<10 resolved predictions)"
    cal = _bin_calibration(records, n_bins=5)
    lines = ["📊 Calibration Report"]
    lines.append(f"  Total resolved: {len(records)}")
    for outcome, label in [('H', 'Home'), ('D', 'Draw'), ('A', 'Away')]:
        pts = cal[outcome]
        if not pts:
            continue
        mae = sum(abs(p['predicted'] - p['actual']) for p in pts) / len(pts)
        lines.append(f"  {label}: MAE={mae:.3f}")
        for p in pts:
            lines.append(f"    Pred {p['predicted']:.0%} → Actual {p['actual']:.0%} (n={p['count']})")
    return "\n".join(lines)

if __name__ == '__main__':
    print(calibration_report())
