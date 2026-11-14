"""Bounded, normalized director images. Uploading never starts inference.

Up to MAX_COUNT individual screenshots may accompany one director message. Per-image
and aggregate sizes are validated on the normalized local files; image bytes are never
embedded in history, prompts or logs - only IDs, names, dimensions and sizes.
"""
import base64, binascii, io, json, re, threading, uuid
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

class ChatImages:
 LOCK=threading.Lock()
 MAX_BYTES=6_000_000              # per uploaded image (decoded bytes)
 MAX_ENCODED=8_000_000            # per base64 upload body
 MAX_COUNT=10                     # individual screenshots per director message
 MAX_AGGREGATE_BYTES=24_000_000   # sum of normalized stored files for one message
 STORE_LIMIT_BYTES=500_000_000    # screenshot folder cap before the storage policy offers cleanup
 LEGACY_MAX_COUNT=4               # historical messages keep their four-image shape
 def __init__(self,root):
  self.folder=Path(root)/'data/command/images';self.lock=self.LOCK
 @classmethod
 def limits(cls):
  return {'max_images':cls.MAX_COUNT,'max_image_bytes':cls.MAX_BYTES,'max_aggregate_bytes':cls.MAX_AGGREGATE_BYTES,'formats':['PNG','JPEG','WEBP'],'individual_images':True}
 @staticmethod
 def clean_name(value):
  name=re.sub(r'[\x00-\x1f\x7f]+',' ',str(value or 'Screenshot')).strip()[:120]
  return name or 'Screenshot'
 def upload(self,data):
  encoded=data.get('data','')
  if not isinstance(encoded,str) or len(encoded)>self.MAX_ENCODED:raise ValueError('Image limit: 6 MB each')
  try:raw=base64.b64decode(encoded.split(',',1)[-1],validate=True)
  except (ValueError,binascii.Error):raise ValueError('Invalid image data')
  if not raw or len(raw)>self.MAX_BYTES:raise ValueError('Image limit: 6 MB each')
  try:
   with Image.open(io.BytesIO(raw)) as src:
    if src.format not in ['PNG','JPEG','WEBP'] or src.width*src.height>20_000_000 or min(src.size)<1:raise ValueError('Use a PNG, JPEG or WebP under 20 megapixels')
    if getattr(src,'n_frames',1)!=1:raise ValueError('Use a still screenshot')
    src.load();im=ImageOps.exif_transpose(src).convert('RGB');im.thumbnail((2560,2560))
  except (UnidentifiedImageError,Image.DecompressionBombError,OSError):raise ValueError('Image could not be decoded')
  with self.lock:
   self.folder.mkdir(parents=True,exist_ok=True)
   if sum(f.stat().st_size for f in self.folder.glob('*.jpg'))>self.STORE_LIMIT_BYTES:raise ValueError('Screenshot storage is full (500 MB); archive old screenshots first')
   ident=uuid.uuid4().hex;path=self.folder/(ident+'.jpg');im.save(path,'JPEG',quality=92)
   row={'id':ident,'name':self.clean_name(data.get('name')),'width':im.width,'height':im.height,'url':'/api/command/image?id='+ident,'bytes':path.stat().st_size}
   (self.folder/(ident+'.json')).write_text(json.dumps(row),encoding='utf-8')
  return row
 def path(self,ident):
  if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Invalid screenshot ID')
  path=self.folder/(ident+'.jpg')
  if not path.is_file():raise ValueError('Screenshot is no longer available')
  return path
 def resolve(self,ids):
  """Validate IDs for a new message; order is the caller's order and is preserved."""
  if not isinstance(ids,list) or len(ids)>self.MAX_COUNT or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('Attach up to ten different screenshots')
  rows=[];total=0
  for position,ident in enumerate(ids):
   path=self.path(ident)
   row=json.loads((self.folder/(ident+'.json')).read_text(encoding='utf-8'))
   row['name']=self.clean_name(row.get('name'));row['position']=position+1
   total+=path.stat().st_size;rows.append(row)
  if total>self.MAX_AGGREGATE_BYTES:raise ValueError('These screenshots total '+str(round(total/1e6,1))+' MB; the limit is '+str(self.MAX_AGGREGATE_BYTES//1_000_000)+' MB per message. Remove some and retry; your draft is kept.')
  return rows
 def prompt_note(self,rows,tool_name='Read'):
  """Path-only instruction for file-reading providers. Never contains image bytes."""
  lines=[f"{r.get('position',i+1)}. {self.path(r['id'])} ({r.get('name','Screenshot')}, {r.get('width')}x{r.get('height')})" for i,r in enumerate(rows or [])]
  if not lines:return ''
  return '\n\nThe human attached '+str(len(lines))+' individual screenshot(s) in this order. Open EVERY one with the '+str(tool_name)+' tool and look at it before you answer or act; describe only what you actually saw. Paths:\n'+'\n'.join(lines)+'\n'
