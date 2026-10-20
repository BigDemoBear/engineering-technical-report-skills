"""Read-only checks of a technical-report evidence ledger; not manuscript verification.

Numeric grouping is adapted from K-Dense scientific-writing/check_consistency.py.
See ../THIRD_PARTY_NOTICES.md and ../licenses/K-Dense-MIT.txt.
"""
import argparse
import math
from pathlib import Path
from report_io import emit_json, read_json


def required_text(record, field, where):
    value = record[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}.{field} must be non-empty text")
    return value


def fields(record, required, optional, where, warnings):
    if not isinstance(record, dict):
        raise ValueError(f"{where} must be an object")
    missing = required - record.keys()
    if missing:
        raise ValueError(f"{where}: missing fields: {', '.join(sorted(missing))}")
    for key in sorted(record.keys() - required - optional - {'extensions'}):
        warnings.append(f"UNKNOWN_FIELD:{where}.{key}")
    if 'extensions' in record and not isinstance(record['extensions'], dict):
        raise ValueError(f"{where}.extensions must be an object")


def validate_schema(data, warnings):
    fields(data, {'sources', 'claims', 'numbers'}, {'schema_version'}, 'root', warnings)
    if 'schema_version' not in data:
        warnings.append('LEGACY_SCHEMA:unversioned ledger; interpreted as 1.0')
    elif data['schema_version'] != '1.0':
        raise ValueError('root.schema_version: supported version is 1.0')
    schemas = {
        'sources': ({'id', 'location', 'locator', 'verification'}, set()),
        'claims': ({'id', 'text', 'source_ids', 'section', 'status'}, set()),
        'numbers': ({'key', 'condition', 'section', 'value', 'unit', 'source_ids'}, {'occurrences'}),
    }
    for group, (required, optional) in schemas.items():
        if not isinstance(data[group], list):
            raise ValueError(f'{group} must be an array')
        for i, record in enumerate(data[group]):
            where = f'{group}[{i}]'
            fields(record, required, optional, where, warnings)
            if group == 'numbers' and 'occurrences' in record:
                if not isinstance(record['occurrences'], list):
                    raise ValueError(f'{where}.occurrences must be an array')
                for j, occurrence in enumerate(record['occurrences']):
                    at = f'{where}.occurrences[{j}]'
                    fields(occurrence, {'locator', 'quote', 'value_text', 'unit'}, set(), at, warnings)
                    for key in ('locator', 'quote', 'value_text', 'unit'):
                        required_text(occurrence, key, at)
    # Only explicit markers are structural placeholders; ordinary Chinese words are not.
    def explicit_placeholder(value, where):
        if isinstance(value, str) and (value.strip().upper() in {'TODO', 'TBD', 'TK', 'XXXX', '????'}
                                      or value.strip().startswith(('[[TODO', '【待补', '【待定'))):
            raise ValueError(f'{where}: unresolved explicit placeholder')
    for group in schemas:
        for i, record in enumerate(data[group]):
            for key, value in record.items():
                # Quotes intentionally mirror manuscripts; the content checker locates them.
                if key not in {'extensions', 'occurrences'}:
                    explicit_placeholder(value, f'{group}[{i}].{key}')


def audit(data, final=False):
    errors, warnings = [], []
    sources, ids, repeated = {}, set(), {}
    validate_schema(data, warnings)
    if not data["sources"]:
        errors.append("NO_SOURCES")
    if not data["claims"]:
        errors.append("NO_KEY_CLAIMS")
    for source in data["sources"]:
        sid = required_text(source, "id", "source")
        required_text(source, "location", sid)
        required_text(source, "locator", sid)
        if not isinstance(source['verification'], str) or source["verification"] not in {"opened", "metadata-only", "unread"}:
            raise ValueError(f"{sid}: invalid verification")
        if sid in sources:
            errors.append(f"DUPLICATE_SOURCE:{sid}")
        sources[sid] = source

    def references(record, where, require_opened, allow_empty=False):
        refs = record["source_ids"]
        if not isinstance(refs, list) or (not refs and not allow_empty) or any(not isinstance(s, str) or not s.strip() for s in refs):
            raise ValueError(f"{where}.source_ids must contain source IDs")
        for sid in refs:
            if sid not in sources:
                errors.append(f"UNKNOWN_SOURCE:{where}:{sid}")
            elif require_opened and sources[sid]["verification"] != "opened":
                errors.append(f"SOURCE_NOT_OPENED:{where}:{sid}")

    for claim in data["claims"]:
        cid = required_text(claim, "id", "claim")
        required_text(claim, "text", cid)
        required_text(claim, "section", cid)
        if cid in ids:
            errors.append(f"DUPLICATE_CLAIM:{cid}")
        ids.add(cid)
        if not isinstance(claim['status'], str) or claim["status"] not in {"supported", "needs-evidence"}:
            raise ValueError(f"{cid}: invalid status")
        if claim["status"] == "needs-evidence":
            (errors if final else warnings).append(f"UNRESOLVED_CLAIM:{cid}")
        references(claim, cid, claim["status"] == "supported", claim["status"] == "needs-evidence")

    for index, number in enumerate(data["numbers"]):
        where = f"numbers[{index}]"
        key = required_text(number, "key", where)
        condition = required_text(number, "condition", where)
        section = required_text(number, "section", where)
        unit = required_text(number, "unit", where)
        value = number["value"]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"{where}.value must be finite numeric data")
        references(number, where, True)
        group = (key, condition)
        if group in repeated:
            prior = repeated[group]
            if prior[1] != unit:
                errors.append(f"UNIT_MISMATCH:{key}:{condition}:{prior[2]}:{section}")
            elif not math.isclose(prior[0], value, rel_tol=1e-9, abs_tol=1e-12):
                errors.append(f"VALUE_MISMATCH:{key}:{condition}:{prior[2]}:{section}")
        else:
            repeated[group] = (value, unit, section)
    return {"status": "fail" if errors else "pass", "errors": errors, "warnings": warnings,
            "scope": "ledger only; source truth, manuscript coverage and layout not verified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        data = read_json(args.ledger)
        if not isinstance(data, dict):
            raise ValueError("ledger must be an object")
        result = audit(data, args.final)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        emit_json({"status": "input-error", "error": str(exc)})
        return 2
    emit_json(result)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
