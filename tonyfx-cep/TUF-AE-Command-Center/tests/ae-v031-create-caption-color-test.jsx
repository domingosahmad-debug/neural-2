(function () {
    var output = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/tonyfx_v031_create_caption_color_test.json");
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
    function animatorByName(layer,name){var animators=layer.property("ADBE Text Properties").property("ADBE Text Animators");for(var i=1;i<=animators.numProperties;i++){if(animators.property(i).name===name){return animators.property(i);}}return null;}
    try {
        $.evalFile(new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/jsx/host.jsx"));
        testComp=app.project.items.addComp("__TONYFX_V031_CREATE_TEST__",1080,1080,1,8,30);
        testComp.openInViewer();testComp.time=0.5;
        var textLayer=testComp.layers.addText("TONYFX 3D TEXT");textLayer.inPoint=0;textLayer.outPoint=8;selectOnly(textLayer);

        var matrixIds=["cleanReveal","deepShadow","longShadow","dualGlow","neonTube","bevelEdge","sweep","flipX","flipY","depthPush","cascade3d","blurTrack","impact3d"];
        for(var m=0;m<matrixIds.length;m++){
            var matrixResult=parse(TUF.applyTextEffect(stringify({id:matrixIds[m],strength:105,duration:18})));
            expect(matrixResult.ok===true,"matrix-"+matrixIds[m],matrixResult.error||("Text treatment failed: "+matrixIds[m]));
            var treatmentCount=0,effects=textLayer.property("ADBE Effect Parade"),animators=textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
            for(var me=1;me<=effects.numProperties;me++){if(String(effects.property(me).name).indexOf("TonyFX - Text FX")===0){treatmentCount++;}}
            for(var ma=1;ma<=animators.numProperties;ma++){if(String(animators.property(ma).name).indexOf("TonyFX - Text FX")===0){treatmentCount++;}}
            expect(treatmentCount>0,"matrix-content-"+matrixIds[m],"Text treatment created no editable AE properties: "+matrixIds[m]);
        }

        var glowResult=parse(TUF.applyTextEffect(stringify({id:"dualGlow",strength:115,duration:18})));
        expect(glowResult.ok===true,"dual-glow-response",glowResult.error||"Dual Glow failed");
        var coreGlow=effectByName(textLayer,"TonyFX - Text FX - Dual Glow Core"),bloomGlow=effectByName(textLayer,"TonyFX - Text FX - Dual Glow Bloom");
        expect(!!coreGlow&&!!bloomGlow,"dual-glow-effects","Dual Glow did not create both editable glow passes");
        if(coreGlow){expect(Number(coreGlow.property(3).value)>0&&Number(coreGlow.property(4).value)>0,"dual-glow-values","Dual Glow values remained zero");}

        var flipResult=parse(TUF.applyTextEffect(stringify({id:"flipX",strength:100,duration:20})));
        expect(flipResult.ok===true,"flip-x-response",flipResult.error||"3D Flip X failed");
        var flipAnimator=animatorByName(textLayer,"TonyFX - Text FX - 3D Flip X");
        expect(!!flipAnimator,"flip-x-animator","3D Flip X animator was not created");
        if(flipAnimator){var flipProps=flipAnimator.property("ADBE Text Animator Properties"),flipRotation=flipProps.property("ADBE Text Rotation X");expect(flipRotation&&Math.abs(Number(flipRotation.value))>40,"flip-x-values","3D X rotation is missing or too subtle");}

        var depthResult=parse(TUF.applyTextEffect(stringify({id:"depthPush",strength:120,duration:22})));
        expect(depthResult.ok===true,"depth-push-response",depthResult.error||"3D Depth Push failed");
        var depthAnimator=animatorByName(textLayer,"TonyFX - Text FX - 3D Depth Push");
        expect(!!depthAnimator,"depth-push-animator","3D Depth Push animator was not created");
        if(depthAnimator){var depthPosition=depthAnimator.property("ADBE Text Animator Properties").property("ADBE Text Position 3D");expect(depthPosition&&depthPosition.value.length===3&&depthPosition.value[2]<-200,"depth-push-values","3D depth offset is missing or too subtle");}

        var captions=parse(TUF.createCaptions(stringify({language:"en",compIn:2,placement:"center",animation:"flipY",fontSize:54,style:{font:"Arial-BoldMT",fontSize:54,fill:[255,185,205],strokeEnabled:false,stroke:[0,0,0],strokeWidth:0,shadowEnabled:true,shadowColor:[0,0,0],shadowOpacity:74,shadowDirection:135,shadowDistance:10,shadowSoftness:24,glowEnabled:true,glowIntensity:1.25,glowRadius:36},textEffect:{id:"neonTube",strength:90,duration:14},captions:[{start:0,end:1.4,text:"CAPTION STYLE TEST"}]})));
        expect(captions.ok===true,"caption-styled-response",captions.error||"Styled caption creation failed");
        var captionLayer=null;for(var l=1;l<=testComp.numLayers;l++){if(testComp.layer(l).name.indexOf("CAPTION ")===0){captionLayer=testComp.layer(l);break;}}
        expect(!!captionLayer,"caption-layer","Styled caption layer was not created");
        if(captionLayer){
            var doc=captionLayer.property("ADBE Text Properties").property("ADBE Text Document").value;
            expect(doc.fillColor[0]>.9&&doc.fillColor[1]<.85,"caption-style-color","Caption fill style was not transferred from the panel payload");
            expect(!!animatorByName(captionLayer,"TonyFX - Caption Reveal"),"caption-3d-animation","Caption 3D reveal animator is missing");
            var neon=effectByName(captionLayer,"TonyFX - Text FX - Neon Core"),shadow=effectByName(captionLayer,"TonyFX - Text Shadow");
            expect(!!neon&&!!shadow,"caption-style-effects","Caption text treatment or appearance effect is missing");
            if(neon){expect(Number(neon.property(3).value)>0&&Number(neon.property(4).value)>0,"caption-effect-values","Caption treatment values remained zero");}
        }
        report.ok=report.failed.length===0;report.total=report.passed.length+report.failed.length;
    } catch(error) {
        report.failed.push({id:"v031-test-setup",error:error.toString(),line:error.line||0});
    } finally {
        try{if(testComp){testComp.remove();}}catch(ignoreRemove){}
        try{if(original&&original instanceof CompItem){original.openInViewer();}}catch(ignoreRestore){}
        report.ok=report.failed.length===0;write(report);
    }
}());
