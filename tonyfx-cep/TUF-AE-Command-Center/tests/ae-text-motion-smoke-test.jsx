(function () {
    var output = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/tonyfx_text_motion_test.json");
    var original = app.project ? app.project.activeItem : null;
    var testComp = null;
    var report = { ok: false };

    function writeReport(value) {
        function quote(text) {
            return '"' + String(text).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r/g, "\\r").replace(/\n/g, "\\n") + '"';
        }
        function stringify(data) {
            if (data === null) { return "null"; }
            var type = typeof data;
            if (type === "string") { return quote(data); }
            if (type === "number") { return isFinite(data) ? String(data) : "null"; }
            if (type === "boolean") { return data ? "true" : "false"; }
            if (data instanceof Array) {
                var list = [];
                for (var i = 0; i < data.length; i++) { list.push(stringify(data[i])); }
                return "[" + list.join(",") + "]";
            }
            var pairs = [];
            for (var key in data) {
                if (data.hasOwnProperty(key) && typeof data[key] !== "undefined") { pairs.push(quote(key) + ":" + stringify(data[key])); }
            }
            return "{" + pairs.join(",") + "}";
        }
        output.encoding = "UTF-8";
        if (output.open("w")) {
            output.write(stringify(value));
            output.close();
        }
    }

    try {
        $.evalFile(new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
        testComp = app.project.items.addComp("__TONYFX_TEXT_MOTION_TEST__", 1080, 1080, 1, 2, 30);
        testComp.openInViewer();
        var textLayer = testComp.layers.addText("TonyFX Text Motion Test");
        textLayer.inPoint = 0;
        textLayer.outPoint = 2;
        textLayer.selected = true;
        testComp.time = 0;

        var raw = TUF.runTool('{"id":"text-char-fade","name":"Letter Fade","tool":"textMotion","mode":"opacity","unit":"characters","duration":12,"amount":120,"stagger":0}');
        var result = eval("(" + raw + ")");
        var animators = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
        var animator = animators.numProperties ? animators.property(1) : null;
        var selector = animator ? animator.property("ADBE Text Selectors").property(1) : null;
        var offset = selector ? selector.property("ADBE Text Percent Offset") : null;
        report = {
            ok: result.ok === true && !!animator && !!offset && offset.numKeys === 2,
            hostResult: result,
            animatorCount: animators.numProperties,
            animatorName: animator ? animator.name : "",
            offsetKeys: offset ? offset.numKeys : 0
        };
    } catch (error) {
        report = { ok: false, error: error.toString(), line: error.line || 0 };
    } finally {
        try { if (testComp) { testComp.remove(); } } catch (ignoreRemove) {}
        try { if (original && original instanceof CompItem) { original.openInViewer(); } } catch (ignoreRestore) {}
        writeReport(report);
    }
}());
