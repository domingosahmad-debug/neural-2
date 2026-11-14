#target aftereffects
(function () {
    var output = new File("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_enhance_artifacts/ai_upscale_v0422.mp4");
    var report = new File("C:/Users/TUF/Documents/ae-mcp-bridge/tonyfx_enhance_v0422_import_test.txt");
    var comp = null, importedItem = null, original = app.project ? app.project.activeItem : null;
    function write(value) { report.encoding = "UTF-8"; if (report.open("w")) { report.write(value); report.close(); } }
    try {
        if (!output.exists) { throw new Error("Verified enhancement output is missing"); }
        if (typeof TUF === "undefined" || typeof TUF.importLocalEngineOutput !== "function") {
            $.evalFile(new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
        }
        comp = app.project.items.addComp("__TONYFX_ENHANCE_V0422_QA__", 512, 512, 1, 1, 6);
        comp.openInViewer();
        var payload = '{"paths":["C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests/_enhance_artifacts/ai_upscale_v0422.mp4"],"compIn":0,"kind":"enhance","addToTimeline":true}';
        TUF.importLocalEngineOutput(payload);
        var layer = comp.layer(1);
        if (!layer || !layer.source || !layer.source.file || layer.source.file.fsName !== output.fsName) { throw new Error("Enhanced output was not added to the disposable comp."); }
        importedItem = layer.source;
        if (Math.abs(layer.inPoint) > 0.0001 || layer.label !== 13) { throw new Error("Imported layer alignment or label is incorrect."); }
        if (importedItem.width !== 512 || importedItem.height !== 512) { throw new Error("Imported dimensions are incorrect."); }
        write("PASSED\nHOST_IMPORT=YES\nALIGNED=YES\nDIMENSIONS=512x512\nLABEL=13\nOUTPUT=" + output.fsName);
    } catch (error) {
        write("FAILED\nERROR=" + error.toString() + "\nLINE=" + (error.line || ""));
    }
    try { if (comp) { comp.remove(); } } catch (ignoreComp) {}
    try { if (importedItem && importedItem.parentFolder) { importedItem.remove(); } } catch (ignoreItem) {}
    try { if (original && original instanceof CompItem) { original.openInViewer(); } } catch (ignoreRestore) {}
}());
