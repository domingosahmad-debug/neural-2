(function () {
    var output = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/tonyfx_adjustment_effects_test.json");
    var original = app.project ? app.project.activeItem : null;
    var comp = null;
    var report = {ok:false, passed:[], failed:[]};
    function quote(value) { return '"' + String(value).replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n") + '"'; }
    function json(value) { if(value===null)return"null";var t=typeof value;if(t==="string")return quote(value);if(t==="number")return isFinite(value)?String(value):"null";if(t==="boolean")return value?"true":"false";if(value instanceof Array){var a=[];for(var i=0;i<value.length;i++)a.push(json(value[i]));return"["+a.join(",")+"]";}var p=[];for(var k in value)if(value.hasOwnProperty(k)&&typeof value[k]!=="undefined")p.push(quote(k)+":"+json(value[k]));return"{"+p.join(",")+"}"; }
    function write() { output.encoding="UTF-8"; if(output.open("w")){output.write(json(report));output.close();} }
    function select(layers) { for(var i=1;i<=comp.numLayers;i++)comp.layer(i).selected=false;for(var j=0;j<layers.length;j++)layers[j].selected=true; }
    function findLayer(prefix) { for(var i=1;i<=comp.numLayers;i++)if(comp.layer(i).name.indexOf(prefix)===0)return comp.layer(i);return null; }
    function hasNonZero(property) {
        if (!property) return false;
        if (property.propertyType===PropertyType.PROPERTY) {
            try { for(var k=1;k<=property.numKeys;k++){var v=property.keyValue(k);if(typeof v==="number"&&Math.abs(v)>0.0001)return true;if(v instanceof Array){for(var x=0;x<v.length;x++)if(Math.abs(v[x])>0.0001)return true;}} } catch(ignoreKeys){}
            try { var current=property.value;if(typeof current==="number"&&Math.abs(current)>0.0001)return true;if(current instanceof Array){for(var y=0;y<current.length;y++)if(Math.abs(current[y])>0.0001)return true;} } catch(ignoreValue){}
            return false;
        }
        for(var i=1;i<=property.numProperties;i++)if(hasNonZero(property.property(i)))return true;
        return false;
    }
    function keyStats(property, stats) {
        stats=stats||{first:999999,last:-999999,maxKeys:0};
        if(!property)return stats;
        if(property.propertyType===PropertyType.PROPERTY){if(property.numKeys){stats.first=Math.min(stats.first,property.keyTime(1));stats.last=Math.max(stats.last,property.keyTime(property.numKeys));stats.maxKeys=Math.max(stats.maxKeys,property.numKeys);}return stats;}
        for(var i=1;i<=property.numProperties;i++)keyStats(property.property(i),stats);return stats;
    }
    function runSingle(preset, source) {
        select([source]);
        var before=source.property("ADBE Effect Parade").numProperties;
        var result=eval("("+TUF.runTool(json(preset))+")");
        if(!result||result.ok!==true)throw new Error(result&&result.error?result.error:"Command failed");
        var adjustment=findLayer("TonyFX FX - "+preset.name+" - ");
        if(!adjustment||!adjustment.adjustmentLayer)throw new Error("No adjustment layer was created");
        if(adjustment.index!==source.index-1)throw new Error("Adjustment layer is not directly above the scene");
        if(source.property("ADBE Effect Parade").numProperties!==before)throw new Error("Source footage was modified");
        var parade=adjustment.property("ADBE Effect Parade");
        if(!parade||parade.numProperties<1)throw new Error("Adjustment layer has no effect");
        if(!hasNonZero(parade))throw new Error("Effect contains no nonzero values");
        var stats=keyStats(parade);
        if(stats.last>=stats.first&&(Math.abs(adjustment.inPoint-stats.first)>0.001||Math.abs(adjustment.outPoint-stats.last)>0.001))throw new Error("Animated adjustment layer is not trimmed to its keyframes");
        if(stats.last<stats.first&&(Math.abs(adjustment.inPoint-source.inPoint)>0.001||Math.abs(adjustment.outPoint-source.outPoint)>0.001))throw new Error("Static adjustment layer does not span its scene");
        if(preset.effect!=="flashShake"&&preset.effect!=="punchFlicker"&&stats.maxKeys>2)throw new Error("Simple effect created more than two keyframes on one property");
    }
    var singles=[
        ["Glow Pulse","glow"],["Directional Smear","directionalBlur"],["Exposure Flash","exposure"],["Chromatic Hit","chromatic"],
        ["Clean VHS","vhs"],["Duotone","duotone"],["Ghost Zoom","ghostZoom"],["Echo Trails","echoTrail"],
        ["Radial Zoom Blur","radialZoom"],["Optical Ripple","opticalRipple"],["Soft Halation","halation"],["Flash + Shake","flashShake"],
        ["Clean Black Hit","blackHit"],["Lens Glimmer","lensGlimmer"],["Punch Flicker","punchFlicker"],["RGB Pulse","rgbPulse"]
    ];
    var paired=[["Flash Smear Cut","flashSmear"],["Zoom Blur Cut","zoomBlur"],["Black Dip Cut","blackDip"],["RGB Whip Cut","rgbWhip"]];
    try {
        $.evalFile(new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/jsx/host.jsx"));
        comp=app.project.items.addComp("__TONYFX_ADJUSTMENT_EFFECTS_TEST__",1080,1080,1,6,30);comp.openInViewer();comp.time=1;
        var source=comp.layers.addSolid([0.2,0.2,0.25],"SOURCE SCENE",1080,1080,1,4);source.inPoint=0.25;source.outPoint=4.25;
        for(var s=0;s<singles.length;s++){var preset={id:"single-"+s,name:singles[s][0],category:"Effects",tool:"effect",effect:singles[s][1],duration:6,amount:160};try{runSingle(preset,source);report.passed.push(preset.name);}catch(error){report.failed.push({id:preset.name,error:error.toString()});}}
        var outgoing=comp.layers.addSolid([0.3,0.1,0.1],"OUTGOING",1080,1080,1,3);outgoing.inPoint=0;outgoing.outPoint=2.2;
        var incoming=comp.layers.addSolid([0.1,0.1,0.3],"INCOMING",1080,1080,1,4);incoming.inPoint=2;incoming.outPoint=6;
        for(var p=0;p<paired.length;p++){select([outgoing,incoming]);var outBefore=outgoing.property("ADBE Effect Parade").numProperties,inBefore=incoming.property("ADBE Effect Parade").numProperties;try{var result=eval("("+TUF.runTool(json({id:"paired-"+p,name:paired[p][0],category:"Effects",tool:"pairedTransition",transition:paired[p][1],duration:5,amount:175}))+")");if(!result||result.ok!==true)throw new Error(result&&result.error?result.error:"Command failed");var adj=findLayer("TonyFX FX - "+paired[p][0]+" - ");if(!adj||!adj.adjustmentLayer)throw new Error("No paired adjustment layer");if(adj.outPoint-adj.inPoint>comp.frameDuration*11)throw new Error("Paired adjustment layer is longer than its transition");if(outgoing.property("ADBE Effect Parade").numProperties!==outBefore||incoming.property("ADBE Effect Parade").numProperties!==inBefore)throw new Error("Paired transition modified source footage");if(!hasNonZero(adj.property("ADBE Effect Parade")))throw new Error("Paired effect contains no nonzero values");report.passed.push(paired[p][0]);}catch(pairError){report.failed.push({id:paired[p][0],error:pairError.toString()});}}
        select([outgoing,incoming]);try{var whip=eval("("+TUF.runTool(json({id:"whip",name:"Fast Whip Left",category:"Effects",tool:"pairedWhip",direction:"left",duration:5,amount:185}))+")");if(!whip||whip.ok!==true)throw new Error(whip&&whip.error?whip.error:"Command failed");var whipAdj=findLayer("TonyFX FX - Fast Whip Left - ");if(!whipAdj||!whipAdj.adjustmentLayer||!hasNonZero(whipAdj.property("ADBE Effect Parade")))throw new Error("Whip adjustment layer is invalid");report.passed.push("Fast Whip Left");}catch(whipError){report.failed.push({id:"Fast Whip Left",error:whipError.toString()});}
        report.ok=report.failed.length===0;report.total=report.passed.length+report.failed.length;
    } catch(error) { report.failed.push({id:"setup",error:error.toString(),line:error.line||0}); }
    finally { try{if(comp)comp.remove();}catch(ignoreRemove){}try{if(original&&original instanceof CompItem)original.openInViewer();}catch(ignoreRestore){}write(); }
}());
