(function () {
    var extension = "C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center";
    var output = new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_v052_caption_textfx_matrix.json");
    var original = app.project.activeItem, comp = null, report = {ok:false, captions:[], effects:[], motions:[], error:""};
    function stringify(value) {
        if (value === null) { return "null"; }
        if (typeof value === "number" || typeof value === "boolean") { return String(value); }
        if (typeof value === "string") { return '"' + value.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n") + '"'; }
        if (value instanceof Array) { var array=[]; for(var a=0;a<value.length;a++){array.push(stringify(value[a]));} return "["+array.join(",")+"]"; }
        var pairs=[]; for(var key in value){if(value.hasOwnProperty(key)){pairs.push(stringify(key)+":"+stringify(value[key]));}} return "{"+pairs.join(",")+"}";
    }
    function parse(value) { return eval("(" + value + ")"); }
    function selectorStart(layer) {
        var animators=layer.property("ADBE Text Properties").property("ADBE Text Animators");
        if (!animators || !animators.numProperties) { return null; }
        var selector=animators.property(1).property("ADBE Text Selectors").property(1);
        return selector && (selector.property("ADBE Text Percent Start") || selector.property("Start"));
    }
    try {
        $.evalFile(new File(extension + "/jsx/host.jsx"));
        comp=app.project.items.addComp("__TONYFX_V052_CAPTION_MATRIX__",1080,1080,1,5,30); comp.openInViewer();
        var animations=["wordFade","letterFade","pop","scalePunch","wipeLeft","wipeRight","blurReveal","trackingTight","flipX","flipY","depthPush","waveRise","none"];
        var caption={start:0,end:2,text:"ONE TWO THREE",words:[{text:"ONE",start:0,end:.25},{text:"TWO",start:.7,end:.95},{text:"THREE",start:1.4,end:1.75}]};
        for(var i=0;i<animations.length;i++) {
            var before=comp.numLayers;
            var result=parse(TUF.createCaptions(stringify({captions:[caption],compIn:0,sourceDuration:2,compDuration:2,reverse:false,placement:"center",fontSize:48,language:"en",animation:animations[i],textEffect:{id:"none"}})));
            if(!result.ok || comp.numLayers!==before+1){throw new Error("Caption animation failed: "+animations[i]+" "+(result.error||"no layer"));}
            var layer=comp.layer(1), start=selectorStart(layer), keys=start?start.numKeys:0;
            if(animations[i]!=="none" && keys<2){throw new Error("Caption selector missing keys: "+animations[i]);}
            if((animations[i]==="wordFade" || animations[i]==="pop" || animations[i]==="scalePunch") && keys<6){throw new Error("Word timestamps missing: "+animations[i]);}
            report.captions.push({id:animations[i],keys:keys,animators:layer.property("ADBE Text Properties").property("ADBE Text Animators").numProperties});
            layer.remove();
        }
        var text=comp.layers.addText("TONYFX TEXT FX"); text.inPoint=0;text.outPoint=3;text.selected=true;
        var effects=["cleanReveal","deepShadow","longShadow","dualGlow","neonTube","bevelEdge","sweep","flipX","flipY","depthPush","cascade3d","blurTrack","impact3d","softBloom","chromaticShadow","echoTrail","focusSnap","kineticTilt"];
        for(var e=0;e<effects.length;e++) {
            text.selected=true;
            var fx=parse(TUF.applyTextEffect(stringify({id:effects[e],strength:100,duration:18})));
            if(!fx.ok){throw new Error("Text FX failed: "+effects[e]+" "+fx.error);}
            var animatorCount=text.property("ADBE Text Properties").property("ADBE Text Animators").numProperties;
            var effectCount=text.property("ADBE Effect Parade").numProperties;
            if(animatorCount+effectCount<1){throw new Error("Text FX created nothing: "+effects[e]);}
            report.effects.push({id:effects[e],animators:animatorCount,effects:effectCount});
        }
        text.remove();
        var motions=[
            {name:"Position",mode:"position",unit:"words",direction:"left"},{name:"Scale",mode:"scale",unit:"words"},{name:"Rotate",mode:"rotate",unit:"characters"},
            {name:"Blur",mode:"blur",unit:"characters"},{name:"Pop Blur",mode:"popBlur",unit:"words"},{name:"Scale Punch",mode:"scalePunch",unit:"words"},
            {name:"Tracking Tight",mode:"trackingTight",unit:"characters"},{name:"Wipe",mode:"wipe",unit:"characters",direction:"right"},{name:"Wave",mode:"wave",unit:"characters"},
            {name:"Flicker",mode:"flicker",unit:"words"},{name:"Tracking",mode:"tracking",unit:"characters"},{name:"Opacity",mode:"opacity",unit:"words"}
        ];
        for(var m=0;m<motions.length;m++) {
            var motionLayer=comp.layers.addText("TONYFX MOTION");motionLayer.inPoint=.5;motionLayer.outPoint=3;motionLayer.selected=true;
            var motion=motions[m];motion.tool="textMotion";motion.duration=12;motion.amount=72;motion.stagger=0;
            var motionResult=parse(TUF.runTool(stringify(motion)));if(!motionResult.ok){throw new Error("Text motion failed: "+motion.name+" "+motionResult.error);}
            var motionAnimators=motionLayer.property("ADBE Text Properties").property("ADBE Text Animators"),motionSelector=motionAnimators.property(1).property("ADBE Text Selectors").property(1),motionStart=motionSelector.property("ADBE Text Percent Start")||motionSelector.property("Start");
            if(!motionStart||motionStart.numKeys<2||Math.abs(motionStart.keyTime(1)-motionLayer.inPoint)>.001){throw new Error("Text motion did not begin at in-point: "+motion.name);}
            report.motions.push({id:motion.name,keys:motionStart.numKeys,first:Number(motionStart.keyTime(1).toFixed(3))});motionLayer.remove();
        }
        report.ok=true;
    } catch(error) { report.error=error.toString(); report.line=error.line||0; }
    finally {
        try{if(comp)comp.remove();}catch(ignoreRemove){}
        try{if(original && original instanceof CompItem)original.openInViewer();}catch(ignoreRestore){}
        output.encoding="UTF-8";if(output.open("w")){output.write(stringify(report));output.close();}
    }
}());
