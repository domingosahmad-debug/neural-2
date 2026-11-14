(function () {
    var extension = "C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center";
    var output = new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_v052_live_result.json");
    var report = {ok:false,caption:{},graph:{},builder:{},error:""}, original = app.project.activeItem, comps = [];
    function stringify(value) {
        if (value === null) { return "null"; }
        if (typeof value === "number" || typeof value === "boolean") { return String(value); }
        if (typeof value === "string") { return '"' + value.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n") + '"'; }
        if (value instanceof Array) { var array=[]; for(var a=0;a<value.length;a++){array.push(stringify(value[a]));} return "["+array.join(",")+"]"; }
        var pairs=[]; for(var key in value){if(value.hasOwnProperty(key)){pairs.push(stringify(key)+":"+stringify(value[key]));}} return "{"+pairs.join(",")+"}";
    }
    function parse(value) { return eval("(" + value + ")"); }
    function selectOnly(layer) { for (var i=1;i<=layer.containingComp.numLayers;i++) { layer.containingComp.layer(i).selected=false; } layer.selected=true; }
    try {
        $.evalFile(new File(extension + "/jsx/host.jsx"));
        var captionComp=app.project.items.addComp("__TONYFX_V052_CAPTION__",1080,1080,1,4,30); comps.push(captionComp); captionComp.openInViewer();
        var captionPayload={captions:[{start:0,end:2,text:"ONE TWO THREE",words:[{text:"ONE",start:0,end:.3},{text:"TWO",start:.7,end:1},{text:"THREE",start:1.4,end:1.8}]}],compIn:0,sourceDuration:2,compDuration:2,reverse:false,placement:"center",fontSize:48,language:"en",animation:"wordFade",textEffect:{id:"none"}};
        var captionResult=parse(TUF.createCaptions(stringify(captionPayload))); if(!captionResult.ok)throw new Error(captionResult.error);
        var captionLayer=captionComp.layer(1),animators=captionLayer.property("ADBE Text Properties").property("ADBE Text Animators"),selector=animators.property(1).property("ADBE Text Selectors").property(1),startProp=selector.property("ADBE Text Percent Start")||selector.property("Start");
        report.caption={layers:captionComp.numLayers,keys:startProp.numKeys,times:[]}; for(var ck=1;ck<=startProp.numKeys;ck++){report.caption.times.push(Number(startProp.keyTime(ck).toFixed(3)));} if(startProp.numKeys<6)throw new Error("Word timing did not create per-word keys.");
        var graphComp=app.project.items.addComp("__TONYFX_V052_GRAPH__",1080,1080,1,2,30); comps.push(graphComp); graphComp.openInViewer(); var solid=graphComp.layers.addSolid([.2,.2,.2],"GRAPH",1080,1080,1,2),scale=solid.property("ADBE Transform Group").property("ADBE Scale"); scale.setValueAtTime(0,[100,100]);scale.setValueAtTime(1,[130,130]);scale.setSelectedAtKey(1,true);scale.setSelectedAtKey(2,true);scale.selected=true;
        var graphResult=parse(TUF.runTool(stringify({name:"Custom Test",tool:"ease",curve:"customBezier",bezier:[.09,.72,.94,.27]})));if(!graphResult.ok)throw new Error(graphResult.error);report.graph={keys:scale.numKeys,outInfluence:scale.keyOutTemporalEase(1)[0].influence,inInfluence:scale.keyInTemporalEase(2)[0].influence};
        var sourceComp=app.project.items.addComp("__TONYFX_V052_SOURCE__",1080,1080,1,4,30);comps.push(sourceComp);sourceComp.openInViewer();var one=sourceComp.layers.addSolid([.3,.1,.1],"SOURCE ONE",1080,1080,1,4),two=sourceComp.layers.addSolid([.1,.2,.4],"SOURCE TWO",1080,1080,1,4);one.selected=true;two.selected=true;
        var blueprint={fps:30,shots:[{index:1,startTime:0,endTime:1,zoomDirection:"in",zoomRatio:1.1,advancedCurve:{controls:[.09,.72,.94,.27]}},{index:2,startTime:1,endTime:2,zoomDirection:"out",zoomRatio:.9,advancedCurve:{controls:[.09,.72,.94,.27]}}],transitions:[{time:1,primary:"directional_smear",durationFrames:7,curve:"0.41, -0.12, 0.59, 1.12",aeRecipe:[{effect:"Directional Blur",settings:{"Blur Length":67}}]}]};
        var build=parse(TUF.buildOfflineEdit(stringify({blueprint:blueprint,sourceName:"LIVE TEST"})));if(!build.ok)throw new Error(build.error);var built=app.project.activeItem;comps.push(built);report.builder={name:build.compName,count:build.count,layers:built.numLayers};if(build.count!==2)throw new Error("Offline builder scene count mismatch.");
        report.ok=true;
    } catch(error) { report.error=error.toString(); report.line=error.line||0; }
    finally {
        for(var i=comps.length-1;i>=0;i--){try{if(comps[i])comps[i].remove();}catch(ignoreRemove){}}
        try{if(original && original instanceof CompItem){original.openInViewer();}}catch(ignoreRestore){}
        output.encoding="UTF-8"; if(output.open("w")){output.write(stringify(report));output.close();}
    }
}());
