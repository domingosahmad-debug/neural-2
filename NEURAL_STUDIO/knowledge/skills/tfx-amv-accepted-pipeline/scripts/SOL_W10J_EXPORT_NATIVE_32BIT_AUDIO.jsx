(function(){
function enc(x){if(x===null||x===undefined)return 'null';if(typeof x==='string')return '"'+x.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t')+'"';if(typeof x==='number'||typeof x==='boolean')return String(x);var a=[],k;if(x instanceof Array){for(k=0;k<x.length;k++)a.push(enc(x[k]));return '['+a.join(',')+']';}for(k in x)if(x.hasOwnProperty(k))a.push(enc(k)+':'+enc(x[k]));return '{'+a.join(',')+'}';}
var W='C:/Users/TUF/Documents/New project/NEURAL_STUDIO/data/bleach-we-on-go-20261027/',p=app.project,R={ok:false},item=null,states=[];
function write(){var f=new File(W+'SOL_W10J_NATIVE_AUDIO_EXPORT_RESULT.json');f.encoding='UTF-8';f.open('w');f.write(enc(R));f.close();}
try{
if(!p||!p.file||p.file.fsName!==new File(W+'EDIT_WOG_W10H_REVIEW_MASTER_AE24.aep').fsName||p.renderQueue.rendering)throw Error('Live project/render mismatch');
var c=p.itemByID(580),main=p.itemByID(7);if(!c||c.name!=='WOG_W10_DELIVERY_MASTER'||c.numLayers!==1||c.layer(1).source.id!==7||main.numLayers!==229||Math.round(c.duration/c.frameDuration)!==2757)throw Error('Delivery/master mismatch');
var gain=c.layer(1).property('ADBE Audio Group').property('ADBE Audio Levels').value;if(gain[0]!==-1||gain[1]!==-1)throw Error('Headroom changed');
var out=new File(W+'delivery/WOG_W10H_NATIVE_32BIT_MIX.aif');if(out.exists)throw Error('Unique output exists; no replay');
R.project=p.file.fsName;R.wasDirty=p.dirty;R.pictureDepth=p.bitsPerChannel;R.comp=580;R.duration=c.duration;R.frames=2757;R.note='Audio-only native render, original source mix and1dBheadroom. No picturedepth, timing or layer mutation. Probeactualcodec before floatclaim.';
for(var i=1;i<=p.renderQueue.numItems;i++){var q=p.renderQueue.item(i);if(q.status===RQItemStatus.QUEUED&&q.render){states.push(q);q.render=false;}}
item=p.renderQueue.items.add(c);item.applyTemplate('Best Settings');var om=item.outputModule(1);om.applyTemplate('AIFF 48kHz');om.setSettings({'Audio Bit Depth':'32 Bit','Audio Channels':'Stereo','Audio Sample Rate':'48.000 kHz','Output Audio':'On'});var s=om.getSettings(GetSettingsFormat.STRING);R.settings=s;if(s['Video Output']!=='false'||s['Audio Bit Depth']!=='32 Bit')throw Error('Nativeaudio32/output gate');
om.file=out;item.timeSpanStart=0;item.timeSpanDuration=c.duration;item.render=true;R.phase='configured32bitNativeAudio';write();p.renderQueue.render();if(item.status!==RQItemStatus.DONE)throw Error('Nativeaudio render notDONE');if(!out.exists||out.length<1000)throw Error('Nativeaudio output missing');R.output=out.fsName;R.bytes=out.length;R.ok=true;R.phase='done';
}catch(e){R.error=String(e);R.line=e.line;}
finally{try{if(item)item.remove();}catch(e){R.cleanupError=String(e);}for(var i=0;i<states.length;i++){try{states[i].render=true;}catch(e){}}write();}
return R.ok?'ok':'failed '+R.error;
})();
