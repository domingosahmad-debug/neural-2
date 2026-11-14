const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const required = [
  "CSXS/manifest.xml",
  "index.html",
  "css/panel.css",
  "js/app.js",
  "js/presets.js",
  "js/features.js",
  "jsx/host.jsx",
  "python/auto_caption.py",
  "python/local_engine.py",
  "python/color_match.py",
  "python/framepack_cli.py",
  "python/reference_analyzer.py",
  "python/reference_intelligence.py",
  "python/transition_forensics.py",
  "python/setup_local_engine.py",
  "python/demucs_runner.py",
  "js/local-engines.js",
  "assets/effect-preview-a.mp4",
  "assets/effect-preview-b.mp4",
  "tests/ae-preset-matrix-smoke-test.jsx",
  "tests/ae-motion-easy-ease-test.jsx",
  "tests/ae-motion-visual-preview.jsx",
  "tests/ae-text-visual-preview.jsx",
  "tests/ae-v054-text-motion-regression.jsx",
  "tests/ae-v056-text-offline-regression.jsx",
  "tests/ae-v058-offline-director-regression.jsx",
  "tests/test-offline-director-v2.js",
  "tests/render-analyzer-panel.js",
  "tests/render-color-match-panel.js",
  "tests/render-v056-text-offline-panel.js",
  "tests/ae-reference-analyzer-marker-test.jsx",
  "tests/ae-v031-create-caption-color-test.jsx",
  "vendor/lucide.min.js"
];

for (const relative of required) {
  const full = path.join(root, relative);
  if (!fs.existsSync(full) || fs.statSync(full).size === 0) {
    throw new Error(`Missing extension file: ${relative}`);
  }
}

new Function(fs.readFileSync(path.join(root, "js/app.js"), "utf8"));
new Function(fs.readFileSync(path.join(root, "js/presets.js"), "utf8"));
new Function(fs.readFileSync(path.join(root, "js/features.js"), "utf8"));
new Function(fs.readFileSync(path.join(root, "js/local-engines.js"), "utf8"));
new Function(fs.readFileSync(path.join(root, "jsx/host.jsx"), "utf8"));

const manifest = fs.readFileSync(path.join(root, "CSXS/manifest.xml"), "utf8");
for (const fragment of [
  'Host Name="AEFT" Version="[23.0,27.0)"',
  "--enable-nodejs",
  "TonyFX"
]) {
  if (!manifest.includes(fragment)) throw new Error(`Manifest check failed: ${fragment}`);
}

const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
for (const fragment of [
  "TonyFX",
  'data-theme-option="classic"',
  'data-theme-option="titan"',
  'data-theme-option="volt"',
  'data-theme-option="gears"',
  'data-theme-option="prism"',
  'data-theme-option="ember"',
  'data-theme-option="studio"',
  'data-theme-option="blueprint"',
  'data-theme-option="mono"',
  'data-layout-option="guided"',
  'id="homeTab"',
  'id="colorTab"',
  'id="colorMatchAnalyze"',
  'id="colorMatchApply"',
  'id="colorMatchRender"',
  'id="colorMatchScopesPreview"',
  'id="graphsTab"',
  'id="createTab"',
  'id="captionsTab"',
  'id="analyzeTab"',
  'id="enhanceTab"',
  'id="audioLabTab"',
  'id="generateTab"',
  'id="runEnhance"',
  'id="runAudio"',
  'id="runGeneration"',
  'id="videoBackend"',
  'id="runAnalyze"',
  'id="compareFinishedEdit"',
  'id="openRepairPlan"',
  'id="graphPresetGrid"',
  'id="customGraphSvg"',
  'id="saveCustomGraph"',
  'id="textPreviewInput"',
  'id="motionPreviewTarget"',
  'id="effectPreviewPanel"',
  'id="applyEffectPreview"',
  'id="textStylePreview"',
  'id="textFxGrid"',
  'id="applyTextFx"',
  'id="captionTextFx"',
  'id="captionPreview"',
  'data-action="twixtorSelected"',
  'id="iconGrid"',
  'id="generateCaptions"',
  'id="createStyledText"',
  'id="textComposeValue"',
  'id="textComposeAnimation"',
  'id="textComposeMatchedExit"',
  'id="captionMatchedExit"',
  'id="buildOfflineEdit"',
  'id="reeditOfflineEdit"',
  'id="auditOfflineEdit"',
  'id="offlineMode"',
  'id="offlinePrompt"',
  'id="offlineAutoQA"',
  'id="offlineBlurMo"',
  'id="offlineFullStack"',
  'id="offlineStrictMatch"',
  'id="browseAnalyzeSongFolder"',
  'id="browseAnalyzeSongFile"',
  'data-engine-pair="audioPresence"',
  'data-engine-pair="audioCompression"',
  "Lumetri control surface",
  "Shot Match Lab",
  'data-grade="tealOrange"',
  'data-grade="filmWarm"',
  'data-grade="bleach"',
  'data-grade="cyber"',
  'data-grade="golden"',
  'data-grade="pastel"',
  'data-grade="moodyGreen"',
  'data-grade="sunset"',
  'data-grade="monoContrast"',
  'data-grade="skinPop"'
]) {
  if (!index.includes(fragment)) throw new Error(`Interface check failed: ${fragment}`);
}

for (const id of [
  "openAnalyzeReport",
  "applyAnalyzeMarkers",
  "compareFinishedEdit",
  "openRepairPlan",
  "applySafeRepair",
  "buildOfflineEdit",
  "reeditOfflineEdit",
  "auditOfflineEdit"
]) {
  const tag = index.match(new RegExp(`<button[^>]*id=["']${id}["'][^>]*>`, "i"));
  if (!tag) throw new Error(`Analyze action button is missing: ${id}`);
  if (/\sdisabled(?:\s|>|=)/i.test(tag[0])) {
    throw new Error(`Analyze action must remain clickable for prerequisite feedback: ${id}`);
  }
}

const app = fs.readFileSync(path.join(root, "js/app.js"), "utf8");
for (const fragment of ["tonyfx.theme", "setTheme", 'data-theme-option', "renderGraphPresets", "tonyfx.customGraphs", "saveCustomGraph", "customBezier", "restartTextPreview", "restartMotionPreview", "selectEffectPreview", "restartEffectPreview", "effect-preview-a.mp4", "effect-preview-b.mp4", "TonyFXCore", "tealOrange", "filmWarm", "bleach", "cyber", "golden", "pastel", "moodyGreen", "sunset", "monoContrast", "skinPop", 'preset.tool === "textMotion"', "Number(preset.amount)"]) {
  if (!app.includes(fragment)) throw new Error(`Theme behavior check failed: ${fragment}`);
}

const styles = fs.readFileSync(path.join(root, "css/panel.css"), "utf8");
for (const fragment of ['body[data-theme="titan"]', 'body[data-theme="volt"]', 'body[data-theme="gears"]', 'body[data-theme="prism"]', 'body[data-theme="ember"]', 'body[data-theme="studio"]', 'body[data-theme="blueprint"]', 'body[data-theme="mono"]', ".gears-blueprint", ".theme-switch", ".layout-switch", ".guided-steps", ".create-layout", ".caption-workflow", ".icon-grid", ".color-wheel", ".graph-preset", ".text-preview-stage", ".motion-preview-stage", ".effect-preview-stage", ".text-fx-grid", ".text-fx-preview", ".caption-style-preview", ".local-engine-studio", ".engine-workspace", ".audio-mode-grid", ".generation-mode-switch", "tonyFlipX", "tonyDepthPush", "effectFlashSmear", 'content:"TONYFX"']) {
  if (!styles.includes(fragment)) throw new Error(`Theme style check failed: ${fragment}`);
}
for (const fragment of [
  ".analyzer-report-actions button,.analyzer-compare-source button",
  "background:#171b20",
  "color:#e3e7eb",
  "button.is-unavailable"
]) {
  if (!styles.includes(fragment)) throw new Error(`Analyze action visibility check failed: ${fragment}`);
}

const host = fs.readFileSync(path.join(root, "jsx/host.jsx"), "utf8");
for (const fragment of [
  "TUF_PROTECTED",
  "ADBE Lumetri",
  "ADBE Tile",
  "Output Width",
  "Output Height",
  "runTool",
  "applyLumetri",
  "readLumetriSelected",
  "resetLumetriSelected",
  "getColorMatchSelection",
  "applyColorMatch",
  "removeColorMatch",
  "LUMETRI - TONYFX COLOR MATCH",
  "applyTextMotion",
  "addTextMotionAccent",
  "removeTonyFxTextMotion",
  "buildTextMotionAnimator",
  "captionMotionSpec",
  "applyTextStyle",
  "applyTextEffect",
  "applyTextEffectToLayer",
  "createIcon",
  "getCaptionSourceSelection",
  "createCaptions",
  "createStyledText",
  "buildTextMotionExitAnimator",
  "addMatchedTextExit",
  "revealCaptionWords",
  "easeCustomBezier",
  "api.buildOfflineEdit",
  "result.duration-result.frameDuration",
  "offlineChooseSource",
  "offlineNormalizePolicy",
  "offlinePlanSources",
  "offlineAuditComp",
  "api.auditOfflineEdit",
  "offlineTransitionEvents",
  "offlineAddMatchedSong",
  "offlinePairedSlide",
  "offlineCrossfade",
  "offlineMaskWipe",
  "TONYFX REVIEW - ",
  "applyTwixtorSelected",
  "Twixtor 45-0005",
  "importLocalEngineOutput",
  "applyReferenceAnalysisMarkers",
  "getInstalledEffectInventory",
  "ADBE Text Percent Start",
  "ADBE Text Percent End",
  "safeStringify",
  "parseJSON",
  "applyEaseToSelection",
  "applyPairedTransition",
  "45",
  "100"
]) {
  if (!host.includes(fragment)) throw new Error(`Host workflow check failed: ${fragment}`);
}

const presets = fs.readFileSync(path.join(root, "js/presets.js"), "utf8");
for (const fragment of [
  "text-blur-reveal",
  "text-tracking-reveal",
  "ghost-zoom",
  "optical-ripple",
  "radial-zoom",
  "flash-shake",
  "flash-smear-cut",
  "zoom-blur-cut",
  "black-dip-cut",
  "rgb-whip-cut",
  "whip-left",
  "whip-right"
  ,"punch-flicker"
  ,"rgb-pulse"
  ,"camera-snap"
  ,"zoom-stutter"
  ,"text-soft-rise"
  ,"text-wipe-left"
  ,"motion-punch-in"
  ,"motion-focus-push"
]) {
  if (!presets.includes(fragment)) throw new Error(`Trend Lab preset check failed: ${fragment}`);
}

const presetIds = Array.from(presets.matchAll(/\{id:"([^"]+)"/g), (match) => match[1]);
const duplicateIds = presetIds.filter((id, index) => presetIds.indexOf(id) !== index);
if (duplicateIds.length) throw new Error(`Duplicate preset IDs: ${Array.from(new Set(duplicateIds)).join(", ")}`);
if (presetIds.length < 74) throw new Error(`Preset catalog unexpectedly small: ${presetIds.length}`);
const effectEntries = Array.from(presets.matchAll(/\{id:"([^"]+)",name:"([^"]+)",category:"Effects"([^}]*)\}/g));
if (effectEntries.length < 20) throw new Error(`Effects catalog unexpectedly small: ${effectEntries.length}`);
for (const match of effectEntries) {
  if (!/duration:\d+/.test(match[3])) throw new Error(`Effect has no duration: ${match[1]}`);
  if (!/amount:\d+/.test(match[3])) throw new Error(`Effect has no meaningful amount: ${match[1]}`);
  if (!/preview:"[^"]+"/.test(match[3])) throw new Error(`Effect has no video preview mapping: ${match[1]}`);
}

const features = fs.readFileSync(path.join(root, "js/features.js"), "utf8");
for (const fragment of [
  "data-layout-option",
  "applyTextStyle",
  "applyTextEffect",
  "textFxCatalog",
  "createIcon",
  "getCaptionSourceSelection",
  "createCaptions",
  "softBloom",
  "chromaticShadow",
  "echoTrail",
  "focusSnap",
  "kineticTilt",
  "auto_caption.py",
  "compDuration",
  "sourceDuration"
]) {
  if (!features.includes(fragment)) throw new Error(`Feature module check failed: ${fragment}`);
}

const captionWorker = fs.readFileSync(path.join(root, "python/auto_caption.py"), "utf8");
for (const fragment of ["WhisperModel", "word_timestamps=True", "vad_filter=True", "speech_pad_ms", "normalize_word_timing", "--language", "--words"]) {
  if (!captionWorker.includes(fragment)) throw new Error(`Caption worker check failed: ${fragment}`);
}
if ((presets.match(/tool:"pairedTransition"/g) || []).length < 4) throw new Error("Paired transition catalog is incomplete.");

const localEngine = fs.readFileSync(path.join(root, "python/local_engine.py"), "utf8");
for (const fragment of ["Real-ESRGAN", "RIFE", "Demucs", "generate-image", "generate-video", "analyze-reference", "compare-edit", "face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx", "FFmpeg restoration", "self-test", "opticalMotion", "Experimental FramePack needs at least 24 GB", "Execute only the requested subject action", "BitsAndBytesConfig", "quantizedTextEncoder", "low_cpu_mem_usage", "restore_reference_identity_video", "identityRestoration"]) {
  if (!localEngine.includes(fragment)) throw new Error(`Local engine check failed: ${fragment}`);
}
if (!localEngine.includes('enhance_parser.add_argument("--engine-root", default=argparse.SUPPRESS)')) {
  throw new Error("Enhance worker is missing cached-panel engine-root compatibility.");
}
const localUi = fs.readFileSync(path.join(root, "js/local-engines.js"), "utf8");
for (const fragment of ['data-enhance-source-mode="clips"', 'data-enhance-source-mode="composition"', 'id="enhancePreviewVideo" controls preload="metadata"']) {
  if (!index.includes(fragment)) throw new Error(`Enhance 0.43 UI is missing: ${fragment}`);
}
for (const fragment of ["setEnhanceSourceMode", "inspectEnhanceSources", "processEnhanceQueue", "importEnhanceResults", "video.muted = false"]) {
  if (!localUi.includes(fragment)) throw new Error(`Enhance 0.43 controller is missing: ${fragment}`);
}
for (const fragment of ["api.getEnhanceSourceSelection", "renderCompositionIntermediate", "entries = options.entries || []"]) {
  if (!host.includes(fragment)) throw new Error(`Enhance 0.43 host support is missing: ${fragment}`);
}
for (const fragment of ["runEnhance", "runAudio", "audioPresets", "audioPresence", "audioCompression", "runGeneration", "runAnalyze", "buildOfflineEdit", "reeditOfflineEdit", "auditOfflineEdit", "compileOfflineEditPolicy", "offlineBuildPayload", "runCompareFinishedEdit", "renderAnalysis", "applyAnalysisMarkers", "reference-feedback.json", "transition-dna.json", "getInstalledEffectInventory", "probeEngines", "importLocalEngineOutput", "setup_local_engine.py", "--song-source", "audioAlignment"]) {
  if (!localUi.includes(fragment)) throw new Error(`Local engine UI check failed: ${fragment}`);
}
for (const fragment of [
  "updateAnalyzeActionState",
  "buildOfflineEditFromFile",
  "applyReferenceAnalysisMarkersFromFile",
  "applyReferenceSafeRepairFromFile"
]) {
  if (!localUi.includes(fragment)) throw new Error(`Analyze action regression check failed: ${fragment}`);
}
for (const fragment of ["explicitCamera", "explicitMotion", "one continuous shot, preserve the same subject and environment"]) {
  if (!localUi.includes(fragment)) throw new Error(`Video prompt guardrail check failed: ${fragment}`);
}
if (!localUi.includes('"--engine-root",defaultEngineRoot(),"enhance"')) {
  throw new Error("Enhance panel is not using the supported global engine-root order.");
}
for (const fragment of ["taskkill", "__tonyfxHandlers", "handlers.workspace", "fs.rmSync", "the entire file will be processed"]) {
  if (!localUi.includes(fragment)) throw new Error(`Enhance cancellation/source check failed: ${fragment}`);
}
for (const fragment of ["run_frame_process", "format_eta", "Restored", "Interpolated"]) {
  if (!localEngine.includes(fragment)) throw new Error(`Enhance progress check failed: ${fragment}`);
}
const appUi = fs.readFileSync(path.join(root, "js/app.js"), "utf8");
for (const fragment of ["hostBootstrapScript", "TONYFX_HOST_READY", "AE ready - open comp"]) {
  if (!appUi.includes(fragment)) throw new Error(`AE reconnection check failed: ${fragment}`);
}

for (const fragment of [
  "ADBE Magnify",
  "ADBE Bulge",
  "ADBE Echo",
  "ADBE Radial Blur",
  "TonyFX - Fast Whip",
  "applyPairedWhip",
  "ADBE Text Blur",
  "ADBE Text Tracking Amount"
  ,"TonyFX - Punch Flicker"
  ,"TonyFX - RGB Pulse"
  ,"TonyFX - Camera Snap"
  ,"TonyFX - Zoom Stutter"
]) {
  if (!host.includes(fragment)) throw new Error(`Trend Lab host check failed: ${fragment}`);
}

console.log("Extension structure and JavaScript syntax checks passed.");
