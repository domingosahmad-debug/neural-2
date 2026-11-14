#target aftereffects
(function () {
    var output = new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_enhance_artifacts/ai_upscale.mp4");
    var report = new File("C:/Users/TUF/Documents/ae-mcp-bridge/tonyfx_enhance_v0421_import_test.txt");
    var compName = "TONYFX ENHANCE V0421 QA";

    function write(value) {
        report.encoding = "UTF-8";
        if (report.open("w")) {
            report.write(value);
            report.close();
        }
    }

    function findComp(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === name) return item;
        }
        return null;
    }

    try {
        if (!output.exists) throw new Error("Verified enhancement output is missing");
        if (typeof TUF === "undefined" || typeof TUF.importLocalEngineOutput !== "function") {
            throw new Error("TonyFX host import function is unavailable");
        }

        var oldComp = findComp(compName);
        if (oldComp) oldComp.remove();
        app.beginUndoGroup("TonyFX Enhance import QA");
        var comp = app.project.items.addComp(compName, 512, 512, 1, 1, 6);
        comp.openInViewer();

        var payload = '{"paths":["C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_enhance_artifacts/ai_upscale.mp4"],"compIn":0,"kind":"enhance","addToTimeline":true}';
        var raw = TUF.importLocalEngineOutput(payload);
        var importedLayer = null;
        for (var layerIndex = 1; layerIndex <= comp.numLayers; layerIndex++) {
            var layer = comp.layer(layerIndex);
            if (layer.source && layer.source.file && layer.source.file.fsName === output.fsName) {
                importedLayer = layer;
                break;
            }
        }
        if (!importedLayer) throw new Error("Enhanced output was not added to the disposable comp. Host result: " + raw);
        if (Math.abs(importedLayer.inPoint) > 0.0001) throw new Error("Imported output is not aligned at zero");
        if (importedLayer.label !== 13) throw new Error("Enhanced output did not receive the expected label");
        if (importedLayer.source.width !== 512 || importedLayer.source.height !== 512) throw new Error("Imported dimensions are incorrect");

        var importedItem = importedLayer.source;
        comp.remove();
        if (importedItem && importedItem.parentFolder) importedItem.remove();
        app.endUndoGroup();
        write("PASSED\nHOST_IMPORT=YES\nALIGNED=YES\nDIMENSIONS=512x512\nLABEL=13\nOUTPUT=" + output.fsName);
    } catch (error) {
        try { app.endUndoGroup(); } catch (ignore) {}
        write("FAILED\nERROR=" + error.toString() + "\nLINE=" + (error.line || ""));
    }
})();
