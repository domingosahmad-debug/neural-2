(function () {
    var reportFile = new File("C:/Users/TUF/Documents/ae-mcp-bridge/tonyfx_enhance_v0422_selection_test.json");
    var reportText = '{"ok":false,"error":"Selection test did not run."}';
    var original = app.project ? app.project.activeItem : null;
    var testComp = null, innerComp = null;
    try {
        $.evalFile(new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
        var footage = null;
        for (var itemIndex = 1; itemIndex <= app.project.numItems; itemIndex++) {
            var item = app.project.item(itemIndex);
            if (item instanceof FootageItem && item.file && item.hasVideo) { footage = item; break; }
        }
        if (!footage) { throw new Error("The open project has no local video footage for the selection test."); }
        var fps = footage.frameRate || 30;
        var duration = Math.max(1 / fps, Math.min(2, footage.duration || 2));
        innerComp = app.project.items.addComp("__TONYFX_SELECTION_INNER__", footage.width || 1080, footage.height || 1080, 1, duration, fps);
        var innerLayer = innerComp.layers.add(footage);
        innerLayer.inPoint = 0;
        innerLayer.outPoint = duration;
        testComp = app.project.items.addComp("__TONYFX_SELECTION_TEST__", footage.width || 1080, footage.height || 1080, 1, duration, fps);
        testComp.openInViewer();
        var layer = testComp.layers.add(innerComp);
        layer.inPoint = 0;
        layer.outPoint = duration;
        layer.selected = true;
        reportText = TUF.getCaptionSourceSelection();
    } catch (error) {
        reportText = '{"ok":false,"error":"' + String(error).replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"}';
    }
    try { if (testComp) { testComp.remove(); } } catch (ignoreCleanup) {}
    try { if (innerComp) { innerComp.remove(); } } catch (ignoreInnerCleanup) {}
    try { if (original && original instanceof CompItem) { original.openInViewer(); } } catch (ignoreRestore) {}
    reportFile.encoding = "UTF-8";
    if (reportFile.open("w")) { reportFile.write(reportText); reportFile.close(); }
}());
