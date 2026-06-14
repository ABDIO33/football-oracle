"""Deep analyze homepage HTML for embedded data"""
import os, json, re
os.environ['PYTHONIOENCODING'] = 'utf-8'
from curl_cffi import requests

r = requests.get('https://www.sofascore.com/', impersonate='chrome120', timeout=15, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
})

html = r.text
print(f"Total size: {len(html)} bytes")

# Search for any JSON data with team names (format: "name":"TeamName")
team_names = re.findall(r'"name":"([A-Z][^"]{2,30})"', html)
team_names = [t for t in team_names if not re.match(r'^[A-Z\s/]+$', t) and len(t) > 2]
print(f"\nPotential team names found: {len(team_names)}")
for t in team_names[:20]:
    print(f"  {t}")

# Search for match-like patterns
match_patterns = re.findall(r'"homeTeam":\{[^}]{10,200}\}', html)
print(f"\nMatch patterns found: {len(match_patterns)}")

# Search for events arrays
event_arrays = re.findall(r'[eE]vents["\']?\s*:\s*\[', html)
print(f"Events arrays: {len(event_arrays)}")

# Check for any script with JSON content
script_contents = re.findall(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"\n__NEXT_DATA__ scripts: {len(script_contents)}")
if script_contents:
    d = json.loads(script_contents[0])
    pp = d.get('props', {}).get('pageProps', {})
    print(f"Keys in pageProps: {list(pp.keys())}")

# Check for other data scripts
other_scripts = re.findall(r'<script[^>]*>(window\.__[^=]+=)', html)
print(f"\nWindow data assignments: {len(other_scripts)}")
