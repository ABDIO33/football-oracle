"""Check raw odds JSON structure"""
import sqlite3, json

conn = sqlite3.connect('scrape_cache.db')

cur = conn.execute("SELECT odds_json FROM odds_upcoming WHERE home_team='France' AND away_team='Iraq'")
r = cur.fetchone()
if r:
    ojson = r[0]
    # Print first 2000 chars to see structure
    print(ojson[:2000])

conn.close()
