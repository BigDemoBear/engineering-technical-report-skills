"""Read-only DOCX checks for mapped paragraph roles; not semantic or visual acceptance."""
import argparse
from pathlib import Path
import re

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from build_template import ALIGN, load_profile
from report_io import emit_json


def inherited(style, attribute, paragraph=False):
    while style is not None:
        value = getattr(style.paragraph_format if paragraph else style.font, attribute)
        if value is not None:
            return value
        style = style.base_style
    return None


def font_value(run, paragraph, attr):
    value = getattr(run.font, attr)
    if value is None and run.style and run.style.style_id != 'DefaultParagraphFont':
        value = inherited(run.style, attr)
    return inherited(paragraph.style, attr) if value is None else value


def east_asia(run, paragraph):
    nodes = [run._r.rPr]
    for initial in [run.style, paragraph.style]:
        style = initial
        while style is not None:
            nodes.append(style.element.rPr)
            style = style.base_style
    for node in nodes:
        if node is not None:
            rf = node.find(qn('w:rFonts'))
            if rf is not None and rf.get(qn('w:eastAsia')):
                return rf.get(qn('w:eastAsia'))
    return None


def audit(path, profile):
    doc = Document(path)
    issues, checked, unmapped = [], 0, []

    def issue(code, location, detail, severity='error'):
        issues.append({'code': code, 'location': location, 'severity': severity, 'detail': detail})

    for i, section in enumerate(doc.sections, 1):
        for attr, expected in [('page_width', profile['page']['width_mm']), ('page_height', profile['page']['height_mm'])] + [(x+'_margin', profile['page']['margin_mm']) for x in ['top', 'bottom', 'left', 'right']]:
            actual = getattr(section, attr)
            if actual is None or abs(actual.mm - expected) > 0.1:
                issue('PAGE_PARAMETER', f'section:{i}', f'{attr}: expected {expected} mm; actual {actual.mm if actual else None}')
        if section._sectPr.find(qn('w:docGrid')) is not None:
            issue('GRID_REVIEW', f'section:{i}', 'Check document grid and paragraph snapToGrid against actual line spacing.', 'warning')
    package = doc.part.package
    for part in package.parts:
        name = str(part.partname)
        if name.startswith('/word/header') and not profile['page']['header']:
            issue('HEADER_REVIEW', name, 'Default forbids headers; check referenced content and remove only within authorized formatting scope.', 'warning')
        if hasattr(part, 'element') and not profile['page']['page_numbers']:
            fields = [n.text or '' for n in part.element.iter(qn('w:instrText'))]
            fields += [n.get(qn('w:instr'), '') for n in part.element.iter(qn('w:fldSimple'))]
            if any(re.search(r'\b(?:PAGE|NUMPAGES)\b', text, re.I) for text in fields):
                issue('PAGE_FIELD', name, 'Profile has no page numbers, but PAGE/NUMPAGES field exists.')
    for i, node in enumerate(doc.element.body.iter(qn('w:p')), 1):
        p = Paragraph(node, doc)
        if not p.text.strip():
            continue
        location = f'paragraph:{i}'
        role = p.style.name
        ancestors, parent = [], node.getparent()
        while parent is not None:
            ancestors.append(parent)
            parent = parent.getparent()
        row = next((x for x in ancestors if x.tag == qn('w:tr')), None)
        if row is not None and role == 'Normal':
            role = 'Report Table Header' if row.find('./'+qn('w:trPr')+'/'+qn('w:tblHeader')) is not None else 'Report Table Text'
        if role == 'Normal' and re.match(r'^(?:图|表)\s*\d+', p.text):
            issue('ROLE_REVIEW', location, 'May be caption or prose reference; map semantic role before applying style.', 'warning')
            unmapped.append(location)
            continue
        if role not in profile['styles']:
            unmapped.append(f'{location}:{role}')
            continue
        spec = profile['styles'][role]
        checked += 1
        if role == 'Title':
            style = p.style
            border = p._p.find('./'+qn('w:pPr')+'/'+qn('w:pBdr'))
            while border is None and style is not None:
                border = style.element.find('./'+qn('w:pPr')+'/'+qn('w:pBdr'))
                style = style.base_style
            if border is not None:
                issue('TITLE_BORDER', location, 'Plain default title must not inherit a decorative border.')
        mismatches = []
        for attr, expected in [('line_spacing', spec['line']), ('space_before', spec['before_pt']), ('space_after', spec['after_pt']), ('first_line_indent', spec['first_line_pt']), ('left_indent', spec['left_pt']), ('alignment', ALIGN[spec['alignment']]), ('keep_with_next', spec['keep_next'])]:
            actual = getattr(p.paragraph_format, attr)
            actual = inherited(p.style, attr, paragraph=True) if actual is None else actual
            if actual is not None and hasattr(actual, 'pt'):
                actual = actual.pt
            if actual is None:
                # Absent indents/spacing/keepNext have zero/false OOXML defaults.
                actual = {'space_before': 0, 'space_after': 0, 'first_line_indent': 0, 'left_indent': 0, 'keep_with_next': False}.get(attr)
            if actual is None or abs(float(actual) - float(expected)) > 0.05:
                mismatches.append(f'{attr}={actual}, expected={expected}')
        if p.paragraph_format.line_spacing_rule is not None and int(p.paragraph_format.line_spacing_rule) in (3, 4):
            mismatches.append('fixed/minimum line spacing needs explicit review')
        runs = [r for r in p.runs if r.text.strip()]
        for j, run in enumerate(runs, 1):
            size = font_value(run, p, 'size')
            if size is None or abs(size.pt-spec['size_pt']) > 0.05:
                mismatches.append(f'run:{j} size={size.pt if size else None}, expected={spec["size_pt"]}')
            if re.search(r'[\u3400-\u9fff]', run.text):
                font = east_asia(run, p)
                expected = profile['fonts']['heading' if spec['font_role'] == 'heading' else 'east_asia']
                if font != expected:
                    mismatches.append(f'run:{j} eastAsia={font}, expected={expected}')
            if re.search(r'[A-Za-z0-9]', run.text) and font_value(run, p, 'name') != profile['fonts']['latin']:
                mismatches.append(f'run:{j} Latin font differs from profile; math may need exception')
        if mismatches:
            issue('FORMAT_PARAMETER', location, '; '.join(mismatches))
        if runs:
            weights = [font_value(r, p, 'bold') is True for r in runs]
            if all(weights) != spec['bold'] or (spec['bold'] and not all(weights)):
                issue('WEIGHT_REVIEW', location, f'{role}: paragraph weight differs; preserve valid local emphasis/math, review prose after item lead.', 'warning')
            if re.match(r'^[（(]\d+[）)]', p.text) and all(weights):
                issue('ITEM_ALL_BOLD', location, p.text[:160], 'warning')
    return {'status': 'issues' if issues else 'no_mechanical_issues', 'profile': profile['id'],
            'input': str(path), 'mapped_paragraphs_checked': checked, 'unmapped_paragraphs': unmapped,
            'issues': issues, 'scope': 'Mapped body/table paragraph font and spacing, page geometry and field presence only.',
            'not_checked': ['Unmapped roles and docDefaults/theme/table-style cascades beyond resolved paragraph/run properties',
                            'List and caption semantics; numbering actual display; symbol italic/roman; bibliography correctness',
                            'Table border geometry/cell widths/pagination; image contents; text boxes/notes; rendered appearance']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--profile', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.input, load_profile(args.profile))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        emit_json({'status': 'input_error', 'error': str(exc)})
        return 2
    emit_json(result)
    return 1 if any(x['severity'] == 'error' for x in result['issues']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
