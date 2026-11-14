(function () {
    var root = "C:/Users/TUF/Documents/New project/tuf-ae-command-center";
    var bridge = "C:/Users/TUF/Documents/ae-mcp-bridge";
    var markerPayload = bridge + "/tonyfx_v0561_marker_payload.json";
    var buildPayload = bridge + "/tonyfx_v0561_build_payload.json";
    var output = new File(bridge + "/tonyfx_v0561_analyze_actions_result.json");
    var original = app.project.activeItem;
    var sourceComp = null;
    var builtComp = null;
    var repairedComp = null;
    var report = {ok:false,markers:null,build:null};
    function decode(raw) { return eval("(" + raw + ")"); }
    function escapeText(value) { return String(value === undefined ? "" : value).replace(/\\/g,"\\\\").replace(/\"/g,"\\\"").replace(/[\r\n]+/g," "); }
    function reportText() {
        return '{"ok":' + (report.ok ? "true" : "false") + ',"error":"' + escapeText(report.error || "") + '","markerOk":' + (report.markers && report.markers.ok ? "true" : "false") + ',"markerCount":' + Number(report.markers && report.markers.added || 0) + ',"buildOk":' + (report.build && report.build.ok ? "true" : "false") + ',"buildCount":' + Number(report.build && report.build.count || 0) + '}';
    }
    try {
        $.evalFile(new File(root + "/jsx/host.jsx"));
        sourceComp = app.project.items.addComp("__TONYFX_V0561_ACTION_SOURCE__",320,320,1,3,30);
        sourceComp.layers.addSolid([0.1,0.1,0.1],"SOURCE THREE",320,320,1,3);
        sourceComp.layers.addSolid([0.2,0.2,0.2],"SOURCE TWO",320,320,1,3);
        sourceComp.layers.addSolid([0.3,0.3,0.3],"SOURCE ONE",320,320,1,3);
        sourceComp.openInViewer();
        for (var i=1;i<=sourceComp.numLayers;i++) { sourceComp.layer(i).selected=true; }
        report.markers = decode(TUF.applyReferenceAnalysisMarkersFromFile(markerPayload));
        if (!report.markers.ok || report.markers.added < 4) { throw new Error("File-backed marker action failed: " + report.markers.error); }
        report.build = decode(TUF.buildOfflineEditFromFile(buildPayload));
        if (!report.build.ok || report.build.count !== 3) { throw new Error("File-backed offline build failed: " + report.build.error); }
        for (var p=1;p<=app.project.numItems;p++) {
            var item=app.project.item(p);
            if (item instanceof CompItem && item.name===report.build.compName) { builtComp=item;break; }
        }
        if (!builtComp || builtComp.numLayers < 3) { throw new Error("Offline build composition was not created correctly."); }
        report.ok=true;
    } catch (error) {
        report.error=error.toString();report.line=error.line || 0;
    } finally {
        try { if (builtComp) { builtComp.remove(); } } catch (ignoreBuilt) {}
        try { if (repairedComp) { repairedComp.remove(); } } catch (ignoreRepair) {}
        try { if (sourceComp) { sourceComp.remove(); } } catch (ignoreSource) {}
        try { if (original && original instanceof CompItem) { original.openInViewer(); } } catch (ignoreOriginal) {}
        output.encoding="UTF-8";
        if (output.open("w")) { output.write(reportText());output.close(); }
    }
}());
