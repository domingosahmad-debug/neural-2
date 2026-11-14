(function () {
  "use strict";

  var core = window.TonyFXCore;
  var nodeAvailable = typeof require === "function";
  var fs = nodeAvailable ? require("fs") : null;
  var path = nodeAvailable ? require("path") : null;
  var os = nodeAvailable ? require("os") : null;
  var childProcess = nodeAvailable ? require("child_process") : null;
  var captionProcess = null;
  var captionSource = null;
  var selectedIcon = "star";
  var selectedTextFx = "cleanReveal";

  function byId(id) { return document.getElementById(id); }

  function escapeForEval(value) {
    return String(value).replace(/\\/g, "\\\\").replace(/\"/g, "\\\"").replace(/\r/g, "\\r").replace(/\n/g, "\\n");
  }

  function parseResult(raw) {
    return core && core.parseResult ? core.parseResult(raw) : (function () { try { return JSON.parse(raw); } catch (error) { return {ok:false,error:String(raw || error)}; } }());
  }

  function evalHost(script, callback) {
    if (core && core.evalHost) { core.evalHost(script, callback); return; }
    if (window.__adobe_cep__) { window.__adobe_cep__.evalScript(script, callback || function () {}); }
  }

  function setFooter(message) { if (core && core.setFooter) { core.setFooter(message); } }

  function showLocalResult(raw, successMessage) {
    var result = parseResult(raw);
    setFooter(result.ok ? (result.message || successMessage) + " - no Codex usage" : (result.error || "Local action failed"));
    return result;
  }

  function setLayout(layout, persist) {
    var selected = layout === "guided" ? "guided" : "pro";
    document.body.setAttribute("data-layout", selected);
    document.querySelectorAll("[data-layout-option]").forEach(function (button) {
      var active = button.getAttribute("data-layout-option") === selected;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    if (persist) { localStorage.setItem("tonyfx.layout", selected); }
    if (selected === "guided" && core) { core.selectTab("home"); }
    if (selected === "pro" && document.querySelector(".tab.active[data-tab='home']") && core) { core.selectTab("chat"); }
  }

  function wireLayout() {
    setLayout(localStorage.getItem("tonyfx.layout") || "pro", false);
    document.querySelectorAll("[data-layout-option]").forEach(function (button) {
      button.addEventListener("click", function () { setLayout(button.getAttribute("data-layout-option"), true); });
    });
    document.querySelectorAll("[data-guided-tab]").forEach(function (button) {
      button.addEventListener("click", function () { if (core) { core.selectTab(button.getAttribute("data-guided-tab")); } });
    });
  }

  function hexToRgb(hex) {
    var value = String(hex || "#ffffff").replace("#", "");
    return [parseInt(value.slice(0,2),16) || 0, parseInt(value.slice(2,4),16) || 0, parseInt(value.slice(4,6),16) || 0];
  }

  function pairControls(rangeId, numberId, callback) {
    var range = byId(rangeId), number = byId(numberId);
    if (!range || !number) { return; }
    range.addEventListener("input", function () { number.value = range.value; callback(); });
    number.addEventListener("input", function () { range.value = number.value; callback(); });
  }

  function textStylePayload() {
    return {
      font: byId("textStyleFont").value,
      fontSize: Number(byId("textStyleSize").value) || 58,
      fill: hexToRgb(byId("textStyleFill").value),
      strokeEnabled: byId("textStyleStrokeEnabled").checked,
      stroke: hexToRgb(byId("textStyleStroke").value),
      strokeWidth: Number(byId("textStyleStrokeWidth").value) || 0,
      shadowEnabled: byId("textStyleShadowEnabled").checked,
      shadowColor: [0,0,0],
      shadowOpacity: Number(byId("textStyleShadowOpacityNumber").value) || 0,
      shadowDistance: Number(byId("textStyleShadowDistanceNumber").value) || 0,
      shadowSoftness: Number(byId("textStyleShadowSoftnessNumber").value) || 0,
      shadowDirection: Number(byId("textStyleShadowDirectionNumber").value) || 135,
      glowEnabled: byId("textStyleGlowEnabled").checked,
      glowIntensity: Number(byId("textStyleGlowIntensityNumber").value) || 0,
      glowRadius: Number(byId("textStyleGlowRadiusNumber").value) || 0
    };
  }

  function updateTextStylePreview() {
    var values = textStylePayload(), target = byId("textStylePreview").querySelector("span");
    target.style.fontFamily = byId("textStyleFont").options[byId("textStyleFont").selectedIndex].text.replace(" Bold", "");
    target.style.fontSize = Math.max(18, Math.min(76, values.fontSize * 0.76)) + "px";
    target.style.color = byId("textStyleFill").value;
    target.style.webkitTextStroke = values.strokeEnabled ? values.strokeWidth + "px " + byId("textStyleStroke").value : "0 transparent";
    var shadows = [];
    if (values.shadowEnabled) { shadows.push("0 " + Math.max(2, values.shadowDistance * 0.5) + "px " + Math.max(2, values.shadowSoftness * 0.5) + "px rgba(0,0,0," + values.shadowOpacity / 100 + ")"); }
    if (values.glowEnabled) { shadows.push("0 0 " + Math.max(3, values.glowRadius * 0.35) + "px " + byId("textStyleFill").value); }
    target.style.textShadow = shadows.join(",");
  }

  var textLooks = {
    clean:{fill:"#ffffff",stroke:false,shadow:true,shadowOpacity:62,shadowDistance:10,shadowSoftness:24,glow:false,glowIntensity:0,glowRadius:0},
    soft:{fill:"#fff6ef",stroke:false,shadow:true,shadowOpacity:48,shadowDistance:8,shadowSoftness:36,glow:true,glowIntensity:0.55,glowRadius:26},
    neon:{fill:"#86fff3",stroke:false,shadow:true,shadowOpacity:78,shadowDistance:5,shadowSoftness:20,glow:true,glowIntensity:1.75,glowRadius:58},
    cinema:{fill:"#f4ead8",stroke:false,shadow:true,shadowOpacity:72,shadowDistance:14,shadowSoftness:32,glow:true,glowIntensity:0.35,glowRadius:18},
    impact:{fill:"#ffffff",stroke:true,strokeColor:"#101010",strokeWidth:3,shadow:true,shadowOpacity:82,shadowDistance:12,shadowSoftness:12,glow:false,glowIntensity:0,glowRadius:0}
  };

  var textFxCatalog = [
    {id:"none",name:"No Additional FX",detail:"Keep only the selected caption animation",preview:"none"},
    {id:"cleanReveal",name:"Clean Reveal",detail:"Opacity reveal with editable selector",preview:"none"},
    {id:"deepShadow",name:"Deep Shadow",detail:"Layered dimensional drop shadow",preview:"deepShadow"},
    {id:"longShadow",name:"Long Shadow",detail:"Graphic stacked shadow treatment",preview:"longShadow"},
    {id:"dualGlow",name:"Dual Glow",detail:"Cool and warm chromatic bloom",preview:"dualGlow"},
    {id:"neonTube",name:"Neon Tube",detail:"Bright core with soft outer glow",preview:"neonTube"},
    {id:"bevelEdge",name:"Bevel Edge",detail:"Editable highlight and depth edge",preview:"bevelEdge"},
    {id:"sweep",name:"Highlight Sweep",detail:"Fast luminous word reveal",preview:"sweep"},
    {id:"flipX",name:"3D Flip X",detail:"Per-character X-axis rotation",preview:"flipX"},
    {id:"flipY",name:"3D Flip Y",detail:"Per-character Y-axis rotation",preview:"flipY"},
    {id:"depthPush",name:"3D Depth Push",detail:"Characters arrive from Z depth",preview:"depthPush"},
    {id:"cascade3d",name:"3D Cascade",detail:"Rotated staggered depth reveal",preview:"cascade3d"},
    {id:"blurTrack",name:"Blur + Tracking",detail:"Wide tracking resolves into focus",preview:"blurTrack"},
    {id:"impact3d",name:"3D Impact",detail:"Sharp depth punch with overshoot",preview:"impact3d"},
    {id:"softBloom",name:"Soft Bloom",detail:"Clean luminous core and broad bloom",preview:"softBloom"},
    {id:"chromaticShadow",name:"Chromatic Shadow",detail:"Red and cyan dimensional edge shadows",preview:"chromaticShadow"},
    {id:"echoTrail",name:"Echo Trail",detail:"Layered directional text trail",preview:"echoTrail"},
    {id:"focusSnap",name:"Focus Snap",detail:"Blurred scale resolves sharply",preview:"focusSnap"},
    {id:"kineticTilt",name:"Kinetic Tilt",detail:"Fast angled character entrance",preview:"kineticTilt"}
  ];

  function selectedTextFxPayload(source) {
    var effectId = source === "caption" ? byId("captionTextFx").value : selectedTextFx;
    return {
      id: effectId || "cleanReveal",
      strength: Number(source === "caption" ? byId("captionFxStrength").value : byId("textFxStrengthNumber").value) || 100,
      duration: Number(source === "caption" ? 18 : byId("textFxDurationNumber").value) || 18
    };
  }

  function renderTextFxCards() {
    var grid = byId("textFxGrid"), captionSelect = byId("captionTextFx");
    var captionSelection = captionSelect.value || "none";
    grid.innerHTML = ""; captionSelect.innerHTML = "";
    textFxCatalog.forEach(function (item) {
      if (item.id !== "none") {
        var button = document.createElement("button");
        button.className = "text-fx-card" + (item.id === selectedTextFx ? " active" : "");
        button.setAttribute("data-text-fx-card", item.id);
        button.innerHTML = "<strong>" + item.name + "</strong><small>" + item.detail + "</small>";
        button.addEventListener("click", function () { selectedTextFx = item.id; renderTextFxCards(); updateTextFxPreview(); });
        grid.appendChild(button);
      }
      var option = document.createElement("option"); option.value = item.id; option.textContent = item.name; captionSelect.appendChild(option);
    });
    captionSelect.value = captionSelection;
  }

  function textFxPreviewName(id) {
    for (var i = 0; i < textFxCatalog.length; i++) { if (textFxCatalog[i].id === id) { return textFxCatalog[i]; } }
    return textFxCatalog[0];
  }

  function updateTextFxPreview() {
    var item = textFxPreviewName(selectedTextFx), preview = byId("textFxPreview");
    preview.setAttribute("data-text-fx", item.preview);
    byId("selectedTextFxName").textContent = item.name + " selected";
  }

  function captionStylePayload() {
    var look = textLooks[byId("captionLook").value] || textLooks.clean;
    return {
      font: byId("textStyleFont").value,
      fontSize: Number(byId("captionFontSize").value) || 48,
      fill: hexToRgb(look.fill || "#ffffff"),
      strokeEnabled: !!look.stroke,
      stroke: hexToRgb(look.strokeColor || "#111111"),
      strokeWidth: Number(look.strokeWidth) || 0,
      shadowEnabled: !!look.shadow,
      shadowColor: [0,0,0],
      shadowOpacity: Number(look.shadowOpacity) || 0,
      shadowDistance: Number(look.shadowDistance) || 0,
      shadowSoftness: Number(look.shadowSoftness) || 0,
      shadowDirection: 135,
      glowEnabled: !!look.glow,
      glowIntensity: Number(look.glowIntensity) || 0,
      glowRadius: Number(look.glowRadius) || 0
    };
  }

  function updateCaptionPreview() {
    var style = captionStylePayload(), fx = textFxPreviewName(byId("captionTextFx").value), target = byId("captionPreview");
    target.setAttribute("data-text-fx", fx.preview);
    target.style.fontFamily = byId("textStyleFont").options[byId("textStyleFont").selectedIndex].text.replace(" Bold", "");
    target.style.fontSize = Math.max(16, Math.min(34, style.fontSize * 0.48)) + "px";
    target.style.color = "rgb(" + style.fill.join(",") + ")";
    target.style.webkitTextStroke = style.strokeEnabled ? style.strokeWidth + "px rgb(" + style.stroke.join(",") + ")" : "0 transparent";
    if (style.shadowEnabled && fx.preview === "none") { target.style.textShadow = "0 " + Math.max(2, style.shadowDistance * 0.45) + "px " + Math.max(2, style.shadowSoftness * 0.45) + "px rgba(0,0,0," + style.shadowOpacity / 100 + ")"; }
    else { target.style.textShadow = ""; }
  }

  function wireTextFx() {
    renderTextFxCards(); updateTextFxPreview(); updateCaptionPreview();
    pairControls("textFxStrength","textFxStrengthNumber",updateTextFxPreview);
    pairControls("textFxDuration","textFxDurationNumber",updateTextFxPreview);
    byId("applyTextFx").addEventListener("click", function () {
      setFooter("Applying editable text treatment locally...");
      evalHost('TUF.applyTextEffect("' + escapeForEval(JSON.stringify(selectedTextFxPayload("create"))) + '")', function (raw) { showLocalResult(raw, "Text treatment applied"); });
    });
  }

  function applyTextLook(name) {
    var look = textLooks[name]; if (!look) { return; }
    byId("textStyleFill").value = look.fill;
    byId("textStyleStrokeEnabled").checked = look.stroke;
    if (look.strokeColor) { byId("textStyleStroke").value = look.strokeColor; }
    if (look.strokeWidth !== undefined) { byId("textStyleStrokeWidth").value = look.strokeWidth; }
    byId("textStyleShadowEnabled").checked = look.shadow;
    byId("textStyleShadowOpacity").value = byId("textStyleShadowOpacityNumber").value = look.shadowOpacity;
    byId("textStyleShadowDistance").value = byId("textStyleShadowDistanceNumber").value = look.shadowDistance;
    byId("textStyleShadowSoftness").value = byId("textStyleShadowSoftnessNumber").value = look.shadowSoftness;
    byId("textStyleGlowEnabled").checked = look.glow;
    byId("textStyleGlowIntensity").value = byId("textStyleGlowIntensityNumber").value = look.glowIntensity;
    byId("textStyleGlowRadius").value = byId("textStyleGlowRadiusNumber").value = look.glowRadius;
    document.querySelectorAll("[data-text-look]").forEach(function (button) { button.classList.toggle("active", button.getAttribute("data-text-look") === name); });
    updateTextStylePreview();
  }

  function wireTextStyle() {
    ["textStyleFont","textStyleSize","textStyleFill","textStyleStrokeEnabled","textStyleStroke","textStyleStrokeWidth","textStyleShadowEnabled","textStyleGlowEnabled"].forEach(function (id) {
      byId(id).addEventListener("input", updateTextStylePreview);
      byId(id).addEventListener("change", updateTextStylePreview);
    });
    pairControls("textStyleShadowOpacity","textStyleShadowOpacityNumber",updateTextStylePreview);
    pairControls("textStyleShadowDistance","textStyleShadowDistanceNumber",updateTextStylePreview);
    pairControls("textStyleShadowSoftness","textStyleShadowSoftnessNumber",updateTextStylePreview);
    pairControls("textStyleShadowDirection","textStyleShadowDirectionNumber",updateTextStylePreview);
    pairControls("textStyleGlowIntensity","textStyleGlowIntensityNumber",updateTextStylePreview);
    pairControls("textStyleGlowRadius","textStyleGlowRadiusNumber",updateTextStylePreview);
    document.querySelectorAll("[data-text-look]").forEach(function (button) { button.addEventListener("click", function () { applyTextLook(button.getAttribute("data-text-look")); }); });
    byId("applyTextStyle").addEventListener("click", function () {
      setFooter("Applying text appearance locally...");
      evalHost('TUF.applyTextStyle("' + escapeForEval(JSON.stringify(textStylePayload())) + '")', function (raw) { showLocalResult(raw, "Text style applied"); });
    });
    var animationSelect=byId("textComposeAnimation");
    (window.TUF_PRESETS||[]).filter(function(preset){return preset.tool==="textMotion";}).forEach(function(preset){
      var option=document.createElement("option"); option.value=preset.id; option.textContent=preset.name; animationSelect.appendChild(option);
    });
    animationSelect.value="text-word-fade";
    byId("createStyledText").addEventListener("click",function(){
      var animation=null;
      (window.TUF_PRESETS||[]).some(function(preset){if(preset.id===animationSelect.value){animation={};Object.keys(preset).forEach(function(key){animation[key]=preset[key];});return true;}return false;});
      if(!animation){animation={id:"text-word-fade",name:"Word Fade",tool:"textMotion",mode:"opacity",unit:"words",duration:22};}
      animation.duration=Math.max(6,Number(byId("textComposeEntry").value)||22);
      animation.exitDuration=Math.max(6,Number(byId("textComposeExit").value)||22);
      animation.matchedExit=byId("textComposeMatchedExit").checked;
      var payload={text:byId("textComposeValue").value,placement:byId("textComposePlacement").value,durationFrames:Math.max(30,Number(byId("textComposeDuration").value)||150),matchedExit:animation.matchedExit,exitDuration:animation.exitDuration,style:textStylePayload(),animation:animation,textEffect:selectedTextFxPayload("create")};
      setFooter("Creating styled text with matched entry and exit locally...");
      evalHost('TUF.createStyledText("' + escapeForEval(JSON.stringify(payload)) + '")',function(raw){showLocalResult(raw,"Styled text created");});
    });
    updateTextStylePreview();
  }

  var icons = [
    {id:"star",label:"Star",glyph:"star"},{id:"heart",label:"Heart",glyph:"heart"},{id:"sparkle",label:"Sparkle",glyph:"sparkles"},
    {id:"play",label:"Play",glyph:"play"},{id:"pause",label:"Pause",glyph:"pause"},{id:"music",label:"Music",glyph:"music-2"},
    {id:"camera",label:"Camera",glyph:"camera"},{id:"bolt",label:"Bolt",glyph:"zap"},{id:"check",label:"Check",glyph:"check"},
    {id:"x",label:"Close",glyph:"x"},{id:"plus",label:"Plus",glyph:"plus"},{id:"diamond",label:"Diamond",glyph:"diamond"},
    {id:"arrow-left",label:"Arrow Left",glyph:"arrow-left"},{id:"arrow-right",label:"Arrow Right",glyph:"arrow-right"},{id:"chevron",label:"Chevron",glyph:"chevron-down"},
    {id:"circle",label:"Circle",glyph:"circle"},{id:"square",label:"Square",glyph:"square"},{id:"triangle",label:"Triangle",glyph:"triangle"}
  ];

  function renderIcons() {
    var query = byId("iconSearch").value.trim().toLowerCase(), grid = byId("iconGrid"); grid.innerHTML = "";
    icons.forEach(function (icon) {
      if (query && icon.label.toLowerCase().indexOf(query) < 0) { return; }
      var button = document.createElement("button"); button.className = "icon-tile" + (selectedIcon === icon.id ? " active" : "");
      button.innerHTML = '<span data-lucide="' + icon.glyph + '"></span><small>' + icon.label + '</small>';
      button.addEventListener("click", function () { selectedIcon = icon.id; byId("selectedIconName").textContent = icon.label + " selected"; renderIcons(); });
      grid.appendChild(button);
    });
    if (core) { core.initializeIcons(); }
  }

  function wireIcons() {
    byId("iconSearch").addEventListener("input", renderIcons);
    byId("addIcon").addEventListener("click", function () {
      var payload = {icon:selectedIcon,color:hexToRgb(byId("iconColor").value),size:Number(byId("iconSize").value) || 180};
      setFooter("Adding vector icon locally...");
      evalHost('TUF.createIcon("' + escapeForEval(JSON.stringify(payload)) + '")', function (raw) { showLocalResult(raw, "Icon added"); });
    });
    renderIcons();
  }

  function setCaptionProgress(percent, text) {
    byId("captionProgressFill").style.width = Math.max(0, Math.min(100, percent)) + "%";
    byId("captionProgressText").textContent = text;
  }

  function inspectCaptionSource(callback) {
    setCaptionProgress(2, "Inspecting selected media...");
    evalHost("TUF.getCaptionSourceSelection()", function (raw) {
      var result = parseResult(raw);
      if (!result.ok) { captionSource = null; byId("captionSourceStatus").textContent = result.error; setCaptionProgress(0, "Select one media layer"); setFooter(result.error); return; }
      captionSource = result;
      byId("captionSourceStatus").textContent = result.layerName + " | " + result.sourceDuration.toFixed(2) + " seconds" + (result.reverse ? " | reverse timing mapped" : "") + (result.timeRemapped ? " | time-remap timing mapped" : "");
      setCaptionProgress(4, "Source ready");
      if (callback) { callback(result); }
    });
  }

  function extensionRoot() {
    if (!nodeAvailable) { return ""; }
    var localPath = decodeURIComponent(window.location.pathname || "").replace(/^\/([A-Za-z]:)/, "$1").replace(/\//g, path.sep);
    return path.dirname(localPath);
  }

  function captionModelPath(modelName) {
    if (modelName === "small.en") { return "C:\\Users\\TUF\\Documents\\New project\\models\\faster-whisper-small.en"; }
    return localStorage.getItem("tonyfx.captionModel") || "C:\\Users\\TUF\\Documents\\New project\\caption_song_test\\faster_whisper_large_v3_turbo";
  }

  function generateCaptions() {
    if (!nodeAvailable) { setCaptionProgress(0, "Node.js is unavailable in this panel"); return; }
    if (captionProcess) { return; }
    inspectCaptionSource(function (source) {
      var language = byId("captionLanguage").value, modelName = byId("captionModel").value;
      if (language === "ar" && modelName === "small.en") { modelName = "large-v3-turbo"; byId("captionModel").value = modelName; }
      var python = localStorage.getItem("tonyfx.python") || "C:\\Users\\TUF\\AppData\\Local\\Programs\\Python\\Python312\\python.exe";
      var script = path.join(extensionRoot(), "python", "auto_caption.py"), model = captionModelPath(modelName);
      var output = path.join(os.tmpdir(), "tonyfx-captions-" + Date.now() + ".json");
      if (!fs.existsSync(python)) { setCaptionProgress(0, "Python executable not found. Set it in Settings."); return; }
      if (!fs.existsSync(script)) { setCaptionProgress(0, "TonyFX caption worker is missing."); return; }
      if (!fs.existsSync(model)) { setCaptionProgress(0, "Whisper model not found. Set its path in Settings."); return; }
      var args = [script,"--input",source.path,"--output",output,"--model",model,"--language",language,"--start",String(source.sourceStart),"--duration",String(source.sourceDuration),"--words",String(Number(byId("captionWords").value) || 4)];
      setCaptionProgress(8, "Loading local speech model..."); setFooter("Offline transcription running - no Codex usage");
      byId("generateCaptions").disabled = true; byId("cancelCaptions").classList.remove("hidden");
      captionProcess = childProcess.spawn(python,args,{windowsHide:true});
      var stderr = "", stdout = "";
      captionProcess.stdout.on("data", function (chunk) {
        stdout += chunk.toString();
        var matches = stdout.match(/PROGRESS\s+(\d+)/g);
        if (matches && matches.length) { var last = Number(matches[matches.length-1].replace(/\D/g,"")); setCaptionProgress(Math.max(10,Math.min(92,last)),"Transcribing locally... " + last + "%"); }
      });
      captionProcess.stderr.on("data", function (chunk) { stderr += chunk.toString(); });
      captionProcess.on("error", function (error) { captionProcess = null; byId("generateCaptions").disabled = false; byId("cancelCaptions").classList.add("hidden"); setCaptionProgress(0,"Caption worker failed: " + error.message); });
      captionProcess.on("close", function (code) {
        captionProcess = null; byId("generateCaptions").disabled = false; byId("cancelCaptions").classList.add("hidden");
        if (code !== 0 || !fs.existsSync(output)) { setCaptionProgress(0,"Transcription failed"); setFooter((stderr || "Offline transcription failed").slice(-500)); return; }
        var data;
        try { data = JSON.parse(fs.readFileSync(output,"utf8")); fs.unlinkSync(output); } catch (error) { setCaptionProgress(0,"Could not read transcript"); return; }
        if (!data.captions || !data.captions.length) { setCaptionProgress(0,"No speech detected in the selected range"); return; }
        data.compIn = source.compIn; data.compDuration = source.compDuration; data.sourceDuration = source.sourceDuration; data.reverse = !!source.reverse;
        data.placement = byId("captionPlacement").value; data.animation = byId("captionAnimation").value; data.fontSize = Number(byId("captionFontSize").value) || 48;
        data.matchedExit = byId("captionMatchedExit").checked; data.exitDuration = Math.max(6,Number(byId("captionExitFrames").value)||14);
        data.style = captionStylePayload(); data.textEffect = selectedTextFxPayload("caption");
        setCaptionProgress(94,"Creating editable AE text layers...");
        evalHost('TUF.createCaptions("' + escapeForEval(JSON.stringify(data)) + '")', function (raw) {
          var result = showLocalResult(raw,"Offline captions created");
          setCaptionProgress(result.ok ? 100 : 0,result.ok ? (data.captions.length + " captions created | " + (data.language || language)) : (result.error || "Caption creation failed"));
        });
      });
    });
  }

  function wireCaptions() {
    byId("inspectCaptionSource").addEventListener("click", function () { inspectCaptionSource(); });
    byId("generateCaptions").addEventListener("click", generateCaptions);
    byId("cancelCaptions").addEventListener("click", function () { if (captionProcess) { captionProcess.kill(); captionProcess = null; } byId("generateCaptions").disabled = false; byId("cancelCaptions").classList.add("hidden"); setCaptionProgress(0,"Cancelled"); });
    ["captionAnimation","captionLook","captionTextFx","captionFontSize","captionFxStrength"].forEach(function (id) {
      byId(id).addEventListener("input", updateCaptionPreview); byId(id).addEventListener("change", updateCaptionPreview);
    });
  }

  function boot() {
    wireLayout(); wireTextStyle(); wireTextFx(); wireIcons(); wireCaptions();
  }

  document.addEventListener("DOMContentLoaded", boot);
}());
