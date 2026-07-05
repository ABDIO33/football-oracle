"""Download ALL football-data.co.uk historical data (1993-2025 = 32 seasons)"""
import requests, zipfile, io, os, csv, sqlite3, sys, re, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

# Generate all 32 season codes: 9394, 9495, ..., 2425
seasons = []
for y in range(1993, 2025):  # 1993-94 to 2024-25
    yr1 = y % 100
    yr2 = yr1 + 1
    seasons.append(f'{yr1:02d}{yr2:02d}')
print(f'Downloading {len(seasons)} seasons: {seasons[0]} to {seasons[-1]}')

BASE = 'https://www.football-data.co.uk/mmz4281/{}/data.zip'
TDIR = os.path.join(os.path.dirname(__file__), 'fd_historical')
os.makedirs(TDIR, exist_ok=True)

downloaded = 0
for s, season_code in enumerate(seasons):
    url = BASE.format(season_code)
    zip_path = os.path.join(TDIR, f'{season_code}.zip')
    if os.path.exists(zip_path) and os.path.getsize(zip_path) > 1000:
        if s % 5 == 0:
            print(f'  [{s+1}/{len(seasons)}] {season_code} already cached ({os.path.getsize(zip_path)/1024:.0f}KB)')
        continue
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f'  [{season_code}] HTTP {r.status_code}')
            continue
        with open(zip_path, 'wb') as f:
            f.write(r.content)
        downloaded += 1
        print(f'  [{s+1}/{len(seasons)}] {season_code} downloaded ({len(r.content)/1024:.0f}KB)')
    except Exception as e:
        print(f'  [{season_code}] Error: {e}')
    time.sleep(0.3)

print(f'\nDownloaded {downloaded} new season archives to {TDIR}')
total_size = sum(os.path.getsize(os.path.join(TDIR, f)) for f in os.listdir(TDIR) if f.endswith('.zip')) / (1024*1024)
print(f'Total cache size: {total_size:.0f} MB')
