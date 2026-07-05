"""
fetch_weather_bulk.py — Parallel weather backfill from Open-Meteo
Uses yearly chunks + parallel workers to avoid rate limits
"""
import sys, os, json, time, sqlite3, urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def get_coords():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT DISTINCT ROUND(lat,4), ROUND(lon,4) FROM team_venue").fetchall()
    conn.close()
    return [(float(r[0]), float(r[1])) for r in rows]

def fetch_year(lat, lon, year):
    url = (f'https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}'
           f'&start_date={year}-01-01&end_date={year}-12-31'
           f'&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,relative_humidity_2m_mean'
           f'&timezone=auto')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            r = urllib.request.urlopen(req, timeout=30)
            return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            return None
    return None

def save_weather(data):
    daily = data.get('daily', {})
    dates = daily.get('time', [])
    if not dates:
        return 0
    conn = sqlite3.connect(DB)
    lat = data.get('latitude', 0)
    lon = data.get('longitude', 0)
    saved = 0
    for i, d in enumerate(dates):
        try:
            conn.execute("""INSERT OR REPLACE INTO venue_weather
                (date, lat, lon, temp_max, temp_min, precip, wind, humidity)
                VALUES (?,?,?,?,?,?,?,?)""",
                (d, lat, lon,
                 daily.get('temperature_2m_max', [None])[i],
                 daily.get('temperature_2m_min', [None])[i],
                 daily.get('precipitation_sum', [None])[i],
                 daily.get('wind_speed_10m_max', [None])[i],
                 daily.get('relative_humidity_2m_mean', [None])[i]))
            saved += 1
        except:
            pass
    conn.commit()
    conn.close()
    return saved

log('=' * 50)
log('PARALLEL WEATHER BACKFILL (yearly chunks)')
log('=' * 50)

coords = get_coords()
log(f'Found {len(coords)} coordinates')

now_year = datetime.now().year
total_saved = 0
done = 0
total_jobs = 0

tasks = []
for lat, lon in coords:
    for year in range(1993, now_year + 1):
        tasks.append((lat, lon, year))
total_jobs = len(tasks)
log(f'Total jobs: {total_jobs} ({len(coords)} coords x {now_year-1993+1} years)')

with ThreadPoolExecutor(max_workers=4) as ex:
    fut_map = {ex.submit(fetch_year, lat, lon, year): (lat, lon, year) for lat, lon, year in tasks}
    for f in as_completed(fut_map):
        lat, lon, year = fut_map[f]
        done += 1
        data = f.result()
        if data:
            saved = save_weather(data)
            total_saved += saved
        if done % 200 == 0:
            log(f'  [{done:,}/{total_jobs:,}] saved {total_saved:,} total')

log(f'\nDONE! Total: {total_saved:,} weather rows saved')
log(f'Jobs: {done:,}/{total_jobs:,}')
