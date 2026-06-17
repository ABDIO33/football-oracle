from flask import Flask, render_template, request, jsonify, session
import os
import time
import json
import threading
from datetime import datetime, timedelta
from database import init_db
from prediction_engine import analyze_match_deep, get_daily_matches, rate_matches
import evaluation
from url_parser import parse_match_url

# تحميل المفاتيح من .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

init_db()
evaluation.init_evaluation_db()

_analysis_cache = {}
_last_analysis_time = {}

BEST_MATCHES = {
    'matches': [],
    'last_updated': None
}

def update_best_matches():
    while True:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            matches = get_daily_matches(today)
            if matches:
                best = rate_matches(matches)
                BEST_MATCHES['matches'] = best
                BEST_MATCHES['last_updated'] = datetime.now().isoformat()
        except Exception as e:
            print(f"Error updating matches: {e}")
        time.sleep(1800)

def _thinking_delay(seconds=3):
    time.sleep(seconds)

@app.route('/')
def index():
    best = BEST_MATCHES['matches'] if BEST_MATCHES['matches'] else []
    last_upd = BEST_MATCHES['last_updated']
    if not last_upd:
        last_upd = datetime.now().isoformat()
    return render_template('index.html', best_matches=best, last_updated=last_upd)

@app.route('/analyze_url', methods=['POST'])
def analyze_url():
    url = request.form.get('match_url', '').strip()
    if not url:
        return render_template('result.html', error="Please enter a valid URL")
    parsed = parse_match_url(url)
    if not parsed:
        return render_template('result.html', error="Could not parse this URL. Please enter team names manually.")
    home_team = parsed.get('home_team', '')
    away_team = parsed.get('away_team', '')
    if not home_team or not away_team:
        return render_template('result.html', error="Could not identify teams from URL. Try manual entry.")
    cache_key = f"{home_team}|{away_team}"
    now = time.time()
    if cache_key in _analysis_cache and (now - _last_analysis_time.get(cache_key, 0)) < 60:
        prediction = _analysis_cache[cache_key]
    else:
        _thinking_delay(1)
        prediction = analyze_match_deep(home_team, away_team, use_direct_model=True)
        _analysis_cache[cache_key] = prediction
        _last_analysis_time[cache_key] = now
    return render_template('result.html',
                         home_team=home_team,
                         away_team=away_team,
                         prediction=prediction,
                         source=parsed.get('source', 'manual'))

@app.route('/predict', methods=['POST'])
def predict():
    home_team = request.form.get('home_team', '').strip()
    away_team = request.form.get('away_team', '').strip()
    if not home_team or not away_team:
        return render_template('result.html', error="Please enter both team names")
    neutral_venue = request.form.get('neutralVenue') == 'on'
    cache_key = f"{home_team}|{away_team}|{neutral_venue}"
    now = time.time()
    if cache_key in _analysis_cache and (now - _last_analysis_time.get(cache_key, 0)) < 60:
        prediction = _analysis_cache[cache_key]
    else:
        _thinking_delay(1)
        prediction = analyze_match_deep(home_team, away_team, neutral_venue=neutral_venue, use_direct_model=True)
        _analysis_cache[cache_key] = prediction
        _last_analysis_time[cache_key] = now
    return render_template('result.html',
                         home_team=home_team,
                         away_team=away_team,
                         prediction=prediction,
                         source='manual')

@app.route('/analyze_selected', methods=['POST'])
def analyze_selected():
    data = request.get_json()
    matches = data.get('matches', [])
    results = []
    for m in matches:
        home = m.get('home_team', '')
        away = m.get('away_team', '')
        if home and away:
            pred = analyze_match_deep(home, away, use_direct_model=True)
            results.append({
                'home_team': home,
                'away_team': away,
                'prediction': pred
            })
    return jsonify({'results': results})

@app.route('/update_ticket', methods=['POST'])
def update_ticket():
    threading.Thread(target=update_best_matches, daemon=False).start()
    return jsonify({'status': 'updating', 'message': 'Updating best matches...'})

@app.route('/api/ticket')
def api_ticket():
    return jsonify(BEST_MATCHES)

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.get_json()
    home_team = data.get('homeTeam', '').strip()
    away_team = data.get('awayTeam', '').strip()
    match_url = data.get('matchUrl', '').strip()
    neutral_venue = data.get('neutralVenue', False)
    if match_url:
        parsed = parse_match_url(match_url)
        if parsed:
            home_team = parsed.get('home_team', home_team)
            away_team = parsed.get('away_team', away_team)
    if not home_team or not away_team:
        return jsonify({'error': 'Team names required'}), 400
    cache_key = f"{home_team}|{away_team}|{neutral_venue}"
    now = time.time()
    if cache_key in _analysis_cache and (now - _last_analysis_time.get(cache_key, 0)) < 60:
        pred = _analysis_cache[cache_key]
    else:
        time.sleep(2)
        pred = analyze_match_deep(home_team, away_team, neutral_venue=neutral_venue, use_direct_model=True)
        _analysis_cache[cache_key] = pred
        _last_analysis_time[cache_key] = now
    top_3 = pred.get('top_scores', [])[:3]
    hw = float(pred['home_win_prob'])
    dw = float(pred['draw_prob'])
    aw = float(pred['away_win_prob'])
    winner = home_team if hw > dw and hw > aw else (away_team if aw > dw and aw > hw else 'Draw')
    btts_yes = 1 if float(pred['btts_yes']) > float(pred['btts_no']) else 0
    over_yes = 1 if float(pred['over_2_5']) > float(pred['under_2_5']) else 0
    risk = float(max(hw, dw, aw))
    if risk > 55:
        risk_level = 'Low'
        risk_pct = 25
    elif risk > 45:
        risk_level = 'Medium'
        risk_pct = 50
    else:
        risk_level = 'High'
        risk_pct = 75
    final_score = pred['most_likely_score']
    parts = final_score.split('-')
    fh = f"{parts[0]}-0" if parts else "0-0"
    sh = f"0-{parts[1]}" if len(parts) > 1 else "0-0"
    return jsonify({
        'home_team': home_team,
        'away_team': away_team,
        'first_half': fh,
        'second_half': sh,
        'final_score': final_score,
        'confidence': round(float(max(hw, dw, aw)), 0),
        'top_3_scores': [{'score': s['score'], 'prob': s['prob']} for s in top_3],
        'ai_analysis': f"AI analysis based on Poisson-Dixon-Coles model. {pred['analysis']['recommendation']}. "
                       f"Exact score {pred['most_likely_score']} with {pred['exact_score_prob']}% probability. "
                       f"Home form: {pred['analysis']['home_form_rating']}/100, Away form: {pred['analysis']['away_form_rating']}/100.",
        'safe_bet': pred['analysis']['best_bet_type'],
        'risk_percent': risk_pct,
        'risk_level': risk_level,
        'win_probability': {'home': hw, 'draw': dw, 'away': aw},
        'btts': btts_yes,
        'btts_probability': round(float(pred['btts_yes']) * 100, 0),
        'over_2_5': over_yes,
        'over_2_5_prob': round(float(pred['over_2_5']) * 100, 0)
    })

def background_updater():
    time.sleep(5)
    update_best_matches()

if __name__ == '__main__':
    threading.Thread(target=background_updater, daemon=True).start()
    evaluation.start_evaluation_thread()
    evaluation.print_metrics_report()
    print("\n" + "="*60)
    print("   Score Exact 100 - AI Football Prediction System")
    print("   Running on http://127.0.0.1:5000")
    print("="*60 + "\n")
    app.run(debug=True, port=5000, threaded=True, use_reloader=False)
