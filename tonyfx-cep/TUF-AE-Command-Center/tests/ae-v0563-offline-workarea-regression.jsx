(function () {
    var root = "C:/Users/TUF/Documents/New project/tuf-ae-command-center";
    var bridge = "C:/Users/TUF/Documents/ae-mcp-bridge";
    var payload = bridge + "/tonyfx_v0563_workarea_payload.json";
    var output = new File(bridge + "/tonyfx_v0563_workarea_result.json");
    var original = app.project.activeItem;
    var sourceComp = null;
    var builtComp = null;
    var report = {ok:false};
    function decode(raw) { return eval("(" + raw + ")"); }
    function escaped(value) { return String(value === undefined ? "" : value).replace(/\\/g,"\\\\").replace(/\"/g,"\\\"").replace(/[\r\n]+/g," "); }
    function reportText() {
        return '{"ok":' + (report.ok ? "true" : "false") + ',"error":"' + escaped(report.error || "") + '","duration":' + Number(report.duration || 0) + ',"workAreaDuration":' + Number(report.workAreaDuration || 0) + ',"count":' + Number(report.count || 0) + '}';
    }
    try {
        $.evalFile(new File(root + "/jsx/host.jsx"));
        sourceComp = app.project.items.addComp("__TONYFX_V0563_WORKAREA_SOURCE__",320,320,1,12,30);
        sourceComp.layers.addSolid([0.1,0.1,0.1],"SOURCE THREE",320,320,1,12);
        sourceComp.layers.addSolid([0.2,0.2,0.2],"SOURCE TWO",320,320,1,12);
        sourceComp.layers.addSolid([0.3,0.3,0.3],"SOURCE ONE",320,320,1,12);
        sourceComp.openInViewer();
        for (var i=1;i<=sourceComp.numLayers;i++) { sourceComp.layer(i).selected=true; }
        var built = decode(TUF.buildOfflineEditFromFile(payload));
        if (!built.ok || built.count !== 3) { throw new Error("Offline build failed: " + built.error); }
        for (var p=1;p<=app.project.numItems;p++) {
            var item=app.project.item(p);
            if (item instanceof CompItem && item.name===built.compName) { builtComp=item;break; }
        }
        if (!builtComp) { throw new Error("Offline build composition was not created."); }
        report.duration=builtComp.duration;
        report.workAreaDuration=builtComp.workAreaDuration;
        report.count=built.count;
        if (builtComp.workAreaDuration <= 0 || builtComp.workAreaDuration > builtComp.duration) {
            throw new Error("Work area is outside the legal composition range.");
        }
        report.ok=true;
    } catch (error) {
        report.error=error.toString();
    } finally {
        try { if (builtComp) { builtComp.remove(); } } catch (ignoreBuilt) {}
        try { if (sourceComp) { sourceComp.remove(); } } catch (ignoreSource) {}
        try { if (original && original instanceof CompItem) { original.openInViewer(); } } catch (ignoreOriginal) {}
        output.encoding="UTF-8";
        if (output.open("w")) { output.write(reportText());output.close(); }
    }
}());
