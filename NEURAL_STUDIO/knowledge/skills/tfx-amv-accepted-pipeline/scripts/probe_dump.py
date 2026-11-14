"""Convert an ExtendScript toSource() probe result to JSON and print a compact keyframe summary. Usage: probe_dump.py RESULT.json [skip_prefix ...]"""
import json, re, sys
sys.stdout.reconfigure(encoding='utf-8')
src = sys.argv[1]; skip = tuple(sys.argv[2:])
s = open(src, encoding='utf-8').read().strip()
s = s.replace('({', '{').replace('})', '}')
s = re.sub(r'([\{,]\s*)([A-Za-z_]\w*):', r'\1"\2":', s)
r = json.loads(s)
json.dump(r, open(src.replace('_RESULT.json', '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('file', r.get('file'), 'dirty', r.get('dirty'), 'n', r.get('numLayers'), 'comps', r.get('comps'))
B = {6612: 'B', 6613: 'L', 6614: 'H'}
for L in r.get('layers', []):
    if skip and L['name'].startswith(skip): continue
    print('\n#%s %s | in %s out %s st %s str %s en %s blend %s adj %s mb %s src %s' % (L['idx'], L['name'], L['inP'], L['outP'], L['st'], L['stretch'], L['enabled'], L.get('blend'), L.get('adj'), L.get('mb'), L.get('src')))
    print('   static', L['static'], 'fx', [f[0] for f in L['fx']])
    for a in L['animated']:
        if 'expr' in a: print('   ', a['p'], 'EXPR', a['expr']); continue
        print('   ', a['p'], ' | '.join('%s:%s%s o%s i%s' % (k['t'], k['v'], B.get(k.get('oi'), '?'), k.get('eout', ''), k.get('ein', '')) for k in a['keys']))
