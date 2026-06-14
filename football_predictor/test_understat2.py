"""Find Understat data sources"""
import requests, re

r = requests.get('https://understat.com/league/EPL', headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)

print("=== Scripts loaded ===")
scripts = re.findall(r'<script[^>]*src="([^"]+)"', r.text)
for s in scripts:
    print(f'  {s}')

print("\n=== JS files to check ===")
# Check the main JS file for API endpoints
for s in scripts:
    if '.js' in s and 'main' in s.lower():
        js_url = 'https://understat.com' + s if s.startswith('/') else s
        try:
            js = requests.get(js_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            print(f'\nJS: {js_url} ({len(js.text)} bytes)')
            # Find API endpoints
            apis = re.findall(r'(?:get|fetch|ajax|url:\s*|["\'])([^"\']*api[^"\']*)', js.text, re.IGNORECASE)
            for a in apis[:20]:
                print(f'  API: {a}')
        except Exception as e:
            print(f'{js_url}: ERROR {e}')
