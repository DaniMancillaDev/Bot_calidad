"""Real Chromium checks for themed dialogs and the Operation delete caller."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CHECKS = r"""
async function check() {
  const assert = (value, text) => { if (!value) throw Error(text); };
  const tick = () => new Promise(resolve => setTimeout(resolve, 30));
  const dialog = document.getElementById('app-dialog');
  const cancel = document.getElementById('app-dialog-cancel');
  const accept = document.getElementById('app-dialog-accept');
  document.getElementById('trigger').focus();
  let promise = iqaConfirm('<img src=x onerror=alert(1)>'); await tick();
  assert(dialog.open && document.activeElement === cancel, 'Safe initial focus');
  assert(!dialog.querySelector('img'), 'Message is plain text');
  cancel.click(); assert(await promise === false, 'Cancel is false');
  assert(document.activeElement.id === 'trigger', 'Focus restored');
  let callbacks = 0;
  promise = showConfirmModal('Eliminar', 'Mensaje', 'Eliminar', 'var(--danger)', () => callbacks++);
  await tick(); accept.click(); accept.click();
  assert(await promise === true && callbacks === 1, 'Callback once');
  promise = iqaPrompt('Motivo', 'Original'); await tick();
  const input = document.getElementById('app-dialog-input');
  assert(document.activeElement === input && input.value === 'Original', 'Prompt focus and default');
  input.value = ''; dialog.querySelector('form').requestSubmit(accept);
  assert(await promise === '', 'Empty input preserved');
  promise = iqaPrompt('Editar', 'Original'); await tick();
  cancel.click(); assert(await promise === null, 'Prompt cancel is null');
  const first = iqaAlert('Uno'), second = iqaAlert('Dos'); await tick();
  assert(cancel.hidden && document.getElementById('app-dialog-text').textContent === 'Uno', 'Alert without cancel');
  accept.click(); await first; await tick();
  assert(document.getElementById('app-dialog-text').textContent === 'Dos', 'Concurrent dialogs queued');
  accept.click(); await second;
  let requests = 0, rendered = 0;
  window.fetch = async () => { requests++; return {ok: true}; };
  const panel = Object.create(PanelOperativo.prototype);
  panel.registros = [{id: 1}, {id: 2}]; panel.getCsrfToken = () => 'synthetic';
  panel.renderTabla = () => rendered++; panel.mostrarToast = () => {};
  promise = panel.eliminarRegistro(1); await tick();
  assert(requests === 0, 'No request before confirmation');
  cancel.click(); await promise;
  assert(requests === 0 && panel.registros.length === 2, 'Cancel leaves records untouched');
  promise = panel.eliminarRegistro(1); await tick(); accept.click(); await promise;
  assert(requests === 1 && rendered === 1 && panel.registros[0].id === 2, 'Confirm deletes only requested row');
  window.escapeResult = undefined;
  iqaConfirm('Confirmacion pendiente').then(value => { window.escapeResult = value; });
  await tick();
  const bounds = dialog.getBoundingClientRect();
  assert(bounds.left >= 0 && bounds.right <= innerWidth && bounds.bottom <= innerHeight, 'Dialog fits viewport');
}
check().then(() => document.documentElement.dataset.test = 'PASS')
  .catch(error => document.documentElement.dataset.test = 'FAIL: ' + error.message);
"""


class AppDialogTests(unittest.TestCase):
    def test_native_browser_messages_replaced(self):
        files = [* (ROOT / 'web/templates').rglob('*.html'),
                 * (ROOT / 'web/workspace/templates').rglob('*.html'),
                 * (ROOT / 'web/static/js').rglob('*.js')]
        for path in files:
            self.assertIsNone(re.search(r'\b(?:alert|confirm|prompt)\s*\(', path.read_text()), str(path))

    def test_desktop_and_mobile(self):
        browsers = list((Path.home() / '.cache/ms-playwright').glob('chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'))
        browser = os.environ.get('CHROME_BIN') or shutil.which('chromium') or (str(sorted(browsers)[-1]) if browsers else None)
        if not browser:
            self.skipTest('No Chromium installed; browser checks not performed')
        partial = (ROOT / 'web/templates/calidad/partials/app_dialog.html').read_text()
        panel = (ROOT / 'web/static/js/panel_operativo.js').read_text().split('// Iniciar aplicación', 1)[0]
        html = '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><button id="trigger">Abrir</button>' + partial + '<script>' + panel + CHECKS + '</script></body></html>'
        for width, height in [(1440, 1000), (390, 844)]:
            with self.subTest(width=width), tempfile.TemporaryDirectory(dir='/dev/shm', prefix='iqa-dialog-test-') as scratch:
                page = Path(scratch) / 'test.html'
                page.write_text(html)
                output = Path('/dev/shm') / f'iqa-app-dialog-{width}.png'
                result = subprocess.run(['node', str(Path(__file__).with_name('app_dialog_browser.mjs')),
                                         browser, scratch + '/profile', page.as_uri(), str(width), str(height), str(output)], capture_output=True, text=True, timeout=25)
                self.assertEqual(result.returncode, 0, result.stderr[-1500:])
                self.assertIn('PASS', result.stdout)
