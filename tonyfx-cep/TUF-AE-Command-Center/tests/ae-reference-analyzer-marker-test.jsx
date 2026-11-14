(function () {
    var resultFile = new File("C:/Users/TUF/Documents/ae-mcp-bridge/tonyfx_reference_analyzer_marker_test.txt");
    var extensionRoot = Folder.userData.fsName + "/Adobe/CEP/extensions/TUF-AE-Command-Center";
    var hostFile = new File(extensionRoot + "/jsx/host.jsx");
    var previous = app.project.activeItem;
    var testComp = null;
    var result = {ok:false,tests:[]};
    function record(name, passed, detail) { result.tests.push({name:name,passed:!!passed,detail:String(detail || "")}); }
    try {
        if (!hostFile.exists) { throw new Error("Installed TonyFX host.jsx was not found."); }
        $.evalFile(hostFile);
        record("host API loaded", typeof TUF !== "undefined" && typeof TUF.applyReferenceAnalysisMarkers === "function", "applyReferenceAnalysisMarkers");
        testComp = app.project.items.addComp("TONYFX REF ANALYZER DISPOSABLE TEST", 1080, 1080, 1, 8, 30);
        testComp.openInViewer();
        var payload = {
            source:"synthetic-reference.mp4", offset:1.0, includeCuts:true, includeBeats:true, replace:true,
            events:[
                {time:0.5,family:"whip_left",durationFrames:5,graph:"speed_ramp",curve:"0.09, 0.72, 0.94, 0.27",confidence:0.92,aeRecipe:[{effect:"Motion Tile"},{property:"Position"},{effect:"Directional Blur"}]},
                {time:1.2,family:"black_dip",durationFrames:4,graph:"sharp_end",curve:"0.75, 0.00, 0.95, 0.25",confidence:0.88,aeRecipe:[{property:"Opacity"}]}
            ],
            beats:[0.25,0.75,1.25]
        };
        var raw = TUF.applyReferenceAnalysisMarkers(payload.toSource());
        record("marker command succeeded", raw.indexOf('"ok":true') >= 0, raw);
        record("cut and beat markers created", testComp.markerProperty.numKeys === 5, "count=" + testComp.markerProperty.numKeys);
        record("offset applied", Math.abs(testComp.markerProperty.keyTime(1) - 1.25) < 0.001, "first=" + testComp.markerProperty.keyTime(1));
        var comments = [];
        for (var i=1;i<=testComp.markerProperty.numKeys;i++) { comments.push(testComp.markerProperty.keyValue(i).comment); }
        record("recipe and graph preserved", comments.join(" | ").indexOf("speed_ramp") >= 0 && comments.join(" | ").indexOf("Directional Blur") >= 0, comments.join(" | "));
        result.ok = true; for (var t=0;t<result.tests.length;t++) { if (!result.tests[t].passed) { result.ok = false; break; } }
    } catch (error) {
        result.error = error.toString() + (error.line ? " at line " + error.line : "");
    } finally {
        try { if (testComp) { testComp.remove(); } } catch (ignoreRemove) {}
        try { if (previous && previous.openInViewer) { previous.openInViewer(); } } catch (ignoreRestore) {}
        var lines = ["ok=" + result.ok];
        if (result.error) { lines.push("error=" + result.error); }
        for (var lineIndex=0;lineIndex<result.tests.length;lineIndex++) { var test=result.tests[lineIndex]; lines.push((test.passed ? "PASS" : "FAIL") + " | " + test.name + " | " + test.detail); }
        resultFile.encoding = "UTF-8"; resultFile.open("w"); resultFile.write(lines.join("\n")); resultFile.close();
    }
}());
