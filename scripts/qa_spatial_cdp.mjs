import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const [, , endpoint = 'http://127.0.0.1:9223', targetUrl, output = 'output/qa/spatial.png'] = process.argv;
if (!targetUrl) throw new Error('Usage: node scripts/qa_spatial_cdp.mjs <endpoint> <url> <output>');

const targets = await fetch(`${endpoint}/json`).then((response) => response.json());
const page = targets.find((target) => target.type === 'page');
if (!page) throw new Error('No debuggable Chrome page found');

const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolveOpen, reject) => {
  socket.addEventListener('open', resolveOpen, { once: true });
  socket.addEventListener('error', reject, { once: true });
});

let sequence = 0;
const pending = new Map();
socket.addEventListener('message', ({ data }) => {
  const message = JSON.parse(data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve: resolveCall, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(message.error.message));
  else resolveCall(message.result);
});

function call(method, params = {}) {
  const id = ++sequence;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCall, reject) => pending.set(id, { resolve: resolveCall, reject }));
}

await call('Page.enable');
await call('Runtime.enable');
await call('Emulation.setDeviceMetricsOverride', {
  width: 1440,
  height: 1000,
  deviceScaleFactor: 1,
  mobile: false,
});
await call('Page.navigate', { url: targetUrl });
await new Promise((resolveWait) => setTimeout(resolveWait, 5000));
await call('Runtime.evaluate', {
  expression: `Array.from(document.querySelectorAll('button')).find((button) => button.textContent?.includes('3D context'))?.click()`,
  awaitPromise: true,
});
await new Promise((resolveWait) => setTimeout(resolveWait, 7000));
const result = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
const destination = resolve(output);
await mkdir(dirname(destination), { recursive: true });
await writeFile(destination, Buffer.from(result.data, 'base64'));
socket.close();
console.log(destination);
