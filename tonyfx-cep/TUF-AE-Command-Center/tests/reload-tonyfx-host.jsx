(function () {
    try {
        $.evalFile(new File("C:/Users/TUF/AppData/Roaming/Adobe/CEP/extensions/TUF-AE-Command-Center/jsx/host.jsx"));
        return TUF.inspectActiveComp();
    } catch (error) {
        return '{"ok":false,"error":"' + String(error).replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"}';
    }
}());
