"""Expose heading/list evidence and conservative structural candidates, not final judgments."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
PREFIX = re.compile(r'^(\[\d+\]|[（(][\d一二三四五六七八九十]+[）)]|\d+[）)]|[①-⑳]|[一二三四五六七八九十]+[、.．]?|\d+(?:\.\d+)*(?:[.．、。])?)')


def child_value(node, path):
    value = node.find(path) if node is not None else None
    return value.get(W+'val') if value is not None else None


def visible(node):
    if node.tag in {W+'del', W+'moveFrom', W+'instrText'}:
        return ''
    if node.tag == W+'t':
        return node.text or ''
    return ''.join(visible(c) for c in node)


def inspect(path, heading_mode='decimal'):
    path = Path(path)
    records, definitions = [], {}
    if path.suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as package:
            styles = {}
            if 'word/styles.xml' in package.namelist():
                root = ET.fromstring(package.read('word/styles.xml'))
                styles = {x.get(W+'styleId'): x for x in root.findall(W+'style')}
            default_style = next((k for k,v in styles.items() if v.get(W+'default') == '1' and v.get(W+'type') == 'paragraph'), None)

            def style_property(style_id, path):
                visited = set()
                while style_id in styles:
                    if style_id in visited:
                        raise ValueError('cyclic style inheritance')
                    visited.add(style_id)
                    node = styles[style_id]
                    value = child_value(node, path)
                    if value is not None:
                        return value
                    style_id = child_value(node, W+'basedOn')
                return None

            if 'word/numbering.xml' in package.namelist():
                nr = ET.fromstring(package.read('word/numbering.xml'))
                abstracts = {x.get(W+'abstractNumId'): x for x in nr.findall(W+'abstractNum')}
                for num in nr.findall(W+'num'):
                    aid = child_value(num, W+'abstractNumId')
                    abstract = abstracts.get(aid)
                    levels = {}
                    if abstract is not None:
                        for lvl in abstract.findall(W+'lvl'):
                            levels[lvl.get(W+'ilvl')] = {key: child_value(lvl, W+key) for key in ['numFmt', 'lvlText', 'start', 'pStyle']}
                    definitions[num.get(W+'numId')] = {'abstractNumId': aid, 'levels': levels,
                        'overrides_present': bool(num.findall(W+'lvlOverride')),
                        'linked_style': child_value(abstract, W+'numStyleLink')}
            root = ET.fromstring(package.read('word/document.xml'))
            body = root.find(W+'body')
            for i, paragraph in enumerate(body.iter(W+'p'), 1):
                text = visible(paragraph).strip()
                if not text:
                    continue
                sid = child_value(paragraph, W+'pPr/'+W+'pStyle') or default_style
                prop = lambda p: child_value(paragraph, W+'pPr/'+p) or style_property(sid, W+'pPr/'+p)
                outline = prop(W+'outlineLvl')
                level = int(outline)+1 if outline is not None and outline.isdigit() and int(outline) < 9 else None
                nid, ilvl = prop(W+'numPr/'+W+'numId'), prop(W+'numPr/'+W+'ilvl')
                numbering = None
                if nid not in {None, '0'}:
                    definition = definitions.get(nid, {})
                    numbering = {'numId': nid, 'ilvl': ilvl,
                                 'level_definition': definition.get('levels', {}).get(ilvl or '0'),
                                 'overrides_present': definition.get('overrides_present'),
                                 'linked_style': definition.get('linked_style')}
                records.append({'location': {'paragraph': i}, 'text': text, 'style': sid,
                                'heading_level': level, 'automatic': numbering})
    elif path.suffix.lower() in {'.md', '.txt'}:
        fence = None
        frontmatter = False
        for i, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if i == 1 and line.strip() == '---':
                frontmatter = True
                continue
            if frontmatter:
                if line.strip() == '---':
                    frontmatter = False
                continue
            marker = re.match(r'^\s*(`{3,}|~{3,})', line)
            if fence:
                if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1]:
                    fence = None
                continue
            if marker:
                fence = (marker[1][0], len(marker[1]))
                continue
            md = re.match(r'^(#{1,6})\s+(.*)', line)
            records.append({'location': {'line': i}, 'text': md[2] if md else line.strip(),
                            'style': None, 'heading_level': len(md[1]) if md else None, 'automatic': None})
    else:
        raise ValueError('numbering inspection supports DOCX, Markdown and UTF-8 text')
    headings, items, candidates = [], [], []
    parent, in_references = {}, False

    def add(record, message):
        candidates.append({'rule': 'N01', 'kind': 'structural_candidate',
                           'location': record['location'], 'original': record['text'],
                           'context': record['text'], 'suggestion': message})

    for record in records:
        text, level, automatic = record['text'], record['heading_level'], record['automatic']
        if re.fullmatch(r'(?:\d+(?:\.\d+)*\s+)?(?:参考文献|资料来源|References|Bibliography)', text, re.I):
            in_references = True
            continue
        if in_references:
            if text.startswith('附录') or level:
                in_references = False
            else:
                continue
        marker = PREFIX.match(text)
        if not level and not automatic and not marker:
            continue
        record['typed_marker'] = marker[0] if marker else None
        if level:
            headings.append(record)
            if automatic:
                if marker:
                    add(record, '标题同时存在自动编号和疑似手工前缀，核对渲染是否重复；型号/数字标题可能合法。')
                definition = automatic['level_definition']
                expected = '.'.join('%'+str(i) for i in range(1, level+1))
                if heading_mode == 'decimal' and definition and definition['lvlText'] != expected:
                    add(record, f'所选十进制标题口径预期 {expected}；实际编号定义 {definition["lvlText"]}，先核对模板。')
                continue
            if heading_mode == 'decimal' and marker:
                token = marker[0]
                if not re.fullmatch(r'\d+(?:\.\d+)*', token) or len(token.split('.')) != level:
                    add(record, f'这是第{level}级标题，但前缀 {token} 不符合所选 1/1.1/1.1.1 层级；结合完整标题树判定，不能当文献号或普通列项自动改。')
                else:
                    components = token.split('.')
                    if level > 1 and parent.get(level-1) != '.'.join(components[:-1]):
                        add(record, '手工标题的父级不在当前标题树中；核对缺号、摘录范围及父子关系。')
                    parent[level] = token
                    for old in list(parent):
                        if old > level:
                            parent.pop(old)
        else:
            items.append(record)
    return {'heading_mode': heading_mode, 'headings': headings, 'items': items,
            'candidate_count': len(candidates), 'candidates': candidates,
            'render_review_required': any(r['automatic'] for r in headings+items),
            'scope': 'Style/outline/manual-marker evidence and selected heading-convention candidates; automatic displayed counters, list-group semantics and image text require separate review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--heading-mode', choices=['decimal', 'template'], default='decimal')
    args = parser.parse_args()
    try:
        result = inspect(args.input, args.heading_mode)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(json.dumps({'status': 'input_error', 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
