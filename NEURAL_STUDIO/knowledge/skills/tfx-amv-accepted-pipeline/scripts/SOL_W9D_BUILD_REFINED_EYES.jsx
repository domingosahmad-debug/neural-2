(function(){
function neuralEncode(value){
 if(value===null||value===undefined)return 'null';
 if(typeof value==='string')return '"'+value.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';
 if(typeof value==='number')return isFinite(value)?String(value):'null';
 if(typeof value==='boolean')return String(value);
 var parts=[],i,key;
 if(value instanceof Array){for(i=0;i<value.length;i++)parts.push(neuralEncode(value[i]));return '['+parts.join(',')+']';}
 for(key in value)if(value.hasOwnProperty(key))parts.push(neuralEncode(key)+':'+neuralEncode(value[key]));
 return '{'+parts.join(',')+'}';
}


var W="C:/Users/TUF/Documents/New project/NEURAL_STUDIO/data/bleach-we-on-go-20261027/",R={ok:false},p=app.project,propertyCount=0;

function read(p){var f=new File(p);f.encoding='UTF-8';if(!f.open('r'))throw Error('read '+p);var x=f.read();f.close();return eval('('+x+')');}
function write(n,x){var f=new File(W+n);f.encoding='UTF-8';if(!f.open('w'))throw Error('write '+n);f.write(neuralEncode(x));f.close();}
function fail(s){throw Error(s);}
function value(v){if(v===null||typeof v==='number'||typeof v==='boolean'||typeof v==='string')return v;if(v instanceof Array)return v;if(v&&v.text!==undefined)return {text:v.text,font:v.font,fontSize:v.fontSize,tracking:v.tracking,applyFill:v.applyFill,fillColor:v.fillColor,applyStroke:v.applyStroke,strokeColor:v.strokeColor,strokeWidth:v.strokeWidth,justification:v.justification};if(v&&v.vertices!==undefined)return {vertices:v.vertices,inTangents:v.inTangents,outTangents:v.outTangents,closed:v.closed};return '[unsupported value type]';}
function properties(g){var out=[];for(var i=1;i<=g.numProperties;i++){if(++propertyCount>300000)fail('Snapshot too large; select fewer comp IDs');var q=g.property(i),o={name:q.name,matchName:q.matchName};if(q.propertyType===PropertyType.PROPERTY){o.keys=[];try{if(q.canSetExpression){o.expression=q.expression;o.expressionEnabled=q.expressionEnabled;}}catch(e){}try{o.value=value(q.value);}catch(e){o.value='[unavailable]';}for(var k=1;k<=q.numKeys;k++){if(++propertyCount>700000)fail('Key snapshot too large');var key={time:q.keyTime(k),value:value(q.keyValue(k))};try{key.inInterpolation=q.keyInInterpolationType(k);key.outInterpolation=q.keyOutInterpolationType(k);var ie=q.keyInTemporalEase(k),oe=q.keyOutTemporalEase(k);key.easeIn=[];key.easeOut=[];for(var z=0;z<ie.length;z++)key.easeIn.push({speed:ie[z].speed,influence:ie[z].influence});for(var z=0;z<oe.length;z++)key.easeOut.push({speed:oe[z].speed,influence:oe[z].influence});}catch(e){}o.keys.push(key);}}else {try{if(q.canSetEnabled)o.enabled=q.enabled;}catch(e){}o.children=properties(q);}out.push(o);}return out;}

function capture(c){propertyCount=0;var row={id:c.id,name:c.name,width:c.width,height:c.height,fps:c.frameRate,duration:c.duration,time:c.time,layers:[]};for(var j=1;j<=c.numLayers;j++){var l=c.layer(j),o={id:l.id,index:j,name:l.name,enabled:l.enabled,inPoint:l.inPoint,outPoint:l.outPoint,startTime:l.startTime,stretch:l.stretch,locked:l.locked,solo:l.solo,shy:l.shy,parent:l.parent?l.parent.id:null,properties:properties(l)};try{o.source_id=l.source?l.source.id:null;o.source_file=l.source&&l.source.file?l.source.file.fsName:null;o.audioEnabled=l.audioEnabled;o.hasAudio=l.hasAudio;o.blendingMode=l.blendingMode;o.motionBlur=l.motionBlur;o.timeRemapEnabled=l.timeRemapEnabled;o.frameBlendingType=l.frameBlendingType;o.threeDLayer=l.threeDLayer;o.adjustmentLayer=l.adjustmentLayer;}catch(e){}row.layers.push(o);}return row;}

var begun=false,added=[],oldGlow=[347,351,324];
function byid(c,id){for(var j=1;j<=c.numLayers;j++)if(c.layer(j).id===id)return c.layer(j);fail('Missing layer '+id);}
function setIO(l,a,b){l.outPoint=b;l.inPoint=a;if(Math.abs(l.outPoint-b)>.0001)l.outPoint=b;}
function normalized(layers,base,ignoreFlags){var out=[];for(var j=0;j<layers.length;j++){var z=layers[j],found=null;for(var k=0;k<base.length;k++)if(base[k].id===z.id){found=base[k];break;}if(!found)continue;z.index=found.index;if(ignoreFlags&&(z.id===347||z.id===351||z.id===324))z.enabled=found.enabled;out.push(z);}return out;}
try{
if(!p||!p.file||p.file.fsName!==new File(W+'EDIT_WOG_W9C_IRIS_PROOF_AE24.aep').fsName||p.renderQueue.rendering)fail('Current W9C identity/render mismatch');
var bp=read(W.replace('bleach-we-on-go-20261027/','blueprints/6d717e0d532844159a8e4156aed4abd9/CURRENT.json'));if(bp.hash!=='ef194b482f8392079f826cb2ddc135d5cb7a3c51be186a64f39f66ae733ee327')fail('Stale blueprint');
var c=p.itemByID(7),base=read(W+'SOL_W9C_AFTER_SNAPSHOT.json').compositions[0];if(!c||c.name!=='WOG_MAIN'||c.numLayers!==183||Math.round(c.duration/c.frameDuration)!==2709)fail('W9C signature mismatch');
var ct=c.time;c.time=base.time;var before=capture(c);c.time=ct;
if(neuralEncode(normalized(before.layers,base.layers,false))!==neuralEncode(base.layers))fail('W9C manual state differs');
R.recovery=W+'LIVE_BEFORE_W9D_EYES_'+new Date().getTime()+'_AE24.aep';p.save(new File(R.recovery));var dest=new File(W+'EDIT_WOG_W9D_EYES_AE24.aep');if(dest.exists)fail('New output exists');
app.beginUndoGroup('W9D source-detail iris rings, pupil/sclera protected');begun=true;
var specs=read(W+'analysis/w9/W9D_IRIS_TRACK_PLAN.json'),fps=24000/1001;R.eyes=[];
for(var i=0;i<specs.length;i++){
 var sp=specs[i],F=byid(c,sp.source_layer),E=F.duplicate();added.push(E.id);E.name='W9 IRIS DETAIL | '+sp.tag;E.audioEnabled=false;
 var ss=F.inPoint+sp.first/fps,ee=Math.min(F.outPoint,F.inPoint+(sp.last+1)/fps);setIO(E,ss,ee);
 for(var mi=0;mi<sp.polys.length;mi++){
  var poly=sp.polys[mi],m=E.property('ADBE Mask Parade').addProperty('ADBE Mask Atom');m.name=(poly.mode==='add'?'IRIS RING ':'PUPIL EXCLUSION ')+mi;m.maskMode=poly.mode==='add'?MaskMode.ADD:MaskMode.SUBTRACT;m.property('ADBE Mask Feather').setValue(poly.mode==='add'?[.65,.65]:[.4,.4]);
  var pa=m.property('ADBE Mask Shape');for(var f=sp.first;f<=sp.last;f++){var row=sp.tracking[f];if(!row.visible)fail('Unverified '+sp.tag+' '+f);var shape=new Shape(),v=[],it=[],ot=[];for(var k=0;k<poly.v.length;k++){v.push([poly.v[k][0]+row.dx,poly.v[k][1]+row.dy]);it.push([0,0]);ot.push([0,0]);}shape.vertices=v;shape.inTangents=it;shape.outTangents=ot;shape.closed=true;pa.setValueAtTime(F.inPoint+f/fps,shape);pa.setInterpolationTypeAtKey(pa.numKeys,KeyframeInterpolationType.LINEAR,KeyframeInterpolationType.LINEAR);}
 }
 var ex=E.property('ADBE Effect Parade').addProperty('ADBE Exposure2');ex.name='IRIS DETAIL exposure';ex.property('Exposure').setValue(sp.exposure);
 var gl=E.property('ADBE Effect Parade').addProperty('ADBE Glo2');gl.name='IRIS HALO controlled';gl.property('Glow Threshold').setValue(65);gl.property('Glow Radius').setValue(sp.glow_radius);gl.property('Glow Intensity').setValue(sp.intensity);E.property('ADBE Transform Group').property('ADBE Opacity').setValue(90);
 byid(c,sp.old_glow).enabled=false;
 R.eyes.push({tag:sp.tag,new_layer:E.id,source_owner:F.id,inPoint:E.inPoint,outPoint:E.outPoint,masks:sp.polys.length,old_glow_disabled:sp.old_glow,first:sp.first,last:sp.last});
}
R.text_audit=[];for(i=1;i<=c.numLayers;i++){var t=c.layer(i);if(t instanceof TextLayer){try{R.text_audit.push({id:t.id,name:t.name,inPoint:t.inPoint,outPoint:t.outPoint,enabled:t.enabled,text:t.property('ADBE Text Properties').property('ADBE Text Document').value.text});}catch(te){R.text_audit.push({id:t.id,error:String(te)});}}}
c.time=base.time;var after=capture(c);c.time=ct;
if(neuralEncode(normalized(after.layers,base.layers,true))!==neuralEncode(base.layers))fail('Original W9C properties changed outside3old-glow switches');
var proof=p.items.addComp('W9D_EYES_COMBINED_PROOF',1920,1080,1,246/fps,fps),parts=[[63.981981981982,132],[69.47997997998,34],[85.412996329663,48],[109.76001001001,32]],cursor=0;
for(i=0;i<parts.length;i++){var l=proof.layers.add(c);l.name='W9D eye passage '+i;l.startTime=cursor/fps-parts[i][0];setIO(l,cursor/fps,(cursor+parts[i][1])/fps);cursor+=parts[i][1];}
p.save(dest);R.saved=p.file.fsName;R.master={id:7,name:c.name,layers:c.numLayers,frames:2709};R.proof={id:proof.id,frames:246,width:1920,height:1080,fps:'24000/1001'};R.protected_fields_equal_except3_switches=true;write('SOL_W9D_AFTER_SNAPSHOT.json',{project:p.file.fsName,compositions:[after]});R.ok=true;
}catch(e){R.error=String(e);R.line=e.line;R.added=added;}
finally{if(begun)app.endUndoGroup();}
write('SOL_W9D_EYES_BUILD_RESULT.json',R);
})();
