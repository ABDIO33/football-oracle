"""Check football-data.co.uk archive downloads"""
import requests

urls = [
    'https://www.football-data.co.uk/new_data.zip',
    'https://www.football-data.co.uk/mmz4281/2425/data.zip',
    'https://www.football-data.co.uk/mmz4281/2324/data.zip',
    'https://www.football-data.co.uk/englandm.html',
]
for url in urls:
    try:
        r = requests.head(url, timeout=10)
        size = r.headers.get('content-length', '?')
        print(f'{url}\n  HTTP {r.status_code}, size={size}')
    except Exception as e:
        print(f'{url}\n  ERROR: {e}')
