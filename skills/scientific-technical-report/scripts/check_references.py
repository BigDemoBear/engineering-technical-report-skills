"""Check numbered citations and reference identifiers; no network or GB/T compliance claim."""
import argparse
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

from report_io import emit_json, mask_literals, read_report

CITATION = re.compile(r'\[(\d+(?:\s*[,，、;；\-–—]\s*\d+)*)\]')
ENTRY = re.compile(r'^\s*\[(\d+)\]\s*(.*)')
DOI = re.compile(r'(?:\bdoi\s*[:：]\s*|https?://(?:dx\.)?doi\.org/)([^\s<>"，。；、《》]+)|\b(10\.\d{4,9}/[^\s<>"，。；、《》]+)', re.I)
TYPE = r'(?:J|M|S|C|D|R|N|P|EB|DB|CP|DS|Z)(?:/OL)?'


def issue(code, location, detail, severity='warning'):
    return {'code': code, 'location': location, 'detail': detail, 'severity': severity}


def normalize_title(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def valid_isbn(raw):
    value = re.sub(r'[\s-]', '', raw).upper()
    if re.fullmatch(r'\d{9}[\dX]', value):
        return sum((10 - i) * (10 if c == 'X' else int(c)) for i, c in enumerate(value)) % 11 == 0
    if re.fullmatch(r'97[89]\d{10}', value):
        return sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0
    return False


def expand_citation(text):
    result = set()
    for item in re.split(r'[,，、;；]', text):
        ends = re.split(r'[-–—]', item)
        values = [int(x.strip()) for x in ends]
        if any(x < 1 for x in values):
            raise ValueError('Citation numbers must be positive.')
        if len(values) == 1:
            result.add(values[0])
        elif len(values) == 2 and values[0] <= values[1] and values[1] - values[0] <= 1000:
            result.update(range(values[0], values[1] + 1))
        else:
            raise ValueError('Invalid or excessively large citation range.')
    return result


def check(blocks):
    issues, entries, body = [], [], []
    masked = mask_literals(blocks)
    in_refs, reference_heading, current = False, None, None
    section_count = 0
    for block, text in zip(blocks, masked):
        if block['part'] != 'body':
            body.append((block, text))
            continue
        heading_text = re.sub(r'^#{1,6}\s*', '', text.strip())
        heading_text = re.sub(r'^\d+(?:\.\d+)*\s+', '', heading_text)
        if re.fullmatch(r'参考文献|References|Bibliography', heading_text, re.I):
            section_count += 1
            in_refs, reference_heading, current = True, block['heading'], None
            continue
        if in_refs and ((block['heading'] and (reference_heading is None or block['heading'] <= reference_heading))
                        or re.match(r'^附录\s*[A-Z一二三四五六七八九十]?', heading_text)):
            in_refs, current = False, None
        if not in_refs:
            body.append((block, text))
            continue
        entry = ENTRY.match(text)
        if entry:
            current = {'number': int(entry[1]), 'text': block['text'][entry.start(2):], 'location': block['locator']}
            entries.append(current)
        elif text.strip() or re.match(r'^\s*https?://', block['text']):
            if current is None:
                issues.append(issue('UNPARSED_REFERENCE_CONTENT', block['locator'],
                                    'No visible [n] entry; inspect automatic numbering/field output or other citation style.'))
            else:
                current['text'] += ' ' + block['text'].strip()
    if section_count > 1:
        issues.append(issue('MULTIPLE_REFERENCE_SECTIONS', 'document', 'Check section scope manually.'))
    numbers = [e['number'] for e in entries]
    known = set(numbers)
    for entry in entries:
        if entry['number'] < 1 or numbers.count(entry['number']) > 1:
            issues.append(issue('DUPLICATE_OR_INVALID_REFERENCE_NUMBER', entry['location'], str(entry['number']), 'error'))
        if not entry['text'].strip():
            issues.append(issue('EMPTY_REFERENCE', entry['location'], str(entry['number']), 'error'))
    if entries and numbers != list(range(1, len(entries) + 1)):
        issues.append(issue('REFERENCE_NUMBER_ORDER', 'references', 'Expected unique [1]...[n] in a complete sequential bibliography.'))
    used, first_use = set(), []
    for block, text in body:
        for match in CITATION.finditer(text):
            if re.search(r'(?:区间|范围|集合|矩阵|数组|向量|索引|下标)\s*$', text[:match.start()]):
                continue
            try:
                cited = expand_citation(match[1])
            except ValueError as exc:
                issues.append(issue('MALFORMED_CITATION_RANGE', block['locator'], str(exc), 'error'))
                continue
            # Canonical numeric order within a grouped citation; repeated references are normal.
            for number in sorted(cited):
                if number not in used:
                    first_use.append(number)
                used.add(number)
                if number not in known:
                    issues.append(issue('CITATION_WITHOUT_REFERENCE', block['locator'], str(number), 'error'))
    for number in sorted(known - used):
        issues.append(issue('REFERENCE_NOT_CITED', 'references', str(number)))
    if first_use and first_use != sorted(first_use):
        issues.append(issue('CITATION_FIRST_USE_ORDER', 'document', 'Check numbering against first appearance.'))
    if not entries:
        issues.append(issue('NO_PARSED_NUMBERED_REFERENCES', 'document',
                            'No visible numbered bibliography parsed; may be inapplicable or require manual field/style inspection.'))

    seen_doi, seen_title = {}, {}
    for entry in entries:
        at, text = entry['location'], entry['text']
        for match in DOI.finditer(text):
            doi = (match[1] or match[2]).rstrip('.,;').casefold()
            if not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
                issues.append(issue('MALFORMED_DOI', at, doi, 'error'))
            elif doi in seen_doi and seen_doi[doi] != entry['number']:
                issues.append(issue('POSSIBLE_DUPLICATE_DOI', at, f"[{seen_doi[doi]}] and [{entry['number']}]: {doi}"))
            else:
                seen_doi[doi] = entry['number']
        for match in re.finditer(r'\bISBN(?:-1[03])?\s*[:：]?\s*([0-9Xx][0-9Xx -]*)', text, re.I):
            if not valid_isbn(match[1].strip()):
                issues.append(issue('INVALID_ISBN_CHECKSUM', at, match[1].strip(), 'error'))
        for match in re.finditer(r'https?://[^\s<>"，。；、《》]*', text, re.I):
            url = match.group().rstrip('.,;)）')
            try:
                parsed = urlsplit(url)
                valid = bool(parsed.hostname) and not re.search(r'\s', parsed.netloc)
                parsed.port  # Also detect malformed port syntax.
            except ValueError:
                valid = False
            if not valid:
                issues.append(issue('MALFORMED_URL', at, url, 'error'))
        # Conservative heuristic for author. title[type]. Ambiguous metadata stays a candidate.
        title = re.search(r'^.+?[.．]\s*(.+?)\[' + TYPE + r'\]', text, re.I)
        if title:
            key = normalize_title(title[1])
            if key and key in seen_title and seen_title[key] != entry['number']:
                issues.append(issue('POSSIBLE_DUPLICATE_TITLE', at,
                                    f"[{seen_title[key]}] and [{entry['number']}]; compare authors, year and edition."))
            elif key:
                seen_title[key] = entry['number']
    return {'status': 'issues' if issues else 'complete', 'issues': issues,
            'references_parsed': len(entries), 'citation_numbers_used': sorted(used),
            'scope': 'Visible bracketed sequential citations and identifier syntax only; no resolution, source-truth, full metadata or GB/T 7714 compliance check.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    args = parser.parse_args()
    try:
        blocks, notes = read_report(args.manuscript)
        result = check(blocks)
        result['notes'] = notes + ['Numeric brackets can be non-citation notation; review contexts. No global author/title/year/issue/pages/DOI requirement is imposed.']
    except (OSError, ValueError, KeyError, TypeError, OverflowError, zipfile.BadZipFile, ET.ParseError) as exc:
        emit_json({'status': 'input-error', 'error': str(exc)})
        return 2
    emit_json(result)
    return 1 if any(i['severity'] == 'error' for i in result['issues']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
