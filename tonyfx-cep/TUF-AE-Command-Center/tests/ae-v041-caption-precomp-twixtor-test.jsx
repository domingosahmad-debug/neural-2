(function () {
    var reportPath = "C:/Users/TUF/Documents/ae-mcp-bridge/tonyfx_v041_caption_precomp_twixtor_test.json";
    var hostPath = "C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx";
    var report = {ok:false,checks:[],errors:[]};

    function add(check, detail) { report.checks.push({check:check,detail:detail || "ok"}); }
    function assert(value, message) { if (!value) { throw new Error(message); } add(message); }
    function parse(value) { try { return JSON.parse(value); } catch (error) { return eval("(" + value + ")"); } }
    function selectOnly(comp, layers) { for (var i=1;i<=comp.numLayers;i++){comp.layer(i).selected=false;} for(var j=0;j<layers.length;j++){layers[j].selected=true;} }
    function byMatch(group, matchName) { if(!group){return null;} for(var i=1;i<=group.numProperties;i++){if(group.property(i).matchName===matchName){return group.property(i);}} return null; }
    function cleanup() { for(var i=app.project.numItems;i>=1;i--){var item=app.project.item(i);if(/^TONYFX_TEST_/.test(item.name)){try{item.remove();}catch(ignore){}}} }
    function write() { var file=new File(reportPath); file.encoding="UTF-8"; file.open("w"); file.write(JSON.stringify(report)); file.close(); }

    try {
        $.evalFile(new File(hostPath));
        cleanup();

        var pre=app.project.items.addComp("TONYFX_TEST_PRECOMP",1080,1080,1,12,30);
        var preLayers=[];
        for(var p=0;p<3;p++){var solid=pre.layers.addSolid([0.2+p*0.2,0.3,0.5],"TONYFX_TEST_SOURCE_"+p,1080,1080,1,12);solid.inPoint=1+p;solid.outPoint=3.5+p;preLayers.push(solid);}
        selectOnly(pre,preLayers);app.project.activeItem=pre;
        var preResult=parse(TUF.precomposeSelectedSeparately());
        assert(preResult.ok,"Separate pre-compose returns success");
        assert(pre.selectedLayers.length===3,"Separate pre-compose preserves all three selections");
        for(var pl=0;pl<pre.selectedLayers.length;pl++){
            var outer=pre.selectedLayers[pl];
            assert(outer.source instanceof CompItem,"Separate pre-compose created an individual comp");
            assert(Math.abs(outer.source.duration-(outer.outPoint-outer.inPoint))<0.0001,"Separate pre-compose trimmed duration");
            assert(Math.abs(outer.source.layer(1).inPoint)<0.0001,"Separate pre-compose inner layer begins at frame zero");
        }

        var textComp=app.project.items.addComp("TONYFX_TEST_TEXT",1080,1080,1,12,30), textModes=[
            {name:"Position",mode:"position",unit:"words",expected:"ADBE Text Position 3D"},
            {name:"Pop",mode:"scale",unit:"words",expected:"ADBE Text Scale 3D"},
            {name:"Rotate",mode:"rotate",unit:"characters",expected:"ADBE Text Rotation"},
            {name:"Blur",mode:"blur",unit:"words",expected:"ADBE Text Blur"},
            {name:"Tracking",mode:"tracking",unit:"characters",expected:"ADBE Text Tracking Amount"},
            {name:"Wave",mode:"wave",unit:"characters",expected:"ADBE Text Position 3D"}
        ];
        app.project.activeItem=textComp;textComp.time=7;
        for(var t=0;t<textModes.length;t++){
            var textLayer=textComp.layers.addText("TonyFX motion test");textLayer.name="TONYFX_TEST_TEXT_"+t;textLayer.inPoint=2;textLayer.outPoint=6;selectOnly(textComp,[textLayer]);
            var tool={tool:"textMotion",name:textModes[t].name,mode:textModes[t].mode,unit:textModes[t].unit,duration:12,amount:58,smoothness:24,stagger:0};
            var textResult=parse(TUF.runTool(JSON.stringify(tool)));assert(textResult.ok,"Text "+textModes[t].name+" applies");
            var animator=textLayer.property("ADBE Text Properties").property("ADBE Text Animators").property(1);
            assert(!!byMatch(animator.property("ADBE Text Animator Properties"),textModes[t].expected),"Text "+textModes[t].name+" has its motion property");
            var selector=animator.property("ADBE Text Selectors").property(1),startProp=selector.property("ADBE Text Percent Start");
            assert(startProp.numKeys>=2 && Math.abs(startProp.keyTime(1)-textLayer.inPoint)<0.0001,"Text "+textModes[t].name+" starts at layer in-point");
        }

        var captionComp=app.project.items.addComp("TONYFX_TEST_CAPTIONS",1080,1080,1,20,30), captionModes=["wordFade","letterFade","pop","blurReveal","trackingTight","flipX","flipY","depthPush","waveRise"];
        app.project.activeItem=captionComp;
        for(var c=0;c<captionModes.length;c++){
            var payload={captions:[{start:0,end:2,text:"Caption animation test"}],compIn:10,compDuration:4,sourceDuration:8,reverse:false,animation:captionModes[c],fontSize:48,placement:"center",language:"en"};
            var captionResult=parse(TUF.createCaptions(JSON.stringify(payload)));assert(captionResult.ok,"Caption "+captionModes[c]+" applies");
            var caption=captionComp.selectedLayers[0];assert(Math.abs(caption.inPoint-10)<0.0001 && Math.abs(caption.outPoint-11)<0.0001,"Caption timing maps source duration to comp duration");
            var captionAnimator=caption.property("ADBE Text Properties").property("ADBE Text Animators").property(1),captionStart=captionAnimator.property("ADBE Text Selectors").property(1).property("ADBE Text Percent Start");
            assert(captionStart.numKeys===2 && captionStart.keyTime(2)-captionStart.keyTime(1)<=12*captionComp.frameDuration+0.0001,"Caption "+captionModes[c]+" reveal is brief");
        }

        var reversePayload={captions:[{start:1,end:2,text:"Reverse timing"}],compIn:2,compDuration:4,sourceDuration:8,reverse:true,animation:"wordFade",fontSize:48,placement:"center",language:"en"};
        var reverseResult=parse(TUF.createCaptions(JSON.stringify(reversePayload)));assert(reverseResult.ok,"Reverse caption mapping applies");
        var reverseCaption=captionComp.selectedLayers[0];assert(Math.abs(reverseCaption.inPoint-5)<0.0001 && Math.abs(reverseCaption.outPoint-5.5)<0.0001,"Reverse caption timing maps back into the comp");

        var twComp=app.project.items.addComp("TONYFX_TEST_TWIXTOR",1080,1080,1,10,30),twLayers=[];
        for(var w=0;w<2;w++){var twSolid=twComp.layers.addSolid([0.3,0.2+w*0.3,0.6],"TONYFX_TEST_TW_SOURCE_"+w,1080,1080,1,10);twSolid.inPoint=1+w;twSolid.outPoint=4+w;twLayers.push(twSolid);}
        selectOnly(twComp,twLayers);app.project.activeItem=twComp;
        var twResult=parse(TUF.applyTwixtorSelected());assert(twResult.ok,"Selected-layer Twixtor action returns success");
        assert(twComp.selectedLayers.length===2,"Twixtor action preserves both selected scenes");
        for(var x=0;x<twComp.selectedLayers.length;x++){
            var twOuter=twComp.selectedLayers[x],tw=byMatch(twOuter.property("ADBE Effect Parade"),"Twixtor 45"),speed=tw?tw.property("Twixtor 45-0005"):null;
            assert(twOuter.source instanceof CompItem,"Twixtor action pre-composes source footage");
            assert(speed && speed.numKeys===3,"Twixtor action creates exactly three Speed keys");
            assert(speed.keyValue(1)===150 && speed.keyValue(2)===35 && speed.keyValue(3)===150,"Twixtor action uses 150 / 35 / 150");
            assert(speed.keyInTemporalEase(2)[0].influence>99.9 && speed.keyOutTemporalEase(2)[0].influence>99.9,"Twixtor action uses approved U-ramp midpoint handles");
        }

        report.ok=true;
    } catch(error) {
        report.errors.push(error.toString()+(error.line?" at line "+error.line:""));
    }
    try{cleanup();}catch(ignoreCleanup){}
    write();
    try{app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);}catch(ignoreClose){}
    app.quit();
}());
