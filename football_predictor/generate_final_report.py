#!/usr/bin/env python3
"""BETTING ROUND 2 — التقرير النهائي الشامل"""

import json, sqlite3, os, math
import numpy as np
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'output')

with open(os.path.join(OUT, 'upcoming_predictions.json')) as f:
    all_m = json.load(f)

non_wc = [m for m in all_m if 'World Cup' not in m.get('league','')]

# Load odds
conn = sqlite3.connect(os.path.join(BASE, 'scrape_cache.db'))
c = conn.cursor()
c.execute('SELECT home_team, away_team, odds_json FROM odds_upcoming')
odds = {}
for r in c.fetchall():
    try:
        d = json.loads(r[2])
        best = {}
        for b in d:
            if isinstance(b,dict) and 'markets' in b:
                for mkt in b['markets']:
                    if mkt.get('key')=='h2h':
                        pr = {o['name']:o['price'] for o in mkt['outcomes']}
                        h=pr.get(r[0],0); d_=pr.get('Draw',0); a=pr.get(r[1],0)
                        if h and d_ and a and (not best or h>best.get('h',0)):
                            best={'h':h,'d':d_,'a':a}
        if best: odds[(r[0].lower(),r[1].lower())] = best
    except: pass
conn.close()

def calc_mk(ts):
    p = np.ones(25)*0.001
    for s in ts[:10]:
        try:
            h,a = map(int,s[0].split('-')); 
            if h<5 and a<5: p[min(h*5+a,24)]=s[1]
        except: pass
    p /= p.sum(); s = p.reshape(5,5)
    hw=float(sum(s[h,a]for h in range(5)for a in range(5)if h>a))
    dr=float(sum(s[i,i]for i in range(5)))
    aw=float(sum(s[h,a]for h in range(5)for a in range(5)if a>h))
    tg=np.zeros(9)
    for h in range(5):
        for a in range(5): tg[min(h+a,8)]+=s[h,a]
    ex=[{'s':f'{h}-{a}','p':float(s[h,a])}for h in range(5)for a in range(5)if s[h,a]>0.005]
    ex.sort(key=lambda x:-x['p'])
    return {'1x2':{'h':hw,'d':dr,'a':aw},'exact':ex[:5],
            'ou':{f'ov{l}':float(tg[math.ceil(l):].sum())for l in[0.5,1.5,2.5,3.5,4.5]},
            'btts':{'y':float(sum(s[h,a]for h in range(1,5)for a in range(1,5))),
                    'n':float(1-sum(s[h,a]for h in range(1,5)for a in range(1,5)))},
            'dc':{'1x':hw+dr,'12':hw+aw,'2x':dr+aw},
            'wtn':{'h':float(sum(s[h,0]for h in range(1,5))),'a':float(sum(s[0,a]for a in range(1,5)))},
            'tg':{f'{g}':float(tg[min(g,8)])for g in range(9)},
            'oe':{'odd':float(sum(tg[g]for g in range(1,9,2))),'even':float(tg[0]+sum(tg[g]for g in range(2,9,2)))},
            'gr':{'0-1':float(tg[0]+tg[1]),'2-3':float(tg[2]+tg[3]),'4-5':float(tg[4]+tg[5]),'6+':float(tg[6:].sum())}}

# Group by date
by_date = defaultdict(list)
for m in non_wc:
    by_date[m.get('date','?')].append(m)

# Generate HTML
html = '''<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8">
<title>🔥 الرهان الثاني — التقرير النهائي</title>
<style>
*{box-sizing:border-box}
body{font-family:'Segoe UI',system-ui;background:#0d0d1a;color:#fff;margin:0;padding:20px}
h1{color:#ff4444;text-align:center;text-shadow:0 0 40px #f448;font-size:2.2em;margin:10px 0}
h2{color:#ffdd44;margin:24px 0 12px;padding-bottom:8px;border-bottom:2px solid #333}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:16px 0}
.st{background:#1a1a2e;border:1px solid #333;border-radius:12px;padding:14px;text-align:center}
.sn{font-size:1.8em;font-weight:bold;color:#ff4444}
.sl{color:#888;font-size:0.8em}
.date-hdr{color:#ffdd44;font-size:1.3em;margin:20px 0 10px;padding:8px;background:#1a1a2e;border-radius:8px}
.card{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:12px;padding:14px;margin:8px 0;transition:0.3s}
.card:hover{border-color:#ff4444;transform:translateX(3px)}
.ch{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.ct{font-weight:bold;font-size:1em}
.cl{color:#888;font-size:0.8em}
.ps{font-size:1.5em;font-weight:bold;color:#ffdd44;text-align:center;margin:6px 0}
.pb{display:flex;height:22px;border-radius:11px;overflow:hidden;margin:6px 0;font-size:0.75em;font-weight:bold}
.bh{background:#2a7a2a;text-align:left;padding:2px 6px}
.bd{background:#7a7a2a;text-align:center;padding:2px 4px}
.ba{background:#7a2a2a;text-align:right;padding:2px 6px}
.or{display:flex;gap:10px;margin:6px 0;font-size:0.85em}
.oh{color:#4a4}.od{color:#aa4}.oa{color:#a44}
.vb{padding:6px 10px;border-radius:6px;margin:4px 0;font-size:0.85em}
.vs{background:#2a0000;border:1px solid #f44}
.vm{background:#1a1a00;border:1px solid #fd4}
.eg{color:#0f0;font-weight:bold}
details{margin-top:6px}
summary{cursor:pointer;color:#ffdd44;font-size:0.9em}
table{width:100%;border-collapse:collapse;margin:6px 0;font-size:0.78em}
th{background:#222;padding:3px 5px;text-align:center;color:#ffdd44}
td{padding:2px 5px;border-bottom:1px solid #1a1a2e;text-align:center}
.chip{display:inline-block;background:#222;padding:2px 8px;border-radius:10px;margin:2px;font-size:0.8em}
.tag-ft{color:#888}
</style></head><body>
<h1>🔥 الرهان الثاني — BETTING ROUND 2</h1>
<p style="text-align:center;color:#888">'''+datetime.now().strftime('%Y-%m-%d %H:%M')+''' | Ultimate 306 (41.46%) | 15 أسواق رهان</p>'''

total_vb = 0
cards_html = ''
# Count stats
strong_vb = 0
mod_vb = 0
for m in non_wc:
    mk = calc_mk(m.get('top_scores',[]))
    key = (m['home_team'].lower(), m['away_team'].lower())
    od = odds.get(key, {})
    if od:
        mp = {'h':1/od['h'],'d':1/od['d'],'a':1/od['a']}
        ti = mp['h']+mp['d']+mp['a']
        for k in mp: mp[k]/=ti
        for lbl, mkp in [('H',mk['1x2']['h']),('D',mk['1x2']['d']),('A',mk['1x2']['a'])]:
            if mp[lbl.lower()]>0.01:
                edge = (mkp-mp[lbl.lower()])/mp[lbl.lower()]*100
                if edge>10: total_vb+=1; strong_vb+=edge>20; mod_vb+=10<edge<=20

# Sort by date
sorted_matches = sorted(non_wc, key=lambda m: m.get('date',''))
prev_date = None
for m in sorted_matches:
    date = m.get('date','?')
    if date != prev_date:
        is_past = date < '2026-07-03'
        tag = '🔴 منتهية' if is_past else '📅 قادمة'
        if date != prev_date:
            cards_html += f'<h2 class="date-hdr">{tag} {date} ({len(by_date[date])} مباراة)</h2>'
        prev_date = date
    
    mk = calc_mk(m.get('top_scores',[]))
    key = (m['home_team'].lower(), m['away_team'].lower())
    od = odds.get(key, {})
    
    pred = m.get('predicted_score','?-?')
    prob_val = m.get('probability',0)*100
    
    # Value bets
    vb_list = []
    if od:
        mp = {'h':1/od['h'],'d':1/od['d'],'a':1/od['a']}
        ti = mp['h']+mp['d']+mp['a']
        for k in mp: mp[k]/=ti
        for lbl, mkp, ol in [('HOME',mk['1x2']['h'],od['h']),('DRAW',mk['1x2']['d'],od['d']),('AWAY',mk['1x2']['a'],od['a'])]:
            if mp[lbl.lower()[:1]]>0.01:
                edge = (mkp-mp[lbl.lower()[:1]])/mp[lbl.lower()[:1]]*100
                if edge>10:
                    kelly = mkp - (1-mkp)/(ol-1) if ol>1 else 0
                    vb_list.append({'lbl':lbl,'mp':round(mkp*100,1),'edge':round(edge,1),'kelly':round(max(0,kelly*0.25)*100,2),'odds':round(ol,2)})
        vb_list.sort(key=lambda x:-x['edge'])
    
    vb_html = ''
    for v in vb_list[:3]:
        cls = 'vs' if v['edge']>20 else 'vm'
        vb_html += f'<div class="vb {cls}"><b>{v["lbl"]}</b> @ {v["odds"]:.2f} | Model: {v["mp"]:.0f}% | <span class="eg">Edge: +{v["edge"]:.0f}%</span> | Kelly: {v["kelly"]:.1f}%</div>'
    
    odds_html = ''
    if od:
        odds_html = f'<div class="or"><span class="oh">H: {od["h"]:.2f}</span><span class="od">D: {od["d"]:.2f}</span><span class="oa">A: {od["a"]:.2f}</span></div>'
    
    # Detail markets
    ex_html = ' '.join(f'<span class="chip">{e["s"]} ({e["p"]*100:.0f}%)</span>' for e in mk['exact'][:5])
    
    cards_html += f'''
<div class="card">
<div class="ch"><span class="ct">{m["home_team"]} 🆚 {m["away_team"]}</span><span class="cl">{m.get("league","?")[:25]}</span></div>
<div class="ps">{pred} <span style="font-size:0.5em">({prob_val:.0f}%)</span></div>
<div class="pb"><div class="bh" style="width:{mk['1x2']['h']*100:.1f}%">H {mk['1x2']['h']*100:.0f}%</div><div class="bd" style="width:{mk['1x2']['d']*100:.1f}%">D {mk['1x2']['d']*100:.0f}%</div><div class="ba" style="width:{mk['1x2']['a']*100:.1f}%">A {mk['1x2']['a']*100:.0f}%</div></div>
{odds_html}{vb_html}
<details><summary>📊 كل الأسواق (15)</summary>
<table><tr><th>O/U 2.5</th><th>BTTS Y</th><th>BTTS N</th><th>DC 1X</th><th>DC 12</th><th>DC 2X</th><th>W2N H</th><th>W2N A</th></tr>
<tr><td>{mk['ou']['ov2.5']*100:.0f}%/{mk['ou'].get('un2.5',1-mk['ou']['ov2.5'])*100:.0f}%</td><td>{mk['btts']['y']*100:.0f}%</td><td>{mk['btts']['n']*100:.0f}%</td><td>{mk['dc']['1x']*100:.0f}%</td><td>{mk['dc']['12']*100:.0f}%</td><td>{mk['dc']['2x']*100:.0f}%</td><td>{mk['wtn']['h']*100:.0f}%</td><td>{mk['wtn']['a']*100:.0f}%</td></tr></table>
<table><tr><th colspan="5">Total Goals</th><th colspan="2">Odd/Even</th><th colspan="4">Goal Ranges</th></tr>
<tr><td>0: {mk['tg']['0']*100:.0f}%</td><td>1: {mk['tg']['1']*100:.0f}%</td><td>2: {mk['tg']['2']*100:.0f}%</td><td>3: {mk['tg']['3']*100:.0f}%</td><td>4+: {mk['tg']['4']*100:.0f}%</td><td>Odd: {mk['oe']['odd']*100:.0f}%</td><td>Even: {mk['oe']['even']*100:.0f}%</td><td>{mk['gr']['0-1']*100:.0f}%</td><td>{mk['gr']['2-3']*100:.0f}%</td><td>{mk['gr']['4-5']*100:.0f}%</td><td>{mk['gr']['6+']*100:.0f}%</td></tr></table>
<div style="margin-top:4px"><b>🎯 Exact Scores:</b> {ex_html}</div>
</details></div>'''

html += f'''
<div class="stats">
<div class="st"><div class="sn">{len(non_wc)}</div><div class="sl">🏟️ المباريات</div></div>
<div class="st"><div class="sn">{total_vb}</div><div class="sl">💰 Value Bets</div></div>
<div class="st"><div class="sn">{strong_vb}</div><div class="sl">🔥 STRONG</div></div>
<div class="st"><div class="sn">{mod_vb}</div><div class="sl">✅ MODERATE</div></div>
<div class="st"><div class="sn">15</div><div class="sl">🎰 أسواق</div></div>
<div class="st"><div class="sn">{len(by_date)}</div><div class="sl">📅 تواريخ</div></div>
</div>
{cards_html}
</body></html>'''

report_path = os.path.join(OUT, 'betting_round2_final.html')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(html)

# Save JSON
json_path = os.path.join(OUT, 'betting_round2_data.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump([{
        'match':f"{m['home_team']} vs {m['away_team']}",
        'date':m.get('date','?'),'league':m.get('league','?'),
        'predicted_score':m.get('predicted_score','?'),
        'probability':m.get('probability',0),
        'markets':calc_mk(m.get('top_scores',[]))
    } for m in non_wc], f, ensure_ascii=False, indent=2)

print(f"✅ FINAL REPORT: {report_path}")
print(f"  📊 {len(non_wc)} matches, {total_vb} value bets (🔥{strong_vb} strong, ✅{mod_vb} moderate)")
print(f"  📅 {len(by_date)} dates: {', '.join(sorted(by_date.keys()))}")
