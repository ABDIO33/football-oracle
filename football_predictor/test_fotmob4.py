"""Test fotmob library - direct import"""
import sys, json

# Fix the buggy __init__.py by importing directly
from fotmob.fotmob import FotMob

f = FotMob()

# Test 1: matches by date
try:
    data = f.getMatchesByDate('20260613')
    print(f'getMatchesByDate: {type(data).__name__}')
    if data:
        print(json.dumps(data, indent=2)[:1000])
except Exception as e:
    print(f'getMatchesByDate: {type(e).__name__}: {e}')
