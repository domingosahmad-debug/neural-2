(function () {
    var reportFile = new File("C:/Users/TUF/Documents/ae-mcp-bridge/tonyfx_enhance_v043_live_test.json");
    var reportText = '{"ok":false,"error":"Live test did not complete."}';
    var original = app.project ? app.project.activeItem : null;
    var outer = null, inner = null;
    try {
        $.evalFile(new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
        var footage = null;
        for (var itemIndex = 1; itemIndex <= app.project.numItems; itemIndex++) {
            var candidate = app.project.item(itemIndex);
            if (candidate instanceof FootageItem && candidate.file && candidate.hasVideo) { footage = candidate; break; }
        }
        if (!footage) { throw new Error("The open project has no local video footage for the TonyFX live test."); }
        var fps = footage.frameRate || 30, duration = Math.max(6 / fps,Math.min(0.5,footage.duration || 0.5));
        inner = app.project.items.addComp("__TONYFX_V043_INNER__",320,180,1,duration,fps);
        var sourceLayer = inner.layers.add(footage); sourceLayer.inPoint=0; sourceLayer.outPoint=duration;
        var scale = Math.max(320/Math.max(1,footage.width),180/Math.max(1,footage.height))*100;
        sourceLayer.property("ADBE Transform Group").property("ADBE Scale").setValue([scale,scale]);
        sourceLayer.property("ADBE Transform Group").property("ADBE Position").setValue([160,90]);
        outer = app.project.items.addComp("__TONYFX_V043_OUTER__",320,180,1,duration*2,fps); outer.openInViewer();
        var first = outer.layers.add(inner); first.inPoint=0; first.outPoint=duration;
        var second = outer.layers.add(inner); second.startTime=duration; second.inPoint=duration; second.outPoint=duration*2;
        first.selected=true; second.selected=true;
        var clipsRaw = TUF.getEnhanceSourceSelection('{"mode":"clips","engineRoot":"C:/Users/TUF/Documents/TonyFX Local Engine"}');
        first.selected=true; second.selected=false;
        var compositionRaw = TUF.getEnhanceSourceSelection('{"mode":"composition","engineRoot":"C:/Users/TUF/Documents/TonyFX Local Engine"}');
        var clipsOk = clipsRaw.indexOf('"ok":true') >= 0 && clipsRaw.indexOf('"items":[') >= 0;
        var compositionOk = compositionRaw.indexOf('"ok":true') >= 0 && compositionRaw.indexOf('"renderedComposition":true') >= 0;
        reportText = '{"ok":' + (clipsOk && compositionOk ? 'true' : 'false') + ',"clips":' + clipsRaw + ',"composition":' + compositionRaw + '}';
    } catch (error) {
        reportText = '{"ok":false,"error":"' + String(error).replace(/\\/g,"\\\\").replace(/"/g,'\\"') + (error.line ? " at line " + error.line : "") + '"}';
    }
    try { if (outer) { outer.remove(); } } catch (ignoreOuter) {}
    try { if (inner) { inner.remove(); } } catch (ignoreInner) {}
    try { if (original && original instanceof CompItem) { original.openInViewer(); } } catch (ignoreRestore) {}
    reportFile.encoding="UTF-8";
    if (reportFile.open("w")) { reportFile.write(reportText); reportFile.close(); }
}());
