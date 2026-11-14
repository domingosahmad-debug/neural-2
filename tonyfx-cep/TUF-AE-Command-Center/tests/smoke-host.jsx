(function () {
    var output = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/tuf_panel_host_smoke.json");
    output.encoding = "UTF-8";
    try {
        $.evalFile(new File(Folder.userData.fsName + "/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
        var result = TUF.inspectActiveComp();
        if (!output.open("w")) { throw new Error("Could not open smoke-test result file."); }
        output.write(result);
        output.close();
    } catch (error) {
        if (output.open("w")) {
            output.write(JSON.stringify({ok: false, error: error.toString()}));
            output.close();
        }
    }
}());
