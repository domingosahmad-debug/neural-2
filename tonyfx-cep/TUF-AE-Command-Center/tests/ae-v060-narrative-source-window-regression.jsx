(function () {
    var output = new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_v060_narrative_source_window_result.json");
    function encode(value) { var i,parts=[];if(value===null){return "null";}if(typeof value==="string"){return '"'+value.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n")+'"';}if(typeof value==="number"||typeof value==="boolean"){return String(value);}if(value instanceof Array){for(i=0;i<value.length;i++){parts.push(encode(value[i]));}return "["+parts.join(",")+"]";}for(i in value){if(value.hasOwnProperty(i)){parts.push(encode(i)+":"+encode(value[i]));}}return "{"+parts.join(",")+"}"; }
    function write(value) { output.open("w"); output.write(encode(value)); output.close(); }
    function parse(value) { return typeof value === "string" ? eval("("+value+")") : value; }
    function closeTo(left,right,tolerance){return Math.abs(Number(left)-Number(right))<=tolerance;}
    var created=[],original=app.project&&app.project.activeItem instanceof CompItem?app.project.activeItem:null,originalTime=original?original.time:0;
    function cleanup(){for(var index=created.length-1;index>=0;index--){try{if(created[index]){created[index].remove();}}catch(ignoreRemove){}}try{if(original){original.openInViewer();original.time=originalTime;}}catch(ignoreRestore){}try{if(app.project&&app.project.file){app.project.save();}}catch(ignoreSave){}}
    try {
        $.evalFile(new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
        if (!app.project) { app.newProject(); }
        var source=app.project.items.addComp("TONYFX V060 MATCHED MOMENT SOURCES",1080,1080,1,2,30);created.push(source);
        var previewFile=new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/assets/effect-preview.mp4");if(!previewFile.exists){throw new Error("Regression footage is missing");}
        var names=["AKAZA ACTION A","TANJIRO ACTION B","RESOLUTION C"];
        for(var i=0;i<names.length;i++){var footage=app.project.importFile(new ImportOptions(previewFile));created.push(footage);var layer=source.layers.add(footage);layer.name=names[i];layer.inPoint=0;layer.outPoint=Math.min(2,footage.duration);layer.selected=false;}
        source.openInViewer();
        var matchedTimes=[1.2,0.75,1.65],motions=[0.82,0.74,0.81],phases=["setup","first_highlight","climax"],functions=["story_setup","action_peak","climax_action"],shots=[];
        for(i=0;i<3;i++){
            var matchName=i===2?names[0]:names[i];
            var peakPriority=i===1?2:(i===2?3:0);
            shots.push({id:"shot_00"+(i+1),index:i+1,compFrames:[i*15,(i+1)*15],startTime:i*0.5,endTime:(i+1)*0.5,durationFrames:15,duration:0.5,zoomDirection:"none",zoomRatio:1,motionPlan:{zoom:{enabled:false,owner:"none",frames:[i*15,(i+1)*15],direction:"none",ratio:1,curve:null}},sourceRequirements:{minimumFrames:15,continuousShotRequired:true,nativeSpeedRequired:true,wideRequired:false,minimumMatchConfidence:0.42,matchedSourceWindowRequired:true,minimumMotionScore:i===0?0:0.48,flashyActionRequired:i>0,mouthMotionPolicy:"avoid_visible_speech_without_aligned_dialogue"},footageMatches:[{layerName:matchName,confidence:0.96,time:matchedTimes[i],sourceStart:0,sourceDuration:2,motionScore:motions[i]}],semantic:{phase:phases[i],editorialFunction:functions[i],peakPriority:peakPriority,flashyRequired:i>0},narrativePhase:phases[i],editorialFunction:functions[i],peakPriority:peakPriority,energy:{visual:motions[i],audio:motions[i],combined:motions[i]}});
        }
        var transitions=[{id:"transition_001",kind:"cut_transition",cutFrame:15,frames:[15,16],time:0.5,families:["hard_cut"],primary:"hard_cut",direction:"none",durationFrames:1,curve:null,zoomOwner:"none",confidence:0.99,aeRecipe:[],supported:true},{id:"transition_002",kind:"cut_transition",cutFrame:30,frames:[30,31],time:1,families:["hard_cut"],primary:"hard_cut",direction:"none",durationFrames:1,curve:null,zoomOwner:"none",confidence:0.99,aeRecipe:[],supported:true}];
        var contract={schema:"tonyfx.replica-builder-contract.v1",version:1,reference:{path:"regression",width:1080,height:1080,fps:"30/1",totalFrames:45},timingUnit:"half_open_reference_frames",shots:shots,transitions:transitions,repeatGroups:[{id:"repeat_001",shots:[1,3],directions:["forward","reverse"],expectedDirections:["forward","reverse"],confidence:0.99,sourceRangeMustMatch:true}],audio:{alignmentFrame:0,events:[]},narrative:{available:true,firstHighlightShot:2,firstHighlightFrame:15,climaxShot:3,climaxFrame:30},ambiguities:[],buildGate:{exactReady:true,blockingCount:0,blockingCodes:[],creativeDecisionsAllowedInAE:false,genericCurveFallbackAllowed:false,genericEffectFallbackAllowed:false,nativeDialogueSpeedRequired:true,singleZoomOwnerRequired:true,visionMatchedSourceMomentRequired:true,peakEnergyMappingRequired:true,dialogueVisualCoherenceRequired:true},certificate:{schema:"tonyfx.replica-contract-certificate.v1",sha256:"v060-regression-contract"}};
        var payload={sourceName:"V060 NARRATIVE SOURCE WINDOW",sourceCompName:source.name,blueprint:{fps:30,shots:shots,transitions:transitions,replicaBuilderContract:contract},replicaBuilderContract:contract,blurMo:false,fullStack:true,strictMatch:true,policy:{mode:"exact",seed:60,fidelity:1,intensity:1,transitionDensity:1,noRepeatWindow:2,autoQA:true,keepExactCuts:true}};
        var result=parse(TUF.buildOfflineEdit(encode(payload)));if(!result.ok){throw new Error(result.error||"V060 exact build failed");}
        var built=null;for(i=1;i<=app.project.numItems;i++){if(app.project.item(i) instanceof CompItem&&app.project.item(i).name===result.compName){built=app.project.item(i);break;}}
        if(!built){throw new Error("V060 build was not found");}created.push(built);
        if(!result.audit||!result.audit.passed||result.audit.matchedSourceEvidence!==3){throw new Error("Matched-source structural evidence failed");}
        if(!closeTo(result.assignments[0].sourceTime,0.95,0.04)){throw new Error("Shot 1 did not center on the matched source moment");}
        if(!closeTo(result.assignments[1].sourceTime,0.50,0.04)){throw new Error("Shot 2 did not center on the matched source moment");}
        if(!closeTo(result.assignments[2].sourceTime,result.assignments[0].sourceTime,0.001)){throw new Error("Reverse motif drifted away from its source window");}
        if(Number(result.assignments[1].motionScore)<0.48||Number(result.assignments[2].motionScore)<0.48){throw new Error("Peak motion evidence was lost");}
        var markerNames=[];for(i=1;i<=built.markerProperty.numKeys;i++){markerNames.push(String(built.markerProperty.keyValue(i).comment||""));}
        var hasFirst=false,hasClimax=false;for(i=0;i<markerNames.length;i++){if(markerNames[i].indexOf("TONYFX FIRST HIGHLIGHT")>=0){hasFirst=true;}if(markerNames[i].indexOf("TONYFX CLIMAX")>=0){hasClimax=true;}}
        if(!hasFirst||!hasClimax){throw new Error("Narrative peak markers were not created: "+markerNames.join(" | "));}
        write({ok:true,assignments:result.assignments,audit:result.audit,markers:markerNames});
    } catch(error) { write({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")}); }
    finally { cleanup(); }
}());
