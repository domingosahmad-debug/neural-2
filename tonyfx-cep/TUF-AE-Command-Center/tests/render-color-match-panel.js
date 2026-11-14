const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9355;
const profile = path.join(process.env.TEMP, "tonyfx-color-match-profile");
const child = spawn(chrome, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--allow-file-access-from-files", "--window-size=1180,940", "about:blank"], {stdio:"ignore"});
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function endpoint() {
  for (let i = 0; i < 60; i++) {
    try {
      const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      const page = pages.find((item) => item.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch (_) {}
    await sleep(100);
  }
  throw new Error("Chrome did not expose a DevTools endpoint.");
}

(async () => {
  const socket = new WebSocket(await endpoint());
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let id = 0;
  const pending = new Map();
  const errors = [];
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.exception.description);
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id); pending.delete(message.id);
      message.error ? entry.reject(new Error(message.error.message)) : entry.resolve(message.result);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => { const command = ++id; pending.set(command, {resolve, reject}); socket.send(JSON.stringify({id:command, method, params})); });
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", {expression, returnByValue:true});
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception.description);
    return result.result.value;
  };
  await send("Page.enable"); await send("Runtime.enable");
  const url = encodeURI(`file:///${path.resolve(__dirname, "../index.html").replace(/\\/g, "/")}`);
  await send("Page.navigate", {url});
  for (let i = 0; i < 60; i++) { if (await evaluate("document.readyState==='complete' && !!window.TonyFXCore")) break; await sleep(100); }
  const state = await evaluate(`(()=>{document.querySelector('[data-tab="color"]').click();const panel=document.getElementById('colorTab');const lab=document.querySelector('.color-match-lab');const lastBand=document.querySelectorAll('[data-color-band]')[3];if(!lastBand.classList.contains('open'))lastBand.querySelector('.color-band-title').click();const lastControl=document.querySelector('[data-color-control="vignetteFeather"]');const rect=lab.getBoundingClientRect();panel.scrollTop=panel.scrollHeight;const lastRect=lastControl.getBoundingClientRect();const panelRect=panel.getBoundingClientRect();return{active:panel.classList.contains('active'),width:rect.width,height:rect.height,buttons:['colorMatchAnalyze','colorMatchApply','colorMatchRender','colorMatchRemove'].every(id=>!!document.getElementById(id)),previews:document.querySelectorAll('.color-match-preview-grid figure').length,metrics:document.querySelectorAll('#colorMatchMetrics>div').length,overflow:document.documentElement.scrollWidth-innerWidth,scrollable:panel.scrollHeight>panel.clientHeight,lastControlReachable:lastRect.bottom<=panelRect.bottom+2&&lastRect.top>=panelRect.top-2,version:document.querySelector('.version').textContent};})()`);
  if (!state.active || !state.buttons || state.previews !== 4 || state.metrics !== 6 || state.width < 500 || state.overflow > 1 || !state.scrollable || !state.lastControlReachable || state.version !== "v0.58.1") throw new Error(`Color Match panel failed: ${JSON.stringify(state)}`);
  const shot = await send("Page.captureScreenshot", {format:"png", captureBeyondViewport:false});
  fs.writeFileSync(path.resolve(__dirname, "tonyfx-v055-color-match.png"), Buffer.from(shot.data, "base64"));
  await send("Emulation.setDeviceMetricsOverride", {width:430, height:780, deviceScaleFactor:1, mobile:false});
  await send("Page.reload", {ignoreCache:true}); await sleep(700);
  const narrow = await evaluate(`(()=>{document.querySelector('[data-tab="color"]').click();document.querySelector('.color-match-lab').scrollIntoView();return{overflow:document.documentElement.scrollWidth-innerWidth,columns:getComputedStyle(document.querySelector('.color-match-preview-grid')).gridTemplateColumns};})()`);
  if (narrow.overflow > 1) throw new Error(`Narrow Color Match overflow: ${JSON.stringify(narrow)}`);
  if (errors.length) throw new Error(errors.join(" | "));
  socket.close(); child.kill(); console.log("TonyFX v0.58.1 Color Match visual checks passed.");
})().catch((error) => { child.kill(); console.error(error); process.exit(1); });
