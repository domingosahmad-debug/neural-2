"""Use the running Neural 2 local lane; never start a second engine or old Neural."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
sub=parser.add_subparsers(dest='command',required=True)
sub.add_parser('capabilities')
p=sub.add_parser('submit');p.add_argument('plan',type=Path);p.add_argument('--project')
for name in ('job','cancel'):
    sub.add_parser(name).add_argument('id')
p=sub.add_parser('artifact');p.add_argument('id');p.add_argument('step');p.add_argument('filename')
parser.add_argument('--out',type=Path,help='Save full reply instead of printing it.')
args=parser.parse_args()
base=json.loads((root/'.desktop-service.json').read_text())['url']
with urlopen(base+'api/workspace',timeout=10) as response: token=json.load(response)['token']
body={'action':{'capabilities':'media-capabilities','submit':'media-submit','job':'media-job','cancel':'media-cancel','artifact':'media-artifact'}[args.command]}
if hasattr(args,'id'):body['id']=args.id
if args.command=='submit':body.update(plan=json.loads(args.plan.read_text(encoding='utf-8-sig')),project=args.project)
if args.command=='artifact':body.update(step=args.step,filename=args.filename)
request=Request(base+'api/services',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Neural-Token':token})
with urlopen(request,timeout=20) as response: result=json.load(response)['result']
text=json.dumps(result,ensure_ascii=True,indent=2)
if args.out:
    args.out.write_text(text,encoding='utf-8');print('Saved '+str(args.out.resolve()))
else:print(text)
