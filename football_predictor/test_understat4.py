"""Deep scan Understat JS"""
import requests, re

files = [
    'https://understat.com/js/main.min.js?t=1765138215',
    'https://understat.com/js/league.min.js?t=1765269520',
]

for url in files:
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    print(f'=== {url.split("/")[-1].split("?")[0]} ===')
    # Find all URLs
    urls = re.findall(r'["\x27](https?://[^"\x27]+)["\x27]', r.text)
    for u in urls[:30]:
        print(f'  URL: {u}')
    # Find data references
    datas = re.findall(r'["\x27]([^"\x27]*data[^"\x27]*)["\x27]', r.text, re.IGNORECASE)
    for d in datas[:30]:
        print(f'  data: {d}')
