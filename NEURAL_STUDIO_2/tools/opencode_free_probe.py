"""One two-step MCP tool probe per free OpenCode model (dummy tools only; never touches AE).
Usage: python tools/opencode_free_probe.py opencode/<name>-free ...   One attempt each; no retries. passed=true means the model
called both scoped tools in order and returned the exact JSON. Results: data/opencode-probe/<model>/summary.json."""
import json, os, subprocess, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
H = Path(__file__).resolve().parent
CLI = sorted((Path.home() / 'AppData/Roaming/ai.opencode.desktop/cli').glob('*/opencode-cli.exe'))[-1]
DENY = {k: 'deny' for k in ('*', 'read', 'glob', 'grep', 'list', 'edit', 'write', 'patch', 'shell', 'bash', 'webfetch', 'websearch', 'subagent', 'task', 'browser', 'external_directory')}
PROMPT = ('Use the probe tools. Step 1: call get_code with name "alpha". Step 2: call add_layer with that code and frames [14,15,14]. '
          'Then reply with ONLY this JSON, no prose: {"code": <code>, "layerId": "<layerId>"}')
def run(model):
    d = H.parent / 'data' / 'opencode-probe' / model.replace('/', '_'); cfg = d / 'cfg'; cfg.mkdir(parents=True, exist_ok=True)
    perm = dict(DENY); perm['probe_*'] = 'allow'
    (d / 'opencode.json').write_text(json.dumps({'permission': perm, 'mcp': {'servers': {'probe': {'type': 'local', 'command': [sys.executable, str(H / 'opencode_probe_mcp.py')]}}}}), encoding='utf-8')
    env = dict(os.environ); env.update(OPENCODE_CONFIG_DIR=str(cfg), OPENCODE_DISABLE_AUTOUPDATE='true', OPENCODE_DISABLE_PROJECT_CONFIG='true', OPENCODE_DISABLE_LSP_DOWNLOAD='true', OPENCODE_DISABLE_DEFAULT_PLUGINS='true')
    t = time.time(); out = ''
    try:
        p = subprocess.run([str(CLI), 'run', '--standalone', '--format', 'json', '--model', model, '--title', 'Neural2 tool probe'], input=PROMPT, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=d, env=env, timeout=240)
        out = p.stdout; (d / 'raw.log').write_text(out + '\n--STDERR--\n' + p.stderr, encoding='utf-8'); state = 'exit%d' % p.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b'').decode('utf-8', 'replace') if isinstance(e.stdout, bytes) else (e.stdout or ''); (d / 'raw.log').write_text(out, encoding='utf-8'); state = 'TIMEOUT'
    tools, text, err, cost, types = [], '', None, 0, {}
    for line in out.splitlines():
        try: e = json.loads(line)
        except ValueError: continue
        types[e.get('type')] = types.get(e.get('type'), 0) + 1; part = e.get('part') or {}
        if e.get('type') == 'tool_use' or part.get('type') == 'tool': tools.append((part.get('tool'), (part.get('state') or {}).get('status')))
        if e.get('type') == 'text': text += str(part.get('text', ''))
        if e.get('type') == 'error': err = str(e.get('error'))[:300]
        if e.get('type') == 'step_finish': cost += part.get('cost') or 0
    ok = '7319' in text and 'L7319-43' in text
    r = dict(model=model, state=state, seconds=round(time.time() - t), tools=tools, text=text.strip()[:160], error=err, cost=cost, passed=ok, eventTypes=types)
    (d / 'summary.json').write_text(json.dumps(r, indent=1), encoding='utf-8'); return r
if __name__ == '__main__':
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(run, sys.argv[1:]): print(json.dumps(r))
