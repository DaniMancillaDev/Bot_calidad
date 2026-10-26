import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {readFile, writeFile} from 'node:fs/promises';
import {setTimeout as delay} from 'node:timers/promises';

const [binary, profile, page, width, height, screenshot] = process.argv.slice(2);
const browser = spawn(binary, ['--no-sandbox', '--disable-gpu', '--disable-background-networking',
  '--no-first-run', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
  `--user-data-dir=${profile}`, `--window-size=${width},${height}`, page], {stdio: 'ignore'});
let socket;
try {
  let port;
  for (let i = 0; i < 100; i++) {
    try {port = (await readFile(profile + '/DevToolsActivePort', 'utf8')).split('\n')[0]; break;}
    catch {await delay(50);}
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
    const {resolve, reject} = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(Error(message.error.message)); else resolve(message.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
  });
  const evaluate = async expression => {
    const result = await send('Runtime.evaluate', {expression, returnByValue: true});
    assert.ok(!result.exceptionDetails, result.exceptionDetails?.text);
    return result.result.value;
  };
  let status;
  for (let i = 0; i < 150; i++) {
    status = await evaluate('document.documentElement.dataset.test');
    if (status) break;
    await delay(50);
  }
  assert.equal(status, 'PASS', status);
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27});
  await delay(50);
  assert.equal(await evaluate('window.escapeResult'), false, 'Escape cancels, never confirms');
  await evaluate('iqaPrompt("Motivo", "Original"); void 0');
  await delay(50);
  assert.equal(await evaluate('document.activeElement.id'), 'app-dialog-input');
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Enter', code: 'Enter', text: '\r', windowsVirtualKeyCode: 13});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13});
  await delay(50);
  assert.equal(await evaluate('document.getElementById("app-dialog").open'), false, 'Enter submits prompt');
  await evaluate('showConfirmModal("Eliminar registro", "¿Seguro que deseas eliminar este registro permanentemente?", "Eliminar", "#ef4444"); void 0');
  await delay(50);
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9});
  assert.equal(await evaluate('document.getElementById("app-dialog").contains(document.activeElement)'), true, 'Keyboard focus remains inside dialog');
  const image = await send('Page.captureScreenshot', {format: 'png'});
  await writeFile(screenshot, Buffer.from(image.data, 'base64'));
  console.log(`PASS ${width}x${height}: dialogs, prompts, cancel, Escape, focus, delete caller`);
} finally {
  socket?.close(); const done = once(browser, 'exit'); browser.kill('SIGTERM'); await done;
}
