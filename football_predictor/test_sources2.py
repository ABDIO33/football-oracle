"""
اختبار إضافي: طرق بديلة لـ FBref و Sofascore
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

H = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# 1. FBref عبر صفحة المباريات مباشرة (ممكن تكون مسموحة)
def test_fbref_matches():
    print("\n[1] FBref - match schedule (lighter page)...")
    start = time.time()
    try:
        url = "https://fbref.com/en/comps/9/2025-2026/schedule/2025-2026-Premier-League-Schedule"
        r = requests.get(url, headers=H, impersonate="chrome", timeout=20)
        if r.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table')
            log('FBref_schedule', 'OK', time.time()-start, len(tables))
        else:
            log('FBref_schedule', 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('FBref_schedule', 'ERROR', time.time()-start, 0, str(e))

# 2. Sofascore API مع إضافة cookies من متصفح حقيقي
def test_sofascore_api2():
    print("\n[2] Sofascore API - curl_cffi + chrome120 impersonate...")
    start = time.time()
    try:
        url = "https://api.sofascore.com/api/v1/team/42"
        h = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.sofascore.com/',
            'Origin': 'https://www.sofascore.com',
        }
        r = requests.get(url, headers=h, impersonate="chrome120", timeout=15)
        if r.status_code == 200:
            log('SofaAPI_v2', 'OK', time.time()-start, len(r.json()))
        else:
            log('SofaAPI_v2', 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('SofaAPI_v2', 'ERROR', time.time()-start, 0, str(e))

# 3. Sofascore - team seasons endpoint
def test_sofascore_seasons():
    print("\n[3] Sofascore - team/seasons endpoint...")
    start = time.time()
    try:
        url = "https://api.sofascore.com/api/v1/team/42/seasons"
        h = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://www.sofascore.com/'}
        r = requests.get(url, headers=h, impersonate="chrome", timeout=15)
        log('Sofa_seasons', 'OK' if r.status_code == 200 else 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('Sofa_seasons', 'ERROR', time.time()-start, 0, str(e))

# 4. Understat: تحت المجهر - هل يعطينا xG لكل فريق؟
def test_understat_xg():
    print("\n[4] Understat - xG لكل فريق في البريميرليغ...")
    start = time.time()
    try:
        from understatapi import UnderstatClient
        understat = UnderstatClient()
        teams = understat.league(league="EPL").get_team_data(season="2025")
        xg_data = []
        for team_name, team_info in teams.items():
            if isinstance(team_info, dict) and 'xG' in team_info:
                xg_data.append((team_name, team_info['xG']))
        log('Understat_xG', 'OK', time.time()-start, len(xg_data))
    except Exception as e:
        log('Understat_xG', 'ERROR', time.time()-start, 0, str(e))

# 5. تحت المجهر: هل نقدر نجيب xG من صفحة Understat team؟
def test_understat_team():
    print("\n[5] Understat - direct team page...")
    start = time.time()
    try:
        url = "https://understat.com/team/Liverpool/2025"
        r = requests.get(url, headers=H, impersonate="chrome", timeout=15)
        if r.status_code == 200:
            import re
            # Understat يخلي الـ JSON داخل <script>
            matches = re.findall(r'JSON\.parse\(\'(.+?)\'\)', r.text)
            log('Understat_direct', 'OK', time.time()-start, len(matches))
        else:
            log('Understat_direct', 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('Understat_direct', 'ERROR', time.time()-start, 0, str(e))

# 6. FBref عبر curl_cffi مع chrome120 بدل chrome
def test_fbref_curl2():
    print("\n[6] FBref - curl_cffi chrome120 impersonate...")
    start = time.time()
    try:
        url = "https://fbref.com/en/squads/822bd0ba/Liverpool-Stats"
        r = requests.get(url, headers=H, impersonate="chrome120", timeout=20)
        log('FBref_cURL2', 'OK' if r.status_code == 200 else 'BLOCKED', time.time()-start, 0, f'HTTP {r.status_code}')
    except Exception as e:
        log('FBref_cURL2', 'ERROR', time.time()-start, 0, str(e))

if __name__ == '__main__':
    print("=" * 60)
    print("[TEST ROUND 2] طرق اضافية لاختراق المصادر")
    print(f"[DATE] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    test_sofascore_api2()
    test_sofascore_seasons()
    test_understat_xg()
    test_understat_team()
    test_fbref_matches()
    test_fbref_curl2()
    
    print("\n" + "=" * 60)
    print("[RESULTS]")
    print("=" * 60)
    for r in RESULTS:
        icon = '[OK]' if r['status'] == 'OK' else '[FAIL]'
        print(f"  {icon} {r['source']}: {r['duration_s']}s | {r['data_points']} pts | {r['error']}")
    
    print("\n[VERDICT] ماذا نستخدم:")
    working = [r for r in RESULTS if r['status'] == 'OK']
    failed = [r for r in RESULTS if r['status'] != 'OK']
    if working:
        for r in working:
            print(f"  [USE] {r['source']}: {r['duration_s']}s - {r['data_points']} نقاط")
    print(f"  [BLOCKED] {len(failed)} مصادر")
