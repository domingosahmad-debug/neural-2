"""Private scoped MCP server for Neural production. JSON-lines stdio; no shell tool.

Launch: python station_tools.py --scope ABSOLUTE_PRIVATE_SCOPE_JSON
Only the trusted parent provisions scope, service credentials and native ownership.
"""
import argparse
import json
import sys
from production_gateway import ProductionGateway


def schema(properties=None, required=()):
    return {'type':'object','properties':properties or {},'required':list(required),'additionalProperties':False}
STRING={'type':'string'}
WAIT={'type':'number','minimum':0,'maximum':60,'default':0}
GUARD=schema({'projectPath':{'type':['string','null']},'compId':{'type':['integer','null']},'compName':{'type':['string','null']},'signature':STRING},('projectPath','compId','compName','signature'))
TOOLS=[
    ('project_context','Read the exact saved assignment and pause state. No dispatch.',schema()),
    ('read_artifact','Read scoped text evidence by explicit byte range, or a PNG/JPEG as an actual image. Partial text is labeled; no arbitrary binary.',schema({'path':STRING,'offset':{'type':'integer','minimum':0,'default':0},'length':{'type':'integer','minimum':1,'maximum':65536,'default':65536},'jsonPointer':STRING},('path',))),
    ('write_artifact','Save a new immutable scoped text/JSON/JSX artifact. Existing changed content is refused.',schema({'path':STRING,'text':{'type':'string','maxLength':524288}},('path','text'))),
    ('ae_inspect','Submit a fixed read-only AE inspection using the exact owned TonyFX lane. Persist requestId; inspect still consumes the native channel.',schema({'requestId':STRING},('requestId',))),
    ('ae_submit','Submit bounded JSX with the exact guard returned by completed ae_inspect. Requires native mutation scope. UNKNOWN is never replayed. The JSX runs as a function body: return a plain JSON value or nothing. Save only in place with app.project.save(); the scoped AEP path is pinned. A FAILED mutation may have applied partial edits, so re-inspect before the next submit. For long work return production.outcome=waiting with waitNative=requestId and stop inference.',schema({'requestId':STRING,'jsx':{'type':'string','maxLength':98304},'guard':GUARD},('requestId','jsx','guard'))),
    ('ae_bootstrap','Create a NEW scoped AEP and comp after exact inspect guard. Requires explicit bootstrap scope; preserves old project copy before close. Never overwrites an AEP.',schema({'requestId':STRING,'guard':GUARD,'width':{'type':'integer','minimum':16,'maximum':8192},'height':{'type':'integer','minimum':16,'maximum':8192},'fps':{'type':'number','minimum':1,'maximum':240},'duration':{'type':'number','exclusiveMinimum':0,'maximum':3600}},('requestId','guard','width','height','fps','duration'))),
    ('ae_open','Reopen the existing scoped AEP when a completed ae_inspect shows another or no project open. Preserves a copy of the open project first; never creates or overwrites. Inspect again afterwards.',schema({'requestId':STRING,'guard':GUARD},('requestId','guard'))),
    ('ae_status','Read or locally wait up to60seconds for matching command AND own report. No inference timer, cancellation, or replay.',schema({'requestId':STRING,'waitSeconds':WAIT},('requestId',))),
    ('media_capabilities','Read installed typed mechanical operations. Native dispatch/assembly/publication excluded.',schema()),
    ('media_submit','Submit an immutable bounded typed mechanical plan through the running local engine. Plan shape: {version:1,title:string,steps:[{id:lower-case-name,operation:name from media_capabilities,args:{...},depends_on:[earlier ids]}]}. A FAILED submit was refused before running; correct the plan and submit under a new requestId. Project linkage is forced. No shell. Return production.outcome=waiting with waitMedia=[jobId] and stop inference while work runs.',schema({'requestId':STRING,'plan':{'type':'object'}},('requestId','plan'))),
    ('media_status','Read/wait on a local mechanical job of this project and admit its output folder as evidence. The reply gives readRoot: read_artifact readRoot/<stepId>/<output name> (images included); a folder path lists its entries.',schema({'jobId':STRING,'waitSeconds':WAIT},('jobId',))),
    ('desktop_observe','Capture a fresh, timestamped screenshot of one allowlisted window as an actual image: neural-studio-2 or after-effects. Observation only; it never launches, focuses, clicks or types, and a blank or missing window is an error, not evidence.',schema({'target':{'type':'string','enum':['neural-studio-2','after-effects']}})),
]

class StationTools:
    def __init__(self,gateway,read_only=False):self.gateway=gateway;self.read_only=read_only
    def names(self):
        return {name for name,_,_ in TOOLS if not self.read_only or name in ('project_context','read_artifact','ae_status','media_capabilities','media_status','desktop_observe')}
    def handle(self,message):
        identity=message.get('id');method=message.get('method')
        if identity is None:return None
        result=None
        try:
            if method=='initialize':
                requested=(message.get('params') or {}).get('protocolVersion','2024-11-05')
                result={'protocolVersion':requested if requested in ('2024-11-05','2025-03-26','2025-06-18') else '2025-06-18','capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'neural-station-tools','version':'1.0.0'}}
            elif method=='ping':result={}
            elif method=='tools/list':result={'tools':[{'name':name,'description':description,'inputSchema':definition} for name,description,definition in TOOLS if name in self.names()]}
            elif method=='tools/call':
                params=message.get('params') or {};name=params.get('name');arguments=params.get('arguments') or {}
                if name not in self.names():raise ValueError('Tool is not admitted in this scoped server.')
                if not isinstance(arguments,dict):raise ValueError('Typed tool argument object required.')
                definition=next(row[2] for row in TOOLS if row[0]==name)
                if set(arguments)-set(definition['properties']) or any(key not in arguments for key in definition['required']):raise ValueError('Tool arguments do not match the explicit contract.')
                value=getattr(self.gateway,name)(**arguments)
                if isinstance(value,dict) and value.get('kind')=='image':
                    result={'content':[{'type':'text','text':json.dumps({k:v for k,v in value.items() if k!='data'})},{'type':'image','data':value['data'],'mimeType':value['mimeType']}],'isError':False}
                else:result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
            else:return {'jsonrpc':'2.0','id':identity,'error':{'code':-32601,'message':'Unknown method'}}
            return {'jsonrpc':'2.0','id':identity,'result':result}
        except Exception as error:
            if method=='tools/call':return {'jsonrpc':'2.0','id':identity,'result':{'content':[{'type':'text','text':json.dumps({'error':str(error),'noAutomaticReplay':True})}],'isError':True}}
            return {'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':str(error)}}


def serve(server,source,sink):
    """Modern MCP newline framing; accepts legacy Content-Length without mixing modes."""
    while True:
        line=source.readline()
        if not line:return
        framed=line.lower().startswith(b'content-length:')
        try:
            if framed:
                length=int(line.split(b':',1)[1])
                if not 0<length<=2_000_000:raise ValueError('MCP message size exceeds bound.')
                while True:
                    header=source.readline()
                    if header in (b'\r\n',b'\n',b''):break
                raw=source.read(length)
                if len(raw)!=length:raise ValueError('Incomplete MCP frame.')
            else:
                raw=line
                if len(raw)>2_000_000:raise ValueError('MCP message size exceeds bound.')
            message=json.loads(raw)
            if not isinstance(message,dict):raise ValueError('JSON-RPC object required.')
            response=server.handle(message)
        except Exception as error:response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':str(error)}}
        if response is None:continue
        payload=json.dumps(response,ensure_ascii=False).encode('utf-8')
        sink.write((b'Content-Length: '+str(len(payload)).encode()+b'\r\n\r\n'+payload) if framed else payload+b'\n');sink.flush()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',required=True)
    parser.add_argument('--read-only',action='store_true',help='Commissioning: context/artifact/status only; no AE submission, writes or media submission.')
    args=parser.parse_args()
    try:gateway=ProductionGateway(args.scope)
    except Exception as error:parser.exit(2,str(error)+'\n')
    serve(StationTools(gateway,args.read_only),sys.stdin.buffer,sys.stdout.buffer)

if __name__=='__main__':main()
