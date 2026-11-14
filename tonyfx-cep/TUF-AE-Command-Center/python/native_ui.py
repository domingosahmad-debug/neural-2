"""TonyFX-owned AE window input. Each input consumes one recent observation.

Only invoked by the installed CEP command owner; no network service, shell
command execution, other-app targeting, or automatic input retries.
"""
from pathlib import Path
import base64, ctypes, hashlib, io, json, math, os, re, sys, time, uuid
from datetime import datetime, timezone
from ctypes import wintypes as w
from PIL import Image, ImageGrab, ImageChops

COMMANDS = {'uiSnapshot','uiActivate','uiClick','uiDoubleClick','uiStroke','uiScroll','uiKey','uiText'}
OBSERVATION_TTL = 120
MODIFIERS = {'CTRL':0x11,'ALT':0x12,'SHIFT':0x10}
SPECIAL = {'ENTER':13,'TAB':9,'ESCAPE':27,'SPACE':32,'BACKSPACE':8,'DELETE':46,
           'LEFT':37,'UP':38,'RIGHT':39,'DOWN':40,'HOME':36,'END':35,'PAGEUP':33,'PAGEDOWN':34,
           'LBRACKET':0xDB,'RBRACKET':0xDD,'COMMA':0xBC,'PERIOD':0xBE,'SLASH':0xBF,'MINUS':0xBD,'EQUALS':0xBB,
           'NUMPADADD':0x6B,'NUMPADSUBTRACT':0x6D,'NUMPADMULTIPLY':0x6A,'NUMPADDIVIDE':0x6F,'NUMPADDECIMAL':0x6E}

def atomic(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)

def keycodes(chord):
    parts=str(chord).upper().split('+')
    if len(parts)>4 or any(p in ('WIN','WINDOWS','META','SUPER','LWIN','RWIN') for p in parts):
        raise ValueError('Desktop/system shortcuts are not AE UI commands')
    mods=parts[:-1];key=parts[-1]
    if len(set(mods))!=len(mods) or any(m not in MODIFIERS for m in mods):raise ValueError('Invalid key modifiers')
    if (key=='DELETE' and {'CTRL','ALT'}<=set(mods)) or (key=='ESCAPE' and 'CTRL' in mods) or (key in ('TAB','F4') and 'ALT' in mods):raise ValueError('System/window-management shortcut refused')
    vk=SPECIAL.get(key)
    if vk is None:
        if len(key)==1 and key.isascii() and key.isalnum():vk=ord(key)
        elif re.fullmatch(r'F([1-9]|1[0-2])',key):vk=0x70+int(key[1:])-1
        elif re.fullmatch(r'NUMPAD[0-9]',key):vk=0x60+int(key[-1])
        else:raise ValueError('Unsupported key name')
    return [MODIFIERS[m] for m in mods]+[vk]

def validate_context(current, expected):
    if not isinstance(expected,dict):raise ValueError('Input requires expectedContext from uiSnapshot')
    for key in ('projectPath','itemId','viewerType','toolType','selectedLayerIds'):
        if current.get(key)!=expected.get(key):raise ValueError('AE context changed: '+key)
    if abs(float(current.get('time') or 0)-float(expected.get('time') or 0))>.001:raise ValueError('AE frame changed')

def validate_action(command,args,width,height):
    def point(p):
        if not isinstance(p,(list,tuple)) or len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in p):raise ValueError('Invalid coordinate')
        if not 0<=p[0]<width or not 0<=p[1]<height:raise ValueError('Coordinate outside observed AE window')
    if command in ('uiClick','uiDoubleClick','uiScroll'):point([args.get('x'),args.get('y')])
    if command=='uiScroll' and (type(args.get('delta')) is not int or not -3000<=args['delta']<=3000):raise ValueError('Scroll delta requires bounded Windows wheel units')
    if command=='uiStroke':
        points=args.get('points',[])
        if not isinstance(points,list) or not 2<=len(points)<=2048:raise ValueError('Stroke requires 2-2048 observed points')
        for p in points:point(p)
        duration=args.get('durationMs',500)
        if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not 100<=duration<=10000:raise ValueError('Stroke duration outside bounds')
    if command in ('uiClick','uiDoubleClick','uiStroke'):
        if args.get('button','left') not in ('left','right'):raise ValueError('Unsupported mouse button')
        if not isinstance(args.get('modifiers',[]),list) or any(m not in MODIFIERS for m in args.get('modifiers',[])):raise ValueError('Invalid pointer modifier')
    if command=='uiKey':keycodes(args.get('keys',''))
    if command=='uiText':
        text=args.get('text')
        if not isinstance(text,str) or not 1<=len(text)<=4000 or any(ord(c)<32 for c in text):raise ValueError('Use uiKey for control keys; text must be 1-4000 printable characters')

class Windows:
    def __init__(self):
        if os.name!='nt':raise RuntimeError('Native UI requires Windows')
        self.u=ctypes.WinDLL('user32',use_last_error=True);self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        try:self.u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError,OSError):pass
        self.u.GetForegroundWindow.restype=w.HWND
        self.u.GetWindowTextLengthW.argtypes=[w.HWND]
        self.u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int]
        self.u.GetWindowRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
        self.u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
        self.u.IsWindowVisible.argtypes=[w.HWND]
        self.u.IsIconic.argtypes=[w.HWND]
        self.u.WindowFromPoint.argtypes=[w.POINT];self.u.WindowFromPoint.restype=w.HWND
        self.u.GetAncestor.argtypes=[w.HWND,w.UINT];self.u.GetAncestor.restype=w.HWND
        self.u.SetForegroundWindow.argtypes=[w.HWND]
        self.u.BringWindowToTop.argtypes=[w.HWND]
        self.u.AttachThreadInput.argtypes=[w.DWORD,w.DWORD,w.BOOL]
        self.k.GetCurrentThreadId.restype=w.DWORD
        self.u.ShowWindow.argtypes=[w.HWND,ctypes.c_int]
        self.u.ShowWindowAsync.argtypes=[w.HWND,ctypes.c_int]
        class GuiInfo(ctypes.Structure):
            _fields_=[('cbSize',w.DWORD),('flags',w.DWORD),('hwndActive',w.HWND),('hwndFocus',w.HWND),('hwndCapture',w.HWND),('hwndMenuOwner',w.HWND),('hwndMoveSize',w.HWND),('hwndCaret',w.HWND),('rcCaret',w.RECT)]
        self.GuiInfo=GuiInfo;self.u.GetGUIThreadInfo.argtypes=[w.DWORD,ctypes.POINTER(GuiInfo)]
        self.k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];self.k.OpenProcess.restype=w.HANDLE
        self.k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
        self.k.CloseHandle.argtypes=[w.HANDLE]
        class Mouse(ctypes.Structure):_fields_=[('dx',w.LONG),('dy',w.LONG),('mouseData',w.DWORD),('dwFlags',w.DWORD),('time',w.DWORD),('dwExtraInfo',ctypes.c_size_t)]
        class Keyboard(ctypes.Structure):_fields_=[('wVk',w.WORD),('wScan',w.WORD),('dwFlags',w.DWORD),('time',w.DWORD),('dwExtraInfo',ctypes.c_size_t)]
        class Hardware(ctypes.Structure):_fields_=[('uMsg',w.DWORD),('wParamL',w.WORD),('wParamH',w.WORD)]
        class Union(ctypes.Union):_fields_=[('mi',Mouse),('ki',Keyboard),('hi',Hardware)]
        class Input(ctypes.Structure):_anonymous_=('data',);_fields_=[('type',w.DWORD),('data',Union)]
        self.Mouse,self.Keyboard,self.Input=Mouse,Keyboard,Input
        self.u.SendInput.argtypes=[w.UINT,ctypes.POINTER(Input),ctypes.c_int];self.u.SendInput.restype=w.UINT
    def info(self,hwnd):
        pid=w.DWORD();thread=self.u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        handle=self.k.OpenProcess(0x1000,False,pid.value);buf=ctypes.create_unicode_buffer(32768);n=w.DWORD(len(buf))
        try:
            if not handle or not self.k.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(n)):raise RuntimeError('Cannot verify target process')
        finally:
            if handle:self.k.CloseHandle(handle)
        if Path(buf.value).name.lower()!='afterfx.exe':raise ValueError('Only the actual After Effects process is allowed')
        title=ctypes.create_unicode_buffer(self.u.GetWindowTextLengthW(hwnd)+1);self.u.GetWindowTextW(hwnd,title,len(title))
        rect=w.RECT()
        if not self.u.GetWindowRect(hwnd,ctypes.byref(rect)):raise RuntimeError('AE window rectangle unavailable')
        gui=self.GuiInfo();gui.cbSize=ctypes.sizeof(gui);self.u.GetGUIThreadInfo(thread,ctypes.byref(gui))
        return {'hwnd':int(hwnd),'pid':pid.value,'exe':buf.value,'title':title.value,'rect':[rect.left,rect.top,rect.right,rect.bottom],'focusHwnd':int(gui.hwndFocus or 0)}
    def select(self,args):
        if args.get('hwnd'):return self.info(int(args['hwnd']))
        try:return self.info(self.u.GetForegroundWindow())
        except (ValueError,RuntimeError):pass
        candidates=[]
        callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        def visit(hwnd,_):
            if self.u.IsWindowVisible(hwnd):
                try:
                    info=self.info(hwnd)
                    if info['title']:candidates.append(info)
                except (ValueError,RuntimeError):pass
            return True
        self.u.EnumWindows(callback(visit),0)
        if len(candidates)!=1:raise ValueError('Select exactly one returned AE window using hwnd; candidates='+json.dumps(candidates))
        return candidates[0]
    def foreground(self,info):
        if getattr(self,'ownership_guard',None):self.ownership_guard()
        if int(self.u.GetForegroundWindow() or 0)!=info['hwnd']:raise RuntimeError('AE is not foreground; observe and uiActivate first')
        current=self.info(info['hwnd'])
        if any(current[k]!=info[k] for k in ('pid','exe','rect','focusHwnd')) or current['title'].rstrip(' *')!=info['title'].rstrip(' *'):raise RuntimeError('Observed AE window/focus changed')
    def capture(self,info):
        self.foreground(info);image=ImageGrab.grab(bbox=tuple(info['rect']),all_screens=True);self.foreground(info);return image.convert('RGB')
    def send(self,item):
        if self.u.SendInput(1,ctypes.byref(item),ctypes.sizeof(item))!=1:raise RuntimeError('Windows refused native input')
    def key(self,vk,up=False,unit=None):
        item=self.Input();item.type=1;item.ki=self.Keyboard(0 if unit is not None else vk,unit or 0,(4 if unit is not None else 0)|(2 if up else 0),0,0);self.send(item)
    def mouse(self,info,point=None,flag=0,data=0):
        item=self.Input();item.type=0;dx=dy=0
        if point is not None:
            x,y=point;left,top=info['rect'][:2];vx,vy=self.u.GetSystemMetrics(76),self.u.GetSystemMetrics(77);vw,vh=self.u.GetSystemMetrics(78),self.u.GetSystemMetrics(79)
            hit=self.u.WindowFromPoint(w.POINT(round(left+x),round(top+y)));pid=w.DWORD();self.u.GetWindowThreadProcessId(hit,ctypes.byref(pid))
            if pid.value!=info['pid'] and int(self.u.GetAncestor(hit,2) or 0)!=info['hwnd']:raise RuntimeError('Pointer target is covered by a different app; no input')
            dx=round((left+x-vx)*65535/max(1,vw-1));dy=round((top+y-vy)*65535/max(1,vh-1));flag|=0xC001
        item.mi=self.Mouse(dx,dy,data & 0xFFFFFFFF,flag,0,0);self.send(item)
    def activate(self,info):
        if self.u.IsIconic(info['hwnd']) or info['rect'][0]<=-30000:
            self.u.ShowWindowAsync(info['hwnd'],9);time.sleep(.3)
            if self.info(info['hwnd'])['rect'][0]<=-30000:self.u.ShowWindowAsync(info['hwnd'],3);time.sleep(.3)
        self.u.SetForegroundWindow(info['hwnd']);time.sleep(.15)
        if int(self.u.GetForegroundWindow() or 0)!=info['hwnd']:
            foreground=self.u.GetForegroundWindow();foreground_thread=self.u.GetWindowThreadProcessId(foreground,None);own_thread=self.k.GetCurrentThreadId()
            attached=bool(foreground_thread and foreground_thread!=own_thread and self.u.AttachThreadInput(own_thread,foreground_thread,True))
            try:self.u.BringWindowToTop(info['hwnd']);self.u.SetForegroundWindow(info['hwnd'])
            finally:
                if attached:self.u.AttachThreadInput(own_thread,foreground_thread,False)
            time.sleep(.15)
        current=self.info(info['hwnd']);self.foreground(current)
        if self.u.IsIconic(info['hwnd']) or current['rect'][0]<=-30000:raise RuntimeError('AE has not restored from minimized state; no input')
    def act(self,command,args,info):
        held=[];button=None
        try:
            self.foreground(info)
            if command=='uiActivate':return self.activate(info)
            if command=='uiScroll':self.mouse(info,[args['x'],args['y']]);self.mouse(info,flag=0x0800,data=args['delta'])
            elif command=='uiKey':
                for vk in keycodes(args['keys']):self.key(vk);held.append(vk)
            elif command=='uiText':
                raw=args['text'].encode('utf-16-le')
                for i in range(0,len(raw),2):
                    self.foreground(info);unit=int.from_bytes(raw[i:i+2],'little');self.key(0,unit=unit);self.key(0,True,unit)
            else:
                for mod in args.get('modifiers',[]):self.key(MODIFIERS[mod]);held.append(MODIFIERS[mod])
                down,up=(2,4) if args.get('button','left')=='left' else (8,16)
                points=args['points'] if command=='uiStroke' else [[args['x'],args['y']]]
                self.mouse(info,points[0]);self.mouse(info,flag=down);button=up
                if command=='uiStroke':
                    delay=args.get('durationMs',500)/1000/(len(points)-1)
                    for point in points[1:]:time.sleep(delay);self.foreground(info);self.mouse(info,point)
                else:time.sleep(.05)
                self.mouse(info,flag=up);button=None
                if command=='uiDoubleClick':time.sleep(.08);self.mouse(info,flag=down);button=up;self.mouse(info,flag=up);button=None
        finally:
            if button:self.mouse(info,flag=button)
            for vk in reversed(held):self.key(vk,True)

class Controller:
    def __init__(self,root,backend):self.root=Path(root);self.ui=self.root/'ui';self.backend=backend
    def snapshot(self,context,args):
        info=self.backend.select(args);ident=uuid.uuid4().hex;image=None
        try:image=self.backend.capture(info)
        except RuntimeError:pass
        observation={'id':ident,'created':time.time(),'window':info,'context':context,'foreground':image is not None}
        if image is not None:
            self.ui.mkdir(parents=True,exist_ok=True);p=self.ui/(ident+'.png');image.save(p);observation['image']=str(p)
            b=io.BytesIO();image.resize((160,90)).save(b,format='PNG');observation['thumbnail']=base64.b64encode(b.getvalue()).decode()
        atomic(self.ui/'observations'/(ident+'.json'),observation)
        return {'ok':True,'observationId':ident,'window':info,'image':observation.get('image'),'foreground':image is not None,'context':context,'expiresInSeconds':OBSERVATION_TTL}
    def run(self,command,args,context):
        if command=='uiSnapshot':return self.snapshot(context,args)
        ident=args.get('observationId','')
        if not re.fullmatch(r'[a-f0-9]{32}',str(ident)):raise ValueError('Input requires a returned observationId')
        p=self.ui/'observations'/(ident+'.json');o=json.loads(p.read_text(encoding='utf-8'))
        if not 0<=time.time()-o['created']<=OBSERVATION_TTL:raise ValueError('Observation expired; capture fresh AE state')
        validate_context(context,o['context']);validate_context(context,args.get('expectedContext'))
        info=o['window'];current=self.backend.info(info['hwnd'])
        if current!=info:raise ValueError('Observed window identity/layout changed')
        width,height=info['rect'][2]-info['rect'][0],info['rect'][3]-info['rect'][1]
        validate_action(command,args,width,height)
        if command!='uiActivate':
            self.backend.foreground(info)
            if not o.get('thumbnail'):raise ValueError('A foreground screenshot is required before input')
            before=Image.open(io.BytesIO(base64.b64decode(o['thumbnail']))).convert('RGB')
            now=self.backend.capture(info).resize((160,90));difference=ImageChops.difference(before,now)
            pixels=difference.get_flattened_data() if hasattr(difference,'get_flattened_data') else difference.getdata()
            changed=sum(max(px)>24 for px in pixels)/(160*90)
            if changed>.01:raise ValueError('AE pixels changed; capture and inspect a new observation')
        with (self.ui/'observations'/(ident+'.used')).open('x',encoding='utf-8') as used:used.write(command)
        started=True
        try:
            if command=='uiActivate':self.backend.activate(info)
            else:self.backend.act(command,args,info)
            time.sleep(.12);after=self.backend.capture(self.backend.info(info['hwnd']));target=self.ui/(ident+'-after.png');after.save(target)
            return {'ok':True,'action':command,'afterImage':str(target),'inputStarted':started,'requiresFreshSnapshot':True}
        except Exception as e:return {'ok':False,'error':str(e),'inputStarted':True,'uncertain':True,'requiresFreshSnapshot':True,'noAutomaticRetry':True}

def owned_request(path):
    path=Path(path).resolve();root=path.parents[2]
    if path.parent!=root/'ui'/'requests':raise ValueError('Request must be published by the TonyFX UI queue')
    request=json.loads(path.read_text(encoding='utf-8-sig'))
    live=json.loads((root/'ae_command.json').read_text(encoding='utf-8-sig'));lock=json.loads((root/'ae_command.json.tonyfx.lock').read_text(encoding='utf-8-sig'))
    if live.get('id')!=request.get('id') or live.get('status')!='running' or live.get('command')!=request.get('command') or live.get('owner')!=lock.get('owner') or lock.get('commandId')!=live.get('id'):raise ValueError('TonyFX command ownership changed; no input')
    heartbeat=datetime.fromisoformat(str(lock.get('heartbeat','')).replace('Z','+00:00'))
    if not 0<=(datetime.now(timezone.utc)-heartbeat).total_seconds()<=15:raise ValueError('TonyFX owner heartbeat is stale; no input')
    if request.get('command') not in COMMANDS:raise ValueError('Unknown native UI command')
    return root,request

def main():
    try:
        root,request=owned_request(sys.argv[1]);backend=Windows();backend.ownership_guard=lambda:owned_request(sys.argv[1])
        result=Controller(root,backend).run(request['command'],request.get('args',{}),request['context'])
    except Exception as e:result={'ok':False,'error':str(e),'inputStarted':False,'requiresFreshSnapshot':True,'noAutomaticRetry':True}
    print(json.dumps(result,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
