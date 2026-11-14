(function () {
    var hostFile = new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx");
    var outputFolder = new Folder(Folder.myDocuments.fsName + "/ae-mcp-bridge/tonyfx-text-preview");
    var reportFile = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/tonyfx_text_visual_preview.json");
    var original = app.project ? app.project.activeItem : null;
    var comp = null;
    var report = {ok:false, files:[], error:"", line:0};

    function quote(value) {
        return '"' + String(value).replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n") + '"';
    }
    function stringify(value) {
        if (value === null) { return "null"; }
        var type = typeof value;
        if (type === "string") { return quote(value); }
        if (type === "number") { return isFinite(value) ? String(value) : "null"; }
        if (type === "boolean") { return value ? "true" : "false"; }
        if (value instanceof Array) {
            var values = [];
            for (var i=0; i<value.length; i++) { values.push(stringify(value[i])); }
            return "[" + values.join(",") + "]";
        }
        var pairs = [];
        for (var key in value) {
            if (value.hasOwnProperty(key) && typeof value[key] !== "undefined") {
                pairs.push(quote(key) + ":" + stringify(value[key]));
            }
        }
        return "{" + pairs.join(",") + "}";
    }
    function parse(value) { return eval("(" + value + ")"); }
    function selectOnly(layer) {
        for (var i=1; i<=comp.numLayers; i++) { comp.layer(i).selected = false; }
        layer.selected = true;
    }
    function addPreset(id, name, mode, direction, unit, duration, amount, smoothness, variant) {
        var preset = {
            id:id,
            name:name,
            tool:"textMotion",
            mode:mode,
            direction:direction || "up",
            unit:unit || "words",
            duration:duration,
            smoothness:smoothness
        };
        if (amount !== null) { preset.amount = amount; }
        if (variant) { preset.variant = variant; }
        return preset;
    }

    var presets = [
        addPreset("text-left", "Text Reveal Left", "position", "left", "words", 10, 420, 22),
        addPreset("text-right", "Text Reveal Right", "position", "right", "words", 10, 420, 22),
        addPreset("text-up", "Text Reveal Up", "position", "up", "words", 10, 260, 22),
        addPreset("text-down", "Text Reveal Down", "position", "down", "words", 10, 260, 22),
        addPreset("text-char-fade", "Letter Fade", "opacity", "up", "characters", 14, null, 22),
        addPreset("text-word-fade", "Word Fade", "opacity", "up", "words", 12, null, 38),
        addPreset("text-scale-pop", "Word Scale Pop", "scale", "up", "words", 9, null, 28, "overshoot"),
        addPreset("text-rotate", "Letter Rotate In", "rotate", "up", "characters", 12, null, 20),
        addPreset("text-blur-reveal", "Blur Reveal", "blur", "up", "words", 11, null, 42),
        addPreset("text-tracking-reveal", "Tracking Reveal", "tracking", "up", "characters", 15, null, 28),
        addPreset("text-soft-rise", "Soft Word Rise", "position", "up", "words", 14, 110, 24),
        addPreset("text-drop-in", "Word Drop In", "position", "down", "words", 12, 170, 20),
        addPreset("text-pop-blur", "Pop + Focus", "popBlur", "up", "words", 12, null, 18),
        addPreset("text-scale-punch", "Scale Punch", "scalePunch", "up", "words", 10, null, 15),
        addPreset("text-rotate-words", "Word Rotate In", "rotate", "up", "words", 13, null, 24),
        addPreset("text-tighten", "Tracking Tighten", "trackingTight", "up", "characters", 16, null, 30),
        addPreset("text-wipe-left", "Clean Wipe Left", "wipe", "left", "characters", 13, null, 8),
        addPreset("text-wipe-right", "Clean Wipe Right", "wipe", "right", "characters", 13, null, 8),
        addPreset("text-flicker-on", "Flicker On", "flicker", "up", "characters", 10, null, 0),
        addPreset("text-wave-rise", "Wave Rise", "wave", "up", "characters", 18, null, 36)
    ];

    try {
        $.evalFile(hostFile);
        if (!outputFolder.exists) { outputFolder.create(); }
        comp = app.project.items.addComp("__TONYFX_TEXT_VISUAL_TEST__", 1080, 1080, 1, 2, 30);
        comp.layers.addSolid([0.02,0.025,0.035], "Background", 1080, 1080, 1, 2);
        comp.openInViewer();

        for (var p=0; p<presets.length; p++) {
            var layer = comp.layers.addText(presets[p].name.toUpperCase());
            var textDocumentProperty = layer.property("ADBE Text Properties").property("ADBE Text Document");
            var textDocument = textDocumentProperty.value;
            textDocument.fontSize = 18;
            textDocument.fillColor = [1,1,1];
            textDocument.justification = ParagraphJustification.CENTER_JUSTIFY;
            textDocumentProperty.setValue(textDocument);
            var column = p % 4;
            var row = Math.floor(p / 4);
            layer.property("ADBE Transform Group").property("ADBE Position").setValue([140 + column * 270, 115 + row * 205]);
            layer.inPoint = 0;
            layer.outPoint = 2;
            selectOnly(layer);
            var result = parse(TUF.runTool(stringify(presets[p])));
            if (!result.ok) { throw new Error(presets[p].name + ": " + (result.error || "failed")); }
        }

        var times = [0, 0.12, 0.7];
        for (var t=0; t<times.length; t++) {
            var frameFile = new File(outputFolder.fsName + "/text_motion_all_" + (t+1) + ".png");
            comp.saveFrameToPng(times[t], frameFile);
            report.files.push(frameFile.fsName);
        }
        report.ok = true;
    } catch (error) {
        report.error = error.toString();
        report.line = error.line || 0;
    } finally {
        try { if (comp) { comp.remove(); } } catch (ignoreRemove) {}
        try { if (original && original instanceof CompItem) { original.openInViewer(); } } catch (ignoreRestore) {}
        reportFile.encoding = "UTF-8";
        if (reportFile.open("w")) {
            reportFile.write(stringify(report));
            reportFile.close();
        }
    }
}());
