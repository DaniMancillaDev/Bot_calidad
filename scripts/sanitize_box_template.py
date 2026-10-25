"""Sanitize the reviewed PROD workbook without round-tripping its drawing objects."""
import argparse
import hashlib
import io
import re
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

SOURCE_SHA256 = '10c9072b071759e130544f095d762ac61bb9dbccf2ff4dee18dd75145f14cf6a'
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def sanitized_bytes(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unreviewed workbook: inspect and classify it before sanitizing')
    with ZipFile(io.BytesIO(source)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    original_parts = dict(parts)

    def xml(tree, name):
        namespaces = dict(item for _, item in ET.iterparse(io.BytesIO(original_parts[name]), events=['start-ns']))
        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)
        result = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        for prefix in tree.get('{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable', '').split():
            if f'xmlns:{prefix}='.encode() not in result:
                tree.set(f'xmlns:{prefix}', namespaces[prefix])
        return ET.tostring(tree, encoding='utf-8', xml_declaration=True)
    removed = {name for name in parts if name.startswith('customXml/') or name.startswith('xl/media/')}
    removed.update({
        'docProps/custom.xml', 'xl/comments1.xml', 'xl/drawings/vmlDrawing1.vml',
        'xl/drawings/drawing1.xml', 'xl/drawings/_rels/drawing1.xml.rels',
    })
    used_strings = set()
    for name in [name for name in parts if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name)]:
        tree = ET.fromstring(parts[name])
        # Reviewed sample records: row 3+ on the first sheet, row 2+ on Gantt.
        first_sample = {'xl/worksheets/sheet1.xml': 3, 'xl/worksheets/sheet2.xml': 2}.get(name)
        for cell in tree.findall(f'.//{{{MAIN}}}c'):
            row = int(re.search(r'\d+', cell.get('r')).group())
            if first_sample is not None and row >= first_sample:
                for child in list(cell):
                    if child.tag in (f'{{{MAIN}}}v', f'{{{MAIN}}}is', f'{{{MAIN}}}f'):
                        cell.remove(child)
                cell.attrib.pop('t', None)
            if cell.get('t') == 's':
                used_strings.add(int(cell.find(f'{{{MAIN}}}v').text))
        if name.endswith('sheet1.xml'):
            for child in list(tree):
                if child.tag in (f'{{{MAIN}}}drawing', f'{{{MAIN}}}legacyDrawing'):
                    tree.remove(child)
        parts[name] = xml(tree, name)
    strings = ET.fromstring(parts['xl/sharedStrings.xml'])
    old_strings = list(strings)
    mapping = {old: new for new, old in enumerate(sorted(used_strings))}
    for child in list(strings):
        strings.remove(child)
    for old in sorted(used_strings):
        strings.append(deepcopy(old_strings[old]))
    strings.set('uniqueCount', str(len(mapping)))
    references = 0
    for name in [name for name in parts if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name)]:
        tree = ET.fromstring(parts[name])
        for cell in tree.findall(f'.//{{{MAIN}}}c'):
            if cell.get('t') == 's':
                value = cell.find(f'{{{MAIN}}}v')
                value.text = str(mapping[int(value.text)])
                references += 1
        parts[name] = xml(tree, name)
    strings.set('count', str(references))
    parts['xl/sharedStrings.xml'] = xml(strings, 'xl/sharedStrings.xml')
    for name in [name for name in parts if name.endswith('.rels') and name not in removed]:
        tree = ET.fromstring(parts[name])
        for relation in list(tree):
            kind = relation.get('Type').rsplit('/', 1)[-1]
            if kind in ('comments', 'vmlDrawing', 'customXml', 'custom-properties') or (
                name == 'xl/worksheets/_rels/sheet1.xml.rels' and kind == 'drawing'
            ):
                tree.remove(relation)
            elif relation.get('Target', '').endswith(('drawing2.xml', 'drawing3.xml')):
                relation.set('Target', relation.get('Target').replace('/drawing2.xml', '/templateDrawing2.xml').replace('/drawing3.xml', '/templateDrawing3.xml'))
        parts[name] = xml(tree, name)
    content_types = ET.fromstring(parts['[Content_Types].xml'])
    for element in list(content_types):
        name = element.get('PartName', '').lstrip('/')
        if name in removed:
            content_types.remove(element)
        elif name in ('xl/drawings/drawing2.xml', 'xl/drawings/drawing3.xml'):
            element.set('PartName', '/' + name.replace('/drawing2.xml', '/templateDrawing2.xml').replace('/drawing3.xml', '/templateDrawing3.xml'))
    parts['[Content_Types].xml'] = xml(content_types, '[Content_Types].xml')
    for name in ('docProps/core.xml', 'docProps/app.xml'):
        tree = ET.fromstring(parts[name])
        for child in list(tree):
            if child.tag.rsplit('}', 1)[-1] in (
                'creator', 'lastModifiedBy', 'Company', 'Manager', 'title', 'subject',
                'description', 'keywords', 'category', 'contentStatus', 'identifier',
            ):
                tree.remove(child)
        parts[name] = xml(tree, name)
    output = io.BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            if name not in removed:
                if name in ('xl/drawings/drawing2.xml', 'xl/drawings/drawing3.xml'):
                    name = name.replace('/drawing2.xml', '/templateDrawing2.xml').replace('/drawing3.xml', '/templateDrawing3.xml')
                archive.writestr(name, content)
    return output.getvalue()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('xb') as output:
        output.write(sanitized_bytes(args.source.read_bytes()))
