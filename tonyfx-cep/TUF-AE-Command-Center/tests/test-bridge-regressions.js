const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.resolve(__dirname, "../js/app.js"), "utf8");
const required = [
  "bridgeActiveCommandId",
  "bridgeLastProcessedId",
  "acquireBridgeLock",
  "recoverInterruptedBridgeCommand",
  "_commandId",
  "Duplicate AE command blocked safely",
  "The command was not rerun",
  "fs.unlinkSync(resultPath)",
  "bridgeTimeoutMs"
];

for (const token of required) {
  if (!source.includes(token)) throw new Error(`Missing bridge safety token: ${token}`);
}

if (!/if \(!bridgeBusy \|\| bridgeActiveCommandId !== commandId\) \{ return; \}/.test(source)) {
  throw new Error("Bridge completion is not guarded by the active command ID.");
}

if (!/if \(commandId === bridgeLastProcessedId\)/.test(source)) {
  throw new Error("Bridge duplicate-command protection is missing.");
}

console.log("TonyFX bridge regression checks passed.");

// Exercise the actual timeout callback without CEP, AE, or a real timer.
const vm = require("vm");
const timeoutDecl = source.match(/var bridgeTimeoutMs = ([^;]+);/);
const timeoutBody = source.match(/bridgeTimeoutTimer = window\.setTimeout\(function \(\) \{([\s\S]*?)\}, bridgeTimeoutMs\);/);
if (!timeoutDecl || !timeoutBody) throw new Error("Missing bounded timeout implementation");
const calls = [];
const context = {bridgeBusy:true, bridgeActiveCommandId:"exact", commandId:"exact",
  commandPath:"fixture-command",resultPath:"fixture-result",commandData:{id:"exact"},Math,
  finishBridgeCommand:(...args)=>calls.push(args),setFooter:()=>{}};
vm.createContext(context);
vm.runInContext("var bridgeTimeoutMs = "+timeoutDecl[1]+";", context);
if (context.bridgeTimeoutMs !== 65*60*1000) throw new Error("Native wait no longer covers measured46minute renders");
vm.runInContext("var expire = function(){"+timeoutBody[1]+"}; expire();",context);
if(calls.length!==1 || calls[0][3].ok!==false || !calls[0][3].error.includes("Completion is unconfirmed"))
  throw new Error("Timeout must retain uncertainty, never claim cancellation or success");
context.bridgeActiveCommandId="newer";
vm.runInContext("expire();",context);
if(calls.length!==1) throw new Error("Stale timer overwrote a newer command");
console.log("Measured render wait and exact-command timeout behavior passed.");
