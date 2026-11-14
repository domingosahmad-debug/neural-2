"use strict";
// Input is serialized by TonyFX's existing AE command lock. This adapter never
// retries, invokes a shell, or connects to an external automation service.
module.exports.run = function (options, callback) {
  var fs = require("fs"), path = require("path"), childProcess = require("child_process");
  var finished = false, output = "", errors = "", child, timer;
  function done(result) {
    if (finished) return;
    finished = true;
    if (timer) clearTimeout(timer);
    callback(result);
  }
  try {
    var folder = path.join(options.bridge, "ui", "requests");
    fs.mkdirSync(folder, { recursive: true });
    if (!/^[A-Za-z0-9_-]{1,160}$/.test(options.command.id)) throw new Error("Native UI needs a bounded unique command ID");
    var requestPath = path.join(folder, options.command.id + ".json");
    fs.writeFileSync(requestPath, JSON.stringify({ id: options.command.id, command: options.command.command, args: options.command.args || {}, context: options.context }), "utf8");
    child = childProcess.spawn(options.python, [path.join(options.extension, "python", "native_ui.py"), requestPath], { windowsHide: true, shell: false, stdio: ["ignore", "pipe", "pipe"] });
    timer = setTimeout(function () {
      child.kill();
      done({ ok: false, uncertain: true, error: "Native UI helper did not return within 30 seconds. Inspect fresh state; no input was retried.", noAutomaticRetry: true });
    }, 30000);
    child.stdout.on("data", function (data) { output += data.toString("utf8"); if (output.length > 262144) { child.kill(); done({ ok: false, uncertain: true, error: "Native UI output exceeded its bound", noAutomaticRetry: true }); } });
    child.stderr.on("data", function (data) { errors = (errors + data.toString("utf8")).slice(-4000); });
    child.on("error", function (error) { done({ ok: false, inputStarted: false, error: error.message, noAutomaticRetry: true }); });
    child.on("close", function (code) {
      if (finished) return;
      try { done(JSON.parse(output.trim())); }
      catch (error) { done({ ok: false, uncertain: true, error: "Native UI returned no valid result (exit " + code + "): " + errors, noAutomaticRetry: true }); }
    });
  } catch (error) { done({ ok: false, inputStarted: false, error: error.message, noAutomaticRetry: true }); }
};
