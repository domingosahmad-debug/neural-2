const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9337;
const profile = path.join(process.env.TEMP, "tonyfx-headless-profile");
const child = spawn(chrome, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required", "--window-size=1000,900", "about:blank"], { stdio: "ignore" });

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
async function endpoint() {
  for (let i = 0; i < 30; i++) {
    try { const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); const page = list.find((item) => item.type === "page"); if (page) { console.log(`CDP target: ${page.url}`); return page.webSocketDebuggerUrl; } } catch (_) {}
    await sleep(100);
  }
  throw new Error("Chrome DevTools endpoint did not start.");
}

(async () => {
  const socket = new WebSocket(await endpoint());
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let id = 0;
  const pending = new Map();
  socket.onmessage = (event) => { const message = JSON.parse(event.data); if (message.method === "Runtime.exceptionThrown") console.error(`PAGE ERROR: ${message.params.exceptionDetails.exception.description}`); if (message.id && pending.has(message.id)) { const item = pending.get(message.id); pending.delete(message.id); message.error ? item.reject(new Error(message.error.message)) : item.resolve(message.result); } };
  const send = (method, params = {}) => new Promise((resolve, reject) => { const commandId = ++id; pending.set(commandId, { resolve, reject }); socket.send(JSON.stringify({ id: commandId, method, params })); });
  await send("Page.enable");
  await send("Runtime.enable");
  const url = encodeURI(`file:///${path.resolve(__dirname, "../index.html").replace(/\\/g, "/")}`);
  await send("Page.navigate", { url });
  for (let attempt = 0; attempt < 60; attempt++) {
    const ready = await send("Runtime.evaluate", { expression: `document.readyState === 'complete' && !!window.TUF_PRESETS && window.TUF_PRESETS.length > 0`, returnByValue: true });
    if (ready.result && ready.result.value) break;
    await sleep(100);
  }
  const expression = `(() => { document.querySelector('[data-tab="library"]').click(); const buttons=[...document.querySelectorAll('#categoryChips button')]; const effects=buttons.find(b=>b.textContent==='Effects'); if(!effects)return {error:'Missing Effects category',ready:document.readyState,presets:(window.TUF_PRESETS||[]).length,scripts:[...document.scripts].map(s=>s.src),buttons:buttons.map(b=>b.textContent)}; effects.click(); const cards=[...document.querySelectorAll('.preset-card')]; const card=cards.find(c=>c.textContent.includes('Zoom Blur Cut')); if(!card)return {error:'Missing Zoom Blur Cut',cards:cards.map(c=>c.textContent)}; card.click(); return {visible:!document.getElementById('effectPreviewPanel').classList.contains('hidden'),enabled:!document.getElementById('applyEffectPreview').disabled,name:document.getElementById('effectPreviewName').textContent}; })()`;
  const result = await send("Runtime.evaluate", { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error(`Browser evaluation failed: ${JSON.stringify(result.exceptionDetails)}`);
  const value = result.result.value;
  if (!value || value.error || !value.visible || !value.enabled || value.name !== "Zoom Blur Cut") throw new Error(`Effect preview state failed: ${JSON.stringify(value)}`);
  await sleep(700);
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  fs.writeFileSync(path.resolve(__dirname, "tonyfx-v018-effects.png"), Buffer.from(shot.data, "base64"));
  socket.close(); child.kill();
  console.log("Effects panel visual test passed.");
})().catch((error) => { child.kill(); console.error(error); process.exit(1); });
