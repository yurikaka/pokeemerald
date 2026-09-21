#!/usr/bin/env python3
"""Import named Chinese C strings while preserving the vanilla C logic."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


CJK_RE = re.compile(r"[\u3400-\u9fff]")
PRESERVE_ENGLISH = {
    # These defaults are copied verbatim into the save file.  Keep their
    # original single-byte encoding for compatibility with unmodified games.
    "gText_Hello",
    "gText_Pokemon2",
    "gText_Trade",
    "gText_Battle",
    "gText_Lets",
    "gText_Ok",
    "gText_Sorry",
    "gText_YaySmileEmoji",
    "gText_ThankYou",
    "gText_ByeBye",
    "gText_Peekaboo",
}
DECL_RE = re.compile(
    r"(?m)^(?P<prefix>[ \t]*(?:(?:static|const|extern|ALIGNED\([^\n]*?\))\s+)*"
    r"u8\s+(?P<name>[A-Za-z_]\w*)\s*\[[^;=]*?\]\s*=\s*)"
)


@dataclass(frozen=True)
class CString:
    path: Path
    name: str
    start: int
    end: int
    expression: str


def matching_paren(text: str, opening: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False
    for pos in range(opening, len(text)):
        char = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return pos + 1
    return None


def collect(root: Path) -> dict[tuple[str, str], list[CString]]:
    found: dict[tuple[str, str], list[CString]] = defaultdict(list)
    paths = list(root.rglob("*.c")) + list(root.rglob("*.h"))
    for path in paths:
        if any(part in {"build", "tools"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(root))
        for match in DECL_RE.finditer(text):
            start = match.end()
            macro = next((item for item in ("_", "COMPOUND_STRING")
                          if text.startswith(item, start)), None)
            if macro is None:
                continue
            opening = start + len(macro)
            if opening >= len(text) or text[opening] != "(":
                continue
            end = matching_paren(text, opening)
            if end is None or ";" not in text[end:end + 8]:
                continue
            item = CString(path, match.group("name"), start, end, text[start:end])
            found[(relative, item.name)].append(item)
    return found


def target_expression(source: str) -> str:
    if source.startswith("COMPOUND_STRING("):
        return "_(" + source[len("COMPOUND_STRING("):]
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    target_root = Path(__file__).resolve().parent.parent
    source_root = args.source.resolve()
    target = collect(target_root)
    source = collect(source_root)
    target_by_name: dict[str, list[CString]] = defaultdict(list)
    source_by_name: dict[str, list[CString]] = defaultdict(list)
    for entries in target.values():
        for entry in entries:
            target_by_name[entry.name].append(entry)
    for entries in source.values():
        for entry in entries:
            source_by_name[entry.name].append(entry)
    edits_by_path: dict[Path, list[tuple[int, int, str, str]]] = defaultdict(list)
    ambiguous: list[str] = []

    for key in sorted(set(target) & set(source)):
        if key[1] in PRESERVE_ENGLISH:
            continue
        if len(target[key]) != 1 or len(source[key]) != 1:
            ambiguous.append(f"{key[0]}:{key[1]}")
            continue
        translated = target_expression(source[key][0].expression)
        if not CJK_RE.search(translated):
            continue
        old = target[key][0]
        if CJK_RE.search(old.expression):
            continue
        if old.expression != translated:
            edits_by_path[old.path].append((old.start, old.end, translated, old.name))

    already_selected = {
        (path, start, end)
        for path, edits in edits_by_path.items()
        for start, end, _replacement, _name in edits
    }
    for name in sorted(set(target_by_name) & set(source_by_name)):
        if name in PRESERVE_ENGLISH:
            continue
        if len(target_by_name[name]) != 1:
            continue
        old = target_by_name[name][0]
        if (old.path, old.start, old.end) in already_selected:
            continue
        if CJK_RE.search(old.expression):
            continue
        source_expressions = {
            target_expression(entry.expression) for entry in source_by_name[name]
            if CJK_RE.search(entry.expression)
        }
        if len(source_expressions) != 1:
            continue
        translated = source_expressions.pop()
        if CJK_RE.search(translated) and old.expression != translated:
            edits_by_path[old.path].append((old.start, old.end, translated, old.name))

    changed_files: list[str] = []
    changed_symbols: list[str] = []
    for path, edits in sorted(edits_by_path.items(), key=lambda item: str(item[0])):
        text = path.read_text(encoding="utf-8")
        for start, end, replacement, name in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
            changed_symbols.append(name)
        changed_files.append(str(path.relative_to(target_root)))
        if args.apply:
            path.write_text(text, encoding="utf-8")

    report = {
        "source": str(args.source),
        "apply": args.apply,
        "changed_file_count": len(changed_files),
        "changed_symbol_count": len(changed_symbols),
        "changed_files": changed_files,
        "skipped_ambiguous": ambiguous,
    }
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
