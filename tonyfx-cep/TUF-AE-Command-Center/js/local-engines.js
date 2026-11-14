(function () {
  "use strict";

  var core = window.TonyFXCore;
  var nodeAvailable = typeof require === "function";
  var fs = nodeAvailable ? require("fs") : null;
  var path = nodeAvailable ? require("path") : null;
  var os = nodeAvailable ? require("os") : null;
  var childProcess = nodeAvailable ? require("child_process") : null;
  var processes = {enhance:null,audio:null,generation:null,analyze:null,compare:null,candidateScore:null,colorMatch:null,setup:null,probe:null};
  var sources = {enhance:null,audio:null,analyze:null,song:null,compare:null,generationReference:"",colorTarget:null,colorReference:null};
  var analysisResult = null;
  var comparisonResult = null;
  var colorMatchResult = null;
  var audioMode = "remove-background";
  var generationMode = "video";
  var enhanceSourceMode = "clips";
  var enhanceQueueCancelled = false;
  var outputSequence = 0;
  var offlineBuildState = {sourceCompName:"",lastCompName:"",assignments:[],lastPrompt:"",buildCount:0,lastAudit:null};

  function byId(id) { return document.getElementById(id); }
  function setFooter(message) { if (core && core.setFooter) { core.setFooter(message); } }

  function parseResult(raw) {
    if (core && core.parseResult) { return core.parseResult(raw); }
    try { return JSON.parse(raw); } catch (error) { return {ok:false,error:String(raw || error)}; }
  }

  function evalHost(script, callback) {
    if (core && core.evalHost) { core.evalHost(script, callback); return; }
    if (window.__adobe_cep__) { window.__adobe_cep__.evalScript(script, callback || function () {}); }
  }

  function escapeForEval(value) {
    return String(value).replace(/\\/g, "\\\\").replace(/\"/g, "\\\"").replace(/\r/g, "\\r").replace(/\n/g, "\\n");
  }

  function extensionRoot() {
    if (!nodeAvailable) { return ""; }
    var localPath = decodeURIComponent(window.location.pathname || "").replace(/^\/([A-Za-z]:)/, "$1").replace(/\//g, path.sep);
    return path.dirname(localPath);
  }

  function defaultEngineRoot() {
    return localStorage.getItem("tonyfx.localEngine") || path.join(os.homedir(), "Documents", "TonyFX Local Engine");
  }

  function defaultOutputRoot() {
    return localStorage.getItem("tonyfx.localOutput") || path.join(os.homedir(), "Videos", "TonyFX Outputs");
  }

  function configuredPython() {
    return localStorage.getItem("tonyfx.python") || "C:\\Users\\TUF\\AppData\\Local\\Programs\\Python\\Python312\\python.exe";
  }

  function workerPython() {
    var localPython = path.join(defaultEngineRoot(), ".venv", "Scripts", "python.exe");
    return fs.existsSync(localPython) ? localPython : configuredPython();
  }

  function ensureDirectory(directory) {
    if (!fs.existsSync(directory)) { fs.mkdirSync(directory,{recursive:true}); }
  }

  function writeHostPayload(prefix,payload) {
    if (!nodeAvailable || !fs || !path) { throw new Error("TonyFX local file transport is unavailable."); }
    var directory = path.join(defaultOutputRoot(),"Host Payloads");
    ensureDirectory(directory);
    var filePath = path.join(directory,slug(prefix || "action") + "_" + Date.now() + "_" + (++outputSequence) + ".json");
    fs.writeFileSync(filePath,JSON.stringify(payload || {}),"utf8");
    return filePath;
  }

  function runHostPayloadAction(method,prefix,payload,button,workingMessage,callback) {
    var filePath,completed=false,watchdog;
    try { filePath=writeHostPayload(prefix,payload); }
    catch(error){setFooter("TonyFX could not prepare the AE command: " + error.message);return;}
    if(button){button.disabled=true;button.classList.add("is-running");}
    setFooter(workingMessage || "Sending the TonyFX action to After Effects...");
    watchdog=window.setTimeout(function(){
      if(completed){return;}completed=true;
      if(button){button.disabled=false;button.classList.remove("is-running");}
      setFooter("After Effects did not answer this TonyFX action. Reopen TonyFX once, then try again.");
    },120000);
    evalHost('TUF.' + method + '("' + escapeForEval(filePath) + '")',function(raw){
      if(completed){return;}completed=true;window.clearTimeout(watchdog);
      if(button){button.disabled=false;button.classList.remove("is-running");}
      var result=parseResult(raw);
      try{if(fs.existsSync(filePath)){fs.unlinkSync(filePath);}}catch(ignoreCleanup){}
      if(callback){callback(result);}else{setFooter(result.ok?(result.message || "TonyFX action complete"):(result.error || "TonyFX action failed"));}
    });
  }

  function openLocalPath(filePath,label) {
    if(!filePath){setFooter((label || "File") + " is not ready yet.");return false;}
    if(!nodeAvailable || !fs.existsSync(filePath)){setFooter((label || "File") + " was not found: " + filePath);return false;}
    try{
      var opener=childProcess.spawn("explorer.exe",[filePath],{windowsHide:true,detached:true,stdio:"ignore"});
      opener.unref();setFooter((label || "File") + " opened.");return true;
    }catch(error){setFooter("Could not open " + (label || "file").toLowerCase() + ": " + error.message);return false;}
  }

  function slug(value) {
    return String(value || "media").replace(/\.[^.]+$/, "").replace(/[^a-z0-9_-]+/gi,"-").replace(/^-+|-+$/g,"").slice(0,64) || "media";
  }

  function fileUrl(filePath) {
    return encodeURI("file:///" + String(filePath).replace(/\\/g,"/").replace(/^\/+/,""));
  }

  function chooseLocalFile(title, extensions, callback) {
    if (!window.cep || !window.cep.fs || !window.cep.fs.showOpenDialog) {
      setFooter("File selection is available inside the After Effects panel.");
      return;
    }
    var result = window.cep.fs.showOpenDialog(false,false,title,"",extensions || []);
    if (result && result.data && result.data.length) { callback(result.data[0]); }
  }

  function chooseLocalFolder(title, callback) {
    if (!window.cep || !window.cep.fs || !window.cep.fs.showOpenDialog) {
      setFooter("Folder selection is available inside the After Effects panel.");
      return;
    }
    var result = window.cep.fs.showOpenDialog(false,true,title,"",[]);
    if (result && result.data && result.data.length) { callback(result.data[0]); }
  }

  function setAnalyzeSongSource(filePath,mode) {
    sources.song = filePath ? {path:filePath,mode:mode || "file"} : null;
    byId("analyzeSongName").textContent = filePath ? path.basename(filePath) : "No song selected";
    byId("analyzeSongMeta").textContent = filePath ? ((mode === "folder" ? "Song folder" : "Song file") + " ready for exact phrase matching") : "Optional: choose the clean song or its folder";
    setFooter(filePath ? "Song source selected. Analyze will locate the exact phrase used by the reference." : "Song matching cleared.");
  }

  function browseAnalyzeSongFolder() {
    chooseLocalFolder("Choose the folder containing the song",function (folderPath) { setAnalyzeSongSource(folderPath,"folder"); });
  }

  function browseAnalyzeSongFile() {
    chooseLocalFile("Choose the clean song",["wav","mp3","m4a","aac","flac","ogg","opus","mp4","mov","mkv","webm"],function (filePath) { setAnalyzeSongSource(filePath,"file"); });
  }

  function clearAnalyzeSong() { setAnalyzeSongSource("",""); }

  function pairEngineControls() {
    document.querySelectorAll("[data-engine-pair]").forEach(function (label) {
      var controls = label.querySelectorAll("input");
      if (controls.length !== 2) { return; }
      controls[0].addEventListener("input",function () { controls[1].value = controls[0].value; });
      controls[1].addEventListener("input",function () { controls[0].value = controls[1].value; });
    });
  }

  function pairValue(name) {
    var label = document.querySelector('[data-engine-pair="' + name + '"]');
    var number = label ? label.querySelector('input[type="number"]') : null;
    return number ? Number(number.value) : 0;
  }

  function setPairValue(name,value) {
    var label = document.querySelector('[data-engine-pair="' + name + '"]');
    if (!label) { return; }
    label.querySelectorAll("input").forEach(function (input) { input.value = value; });
  }

  function setProgress(prefix,percent,message) {
    var fill = byId(prefix + "ProgressFill"), text = byId(prefix + "ProgressText");
    if (fill) { fill.style.width = Math.max(0,Math.min(100,Number(percent) || 0)) + "%"; }
    if (text) { text.textContent = message || "Working"; }
  }

  function setRunState(kind,running) {
    var config = {
      enhance:{run:"runEnhance",cancel:"cancelEnhance"},
      audio:{run:"runAudio",cancel:"cancelAudio"},
      generation:{run:"runGeneration",cancel:"cancelGeneration"},
      analyze:{run:"runAnalyze",cancel:"cancelAnalyze"},
      colorMatch:{run:"colorMatchAnalyze",cancel:"colorMatchCancel"}
    }[kind];
    if (!config) { return; }
    byId(config.run).disabled = running;
    byId(config.cancel).classList.toggle("hidden",!running);
  }

  function parseWorkerLine(line,handlers) {
    var value = String(line || "").trim();
    if (!value || value.indexOf("PROGRESS ") === 0) { return; }
    var payload;
    try { payload = JSON.parse(value); } catch (error) { return; }
    if (payload.type === "progress" && handlers.progress) { handlers.progress(payload.percent,payload.message); }
    if (payload.type === "workspace") { handlers.workspace = payload.path || ""; }
    if (payload.type === "result") { handlers.resultPayload = payload; }
    if (payload.type === "error") { handlers.errorPayload = payload; }
  }

  function runWorker(kind,python,script,args,handlers) {
    if (!nodeAvailable) { handlers.done({ok:false,error:"Node.js is unavailable in this panel."}); return; }
    if (!fs.existsSync(python)) { handlers.done({ok:false,error:"Python executable not found: " + python}); return; }
    if (!fs.existsSync(script)) { handlers.done({ok:false,error:"TonyFX local worker is missing."}); return; }
    if (processes[kind]) { handlers.done({ok:false,error:"A " + kind + " task is already running."}); return; }
    var process = childProcess.spawn(python,[script].concat(args),{windowsHide:true});
    process.__tonyfxHandlers = handlers;
    processes[kind] = process;
    var pending = "", stderr = "";
    process.stdout.on("data",function (chunk) {
      pending += chunk.toString();
      var lines = pending.split(/\r?\n/); pending = lines.pop();
      lines.forEach(function (line) { parseWorkerLine(line,handlers); });
    });
    process.stderr.on("data",function (chunk) { stderr += chunk.toString(); });
    process.on("error",function (error) {
      processes[kind] = null;
      if (!handlers.cancelled) { handlers.done({ok:false,error:error.message}); }
    });
    process.on("close",function (code) {
      if (pending) { parseWorkerLine(pending,handlers); }
      processes[kind] = null;
      if (handlers.cancelled) { return; }
      if (handlers.errorPayload) { handlers.done({ok:false,error:handlers.errorPayload.message || "Local worker failed"}); return; }
      if (code !== 0 || !handlers.resultPayload) { handlers.done({ok:false,error:(stderr || "Local worker stopped with code " + code).slice(-1000)}); return; }
      handlers.done(handlers.resultPayload);
    });
    return process;
  }

  function cancelWorker(kind) {
    if (kind === "enhance") { enhanceQueueCancelled = true; }
    var process = processes[kind];
    if (process) {
      var handlers = process.__tonyfxHandlers || {};
      handlers.cancelled = true;
      if (process.pid && os.platform() === "win32") {
        childProcess.spawn("taskkill",["/PID",String(process.pid),"/T","/F"],{windowsHide:true});
      } else {
        try { process.kill("SIGTERM"); } catch (ignoreKill) {}
      }
      processes[kind] = null;
      if (handlers.workspace && kind === "enhance") {
        window.setTimeout(function () {
          try {
            var workspace = path.resolve(handlers.workspace);
            var tempRoot = path.resolve(os.tmpdir()) + path.sep;
            if (workspace.indexOf(tempRoot) === 0 && /^tonyfx-enhance-/i.test(path.basename(workspace))) {
              fs.rmSync(workspace,{recursive:true,force:true});
            }
          } catch (ignoreCleanup) {}
        },1200);
      }
    }
    setRunState(kind,false); setProgress(kind,0,"Cancelled"); setFooter("Local " + kind + " task cancelled");
  }

  function inspectSelectedSource(kind,callback) {
    evalHost("TUF.getCaptionSourceSelection()",function (raw) {
      var result = parseResult(raw);
      if (!result.ok) {
        var label = kind === "enhance" ? "enhance" : "audio";
        byId(label + "SourceName").textContent = "AE selection unavailable";
        byId(label + "SourceMeta").textContent = result.error || "Select one media layer first.";
        setFooter(result.error || "Select one media layer first.");
        return;
      }
      sources[kind] = result;
      var label = kind === "enhance" ? "enhance" : "audio";
      byId(label + "SourceName").textContent = result.layerName;
      byId(label + "SourceMeta").textContent = result.sourceDuration.toFixed(2) + " sec | aligned at " + result.compIn.toFixed(2) + " sec";
      if (callback) { callback(result); }
    });
  }

  function setEnhanceSourceMode(mode) {
    enhanceSourceMode = mode === "composition" ? "composition" : "clips";
    sources.enhance = null;
    document.querySelectorAll("[data-enhance-source-mode]").forEach(function (button) {
      button.classList.toggle("active",button.getAttribute("data-enhance-source-mode") === enhanceSourceMode);
    });
    byId("enhanceSourceName").textContent = enhanceSourceMode === "composition" ? "Select a precomp or use the active composition" : "Select one or more timeline clips";
    byId("enhanceSourceMeta").textContent = enhanceSourceMode === "composition" ? "Effects, transitions, and full audio are rendered together." : "Each selected clip is enhanced and aligned independently.";
    byId("inspectEnhanceSource").textContent = enhanceSourceMode === "composition" ? "Use Composition" : "Use AE Selection";
  }

  function colorMatchStatus(message,error) {
    var status = byId("colorMatchStatus");
    if (status) { status.textContent = message; status.classList.toggle("error",!!error); }
    setFooter(message);
  }

  function setColorMatchSafetyState(isSafe,label) {
    var lab = document.querySelector(".color-match-lab");
    var badge = byId("colorMatchSafety");
    if (lab) { lab.classList.toggle("unsafe",isSafe === false); }
    if (badge) { badge.textContent = label || (isSafe === false ? "REVIEW REQUIRED" : "LOCAL SAFE"); }
  }

  function describeColorSource(source) {
    if (!source) { return "No source"; }
    var duration = Number(source.sourceDuration) || 0;
    return duration > 0 ? duration.toFixed(2) + " sec | source " + (Number(source.sourceStart) || 0).toFixed(2) + " sec" : "Local still or full video";
  }

  function inspectColorSource(role) {
    evalHost("TUF.getColorMatchSelection()",function (raw) {
      var result = parseResult(raw);
      if (!result.ok) { colorMatchStatus(result.error || "Select exactly one scene layer.",true); return; }
      if (role === "reference") {
        sources.colorReference = result;
        byId("colorMatchReferenceName").textContent = result.layerName;
        byId("colorMatchReferenceMeta").textContent = describeColorSource(result);
        byId("colorMatchReferenceStart").value = String(Number(result.sourceStart) || 0);
        byId("colorMatchReferenceDuration").value = String(Number(result.sourceDuration) || 0);
      } else {
        sources.colorTarget = result;
        byId("colorMatchTargetName").textContent = result.layerName;
        byId("colorMatchTargetMeta").textContent = describeColorSource(result);
      }
      colorMatchResult = null;
      setColorMatchSafetyState(true,"LOCAL SAFE");
      byId("colorMatchApply").disabled = true;
      byId("colorMatchRender").disabled = true;
      colorMatchStatus((role === "reference" ? "Reference" : "Target") + " captured. Analysis will not alter the layer.");
    });
  }

  function browseColorReference() {
    chooseLocalFile("Choose color reference",["png","jpg","jpeg","webp","tif","tiff","bmp","mp4","mov","mkv","avi","m4v","webm","mts","m2ts"],function (filePath) {
      sources.colorReference = {path:filePath,layerName:path.basename(filePath),sourceStart:0,sourceDuration:0,localFile:true};
      byId("colorMatchReferenceName").textContent = path.basename(filePath);
      byId("colorMatchReferenceMeta").textContent = "Local still or video reference";
      byId("colorMatchReferenceStart").value = "0";
      byId("colorMatchReferenceDuration").value = "0";
      colorMatchResult = null;
      setColorMatchSafetyState(true,"LOCAL SAFE");
      byId("colorMatchApply").disabled = true;
      byId("colorMatchRender").disabled = true;
      colorMatchStatus("Reference loaded locally. Ready to analyze.");
    });
  }

  function colorMatchWorkspace() {
    var directory = path.join(defaultOutputRoot(),"Color Match","match-" + Date.now());
    ensureDirectory(directory);
    return directory;
  }

  function setColorMatchPreview(id,filePath) {
    var image = byId(id);
    if (!image || !filePath) { return; }
    image.src = fileUrl(filePath) + "?t=" + Date.now();
  }

  function displayColorMatchResult(result) {
    colorMatchResult = result;
    var previews = result.previews || {}, metrics = result.metrics || {}, safety = result.safety || {};
    setColorMatchPreview("colorMatchTargetPreview",previews.target);
    setColorMatchPreview("colorMatchReferencePreview",previews.reference);
    setColorMatchPreview("colorMatchResultPreview",previews.matched);
    setColorMatchPreview("colorMatchScopesPreview",previews.scopes);
    var cards = byId("colorMatchMetrics").querySelectorAll("strong");
    if (cards.length >= 4) {
      cards[0].textContent = Number(metrics.improvementPercent || 0).toFixed(1) + "%";
      cards[1].textContent = Number(metrics.confidence || 0).toFixed(0) + "%";
      cards[2].textContent = String((Number(metrics.targetFaces) || 0) + "/" + (Number(metrics.referenceFaces) || 0));
      var targetSamples = result.targetMetadata && result.targetMetadata.times || [];
      var referenceSamples = result.referenceMetadata && result.referenceMetadata.times || [];
      cards[3].textContent = targetSamples.length + "/" + referenceSamples.length;
      if (cards.length >= 6) {
        cards[4].textContent = Number(safety.skinDeltaE || 0).toFixed(1);
        cards[5].textContent = Number(safety.matchedHighlightClipping || 0).toFixed(2) + "%";
      }
    }
    var safe = result.safe !== false;
    setColorMatchSafetyState(safe,safe ? "VALIDATED" : "REVIEW REQUIRED");
    byId("colorMatchApply").disabled = !safe;
    byId("colorMatchRender").disabled = !safe;
    var improvement = Number(metrics.improvementPercent) || 0;
    var warnings = result.warnings || [];
    var message = !safe ? "Unsafe match blocked: " + (warnings.join(" ") || "skin or clipping validation failed.") : (improvement > 5 ? "Validated match ready. Color error improved by " + improvement.toFixed(1) + "% without unsafe skin or clipping changes." : "Low-confidence match. Review the preview before applying.");
    colorMatchStatus(message,!safe || improvement <= 5);
  }

  function colorMatchArguments(workspace,renderOutput) {
    var target = sources.colorTarget, reference = sources.colorReference;
    var args = [
      "--engine-root",defaultEngineRoot(),"color-match",
      "--target",target.path,"--reference",reference.path,"--output-dir",workspace,
      "--target-start",String(Number(target.sourceStart) || 0),"--target-duration",String(Number(target.sourceDuration) || 0),
      "--reference-start",String(Number(byId("colorMatchReferenceStart").value) || 0),"--reference-duration",String(Number(byId("colorMatchReferenceDuration").value) || 0),
      "--samples",byId("colorMatchSamples").value,"--strength",String(pairValue("colorMatchStrength")),"--mode",byId("colorMatchMode").value,"--lut-size","33",
      byId("colorMatchTone").checked ? "--match-tone" : "--no-match-tone",
      byId("colorMatchColor").checked ? "--match-color" : "--no-match-color",
      byId("colorMatchSkin").checked ? "--protect-skin" : "--no-protect-skin"
    ];
    if (renderOutput) { args.push("--render-output",renderOutput); }
    return args;
  }

  function runColorMatch(renderExact) {
    if (!sources.colorTarget || !sources.colorTarget.path) { colorMatchStatus("Capture one AE target layer first.",true); return; }
    if (!sources.colorReference || !sources.colorReference.path) { colorMatchStatus("Choose a reference still, video, or AE layer first.",true); return; }
    var workspace = colorMatchWorkspace();
    var renderOutput = renderExact ? outputPath("Color Match",sources.colorTarget.layerName + "-precision-match",".mov") : "";
    setRunState("colorMatch",true);
    byId("colorMatchApply").disabled = true;
    byId("colorMatchRender").disabled = true;
    setProgress("colorMatch",2,renderExact ? "Solving and rendering precision match" : "Starting reference analysis");
    colorMatchStatus(renderExact ? "Rendering a precision matched copy. The original layer remains unchanged." : "Analyzing sampled frames locally. No layer is being changed.");
    runWorker("colorMatch",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),colorMatchArguments(workspace,renderOutput),{
      progress:function (percent,message) { setProgress("colorMatch",percent,message); },
      done:function (result) {
        setRunState("colorMatch",false);
        if (!result.ok) { setProgress("colorMatch",0,"Failed"); colorMatchStatus(result.error || "Color Match failed.",true); return; }
        setProgress("colorMatch",100,renderExact ? "Precision render complete" : "Analysis complete");
        displayColorMatchResult(result);
        if (renderExact && result.renderOutput) {
          var entry = {path:result.renderOutput,compIn:Number(sources.colorTarget.compIn) || 0,sourceLayerName:sources.colorTarget.layerName || ""};
          evalHost('TUF.importLocalEngineOutput("' + escapeForEval(JSON.stringify({entries:[entry],kind:"color-match",addToTimeline:true})) + '")',function (raw) {
            var imported = parseResult(raw);
            colorMatchStatus(imported.ok ? "Precision matched media imported and aligned above the source. The source was not replaced." : imported.error, !imported.ok);
          });
        }
      }
    });
  }

  function applyEditableColorMatch() {
    if (!colorMatchResult || !colorMatchResult.recipe) { colorMatchStatus("Analyze a match first.",true); return; }
    if (colorMatchResult.safe === false) { colorMatchStatus("This match failed safety validation and cannot be applied.",true); return; }
    var payload = {values:colorMatchResult.recipe.lumetri || {},matchId:path.basename(colorMatchResult.recipePath || "local-match")};
    evalHost('TUF.applyColorMatch("' + escapeForEval(JSON.stringify(payload)) + '")',function (raw) {
      var result = parseResult(raw);
      colorMatchStatus(result.ok ? result.message : result.error,!result.ok);
    });
  }

  function removeEditableColorMatch() {
    evalHost("TUF.removeColorMatch()",function (raw) {
      var result = parseResult(raw);
      colorMatchStatus(result.ok ? result.message : result.error,!result.ok);
    });
  }

  function inspectEnhanceSources() {
    setProgress("enhance",1,enhanceSourceMode === "composition" ? "Preparing composition render" : "Reading selected clips");
    var options = {mode:enhanceSourceMode,engineRoot:defaultEngineRoot()};
    evalHost('TUF.getEnhanceSourceSelection("' + escapeForEval(JSON.stringify(options)) + '")',function (raw) {
      var result = parseResult(raw);
      if (!result.ok) {
        byId("enhanceSourceName").textContent = "AE selection unavailable";
        byId("enhanceSourceMeta").textContent = result.error || "Choose valid media first.";
        setProgress("enhance",0,"Idle"); setFooter(result.error || "Choose valid media first.");
        return;
      }
      sources.enhance = result;
      var items = result.items || [];
      byId("enhanceSourceName").textContent = result.label || (items.length + " selected clip" + (items.length === 1 ? "" : "s"));
      byId("enhanceSourceMeta").textContent = result.message || (items.length + " item" + (items.length === 1 ? "" : "s") + " ready for sequential enhancement");
      setProgress("enhance",0,"Ready"); setFooter(result.message || "Enhancement source ready");
    });
  }

  function browseSource(kind) {
    chooseLocalFile(kind === "audio" ? "Choose audio or video" : (kind === "analyze" ? "Choose reference video" : "Choose video or image"),[],function (filePath) {
      var result = {path:filePath,layerName:path.basename(filePath),compIn:0,compOut:0,sourceStart:0,sourceDuration:0,browsed:true};
      sources[kind] = kind === "enhance" ? {ok:true,mode:"file",label:result.layerName,message:"Entire local file ready",items:[result]} : result;
      byId(kind + "SourceName").textContent = result.layerName;
      byId(kind + "SourceMeta").textContent = kind === "analyze" ? "Local reference | ready for offline forensics" : "Local file | the entire file will be processed";
      if (kind === "analyze") { updatePreview("analyze",filePath); byId("analyzeMonitorTitle").textContent = path.basename(filePath); }
    });
  }

  function inspectAnalyzeSource() {
    evalHost("TUF.getCaptionSourceSelection()",function (raw) {
      var result = parseResult(raw);
      if (!result.ok) { setFooter(result.error || "Select one reference media layer first."); return; }
      sources.analyze = result;
      byId("analyzeSourceName").textContent = result.layerName;
      byId("analyzeSourceMeta").textContent = Number(result.sourceDuration || 0).toFixed(2) + " sec | source file analysis";
      byId("analyzeOffset").value = Number(result.compIn || 0).toFixed(3);
      updatePreview("analyze",result.path);
      byId("analyzeMonitorTitle").textContent = result.layerName;
      setFooter("Reference media ready for offline analysis");
    });
  }

  function averageConfidence(events) {
    if (!events || !events.length) { return 0; }
    return events.reduce(function (sum,event) { return sum + Number(event.confidence || 0); },0) / events.length;
  }

  function recipeLabel(event) {
    return (event.aeRecipe || []).map(function (item) { return item.effect || item.property || item.transition || item.layer || ""; }).filter(Boolean).join(" + ");
  }

  function feedbackPath() {
    var directory = path.join(defaultEngineRoot(),"analysis"); ensureDirectory(directory);
    return path.join(directory,"reference-feedback.json");
  }

  function learnCandidate(event,family) {
    var target = feedbackPath(), feedback = {version:1,corrections:[],approvedCurves:{},familyBias:{}};
    try { if (fs.existsSync(target)) { feedback = Object.assign(feedback,JSON.parse(fs.readFileSync(target,"utf8"))); } } catch (ignoreFeedback) {}
    feedback.corrections = feedback.corrections || []; feedback.approvedCurves = feedback.approvedCurves || {}; feedback.familyBias = feedback.familyBias || {};
    var detected = event.renderedCandidateFamily || event.family || "hard_cut";
    feedback.corrections.push({time:new Date().toISOString(),detected:detected,approved:family,graph:event.graph,curve:event.curve,source:analysisResult && analysisResult.media && analysisResult.media.name || "reference"});
    if (family !== detected) { feedback.familyBias[family] = Number(feedback.familyBias[family] || 0) + 0.025; feedback.familyBias[detected] = Number(feedback.familyBias[detected] || 0) - 0.0125; }
    if (event.graph && event.curve) { feedback.approvedCurves[event.graph] = event.curve; }
    fs.writeFileSync(target,JSON.stringify(feedback,null,2),"utf8");
    var evidence=event.forensics || {},vector=evidence.dnaVector;
    if(Array.isArray(vector) && vector.length){
      var dnaTarget=path.join(defaultEngineRoot(),"analysis","transition-dna.json"),dna={version:1,entries:[]};
      try{if(fs.existsSync(dnaTarget)){dna=Object.assign(dna,JSON.parse(fs.readFileSync(dnaTarget,"utf8")));}}catch(ignoreDna){}
      dna.entries=dna.entries || [];
      dna.entries.push({name:family,source:analysisResult && analysisResult.media && analysisResult.media.name || "approved reference",vector:vector,time:new Date().toISOString()});
      fs.writeFileSync(dnaTarget,JSON.stringify(dna,null,2),"utf8");
    }
    setFooter("Saved this transition and graph to the TonyFX feedback library");
  }

  function runRealCandidateScore(event,ranked,button) {
    var families=(ranked || []).slice(0,5).map(function(item){return item.family;});
    if(!families.length){families=[event.family || "hard_cut"];}
    button.disabled=true; button.textContent="Rendering in AE..."; setFooter("Rendering real AE transition candidates on disposable composition copies");
    var payload={event:event,families:families,offset:Number(byId("analyzeOffset").value)||0,outputRoot:defaultEngineRoot()};
    evalHost('TUF.renderReferenceCandidateSet("' + escapeForEval(JSON.stringify(payload)) + '")',function(raw){
      var rendered=parseResult(raw);
      if(!rendered.ok){button.disabled=false;button.textContent="Render + Score AE";setFooter(rendered.error);return;}
      var directory=path.join(defaultOutputRoot(),"AE Candidate Scores",String(Date.now()));ensureDirectory(directory);
      var candidatePath=path.join(directory,"candidates.json"),outputPath=path.join(directory,"score.json");
      fs.writeFileSync(candidatePath,JSON.stringify(rendered.items || [],null,2),"utf8");
      var reference=analysisResult && analysisResult.sourceMedia && analysisResult.sourceMedia.analyzed || analysisResult.media.path;
      var duration=Number(event.durationSeconds || (Number(event.durationFrames||5)/Number(analysisResult.media.fps||30)));
      runWorker("candidateScore",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),["score-ae-candidates","--reference",reference,"--event-time",String(event.time),"--duration",String(duration),"--candidates",candidatePath,"--output",outputPath],{
        done:function(result){button.disabled=false;button.textContent="Render + Score AE";if(!result.ok){setFooter(result.error);return;}var winner=result.scoring && result.scoring.winner;button.textContent=winner ? "AE winner: " + String(winner.family).replace(/_/g," ") + " " + Math.round(Number(winner.score||0)*100) + "%" : "No winner";setFooter("Real AE candidate score saved: " + outputPath);}
      });
    });
  }

  function renderAnalysis(result) {
    analysisResult = result;
    var events = result.events || [], summary = result.summary || {}, audio = result.audio || {};
    var boxes = byId("analyzeSummary").children;
    boxes[0].querySelector("strong").textContent = String(summary.cutCount === undefined ? events.length : summary.cutCount);
    boxes[1].querySelector("strong").textContent = audio.tempo ? Number(audio.tempo).toFixed(1) : "-";
    boxes[2].querySelector("strong").textContent = String(summary.repeatCount || 0);
    boxes[3].querySelector("strong").textContent = Math.round(averageConfidence(events) * 100) + "%";
    var container = byId("analyzeEvents"); container.innerHTML = "";
    var contract=result.replicaBuilderContract || result.editBlueprint && result.editBlueprint.replicaBuilderContract || {},gate=contract.buildGate || {};
    var gatePanel=document.createElement("div");gatePanel.className="analyzer-recipe";
    gatePanel.innerHTML="<b>Exact Replica build gate</b><br>" + (gate.exactReady ? "READY — frame-native evidence and ownership are executable." : "BLOCKED — " + Number(gate.blockingCount || 0) + " unresolved issue(s): " + String((gate.blockingCodes || []).join(", ") || "run Deep Replica Lab analysis")) + "<br><small>AE may not invent missing graphs, effects, zooms, repeat direction, or source-speed changes.</small>";
    container.appendChild(gatePanel);
    var narrative=result.narrativeMap || result.editBlueprint && result.editBlueprint.narrativeMap || contract.narrative || {};
    if(narrative.available){
      var narrativePanel=document.createElement("div");narrativePanel.className="analyzer-recipe";
      narrativePanel.innerHTML="<b>Editorial energy map</b><br>First highlight: shot " + Number(narrative.firstHighlightShot||0) + " / frame " + Number(narrative.firstHighlightFrame||0) + "<br>Climax: shot " + Number(narrative.climaxShot||0) + " / frame " + Number(narrative.climaxFrame||0) + "<br><small>Peak slots require high-motion candidate evidence. Calm or scenic footage cannot pass Exact mode at those moments; unaligned mouth movement is flagged for replacement.</small>";
      container.appendChild(narrativePanel);
    }
    if (!events.length) { var empty=document.createElement("p");empty.className="muted";empty.textContent="No strong edit boundaries were detected. Try Deep accuracy for subtle edits.";container.appendChild(empty); }
    events.forEach(function (event,index) {
      var button = document.createElement("button"); button.type = "button"; button.className = "analyzer-event";
      var families = event.componentFamilies && event.componentFamilies.length ? event.componentFamilies : [event.family || "cut"];
      var boundaryType = event.kind === "effect_only" ? "FX only" : "Cut";
      button.innerHTML = "<time>" + Number(event.time).toFixed(3) + "s</time><strong>" + families.map(function (item) { return String(item).replace(/_/g," "); }).join(" + ") + "</strong><small>" + boundaryType + " | " + event.durationFrames + "f</small><small>" + Math.round(Number(event.confidence || 0) * 100) + "%</small>";
      button.addEventListener("click",function () {
        container.querySelectorAll(".analyzer-event").forEach(function (item) { item.classList.remove("active"); }); button.classList.add("active");
        var existing = container.querySelector(".event-recipe"); if (existing) { existing.remove(); }
        var recipe = document.createElement("div"); recipe.className = "analyzer-recipe event-recipe";
        var rendered = event.renderedCandidates || {}, ranked = rendered.candidates || [];
        var forensic=event.forensics || {},transform=forensic.transform || {},flow=forensic.flow || {},dna=(forensic.dnaMatches || [])[0] || {};
        recipe.innerHTML = "<b>Boundary:</b> " + boundaryType + " at frame " + event.frame + "<br><b>Graph:</b> " + event.graph + " | " + event.curve + "<br><b>Bezier fit:</b> " + (event.advancedCurve ? Math.round(Number(event.advancedCurve.confidence || 0) * 100) + "% confidence" : "n/a") + "<br><b>AE stack:</b> " + recipeLabel(event) + "<br><b>Rendered candidate:</b> " + String(rendered.winner || "n/a").replace(/_/g," ") + " | " + Math.round(Number(rendered.confidence || 0) * 100) + "%<br><b>Deep forensics:</b> " + String((forensic.measuredFamilies || []).join(" + ") || "fallback").replace(/_/g," ") + " | travel " + Number(transform.travelPx || 0).toFixed(1) + "px | scale " + Number(transform.scaleRatio || 1).toFixed(3) + "x | rotation " + Number(transform.rotation || 0).toFixed(1) + " deg | perspective " + Number(transform.perspective || 0).toFixed(3) + " | blur direction " + Number(flow.directionDegrees || 0).toFixed(0) + " deg<br><b>Transition DNA:</b> " + String(dna.family || "n/a").replace(/_/g," ") + " | " + Math.round(Number(dna.score || 0)*100) + "%<br><b>Evidence:</b> stable-content change " + Number(event.stableContentChange || 0).toFixed(3) + ", zoom " + event.zoomRatio + "x, blur " + event.blurStrength + ", beat distance " + (event.beatDistanceMs === null || event.beatDistanceMs === undefined ? "n/a" : event.beatDistanceMs + " ms") + "<br><b>Collapsed peaks:</b> " + ((event.sourcePeaks || []).join(", ") || "none");
        if (ranked.length) {
          var controls = document.createElement("div"); controls.className = "candidate-learn";
          var select = document.createElement("select"); ranked.forEach(function (candidate) { var option=document.createElement("option"); option.value=candidate.family; option.textContent=String(candidate.family).replace(/_/g," ") + " | " + Math.round(Number(candidate.score || 0)*100) + "%"; select.appendChild(option); });
          var approve = document.createElement("button"); approve.type="button"; approve.textContent="Approve + Learn"; approve.addEventListener("click",function(){ learnCandidate(event,select.value); });
          var renderButton=document.createElement("button");renderButton.type="button";renderButton.textContent="Render + Score AE";renderButton.addEventListener("click",function(){runRealCandidateScore(event,ranked,renderButton);});
          controls.appendChild(select); controls.appendChild(approve); controls.appendChild(renderButton); recipe.appendChild(controls);
        }
        button.insertAdjacentElement("afterend",recipe);
        var video = byId("analyzePreviewVideo"); if (video && video.classList.contains("active")) { try { video.currentTime = Math.max(0,Number(event.time) - Number(event.durationSeconds || 0) / 2); } catch (ignoreSeek) {} }
      });
      container.appendChild(button);
    });
    var matchedShots = (result.shots || []).filter(function(shot){ return shot.footageMatches && shot.footageMatches.length; });
    if (matchedShots.length) {
      var matchPanel=document.createElement("div"); matchPanel.className="analyzer-recipe";
      var matchHtml="<b>Semantic AE footage matches</b><br>";
      matchedShots.slice(0,12).forEach(function(shot){
        var best=shot.footageMatches[0],semantic=shot.semantic||{}; matchHtml += "Shot " + shot.index + " [" + String(semantic.phase||semantic.role||"shot").replace(/_/g," ") + "]: " + String(best.layerName || best.path) + " @ " + Number(best.time||0).toFixed(2) + "s | match " + Math.round(Number(best.confidence || 0)*100) + "% | motion " + Math.round(Number(best.motionScore || 0)*100) + "%<br>";
      });
      matchPanel.innerHTML=matchHtml; container.appendChild(matchPanel);
    }
    var alignment=result.audioAlignment || result.editBlueprint && result.editBlueprint.audioAlignment || {};
    if(alignment.available){
      var alignmentPanel=document.createElement("div");alignmentPanel.className="analyzer-recipe";
      var accepted=alignment.accepted !== false, confidence=Math.round(Number(alignment.confidence||0)*100);
      alignmentPanel.innerHTML="<b>Clean-song alignment</b><br>" + (accepted ? "Matched " : "Low-confidence candidate: ") + String(alignment.songName||"song") + "<br>Reference " + Number(alignment.referenceStart||0).toFixed(3) + "s = song " + Number(alignment.songStart||0).toFixed(3) + "s | layer start " + Number(alignment.timelineLayerStart||0).toFixed(3) + "s | " + confidence + "% confidence";
      container.appendChild(alignmentPanel);
      byId("analyzeSongName").textContent=String(alignment.songName||"Matched song");
      byId("analyzeSongMeta").textContent=(accepted?"Exact phrase ready":"Review match") + " | reference " + Number(alignment.referenceStart||0).toFixed(2) + "s = song " + Number(alignment.songStart||0).toFixed(2) + "s | " + confidence + "%";
    }
    updateAnalyzeActionState();
    if (result.contactSheet) { updatePreview("analyze",result.contactSheet); }
  }

  function runAnalyzeWithInventory(inventory,catalog) {
    var source = sources.analyze;
    if (!source || !source.path) { setFooter("Choose a reference video or select one in AE first."); return; }
    var directory = path.join(defaultOutputRoot(),"Reference Analysis",slug(source.layerName || "reference") + "_" + String(Date.now()));
    ensureDirectory(directory);
    var inventoryPath = path.join(directory,"ae-effect-inventory.json"); fs.writeFileSync(inventoryPath,JSON.stringify(inventory || [],null,2),"utf8");
    var catalogPath = path.join(directory,"ae-footage-catalog.json"); fs.writeFileSync(catalogPath,JSON.stringify(catalog || {items:[]},null,2),"utf8");
    var deepReplica=byId("analyzeAccuracy").value === "deep";
    var args = ["--engine-root",defaultEngineRoot(),"analyze-reference","--input",source.path,"--output-dir",directory,"--width",byId("analyzeWidth").value,"--accuracy",byId("analyzeAccuracy").value,byId("analyzeAudio").checked ? "--audio" : "--no-audio",byId("analyzeOcr").checked ? "--ocr" : "--no-ocr",byId("analyzeDeepFlow").checked ? "--deep-flow" : "--no-deep-flow",byId("analyzeVision").checked ? "--vision" : "--no-vision",deepReplica ? "--replica-lab" : "--no-replica-lab","--effect-inventory",inventoryPath,"--footage-catalog",catalogPath,"--feedback",feedbackPath()];
    if(sources.song && sources.song.path){args.push("--song-source",sources.song.path);}
    analysisResult = null; comparisonResult = null; updateAnalyzeActionState(); setRunState("analyze",true); setProgress("analyze",1,"Starting reference forensics"); setFooter("Reference analysis running locally - no Codex usage");
    runWorker("analyze",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),args,{
      progress:function (percent,message) { setProgress("analyze",percent,message); },
      done:function (result) {
        setRunState("analyze",false);
        if (!result.ok) { updateAnalyzeActionState(); setProgress("analyze",0,"Analysis failed"); setFooter(result.error); return; }
        setProgress("analyze",100,"Complete"); renderAnalysis(result); byId("analyzeMonitorTitle").textContent = Number(result.summary && result.summary.cutCount || (result.events || []).length) + " canonical cuts mapped"; updateAnalyzeActionState(); setFooter("Reference forensics complete - " + Number(result.footageIndex && result.footageIndex.count || 0) + " AE footage samples indexed with vision QA");
      }
    });
  }

  function runAnalyze() {
    evalHost("TUF.getInstalledEffectInventory()",function (raw) {
      var result = parseResult(raw), inventory = result.ok ? (result.items || []) : [];
      evalHost("TUF.getProjectMediaCatalog()",function (catalogRaw) {
        var catalog = parseResult(catalogRaw); runAnalyzeWithInventory(inventory,catalog.ok ? catalog : {items:[]});
      });
    });
  }

  function browseCompareSource() {
    chooseLocalFile("Choose the rendered edit to compare",[],function (filePath) {
      sources.compare = {path:filePath}; byId("compareSourceName").textContent = path.basename(filePath); byId("compareSourceMeta").textContent = "Ready for frame-accurate comparison";
      updateAnalyzeActionState();setFooter("Rendered edit selected. Press Compare Edit to run frame-accurate QA.");
    });
  }

  function setActionAvailability(id,ready,hint) {
    var button=byId(id);if(!button){return;}
    button.disabled=false;
    button.classList.toggle("is-unavailable",!ready);
    button.setAttribute("aria-disabled",ready?"false":"true");
    button.title=ready?"":String(hint || "Complete the required step first.");
  }

  function updateAnalyzeActionState() {
    var hasAnalysis=!!analysisResult;
    var hasEvents=!!(analysisResult && (analysisResult.events || []).length);
    var hasBlueprint=!!(analysisResult && analysisResult.editBlueprint && (analysisResult.editBlueprint.shots || []).length);
    var gate=analysisResult && (analysisResult.replicaBuilderContract || analysisResult.editBlueprint && analysisResult.editBlueprint.replicaBuilderContract) || {},exactReady=!!(gate.buildGate && gate.buildGate.exactReady);
    var exactSelected=byId("offlineMode") && byId("offlineMode").value === "exact";
    var hasReport=!!(analysisResult && analysisResult.htmlReport && fs && fs.existsSync(analysisResult.htmlReport));
    var hasComparison=!!comparisonResult;
    var hasRepair=!!(comparisonResult && comparisonResult.comparison && comparisonResult.comparison.autoRepair);
    setActionAvailability("openAnalyzeReport",hasReport,"Run Analyze successfully to create the report.");
    setActionAvailability("applyAnalyzeMarkers",hasEvents,"Run Analyze successfully to create cut and beat markers.");
    setActionAvailability("buildOfflineEdit",hasBlueprint && (!exactSelected || exactReady),exactSelected && !exactReady ? "Exact Replica is blocked until Deep Replica Lab resolves the analysis contract." : "Run Analyze successfully to create an offline edit blueprint.");
    setActionAvailability("reeditOfflineEdit",hasBlueprint && !!offlineBuildState.lastCompName,"Build an offline edit first, then describe the revision.");
    setActionAvailability("auditOfflineEdit",true,"");
    setActionAvailability("compareFinishedEdit",hasAnalysis && !!sources.compare,"Analyze a reference, then choose a rendered edit.");
    setActionAvailability("openRepairPlan",hasComparison,"Run Compare Edit successfully to create a repair plan.");
    setActionAvailability("applySafeRepair",hasRepair,"Run Compare Edit and create a safe repair plan first.");
  }

  function runCompareFinishedEdit() {
    if (!analysisResult || !analysisResult.manifest || !sources.compare) { setFooter("Analyze a reference and choose the finished edit render first."); return; }
    var directory = path.join(defaultOutputRoot(),"Reference Comparisons",slug(path.basename(sources.compare.path)) + "_" + Date.now()); ensureDirectory(directory);
    byId("compareFinishedEdit").disabled = true; setProgress("analyze",2,"Comparing finished edit"); setFooter("TonyFX is comparing every cut and transition locally");
    var args = ["--engine-root",defaultEngineRoot(),"compare-edit","--reference-report",analysisResult.manifest,"--candidate",sources.compare.path,"--output-dir",directory,"--width",byId("analyzeWidth").value,"--timeline-offset",byId("analyzeOffset").value];
    runWorker("compare",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),args,{
      progress:function(percent,message){ setProgress("analyze",percent,message); },
      done:function(result){
        byId("compareFinishedEdit").disabled=false;
        if(!result.ok){updateAnalyzeActionState();setProgress("analyze",0,"Comparison failed");setFooter(result.error);return;}
        comparisonResult=result; updateAnalyzeActionState(); setProgress("analyze",100,"Comparison complete");
        var score=Math.round(Number(result.comparison && result.comparison.score || 0)*100); byId("analyzeMonitorTitle").textContent="Finished edit match: " + score + "%"; setFooter((result.comparison && result.comparison.passed ? "Finished edit passed" : "Repair plan ready") + " | match " + score + "%");
      }
    });
  }

  function openRepairPlan() {
    if (!comparisonResult || !comparisonResult.output) { setFooter("Run Compare Edit first; no repair plan exists yet."); return; }
    openLocalPath(comparisonResult.output,"Repair plan");
  }

  function applySafeRepair() {
    var payload=comparisonResult && comparisonResult.comparison && comparisonResult.comparison.autoRepair;
    if(!payload){setFooter("Run Compare Edit first.");return;}
    runHostPayloadAction("applyReferenceSafeRepairFromFile","safe-repair",payload,byId("applySafeRepair"),"Creating a separate safe-repair composition...",function(result){
      updateAnalyzeActionState();setFooter(result.ok ? result.message : result.error);
    });
  }

  function openAnalysisReport() {
    if (!analysisResult || !analysisResult.htmlReport) { setFooter("Run Analyze first; no report exists yet."); return; }
    openLocalPath(analysisResult.htmlReport,"Analyze report");
  }

  function applyAnalysisMarkers() {
    if (!analysisResult) { setFooter("Run Analyze first; there are no reference markers to apply yet."); return; }
    var payload = {events:analysisResult.events || [],beats:analysisResult.audio && analysisResult.audio.beats || [],offset:Number(byId("analyzeOffset").value) || 0,includeCuts:byId("analyzeMarkerCuts").checked,includeBeats:byId("analyzeMarkerBeats").checked,replace:byId("analyzeReplaceMarkers").checked,source:analysisResult.media && analysisResult.media.name || "reference"};
    if(!payload.events.length && !payload.beats.length){setFooter("The latest analysis contains no cut or beat markers.");return;}
    runHostPayloadAction("applyReferenceAnalysisMarkersFromFile","analysis-markers",payload,byId("applyAnalyzeMarkers"),"Applying the analyzed cut and beat markers in After Effects...",function(result){
      updateAnalyzeActionState();setFooter(result.ok ? result.message : result.error);
    });
  }

  function boundedNumber(value,min,max,fallback) {
    var parsed=Number(value);if(!isFinite(parsed)){parsed=Number(fallback)||0;}return Math.max(min,Math.min(max,parsed));
  }

  function parseOfflineShotNumbers(text) {
    var result=[], match, pattern=/(?:clip|shot|scene)s?\s*(?:number\s*)?#?\s*(\d+(?:\s*[,/&-]\s*\d+)*)/gi;
    while((match=pattern.exec(text))){String(match[1]).split(/\s*[,/&-]\s*/).forEach(function(value){var number=Number(value);if(number>0&&result.indexOf(number)<0){result.push(number);}});}
    return result;
  }

  function compileOfflineEditPolicy() {
    var text=String(byId("offlinePrompt").value||"").trim(), lower=text.toLowerCase(), mode=byId("offlineMode").value || "balanced";
    var policy={
      version:2,mode:mode,prompt:text,seed:Math.round(boundedNumber(byId("offlineSeed").value,1,9999,1)),
      fidelity:boundedNumber(byId("offlineFidelity").value,50,100,92)/100,
      intensity:boundedNumber(byId("offlineIntensity").value,50,160,100)/100,
      transitionDensity:boundedNumber(byId("offlineDensity").value,0,100,85)/100,
      noRepeatWindow:Math.round(boundedNumber(byId("offlineRepeatWindow").value,1,12,5)),
      keepExactCuts:true,autoQA:byId("offlineAutoQA").checked,creativeAccents:mode==="creative",creativeAmount:mode==="creative"?0.72:(mode==="balanced"?0.22:0),
      disabledFamilies:[],familyIntensity:{},durationScale:1,zoomStrength:mode==="creative"?1.12:1,zoomPattern:mode==="exact"?"measured":"energy_alternate",
      avoidRepeats:true,subjectBias:"",changeShots:[],changeRange:{start:null,end:null},freezeClips:false,freezeOutsideRange:false
    };
    if(mode==="exact"){policy.fidelity=1;policy.transitionDensity=1;policy.creativeAccents=false;policy.creativeAmount=0;policy.durationScale=1;}
    if(/no\s+(?:slide|whip)|remove\s+(?:slide|whip)|without\s+(?:slide|whip)/.test(lower)){policy.disabledFamilies.push("slide","whip");}
    if(/no\s+(?:glow|flash)|remove\s+(?:glow|flash)|without\s+(?:glow|flash)/.test(lower)){policy.disabledFamilies.push("glow","flash");}
    if(/no\s+(?:shake|impact)/.test(lower)){policy.disabledFamilies.push("shake","impact");}
    if(/no\s+(?:black dip|black fade|dip)/.test(lower)){policy.disabledFamilies.push("black","dip");}
    if(/less\s+(?:glow|flash)|reduce\s+(?:the\s+)?(?:glow|flash)/.test(lower)){policy.familyIntensity.glow=0.62;policy.familyIntensity.flash=0.62;}
    if(/more\s+(?:glow|flash)|heavier\s+(?:glow|flash)|stronger\s+(?:glow|flash)/.test(lower)){policy.familyIntensity.glow=1.3;policy.familyIntensity.flash=1.3;}
    if(/more\s+(?:directional\s+)?blur|heavier\s+(?:directional\s+)?blur|stronger\s+(?:directional\s+)?blur/.test(lower)){policy.familyIntensity.blur=1.3;}
    if(/less\s+(?:directional\s+)?blur|reduce\s+(?:the\s+)?(?:directional\s+)?blur/.test(lower)){policy.familyIntensity.blur=0.72;}
    if(/faster\s+(?:transition|slide|whip)|shorter\s+transition/.test(lower)){policy.durationScale=0.72;}
    if(/slower\s+(?:transition|slide|whip)|longer\s+transition/.test(lower)){policy.durationScale=1.25;}
    if(/aggressive\s+zoom|stronger\s+zoom|harder\s+zoom|more\s+zoom/.test(lower)){policy.zoomStrength=1.28;}
    if(/subtle\s+zoom|less\s+zoom|reduce\s+(?:the\s+)?zoom/.test(lower)){policy.zoomStrength=0.72;}
    if(/alternate\s+zoom|mix\s+(?:the\s+)?zoom/.test(lower)){policy.zoomPattern="alternate";}
    if(/more\s+(?:couple|together|both|kiss)|focus\s+on\s+(?:the\s+)?couple/.test(lower)){policy.subjectBias="couple";}
    else if(/more\s+aniya|focus\s+on\s+aniya/.test(lower)){policy.subjectBias="aniya";}
    else if(/more\s+carl|focus\s+on\s+carl/.test(lower)){policy.subjectBias="carl";}
    if(/keep\s+(?:all\s+)?(?:the\s+)?clips|only\s+(?:fix|change|adjust)\s+(?:the\s+)?(?:effects|transitions)/.test(lower)){policy.freezeClips=true;}
    if(/replace\s+(?:the\s+)?repeated|avoid\s+repeat|new\s+clips|different\s+clips/.test(lower)){policy.avoidRepeats=true;policy.freezeClips=false;}
    policy.changeShots=parseOfflineShotNumbers(text);
    var after=lower.match(/(?:after|from)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?/), before=lower.match(/(?:before|until|to)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?/);
    if(after){policy.changeRange.start=Number(after[1]);policy.freezeOutsideRange=true;}
    if(before){policy.changeRange.end=Number(before[1]);policy.freezeOutsideRange=true;}
    if(policy.changeShots.length){policy.freezeOutsideRange=true;}
    if(/more\s+creative|surprise\s+me|add\s+creative/.test(lower)){policy.creativeAccents=true;policy.creativeAmount=Math.max(policy.creativeAmount,0.82);}
    if(/strict|exact|same\s+effects|replica/.test(lower)){policy.fidelity=1;policy.keepExactCuts=true;}
    return policy;
  }

  function describeOfflinePolicy(policy) {
    var parts=[policy.mode.replace(/_/g," ")+" mode",Math.round(policy.fidelity*100)+"% reference",Math.round(policy.intensity*100)+"% FX",policy.noRepeatWindow+"-shot repeat guard"];
    if(policy.subjectBias){parts.push("favor "+policy.subjectBias);}
    if(policy.disabledFamilies.length){parts.push("disable "+policy.disabledFamilies.join("/"));}
    if(policy.freezeClips){parts.push("preserve clip choices");}
    if(policy.changeShots.length){parts.push("change shots "+policy.changeShots.join(", "));}
    if(policy.changeRange.start!==null||policy.changeRange.end!==null){parts.push("limited time range");}
    return parts.join(" | ");
  }

  function refreshOfflineDirectivePreview() {
    var policy=compileOfflineEditPolicy(), preview=byId("offlineDirectivePreview");
    preview.querySelector("span").textContent="Validated local policy";
    preview.querySelector("small").textContent=describeOfflinePolicy(policy)+". Cuts remain exact, scene layers never overlap, and source audio stays muted.";
  }

  function offlineBuildPayload(reedit) {
    var policy=compileOfflineEditPolicy();
    return {
      blueprint:analysisResult.editBlueprint,sourceName:analysisResult.media && analysisResult.media.name || "REFERENCE",sourceMedia:analysisResult.sourceMedia || {},
      replicaBuilderContract:analysisResult.replicaBuilderContract || analysisResult.editBlueprint.replicaBuilderContract || {},
      repeats:analysisResult.repeats || analysisResult.editBlueprint.repeatInstructions || [],frameRepeats:analysisResult.frameRepeats || [],analysisManifest:analysisResult.manifest || "",
      audioAlignment:analysisResult.audioAlignment || analysisResult.editBlueprint.audioAlignment || {},blurMo:byId("offlineBlurMo").checked,fullStack:byId("offlineFullStack").checked,
      strictMatch:byId("offlineStrictMatch").checked,policy:policy,sourceCompName:reedit?offlineBuildState.sourceCompName:"",reeditOf:reedit?offlineBuildState.lastCompName:"",
      previousAssignments:reedit?offlineBuildState.assignments:[]
    };
  }

  function dispatchOfflineBuild(reedit) {
    if(!analysisResult || !analysisResult.editBlueprint){setFooter("Analyze a reference first.");return;}
    if(reedit && !offlineBuildState.lastCompName){setFooter("Build the first offline edit before requesting a re-edit.");return;}
    var payload=offlineBuildPayload(reedit),gate=payload.replicaBuilderContract && payload.replicaBuilderContract.buildGate || {};
    if(payload.policy.mode==="exact"&&!gate.exactReady){setFooter("Exact Replica build refused: " + String((gate.blockingCodes || []).join(", ") || "run Deep Replica Lab analysis first"));return;}
    var button=byId(reedit?"reeditOfflineEdit":"buildOfflineEdit"), message=reedit?"Compiling the measured revision into a separate composition...":"Binding footage to the certified frame-native replica contract...";
    runHostPayloadAction("buildOfflineEditFromFile",reedit?"offline-reedit":"offline-edit",payload,button,message,function(result){
      if(result.ok){offlineBuildState.sourceCompName=result.sourceCompName||offlineBuildState.sourceCompName;offlineBuildState.lastCompName=result.compName||"";offlineBuildState.assignments=result.assignments||[];offlineBuildState.lastPrompt=payload.policy.prompt;offlineBuildState.buildCount++;offlineBuildState.lastAudit=result.audit||null;}
      updateAnalyzeActionState();setFooter(result.ok?result.message:result.error);
    });
  }

  function buildOfflineEdit() { dispatchOfflineBuild(false); }
  function reeditOfflineEdit() { dispatchOfflineBuild(true); }

  function auditOfflineEdit() {
    var button=byId("auditOfflineEdit");button.disabled=true;button.classList.add("is-running");setFooter("Auditing the active edit for overlaps, gaps, audio, transition bounds, and effect order...");
    evalHost("TUF.auditOfflineEdit()",function(raw){button.disabled=false;button.classList.remove("is-running");var result=parseResult(raw);if(result.ok){offlineBuildState.lastAudit=result.audit;setFooter(result.message);}else{setFooter(result.error||"Offline edit audit failed");}});
  }

  function importOutputs(outputs,source,kind) {
    if (!outputs || !outputs.length) { return; }
    var payload = {paths:outputs,compIn:source && Number(source.compIn) || 0,kind:kind,addToTimeline:true};
    evalHost('TUF.importLocalEngineOutput("' + escapeForEval(JSON.stringify(payload)) + '")',function (raw) {
      var result = parseResult(raw);
      setFooter(result.ok ? (result.message || "Local output imported") : (result.error || "Import failed"));
    });
  }

  function importEnhanceResults(results) {
    if (!results || !results.length) { return; }
    var entries = [];
    results.forEach(function (result) {
      var outputs = result.outputs || [result.output];
      outputs.forEach(function (output) {
        entries.push({path:output,compIn:Number(result.source && result.source.compIn) || 0,sourceLayerName:result.source && result.source.layerName || ""});
      });
    });
    evalHost('TUF.importLocalEngineOutput("' + escapeForEval(JSON.stringify({entries:entries,kind:"enhance",addToTimeline:true})) + '")',function (raw) {
      var imported = parseResult(raw);
      setFooter(imported.ok ? (imported.message || "Enhanced media imported") : (imported.error || "Import failed"));
    });
  }

  function updatePreview(prefix,output) {
    if (!output) { return; }
    var extension = path.extname(output).toLowerCase();
    var video = byId(prefix + "PreviewVideo"), image = byId(prefix + "PreviewImage"), empty = byId(prefix + "PreviewEmpty");
    if (empty) { empty.classList.add("hidden"); }
    if ([".png",".jpg",".jpeg",".webp",".tif",".tiff"].indexOf(extension) >= 0) {
      if (video) { try { video.pause(); } catch (ignorePause) {} video.classList.remove("active"); video.removeAttribute("src"); video.load(); }
      if (image) { image.src = fileUrl(output) + "?t=" + Date.now(); image.classList.add("active"); }
    } else {
      if (image) { image.classList.remove("active"); image.removeAttribute("src"); }
      if (video) {
        try { video.pause(); } catch (ignorePauseVideo) {}
        video.removeAttribute("src"); video.load();
        video.muted = false; video.defaultMuted = false; video.volume = 1;
        video.onloadedmetadata = function () { try { video.currentTime = 0; } catch (ignoreSeek) {} };
        video.onerror = function () { setFooter("Preview could not decode. The enhanced master remains available and importable."); };
        video.src = fileUrl(output) + "?t=" + Date.now(); video.classList.add("active"); video.load();
      }
    }
  }

  function outputPath(group,sourceName,extension) {
    var directory = path.join(defaultOutputRoot(),group);
    ensureDirectory(directory);
    var stamp = new Date().toISOString().replace(/[-:TZ.]/g,"").slice(0,17);
    outputSequence += 1;
    return path.join(directory,slug(sourceName) + "_TonyFX_" + stamp + "_" + String(outputSequence) + extension);
  }

  function enhanceArguments(source,output) {
    var isImage = /\.(png|jpe?g|webp|tiff?|bmp)$/i.test(source.path);
    var codec = byId("enhanceCodec").value;
    return [
      "--engine-root",defaultEngineRoot(),"enhance","--input",source.path,"--output",output,
      "--start",String(Number(source.sourceStart) || 0),"--duration",String(Number(source.sourceDuration) || 0),
      "--width",byId("enhanceWidth").value,"--height",byId("enhanceHeight").value,"--codec",codec,
      "--compression",String(pairValue("enhanceCompression")),"--detail",String(pairValue("enhanceDetail")),
      "--sharpen",String(pairValue("enhanceSharpen")),"--denoise",String(pairValue("enhanceDenoise")),
      "--dehalo",String(pairValue("enhanceDehalo")),"--deblur",String(pairValue("enhanceDeblur")),
      "--grain",String(pairValue("enhanceGrain")),"--target-fps",byId("enhanceFps").value,"--tile",byId("enhanceTile").value,
      byId("enhanceAI").checked ? "--ai" : "--no-ai",byId("enhanceInterpolate").checked ? "--interpolate" : "--no-interpolate"
    ];
  }

  function processEnhanceQueue(items,index,results) {
    if (enhanceQueueCancelled) { return; }
    if (index >= items.length) {
      setRunState("enhance",false); setProgress("enhance",100,"Complete | " + results.length + "/" + items.length);
      if (results.length) {
        var last = results[results.length - 1];
        byId("enhanceMonitorTitle").textContent = results.length === 1 ? path.basename(last.output) : results.length + " enhanced outputs ready";
        updatePreview("enhance",last.preview || last.output);
        if (byId("enhanceAutoImport").checked) { importEnhanceResults(results); }
      }
      setFooter("Enhanced " + results.length + " item" + (results.length === 1 ? "" : "s") + " locally");
      return;
    }
    var source = items[index];
    var isImage = /\.(png|jpe?g|webp|tiff?|bmp)$/i.test(source.path);
    var codec = byId("enhanceCodec").value;
    var extension = isImage ? ".png" : (codec === "h264" ? ".mp4" : ".mov");
    var output = outputPath("Enhanced",source.layerName || ("item-" + (index + 1)),extension);
    var itemLabel = "Item " + (index + 1) + "/" + items.length;
    runWorker("enhance",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),enhanceArguments(source,output),{
      progress:function (percent,message) {
        var totalPercent = ((index + Math.max(0,Math.min(100,Number(percent) || 0)) / 100) / items.length) * 100;
        setProgress("enhance",totalPercent,itemLabel + " | " + (message || "Processing"));
      },
      done:function (result) {
        if (!result.ok) { setRunState("enhance",false); setProgress("enhance",0,"Failed at " + itemLabel); setFooter(result.error); return; }
        result.source = source; results.push(result); updatePreview("enhance",result.preview || result.output);
        processEnhanceQueue(items,index + 1,results);
      }
    });
  }

  function runEnhance() {
    var selection = sources.enhance, items = selection && selection.items || [];
    if (!items.length) { setFooter("Select AE clips, a composition, or browse to a file first."); return; }
    enhanceQueueCancelled = false; setRunState("enhance",true); setProgress("enhance",1,"Starting 1/" + items.length);
    setFooter("Local enhancement queue running - no Codex usage");
    processEnhanceQueue(items,0,[]);
  }

  var enhancePresets = {
    clean:{enhanceCompression:22,enhanceDetail:28,enhanceSharpen:18,enhanceDenoise:10,enhanceDehalo:6,enhanceDeblur:18,enhanceGrain:0},
    ultra:{enhanceCompression:45,enhanceDetail:42,enhanceSharpen:28,enhanceDenoise:12,enhanceDehalo:8,enhanceDeblur:32,enhanceGrain:0},
    detail:{enhanceCompression:58,enhanceDetail:66,enhanceSharpen:44,enhanceDenoise:8,enhanceDehalo:12,enhanceDeblur:48,enhanceGrain:2},
    soft:{enhanceCompression:34,enhanceDetail:30,enhanceSharpen:14,enhanceDenoise:18,enhanceDehalo:10,enhanceDeblur:18,enhanceGrain:3}
  };

  function applyEnhancePreset(name) {
    var values = enhancePresets[name]; if (!values) { return; }
    Object.keys(values).forEach(function (key) { setPairValue(key,values[key]); });
    document.querySelectorAll("[data-enhance-preset]").forEach(function (button) { button.classList.toggle("active",button.getAttribute("data-enhance-preset") === name); });
  }

  function runAudio() {
    var source = sources.audio;
    if (!source || !source.path) { setFooter("Select an AE audio or video layer first."); return; }
    var output = outputPath("Audio",source.layerName,".wav");
    var args = [
      "--engine-root",defaultEngineRoot(),"audio","--input",source.path,"--output",output,"--operation",audioMode,
      "--start",String(Number(source.sourceStart) || 0),"--duration",String(Number(source.sourceDuration) || 0),
      "--denoise",String(pairValue("audioDenoise")),"--dereverb",String(pairValue("audioDereverb")),"--dehum",String(pairValue("audioDehum")),
      "--presence",String(pairValue("audioPresence")),"--clarity",String(pairValue("audioClarity")),"--compression",String(pairValue("audioCompression")),"--deess",String(pairValue("audioDeess")),
      "--highpass",String(pairValue("audioHighpass")),"--lowpass",String(pairValue("audioLowpass")),byId("audioLoudness").checked ? "--normalize" : "--no-normalize",
      "--demucs-model",byId("audioModel").value
    ];
    setRunState("audio",true); setProgress("audio",2,"Starting local audio worker"); setFooter("Offline Audio Lab running - no Codex usage");
    runWorker("audio",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),args,{
      progress:function (percent,message) { setProgress("audio",percent,message); },
      done:function (result) {
        setRunState("audio",false);
        if (!result.ok) { setProgress("audio",0,"Failed"); setFooter(result.error); return; }
        var outputs = result.outputs || [result.output];
        setProgress("audio",100,result.backend || "Complete"); byId("audioMonitorTitle").textContent = outputs.length + " local output" + (outputs.length === 1 ? "" : "s");
        renderAudioOutputs(outputs); setFooter("Audio ready - " + (result.backend || "local engine"));
        if (byId("audioAutoImport").checked) { importOutputs(outputs,source,"audio"); }
      }
    });
  }

  var audioPresets = {
    natural:{audioDenoise:24,audioDereverb:12,audioDehum:8,audioPresence:24,audioClarity:18,audioCompression:18,audioDeess:14,audioHighpass:65,audioLowpass:17500},
    dialogue:{audioDenoise:38,audioDereverb:26,audioDehum:16,audioPresence:48,audioClarity:35,audioCompression:38,audioDeess:30,audioHighpass:78,audioLowpass:16000},
    broadcast:{audioDenoise:32,audioDereverb:20,audioDehum:12,audioPresence:42,audioClarity:30,audioCompression:52,audioDeess:26,audioHighpass:72,audioLowpass:16800},
    vocal:{audioDenoise:18,audioDereverb:12,audioDehum:6,audioPresence:34,audioClarity:28,audioCompression:28,audioDeess:22,audioHighpass:55,audioLowpass:19000}
  };
  function applyAudioPreset(name) {
    var values=audioPresets[name]; if(!values){return;} Object.keys(values).forEach(function(key){setPairValue(key,values[key]);});
    document.querySelectorAll("[data-audio-preset]").forEach(function(button){button.classList.toggle("active",button.getAttribute("data-audio-preset")===name);});
  }

  function renderAudioOutputs(outputs) {
    var list = byId("audioOutputList"); list.innerHTML = "";
    outputs.forEach(function (output,index) {
      var button = document.createElement("button"); button.textContent = path.basename(output);
      button.addEventListener("click",function () { byId("audioPreview").src = fileUrl(output) + "?t=" + Date.now(); byId("audioPreview").play(); });
      list.appendChild(button);
      if (index === 0) { byId("audioPreview").src = fileUrl(output) + "?t=" + Date.now(); }
    });
  }

  var aspectSizes = {
    image:{square:[1024,1024],portrait:[768,1344],landscape:[1344,768],cinema:[1344,576]},
    video:{square:[512,512],portrait:[416,736],landscape:[736,416],cinema:[768,320]}
  };

  function runGeneration() {
    var prompt = byId("generationPrompt").value.trim();
    if (!prompt) { setFooter("Write a generation prompt first."); return; }
    var size = aspectSizes[generationMode][byId("generationAspect").value] || aspectSizes[generationMode].square;
    var output = outputPath("Generated",generationMode,generationMode === "image" ? ".png" : ".mp4");
    var args;
    if (generationMode === "image") {
      args = ["generate-image","--engine-root",defaultEngineRoot(),"--prompt",prompt,"--negative-prompt",byId("generationNegative").value,"--output",output,"--model",byId("imageModel").value,"--width",String(size[0]),"--height",String(size[1]),"--steps",byId("generationSteps").value,"--guidance",byId("generationGuidance").value,"--seed",byId("generationSeed").value,"--strength",byId("generationStrength").value];
      if (sources.generationReference) { args.push("--input-image",sources.generationReference); }
      } else {
        // The requested action is the authority. Earlier builds always added
        // every dropdown, so an explicit "fast push into the eye" could also
        // receive "locked camera" and "subtle movement". Small local models
        // respond to that contradiction with frozen or warped frames.
        var explicitCamera = /\b(camera|zoom|push[ -]?in|pull[ -]?back|dolly|pan|tilt|orbit|tracking|handheld|whip)\b/i.test(prompt);
        var explicitMotion = /\b(walk|run|turn|look|raise|lower|jump|dance|move|moving|action|gesture|blink|breathe|smile|scream|fight)\b/i.test(prompt);
        var promptParts = [prompt, byId("videoStyle").value, byId("videoFraming").value, byId("videoLens").value, byId("videoLighting").value];
        if (!explicitCamera) { promptParts.push(byId("videoCamera").value); }
        if (!explicitMotion) { promptParts.push(byId("videoMotion").value); }
        promptParts.push("one continuous shot, preserve the same subject and environment, physically coherent motion, no scene change");
        var directedPrompt = promptParts.filter(Boolean).join(", ");
      var fps = Number(byId("generationFps").value) || 24;
      var seconds = Number(byId("generationDuration").value) || 3;
      var quality = byId("videoQuality").value;
      args = ["generate-video","--engine-root",defaultEngineRoot(),"--backend",byId("videoBackend").value,"--prompt",directedPrompt,"--negative-prompt",byId("generationNegative").value,"--output",output,"--model",byId("videoModel").value,"--width",String(size[0]),"--height",String(size[1]),"--duration",String(seconds),"--frames",String(seconds * fps + 1),"--fps",String(fps),"--base-fps",byId("videoBaseFps").value,"--profile",byId("videoProfile").value,"--reference-fit",byId("videoReferenceFit").value,"--quality",quality,"--steps",byId("generationSteps").value,"--guidance",byId("generationGuidance").value,"--seed",byId("generationSeed").value];
      if (sources.generationReference) { args.push("--input-image",sources.generationReference); }
    }
    setRunState("generation",true); setProgress("generation",2,"Loading local generation runtime"); setFooter("Local generation running - no Codex or API usage");
    runWorker("generation",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),args,{
      progress:function (percent,message) { setProgress("generation",percent,message); },
      done:function (result) {
        setRunState("generation",false);
        if (!result.ok) { setProgress("generation",0,"Failed"); setFooter(result.error); return; }
        setProgress("generation",100,result.backend || "Complete"); byId("generationMonitorTitle").textContent = path.basename(result.output);
        updatePreview("generation",result.output); setFooter("Generation ready - " + (result.backend || "local engine"));
        if (byId("generationAutoImport").checked) { importOutputs(result.outputs || [result.output],null,"generation"); }
      }
    });
  }

  function setGenerationMode(mode) {
    generationMode = mode === "video" ? "video" : "image";
    byId("generateTab").setAttribute("data-generation-mode",generationMode);
    document.querySelectorAll("[data-generation-mode]").forEach(function (button) { button.classList.toggle("active",button.getAttribute("data-generation-mode") === generationMode); });
    byId("imageGenerationOptions").classList.toggle("active",generationMode === "image");
    byId("videoGenerationOptions").classList.toggle("active",generationMode === "video");
    byId("generationGuidance").value = generationMode === "image" ? "6.5" : "3";
    byId("generationSteps").value = generationMode === "image" ? "28" : "30";
  }

  function tuneVideoGenerationDefaults() {
    var backend = byId("videoBackend").value;
    var profile = byId("videoProfile").value;
    var quality = byId("videoQuality").value;
    var steps = {draft:12,fast:20,balanced:30,quality:40}[quality] || 30;
    if (backend === "framepack") { steps = Math.max(25,Math.min(35,steps)); byId("videoProfile").value = "identity"; byId("videoBaseFps").value = "24"; }
    else if (profile === "identity") { steps = Math.max(24,steps); byId("videoBaseFps").value = "16"; }
    else if (profile === "realism") { steps = Math.max(20,steps); byId("videoBaseFps").value = "16"; }
    else { byId("videoBaseFps").value = "12"; }
    byId("generationSteps").value = String(steps);
  }

  function matchAspectToReference(filePath) {
    var probe = new Image();
    probe.onload = function () {
      var ratio = probe.naturalWidth / Math.max(1,probe.naturalHeight);
      byId("generationAspect").value = ratio < 0.82 ? "portrait" : (ratio > 1.38 ? "landscape" : "square");
    };
    probe.src = fileUrl(filePath) + "?t=" + Date.now();
  }

  function setHealth(prefix,status,text) {
    var container = byId(prefix + "Health").parentNode;
    container.classList.remove("ready","partial","error"); container.classList.add(status);
    byId(prefix + "Health").textContent = text;
  }

  function probeEngines() {
    if (!nodeAvailable || processes.probe) { return; }
    runWorker("probe",workerPython(),path.join(extensionRoot(),"python","local_engine.py"),["--engine-root",defaultEngineRoot(),"probe"],{
      progress:function () {},
      done:function (result) {
        if (!result.ok) { setHealth("enhance","error","Engine unavailable"); setHealth("audio","error","Engine unavailable"); setHealth("generate","error","Engine unavailable"); setHealth("analyze","error","Analyzer unavailable"); return; }
        setHealth("enhance",result.realEsrgan ? "ready" : "partial",result.realEsrgan ? "Real-ESRGAN ready" : "FFmpeg ready | AI optional");
        setHealth("audio",result.demucs ? "ready" : "partial",result.demucs ? "Background remover ready" : "Setup background remover");
        setHealth("generate",result.diffusers && result.torch ? "ready" : "partial",result.diffusers && result.torch ? "Local diffusion ready" : "Setup generation runtime");
        var visionReady = result.visionEngine && result.visionEngine.ready;
        var forensicReady=!!(result.transitionForensics && result.transitionForensics.ready);
        setHealth("analyze",result.referenceAnalyzer ? "ready" : "partial",result.referenceAnalyzer ? (visionReady && forensicReady ? "Deep transition forensics ready" : visionReady ? "Vision analyzer ready - forensic models incomplete" : "Reference analyzer ready - vision models incomplete") : "Setup analyzer runtime");
      }
    });
  }

  function setupEngine(profile,prefix) {
    if (processes.setup) { setFooter("Another local engine setup is already running."); return; }
    var script = path.join(extensionRoot(),"python","setup_local_engine.py");
    setProgress(prefix,2,"Preparing one-time local setup"); setFooter("Installing TonyFX local " + profile + " engine...");
    runWorker("setup",configuredPython(),script,["--engine-root",defaultEngineRoot(),"--profile",profile],{
      progress:function (percent,message) { setProgress(prefix,percent,message); },
      done:function (result) {
        if (!result.ok) { setProgress(prefix,0,"Setup failed"); setFooter(result.error); return; }
        setProgress(prefix,100,"Setup complete"); setFooter("TonyFX local " + profile + " engine installed"); probeEngines();
      }
    });
  }

  function wireSettings() {
    var engineInput = byId("localEnginePath"), outputInput = byId("localOutputPath"), save = byId("saveSettings");
    if (!engineInput || !outputInput || !save) { return; }
    engineInput.value = defaultEngineRoot(); outputInput.value = defaultOutputRoot();
    save.addEventListener("click",function () {
      if (engineInput.value.trim()) { localStorage.setItem("tonyfx.localEngine",engineInput.value.trim()); }
      if (outputInput.value.trim()) { localStorage.setItem("tonyfx.localOutput",outputInput.value.trim()); }
      probeEngines();
    });
  }

  function wireEvents() {
    pairEngineControls(); wireSettings();
    byId("colorMatchUseTarget").addEventListener("click",function () { inspectColorSource("target"); });
    byId("colorMatchUseReferenceAE").addEventListener("click",function () { inspectColorSource("reference"); });
    byId("colorMatchBrowseReference").addEventListener("click",browseColorReference);
    byId("colorMatchAnalyze").addEventListener("click",function () { runColorMatch(false); });
    byId("colorMatchRender").addEventListener("click",function () { runColorMatch(true); });
    byId("colorMatchApply").addEventListener("click",applyEditableColorMatch);
    byId("colorMatchRemove").addEventListener("click",removeEditableColorMatch);
    byId("colorMatchCancel").addEventListener("click",function () { cancelWorker("colorMatch"); });
    document.querySelectorAll("[data-enhance-source-mode]").forEach(function (button) { button.addEventListener("click",function () { setEnhanceSourceMode(button.getAttribute("data-enhance-source-mode")); }); });
    byId("inspectEnhanceSource").addEventListener("click",inspectEnhanceSources);
    byId("browseEnhanceSource").addEventListener("click",function () { browseSource("enhance"); });
    byId("runEnhance").addEventListener("click",runEnhance); byId("cancelEnhance").addEventListener("click",function () { cancelWorker("enhance"); });
    byId("setupEnhance").addEventListener("click",function () { setupEngine("enhance","enhance"); });
    document.querySelectorAll("[data-enhance-preset]").forEach(function (button) { button.addEventListener("click",function () { applyEnhancePreset(button.getAttribute("data-enhance-preset")); }); });

    byId("inspectAudioSource").addEventListener("click",function () { inspectSelectedSource("audio"); });
    byId("browseAudioSource").addEventListener("click",function () { browseSource("audio"); });
    byId("runAudio").addEventListener("click",runAudio); byId("cancelAudio").addEventListener("click",function () { cancelWorker("audio"); });
    byId("setupAudio").addEventListener("click",function () { setupEngine("audio","audio"); });
    document.querySelectorAll("[data-audio-mode]").forEach(function (button) { button.addEventListener("click",function () { audioMode = button.getAttribute("data-audio-mode"); document.querySelectorAll("[data-audio-mode]").forEach(function (item) { item.classList.toggle("active",item === button); }); }); });
    document.querySelectorAll("[data-audio-preset]").forEach(function(button){button.addEventListener("click",function(){applyAudioPreset(button.getAttribute("data-audio-preset"));});});

    byId("inspectAnalyzeSource").addEventListener("click",inspectAnalyzeSource);
    byId("browseAnalyzeSource").addEventListener("click",function () { browseSource("analyze"); });
    byId("browseAnalyzeSongFolder").addEventListener("click",browseAnalyzeSongFolder);
    byId("browseAnalyzeSongFile").addEventListener("click",browseAnalyzeSongFile);
    byId("clearAnalyzeSong").addEventListener("click",clearAnalyzeSong);
    byId("runAnalyze").addEventListener("click",runAnalyze); byId("cancelAnalyze").addEventListener("click",function () { cancelWorker("analyze"); });
    byId("setupAnalyze").addEventListener("click",function () { setupEngine("analysis","analyze"); });
    byId("openAnalyzeReport").addEventListener("click",openAnalysisReport); byId("applyAnalyzeMarkers").addEventListener("click",applyAnalysisMarkers);
    byId("buildOfflineEdit").addEventListener("click",buildOfflineEdit);
    byId("reeditOfflineEdit").addEventListener("click",reeditOfflineEdit);
    byId("auditOfflineEdit").addEventListener("click",auditOfflineEdit);
    ["offlineMode","offlineFidelity","offlineIntensity","offlineDensity","offlineRepeatWindow","offlineSeed"].forEach(function(id){byId(id).addEventListener("change",function(){refreshOfflineDirectivePreview();updateAnalyzeActionState();});byId(id).addEventListener("input",refreshOfflineDirectivePreview);});
    byId("offlinePrompt").addEventListener("input",refreshOfflineDirectivePreview);
    byId("offlineFidelity").addEventListener("input",function(){byId("offlineFidelityValue").textContent=byId("offlineFidelity").value+"%";});
    byId("offlineIntensity").addEventListener("input",function(){byId("offlineIntensityValue").textContent=byId("offlineIntensity").value+"%";});
    byId("offlineDensity").addEventListener("input",function(){byId("offlineDensityValue").textContent=byId("offlineDensity").value+"%";});
    byId("browseCompareSource").addEventListener("click",browseCompareSource); byId("compareFinishedEdit").addEventListener("click",runCompareFinishedEdit); byId("openRepairPlan").addEventListener("click",openRepairPlan);
    byId("applySafeRepair").addEventListener("click",applySafeRepair);

    document.querySelectorAll("[data-generation-mode]").forEach(function (button) { button.addEventListener("click",function () { setGenerationMode(button.getAttribute("data-generation-mode")); }); });
    byId("browseGenerationReference").addEventListener("click",function () { chooseLocalFile("Choose reference image",["png","jpg","jpeg","webp","tif","tiff"],function (filePath) { sources.generationReference = filePath; byId("generationReferenceName").textContent = path.basename(filePath); matchAspectToReference(filePath); }); });
    byId("clearGenerationReference").addEventListener("click",function () { sources.generationReference = ""; byId("generationReferenceName").textContent = "No reference image"; });
    byId("runGeneration").addEventListener("click",runGeneration); byId("cancelGeneration").addEventListener("click",function () { cancelWorker("generation"); });
    byId("videoQuality").addEventListener("change",tuneVideoGenerationDefaults);
    byId("videoBackend").addEventListener("change",tuneVideoGenerationDefaults);
    byId("videoProfile").addEventListener("change",tuneVideoGenerationDefaults);
    byId("setupGenerate").addEventListener("click",function () { setupEngine("video","generation"); });
  }

  function boot() {
    setGenerationMode("video");
    setEnhanceSourceMode("clips");
    if (!nodeAvailable) {
      document.querySelectorAll("[data-generation-mode]").forEach(function (button) {
        button.addEventListener("click",function () { setGenerationMode(button.getAttribute("data-generation-mode")); });
      });
      setHealth("enhance","error","Node unavailable");
      setHealth("audio","error","Node unavailable");
      setHealth("generate","error","Node unavailable");
      setHealth("analyze","error","Node unavailable");
      return;
    }
    wireEvents(); refreshOfflineDirectivePreview(); updateAnalyzeActionState(); probeEngines();
    if (core) { core.initializeIcons(); }
  }

  document.addEventListener("DOMContentLoaded",boot);
}());
