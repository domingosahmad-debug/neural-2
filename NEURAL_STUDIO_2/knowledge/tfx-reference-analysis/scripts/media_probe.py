"""Read-only FFprobe metadata and SHA-256; no GPU or transcoding."""
import argparse,hashlib,json,subprocess,shutil
from pathlib import Path
def sha256(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def probe(path,ffprobe='ffprobe'):
 path=path.resolve(strict=True)
 raw=subprocess.run([ffprobe,'-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,text=True,check=True)
 return {'path':str(path),'size':path.stat().st_size,'sha256':sha256(path),'ffprobe':json.loads(raw.stdout),'note':'nb_frames may be absent/estimated. This is metadata, not full-decode or listening QA.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('media',type=Path);p.add_argument('--output',type=Path);p.add_argument('--ffprobe',default='ffprobe');a=p.parse_args();s=json.dumps(probe(a.media,a.ffprobe),indent=2)
 if a.output:a.output.write_text(s,encoding='utf-8')
 else:print(s)
