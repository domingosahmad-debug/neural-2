"""Bounded public documentation lookup via Exa's documented no-key hosted MCP."""
import json,re
from urllib.request import Request,urlopen

def search(query):
 payload={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'web_search_exa','arguments':{'query':str(query)[:500]+' official documentation','numResults':3,'type':'fast','contextMaxCharacters':4500}}}
 req=Request('https://mcp.exa.ai/mcp',json.dumps(payload).encode(),{'Content-Type':'application/json','Accept':'application/json, text/event-stream'})
 with urlopen(req,timeout=15) as response:
  raw=response.read(100000).decode('utf-8');kind=response.headers.get('Content-Type','')
 if 'text/event-stream' in kind:
  messages=[json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:') and line[5:].strip().startswith('{')]
  data=next((m for m in messages if m.get('id')==1),{})
 else:data=json.loads(raw)
 if data.get('error') or data.get('result',{}).get('isError'):raise ValueError('Public documentation search is unavailable or rate limited')
 text='\n'.join(c.get('text','') for c in data.get('result',{}).get('content',[]) if c.get('type')=='text')[:5500]
 if not text:raise ValueError('Search returned no source evidence')
 urls=list(dict.fromkeys(re.findall(r'https://[^\s<>"\)\]]+',text)))[:5]
 return {'text':text,'sources':urls,'provider':'Exa hosted search · free access subject to availability'}
