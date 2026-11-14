"""Unchanged startup bootstrap for Neural Studio 2.

Runs before any normal app module is imported. If a source repair is unfinished
or UNKNOWN it serves a recovery page only: no providers, production recovery,
editor, local engine or native lane are created. Standard library + maintenance
only; both files are protected from repair.

  python bootstrap.py --port 0              start the app (or the recovery page)
  python bootstrap.py --recover status      print recovery state
  python bootstrap.py --recover reconcile ID | restore ID
"""
import json, runpy, secrets, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import maintenance

ROOT = Path(__file__).resolve().parent

PAGE = """<!doctype html><meta charset="utf-8"><title>Neural Studio 2 - source recovery</title>
<style>body{font:14px/1.6 system-ui;margin:48px auto;max-width:760px;color:#202938;background:#f0f2f5}
section{background:#fff;border:1px solid #e1e6ed;border-radius:10px;padding:22px;margin:16px 0}
code{background:#edf2ff;padding:1px 5px;border-radius:4px}button{font:inherit;padding:8px 14px;margin:6px 8px 0 0}
#out{white-space:pre-wrap;color:#8a2d2d}</style>
<h1>Source recovery required</h1>
<p>A source repair did not finish. Production, providers, the editor and After Effects control are not running.
Nothing is retried automatically. Backups are preserved.</p><div id="list"></div><p id="out"></p>
<script>
let token;
async function call(body){const r=await fetch('/api/recovery',{method:'POST',headers:{'Content-Type':'application/json','X-Neural-Token':token},body:JSON.stringify(body)});return r.json();}
function draw(state){const list=document.getElementById('list');list.replaceChildren();
 if(state.clean){const p=document.createElement('section');p.textContent='Recovered. Close and reopen Neural Studio 2 to start normally.';list.append(p);return;}
 for(const m of state.pending){const s=document.createElement('section');const h=document.createElement('h3');h.textContent='Repair '+m.id+' - '+m.state+' - source tree: '+m.tree;s.append(h);
  for(const f of m.files){const d=document.createElement('div');d.textContent=f.path+' : '+(f.now==='after'?'replaced':f.now==='before'?'original':'neither recorded version');s.append(d);}
  const add=(label,action)=>{const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{const r=await call({action,repair:m.id});document.getElementById('out').textContent=r.error||'';if(r.result)draw(r.result);};s.append(b);};
  add('Restore verified backups','restore');
  if(m.tree!=='mixed')add(m.tree==='after'?'Keep the fully applied repair':'Mark as not applied','reconcile');
  list.append(s);}
 if(!state.pending.length&&state.reservation){const s=document.createElement('section');s.textContent='A maintenance reservation without a matching repair record exists ('+state.reservation.state+'). Inspect data/maintenance before continuing.';list.append(s);}}
fetch('/api/workspace').then(r=>r.json()).then(r=>{token=r.token;draw(r.recovery);});
</script>"""


def recovery_server(port):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def trusted(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def reply(self, status, body, mime='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status); self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control', 'no-store'); self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.trusted(): return self.send_error(403)
            if self.path == '/api/workspace':
                return self.reply(200, {'application': 'neural-studio-2', 'mode': 'source-recovery', 'token': token, 'recovery': maintenance.inspect(ROOT)})
            if self.path in ('/', '/index.html'): return self.reply(200, PAGE.encode(), 'text/html')
            self.send_error(404)

        def do_POST(self):
            if not self.trusted() or self.headers.get('X-Neural-Token') != token or self.path != '/api/recovery':
                return self.send_error(403)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096: raise ValueError('Invalid request size.')
                request = json.loads(self.rfile.read(size))
                action = {'restore': maintenance.restore, 'reconcile': maintenance.reconcile}.get(request.get('action'))
                if not action: raise ValueError('Unknown recovery action.')
                action(ROOT, request.get('repair'))
                self.reply(200, {'result': maintenance.inspect(ROOT)})
            except (ValueError, OSError, KeyError, TypeError) as error:
                self.reply(400, {'error': str(error)})

    with ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        print(f'Neural 2.0  http://127.0.0.1:{server.server_port}/', flush=True)
        print('Source recovery mode: normal services were not started.', file=sys.stderr, flush=True)
        server.serve_forever()


def main(argv):
    if '--recover' in argv:
        rest = argv[argv.index('--recover') + 1:]
        if rest[:1] == ['status']: print(json.dumps(maintenance.inspect(ROOT), indent=1))
        elif len(rest) == 2 and rest[0] in ('reconcile', 'restore'):
            getattr(maintenance, rest[0])(ROOT, rest[1]); print(json.dumps(maintenance.inspect(ROOT), indent=1))
        else: raise SystemExit('Usage: --recover status | reconcile ID | restore ID')
        return
    state = maintenance.inspect(ROOT, startup=True)
    if not state['clean']:
        port = int(argv[argv.index('--port') + 1]) if '--port' in argv else 8872
        return recovery_server(port)
    sys.argv = [str(ROOT / 'studio.py')] + argv
    runpy.run_path(str(ROOT / 'studio.py'), run_name='__main__')


if __name__ == '__main__':
    main(sys.argv[1:])
