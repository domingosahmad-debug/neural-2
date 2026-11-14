import sys, json
def send(o): sys.stdout.write(json.dumps(o) + '\n'); sys.stdout.flush()
for line in sys.stdin:
    try: m = json.loads(line)
    except ValueError: continue
    i, meth = m.get('id'), m.get('method')
    if meth == 'initialize':
        send({'jsonrpc': '2.0', 'id': i, 'result': {'protocolVersion': m['params'].get('protocolVersion', '2024-11-05'), 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'probe', 'version': '1'}}})
    elif meth == 'tools/list':
        send({'jsonrpc': '2.0', 'id': i, 'result': {'tools': [
            {'name': 'get_code', 'description': 'Return the secret code for a name.', 'inputSchema': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
            {'name': 'add_layer', 'description': 'Add a layer. Returns its id.', 'inputSchema': {'type': 'object', 'properties': {'code': {'type': 'integer'}, 'frames': {'type': 'array', 'items': {'type': 'integer'}}}, 'required': ['code', 'frames']}}]}})
    elif meth == 'tools/call':
        p = m['params']; a = p.get('arguments') or {}
        if p['name'] == 'get_code': text = json.dumps({'code': 7319 if a.get('name') == 'alpha' else -1})
        else: text = json.dumps({'layerId': 'L' + str(a.get('code')) + '-' + str(sum(a.get('frames') or []))})
        send({'jsonrpc': '2.0', 'id': i, 'result': {'content': [{'type': 'text', 'text': text}]}})
    elif i is not None:
        send({'jsonrpc': '2.0', 'id': i, 'result': {}})
