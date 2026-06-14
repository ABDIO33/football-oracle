"""Find Understat API endpoints in JS"""
import requests, re

# Check league.min.js for API endpoints
url = 'https://understat.com/js/league.min.js?t=1765269520'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
print(f'Size: {len(r.text)} bytes')

# Find all URLs in the JS
urls = set(re.findall(r"https?://[^'\"]+", r.text))
for u in sorted(urls):
    print(f'  URL: {u}')

# Find all fetch/ajax calls
fetches = re.findall(r"\.(?:get|post|ajax|getJSON)\s*\(\s*'([^']+)'", r.text)
for f in fetches:
    print(f'  fetch/ajax: {f}')

# Find all strings containing "api" or "data"
api_refs = re.findall(r"'([^']*api[^']*)'", r.text, re.IGNORECASE)
for a in api_refs:
    print(f'  api ref: {a}')
