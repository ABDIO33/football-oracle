import re, json, time, os, sqlite3
try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

BASE = 'https://www.whoscored.com'
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

TEAM_IDS = {
    'Arsenal': 13, 'Aston Villa': 47, 'Bournemouth': 204, 'Brentford': 133,
    'Brighton & Hove Albion': 166, 'Chelsea': 6, 'Crystal Palace': 19,
    'Everton': 26, 'Fulham': 108, 'Ipswich Town': 73, 'Leicester City': 44,
    'Liverpool': 8, 'Manchester City': 4, 'Manchester United': 11,
    'Newcastle United': 5, 'Nottingham Forest': 80, 'Southampton': 18,
    'Tottenham Hotspur': 12, 'West Ham United': 25, 'Wolverhampton': 43,
    'Barcelona': 28, 'Real Madrid': 37, 'Atletico Madrid': 7,
    'Bayern Munich': 31, 'Borussia Dortmund': 53, 'Inter Milan': 1,
    'AC Milan': 2, 'Juventus': 3, 'Paris Saint Germain': 9,
    'Marseille': 38, 'Roma': 14, 'Napoli': 16, 'Benfica': 15,
    'Porto': 36, 'Sporting CP': 42, 'Ajax': 20, 'PSV': 48,
}

def _headers():
    return {
        'x-requested-with': '721637',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.whoscored.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    }

def _find_match_id(home_team, away_team):
    """Find a WhoScored match ID for a given matchup."""
    hid = TEAM_IDS.get(home_team)
    aid = TEAM_IDS.get(away_team)
    if not hid or not aid: return None
    
    url = f'{BASE}/Teams/{hid}/Show/{home_team.replace(" ","-")}'
    try:
        r = curl_requests.get(url, impersonate='chrome120', headers=_headers(), timeout=10)
        if r.status_code != 200: return None
        text = r.content.decode('utf-8-sig')
        matches = re.findall(r'MatchId=(\d+).*?homeTeamId="?(\d+)"?.*?awayTeamId="?(\d+)"?', text, re.DOTALL)
        for mid, h, a in matches:
            if int(h) == hid and int(a) == aid: return int(mid)
    except: pass
    return None

def get_match_data(home_team, away_team):
    """Extract match data from WhoScored Show page via curl_cffi bypass."""
    if curl_requests is None: return None
    
    mid = _find_match_id(home_team, away_team)
    if not mid: return None
    
    url = f'{BASE}/Matches/{mid}/Show'
    try:
        r = curl_requests.get(url, impersonate='chrome120', headers=_headers(), timeout=15)
        if r.status_code != 200: return None
        text = r.content.decode('utf-8-sig')
        
        result = {'source': 'whoscored', 'match_id': mid}
        
        # Extract match header
        hdr = re.search(r"matchheader'?\s*=\s*\{[^}]*input\s*:\s*\[([^\]]+)\]", text)
        if hdr:
            parts = [p.strip().strip("'") for p in hdr.group(1).split(',')]
            if len(parts) >= 10:
                result['home_team'] = parts[2]
                result['away_team'] = parts[3]
                result['date'] = parts[4]
                result['status'] = parts[7]
                result['score'] = parts[9].strip("'")
                result['half_time'] = parts[8].strip("'")
        
        # Extract match prediction JSON
        pred = re.search(r"JSON\.parse\('([^']+)'\)", text)
        if pred:
            try:
                raw = pred.group(1).replace("\\'", "'").replace('\\"', '"').replace('\\/', '/')
                result['match_json'] = json.loads(raw)
            except: pass
        
        # Extract standings
        args = re.search(r"require\.config\.params\[\"args\"\]\s*=\s*(\{)", text)
        if args:
            # Find the closing brace with proper nesting
            stack = 0
            start = args.start(1)
            for i in range(start, len(text)):
                if text[i] == '{': stack += 1
                elif text[i] == '}': stack -= 1
                if stack == 0:
                    try:
                        result['args_raw'] = text[start:i+1]
                    except: pass
                    break
        
        # Extract recent form
        form_matches = re.findall(
            r'\{[^}]*?"homeTeamName":"[^"]+","awayTeamName":"[^"]+","homeTeamId":(\d+),"awayTeamId":(\d+)[^}]*?"Score":"([^"]+)"[^}]*?\}',
            text
        )
        result['recent_matches'] = form_matches[:10]
        
        return result
    except:
        return None

def get_live_team_data_full(team_name):
    """Interface for prediction_engine - limited data from WhoScored headers."""
    return None

if __name__ == '__main__':
    d = get_match_data('Liverpool', 'Manchester City')
    if d: print(json.dumps(d, indent=2, default=str)[:1000])
    else: print('No data')
