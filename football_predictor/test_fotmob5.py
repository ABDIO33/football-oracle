"""Test fotmob - bypass broken __init__.py"""
import importlib.machinery, importlib.util
import sys, json

# Load the module directly, bypassing __init__.py
loader = importlib.machinery.SourceFileLoader(
    'fotmob_module', 
    r'C:\Python314\Lib\site-packages\fotmob\fotmob.py'
)
spec = importlib.util.spec_from_loader('fotmob_module', loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

f = mod.FotMob()

# Test matches
print('=== Matches by date ===')
try:
    data = f.getMatchesByDate('20260613')
    print(json.dumps(data, indent=2)[:2000])
except Exception as e:
    print(f'Error: {e}')

# Test league
print('\n=== League ===')
try:
    data = mod.FotMob.getLeague(47, 'overview', 'league', 'UTC')
    print(json.dumps(data, indent=2)[:2000])
except Exception as e:
    print(f'Error: {e}')
