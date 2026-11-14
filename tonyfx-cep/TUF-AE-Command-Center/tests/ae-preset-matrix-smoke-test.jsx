(function () {
    var output = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/tonyfx_preset_matrix_test.json");
    var original = app.project ? app.project.activeItem : null;
    var testComp = null;
    var report = {ok:false, passed:[], failed:[]};
    function quote(value) { return '"' + String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r/g, "\\r").replace(/\n/g, "\\n") + '"'; }
    function stringify(value) {
        if (value === null) { return "null"; }
        var type = typeof value;
        if (type === "string") { return quote(value); }
        if (type === "number") { return isFinite(value) ? String(value) : "null"; }
        if (type === "boolean") { return value ? "true" : "false"; }
        if (value instanceof Array) { var items=[]; for(var i=0;i<value.length;i++){items.push(stringify(value[i]));} return "["+items.join(",")+"]"; }
        var pairs=[]; for(var key in value){if(value.hasOwnProperty(key)&&typeof value[key]!=="undefined"){pairs.push(quote(key)+":"+stringify(value[key]));}} return "{"+pairs.join(",")+"}";
    }
    function writeReport(value){output.encoding="UTF-8";if(output.open("w")){output.write(stringify(value));output.close();}}
    function selectOnly(layer){for(var i=1;i<=testComp.numLayers;i++){testComp.layer(i).selected=false;}layer.selected=true;}
    function run(preset,layer){selectOnly(layer);try{var raw=TUF.runTool(stringify(preset));var result=eval("("+raw+")");if(!result||result.ok!==true){throw new Error(result&&result.error?result.error:"Unknown preset failure");}report.passed.push(preset.id);}catch(error){report.failed.push({id:preset.id,error:error.toString()});}}
    var textPresets=[
        {id:"text-left",name:"Text Reveal Left",tool:"textMotion",mode:"position",direction:"left",unit:"words",duration:10,amount:58,smoothness:34},
        {id:"text-right",name:"Text Reveal Right",tool:"textMotion",mode:"position",direction:"right",unit:"words",duration:10,amount:58,smoothness:34},
        {id:"text-up",name:"Text Reveal Up",tool:"textMotion",mode:"position",direction:"up",unit:"words",duration:10,amount:48,smoothness:34},
        {id:"text-down",name:"Text Reveal Down",tool:"textMotion",mode:"position",direction:"down",unit:"words",duration:10,amount:48,smoothness:34},
        {id:"text-char-fade",name:"Letter Fade",tool:"textMotion",mode:"opacity",unit:"characters",duration:14,smoothness:22},
        {id:"text-word-fade",name:"Word Fade",tool:"textMotion",mode:"opacity",unit:"words",duration:12,smoothness:38},
        {id:"text-scale-pop",name:"Word Scale Pop",tool:"textMotion",mode:"scale",unit:"words",duration:9,smoothness:28},
        {id:"text-rotate",name:"Letter Rotate In",tool:"textMotion",mode:"rotate",unit:"characters",duration:12,smoothness:20},
        {id:"text-blur-reveal",name:"Blur Reveal",tool:"textMotion",mode:"blur",unit:"words",duration:11,smoothness:42},
        {id:"text-tracking-reveal",name:"Tracking Reveal",tool:"textMotion",mode:"tracking",unit:"characters",duration:15,smoothness:28},
        {id:"text-soft-rise",name:"Soft Word Rise",tool:"textMotion",mode:"position",direction:"up",unit:"words",duration:14,amount:30,smoothness:24},
        {id:"text-drop-in",name:"Word Drop In",tool:"textMotion",mode:"position",direction:"down",unit:"words",duration:11,amount:68,smoothness:20},
        {id:"text-pop-focus",name:"Pop + Focus",tool:"textMotion",mode:"popBlur",unit:"words",duration:11,smoothness:18},
        {id:"text-scale-punch",name:"Scale Punch",tool:"textMotion",mode:"scalePunch",unit:"words",duration:8,smoothness:14},
        {id:"text-word-rotate",name:"Word Rotate In",tool:"textMotion",mode:"rotate",unit:"words",duration:12,smoothness:20},
        {id:"text-tracking-tighten",name:"Tracking Tighten",tool:"textMotion",mode:"trackingTight",unit:"characters",duration:16,smoothness:22},
        {id:"text-wipe-left",name:"Clean Wipe Left",tool:"textMotion",mode:"wipe",direction:"left",unit:"characters",duration:13,smoothness:8},
        {id:"text-wipe-right",name:"Clean Wipe Right",tool:"textMotion",mode:"wipe",direction:"right",unit:"characters",duration:13,smoothness:8},
        {id:"text-flicker-on",name:"Flicker On",tool:"textMotion",mode:"flicker",unit:"characters",duration:8,smoothness:0},
        {id:"text-wave-rise",name:"Wave Rise",tool:"textMotion",mode:"wave",unit:"characters",duration:16,smoothness:18}
    ];
    var motionPresets=[
        {id:"move-left",name:"Slide In Left",tool:"layerMotion",mode:"position",direction:"left",variant:"normal",duration:6,amount:210},
        {id:"move-right",name:"Slide In Right",tool:"layerMotion",mode:"position",direction:"right",variant:"normal",duration:6,amount:210},
        {id:"move-up",name:"Slide In Up",tool:"layerMotion",mode:"position",direction:"up",variant:"normal",duration:6,amount:170},
        {id:"move-down",name:"Slide In Down",tool:"layerMotion",mode:"position",direction:"down",variant:"normal",duration:6,amount:170},
        {id:"overshoot-left",name:"Overshoot Left",tool:"layerMotion",mode:"position",direction:"left",variant:"overshoot",duration:8,amount:175},
        {id:"overshoot-right",name:"Overshoot Right",tool:"layerMotion",mode:"position",direction:"right",variant:"overshoot",duration:8,amount:175},
        {id:"bounce-up",name:"Bounce Up",tool:"layerMotion",mode:"position",direction:"up",variant:"bounce",duration:10,amount:150},
        {id:"scale-impact",name:"Scale Impact",tool:"layerMotion",mode:"scale",variant:"overshoot",duration:6},
        {id:"impact-shake",name:"Impact Shake",tool:"impactShake",duration:4,amount:150},
        {id:"motion-punch-in",name:"Punch In",tool:"layerMotion",mode:"punchIn",duration:18,amount:150},
        {id:"motion-punch-out",name:"Punch Out",tool:"layerMotion",mode:"punchOut",duration:18,amount:168},
        {id:"motion-spin-in",name:"Spin In",tool:"layerMotion",mode:"spin",duration:20,amount:92},
        {id:"motion-drift-left",name:"Drift Left",tool:"layerMotion",mode:"drift",direction:"left",duration:24,amount:190},
        {id:"motion-drift-right",name:"Drift Right",tool:"layerMotion",mode:"drift",direction:"right",duration:24,amount:190},
        {id:"motion-float-up",name:"Float Up",tool:"layerMotion",mode:"float",direction:"up",duration:24,amount:160},
        {id:"motion-drop-impact",name:"Drop Impact",tool:"layerMotion",mode:"drop",direction:"down",duration:18,amount:240},
        {id:"motion-rotate-snap",name:"Rotate Snap",tool:"layerMotion",mode:"rotate",duration:16,amount:28},
        {id:"motion-fade-rise",name:"Fade + Rise",tool:"layerMotion",mode:"fadeRise",direction:"up",duration:20,amount:130},
        {id:"motion-focus-push",name:"Focus Push",tool:"layerMotion",mode:"focusPush",duration:22,amount:135}
    ];
    var effects=["glow","directionalBlur","exposure","chromatic","vhs","duotone","ghostZoom","echoTrail","radialZoom","opticalRipple","halation","flashShake","blackHit","lensGlimmer","punchFlicker","rgbPulse","cameraSnap","zoomStutter"];
    try{
        $.evalFile(new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/jsx/host.jsx"));
        testComp=app.project.items.addComp("__TONYFX_PRESET_MATRIX_TEST__",1080,1080,1,4,30);testComp.openInViewer();testComp.time=0.5;
        var solid=testComp.layers.addSolid([0.15,0.18,0.22],"TonyFX Motion Test",1080,1080,1,4);
        var textLayer=testComp.layers.addText("TONYFX CLEAN TEXT MOTION");textLayer.inPoint=0;textLayer.outPoint=4;solid.inPoint=0;solid.outPoint=4;
        var originalPosition=solid.property("ADBE Transform Group").property("ADBE Position");originalPosition.setValueAtTime(0,[540,540]);originalPosition.setValueAtTime(3,[560,530]);var originalPositionKeys=originalPosition.numKeys;
        for(var t=0;t<textPresets.length;t++){run(textPresets[t],textLayer);}for(var m=0;m<motionPresets.length;m++){run(motionPresets[m],solid);}for(var e=0;e<effects.length;e++){run({id:"effect-"+effects[e],name:"Matrix "+effects[e],tool:"effect",effect:effects[e],duration:6,amount:120},solid);}
        var whipOut=testComp.layers.addSolid([0.3,0.1,0.1],"Whip Out",1080,1080,1,2),whipIn=testComp.layers.addSolid([0.1,0.1,0.3],"Whip In",1080,1080,1,3);whipOut.inPoint=0;whipOut.outPoint=1.2;whipIn.inPoint=1;whipIn.outPoint=4;selectOnly(whipOut);whipIn.selected=true;try{var whipResult=eval("("+TUF.runTool(stringify({id:"paired-whip",name:"Fast Whip Left",tool:"pairedWhip",direction:"left",duration:6,amount:120}))+")");if(!whipResult||whipResult.ok!==true)throw new Error(whipResult&&whipResult.error?whipResult.error:"Whip failed");report.passed.push("paired-whip");}catch(whipError){report.failed.push({id:"paired-whip",error:whipError.toString()});}
        var transitions=["flashSmear","zoomBlur","blackDip","rgbWhip"];
        for(var tr=0;tr<transitions.length;tr++){selectOnly(whipOut);whipIn.selected=true;try{var transitionResult=eval("("+TUF.runTool(stringify({id:"transition-"+transitions[tr],name:"Matrix "+transitions[tr],tool:"pairedTransition",transition:transitions[tr],duration:5,amount:175}))+")");if(!transitionResult||transitionResult.ok!==true)throw new Error(transitionResult&&transitionResult.error?transitionResult.error:"Transition failed");report.passed.push("transition-"+transitions[tr]);}catch(transitionError){report.failed.push({id:"transition-"+transitions[tr],error:transitionError.toString()});}}
        report.preservedManualPositionKeys=originalPosition.numKeys===originalPositionKeys;if(!report.preservedManualPositionKeys){report.failed.push({id:"non-destructive-motion",error:"Manual Position keys changed."});}report.ok=report.failed.length===0;report.total=report.passed.length+report.failed.length;
    }catch(error){report.failed.push({id:"matrix-setup",error:error.toString(),line:error.line||0});}
    finally{try{if(testComp){testComp.remove();}}catch(ignoreRemove){}try{if(original&&original instanceof CompItem){original.openInViewer();}}catch(ignoreRestore){}writeReport(report);}
}());
