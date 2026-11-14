(function () {
    var root = new Folder("C:/Users/TUF/Documents/New project/tuf-ae-command-center/tests");
    $.evalFile(new File(root.fsName + "/ae-adjustment-effects-test.jsx"));
    $.evalFile(new File(root.fsName + "/ae-user-bug-regression-test.jsx"));
    try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (ignoreClose) {}
    try { app.quit(); } catch (ignoreQuit) {}
}());
