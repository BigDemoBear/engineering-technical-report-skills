"""Read-only candidate scanner; semantic review remains required. Python standard library only."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
MANUAL_RULES = ["N01", "N02", "N03", "N04", "C01", "C02", "C03", "A01", "A02", "A03", "S01", "S02", "Q01", "Q02"]


def invisible(match):
    return "".join("\n" if c == "\n" else " " for c in match.group())


def visible_docx_text(node):
    if node.tag in {W + "del", W + "moveFrom"}:
        return ""
    if node.tag == M + "oMath":
        return "〖公式〗"
    if node.tag == W + "t":
        return node.text or ""
    if node.tag in {W + "tab", W + "br", W + "cr"}:
        return " "
    return "".join(visible_docx_text(child) for child in node)


def read_input(path):
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8-sig"), "line", []
    if suffix != ".docx":
        raise ValueError("supported inputs are UTF-8 .txt, .md, and .docx; PDF requires separate reading/OCR")
    with zipfile.ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
        paragraphs = list(root.iter(W + "p"))
        text = "\n".join(visible_docx_text(p) for p in paragraphs)
        numbering = len(list(root.iter(W + "numPr")))
        revisions = len(list(root.iter(W + "ins"))) + len(list(root.iter(W + "del")))
        notes = ["DOCX locators count body/table paragraphs in XML order, not Word page numbers.",
                 "Automatic/style-inherited numbering, fields, headers, footers, notes, text in images and layout require separate review.",
                 f"Direct numbering nodes: {numbering}; insertion/deletion revision nodes: {revisions}."]
        return text, "paragraph", notes


def protect(text):
    # Keep length and newlines so candidate locations remain tied to original text.
    text = re.sub(r"\A---[^\n]*\n.*?\n---[ \t]*(?=\n|$)", invisible, text, flags=re.S)
    lines = text.splitlines(keepends=True)
    fence = None
    for i, line in enumerate(lines):
        marker = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence:
            lines[i] = invisible(re.match(r"[\s\S]*", line))
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not line[marker.end():].strip():
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]))
            lines[i] = invisible(re.match(r"[\s\S]*", line))
    text = "".join(lines)
    for pattern in [r"(`+)[^\n]*?\1", r"\$\$[\s\S]*?\$\$", r"\\\[[\s\S]*?\\\]",
                    r"(?<!\\)\$[^$\n]+(?<!\\)\$", r"\\\([^\n]*?\\\)",
                    r"https?://[^\s<>()]+", r"\]\([^\n)]*\)", r"\b[A-Za-z]:[\\/][^\s]+",
                    r"\b\d{4}-\d{1,2}-\d{1,2}\b", r"\b\d{3,4}-\d{7,8}\b",
                    r"\b(?:GB(?:/T)?|DL(?:/T)?|IEC|ISO|IEEE)[ \t]+\d+(?:[./—−-]\d+)*",
                    r"(?:图|表|式)[ \t]*\d+(?:-\d+)+"]:
        text = re.sub(pattern, invisible, text)
    return text


def scan(text, locator_kind="line"):
    masked = protect(text)
    original_lines, lines = text.splitlines(), masked.splitlines()
    candidates = []
    in_references = False

    def add(rule, index, match, suggestion, group=0):
        start, end = match.span(group)
        if start == end:
            return
        candidates.append({"rule": rule, "kind": "candidate",
                           "location": {locator_kind: index + 1, "column": start + 1},
                           "original": original_lines[index][start:end],
                           "context": original_lines[index], "suggestion": suggestion})

    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.fullmatch(r"(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*\s+)?(?:参考文献|资料来源|References|Bibliography)\s*", stripped, re.I):
            in_references = True
            continue
        if in_references:
            if re.match(r"^#{1,6}\s+|^附录", stripped):
                in_references = False
            else:
                continue
        unquoted = re.sub(r"“[^”\n]*”|‘[^’\n]*’|《[^》\n]*》", invisible, line)
        for match in re.finditer(r"(?:[（(][0-9一二三四五六七八九十百甲乙丙丁]+[)）]|\d+[)）]|[①-⑳])\s*[、，,.．。；;：:]", unquoted):
            if re.search(r"式\s*$", unquoted[:match.start()]):
                continue
            add("N02", i, match, "先确认为分项序号；若是，删除序号后多余点号，保留序号本身。")
        for match in re.finditer(r"(?<![\w.])(?:\d+|[A-Za-z]|[IVXLCDMivxlcdm]+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)、(?=\s*[\u3400-\u9fff])", unquoted):
            add("N03", i, match, "确认是正文列项后按模板改用下脚点；章节、变量或标签另行判断。")
        for match in re.finditer(r"^(?:#{1,6}\s*)?(\d+(?:\.\d+)+)[.．、。:：](?=\s*[\u3400-\u9fffA-Za-z])", unquoted):
            add("N01", i, match, "若是多级标题编号，去掉编号末尾点号并与标题留空。")
        for match in re.finditer(r"(?:^|[。；：])\s*(?:首先|其次|最后|其[一二三四五六七八九十]|第[一二三四五六七八九十])[、：:；;]", unquoted):
            add("N04", i, match, "确认独立序次语后使用逗号；不要改动作状语的普通词组。")
        for match in re.finditer(r"(?<![\w.])\d+(?:\.\d+)?\s*%?\s*[-−]\s*\d+(?:\.\d+)?\s*(?:%|m/s|mm|ms|kV|kA|Hz|℃|°C|V|A|s|m|年)(?![A-Za-z])", unquoted):
            add("C01", i, match, "核对是数值范围、数学运算还是标识；仅范围按模板建议合适连接号，不自动替换。")
        for match in re.finditer(r"(?:为|是|即)\s*([：:])", unquoted):
            following = original_lines[i][match.end():] + "\n" + "\n".join(original_lines[i + 1:i + 3])
            if re.search(r"=|≜|〖公式〗|\$|\\\[", following):
                add("A02", i, match, "若公式直接承接为/是/即，去掉引导冒号；提示式列举和公式内部符号另行判断。", 1)
        match = re.search(r"(?:步骤如下|结论如下|得到以下结论|分为以下几类)([。.]?)\s*$", unquoted)
        following_lines = [s.strip() for s in lines[i + 1:i + 5] if s.strip()]
        if match and following_lines and re.match(r"(?:[（(]\d+[)）]|\d+[)）.]|[①-⑳])", following_lines[0]):
            add("A03", i, match, "确认这里引出分项；提示语末尾通常用冒号。")
        for match in re.finditer(r"[》”]\s*(、)\s*(?=[《“])", line):
            if not re.match(r"[》”]\s*、\s*[《“]", original_lines[i][match.start():]):
                continue
            add("Q01", i, match, "确认直接并列且没有插入成分；通常删去中间顿号，引用原文/字形说明除外。", 1)
    return candidates


def main():
    from inspect_numbering import inspect as inspect_numbering
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--heading-mode", choices=["decimal", "template"], default="decimal",
                        help="decimal: default heading ladder; template: inventory only, judge headings against the selected template")
    args = parser.parse_args()
    try:
        text, kind, notes = read_input(args.input)
        candidates = scan(text, kind)
        structure = inspect_numbering(args.input, args.heading_mode)
        lexical_count = len(candidates)
        candidates.extend(structure['candidates'])
    except (OSError, UnicodeError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(json.dumps({"status": "input_error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "candidates" if candidates else "no_candidates", "input": str(args.input),
                      "candidate_count": len(candidates), "candidates": candidates,
                      "lexical_candidate_count": lexical_count,
                      "structural_candidate_count": structure['candidate_count'],
                      "numbering_inventory": {k: v for k, v in structure.items() if k != 'candidates'},
                      "manual_review_required": MANUAL_RULES, "notes": notes,
                      "scope": "Read-only candidate scan; no semantic, automatic-numbering or layout pass is implied."},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
