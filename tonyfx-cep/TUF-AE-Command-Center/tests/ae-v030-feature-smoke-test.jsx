(function () {
    var output = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/tonyfx_v030_feature_test.json");
    var original = app.project ? app.project.activeItem : null;
    var testComp = null;
    var report = {ok:false,passed:[],failed:[]};
    function quote(value){return '"'+String(value).replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n")+'"';}
    function stringify(value){if(value===null){return"null";}var type=typeof value;if(type==="string"){return quote(value);}if(type==="number"){return isFinite(value)?String(value):"null";}if(type==="boolean"){return value?"true":"false";}if(value instanceof Array){var values=[];for(var i=0;i<value.length;i++){values.push(stringify(value[i]));}return"["+values.join(",")+"]";}var pairs=[];for(var key in value){if(value.hasOwnProperty(key)&&typeof value[key]!=="undefined"){pairs.push(quote(key)+":"+stringify(value[key]));}}return"{"+pairs.join(",")+"}";}
    function parse(raw){return eval("("+raw+")");}
    function write(value){output.encoding="UTF-8";if(output.open("w")){output.write(stringify(value));output.close();}}
    function expect(condition,id,message){if(condition){report.passed.push(id);}else{report.failed.push({id:id,error:message});}}
    function selectOnly(layer){for(var i=1;i<=testComp.numLayers;i++){testComp.layer(i).selected=false;}layer.selected=true;}
    function effectByName(layer,name){var effects=layer.property("ADBE Effect Parade");for(var i=1;i<=effects.numProperties;i++){if(effects.property(i).name===name){return effects.property(i);}}return null;}
    try {
        $.evalFile(new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/jsx/host.jsx"));
        testComp=app.project.items.addComp("__TONYFX_V030_FEATURE_TEST__",1080,1080,1,8,30);
        testComp.openInViewer();
        testComp.time=0.5;
        var textLayer=testComp.layers.addText("TONYFX FEATURE TEST");
        textLayer.inPoint=0;textLayer.outPoint=8;selectOnly(textLayer);
        var style=parse(TUF.applyTextStyle(stringify({font:"Arial-BoldMT",fontSize:64,fill:[242,248,255],strokeEnabled:false,stroke:[0,0,0],strokeWidth:0,shadowEnabled:true,shadowColor:[0,0,0],shadowOpacity:72,shadowDirection:135,shadowDistance:12,shadowSoftness:28,glowEnabled:true,glowIntensity:1.35,glowRadius:48})));
        expect(style.ok===true,"text-style-response",style.error||"Text style failed");
        var textDoc=textLayer.property("ADBE Text Properties").property("ADBE Text Document").value;
        expect(Math.abs(textDoc.fontSize-64)<0.01&&!textDoc.applyStroke,"text-style-document","Text document values were not written");
        var shadow=effectByName(textLayer,"TonyFX - Text Shadow"),glow=effectByName(textLayer,"TonyFX - Text Glow");
        expect(!!shadow&&!!glow,"text-style-effects","Text shadow or glow missing");
        if(shadow){expect(Number(shadow.property(2).value)>0&&Number(shadow.property(4).value)>0,"text-shadow-values","Text shadow values remained zero");}
        if(glow){expect(Number(glow.property(3).value)>0&&Number(glow.property(4).value)>0,"text-glow-values","Text glow values remained zero");}

        var textMotion=parse(TUF.runTool(stringify({name:"Pop + Focus",tool:"textMotion",mode:"popBlur",unit:"words",duration:11,smoothness:18})));
        expect(textMotion.ok===true,"text-motion-response",textMotion.error||"Text motion failed");
        var animators=textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
        expect(animators.numProperties>0,"text-motion-created","Text animator was not created");
        var lastAnimator=animators.property(animators.numProperties),selector=lastAnimator.property("ADBE Text Selectors").property(1),startProp=selector.property("ADBE Text Percent Start")||selector.property("Start");
        expect(startProp&&startProp.numKeys===2&&startProp.keyValue(1)===0&&startProp.keyValue(2)===100,"text-motion-reveal","Text reveal does not animate cleanly from hidden to visible");

        var solid=testComp.layers.addSolid([0.16,0.2,0.25],"TonyFX Motion Target",500,500,1,8);solid.inPoint=0;solid.outPoint=8;selectOnly(solid);
        var motion=parse(TUF.runTool(stringify({name:"Punch In",tool:"layerMotion",mode:"punchIn",duration:18,amount:150})));
        expect(motion.ok===true,"motion-response",motion.error||"Motion preset failed");
        var motionFx=effectByName(solid,"TonyFX - Punch In"),scale=motionFx?(motionFx.property("Scale Height")||motionFx.property(4)):null;
        expect(scale&&scale.numKeys===3,"motion-three-keys","Punch motion does not contain three meaningful scale keys");
        if(scale){expect(scale.keyValue(1)<70&&scale.keyValue(2)>108&&Math.abs(scale.keyValue(3)-100)<0.01,"motion-values","Punch motion values are too subtle or incorrect");}

        var beforeIcons=testComp.numLayers;
        var iconResult=parse(TUF.createIcon(stringify({icon:"star",color:[255,210,90],size:190})));
        expect(iconResult.ok===true&&testComp.numLayers===beforeIcons+1,"icon-star",iconResult.error||"Star icon was not created");
        var iconLayer=testComp.layer(1);
        expect(iconLayer.property("ADBE Root Vectors Group").numProperties>0,"icon-vector-content","Icon has no editable vector paths");

        var captionResult=parse(TUF.createCaptions(stringify({language:"en",compIn:1,placement:"bottom",animation:"wordFade",fontSize:48,captions:[{start:0,end:1.1,text:"THIS IS TONYFX"},{start:1.2,end:2.3,text:"OFFLINE CAPTIONS"},{start:2.4,end:3.5,text:"مرحبا بكم"}]})));
        expect(captionResult.ok===true,"caption-response",captionResult.error||"Caption creation failed");
        var captionCount=0,captionSafe=true,captionAnimated=true;
        for(var l=1;l<=testComp.numLayers;l++){
            var layer=testComp.layer(l);
            if(layer.name.indexOf("CAPTION ")===0){captionCount++;var pos=layer.property("ADBE Transform Group").property("ADBE Position").value;if(pos[0]!==540||pos[1]>900){captionSafe=false;}var a=layer.property("ADBE Text Properties").property("ADBE Text Animators");if(!a||a.numProperties<1){captionAnimated=false;}}
        }
        expect(captionCount===3,"caption-count","Expected 3 caption layers, got "+captionCount);
        expect(captionSafe,"caption-safe-area","Caption placement left the square safe area");
        expect(captionAnimated,"caption-animation","A caption reveal animator is missing");
        report.ok=report.failed.length===0;
        report.total=report.passed.length+report.failed.length;
    } catch(error) {
        report.failed.push({id:"feature-test-setup",error:error.toString(),line:error.line||0});
    } finally {
        try{if(testComp){testComp.remove();}}catch(ignoreRemove){}
        try{if(original&&original instanceof CompItem){original.openInViewer();}}catch(ignoreRestore){}
        report.ok=report.failed.length===0;
        write(report);
    }
}());
