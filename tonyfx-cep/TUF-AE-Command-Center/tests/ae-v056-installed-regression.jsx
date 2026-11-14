(function () {
    var extension = "C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center";
    var output = new File(extension + "/tests/_v056_installed_result.json");
    var original = app.project ? app.project.activeItem : null, comps = [], report = {ok:false,text:{},caption:{},graph:{},builder:{},error:""};

    function stringify(value) {
        if (value === null) { return "null"; }
        if (typeof value === "number" || typeof value === "boolean") { return String(value); }
        if (typeof value === "string") { return '"' + value.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n") + '"'; }
        if (value instanceof Array) { var array=[]; for(var a=0;a<value.length;a++){array.push(stringify(value[a]));} return "["+array.join(",")+"]"; }
        var pairs=[]; for(var key in value){if(value.hasOwnProperty(key)){pairs.push(stringify(key)+":"+stringify(value[key]));}} return "{"+pairs.join(",")+"}";
    }
    function parse(value) { return eval("(" + value + ")"); }
    function assert(condition, message) { if (!condition) { throw new Error(message); } }
    function animatorBySuffix(layer, suffix) {
        var animators=layer.property("ADBE Text Properties").property("ADBE Text Animators");
        for(var i=1;i<=animators.numProperties;i++){var candidate=animators.property(i);if(String(candidate.name||"").indexOf(suffix)>=0){return candidate;}}
        return null;
    }
    function selectorKeys(animator, propertyName) {
        var selector=animator.property("ADBE Text Selectors").property(1);
        var property=selector.property(propertyName) || selector.property(propertyName === "ADBE Text Percent Start" ? "Start" : "End");
        return property ? property.numKeys : 0;
    }
    function selectOnly(comp, layer) { for(var i=1;i<=comp.numLayers;i++){comp.layer(i).selected=false;} layer.selected=true; }

    try {
        $.evalFile(new File(extension + "/jsx/host.jsx"));

        var textComp=app.project.items.addComp("__TONYFX_V056_TEXT__",1080,1080,1,6,30); comps.push(textComp); textComp.openInViewer(); textComp.time=1;
        var textPayload={text:"VISIBLE TONYFX TEXT",placement:"center",durationFrames:120,matchedExit:true,exitDuration:20,animation:{id:"text-left",name:"Text Reveal Left",tool:"textMotion",mode:"position",direction:"left",unit:"words",duration:20,amount:240,smoothness:28},textEffect:{id:"none"},style:{fontSize:64,fillColor:[1,1,1],shadow:true}};
        var textResult=parse(TUF.createStyledText(stringify(textPayload))); assert(textResult.ok,textResult.error||"Styled text failed.");
        var textLayer=textComp.layer(1), entry=animatorBySuffix(textLayer," - IN"), exit=animatorBySuffix(textLayer," - OUT");
        assert(entry && exit,"Text must contain separate matched IN and OUT animators.");
        assert(selectorKeys(entry,"ADBE Text Percent Start")===2,"Text entry must have two selector keys.");
        assert(selectorKeys(exit,"ADBE Text Percent End")===2,"Text exit must have two selector keys.");
        report.text={layer:textLayer.name,entry:entry.name,exit:exit.name,inPoint:textLayer.inPoint,outPoint:textLayer.outPoint};

        var beforeCaptions=textComp.numLayers, captionPayload={captions:[{start:0,end:3.5,text:"ONE TWO THREE",words:[{text:"ONE",start:0,end:.4},{text:"TWO",start:1,end:1.4},{text:"THREE",start:2,end:2.5}]}],compIn:0,sourceDuration:3.5,compDuration:3.5,reverse:false,placement:"bottom",fontSize:48,language:"en",animation:"letterFade",matchedExit:true,exitDuration:20,textEffect:{id:"none"}};
        var captionResult=parse(TUF.createCaptions(stringify(captionPayload))); assert(captionResult.ok && textComp.numLayers===beforeCaptions+1,captionResult.error||"Caption creation failed.");
        var captionLayer=textComp.layer(1), captionIn=animatorBySuffix(captionLayer," - IN"), captionOut=animatorBySuffix(captionLayer," - OUT");
        assert(captionIn && captionOut,"Caption must contain matched IN and OUT animators.");
        report.caption={entry:captionIn.name,exit:captionOut.name,entryKeys:selectorKeys(captionIn,"ADBE Text Percent Start"),exitKeys:selectorKeys(captionOut,"ADBE Text Percent End")};

        var graphComp=app.project.items.addComp("__TONYFX_V056_GRAPH__",1080,1080,1,2,30); comps.push(graphComp); graphComp.openInViewer();
        var graphLayer=graphComp.layers.addSolid([.2,.2,.2],"DECREASING GRAPH",1080,1080,1,2), scale=graphLayer.property("ADBE Transform Group").property("ADBE Scale");
        scale.setValueAtTime(0,[130,130]); scale.setValueAtTime(1,[100,100]); scale.setSelectedAtKey(1,true); scale.setSelectedAtKey(2,true); scale.selected=true;
        var graphResult=parse(TUF.runTool(stringify({name:"TonyFX Approved Speed Ramp",tool:"ease",curve:"customBezier",bezier:[.09,.72,.94,.27]}))); assert(graphResult.ok,graphResult.error||"Decreasing graph failed.");
        var outEase=scale.keyOutTemporalEase(1), inEase=scale.keyInTemporalEase(2);
        assert(outEase.length && inEase.length,"Decreasing graph has no temporal ease.");
        report.graph={outSpeed:outEase[0].speed,inSpeed:inEase[0].speed,outInfluence:outEase[0].influence,inInfluence:inEase[0].influence};

        var sourceComp=app.project.items.addComp("__TONYFX_V056_SOURCE__",1080,1080,1,5,30); comps.push(sourceComp); sourceComp.openInViewer();
        var one=sourceComp.layers.addSolid([.3,.1,.1],"ANIYA SMILE CLOSE",1080,1080,1,5), two=sourceComp.layers.addSolid([.1,.2,.4],"CARL REACTION CLOSE",1080,1080,1,5), three=sourceComp.layers.addSolid([.1,.4,.2],"COUPLE EMBRACE",1080,1080,1,5);
        one.selected=true; two.selected=true; three.selected=true;
        var blueprint={fps:30,shots:[
            {index:1,startTime:0,endTime:1,zoomDirection:"out",advancedCurve:{controls:[.09,.72,.94,.27]},semantic:{keywords:["aniya","smile"]}},
            {index:2,startTime:1,endTime:2,zoomDirection:"in",advancedCurve:{controls:[.09,.72,.94,.27]},semantic:{keywords:["carl","reaction"]}},
            {index:3,startTime:2,endTime:3,zoomDirection:"out",advancedCurve:{controls:[.09,.72,.94,.27]},semantic:{keywords:["couple","embrace"]}}
        ],transitions:[{time:1,primary:"whip_left",components:[{family:"white_flash"},{family:"directional_smear"}],durationFrames:7,curve:"0.09,0.72,0.94,0.27"}]};
        var build=parse(TUF.buildOfflineEdit(stringify({blueprint:blueprint,sourceName:"V056 LIVE TEST",blurMo:true,fullStack:true}))); assert(build.ok,build.error||"Offline builder failed.");
        var built=app.project.activeItem; comps.push(built); var sceneNames=[], muted=true, sceneCount=0, adjustmentCount=0;
        for(var l=1;l<=built.numLayers;l++){var layer=built.layer(l);if(layer.adjustmentLayer){adjustmentCount++;}else if(String(layer.name).indexOf("AUTO SCENE ")===0){sceneCount++;sceneNames.push(layer.name);if(layer.audioEnabled){muted=false;}}}
        assert(sceneCount===3,"Offline builder scene count mismatch."); assert(muted,"Offline builder left source audio enabled."); assert(sceneNames[0]!==sceneNames[1] && sceneNames[1]!==sceneNames[2],"Offline builder repeated adjacent footage."); assert(adjustmentCount>=5,"Offline builder did not create full scene and transition stacks.");
        report.builder={comp:built.name,scenes:sceneNames,adjustments:adjustmentCount,muted:muted};
        report.ok=true;
    } catch(error) { report.error=error.toString(); report.line=error.line||0; }
    finally {
        for(var i=comps.length-1;i>=0;i--){try{if(comps[i]){comps[i].remove();}}catch(ignoreRemove){}}
        try{if(original && original instanceof CompItem){original.openInViewer();}}catch(ignoreRestore){}
        output.encoding="UTF-8"; if(output.open("w")){output.write(stringify(report));output.close();}
    }
}());
