// Standalone fallback: no connected in-app browser; real viewport emulation in Chrome.
// Only a fresh temporary profile and the local test server are used.
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

const [baseUrl, outputDir] = process.argv.slice(2);
if (!baseUrl?.startsWith('http://127.0.0.1:') || !outputDir) throw new Error('Local URL and output directory required');
const profile = await mkdtemp(join(tmpdir(), 'kiros-m10-chrome-'));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
], {stdio: 'ignore'});
let ws;
try {
  let port;
  for (let i = 0; i < 80; i++) {
    try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break; }
    catch { await delay(100); }
  }
  if (!port) throw new Error('Chrome did not expose a local debugging endpoint');
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {method: 'PUT'})).json();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = event => {
    const value = JSON.parse(event.data);
    const item = pending.get(value.id);
    if (!item) return;
    pending.delete(value.id);
    clearTimeout(item.timer);
    if (value.error) item.reject(new Error(JSON.stringify(value.error)));
    else item.resolve(value.result);
  };
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const messageId = ++id;
    const timer = setTimeout(() => { pending.delete(messageId); reject(new Error(`Timeout: ${method}`)); }, 15000);
    pending.set(messageId, {resolve, reject, timer});
    ws.send(JSON.stringify({id: messageId, method, params}));
  });
  await call('Page.enable');
  const evidence = [];
  for (const tab of ['diversity', 'sources', 'experiments']) {
    for (const [device, width, height] of [['desktop', 1280, 1000], ['mobile', 390, 844]]) {
      await call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: device === 'mobile'});
      await call('Page.navigate', {url: `${baseUrl}/insights?tab=${tab}&include_mock=1`});
      for (let i = 0; i < 60; i++) {
        const ready = await call('Runtime.evaluate', {expression: "document.readyState === 'complete' && !!document.querySelector('.insights')", returnByValue: true});
        if (ready.result.value) break;
        await delay(100);
      }
      await call('Runtime.evaluate', {expression: 'document.fonts.ready.then(() => true)', awaitPromise: true, returnByValue: true});
      const metrics = (await call('Runtime.evaluate', {expression: `JSON.stringify({
        width: innerWidth, documentWidth: document.documentElement.scrollWidth,
        title: document.querySelector('.insights h1')?.textContent,
        height: document.documentElement.scrollHeight,
        duplicateIds: [...document.querySelectorAll('[id]')].map(e=>e.id).filter((id,i,ids)=>ids.indexOf(id)!==i),
        unlabeledControls: [...document.querySelectorAll('.insights input:not([type=hidden]),.insights textarea,.insights select')].filter(e=>!e.labels?.length).length
      })`, returnByValue: true})).result.value;
      const measured = JSON.parse(metrics);
      if (measured.width !== width || measured.documentWidth > width || measured.duplicateIds.length || measured.unlabeledControls) {
        throw new Error(`Invalid UI geometry or labels ${tab}/${device}: ${metrics}`);
      }
      const capture = await call('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true,
        clip: {x: 0, y: 0, width, height: measured.height, scale: 1}});
      const file = `M10-${tab}-${device}.png`;
      await writeFile(join(outputDir, file), Buffer.from(capture.data, 'base64'));
      evidence.push({tab, device, ...measured, file});
      process.stdout.write(`${file}: viewport ${width}px; document ${measured.documentWidth}px; controls labeled\n`);
    }
  }
  await writeFile(join(outputDir, 'M10-visual.json'), JSON.stringify(evidence, null, 2) + '\n');
  await call('Browser.close').catch(() => {});
} finally {
  ws?.close();
  chrome.kill('SIGTERM');
  await Promise.race([new Promise(resolve => chrome.once('exit', resolve)), delay(1500)]);
  await rm(profile, {recursive: true, force: true, maxRetries: 3, retryDelay: 200});
}
