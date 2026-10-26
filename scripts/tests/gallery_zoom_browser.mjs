import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { readFile, writeFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';

const [binary, profile, page, width, height, screenshot] = process.argv.slice(2);
const browser = spawn(binary, ['--no-sandbox', '--disable-gpu', '--disable-background-networking',
  '--no-first-run', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
  `--user-data-dir=${profile}`, `--window-size=${width},${height}`, page], { stdio: 'ignore' });
let socket;
try {
  let port;
  for (let i = 0; i < 100; i++) {
    try { port = (await readFile(`${profile}/DevToolsActivePort`, 'utf8')).split('\n')[0]; break; }
    catch { await delay(50); }
  }
  assert.ok(port, 'Chromium did not start');
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
  await once(socket, 'open');
  let id = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (!pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  async function evaluate(expression) {
    const result = await send('Runtime.evaluate', { expression, returnByValue: true });
    assert.ok(!result.exceptionDetails, result.exceptionDetails?.text);
    return result.result.value;
  }
  let status;
  for (let i = 0; i < 150; i++) {
    status = await evaluate('document.documentElement.dataset.test');
    if (status === 'PASS' || status?.startsWith('FAIL') || status?.startsWith('ERROR')) break;
    await delay(50);
  }
  assert.equal(status, 'PASS', `Browser checks: ${status}`);
  const before = await evaluate(`(() => {
    cambiarZoomModal(4);
    const rect = modalViewport.getBoundingClientRect();
    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2,
      left: modalViewport.scrollLeft, top: modalViewport.scrollTop};
  })()`);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: before.x, y: before.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: before.x + 60, y: before.y + 50, button: 'left', buttons: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: before.x + 60, y: before.y + 50, button: 'left', clickCount: 1 });
  const after = await evaluate('({left: modalViewport.scrollLeft, top: modalViewport.scrollTop, dragging: modalDrag !== null})');
  assert.ok(after.left < before.left && after.top < before.top, 'Real mouse drag pans both axes');
  assert.equal(after.dragging, false, 'Pointer release clears drag');
  await evaluate('cambiarZoomModal(1)');
  if (Number(width) < 769) {
    await send('Emulation.setTouchEmulationEnabled', { enabled: true });
    const target = await evaluate('document.getElementById("modal-zoom-in").getBoundingClientRect().width');
    assert.ok(target >= 44, 'Touch controls keep a comfortable hit area');
  }
  const image = await send('Page.captureScreenshot', { format: 'png' });
  await writeFile(screenshot, Buffer.from(image.data, 'base64'));
  console.log(`PASS ${width}x${height}: zoom, limits, wheel, navigation, original, pan, close/reopen`);
} finally {
  socket?.close();
  const exit = once(browser, 'exit');
  browser.kill('SIGTERM');
  await exit;
}
