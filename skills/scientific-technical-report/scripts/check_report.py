"""Check located manuscript residue and declared numeric occurrences, without edits."""
import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

from audit_evidence import audit
from report_io import emit_json, mask_literals, read_json, read_report

EXPLICIT = re.compile(r'\[\[\s*(?:TODO|TBD|待补|待定)[^\n]*?(?:\]\]|$)|【(?:待补|待定|此处插入)[^】\n]*】|<(?:待补|此处插入)[^>\n]*>', re.I)
POSSIBLE = re.compile(r'\b(?:TODO|TBD|TK|X{2,})\b|\?{3,}|待补|待定|此处插入|[（(]略[）)]')
STRONG = re.compile(r'证明|首次|最优|完全|无局限|无任何局限')
# Within each family, factors map to the stated base unit. Percent and pp stay separate.
UNITS = {
    's': ('time', '1'), 'ms': ('time', '.001'), 'us': ('time', '.000001'),
    'μs': ('time', '.000001'), 'µs': ('time', '.000001'),
    'V': ('voltage', '1'), 'kV': ('voltage', '1000'), 'mV': ('voltage', '.001'),
    'A': ('current', '1'), 'kA': ('current', '1000'), 'mA': ('current', '.001'),
    'Hz': ('frequency', '1'), 'kHz': ('frequency', '1000'),
    'W': ('power', '1'), 'kW': ('power', '1000'), 'MW': ('power', '1000000'),
    '%': ('percent', '1'), '百分比': ('percent', '1'),
    'pp': ('percentage-point', '1'), '百分点': ('percentage-point', '1'),
}


def finding(code, locator, detail, severity='warning'):
    return {'code': code, 'location': locator, 'severity': severity, 'detail': detail}


def lint_blocks(blocks, final=False):
    issues = []
    if not any(b['text'].strip() for b in blocks):
        issues.append(finding('EMPTY_MANUSCRIPT', 'document', 'No visible manuscript text.', 'error'))
    masked = mask_literals(blocks)
    for index, (block, text) in enumerate(zip(blocks, masked)):
        at = block['locator']
        explicit = list(EXPLICIT.finditer(text))
        for match in explicit:
            # Quoted examples may discuss a marker rather than contain unfinished work.
            prefix, suffix = text[:match.start()], text[match.end():]
            quoted = ((prefix.count('“') > prefix.count('”') and '”' in suffix)
                      or (prefix.count('‘') > prefix.count('’') and '’' in suffix)
                      or any(prefix.count(q) % 2 and q in suffix for q in ('"', "'")))
            severity = 'error' if final and not quoted else 'warning'
            issues.append(finding('EXPLICIT_PLACEHOLDER', at, match.group(), severity))
        for match in POSSIBLE.finditer(text):
            if not any(a.start() <= match.start() < a.end() for a in explicit):
                issues.append(finding('POSSIBLE_RESIDUE', at, match.group()))
        for match in STRONG.finditer(text):
            issues.append(finding('ASSERTION_REVIEW', at, match.group()))
        if re.search(r'(?:图|表)\s*\d+(?:[-—.]\d+)?\s*(?:[：:]?\s*)(?:待补|【待补[^】]*】|\?{3,})\s*$', text):
            issues.append(finding('INCOMPLETE_CAPTION', at, text.strip()))
        if block['heading']:
            following = next((b for b in blocks[index + 1:]
                              if b['part'] == block['part'] and b['text'].strip()), None)
            if following is None or (following['heading'] and following['heading'] <= block['heading']):
                issues.append(finding('EMPTY_SECTION', at, block['text']))
    return issues


def decimal_text(value):
    if len(value) > 200 or not re.fullmatch(r'[+−-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+−-]?\d+)?', value):
        raise ValueError('value_text must be one signed decimal/scientific numeric token')
    number = Decimal(value.replace('−', '-'))
    if not number.is_finite() or abs(number.as_tuple().exponent) > 1000:
        raise ValueError('value_text is outside supported finite display precision')
    return number


def numeric_occurrences(blocks, ledger, final=False):
    issues, checked = [], 0
    validation = audit(ledger, final)
    for message in validation['errors']:
        issues.append(finding('LEDGER_ERROR', 'ledger', message, 'error'))
    for message in validation['warnings']:
        issues.append(finding('LEDGER_WARNING', 'ledger', message))
    located = {b['locator']: b for b in blocks}
    for index, number in enumerate(ledger['numbers']):
        occurrences = number.get('occurrences', [])
        if not occurrences:
            issues.append(finding('UNLOCATED_NUMBER', f'numbers[{index}]',
                                  f"{number['key']}/{number['condition']}: no manuscript occurrences supplied",
                                  'error' if final else 'warning'))
        for occurrence in occurrences:
            at = occurrence['locator']
            block = located.get(at)
            quote = occurrence['quote']
            if block is None or block['text'].count(quote) != 1:
                issues.append(finding('STALE_NUMBER_LOCATION', at, 'Exact quote must occur once at the declared location.', 'error'))
                continue
            token, unit = occurrence['value_text'], occurrence['unit']
            displayed = decimal_text(token)
            # Chinese prose may touch digits; prevent matches inside other numeric tokens.
            pattern = r'(?<![0-9A-Za-z_.+−-])' + re.escape(token) + r'\s*' + re.escape(unit) + r'(?![A-Za-z%])'
            if len(re.findall(pattern, quote)) != 1:
                issues.append(finding('NUMBER_TOKEN_NOT_UNIQUE', at, f'{token} {unit} must appear once in the quote.', 'error'))
                continue
            family, factor = UNITS.get(unit, (unit, '1'))
            expected_family, expected_factor = UNITS.get(number['unit'], (number['unit'], '1'))
            if family != expected_family:
                issues.append(finding('DISPLAY_UNIT_MISMATCH', at, f"{unit} versus ledger {number['unit']}", 'error'))
                continue
            factor, expected_factor = Decimal(factor), Decimal(expected_factor)
            expected = Decimal(str(number['value'])) * expected_factor
            # Half the last displayed digit permits rounding, not arbitrary scientific error.
            tolerance = Decimal('0.5').scaleb(displayed.as_tuple().exponent) * factor
            if abs(displayed * factor - expected) > tolerance:
                issues.append(finding('DISPLAY_VALUE_MISMATCH', at,
                                      f"{token} {unit} versus ledger {number['value']} {number['unit']}", 'error'))
            checked += 1
    return issues, checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    try:
        blocks, notes = read_report(args.manuscript)
        issues = lint_blocks(blocks, args.final)
        checked = 0
        if args.ledger:
            additional, checked = numeric_occurrences(blocks, read_json(args.ledger), args.final)
            issues.extend(additional)
        errors = sum(i['severity'] == 'error' for i in issues)
        result = {'status': 'issues' if issues else 'complete', 'issues': issues,
                  'numeric_occurrences_checked': checked, 'block_count': len(blocks), 'notes': notes,
                  'scope': 'Residue candidates and explicitly located numeric displays only; unlisted occurrences, source truth, semantics and layout are not verified.'}
    except (OSError, ValueError, KeyError, TypeError, OverflowError, InvalidOperation, zipfile.BadZipFile, ET.ParseError) as exc:
        emit_json({'status': 'input-error', 'error': str(exc)})
        return 2
    emit_json(result)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
