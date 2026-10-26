"""Real Chromium checks, without Django, production access or npm packages.

Run: python -m unittest scripts.tests.test_gallery_zoom -v
CHROME_BIN can select an installed Chromium binary; scratch stays in RAM.
"""
import base64
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]


def fixture_image():
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    row = b''.join(bytes((40 + (x // 100 % 2) * 100, 140, 170)) for x in range(1600))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1600, 1200, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress((b'\0' + row) * 1200)) + chunk(b'IEND', b'')
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


CHECKS = r"""
async function checkZoom() {
  document.documentElement.dataset.test = 'STARTED';
  function assert(value, name) { if (!value) throw new Error(name); }
  const settle = () => new Promise(resolve => setTimeout(resolve, 80));
  const first = document.querySelector('.thumb-wrap');
  const second = document.querySelectorAll('.thumb-wrap')[1];
  history.replaceState(null, '', '?registro=17&foto=' + encodeURIComponent(second.dataset.orig));
  abrirEvidenciaEnlazada();
  await modalImage.decode(); await settle();
  assert(currentModalIndex === 1 && modalImage.src === second.dataset.orig, 'Deep link selects exact photo');
  cerrarModal();
  history.replaceState(null, '', '?foto=' + encodeURIComponent('https://example.invalid/not-allowed.jpg'));
  abrirEvidenciaEnlazada();
  assert(!document.getElementById('foto-modal').classList.contains('open'), 'Unknown URL does not open or load');
  history.replaceState(null, '', location.pathname);
  abrirModalDesdeThumb(first);
  await modalImage.decode(); await settle();
  const original = modalImage.src;
  const fitWidth = modalImage.getBoundingClientRect().width;
  assert(fitWidth > 0, 'Nonblank image');
  assert(getComputedStyle(modalViewport).scrollbarWidth === 'none', 'Image scrollbars hidden');
  assert(document.getElementById('modal-zoom-out').disabled, 'Minimum disabled');
  document.getElementById('modal-zoom-in').click();
  assert(modalZoom === 1.5 && modalImage.width > fitWidth, 'Button enlarges actual pixels');
  modalViewport.dispatchEvent(new WheelEvent('wheel', {deltaY: -100, cancelable: true}));
  assert(modalZoom === 1.75, 'Wheel zoom');
  cambiarZoomModal(99);
  assert(modalZoom === 4 && document.getElementById('modal-zoom-in').disabled, 'Maximum bound');
  assert(modalViewport.scrollWidth > modalViewport.clientWidth, 'Horizontal pan available');
  assert(modalViewport.scrollHeight > modalViewport.clientHeight, 'Vertical pan available');
  modalViewport.scrollLeft = modalViewport.scrollWidth;
  assert(modalViewport.scrollLeft > 0, 'Far image edge reachable');
  modalImage.dispatchEvent(new MouseEvent('dblclick'));
  assert(modalZoom === 1, 'Double click resets');
  modalImage.dispatchEvent(new MouseEvent('dblclick'));
  assert(modalZoom === 2, 'Double click enlarges');
  cambiarFotoModal(1); await modalImage.decode(); await settle();
  assert(currentModalIndex === 1 && modalZoom === 1, 'Next photo resets zoom');
  document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowLeft'}));
  await modalImage.decode(); await settle();
  assert(currentModalIndex === 0 && modalZoom === 1, 'Keyboard navigation preserved');
  cambiarZoomModal(.1);
  assert(modalZoom === 1, 'Minimum bound');
  assert(modalImage.src === original, 'Original URL unchanged');
  const rect = modalImage.getBoundingClientRect();
  assert(Math.abs(rect.width / rect.height - 4 / 3) < .01, 'Aspect ratio preserved');
  for (const element of document.querySelectorAll('.modal-zoom-tools button, .modal-footer')) {
    const box = element.getBoundingClientRect();
    assert(box.left >= 0 && box.right <= innerWidth && box.bottom <= innerHeight, 'Controls within viewport');
  }
  document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}));
  assert(!document.getElementById('foto-modal').classList.contains('open'), 'Escape closes');
  assert(document.body.style.overflow === '', 'Page scrolling restored');
  abrirModalDesdeThumb(first); await modalImage.decode(); await settle();
  assert(modalZoom === 1, 'Reopening resets');
}
checkZoom().then(() => { document.documentElement.dataset.test = 'PASS'; })
  .catch(error => { document.documentElement.dataset.test = 'FAIL: ' + error.message; });
"""


class GalleryZoomBrowserTests(unittest.TestCase):
    def test_desktop_and_mobile(self):
        cached = list((Path.home() / '.cache/ms-playwright').glob('chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'))
        browser = os.environ.get('CHROME_BIN') or shutil.which('chromium') or (str(sorted(cached)[-1]) if cached else None)
        if not browser:
            self.skipTest('Set CHROME_BIN to an installed Chromium; no browser validation performed')
        template = Path(os.environ.get('IQA_GALLERY_TEMPLATE', ROOT / 'web/templates/calidad/galeria.html')).read_text()
        css = template.split('<style>', 1)[1].split('</style>', 1)[0]
        modal = template.split('<div id="foto-modal"', 1)[1].split('<script>', 1)[0]
        javascript = 'let currentModalPhotos = [];' + template.split('let currentModalPhotos = [];', 1)[1].split('</script>', 1)[0]
        image = fixture_image()
        thumbs = '<div class="rc-thumbs">' + ''.join(
            f'<div class="thumb-wrap" data-orig="{image}#{i}" data-num="{i}" data-modelo="MODELO-PRUEBA-123" '
            'data-linea="T01/T03" data-descripcion="Caja danada durante manejo" data-responsable="TSCEM"></div>'
            for i in (1, 2)) + '</div>'
        html = ('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<style>body{margin:0;font-family:sans-serif}.material-symbols-outlined{font-size:10px}' + css + '</style></head><body>'
                + thumbs + '<div id="foto-modal"' + modal + '<script>window.onerror = message => { document.documentElement.dataset.test = "ERROR: " + message; };</script><script>' + javascript + CHECKS + '</script></body></html>')
        for width, height in [(1440, 1000), (900, 650), (390, 844)]:
            with self.subTest(width=width), tempfile.TemporaryDirectory(prefix='iqa-zoom-', dir='/dev/shm') as scratch:
                page = Path(scratch) / 'test.html'
                page.write_text(html)
                artifacts = Path('/dev/shm/iqa-gallery-zoom-results')
                artifacts.mkdir(exist_ok=True)
                result = subprocess.run(['node', str(Path(__file__).with_name('gallery_zoom_browser.mjs')),
                                         browser, scratch + '/profile', page.as_uri(), str(width), str(height), str(artifacts / f'{width}.png')],
                                        capture_output=True, text=True, timeout=25, env={**os.environ, 'TMPDIR': scratch})
                self.assertEqual(result.returncode, 0, result.stderr[-1000:])
                self.assertIn('PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
