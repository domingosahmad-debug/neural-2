const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const host = fs.readFileSync(path.join(root, "jsx", "host.jsx"), "utf8");
const ui = fs.readFileSync(path.join(root, "js", "local-engines.js"), "utf8");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");

for (const fragment of [
  "offlineNormalizePolicy",
  "offlinePlanSources",
  "offlineCandidateScore",
  "offlineAuditComp",
  "offlineRepairStructure",
  "api.auditOfflineEdit",
  "TRANSITION ",
  "6*frame",
  "sourceCompName",
  "previousAssignments",
  "shotZoomOwnsCut",
  "duplicateCutZooms",
  "offlineReplicaContractIssues",
  "offlineContractShots",
  "offlineContractTransitions",
  "Exact Replica build refused before AE mutation",
  "[ZOOM_OWNER=SCENE]",
  "repeatDirectionByShot",
  "TONYFX OFFLINE DIRECTOR V3"
]) {
  if (!host.includes(fragment)) throw new Error(`Offline Director host contract missing: ${fragment}`);
}

for (const fragment of [
  "compileOfflineEditPolicy",
  "dispatchOfflineBuild",
  "Validated local policy",
  "freezeOutsideRange",
  "reeditOfflineEdit",
  "auditOfflineEdit"
]) {
  if (!ui.includes(fragment)) throw new Error(`Offline Director controller contract missing: ${fragment}`);
}

for (const id of ["offlineMode", "offlineSeed", "offlineFidelity", "offlineIntensity", "offlineDensity", "offlineRepeatWindow", "offlinePrompt", "offlineAutoQA"]) {
  if (!html.includes(`id="${id}"`)) throw new Error(`Offline Director control missing: ${id}`);
}

if (host.includes("offlineExtendScene")) throw new Error("Unsafe base-scene extension logic returned.");
if (!host.includes('scene.audioEnabled=false')) throw new Error("Built source audio is not forcibly muted.");
if (!host.includes('policy.autoQA&&!audit.passed')) throw new Error("Automatic structural QA is not enforced.");
if (!host.includes('shotZoomOwnsCut&&lower.indexOf("zoom")>=0')) throw new Error("Duplicate cut-level zoom guard is missing.");
if (!host.includes('name.indexOf("STRICT ")>=0&&name.toLowerCase().indexOf("zoom")>=0')) throw new Error("Duplicate cut-level zoom QA is missing.");
if (host.includes('repeatOccurrences[sourceIndex]%2===1')) throw new Error("Repeat playback still alternates direction instead of consuming measured topology.");
if (!host.includes('policy.mode==="exact"?100')) throw new Error("Exact mode does not enforce native source speed.");
if (!host.includes('event.families||strict.families')) throw new Error("Builder does not consume contract transition families.");

console.log("Offline Director v3 exact-replica static contracts passed.");
