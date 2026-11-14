const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9338;
const profile = path.join(process.env.TEMP, "tonyfx-v031-profile");
const child = spawn(chrome, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required", "--window-size=1180,900", "about:blank"], { stdio: "ignore" });

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
async function endpoint() {
  for (let i = 0; i < 40; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      const page = list.find((item) => item.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch (_) {}
    await sleep(100);
  }
  throw new Error("Chrome DevTools endpoint did not start.");
}

(async () => {
  const socket = new WebSocket(await endpoint());
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let id = 0;
  const pending = new Map();
  const pageErrors = [];
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") pageErrors.push(message.params.exceptionDetails.exception.description);
    if (message.id && pending.has(message.id)) {
      const item = pending.get(message.id);
      pending.delete(message.id);
      message.error ? item.reject(new Error(message.error.message)) : item.resolve(message.result);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const commandId = ++id;
    pending.set(commandId, { resolve, reject });
    socket.send(JSON.stringify({ id: commandId, method, params }));
  });
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception.description);
    return result.result.value;
  };
  const capture = async (name) => {
    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    fs.writeFileSync(path.resolve(__dirname, name), Buffer.from(shot.data, "base64"));
  };

  await send("Page.enable");
  await send("Runtime.enable");
  const url = encodeURI(`file:///${path.resolve(__dirname, "../index.html").replace(/\\/g, "/")}`);
  await send("Page.navigate", { url });
  for (let attempt = 0; attempt < 60; attempt++) {
    if (await evaluate("document.readyState === 'complete' && !!window.TonyFXCore && document.querySelectorAll('.icon-tile').length === 18")) break;
    await sleep(100);
  }

  const desktop = await evaluate(`(() => {
    const themes=['classic','titan','volt','gears','prism','ember','studio','blueprint','mono'];
    const themeResults=themes.map(name=>{const b=document.querySelector('[data-theme-option="'+name+'"]');b.click();return document.body.getAttribute('data-theme')===name&&b.classList.contains('active');});
    document.querySelector('[data-theme-option="prism"]').click();
    document.querySelector('[data-layout-option="guided"]').click();
    const guided=document.body.getAttribute('data-layout')==='guided'&&document.getElementById('homeTab').classList.contains('active');
    document.querySelector('[data-tab="create"]').click();
    document.querySelector('[data-text-look="neon"]').click();
    document.querySelector('[data-text-fx-card="flipX"]').click();
    const create={icons:document.querySelectorAll('.icon-tile').length,textFx:document.querySelectorAll('.text-fx-card').length,preview:getComputedStyle(document.querySelector('#textStylePreview span')).textShadow,fxPreview:document.getElementById('textFxPreview').getAttribute('data-text-fx')};
    document.querySelector('[data-tab="captions"]').click();
    document.getElementById('captionTextFx').value='neonTube';document.getElementById('captionTextFx').dispatchEvent(new Event('change'));
    const captions=document.getElementById('captionsTab').classList.contains('active')&&document.getElementById('captionLanguage').options.length===3&&document.getElementById('captionAnimation').options.length===10&&document.getElementById('captionPreview').getAttribute('data-text-fx')==='neonTube';
    document.querySelector('[data-layout-option="pro"]').click();
    document.querySelector('[data-tab="generate"]').click();
    const generation={active:document.getElementById('generateTab').classList.contains('active'),mode:document.getElementById('generateTab').getAttribute('data-generation-mode'),quality:document.getElementById('videoQuality').value,baseFps:document.getElementById('videoBaseFps').value,videoOptions:document.getElementById('videoGenerationOptions').classList.contains('active')};
    document.querySelector('[data-tab="library"]').click();
    [...document.querySelectorAll('#categoryChips button')].find(b=>b.textContent==='Effects').click();
    [...document.querySelectorAll('.preset-card')].find(b=>b.textContent.includes('Flash Smear Cut')).click();
    const preview=document.getElementById('effectPreviewPanel').getBoundingClientRect();
    const cards=document.getElementById('presetGrid').getBoundingClientRect();
    const gradeSignatures=[...document.querySelectorAll('[data-grade]')].map(button=>{button.click();return [...document.querySelectorAll('[data-color-control]')].slice(0,10).map(label=>label.querySelector('input[type=number]').value).join('|');});
    return {themeResults,guided,create,captions,generation,grades:gradeSignatures.length,uniqueGrades:new Set(gradeSignatures).size,previewRight:preview.left>cards.left,overflow:document.documentElement.scrollWidth-window.innerWidth,version:document.querySelector('.version').textContent};
  })()`);
  if (desktop.themeResults.some((ok) => !ok) || !desktop.guided || desktop.create.icons !== 18 || desktop.create.textFx !== 13 || desktop.create.fxPreview !== "flipX" || !desktop.create.preview || !desktop.captions || !desktop.generation.active || desktop.generation.mode !== "video" || desktop.generation.quality !== "balanced" || !desktop.generation.videoOptions || desktop.grades !== 15 || desktop.uniqueGrades !== 15 || !desktop.previewRight || desktop.overflow > 1 || desktop.version !== "v0.51.0") {
    throw new Error(`Desktop workspace check failed: ${JSON.stringify(desktop)}`);
  }
  await capture("tonyfx-v031-desktop.png");
  await evaluate("document.querySelector('[data-tab=\"create\"]').click(); document.querySelector('[data-text-look=\"cinema\"]').click(); document.querySelector('[data-text-fx-card=\"cascade3d\"]').click(); true");
  await capture("tonyfx-v031-create.png");
  await evaluate("document.getElementById('createTab').scrollTop=1000; true");
  await capture("tonyfx-v031-create-fx.png");
  await evaluate("document.querySelector('[data-tab=\"captions\"]').click(); true");
  await capture("tonyfx-v031-captions.png");
  await evaluate("document.querySelector('[data-tab=\"generate\"]').click(); true");
  await capture("tonyfx-v049-video-generation.png");

  await send("Emulation.setDeviceMetricsOverride", { width: 420, height: 780, deviceScaleFactor: 1, mobile: false });
  await send("Page.reload", { ignoreCache: true });
  await sleep(700);
  const narrow = await evaluate(`(() => {
    document.querySelector('[data-layout-option="guided"]').click();
    document.querySelector('[data-theme-option="blueprint"]').click();
    const step=document.querySelector('.guided-steps button').getBoundingClientRect();
    return {layout:document.body.getAttribute('data-layout'),theme:document.body.getAttribute('data-theme'),stepRight:step.right,viewport:innerWidth,overflow:document.documentElement.scrollWidth-innerWidth};
  })()`);
  if (narrow.layout !== "guided" || narrow.theme !== "blueprint" || narrow.stepRight > narrow.viewport + 1 || narrow.overflow > 1) throw new Error(`Narrow workspace check failed: ${JSON.stringify(narrow)}`);
  await capture("tonyfx-v031-narrow.png");

  if (pageErrors.length) throw new Error(`Page errors: ${pageErrors.join(" | ")}`);
  socket.close(); child.kill();
  console.log("TonyFX v0.51.0 desktop and narrow workspace tests passed.");
})().catch((error) => { child.kill(); console.error(error); process.exit(1); });
