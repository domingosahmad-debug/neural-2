#target aftereffects
/* Read-only AE inventory. Writes beside this script; does not save/mutate project.
   Snapshot records supported values and opaque/unreadable properties explicitly.
   Large projects: narrow this inspector to the requested comp before dispatch. */
(function () {
    function enc(x) {
        if(x===null || x===undefined)return 'null';
        if(typeof x==='string')return '"'+x.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';
        if(typeof x==='number')return isFinite(x)?String(x):'null';
        if(typeof x==='boolean')return String(x);
        var a=[],i,k;if(x instanceof Array){for(i=0;i<x.length;i++)a.push(enc(x[i]));return '['+a.join(',')+']';}
        for(k in x)if(x.hasOwnProperty(k))a.push(enc(k)+':'+enc(x[k]));return '{'+a.join(',')+'}';
    }
    function val(x) {
        if(x===null || typeof x==='number' || typeof x==='string' || typeof x==='boolean')return x;
        if(x instanceof Array){var a=[];for(var i=0;i<x.length;i++)a.push(val(x[i]));return a;}
        if(x instanceof TextDocument)return {kind:'TextDocument',text:x.text,font:x.font,fontSize:x.fontSize,fillColor:x.fillColor,tracking:x.tracking};
        if(x instanceof Shape)return {kind:'Shape',vertices:x.vertices,inTangents:x.inTangents,outTangents:x.outTangents,closed:x.closed};
        return {opaque:true,note:'Use native copy; this inventory is not a round-trip serializer'};
    }
    function ease(a){var o=[];for(var i=0;i<a.length;i++)o.push({speed:a[i].speed,influence:a[i].influence});return o;}
    function prop(p,t){
        var o={name:p.name,matchName:p.matchName,index:p.propertyIndex};
        if(p.propertyType!==PropertyType.PROPERTY){o.children=[];for(var j=1;j<=p.numProperties;j++)o.children.push(prop(p.property(j),t));return o;}
        try{o.value=val(p.valueAtTime(t,false));}catch(e){o.unreadable=String(e);}
        try{if(p.canSetExpression){o.expression=p.expression;o.expressionEnabled=p.expressionEnabled;}}catch(_){}
        o.keys=[];for(var k=1;k<=p.numKeys;k++){
            var q={time:p.keyTime(k),value:val(p.keyValue(k))};
            try{q.inType=String(p.keyInInterpolationType(k));q.outType=String(p.keyOutInterpolationType(k));q.inEase=ease(p.keyInTemporalEase(k));q.outEase=ease(p.keyOutTemporalEase(k));q.auto=p.keyTemporalAutoBezier(k);q.continuous=p.keyTemporalContinuous(k);}catch(_){}
            o.keys.push(q);
        }return o;
    }
    var project=app.project;if(!project)throw new Error('No project');
    var c=project.activeItem,r={aeVersion:app.version,project:project.file?project.file.fsName:null,rendering:project.renderQueue.rendering,active:null,comps:[]},seen={};
    function visit(c){
        if(!(c instanceof CompItem)||seen[c.id])return;seen[c.id]=true;
        var o={id:c.id,name:c.name,width:c.width,height:c.height,pixelAspect:c.pixelAspect,frameRate:c.frameRate,frameDuration:c.frameDuration,duration:c.duration,sampleTime:c.time,layers:[]};
        for(var i=1;i<=c.numLayers;i++){
            var l=c.layer(i),q={id:l.id,name:l.name,index:i,inPoint:l.inPoint,outPoint:l.outPoint,startTime:l.startTime,stretch:l.stretch,enabled:l.enabled,locked:l.locked,selected:l.selected,threeD:l.threeDLayer,parent:l.parent?l.parent.id:null};
            try{q.sourceId=l.source.id;q.sourceFile=l.source.file?l.source.file.fsName:null;q.audio=l.audioEnabled;q.matteType=String(l.trackMatteType);q.blendMode=String(l.blendingMode);}catch(_){}
            q.properties=[];for(var j=1;j<=l.numProperties;j++)q.properties.push(prop(l.property(j),c.time));o.layers.push(q);
            try{if(l.source instanceof CompItem)visit(l.source);}catch(_){}
        }r.comps.push(o);
    }
    if(c){r.active={id:c.id,name:c.name};visit(c);}
    var f=new File(File($.fileName).parent.fsName+'/active_snapshot_'+(new Date().getTime())+'.json');
    f.encoding='UTF-8';if(!f.open('w'))throw new Error('Cannot write report');try{f.write(enc(r));}finally{f.close();}
})();
