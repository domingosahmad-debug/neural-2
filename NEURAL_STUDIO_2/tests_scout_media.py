"""Offline media contracts: no provider, app, AE or external network."""
import json,sys,tempfile,unittest,wave,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent/'engine'))
import local_ops_tasks as ops
from operations import find_tool
import numpy as np
class Context:
 def __init__(self,out):self.out=out
 def check(self):pass
 def run(self,tool,args,timeout):
  r=subprocess.run([find_tool(tool),*map(str,args)],capture_output=True,text=True,timeout=timeout)
  if r.returncode:raise ValueError(r.stderr)
  return r.stdout,r.stderr
class ScoutMediaTests(unittest.TestCase):
 def test_subtitle_ordinal_maps_exact_stream_and_preserves_times(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'source.mkv';p.touch();out=root/'out';out.mkdir();ctx=Context(out)
   def ff(c,args,timeout):
    self.assertIn('0:s:1',args)
    (out/'subtitles.srt').write_text('1\n00:02:03,456 --> 00:02:05,678\nReal dialogue\n',encoding='utf-8')
   with patch.object(ops,'metadata',return_value={'streams':[{'codec_type':'subtitle','codec_name':'subrip','index':2},{'codec_type':'subtitle','codec_name':'ass','index':4}]}),patch.object(ops,'ff',side_effect=ff):
    r=ops.subtitle_extract(ctx,{'input':str(p),'stream':1})
   self.assertEqual(r['first_cue'][0],'00:02:03,456');self.assertEqual(r['stream_index'],4)
 def test_missing_or_bitmap_subtitle_rejected_before_ffmpeg(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'source.mkv';p.touch();ctx=Context(Path(d))
   for streams in ([],[{'codec_type':'subtitle','codec_name':'hdmv_pgs_subtitle'}]):
    with patch.object(ops,'metadata',return_value={'streams':streams}),patch.object(ops,'ff') as ff:
     with self.assertRaises(ValueError):ops.subtitle_extract(ctx,{'input':str(p)})
     ff.assert_not_called()
 def test_music_location_finds_excerpt_and_flags_it_as_candidate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rate=8000;rng=np.random.default_rng(13);t=np.arange(rate*20)/rate
   # Distinct, time-varying frequencies and amplitudes provide a unique clock.
   x=sum(np.sin(2*np.pi*(f*t+(.4+j*.1)*t*t))*(.4+.3*np.sin((.7+j*.31)*t+j)) for j,f in enumerate((180,440,890,1500)))/5
   def wav(p,x):
    with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes((x*30000).astype('<i2').tobytes())
   song=root/'song.wav';ref=root/'ref.wav';wav(song,x);wav(ref,x[rate*7:rate*13]+rng.normal(0,.005,rate*6));out=root/'out';out.mkdir()
   r=ops.music_locate(Context(out),{'song':str(song),'reference':str(ref),'duration':6})
   self.assertAlmostEqual(r['best']['song_seconds'],7,delta=.1);self.assertGreater(r['best']['score'],.2)
   self.assertIn('candidate',r['verification'].lower())
   self.assertEqual(r['checks'][-1]['status'],'NOT TESTED')
if __name__=='__main__':unittest.main()
