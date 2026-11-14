(function () {
    var extension = "C:/Users/TUF/Documents/New project/tuf-ae-command-center";
    var output = new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_v054_text_motion_regression.json");
    var original = app.project ? app.project.activeItem : null, comp = null;
    var report = {ok:false,presets:[],captions:[],cleanup:null,error:""};

    function stringify(value) {
        if (value === null) { return "null"; }
        if (typeof value === "number" || typeof value === "boolean") { return String(value); }
        if (typeof value === "string") { return '"' + value.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n") + '"'; }
        if (value instanceof Array) { var array=[]; for(var a=0;a<value.length;a++){array.push(stringify(value[a]));} return "["+array.join(",")+"]"; }
        var pairs=[]; for(var key in value){if(value.hasOwnProperty(key)){pairs.push(stringify(key)+":"+stringify(value[key]));}} return "{"+pairs.join(",")+"}";
    }
    function parse(value) { return eval("(" + value + ")"); }
    function deselectAll(targetComp) { for(var i=1;i<=targetComp.numLayers;i++){targetComp.layer(i).selected=false;} }
    function textAnimator(layer) {
        var animators=layer.property("ADBE Text Properties").property("ADBE Text Animators");
        if(!animators){return null;}
        for(var i=1;i<=animators.numProperties;i++){
            var candidate=animators.property(i), name=String(candidate.name||"");
            if(name.indexOf("TonyFX - Text Motion - ")===0 && name.indexOf(" - Settle")<0){return candidate;}
        }
        return null;
    }
    function settleAnimator(layer) {
        var animators=layer.property("ADBE Text Properties").property("ADBE Text Animators");
        if(!animators){return null;}
        for(var i=1;i<=animators.numProperties;i++){
            var candidate=animators.property(i), name=String(candidate.name||"");
            if(name.indexOf("TonyFX - Text Motion - ")===0 && name.indexOf(" - Settle")>=0){return candidate;}
        }
        return null;
    }
    function animatorPropertyNames(animator) {
        var result=[], props=animator.property("ADBE Text Animator Properties");
        for(var i=1;i<=props.numProperties;i++){result.push(String(props.property(i).matchName));}
        return result;
    }
    function hasName(names,name) { for(var i=0;i<names.length;i++){if(names[i]===name){return true;}} return false; }
    function selectorState(animator) {
        var selector=animator.property("ADBE Text Selectors").property(1), advanced=selector.property("ADBE Text Range Advanced");
        var start=selector.property("ADBE Text Percent Start")||selector.property("Start");
        var end=selector.property("ADBE Text Percent End")||selector.property("End");
        var amount=advanced && (advanced.property("ADBE Text Selector Max Amount")||advanced.property("Amount"));
        var basedOn=advanced && advanced.property("ADBE Text Range Type2");
        return {startKeys:start?start.numKeys:0,endKeys:end?end.numKeys:0,amountKeys:amount?amount.numKeys:0,basedOn:basedOn?basedOn.value:null};
    }
    function selectorDriver(animator,driver) {
        var selector=animator.property("ADBE Text Selectors").property(1), advanced=selector.property("ADBE Text Range Advanced");
        if(driver==="end"){return selector.property("ADBE Text Percent End")||selector.property("End");}
        if(driver==="amount"){return advanced && (advanced.property("ADBE Text Selector Max Amount")||advanced.property("Amount"));}
        return selector.property("ADBE Text Percent Start")||selector.property("Start");
    }
    function isBezierAndEased(property) {
        if(!property||property.numKeys<2){return false;}
        for(var i=1;i<=property.numKeys;i++){
            if(property.keyInInterpolationType(i)!==KeyframeInterpolationType.BEZIER||property.keyOutInterpolationType(i)!==KeyframeInterpolationType.BEZIER){return false;}
            var incoming=property.keyInTemporalEase(i), outgoing=property.keyOutTemporalEase(i);
            if(!incoming.length||!outgoing.length||incoming[0].influence<30||outgoing[0].influence<30){return false;}
        }
        return true;
    }
    function animatorPropertyValue(animator,matchName) {
        var props=animator.property("ADBE Text Animator Properties");
        for(var i=1;i<=props.numProperties;i++){if(String(props.property(i).matchName)===matchName){return props.property(i).value;}}
        return null;
    }
    function vectorMagnitude(value) {
        if(value instanceof Array){var total=0;for(var i=0;i<value.length;i++){total+=Number(value[i]||0)*Number(value[i]||0);}return Math.sqrt(total);}
        return Math.abs(Number(value)||0);
    }
    function assert(condition,message){if(!condition){throw new Error(message);}}

    var presets = [
        {id:"text-left",name:"Text Reveal Left",tool:"textMotion",mode:"position",direction:"left",unit:"words",duration:12,amount:220,smoothness:30,expect:["ADBE Text Position 3D","ADBE Text Opacity","ADBE Text Blur"]},
        {id:"text-right",name:"Text Reveal Right",tool:"textMotion",mode:"position",direction:"right",unit:"words",duration:12,amount:220,smoothness:30,expect:["ADBE Text Position 3D","ADBE Text Opacity","ADBE Text Blur"]},
        {id:"text-up",name:"Text Reveal Up",tool:"textMotion",mode:"position",direction:"up",unit:"words",duration:12,amount:150,smoothness:30,expect:["ADBE Text Position 3D","ADBE Text Opacity","ADBE Text Blur"]},
        {id:"text-down",name:"Text Reveal Down",tool:"textMotion",mode:"position",direction:"down",unit:"words",duration:12,amount:150,smoothness:30,expect:["ADBE Text Position 3D","ADBE Text Opacity","ADBE Text Blur"]},
        {id:"text-char-fade",name:"Letter Fade",tool:"textMotion",mode:"opacity",unit:"characters",duration:14,smoothness:22,expect:["ADBE Text Opacity"]},
        {id:"text-word-fade",name:"Word Fade",tool:"textMotion",mode:"opacity",unit:"words",duration:12,smoothness:38,expect:["ADBE Text Opacity"]},
        {id:"text-scale-pop",name:"Word Scale Pop",tool:"textMotion",mode:"scale",unit:"words",duration:9,smoothness:28,expect:["ADBE Text Scale 3D","ADBE Text Opacity"]},
        {id:"text-rotate",name:"Letter Rotate In",tool:"textMotion",mode:"rotate",unit:"characters",duration:12,smoothness:20,expect:["ADBE Text Rotation","ADBE Text Position 3D","ADBE Text Opacity"]},
        {id:"text-blur-reveal",name:"Blur Reveal",tool:"textMotion",mode:"blur",unit:"words",duration:11,smoothness:42,expect:["ADBE Text Blur","ADBE Text Position 3D","ADBE Text Opacity"]},
        {id:"text-tracking-reveal",name:"Tracking Reveal",tool:"textMotion",mode:"tracking",unit:"characters",duration:15,smoothness:28,expect:["ADBE Text Tracking Amount","ADBE Text Blur","ADBE Text Opacity"]},
        {id:"text-soft-rise",name:"Soft Word Rise",tool:"textMotion",mode:"position",direction:"up",unit:"words",duration:14,amount:30,smoothness:24,expect:["ADBE Text Position 3D","ADBE Text Opacity"]},
        {id:"text-drop-in",name:"Word Drop In",tool:"textMotion",mode:"position",direction:"down",unit:"words",duration:12,amount:42,smoothness:20,expect:["ADBE Text Position 3D","ADBE Text Rotation","ADBE Text Opacity"]},
        {id:"text-pop-blur",name:"Pop + Focus",tool:"textMotion",mode:"popBlur",unit:"words",duration:12,smoothness:18,expect:["ADBE Text Scale 3D","ADBE Text Blur","ADBE Text Opacity"]},
        {id:"text-scale-punch",name:"Scale Punch",tool:"textMotion",mode:"scalePunch",unit:"words",duration:10,smoothness:15,expect:["ADBE Text Scale 3D","ADBE Text Blur","ADBE Text Opacity"]},
        {id:"text-rotate-words",name:"Word Rotate In",tool:"textMotion",mode:"rotate",unit:"words",duration:13,smoothness:24,expect:["ADBE Text Rotation","ADBE Text Position 3D","ADBE Text Scale 3D","ADBE Text Opacity"]},
        {id:"text-tighten",name:"Tracking Tighten",tool:"textMotion",mode:"trackingTight",unit:"characters",duration:16,smoothness:30,expect:["ADBE Text Tracking Amount","ADBE Text Blur","ADBE Text Opacity"]},
        {id:"text-wipe-left",name:"Clean Wipe Left",tool:"textMotion",mode:"wipe",direction:"left",unit:"characters",duration:13,smoothness:8,expect:["ADBE Text Position 3D","ADBE Text Opacity"],driver:"start"},
        {id:"text-wipe-right",name:"Clean Wipe Right",tool:"textMotion",mode:"wipe",direction:"right",unit:"characters",duration:13,smoothness:8,expect:["ADBE Text Position 3D","ADBE Text Opacity"],driver:"end"},
        {id:"text-flicker-on",name:"Flicker On",tool:"textMotion",mode:"flicker",unit:"characters",duration:10,smoothness:0,expect:["ADBE Text Opacity"],driver:"amount"},
        {id:"text-wave-rise",name:"Wave Rise",tool:"textMotion",mode:"wave",unit:"characters",duration:18,smoothness:36,expect:["ADBE Text Position 3D","ADBE Text Rotation","ADBE Text Blur","ADBE Text Opacity"]}
    ];

    try {
        $.evalFile(new File(extension + "/jsx/host.jsx"));
        comp=app.project.items.addComp("__TONYFX_V054_TEXT_REGRESSION__",1080,1080,1,4,30); comp.openInViewer();
        for(var p=0;p<presets.length;p++){
            deselectAll(comp); var layer=comp.layers.addText("TONYFX MOTION TEST"); layer.inPoint=.25; layer.outPoint=3.5; layer.selected=true;
            var options=presets[p], result=parse(TUF.runTool(stringify(options))); assert(result.ok,"Preset failed: "+options.id+" "+(result.error||""));
            var animator=textAnimator(layer); assert(!!animator,"No animator: "+options.id); assert(animator.name==="TonyFX - Text Motion - "+options.name,"Wrong animator name: "+options.id);
            var names=animatorPropertyNames(animator); for(var x=0;x<options.expect.length;x++){assert(hasName(names,options.expect[x]),"Missing "+options.expect[x]+" in "+options.id);}
            var selector=selectorState(animator), driver=options.driver||"start", driverProperty=selectorDriver(animator,driver);
            if(driver==="start"){assert(selector.startKeys===2,"Start selector must have two keys: "+options.id);}
            if(driver==="end"){assert(selector.endKeys===2 && selector.startKeys===0,"Reverse wipe must animate End only: "+options.id);}
            if(driver==="amount"){assert(selector.amountKeys>=6,"Flicker must animate Amount: "+options.id);}
            if(driver!=="amount"){assert(isBezierAndEased(driverProperty),"Selector must use visible Easy Ease: "+options.id);}
            if(hasName(options.expect,"ADBE Text Position 3D")){assert(vectorMagnitude(animatorPropertyValue(animator,"ADBE Text Position 3D"))>=80,"Position motion is too subtle: "+options.id);}
            if(hasName(options.expect,"ADBE Text Scale 3D")){assert(vectorMagnitude(animatorPropertyValue(animator,"ADBE Text Scale 3D"))>=100,"Scale motion is too subtle: "+options.id);}
            var settle=settleAnimator(layer);
            if(settle){var settleState=selectorState(settle);assert(settleState.amountKeys===3,"Settle animator must use exactly three amount keys: "+options.id);assert(isBezierAndEased(selectorDriver(settle,"amount")),"Settle animator must use Easy Ease: "+options.id);}
            report.presets.push({id:options.id,animator:animator.name,properties:names,selector:selector,settle:!!settle}); layer.remove();
        }

        deselectAll(comp); var cleanupLayer=comp.layers.addText("CLEANUP TEST"); cleanupLayer.inPoint=0;cleanupLayer.outPoint=3;cleanupLayer.selected=true;
        parse(TUF.runTool(stringify(presets[4]))); parse(TUF.runTool(stringify(presets[17])));
        var cleanupAnimators=cleanupLayer.property("ADBE Text Properties").property("ADBE Text Animators");
        report.cleanup={count:cleanupAnimators.numProperties,name:cleanupAnimators.numProperties?cleanupAnimators.property(1).name:""};
        assert(report.cleanup.count===1,"Switching presets left stacked TonyFX animators.");
        assert(report.cleanup.name==="TonyFX - Text Motion - Clean Wipe Right","Switching presets left the wrong animator active."); cleanupLayer.remove();

        var animations=["wordFade","letterFade","pop","scalePunch","wipeLeft","wipeRight","blurReveal","trackingTight","flipX","flipY","depthPush","waveRise"];
        var caption={start:0,end:2,text:"ONE TWO THREE",words:[{text:"ONE",start:0,end:.25},{text:"TWO",start:.7,end:.95},{text:"THREE",start:1.4,end:1.75}]};
        for(var c=0;c<animations.length;c++){
            deselectAll(comp); var before=comp.numLayers;
            var captionResult=parse(TUF.createCaptions(stringify({captions:[caption],compIn:0,sourceDuration:2,compDuration:2,reverse:false,placement:"center",fontSize:48,language:"en",animation:animations[c],textEffect:{id:"none"}})));
            assert(captionResult.ok && comp.numLayers===before+1,"Caption animation failed: "+animations[c]);
            var captionLayer=comp.layer(1), captionAnimator=textAnimator(captionLayer), captionNames=animatorPropertyNames(captionAnimator), captionSelector=selectorState(captionAnimator);
            assert(captionAnimator.name.indexOf("TonyFX - Text Motion - Caption")===0,"Caption did not use common motion engine: "+animations[c]);
            report.captions.push({id:animations[c],animator:captionAnimator.name,properties:captionNames,selector:captionSelector}); captionLayer.remove();
        }
        report.ok=true;
    } catch(error){report.error=error.toString();report.line=error.line||0;}
    finally{
        try{if(comp)comp.remove();}catch(ignoreRemove){}
        try{if(original && original instanceof CompItem)original.openInViewer();}catch(ignoreRestore){}
        output.encoding="UTF-8";if(output.open("w")){output.write(stringify(report));output.close();}
    }
}());
