"""Navigation contract checks without production services or Django writes."""
import ast
from pathlib import Path
from types import SimpleNamespace
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OperationGalleryLinkTests(unittest.TestCase):
    def test_thumbnail_targets_gallery_and_keeps_source_record(self):
        source = (ROOT / 'web/static/js/panel_operativo.js').read_text()
        start = source.index('const galleryUrl = ')
        end = source.index('\n                });', start)
        script = """
const assert = require('node:assert/strict');
const f = {registro_id: 42, url: '/media-protegida/usuario/a & b.jpg', thumb_url: '/thumbs/a.jpg'};
let fotosBadge = '';
""" + source[start:end] + """
const href = fotosBadge.match(/href="([^"]+)"/)[1];
const link = new URL(href, 'https://example.invalid');
assert.equal(link.pathname, '/fotos/');
assert.equal(link.searchParams.get('registro'), '42');
assert.equal(link.searchParams.get('foto'), f.url);
assert.ok(!href.startsWith('/media-protegida/'));
"""
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)

    def test_record_filter_narrows_allowed_queryset(self):
        tree = ast.parse((ROOT / 'web/calidad/views.py').read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_build_galeria_queryset')
        start = next(i for i, node in enumerate(function.body) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'registro_id' for t in node.targets))
        block = compile(ast.Module(body=function.body[start:start + 2], type_ignores=[]), '<record-filter>', 'exec')

        class AllowedQueryset:
            def __init__(self):
                self.ids = {42}

            def filter(self, *, pk):
                self.ids &= {pk}
                return self

            def none(self):
                self.ids = set()
                return self

        for value, expected in [('42', {42}), ('99', set()), ('bad', set()), ('', set()), ('9' * 100, set()), ('\u00b2', set()), (None, {42})]:
            with self.subTest(value=value):
                allowed = AllowedQueryset()
                context = {'request': SimpleNamespace(GET={} if value is None else {'registro': value}), 'registros_qs': allowed}
                exec(block, context)
                self.assertEqual(context['registros_qs'].ids, expected)


if __name__ == '__main__':
    unittest.main()
