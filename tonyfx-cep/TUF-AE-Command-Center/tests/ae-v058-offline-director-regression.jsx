(function () {
    var output = new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_v058_offline_director_result.json");
    function encode(value) { var i,parts=[];if(value===null){return "null";}if(typeof value==="string"){return '"'+value.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n")+'"';}if(typeof value==="number"||typeof value==="boolean"){return String(value);}if(value instanceof Array){for(i=0;i<value.length;i++){parts.push(encode(value[i]));}return "["+parts.join(",")+"]";}for(i in value){if(value.hasOwnProperty(i)){parts.push(encode(i)+":"+encode(value[i]));}}return "{"+parts.join(",")+"}"; }
    function write(value) { output.open("w"); output.write(encode(value)); output.close(); }
    function parse(value) { return typeof value === "string" ? eval("("+value+")") : value; }
    var created=[],original=app.project&&app.project.activeItem instanceof CompItem?app.project.activeItem:null,originalTime=original?original.time:0;
    function cleanup(){
        for(var index=created.length-1;index>=0;index--){try{if(created[index]){created[index].remove();}}catch(ignoreRemove){}}
        try{if(original){original.openInViewer();original.time=originalTime;}}catch(ignoreRestore){}
        try{if(app.project&&app.project.file){app.project.save();}}catch(ignoreSave){}
    }
    try {
        $.evalFile(new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/jsx/host.jsx"));
        if (!app.project) { app.newProject(); }
        var source=app.project.items.addComp("TONYFX V059 TEST SOURCES",1080,1080,1,2,30);created.push(source);
        var previewFile=new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/assets/effect-preview.mp4");if(!previewFile.exists){throw new Error("Regression footage is missing");}
        for(var i=0;i<4;i++){
            var footage=app.project.importFile(new ImportOptions(previewFile));created.push(footage);var layer=source.layers.add(footage);
            layer.name=(i%2===0?"ANIYA ":"CARL ")+"TEST SHOT "+(i+1);layer.inPoint=0;layer.outPoint=2;layer.selected=false;
        }
        source.openInViewer();
        var shots=[];for(i=0;i<4;i++){shots.push({index:i+1,startTime:i*0.5,endTime:(i+1)*0.5,duration:0.5,zoomDirection:i%2===0?"out":"in",semantic:{keywords:[i%2===0?"aniya":"carl"],role:i%2===0?"aniya":"carl"}});}
        var transitions=[{time:0.5,family:"crossfade",durationFrames:6,confidence:0.98,curve:"0.09,0.72,0.94,0.27"},{time:1,family:"directional_smear",durationFrames:6,confidence:0.96},{time:1.5,family:"impact_shake",durationFrames:5,confidence:0.94}];
        var payload={sourceName:"V058 REGRESSION",blueprint:{fps:30,shots:shots,transitions:transitions,repeatInstructions:[]},blurMo:false,fullStack:true,strictMatch:true,policy:{mode:"balanced",seed:42,fidelity:0.95,intensity:1,transitionDensity:1,noRepeatWindow:3,autoQA:true,keepExactCuts:true}};
        var first=parse(TUF.buildOfflineEdit(encode(payload)));if(!first.ok){throw new Error(first.error||"First build failed");}
        var firstComp=null;for(i=1;i<=app.project.numItems;i++){if(app.project.item(i) instanceof CompItem&&app.project.item(i).name===first.compName){firstComp=app.project.item(i);break;}}
        if(!firstComp){throw new Error("Built comp was not found");}created.push(firstComp);
        if(!first.audit||!first.audit.passed||first.audit.baseOverlaps!==0||first.audit.audioLeaks!==0){throw new Error("First structural audit failed");}
        payload.sourceCompName=source.name;payload.reeditOf=first.compName;payload.previousAssignments=first.assignments;payload.policy={mode:"creative",seed:77,fidelity:0.88,intensity:1.1,transitionDensity:1,noRepeatWindow:4,autoQA:true,creativeAccents:true,creativeAmount:0.6,changeRange:{start:0.5,end:1},freezeOutsideRange:true};
        var second=parse(TUF.buildOfflineEdit(encode(payload)));if(!second.ok){throw new Error(second.error||"Re-edit failed");}
        var secondComp=null;for(i=1;i<=app.project.numItems;i++){if(app.project.item(i) instanceof CompItem&&app.project.item(i).name===second.compName){secondComp=app.project.item(i);break;}}
        if(!secondComp){throw new Error("Re-edit comp was not found");}created.push(secondComp);secondComp.openInViewer();
        if(!second.audit||!second.audit.passed||second.audit.baseOverlaps!==0||second.audit.audioLeaks!==0||second.audit.longTransitions!==0){throw new Error("Re-edit structural audit failed");}
        var activeAudit=parse(TUF.auditOfflineEdit());if(!activeAudit.ok||!activeAudit.audit.passed){throw new Error("Active audit failed");}
        var contractShots=[];
        for(i=0;i<4;i++){
            contractShots.push({id:"shot_00"+(i+1),index:i+1,compFrames:[i*15,(i+1)*15],startTime:i*0.5,endTime:(i+1)*0.5,durationFrames:15,duration:0.5,zoomDirection:i===0?"in":"none",zoomRatio:i===0?1.08:1,motionPlan:{zoom:{enabled:i===0,owner:i===0?"scene":"none",frames:[i*15,(i+1)*15],direction:i===0?"in":"none",ratio:i===0?1.08:1,curve:i===0?{kind:"cubic_bezier",controls:[0.12,0.72,0.88,0.3]}:null}},sourceRequirements:{minimumFrames:15,continuousShotRequired:true,nativeSpeedRequired:true,wideRequired:false,minimumMatchConfidence:0},footageMatches:[]});
        }
        var contractTransitions=[
            {id:"transition_001",kind:"cut_transition",cutFrame:15,frames:[15,16],time:0.5,families:["hard_cut"],primary:"hard_cut",direction:"none",durationFrames:1,curve:null,zoomOwner:"none",confidence:0.99,aeRecipe:[],supported:true},
            {id:"transition_002",kind:"cut_transition",cutFrame:30,frames:[27,33],time:1,families:["directional_smear"],primary:"directional_smear",direction:"left",durationFrames:6,curve:{kind:"cubic_bezier",controls:[0.09,0.72,0.94,0.27],source:"regression"},zoomOwner:"none",confidence:0.96,aeRecipe:[],supported:true},
            {id:"transition_003",kind:"cut_transition",cutFrame:45,frames:[43,48],time:1.5,families:["impact_shake"],primary:"impact_shake",direction:"none",durationFrames:5,curve:{kind:"cubic_bezier",controls:[0.1,0.75,0.9,0.25],source:"regression"},zoomOwner:"none",confidence:0.94,aeRecipe:[],supported:true}
        ];
        var contract={schema:"tonyfx.replica-builder-contract.v1",version:1,reference:{path:"regression",width:1080,height:1080,fps:"30/1",totalFrames:60},timingUnit:"half_open_reference_frames",shots:contractShots,transitions:contractTransitions,repeatGroups:[{id:"repeat_001",shots:[1,3],directions:["forward","reverse"],expectedDirections:["forward","reverse"],confidence:0.99,sourceRangeMustMatch:true}],audio:{alignmentFrame:0,events:[]},ambiguities:[],buildGate:{exactReady:true,blockingCount:0,blockingCodes:[],creativeDecisionsAllowedInAE:false,genericCurveFallbackAllowed:false,genericEffectFallbackAllowed:false,nativeDialogueSpeedRequired:true,singleZoomOwnerRequired:true},certificate:{schema:"tonyfx.replica-contract-certificate.v1",sha256:"regression-contract"}};
        payload={sourceName:"V059 EXACT REGRESSION",sourceCompName:source.name,blueprint:{fps:30,shots:shots,transitions:transitions,repeatInstructions:[],replicaBuilderContract:contract},replicaBuilderContract:contract,blurMo:false,fullStack:true,strictMatch:true,policy:{mode:"exact",seed:99,fidelity:1,intensity:1,transitionDensity:1,noRepeatWindow:2,autoQA:true,keepExactCuts:true}};
        var exact=parse(TUF.buildOfflineEdit(encode(payload)));if(!exact.ok){throw new Error(exact.error||"Exact contract build failed");}
        var exactComp=null;for(i=1;i<=app.project.numItems;i++){if(app.project.item(i) instanceof CompItem&&app.project.item(i).name===exact.compName){exactComp=app.project.item(i);break;}}
        if(!exactComp){throw new Error("Exact contract comp was not found");}created.push(exactComp);exactComp.openInViewer();
        if(!exact.audit||!exact.audit.passed||exact.audit.baseOverlaps!==0||exact.audit.audioLeaks!==0||exact.audit.shotAdjustments!==1){throw new Error("Exact structural/ownership audit failed");}
        var reverseFound=false;for(i=1;i<=exactComp.numLayers;i++){if(String(exactComp.layer(i).name).indexOf("AUTO SCENE 3 ")===0&&String(exactComp.layer(i).name).indexOf("REVERSE MOTIF")>0&&exactComp.layer(i).timeRemapEnabled){reverseFound=true;}}
        if(!reverseFound){throw new Error("Measured repeat direction was not preserved");}
        write({ok:true,first:first,second:second,exact:exact,activeAudit:activeAudit.audit});
    } catch(error) { write({ok:false,error:error.toString()+(error.line?" at line "+error.line:"")}); }
    finally { cleanup(); }
}());
