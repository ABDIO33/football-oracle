"""
اختبار عملي لكل مصادر الـ xG
كلها بـ curl_cffi impersonate لمحاكاة المتصفح الحقيقي
"""
import time, json
from datetime import datetime
from curl_cffi import requests

RESULTS = []

def log(name, status, duration, data_points, error=''):
    r = {'source': name, 'status': status, 'duration_s': round(duration, 2), 'data_points': data_points, 'error': error[:100] if error else ''}
    RESULTS.append(r)
    icon = '[OK]' if status == 'OK' else '[FAIL]'
    print(f"  {icon} {name}: {duration:.1f}s | {data_points} pts | {error[:60] if error else ''}")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

def test_fbref_curl():
    print("\n[1] FBref - curl_cffi impersonate...")
    start = time.time()
    try:
        url = "https://fbref.com/en/squads/822bd0ba/Liverpool-Stats"
        r = requests.get(url, headers=HEADERS, impersonate="chrome", timeout=20)
        if r.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            xg_cells = soup.find_all('td', {'data-stat': 'xg'})
            log('FBref_cURL', 'OK', time.time()-start, len(xg_cells))
        else:
            log('FBref_cURL', 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('FBref_cURL', 'ERROR', time.time()-start, 0, str(e))

def test_fbref_pandas():
    print("\n[2] FBref - pandas read_html...")
    start = time.time()
    try:
        import pandas as pd
        url = "https://fbref.com/en/squads/822bd0ba/Liverpool-Stats"
        tables = pd.read_html(url)
        log('FBref_pandas', 'OK', time.time()-start, len(tables))
    except Exception as e:
        log('FBref_pandas', 'ERROR', time.time()-start, 0, str(e))

def test_understat():
    print("\n[3] Understat - understatapi...")
    start = time.time()
    try:
        from understatapi import UnderstatClient
        understat = UnderstatClient()
        league_data = understat.league(league="EPL").get_player_data(season="2025")
        log('Understat', 'OK', time.time()-start, len(league_data))
    except ImportError:
        log('Understat', 'NO_MODULE', time.time()-start, 0, 'pip install understatapi')
    except Exception as e:
        log('Understat', 'ERROR', time.time()-start, 0, str(e))

def test_sofascore_api():
    print("\n[4] Sofascore - undocumented API via curl_cffi...")
    start = time.time()
    try:
        url = "https://api.sofascore.com/api/v1/team/42"
        h = {**HEADERS, 'Accept': 'application/json', 'Referer': 'https://www.sofascore.com/', 'Origin': 'https://www.sofascore.com'}
        r = requests.get(url, headers=h, impersonate="chrome", timeout=15)
        if r.status_code == 200:
            data = r.json()
            log('SofaAPI', 'OK', time.time()-start, len(data))
        else:
            log('SofaAPI', 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('SofaAPI', 'ERROR', time.time()-start, 0, str(e))

def test_sofascore_nextdata():
    print("\n[5] Sofascore - __NEXT_DATA__ via curl_cffi...")
    start = time.time()
    try:
        url = "https://www.sofascore.com/team/football/42"
        r = requests.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        if r.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            if script:
                data = json.loads(script.string)
                log('Sofa_NEXT', 'OK', time.time()-start, len(data))
            else:
                log('Sofa_NEXT', 'NO_DATA', time.time()-start, 0, 'no __NEXT_DATA__')
        else:
            log('Sofa_NEXT', 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('Sofa_NEXT', 'ERROR', time.time()-start, 0, str(e))

def test_soccerdata():
    print("\n[6] soccerdata (FBref wrapper)...")
    start = time.time()
    try:
        import soccerdata as sd
        # 10 ماتشات من Premier League
        ws = sd.WhoScored(leagues="ENG-Premier League", seasons=2025)
        matches = ws.match_schedule(force_update=False)
        log('SoccerData', 'OK', time.time()-start, len(matches) if matches is not None else 0)
    except ImportError:
        log('SoccerData', 'NO_MODULE', time.time()-start, 0, 'pip install soccerdata')
    except Exception as e:
        log('SoccerData', 'ERROR', time.time()-start, 0, str(e))

if __name__ == '__main__':
    print("=" * 60)
    print("[TEST] اختبار مصادر الـ xG - كلها بـ curl_cffi")
    print(f"[DATE] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    test_fbref_curl()
    test_fbref_pandas()
    test_understat()
    test_sofascore_api()
    test_sofascore_nextdata()
    
    print("\n" + "=" * 60)
    print("[RESULTS] النتائج النهائية:")
    print("=" * 60)
    for r in RESULTS:
        icon = '[OK]' if r['status'] == 'OK' else '[FAIL]'
        print(f"  {icon} {r['source']}: {r['duration_s']}s | {r['data_points']} pts | {r['error']}")
    
    print("\n[SUMMARY] المصادر اللي تشتغل فعلا:")
    for r in RESULTS:
        if r['status'] == 'OK':
            print(f"  [OK] {r['source']}: {r['duration_s']}s - {r['data_points']} نقطه")
        else:
            print(f"  [FAIL] {r['source']}: {r['error'] or r['status']}")
