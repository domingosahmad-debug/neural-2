(function () {
  "use strict";

  var hasCEP = !!window.__adobe_cep__;
  var nodeAvailable = typeof require === "function";
  var childProcess = nodeAvailable ? require("child_process") : null;
  var fs = nodeAvailable ? require("fs") : null;
  var os = nodeAvailable ? require("os") : null;
  var path = nodeAvailable ? require("path") : null;
  var runningProcess = null;
  var typingBubble = null;
  var bridgeTimer = null;
  var bridgeBusy = false;
  var bridgeTimeoutTimer = null;
  var bridgeHeartbeatTimer = null;
  var bridgeLockPath = "";
  var bridgeActiveCommandId = "";
  var bridgeOwnerId = "tonyfx-" + Date.now() + "-" + Math.random().toString(36).slice(2);
  var bridgeLastProcessedId = localStorage.getItem("tonyfx.bridge.lastProcessedId") || "";
  var bridgeTimeoutMs = 65 * 60 * 1000;
  var usageTimer = null;
  var colorTimer = null;
  var previewTimer = null;
  var previewIndex = 0;
  var previewSources = ["assets/effect-preview-a.mp4", "assets/effect-preview-b.mp4"];

  var state = {
    inspectBeforeSend: true,
    theme: localStorage.getItem("tonyfx.theme") || "classic",
    sessionId: localStorage.getItem("tuf.codexSession") || "",
    presetCategory: "All",
    favoritesOnly: false,
    favorites: JSON.parse(localStorage.getItem("tuf.favorites") || "[]"),
    recent: JSON.parse(localStorage.getItem("tuf.recent") || "[]"),
    settings: {
      workspace: localStorage.getItem("tuf.workspace") || "C:\\Users\\TUF\\Documents\\New project",
      bridge: localStorage.getItem("tuf.bridge") || "C:\\Users\\TUF\\Documents\\ae-mcp-bridge",
      python: localStorage.getItem("tonyfx.python") || "C:\\Users\\TUF\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      captionModel: localStorage.getItem("tonyfx.captionModel") || "C:\\Users\\TUF\\Documents\\New project\\caption_song_test\\faster_whisper_large_v3_turbo"
    },
    lastSnapshot: null,
    colorLive: localStorage.getItem("tonyfx.colorLive") !== "false",
    graphMode: "easing",
    selectedGraph: "approved-ramp",
    customGraphs: JSON.parse(localStorage.getItem("tonyfx.customGraphs") || "[]"),
    selectedText: "text-word-fade",
    selectedMotion: "scale-impact",
    selectedEffect: "flash-smear-cut"
  };

  var gradePresets = {
    neutral: {temperature:0,tint:0,exposure:0,contrast:0,highlights:0,shadows:0,whites:0,blacks:0,saturation:100,vibrance:0,sharpen:0,fadedFilm:0,creativeSaturation:100,vignetteAmount:0,vignetteMidpoint:50,vignetteRoundness:0,vignetteFeather:50},
    clean: {temperature:2,tint:1,exposure:0.18,contrast:12,highlights:-16,shadows:18,whites:8,blacks:-8,saturation:106,vibrance:16,sharpen:10,fadedFilm:0,creativeSaturation:104,vignetteAmount:-0.35,vignetteMidpoint:48,vignetteRoundness:8,vignetteFeather:72},
    warm: {temperature:12,tint:5,exposure:0.12,contrast:9,highlights:-20,shadows:14,whites:5,blacks:-5,saturation:108,vibrance:20,sharpen:6,fadedFilm:6,creativeSaturation:106,vignetteAmount:-0.55,vignetteMidpoint:45,vignetteRoundness:16,vignetteFeather:78},
    cool: {temperature:-12,tint:3,exposure:0.08,contrast:18,highlights:-25,shadows:12,whites:8,blacks:-14,saturation:96,vibrance:12,sharpen:14,fadedFilm:2,creativeSaturation:98,vignetteAmount:-0.7,vignetteMidpoint:42,vignetteRoundness:5,vignetteFeather:66},
    night: {temperature:-5,tint:4,exposure:0.38,contrast:8,highlights:-34,shadows:35,whites:2,blacks:-5,saturation:104,vibrance:22,sharpen:8,fadedFilm:4,creativeSaturation:104,vignetteAmount:-0.45,vignetteMidpoint:52,vignetteRoundness:0,vignetteFeather:80},
    tealOrange: {temperature:7,tint:-5,exposure:0.08,contrast:24,highlights:-28,shadows:18,whites:10,blacks:-18,saturation:112,vibrance:28,sharpen:12,fadedFilm:1,creativeSaturation:108,vignetteAmount:-0.75,vignetteMidpoint:43,vignetteRoundness:12,vignetteFeather:72},
    filmWarm: {temperature:15,tint:4,exposure:0.05,contrast:17,highlights:-30,shadows:20,whites:4,blacks:-12,saturation:104,vibrance:14,sharpen:5,fadedFilm:13,creativeSaturation:101,vignetteAmount:-0.8,vignetteMidpoint:40,vignetteRoundness:18,vignetteFeather:82},
    bleach: {temperature:-3,tint:1,exposure:0.1,contrast:38,highlights:-18,shadows:-4,whites:17,blacks:-25,saturation:66,vibrance:-14,sharpen:22,fadedFilm:3,creativeSaturation:72,vignetteAmount:-0.65,vignetteMidpoint:46,vignetteRoundness:-4,vignetteFeather:58},
    cyber: {temperature:-10,tint:18,exposure:0.14,contrast:27,highlights:-24,shadows:12,whites:14,blacks:-20,saturation:124,vibrance:42,sharpen:16,fadedFilm:0,creativeSaturation:118,vignetteAmount:-1.05,vignetteMidpoint:38,vignetteRoundness:6,vignetteFeather:60},
    golden: {temperature:25,tint:7,exposure:0.2,contrast:11,highlights:-32,shadows:24,whites:8,blacks:-8,saturation:112,vibrance:26,sharpen:7,fadedFilm:5,creativeSaturation:108,vignetteAmount:-0.5,vignetteMidpoint:52,vignetteRoundness:20,vignetteFeather:84},
    pastel: {temperature:5,tint:6,exposure:0.3,contrast:-12,highlights:-24,shadows:30,whites:5,blacks:12,saturation:92,vibrance:18,sharpen:4,fadedFilm:18,creativeSaturation:94,vignetteAmount:-0.18,vignetteMidpoint:58,vignetteRoundness:22,vignetteFeather:90},
    moodyGreen: {temperature:-7,tint:-13,exposure:0.05,contrast:25,highlights:-38,shadows:17,whites:-2,blacks:-22,saturation:87,vibrance:9,sharpen:12,fadedFilm:8,creativeSaturation:90,vignetteAmount:-1.1,vignetteMidpoint:36,vignetteRoundness:-5,vignetteFeather:68},
    sunset: {temperature:19,tint:16,exposure:0.14,contrast:19,highlights:-29,shadows:21,whites:9,blacks:-15,saturation:119,vibrance:34,sharpen:9,fadedFilm:4,creativeSaturation:114,vignetteAmount:-0.72,vignetteMidpoint:44,vignetteRoundness:16,vignetteFeather:76},
    monoContrast: {temperature:0,tint:0,exposure:0.08,contrast:46,highlights:-22,shadows:-8,whites:20,blacks:-32,saturation:0,vibrance:-100,sharpen:24,fadedFilm:2,creativeSaturation:0,vignetteAmount:-1.2,vignetteMidpoint:34,vignetteRoundness:-12,vignetteFeather:55},
    skinPop: {temperature:8,tint:4,exposure:0.22,contrast:14,highlights:-26,shadows:25,whites:9,blacks:-10,saturation:108,vibrance:24,sharpen:11,fadedFilm:1,creativeSaturation:105,vignetteAmount:-0.42,vignetteMidpoint:54,vignetteRoundness:18,vignetteFeather:82}
  };

  var graphPreviews = [
    {id:"approved-ramp",name:"TUF Speed Ramp",path:"M12 88 C17 55 31 48 49 42 C70 34 83 29 88 12",curve:"0.09, 0.72, 0.94, 0.27",controls:[0.09,0.72,0.94,0.27]},
    {id:"sharp-start",name:"Sharp Start",path:"M12 88 C14 36 28 22 88 12",curve:"0.02, 0.63, 0.21, 0.88",controls:[0.02,0.63,0.21,0.88]},
    {id:"sharp-end",name:"Sharp End",path:"M12 88 C72 80 86 65 88 12",curve:"0.79, 0.12, 0.98, 0.37",controls:[0.79,0.12,0.98,0.37]},
    {id:"ease-inout",name:"Smooth In Out",path:"M12 88 C28 88 31 62 50 50 C69 38 72 12 88 12",curve:"0.42, 0, 0.58, 1",controls:[0.42,0,0.58,1]},
    {id:"soft-start",name:"Soft Start",path:"M12 88 C42 88 68 26 88 12",curve:"0.55, 0, 0.85, 0.7",controls:[0.55,0,0.85,0.7]},
    {id:"soft-end",name:"Soft End",path:"M12 88 C30 70 48 14 88 12",curve:"0.15, 0.3, 0.45, 1",controls:[0.15,0.3,0.45,1]},
    {id:"snap",name:"Fast Snap",path:"M12 88 C13 18 72 13 88 12",curve:"0.01, 0.9, 0.18, 1",controls:[0.01,0.9,0.18,1]},
    {id:"hard-start",name:"Hard Start",path:"M12 88 C13 38 18 20 88 12",curve:"0.01, 0.66, 0.08, 0.95",controls:[0.01,0.66,0.08,0.95]},
    {id:"hard-end",name:"Hard End",path:"M12 88 C82 80 87 61 88 12",curve:"0.92, 0.05, 0.99, 0.34",controls:[0.92,0.05,0.99,0.34]},
    {id:"overshoot",name:"Overshoot",path:"M12 88 C26 58 63 4 88 12",curve:"0.18, 0.52, 0.58, 1.18",controls:[0.18,0.52,0.58,1.18]},
    {id:"back-start",name:"Back Start",path:"M12 88 C28 101 42 45 88 12",curve:"0.35, -0.18, 0.56, 0.88",controls:[0.35,-0.18,0.56,0.88]},
    {id:"impact",name:"Impact",path:"M12 88 C13 8 66 25 88 12",curve:"0.02, 1.12, 0.42, 0.88",controls:[0.02,1.12,0.42,0.88]},
    {id:"cinematic",name:"Cinematic",path:"M12 88 C34 88 57 17 88 12",curve:"0.48, 0.02, 0.62, 0.96",controls:[0.48,0.02,0.62,0.96]},
    {id:"ease-linear",name:"Linear",path:"M12 88 L88 12",curve:"0, 0, 1, 1",controls:[0,0,1,1]}
  ];

  var textPreviewClasses = {
    "text-left":"preview-text-left","text-right":"preview-text-right","text-up":"preview-text-up","text-down":"preview-text-down",
    "text-char-fade":"preview-letter-fade","text-word-fade":"preview-word-fade","text-scale-pop":"preview-scale-pop","text-rotate":"preview-rotate",
    "text-blur-reveal":"preview-blur","text-tracking-reveal":"preview-tracking","text-soft-rise":"preview-soft-rise",
    "text-drop-in":"preview-drop-in","text-pop-blur":"preview-pop-blur","text-scale-punch":"preview-scale-punch",
    "text-rotate-words":"preview-rotate-words","text-tighten":"preview-tighten","text-wipe-left":"preview-wipe-left",
    "text-wipe-right":"preview-wipe-right","text-flicker-on":"preview-flicker","text-wave-rise":"preview-wave"
  };

  var motionPreviewClasses = {
    "move-left":"preview-move-left","move-right":"preview-move-right","move-up":"preview-move-up","move-down":"preview-move-down",
    "overshoot-left":"preview-over-left","overshoot-right":"preview-over-right","bounce-up":"preview-bounce","scale-impact":"preview-scale-impact",
    "impact-shake":"preview-impact-shake","camera-snap":"preview-camera-snap","zoom-stutter":"preview-zoom-stutter",
    "motion-punch-in":"preview-punch-in","motion-punch-out":"preview-punch-out","motion-spin-in":"preview-spin-in",
    "motion-drift-left":"preview-drift-left","motion-drift-right":"preview-drift-right","motion-float-up":"preview-float-up",
    "motion-drop-impact":"preview-drop-impact","motion-rotate-snap":"preview-rotate-snap","motion-fade-rise":"preview-fade-rise",
    "motion-focus-push":"preview-focus-push"
  };

  var templates = {
    audit: "Audit the active composition. Check every BlurMoCurves speed graph, effect order, scene timing, black edges, repeated shots, and character framing. Repair only confirmed faults and preserve all manual adjustments.",
    reference: "Analyze the reference media I provide, map its cuts and effects frame accurately, and build a separate reference-matched composition using my footage. Preserve the intro area and use the approved TUF graph standards.",
    intro: "Polish only the intro: add the approved aggressive opening zoom-out with directional blur and glow, then a brief sharp-end impact transition into the edit. Do not change anything else.",
    captions: "Transcribe and synchronize dialogue and song lyrics. Keep dialogue low and safe, lyrics centered and smaller, reveal dialogue letter by letter and lyrics word by word, with shadow and no stroke.",
    build: "Build the main edit from the prepared footage in the active project. Sync one continuous camera angle per beat, center the characters, preserve the intro, and use the approved TUF effects and speed-ramp graphs.",
    repair: "Inspect the active composition and repair its flow, transitions, graphs, framing, effect stacking, black edges, and accidental gaps. Preserve every unrelated manual adjustment.",
    export: "Inspect the active edit and recommend exact Topaz Video AI and Adobe Media Encoder settings for an ultra-high-quality TikTok export while preserving its original frame rate."
  };

  function byId(id) { return document.getElementById(id); }

  function setTheme(theme, persist) {
    var themes = {classic:1,titan:1,volt:1,gears:1,prism:1,ember:1,studio:1,blueprint:1,mono:1};
    var selected = themes[theme] ? theme : "classic";
    state.theme = selected;
    document.body.setAttribute("data-theme", selected);
    document.querySelectorAll("[data-theme-option]").forEach(function (button) {
      var active = button.getAttribute("data-theme-option") === selected;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    if (persist) {
      localStorage.setItem("tonyfx.theme", selected);
      setFooter(selected.charAt(0).toUpperCase() + selected.slice(1) + " design active");
    }
  }

  function initializeIcons() {
    if (window.lucide && window.lucide.createIcons) {
      window.lucide.createIcons({ attrs: { "aria-hidden": "true" } });
    }
  }

  function rawEvalHost(script, callback) {
    window.__adobe_cep__.evalScript(script, callback || function () {});
  }

  function hostBootstrapScript() {
    if (!nodeAvailable) { return ""; }
    var pagePath = decodeURIComponent(window.location.pathname || "").replace(/^\/([A-Za-z]:)/, "$1").replace(/\//g, path.sep);
    var hostPath = path.join(path.dirname(pagePath), "jsx", "host.jsx").replace(/\\/g, "\\\\").replace(/\"/g, "\\\"");
    return '(function(){try{if(typeof TUF==="undefined"||!TUF.inspectActiveComp){var f=new File("' + hostPath + '");if(!f.exists){return "TONYFX_HOST_ERROR:Host file missing";}$.evalFile(f);}return (typeof TUF!=="undefined"&&TUF.inspectActiveComp)?"TONYFX_HOST_READY":"TONYFX_HOST_ERROR:Host API unavailable";}catch(e){return "TONYFX_HOST_ERROR:"+e.toString();}}())';
  }

  function evalHost(script, callback) {
    callback = callback || function () {};
    if (hasCEP) {
      rawEvalHost(hostBootstrapScript(), function (status) {
        if (status !== "TONYFX_HOST_READY") {
          callback(JSON.stringify({ok:false,error:String(status || "TonyFX could not connect to After Effects.")}));
          return;
        }
        rawEvalHost(script, callback);
      });
      return;
    }
    var mock = JSON.stringify({
      ok: true,
      mock: true,
      comp: { name: "Browser Preview Comp", width: 1080, height: 1080, frameRate: 30, layers: 18, selected: 2 },
      guards: ["Browser preview: After Effects is not connected."]
    });
    window.setTimeout(function () { callback(mock); }, 180);
  }

  function parseResult(raw) {
    if (!raw) { return { ok: false, error: "After Effects returned no result." }; }
    if (raw.indexOf("EvalScript error") === 0) { return { ok: false, error: raw }; }
    try { return JSON.parse(raw); }
    catch (error) { return { ok: false, error: raw }; }
  }

  function setFooter(message) { byId("footerStatus").textContent = message; }

  function setAEStatus(mode, text) {
    var element = byId("aeStatus");
    element.className = "status-chip " + mode;
    element.lastChild.nodeValue = text;
  }

  function setCodexStatus(mode, text) {
    var element = byId("codexStatus");
    element.className = "status-chip " + mode;
    element.lastChild.nodeValue = text;
  }

  function collectSessionFiles(directory, output, depth) {
    if (depth > 5 || !fs.existsSync(directory)) { return; }
    var entries;
    try { entries = fs.readdirSync(directory, { withFileTypes: true }); }
    catch (error) { return; }
    entries.forEach(function (entry) {
      var fullPath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        collectSessionFiles(fullPath, output, depth + 1);
      } else if (/\.jsonl$/i.test(entry.name)) {
        try { output.push({ file: fullPath, modified: fs.statSync(fullPath).mtimeMs }); }
        catch (error) {}
      }
    });
  }

  function readFileTail(filePath, maximumBytes) {
    var handle = fs.openSync(filePath, "r");
    try {
      var size = fs.fstatSync(handle).size;
      var length = Math.min(size, maximumBytes);
      var buffer = Buffer.alloc(length);
      fs.readSync(handle, buffer, 0, length, size - length);
      var text = buffer.toString("utf8");
      if (size > length) {
        var firstBreak = text.indexOf("\n");
        text = firstBreak >= 0 ? text.slice(firstBreak + 1) : "";
      }
      return text;
    } finally {
      fs.closeSync(handle);
    }
  }

  function findLatestRateLimits() {
    if (!nodeAvailable) { return null; }
    var files = [];
    collectSessionFiles(path.join(os.homedir(), ".codex", "sessions"), files, 0);
    files.sort(function (a, b) { return b.modified - a.modified; });
    for (var fileIndex = 0; fileIndex < Math.min(files.length, 40); fileIndex += 1) {
      var lines;
      try { lines = readFileTail(files[fileIndex].file, 1024 * 1024).split(/\r?\n/); }
      catch (error) { continue; }
      for (var lineIndex = lines.length - 1; lineIndex >= 0; lineIndex -= 1) {
        if (lines[lineIndex].indexOf('"type":"token_count"') < 0) { continue; }
        try {
          var event = JSON.parse(lines[lineIndex]);
          var limits = event && event.payload && event.payload.info && event.payload.info.rate_limits;
          if (limits && (limits.primary || limits.secondary)) {
            return { limits: limits, timestamp: event.timestamp || "", modified: files[fileIndex].modified };
          }
        } catch (error) {}
      }
    }
    return null;
  }

  function formatUsageWindow(minutes) {
    if (!minutes) { return "window"; }
    if (minutes >= 1440 && minutes % 1440 === 0) { return (minutes / 1440) + "d"; }
    if (minutes >= 60 && minutes % 60 === 0) { return (minutes / 60) + "h"; }
    return minutes + "m";
  }

  function remainingForLimit(limit) {
    if (!limit) { return null; }
    if (limit.resets_at && limit.resets_at * 1000 <= Date.now()) { return 100; }
    var used = Number(limit.used_percent);
    return isFinite(used) ? Math.max(0, Math.min(100, 100 - used)) : null;
  }

  function renderUsage(data) {
    var meter = byId("usageMode");
    var percentage = byId("usagePercent");
    var fill = byId("usageFill");
    meter.classList.remove("loading", "warning", "critical");
    if (!data) {
      percentage.textContent = "--%";
      fill.style.width = "0%";
      meter.title = "Codex has not reported plan usage yet. Complete a Codex task, then click to refresh.";
      return;
    }
    var candidates = [data.limits.primary, data.limits.secondary].filter(Boolean);
    var values = candidates.map(remainingForLimit).filter(function (value) { return value !== null; });
    if (!values.length) { renderUsage(null); return; }
    var remaining = Math.round(Math.min.apply(Math, values));
    percentage.textContent = remaining + "%";
    fill.style.width = remaining + "%";
    if (remaining <= 15) { meter.classList.add("critical"); }
    else if (remaining <= 35) { meter.classList.add("warning"); }
    var details = candidates.map(function (limit) {
      var value = Math.round(remainingForLimit(limit));
      var reset = limit.resets_at ? new Date(limit.resets_at * 1000).toLocaleString() : "unknown reset";
      return formatUsageWindow(limit.window_minutes) + ": " + value + "% left, resets " + reset;
    });
    var plan = data.limits.plan_type ? String(data.limits.plan_type).toUpperCase() : "CODEX PLAN";
    meter.title = plan + "\n" + details.join("\n") + "\nClick to refresh";
  }

  function refreshUsage(showFooter) {
    var meter = byId("usageMode");
    if (!meter) { return; }
    meter.classList.add("loading");
    window.setTimeout(function () {
      var data = null;
      try { data = findLatestRateLimits(); } catch (error) {}
      renderUsage(data);
      if (showFooter) { setFooter(data ? "Codex plan usage refreshed" : "No Codex usage report found yet"); }
    }, 20);
  }

  function atomicWriteJSON(filePath, data) {
    var temporary = filePath + ".tuf.tmp";
    fs.writeFileSync(temporary, JSON.stringify(data, null, 2), "utf8");
    try { fs.renameSync(temporary, filePath); }
    catch (error) {
      try { if (fs.existsSync(filePath)) { fs.unlinkSync(filePath); } } catch (ignore) {}
      fs.renameSync(temporary, filePath);
    }
  }

  function readJSONFile(filePath) {
    var source = fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, "");
    return JSON.parse(source);
  }

  function bridgeCommandId(commandData, commandPath) {
    var supplied = commandData && (commandData.id || commandData.commandId || commandData.requestId);
    if (supplied) { return String(supplied); }
    var stats = fs.statSync(commandPath);
    var scriptPath = commandData && commandData.args && commandData.args.scriptPath ? String(commandData.args.scriptPath) : "";
    return ["legacy", Math.round(stats.mtimeMs), stats.size, commandData.command || "unknown", scriptPath].join(":");
  }

  function clearBridgeRuntime() {
    if (bridgeTimeoutTimer) { window.clearTimeout(bridgeTimeoutTimer); bridgeTimeoutTimer = null; }
    if (bridgeHeartbeatTimer) { window.clearInterval(bridgeHeartbeatTimer); bridgeHeartbeatTimer = null; }
    if (bridgeLockPath) {
      try { if (fs.existsSync(bridgeLockPath)) { fs.unlinkSync(bridgeLockPath); } } catch (error) {}
    }
    bridgeLockPath = "";
    bridgeActiveCommandId = "";
    bridgeBusy = false;
  }

  function acquireBridgeLock(commandPath, commandId) {
    var lockPath = commandPath + ".tonyfx.lock";
    try {
      var descriptor = fs.openSync(lockPath, "wx");
      try {
        fs.writeFileSync(descriptor, JSON.stringify({ owner: bridgeOwnerId, commandId: commandId, heartbeat: new Date().toISOString() }), "utf8");
      } finally { fs.closeSync(descriptor); }
    } catch (error) {
      if (!error || error.code !== "EEXIST") { throw error; }
      return false;
    }
    bridgeLockPath = lockPath;
    bridgeHeartbeatTimer = window.setInterval(function () {
      if (!bridgeBusy || !bridgeLockPath) { return; }
      try { atomicWriteJSON(bridgeLockPath, { owner: bridgeOwnerId, commandId: bridgeActiveCommandId, heartbeat: new Date().toISOString() }); }
      catch (error) {}
    }, 2000);
    return true;
  }

  function commandRecordMatches(commandPath, commandId) {
    try {
      var current = readJSONFile(commandPath);
      return bridgeCommandId(current, commandPath) === commandId;
    } catch (error) { return false; }
  }

  function updateCommandRecord(commandPath, commandId, values) {
    if (!commandRecordMatches(commandPath, commandId)) { return false; }
    var current = readJSONFile(commandPath);
    Object.keys(values).forEach(function (key) { current[key] = values[key]; });
    atomicWriteJSON(commandPath, current);
    return true;
  }

  function writeBridgeResult(resultPath, commandData, commandId, result) {
    result = result && typeof result === "object" ? result : { ok: true, result: result };
    result._responseTimestamp = new Date().toISOString();
    result._commandExecuted = commandData.command;
    result._commandId = commandId;
    result._servicedBy = "TonyFX";
    atomicWriteJSON(resultPath, result);
    return result;
  }

  function finishBridgeCommand(commandPath, resultPath, commandData, result) {
    var commandId = bridgeCommandId(commandData, commandPath);
    if (!bridgeBusy || bridgeActiveCommandId !== commandId) { return; }
    result = writeBridgeResult(resultPath, commandData, commandId, result);
    updateCommandRecord(commandPath, commandId, {
      id: commandId,
      status: result.ok === false || result.error ? "error" : "completed",
      completedAt: new Date().toISOString(),
      servicedBy: "TonyFX",
      owner: bridgeOwnerId
    });
    bridgeLastProcessedId = commandId;
    localStorage.setItem("tonyfx.bridge.lastProcessedId", commandId);
    clearBridgeRuntime();
    setAEStatus("ready", "AE + bridge ready");
  }

  function recoverInterruptedBridgeCommand() {
    if (!hasCEP || !nodeAvailable || bridgeBusy) { return; }
    var commandPath = path.join(state.settings.bridge, "ae_command.json");
    var resultPath = path.join(state.settings.bridge, "ae_mcp_result.json");
    var lockPath = commandPath + ".tonyfx.lock";
    if (!fs.existsSync(commandPath)) { return; }
    var commandData;
    try { commandData = readJSONFile(commandPath); } catch (error) { return; }
    if (commandData.status !== "running" || String(commandData.servicedBy || "").toLowerCase().indexOf("tonyfx") < 0) { return; }
    var lockAge = Infinity;
    try { lockAge = Date.now() - fs.statSync(lockPath).mtimeMs; } catch (error) {}
    if (lockAge < 6500) { return; }
    var commandId = bridgeCommandId(commandData, commandPath);
    var result = { ok: false, error: "TonyFX recovered an interrupted AE command after the panel restarted. The command was not rerun. Queue it again with a new command ID if it is still needed." };
    writeBridgeResult(resultPath, commandData, commandId, result);
    updateCommandRecord(commandPath, commandId, { id: commandId, status: "error", completedAt: new Date().toISOString(), servicedBy: "TonyFX", interrupted: true });
    try { if (fs.existsSync(lockPath)) { fs.unlinkSync(lockPath); } } catch (error) {}
    setFooter("Interrupted command stopped safely; nothing was rerun");
  }

  function serviceBridgeCommand() {
    if (!hasCEP || !nodeAvailable || bridgeBusy) { return; }
    var commandPath = path.join(state.settings.bridge, "ae_command.json");
    var resultPath = path.join(state.settings.bridge, "ae_mcp_result.json");
    if (!fs.existsSync(commandPath)) { return; }
    var commandData;
    try { commandData = readJSONFile(commandPath); } catch (error) { return; }
    if (commandData.status !== "pending") { return; }
    var commandId;
    try { commandId = bridgeCommandId(commandData, commandPath); } catch (error) { return; }
    if (commandId === bridgeLastProcessedId) {
      var duplicate = { ok: false, error: "TonyFX refused to rerun an already completed command ID. Queue the request with a new ID.", duplicate: true };
      writeBridgeResult(resultPath, commandData, commandId, duplicate);
      updateCommandRecord(commandPath, commandId, { id: commandId, status: "error", completedAt: new Date().toISOString(), servicedBy: "TonyFX", duplicate: true });
      setFooter("Duplicate AE command blocked safely");
      return;
    }
    try { if (!acquireBridgeLock(commandPath, commandId)) { return; } }
    catch (error) { setFooter("TonyFX could not claim the AE command: " + error.message); return; }
    try { commandData = readJSONFile(commandPath); }
    catch (error) { clearBridgeRuntime(); return; }
    if (commandData.status !== "pending" || bridgeCommandId(commandData, commandPath) !== commandId) { clearBridgeRuntime(); return; }
    bridgeBusy = true;
    bridgeActiveCommandId = commandId;
    try { if (fs.existsSync(resultPath)) { fs.unlinkSync(resultPath); } } catch (error) {}
    commandData.id = commandId;
    commandData.status = "running";
    commandData.startedAt = new Date().toISOString();
    commandData.servicedBy = "TonyFX";
    commandData.owner = bridgeOwnerId;
    try { atomicWriteJSON(commandPath, commandData); }
    catch (error) { clearBridgeRuntime(); return; }
    bridgeTimeoutTimer = window.setTimeout(function () {
      if (!bridgeBusy || bridgeActiveCommandId !== commandId) { return; }
      finishBridgeCommand(commandPath, resultPath, commandData, { ok: false, error: "TonyFX stopped waiting after " + Math.round(bridgeTimeoutMs / 60000) + " minutes. Completion is unconfirmed; it did not retry or rerun the command." });
      setFooter("AE command timed out safely without retrying");
    }, bridgeTimeoutMs);
    setAEStatus("", "AE running " + commandId.slice(0, 18));
    setFooter("TonyFX claimed one AE command: " + commandId);

    if (commandData.command === "uiCapabilities") {
      evalHost("TUF.nativeUICapabilities()", function (raw) {
        finishBridgeCommand(commandPath, resultPath, commandData, parseResult(raw));
      });
      return;
    }
    if (/^ui(Snapshot|Activate|Click|DoubleClick|Stroke|Scroll|Key|Text)$/.test(commandData.command)) {
      evalHost("TUF.nativeUIContext()", function (raw) {
        var observed = parseResult(raw);
        if (!observed.ok) { finishBridgeCommand(commandPath, resultPath, commandData, observed); return; }
        try {
          var extension = decodeURIComponent(window.__adobe_cep__.getSystemPath("extension").replace(/^file:\/\//, "")).replace(/^\/([A-Za-z]:)/, "$1");
          var nativeUI = require(path.join(extension, "js", "native-ui.js"));
          nativeUI.run({ bridge: state.settings.bridge, python: state.settings.python, extension: extension, command: commandData, context: observed.context }, function (result) {
            finishBridgeCommand(commandPath, resultPath, commandData, result);
            setFooter(result.ok ? "Native AE interaction completed; inspect the new screenshot" : "Native AE interaction stopped: " + result.error);
          });
        } catch (error) { finishBridgeCommand(commandPath, resultPath, commandData, { ok: false, error: error.message, inputStarted: false, noAutomaticRetry: true }); }
      });
      return;
    }
    if (commandData.command === "runScriptFile") {
      var scriptPath = commandData.args && commandData.args.scriptPath ? String(commandData.args.scriptPath) : "";
      var escaped = scriptPath.replace(/\\/g, "\\\\").replace(/\"/g, "\\\"");
      var jsx = "(function(){try{var f=new File(\"" + escaped + "\");if(!f.exists)throw new Error(\"Script file not found: \"+f.fsName);$.evalFile(f);return '{\"ok\":true}';}catch(e){var m=String(e&&e.toString?e.toString():e).replace(/\\\\/g,'\\\\\\\\').replace(/\"/g,'\\\\\"').replace(/[\\r\\n]+/g,' ');return '{\"ok\":false,\"error\":\"'+m+'\",\"line\":'+(e&&e.line?e.line:0)+'}';}}())";
      evalHost(jsx, function (raw) {
        finishBridgeCommand(commandPath, resultPath, commandData, parseResult(raw));
        setFooter("AE script completed through Command Center");
      });
      return;
    }
    if (commandData.command === "getProjectInfo" || commandData.command === "getLayerInfo") {
      evalHost("TUF.inspectActiveComp()", function (raw) {
        finishBridgeCommand(commandPath, resultPath, commandData, parseResult(raw));
      });
      return;
    }
    finishBridgeCommand(commandPath, resultPath, commandData, {
      ok: false,
      error: "Use runScriptFile, inspection, or uiCapabilities for the native AE interaction commands."
    });
  }

  function startBridgeWatcher() {
    if (!hasCEP || !nodeAvailable || bridgeTimer) { return; }
    bridgeTimer = window.setInterval(serviceBridgeCommand, 650);
    window.setTimeout(recoverInterruptedBridgeCommand, 7500);
    setAEStatus("ready", "AE + bridge ready");
  }

  function addMessage(role, text, extraClass) {
    var article = document.createElement("article");
    article.className = "message " + role + (extraClass ? " " + extraClass : "");
    if (role !== "system") {
      var avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = role === "user" ? "YOU" : "T";
      article.appendChild(avatar);
    }
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    article.appendChild(bubble);
    byId("messages").appendChild(article);
    byId("messages").scrollTop = byId("messages").scrollHeight;
    return bubble;
  }

  function showTyping() {
    if (typingBubble) { return; }
    typingBubble = addMessage("assistant", "Working", "typing");
  }

  function hideTyping() {
    if (!typingBubble) { return; }
    var article = typingBubble.parentNode;
    if (article && article.parentNode) { article.parentNode.removeChild(article); }
    typingBubble = null;
  }

  function updateProject(result) {
    if (!result || !result.comp) { return; }
    state.lastSnapshot = result;
    byId("compName").textContent = result.comp.name || "Untitled composition";
    byId("compSize").textContent = (result.comp.width || "-") + "x" + (result.comp.height || "-");
    byId("compFps").textContent = result.comp.frameRate ? Number(result.comp.frameRate).toFixed(2).replace(/\.00$/, "") : "-";
    byId("compLayers").textContent = result.comp.layers == null ? "-" : result.comp.layers;
    byId("selectedLayers").textContent = result.comp.selected == null ? "-" : result.comp.selected;
    var list = byId("guardList");
    list.innerHTML = "";
    var guards = result.guards && result.guards.length ? result.guards : ["No structural warnings found in the quick inspection."];
    guards.forEach(function (guard) {
      var item = document.createElement("li");
      item.textContent = guard;
      if (/warning|missing|wrong|overlap|60 fps|unprotected/i.test(guard)) { item.className = "warning"; }
      list.appendChild(item);
    });
    setAEStatus("ready", result.mock ? "AE preview" : "AE connected");
  }

  function inspectComp(silent, callback) {
    setAEStatus("", "AE checking");
    evalHost("TUF.inspectActiveComp()", function (raw) {
      var result = parseResult(raw);
      if (result.ok) {
        updateProject(result);
        setFooter("Active composition inspected");
        if (!silent) { addMessage("system", result.message || "Active composition inspected safely."); }
      } else {
        var needsComp = /open the intended composition/i.test(result.error || "");
        setAEStatus(needsComp ? "" : "error", needsComp ? "AE ready - open comp" : "AE unavailable");
        setFooter(result.error || "Inspection failed");
        if (!silent) { addMessage("system", result.error || "Could not inspect After Effects."); }
      }
      if (callback) { callback(result); }
    });
  }

  function runLocalAction(action) {
    var methods = {
      inspect: "inspectActiveComp",
      protect: "toggleProtectSelected",
      tile: "applyMotionTileSelected",
      opacity: "applyApprovedOpacitySelected",
      audit: "quickAudit",
      snapshot: "saveSnapshot",
      precompSeparate: "precomposeSelectedSeparately",
      precompTogether: "precomposeSelectedTogether",
      twixtorSelected: "applyTwixtorSelected",
      adjustment: "createAdjustmentForSelection",
      null: "createNullForSelection"
    };
    if (!methods[action]) { return; }
    setFooter("Running local action...");
    evalHost("TUF." + methods[action] + "()", function (raw) {
      var result = parseResult(raw);
      if (result.comp) { updateProject(result); }
      if (result.ok) {
        addMessage("system", result.message || "Local action completed.");
        setFooter("Local action completed - no Codex usage");
      } else {
        addMessage("system", result.error || "Local action failed.");
        setFooter("Local action failed");
      }
    });
  }

  function escapeForEval(value) {
    return String(value).replace(/\\/g, "\\\\").replace(/\"/g, "\\\"").replace(/\r/g, "\\r").replace(/\n/g, "\\n");
  }

  function chooseLocalFile(title, extensions, callback) {
    if (!window.cep || !window.cep.fs || !window.cep.fs.showOpenDialog) {
      addMessage("system", "File selection is available inside the After Effects panel.");
      return;
    }
    var result = window.cep.fs.showOpenDialog(false, false, title, "", extensions || []);
    if (result && result.data && result.data.length) { callback(result.data[0]); }
  }

  function presetPayload(preset) {
    var payload = {};
    Object.keys(preset).forEach(function (key) { payload[key] = preset[key]; });
    // Text presets carry carefully tuned, preset-specific distances and
    // entrance lengths. The shared Effect/Motion controls used to overwrite
    // them with 120 px and six frames, making every Text card look like the
    // same barely visible fade. Only non-text tools read those shared fields.
    if (preset.tool === "textMotion") {
      payload.duration = Math.max(12, Number(preset.duration) || 20);
      payload.exitDuration = Math.max(12, Number(preset.exitDuration) || payload.duration);
      payload.matchedExit = preset.matchedExit !== false;
      if (preset.amount !== undefined) { payload.amount = Math.max(1,Number(preset.amount)); }
    } else {
      payload.duration = Math.max(2, Number(byId("durationFrames").value) || Number(preset.duration) || 12);
      payload.amount = Math.max(1, Number(byId("motionAmount").value) || Number(preset.amount) || 120);
    }
    payload.stagger = Math.max(0, Number(byId("staggerFrames").value) || 0);
    return payload;
  }

  function rememberPreset(id) {
    state.recent = [id].concat(state.recent.filter(function (item) { return item !== id; })).slice(0, 5);
    localStorage.setItem("tuf.recent", JSON.stringify(state.recent));
    renderRecent();
  }

  function runPreset(preset) {
    if (preset.tool === "applyFfx") {
      chooseLocalFile("Choose an After Effects preset", ["ffx"], function (filePath) {
        var payload = presetPayload(preset); payload.path = filePath; executePreset(payload, preset);
      });
      return;
    }
    if (preset.tool === "importMedia") {
      chooseLocalFile("Choose media to import", [], function (filePath) {
        var payload = presetPayload(preset); payload.path = filePath; executePreset(payload, preset);
      });
      return;
    }
    executePreset(presetPayload(preset), preset);
  }

  function selectEffectPreview(preset) {
    state.selectedEffect = preset.id;
    byId("durationFrames").value = preset.duration || 6;
    byId("motionAmount").value = preset.amount || 120;
    byId("effectPreviewName").textContent = preset.name;
    byId("effectPreviewHint").textContent = preset.tool === "pairedTransition" || preset.tool === "pairedWhip" ? "One scene: hits at playhead. Two scenes: hits at their cut." : "Creates an adjustment layer at the playhead";
    byId("effectPreviewBadge").textContent = preset.tool === "pairedTransition" || preset.tool === "pairedWhip" ? "CUT TRANSITION" : "LAYER EFFECT";
    var stage = byId("effectPreviewStage");
    stage.className = "effect-preview-stage preview-effect-" + (preset.preview || "clean");
    byId("applyEffectPreview").disabled = false;
    restartEffectPreview();
    renderPresets();
  }

  function restartEffectPreview() {
    var video = byId("effectPreviewVideo");
    if (!video) { return; }
    window.clearTimeout(previewTimer);
    previewIndex = 0;
    try {
      video.pause();
      video.src = previewSources[previewIndex];
      video.currentTime = 0;
      video.onended = function () {
        previewIndex = (previewIndex + 1) % previewSources.length;
        video.src = previewSources[previewIndex];
        video.load();
        var nextPlay = video.play();
        if (nextPlay && nextPlay.catch) { nextPlay.catch(function () {}); }
      };
      var play = video.play(); if (play && play.catch) { play.catch(function () {}); }
    } catch (ignore) {}
    var stage = byId("effectPreviewStage");
    var className = stage.className; stage.className = "effect-preview-stage"; void stage.offsetWidth; stage.className = className;
  }

  function executePreset(payload, preset) {
    setFooter("Applying " + preset.name + " locally...");
    var json = escapeForEval(JSON.stringify(payload));
    evalHost("TUF.runTool(\"" + json + "\")", function (raw) {
      var result = parseResult(raw);
      if (result.comp) { updateProject(result); }
      if (result.ok) {
        rememberPreset(preset.id);
        setFooter((result.message || preset.name + " applied") + " - no Codex usage");
      } else {
        addMessage("system", result.error || (preset.name + " failed."));
        setFooter(result.error || "Local preset failed");
      }
    });
  }

  function toggleFavorite(id) {
    var index = state.favorites.indexOf(id);
    if (index >= 0) { state.favorites.splice(index, 1); }
    else { state.favorites.push(id); }
    localStorage.setItem("tuf.favorites", JSON.stringify(state.favorites));
    renderPresets();
  }

  function renderRecent() {
    var names = state.recent.map(function (id) {
      var preset = (window.TUF_PRESETS || []).filter(function (item) { return item.id === id; })[0];
      return preset ? preset.name : "";
    }).filter(Boolean);
    byId("recentTools").textContent = names.length ? "Recent: " + names.slice(0, 2).join(" / ") : "";
  }

  function renderCategories() {
    var categories = ["All", "Text", "Motion", "Easing", "Effects", "Utility", "Assets"];
    var holder = byId("categoryChips"); holder.innerHTML = "";
    categories.forEach(function (category) {
      var button = document.createElement("button");
      button.textContent = category;
      button.className = state.presetCategory === category ? "active" : "";
      button.addEventListener("click", function () { state.presetCategory = category; renderCategories(); renderPresets(); });
      holder.appendChild(button);
    });
    byId("effectPreviewPanel").classList.toggle("hidden", state.presetCategory !== "Effects");
  }

  function renderPresets() {
    var query = byId("presetSearch").value.trim().toLowerCase();
    var presets = (window.TUF_PRESETS || []).filter(function (preset) {
      var categoryMatch = state.presetCategory === "All" || preset.category === state.presetCategory;
      var favoriteMatch = !state.favoritesOnly || state.favorites.indexOf(preset.id) >= 0;
      var text = (preset.name + " " + preset.category + " " + (preset.tags || "")).toLowerCase();
      return categoryMatch && favoriteMatch && (!query || text.indexOf(query) >= 0);
    });
    byId("presetCount").textContent = presets.length + (presets.length === 1 ? " tool" : " tools");
    var grid = byId("presetGrid"); grid.innerHTML = "";
    if (!presets.length) { var empty = document.createElement("div"); empty.className = "empty-library"; empty.textContent = "No matching tools"; grid.appendChild(empty); return; }
    presets.forEach(function (preset) {
      var card = document.createElement("div"); card.className = "preset-card" + (preset.category === "Effects" && state.selectedEffect === preset.id ? " selected" : ""); card.setAttribute("role", "button"); card.tabIndex = 0;
      card.innerHTML = '<span class="preset-icon" data-lucide="' + preset.icon + '"></span><strong>' + preset.name + '</strong><small>' + preset.category + '</small>';
      card.addEventListener("click", function () { if (preset.category === "Effects") { selectEffectPreview(preset); } else { runPreset(preset); } });
      card.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); if (preset.category === "Effects") { selectEffectPreview(preset); } else { runPreset(preset); } } });
      var favorite = document.createElement("button"); favorite.type = "button"; favorite.className = "favorite-button" + (state.favorites.indexOf(preset.id) >= 0 ? " active" : ""); favorite.title = "Favorite"; favorite.innerHTML = '<span data-lucide="star"></span>';
      favorite.addEventListener("click", function (event) { event.stopPropagation(); toggleFavorite(preset.id); });
      card.appendChild(favorite); grid.appendChild(card);
    });
    initializeIcons();
  }

  function resolveCodexPath() {
    if (!nodeAvailable) { return ""; }
    var configPath = path.join(os.homedir(), ".codex", "config.toml");
    try {
      var config = fs.readFileSync(configPath, "utf8");
      var match = config.match(/CODEX_CLI_PATH\s*=\s*['\"]([^'\"]+)['\"]/);
      if (match && fs.existsSync(match[1])) { return match[1]; }
    } catch (error) {}
    var fallbacks = [
      path.join(os.homedir(), ".codex", "plugins", ".plugin-appserver", "codex.exe"),
      path.join(os.homedir(), ".codex", ".sandbox-bin", "codex.exe")
    ];
    for (var i = 0; i < fallbacks.length; i++) {
      if (fs.existsSync(fallbacks[i])) { return fallbacks[i]; }
    }
    return "";
  }

  function compactSnapshot(snapshot) {
    if (!snapshot || !snapshot.comp) { return "No AE snapshot was available."; }
    return JSON.stringify({ comp: snapshot.comp, guards: snapshot.guards || [] });
  }

  function buildPrompt(userText) {
    return [
      "You are running from the private TUF AE Command Center panel.",
      "Use the installed tuf-ae-editing plugin and its exact editing standards.",
      "Work through the AE command-file workflow at " + state.settings.bridge + ". The Command Center panel owns the bridge, so do not ask the user to open MCP Bridge Auto.",
      "For AE changes, create one guarded JSX file and queue it as a runScriptFile command. Wait for the fresh result before continuing.",
      "Never launch, close, restart, or open another After Effects instance.",
      "Inspect the active project before editing. Preserve protected intro layers and every unrelated manual adjustment.",
      "Use one continuous camera angle per beat layer. Verify graphs and changed frames before saving.",
      "Current compact AE snapshot: " + compactSnapshot(state.lastSnapshot),
      "User command: " + userText
    ].join("\n\n");
  }

  function extractEventText(event) {
    if (!event) { return ""; }
    if (event.type === "thread.started" && event.thread_id) {
      state.sessionId = event.thread_id;
      localStorage.setItem("tuf.codexSession", state.sessionId);
      byId("sessionId").textContent = state.sessionId;
      return "";
    }
    var item = event.item || event.message || null;
    if (item && item.type === "agent_message") { return item.text || item.content || ""; }
    if (event.type === "message" && event.role === "assistant") { return event.content || ""; }
    if (event.type === "error") { return "Error: " + (event.message || event.error || "Unknown Codex error"); }
    return "";
  }

  function beginCodexTask(userText) {
    if (runningProcess) { return; }
    if (!nodeAvailable) {
      addMessage("system", "Node.js is unavailable in this panel. Confirm CEP debug loading and restart After Effects.");
      return;
    }
    var codexPath = resolveCodexPath();
    if (!codexPath) {
      addMessage("system", "Could not locate the installed Codex CLI. Open panel settings after updating Codex.");
      return;
    }
    var prompt = buildPrompt(userText);
    var args;
    if (state.sessionId) {
      args = [
        "-s", "danger-full-access", "-a", "never",
        "exec", "resume", "--json", "--skip-git-repo-check", state.sessionId, "-"
      ];
    } else {
      args = [
        "-C", state.settings.workspace,
        "--add-dir", state.settings.bridge,
        "-s", "danger-full-access", "-a", "never",
        "exec", "--json", "--skip-git-repo-check", "-"
      ];
    }
    addMessage("user", userText);
    showTyping();
    setCodexStatus("", "Codex working");
    setFooter("Codex task running on plan usage");
    byId("sendButton").disabled = true;
    byId("stopButton").classList.remove("hidden");

    var outputBuffer = "";
    var finalMessages = [];
    runningProcess = childProcess.spawn(codexPath, args, {
      cwd: state.settings.workspace,
      windowsHide: true,
      env: process.env
    });
    runningProcess.stdin.write(prompt);
    runningProcess.stdin.end();
    runningProcess.stdout.setEncoding("utf8");
    runningProcess.stderr.setEncoding("utf8");
    runningProcess.stdout.on("data", function (chunk) {
      outputBuffer += chunk;
      var lines = outputBuffer.split(/\r?\n/);
      outputBuffer = lines.pop();
      lines.forEach(function (line) {
        if (!line.trim()) { return; }
        try {
          var text = extractEventText(JSON.parse(line));
          if (text) { finalMessages.push(typeof text === "string" ? text : JSON.stringify(text)); }
        } catch (error) {}
      });
    });
    var stderr = "";
    runningProcess.stderr.on("data", function (chunk) { stderr += chunk; });
    runningProcess.on("error", function (error) {
      finishCodexTask(1, ["Could not start Codex: " + error.message]);
    });
    runningProcess.on("close", function (code) {
      if (outputBuffer.trim()) {
        try {
          var lastText = extractEventText(JSON.parse(outputBuffer));
          if (lastText) { finalMessages.push(lastText); }
        } catch (error) {}
      }
      if (code !== 0 && stderr.trim()) { finalMessages.push(stderr.trim()); }
      finishCodexTask(code, finalMessages);
    });
  }

  function finishCodexTask(code, messages) {
    hideTyping();
    var text = messages && messages.length ? messages[messages.length - 1] : (code === 0 ? "Codex finished the task." : "Codex stopped before completing the task.");
    addMessage("assistant", String(text));
    runningProcess = null;
    byId("sendButton").disabled = false;
    byId("stopButton").classList.add("hidden");
    setCodexStatus(code === 0 ? "ready" : "error", code === 0 ? "Codex ready" : "Codex error");
    setFooter(code === 0 ? "Codex task completed" : "Codex task ended with an error");
    inspectComp(true);
    window.setTimeout(function () { refreshUsage(false); }, 800);
  }

  function sendPrompt() {
    var input = byId("promptInput");
    var text = input.value.trim();
    if (!text || runningProcess) { return; }
    input.value = "";
    if (state.inspectBeforeSend) {
      inspectComp(true, function () { beginCodexTask(text); });
    } else {
      beginCodexTask(text);
    }
  }

  function colorControlValue(name) {
    var control = document.querySelector('[data-color-control="' + name + '"]');
    if (!control) { return 0; }
    return Number(control.querySelector('input[type="number"]').value) || 0;
  }

  function hexToRgb(hex) {
    var value = String(hex || "#808080").replace("#", "");
    return [parseInt(value.slice(0, 2), 16) || 128, parseInt(value.slice(2, 4), 16) || 128, parseInt(value.slice(4, 6), 16) || 128];
  }

  function collectColorPayload() {
    var payload = {};
    document.querySelectorAll("[data-color-control]").forEach(function (control) {
      payload[control.getAttribute("data-color-control")] = Number(control.querySelector('input[type="number"]').value) || 0;
    });
    payload.wheels = {};
    document.querySelectorAll("[data-wheel]").forEach(function (wheel) {
      payload.wheels[wheel.getAttribute("data-wheel")] = {
        color: hexToRgb(wheel.querySelector('input[type="color"]').value),
        luma: Number(wheel.querySelector('input[type="number"]').value) || 0
      };
    });
    return payload;
  }

  function setColorControl(name, value) {
    var control = document.querySelector('[data-color-control="' + name + '"]');
    if (!control || value === undefined || value === null) { return; }
    var range = control.querySelector('input[type="range"]');
    var number = control.querySelector('input[type="number"]');
    range.value = value; number.value = value; updateRangeFill(range);
  }

  function updateRangeFill(range) {
    if (!range) { return; }
    var minimum = Number(range.min) || 0, maximum = Number(range.max) || 100, value = Number(range.value) || 0;
    range.style.setProperty("--fill", Math.max(0, Math.min(100, (value - minimum) / (maximum - minimum) * 100)) + "%");
  }

  function applyColor(silent) {
    var json = escapeForEval(JSON.stringify(collectColorPayload()));
    if (!silent) { setFooter("Applying Lumetri grade..."); }
    evalHost('TUF.applyLumetri("' + json + '")', function (raw) {
      var result = parseResult(raw);
      byId("colorTarget").textContent = result.ok ? (result.message || "Lumetri grade applied") : (result.error || "Lumetri failed");
      byId("colorTarget").parentNode.classList.toggle("error", !result.ok);
      if (!silent) { setFooter(result.ok ? "Lumetri applied locally - no Codex usage" : "Lumetri action failed"); }
    });
  }

  function queueLiveColor() {
    if (!state.colorLive) { return; }
    window.clearTimeout(colorTimer);
    colorTimer = window.setTimeout(function () { applyColor(true); }, 160);
  }

  function resetColor() {
    applyGradePreset("neutral", false);
    evalHost("TUF.resetLumetriSelected()", function (raw) {
      var result = parseResult(raw);
      byId("colorTarget").textContent = result.ok ? result.message : result.error;
      setFooter(result.ok ? "Lumetri reset locally" : "Lumetri reset failed");
    });
  }

  function readColor() {
    setFooter("Reading selected Lumetri grade...");
    evalHost("TUF.readLumetriSelected()", function (raw) {
      var result = parseResult(raw);
      if (!result.ok) { byId("colorTarget").textContent = result.error; setFooter("Could not read Lumetri"); return; }
      Object.keys(result.values || {}).forEach(function (name) { setColorControl(name, result.values[name]); });
      byId("colorTarget").textContent = result.message || "Selected grade loaded";
      setFooter("Selected Lumetri grade loaded");
    });
  }

  function applyGradePreset(name, shouldApply) {
    var preset = gradePresets[name];
    if (!preset) { return; }
    Object.keys(preset).forEach(function (key) { setColorControl(key, preset[key]); });
    document.querySelectorAll("[data-grade]").forEach(function (button) { button.classList.toggle("active", button.getAttribute("data-grade") === name); });
    if (shouldApply !== false) { applyColor(false); }
  }

  function wireColorStudio() {
    byId("liveColor").checked = state.colorLive;
    document.querySelectorAll("[data-color-control]").forEach(function (control) {
      var range = control.querySelector('input[type="range"]'), number = control.querySelector('input[type="number"]');
      updateRangeFill(range);
      range.addEventListener("input", function () { number.value = range.value; updateRangeFill(range); queueLiveColor(); });
      number.addEventListener("input", function () { range.value = number.value; updateRangeFill(range); queueLiveColor(); });
    });
    document.querySelectorAll("[data-wheel]").forEach(function (wheel) {
      var color = wheel.querySelector('input[type="color"]'), range = wheel.querySelector('input[type="range"]'), number = wheel.querySelector('input[type="number"]');
      updateRangeFill(range);
      color.addEventListener("input", function () { wheel.style.setProperty("--wheel-color", color.value); queueLiveColor(); });
      range.addEventListener("input", function () { number.value = range.value; updateRangeFill(range); queueLiveColor(); });
      number.addEventListener("input", function () { range.value = number.value; updateRangeFill(range); queueLiveColor(); });
    });
    document.querySelectorAll("[data-color-band] .color-band-title").forEach(function (button) {
      button.addEventListener("click", function () { button.parentNode.classList.toggle("open"); });
    });
    document.querySelectorAll("[data-grade]").forEach(function (button) { button.addEventListener("click", function () { applyGradePreset(button.getAttribute("data-grade"), true); }); });
    byId("applyColor").addEventListener("click", function () { applyColor(false); });
    byId("readColor").addEventListener("click", readColor);
    byId("resetColor").addEventListener("click", resetColor);
    byId("liveColor").addEventListener("change", function () { state.colorLive = this.checked; localStorage.setItem("tonyfx.colorLive", state.colorLive ? "true" : "false"); setFooter(state.colorLive ? "Live Color enabled" : "Live Color disabled"); });
  }

  function presetById(id) {
    var presets = window.TUF_PRESETS || [];
    for (var i = 0; i < presets.length; i++) { if (presets[i].id === id) { return presets[i]; } }
    return null;
  }

  function restartClassPreview(target, className) {
    target.className = "";
    void target.offsetWidth;
    target.className = className || "";
  }

  function restartTextPreview() {
    var target = byId("textPreviewTarget"), input = byId("textPreviewInput").value || "TONYFX MOTION";
    var characterMode = state.selectedText === "text-char-fade" || state.selectedText === "text-rotate" || state.selectedText === "text-tracking-reveal";
    var units = characterMode ? input.split("") : input.split(/\s+/);
    target.innerHTML = "";
    target.className = "";
    units.forEach(function (unit, index) {
      var span = document.createElement("span");
      span.textContent = unit + (!characterMode && index < units.length - 1 ? "\u00a0" : "");
      span.style.animationDelay = (index * (characterMode ? 0.035 : 0.085)) + "s";
      target.appendChild(span);
    });
    void target.offsetWidth;
    target.className = textPreviewClasses[state.selectedText] || "preview-word-fade";
  }

  function restartMotionPreview() {
    restartClassPreview(byId("motionPreviewTarget"), motionPreviewClasses[state.selectedMotion] || "preview-scale-impact");
  }

  function renderGraphPresets() {
    var grid = byId("graphPresetGrid"); grid.innerHTML = "";
    graphPreviews.concat(state.customGraphs).forEach(function (graph) {
      var button = document.createElement("button");
      button.className = "graph-preset" + (state.selectedGraph === graph.id ? " active" : "");
      button.setAttribute("data-graph-id", graph.id);
      button.innerHTML = '<svg viewBox="0 0 100 100" aria-hidden="true"><path class="graph-grid" d="M12 12V88H88 M12 69H88 M12 50H88 M12 31H88 M31 12V88 M50 12V88 M69 12V88"/><path class="graph-line" d="' + graph.path + '"/><circle cx="12" cy="88" r="2.6"/><circle cx="88" cy="12" r="2.6"/></svg><strong>' + graph.name + '</strong><small>' + graph.curve + '</small>';
      button.addEventListener("click", function () {
        state.selectedGraph = graph.id;
        byId("selectedGraphName").textContent = graph.name + " selected";
        setCustomGraph(graph.controls || [0.25,0.25,0.75,0.75], graph.custom ? graph.name : "");
        renderGraphPresets();
      });
      grid.appendChild(button);
    });
  }

  function clampGraph(value,min,max) { return Math.max(min,Math.min(max,Number(value) || 0)); }
  function graphControls() { return [clampGraph(byId("graphX1").value,0,1),clampGraph(byId("graphY1").value,-2,3),clampGraph(byId("graphX2").value,0,1),clampGraph(byId("graphY2").value,-2,3)]; }
  function graphPoint(x,y) { return {x:10+x*80,y:90-y*80}; }
  function updateCustomGraph() {
    var c=graphControls(),p1=graphPoint(c[0],c[1]),p2=graphPoint(c[2],c[3]);
    byId("customGraphPoint1").setAttribute("cx",p1.x); byId("customGraphPoint1").setAttribute("cy",p1.y);
    byId("customGraphPoint2").setAttribute("cx",p2.x); byId("customGraphPoint2").setAttribute("cy",p2.y);
    byId("customGraphHandles").setAttribute("d","M10 90 L"+p1.x+" "+p1.y+" M90 10 L"+p2.x+" "+p2.y);
    byId("customGraphPath").setAttribute("d","M10 90 C"+p1.x+" "+p1.y+" "+p2.x+" "+p2.y+" 90 10");
  }
  function setCustomGraph(controls,name) { ["graphX1","graphY1","graphX2","graphY2"].forEach(function(id,index){byId(id).value=Number(controls[index]).toFixed(2);}); byId("customGraphName").value=name||""; updateCustomGraph(); }
  function saveCustomGraph() {
    var name=byId("customGraphName").value.trim() || "Custom Graph",id="custom-"+name.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
    var item={id:id,name:name,curve:graphControls().map(function(v){return Number(v).toFixed(2);}).join(", "),controls:graphControls(),custom:true};
    state.customGraphs=state.customGraphs.filter(function(graph){return graph.id!==id;}); state.customGraphs.push(item); localStorage.setItem("tonyfx.customGraphs",JSON.stringify(state.customGraphs)); state.selectedGraph=id; renderGraphPresets(); setFooter("Custom graph saved locally.");
  }
  function deleteCustomGraph() { var before=state.customGraphs.length; state.customGraphs=state.customGraphs.filter(function(graph){return graph.id!==state.selectedGraph;}); if(before!==state.customGraphs.length){localStorage.setItem("tonyfx.customGraphs",JSON.stringify(state.customGraphs));state.selectedGraph="approved-ramp";renderGraphPresets();setFooter("Custom graph deleted.");} }
  function applySelectedGraph() {
    var graph=graphPreviews.concat(state.customGraphs).filter(function(item){return item.id===state.selectedGraph;})[0];
    var preset=presetById(state.selectedGraph);
    if(preset && !graph.custom){runPreset(preset);return;}
    var payload={id:graph.id,name:graph.name,tool:"ease",curve:"customBezier",bezier:graph.controls||graphControls()}; executePreset(payload,payload);
  }
  function wireCustomGraphDrag() {
    var svg=byId("customGraphSvg"),drag=0;
    function move(event){if(!drag)return;var rect=svg.getBoundingClientRect(),px=(event.clientX-rect.left)/rect.width,py=(event.clientY-rect.top)/rect.height,x=clampGraph((px-.1)/.8,0,1),y=clampGraph((.9-py)/.8,-2,3);byId(drag===1?"graphX1":"graphX2").value=x.toFixed(2);byId(drag===1?"graphY1":"graphY2").value=y.toFixed(2);updateCustomGraph();}
    byId("customGraphPoint1").addEventListener("mousedown",function(e){drag=1;e.preventDefault();});byId("customGraphPoint2").addEventListener("mousedown",function(e){drag=2;e.preventDefault();});window.addEventListener("mousemove",move);window.addEventListener("mouseup",function(){drag=0;});
  }

  function renderAnimationPresets() {
    var textGrid = byId("textMotionGrid"), motionGrid = byId("layerMotionGrid");
    textGrid.innerHTML = ""; motionGrid.innerHTML = "";
    (window.TUF_PRESETS || []).forEach(function (preset) {
      if (textPreviewClasses[preset.id]) {
        var textButton = document.createElement("button");
        textButton.className = "animation-preset" + (state.selectedText === preset.id ? " active" : "");
        textButton.innerHTML = '<span class="animation-glyph text-glyph">Aa</span><strong>' + preset.name + '</strong>';
        textButton.addEventListener("click", function () { state.selectedText = preset.id; byId("selectedTextName").textContent = preset.name + " selected"; renderAnimationPresets(); restartTextPreview(); });
        textGrid.appendChild(textButton);
      }
      if (motionPreviewClasses[preset.id]) {
        var motionButton = document.createElement("button");
        motionButton.className = "animation-preset" + (state.selectedMotion === preset.id ? " active" : "");
        motionButton.innerHTML = '<span class="animation-glyph motion-glyph"><i></i></span><strong>' + preset.name + '</strong>';
        motionButton.addEventListener("click", function () { state.selectedMotion = preset.id; byId("selectedMotionName").textContent = preset.name + " selected"; renderAnimationPresets(); restartMotionPreview(); });
        motionGrid.appendChild(motionButton);
      }
    });
  }

  function selectGraphMode(mode) {
    state.graphMode = mode;
    document.querySelectorAll("[data-graph-mode]").forEach(function (button) { button.classList.toggle("active", button.getAttribute("data-graph-mode") === mode); });
    document.querySelectorAll(".graph-mode").forEach(function (panel) { panel.classList.remove("active"); });
    byId(mode + "GraphMode").classList.add("active");
    if (mode === "text") { restartTextPreview(); }
    if (mode === "motion") { restartMotionPreview(); }
  }

  function wireGraphLab() {
    renderGraphPresets(); renderAnimationPresets(); restartTextPreview(); restartMotionPreview();
    document.querySelectorAll("[data-graph-mode]").forEach(function (button) { button.addEventListener("click", function () { selectGraphMode(button.getAttribute("data-graph-mode")); }); });
    byId("textPreviewInput").addEventListener("input", restartTextPreview);
    ["graphX1","graphY1","graphX2","graphY2"].forEach(function(id){byId(id).addEventListener("input",updateCustomGraph);});
    byId("saveCustomGraph").addEventListener("click",saveCustomGraph); byId("deleteCustomGraph").addEventListener("click",deleteCustomGraph); wireCustomGraphDrag(); setCustomGraph([0.09,0.72,0.94,0.27],"");
    byId("applyGraphPreset").addEventListener("click", applySelectedGraph);
    byId("applyTextPreset").addEventListener("click", function () { var preset = presetById(state.selectedText); if (preset) { runPreset(preset); } });
    byId("applyMotionPreset").addEventListener("click", function () { var preset = presetById(state.selectedMotion); if (preset) { runPreset(preset); } });
  }

  function selectTab(name) {
    document.querySelectorAll(".tab").forEach(function (tab) { tab.classList.toggle("active", tab.getAttribute("data-tab") === name); });
    document.querySelectorAll(".tab-panel").forEach(function (panel) { panel.classList.remove("active"); });
    var panel = byId(name + "Tab");
    if (panel) { panel.classList.add("active"); }
  }

  function chooseTemplate(name) {
    if (!templates[name]) { return; }
    selectTab("chat");
    byId("promptInput").value = templates[name];
    byId("promptInput").focus();
  }

  function wireEvents() {
    document.querySelectorAll("[data-theme-option]").forEach(function (button) {
      button.addEventListener("click", function () { setTheme(button.getAttribute("data-theme-option"), true); });
    });
    document.querySelectorAll(".tab").forEach(function (button) {
      button.addEventListener("click", function () { selectTab(button.getAttribute("data-tab")); });
    });
    document.querySelectorAll("[data-template]").forEach(function (button) {
      button.addEventListener("click", function () { chooseTemplate(button.getAttribute("data-template")); });
    });
    document.querySelectorAll("[data-action]").forEach(function (button) {
      button.addEventListener("click", function () { runLocalAction(button.getAttribute("data-action")); });
    });
    byId("sendButton").addEventListener("click", sendPrompt);
    byId("usageMode").addEventListener("click", function () { refreshUsage(true); });
    byId("presetSearch").addEventListener("input", renderPresets);
    byId("replayEffectPreview").addEventListener("click", restartEffectPreview);
    byId("applyEffectPreview").addEventListener("click", function () { var preset = presetById(state.selectedEffect); if (preset) { runPreset(preset); } });
    byId("favoritesOnly").addEventListener("click", function () {
      state.favoritesOnly = !state.favoritesOnly;
      this.classList.toggle("active", state.favoritesOnly);
      renderPresets();
    });
    byId("promptInput").addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); sendPrompt(); }
    });
    byId("inspectBeforeSend").addEventListener("click", function () {
      state.inspectBeforeSend = !state.inspectBeforeSend;
      this.classList.toggle("active", state.inspectBeforeSend);
    });
    byId("stopButton").addEventListener("click", function () {
      if (runningProcess) { runningProcess.kill(); setFooter("Stopping Codex task..."); }
    });
    byId("refreshProject").addEventListener("click", function () { inspectComp(false); });
    byId("newSession").addEventListener("click", function () {
      state.sessionId = "";
      localStorage.removeItem("tuf.codexSession");
      byId("sessionId").textContent = "A new session will start with your next command.";
      addMessage("system", "The next command will start a fresh Codex session.");
    });
    byId("settingsButton").addEventListener("click", function () {
      byId("workspacePath").value = state.settings.workspace;
      byId("bridgePath").value = state.settings.bridge;
      if (byId("pythonPath")) { byId("pythonPath").value = state.settings.python; }
      if (byId("captionModelPath")) { byId("captionModelPath").value = state.settings.captionModel; }
      var dialog = byId("settingsDialog");
      if (dialog.showModal) { dialog.showModal(); } else { dialog.setAttribute("open", "open"); }
    });
    byId("saveSettings").addEventListener("click", function () {
      state.settings.workspace = byId("workspacePath").value.trim() || state.settings.workspace;
      state.settings.bridge = byId("bridgePath").value.trim() || state.settings.bridge;
      state.settings.python = byId("pythonPath") && byId("pythonPath").value.trim() ? byId("pythonPath").value.trim() : state.settings.python;
      state.settings.captionModel = byId("captionModelPath") && byId("captionModelPath").value.trim() ? byId("captionModelPath").value.trim() : state.settings.captionModel;
      localStorage.setItem("tuf.workspace", state.settings.workspace);
      localStorage.setItem("tuf.bridge", state.settings.bridge);
      localStorage.setItem("tonyfx.python", state.settings.python);
      localStorage.setItem("tonyfx.captionModel", state.settings.captionModel);
      setFooter("Panel settings saved");
    });
    wireColorStudio();
    wireGraphLab();
    document.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) { return; }
      button.classList.remove("button-pulse");
      window.setTimeout(function () { button.classList.add("button-pulse"); }, 0);
      window.setTimeout(function () { button.classList.remove("button-pulse"); }, 260);
    });
  }

  function boot() {
    setTheme(state.theme, false);
    initializeIcons();
    wireEvents();
    renderCategories();
    renderPresets();
    renderRecent();
    byId("sessionId").textContent = state.sessionId || "A new session will start with your first command.";
    if (hasCEP) {
      setAEStatus("", "AE checking");
      inspectComp(true);
    } else {
      setAEStatus("", "AE preview");
      inspectComp(true);
    }
    startBridgeWatcher();
    refreshUsage(false);
    usageTimer = window.setInterval(function () { refreshUsage(false); }, 60000);
    setCodexStatus(nodeAvailable ? "ready" : "error", nodeAvailable ? "Codex ready" : "Codex unavailable");
  }

  window.TonyFXCore = {
    evalHost: evalHost,
    parseResult: parseResult,
    setFooter: setFooter,
    selectTab: selectTab,
    initializeIcons: initializeIcons,
    state: state
  };

  document.addEventListener("DOMContentLoaded", boot);
}());
