"""
weather.py — Weather data from open-meteo.com (free, no API key)
Supports both forecast (future) and archive (historical) dates.
"""

import os, json, time, sqlite3
from datetime import datetime
import urllib.request

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
_LAST_REQ = 0

def _rate_limit():
    global _LAST_REQ
    now = time.time()
    if now - _LAST_REQ < 1.0:
        time.sleep(1.0 - (now - _LAST_REQ))
    _LAST_REQ = time.time()

def _init_cache():
    conn = sqlite3.connect(DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS weather_cache (
            lat REAL, lon REAL, date TEXT,
            temp_max REAL, temp_min REAL, precip REAL,
            wind REAL, humidity REAL,
            PRIMARY KEY (lat, lon, date)
        )
    ''')
    conn.commit()
    return conn

def get_weather(lat, lon, date):
    conn = _init_cache()
    cur = conn.execute('SELECT temp_max, temp_min, precip, wind, humidity FROM weather_cache WHERE lat=? AND lon=? AND date=?',
                       (lat, lon, date))
    row = cur.fetchone()
    if row:
        conn.close()
        return {'temp_max_c': row[0], 'temp_min_c': row[1], 'precipitation_mm': row[2],
                'wind_speed_max': row[3], 'humidity_mean': row[4]}
    
    _rate_limit()
    try:
        dt = datetime.strptime(date, '%Y-%m-%d')
        is_future = dt >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if is_future:
            url = (f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}'
                   f'&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,relative_humidity_2m_mean'
                   f'&timezone=auto&start_date={date}&end_date={date}')
        else:
            url = (f'https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}'
                   f'&start_date={date}&end_date={date}'
                   f'&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,relative_humidity_2m_mean'
                   f'&timezone=auto')
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        r = urllib.request.urlopen(req, timeout=15)
        d = json.loads(r.read().decode())
        
        if 'daily' in d:
            day = d['daily']
            result = {
                'temp_max_c': day.get('temperature_2m_max', [None])[0],
                'temp_min_c': day.get('temperature_2m_min', [None])[0],
                'precipitation_mm': day.get('precipitation_sum', [None])[0],
                'wind_speed_max': day.get('wind_speed_10m_max', [None])[0],
                'humidity_mean': day.get('relative_humidity_2m_mean', [None])[0],
            }
            conn.execute('INSERT OR REPLACE INTO weather_cache VALUES (?,?,?,?,?,?,?,?)',
                         (lat, lon, date, result['temp_max_c'], result['temp_min_c'],
                          result['precipitation_mm'], result['wind_speed_max'], result['humidity_mean']))
            conn.commit()
            conn.close()
            return result
    except:
        pass
    conn.close()
    return None

if __name__ == '__main__':
    w = get_weather(53.483, -2.200, '2026-06-15')
    print(f'Manchester weather: {w}')
