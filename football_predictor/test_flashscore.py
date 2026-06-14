"""Check if Flashscore works with curl_cffi"""
import os, re
os.environ['PYTHONIOENCODING'] = 'utf-8'
from curl_cffi import requests

r = requests.get(
    'https://www.flashscore.com/',
    impersonate='chrome120',
    timeout=15,
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    }
)
print(f"Flashscore homepage: Status {r.status_code}")
print(f"Length: {len(r.text)}")
if r.status_code == 200:
    matches = len(re.findall(r'event__match', r.text))
    teams = len(re.findall(r'participant__participantName', r.text))
    print(f"Match elements: {matches}")
    print(f"Team names found: {teams}")
    if matches > 0:
        print("FLASHSCORE IS ACCESSIBLE via curl_cffi!")
else:
    print(f"Response: {r.text[:200]}")
