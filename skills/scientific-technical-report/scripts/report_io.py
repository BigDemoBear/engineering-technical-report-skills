"""Read-only input shared by the report checkers; no rendering or field updates."""
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'


def unique_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique_json_keys)


def emit_json(value):
    # JSON output is UTF-8 even when Windows starts Python with a legacy code page.
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False, indent=2))


def visible_text(node):
    if node.tag in {W + 'del', W + 'moveFrom', W + 'instrText'}:
        return ''
    if node.tag == M + 'oMath':
        return '〖公式：另查〗'
    if node.tag == W + 'drawing':
        return '〖图像：另查〗'
    if node.tag == W + 't':
        return node.text or ''
    if node.tag in {W + 'tab', W + 'br', W + 'cr'}:
        return ' '
    return ''.join(visible_text(child) for child in node)


def read_report(path):
    """Return located blocks, including table cells and auxiliary DOCX parts."""
    path = Path(path)
    if path.suffix.lower() in {'.txt', '.md'}:
        blocks = []
        for i, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            heading = re.match(r'^(#{1,6})\s+', line)
            blocks.append({'locator': f'line:{i}', 'text': line,
                           'heading': len(heading[1]) if heading else None, 'part': 'body'})
        return blocks, ['Source-text inspection only; no rendered layout check.']
    if path.suffix.lower() != '.docx':
        raise ValueError('Expected UTF-8 .md/.txt or .docx; PDF requires separate reading/OCR.')
    blocks, notes = [], []
    with zipfile.ZipFile(path) as package:
        styles = {}
        if 'word/styles.xml' in package.namelist():
            for style in ET.fromstring(package.read('word/styles.xml')).iter(W + 'style'):
                outline = style.find('./' + W + 'pPr/' + W + 'outlineLvl')
                if outline is not None and outline.get(W + 'val', '').isdigit():
                    styles[style.get(W + 'styleId')] = int(outline.get(W + 'val')) + 1
        parts = ['word/document.xml'] + sorted(
            n for n in package.namelist()
            if re.fullmatch(r'word/(?:header\d+|footer\d+|footnotes|endnotes)\.xml', n))
        for part in parts:
            tree = ET.fromstring(package.read(part))
            # Text boxes have nested paragraphs; include their text exactly once.
            parents = {child: node for node in tree.iter() for child in node}
            for index, p in enumerate(tree.iter(W + 'p'), 1):
                ancestor = parents.get(p)
                excluded = False
                while ancestor is not None:
                    if ancestor.tag in {W + 'p', W + 'del', W + 'moveFrom'}:
                        excluded = True
                        break
                    if ancestor.tag in {W + 'footnote', W + 'endnote'} and int(ancestor.get(W + 'id', '0')) <= 0:
                        excluded = True
                        break
                    ancestor = parents.get(ancestor)
                if excluded:
                    continue
                pstyle = p.find('./' + W + 'pPr/' + W + 'pStyle')
                style_id = pstyle.get(W + 'val') if pstyle is not None else None
                outline = p.find('./' + W + 'pPr/' + W + 'outlineLvl')
                level = styles.get(style_id)
                if outline is not None and outline.get(W + 'val', '').isdigit():
                    level = int(outline.get(W + 'val')) + 1
                blocks.append({'locator': f'paragraph:{index}' if part.endswith('/document.xml')
                               else f'{Path(part).stem}:paragraph:{index}',
                               'text': visible_text(p), 'heading': level,
                               'part': 'body' if part.endswith('/document.xml') else Path(part).stem})
        notes.append('DOCX locators are XML paragraph positions, including table cells, not page numbers.')
        notes.append('Includes saved field results and auxiliary parts; does not update fields, resolve automatic/style-inherited numbering or render layout.')
        notes.append('Formulas, images, unbracketed superscript citations, field freshness and actual numbering require separate review; deleted revisions are excluded.')
    return blocks, notes


def mask_literals(blocks):
    """Keep offsets while masking Markdown code, math, links and literal paths."""
    def blank(match):
        return ''.join('\n' if c == '\n' else ' ' for c in match.group())
    text = '\n'.join(b['text'] for b in blocks)
    lines = text.split('\n')
    fence = None
    for i, line in enumerate(lines):
        mark = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            lines[i] = ' ' * len(line)
            if mark and mark[1][0] == fence[0] and len(mark[1]) >= fence[1] and not line[mark.end():].strip():
                fence = None
        elif mark:
            fence = (mark[1][0], len(mark[1]))
            lines[i] = ' ' * len(line)
    text = '\n'.join(lines)
    for pattern in [r'(`+)[^\n]*?\1', r'\$\$[\s\S]*?\$\$', r'\\\[[\s\S]*?\\\]',
                    r'(?<!\\)\$[^$\n]+(?<!\\)\$', r'\\\([^\n]*?\\\)',
                    r'https?://[^\s<>，。；、]+', r'\]\([^\n)]*\)', r'\b[A-Za-z]:[\\/][^\s]+']:
        text = re.sub(pattern, blank, text)
    return text.split('\n')
