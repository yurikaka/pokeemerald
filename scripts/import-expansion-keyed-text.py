#!/usr/bin/env python3
"""Import Chinese strings from matching designated C table entries."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


CJK_RE = re.compile(r"[\u3400-\u9fff]")
ENTRY_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)\[(?P<key>[A-Za-z_]\w*)\]\s*=")
FIELD_RE = re.compile(r"\.([A-Za-z_]\w*)\s*=\s*$")


@dataclass(frozen=True)
class EntryString:
    path: Path
    relative: str
    key: str
    field: str
    start: int
    end: int
    expression: str


def matching_paren(text: str, opening: int, limit: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False
    for pos in range(opening, limit):
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


def matching_brace(text: str, opening: int) -> int | None:
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
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return pos + 1
    return None


def collect(root: Path) -> dict[tuple[str, str, str], list[EntryString]]:
    result: dict[tuple[str, str, str], list[EntryString]] = defaultdict(list)
    paths = list(root.rglob("*.c")) + list(root.rglob("*.h"))
    for path in paths:
        if any(part in {"build", "tools"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(root))
        entries = list(ENTRY_RE.finditer(text))
        for index, entry in enumerate(entries):
            block_start = entry.end()
            content_start = block_start
            while content_start < len(text) and text[content_start].isspace():
                content_start += 1
            if content_start < len(text) and text[content_start] == "{":
                limit = matching_brace(text, content_start)
                if limit is None:
                    continue
            else:
                semicolon = text.find(";", content_start)
                comma = text.find(",", content_start)
                endings = [pos for pos in (semicolon, comma) if pos >= 0]
                if not endings:
                    continue
                limit = min(endings) + 1
            cursor = block_start
            unnamed = 0
            while cursor < limit:
                candidates = [(text.find(macro + "(", cursor, limit), macro)
                              for macro in ("_", "COMPOUND_STRING")]
                candidates = [(pos, macro) for pos, macro in candidates if pos >= 0]
                if not candidates:
                    break
                start, macro = min(candidates)
                end = matching_paren(text, start + len(macro), limit)
                if end is None:
                    break
                line_prefix = text[text.rfind("\n", block_start, start) + 1:start]
                field_match = FIELD_RE.search(line_prefix)
                if field_match:
                    field = field_match.group(1)
                elif unnamed == 0:
                    field = "$value"
                else:
                    field = f"$value{unnamed}"
                unnamed += 1
                item = EntryString(path, relative, entry.group("key"), field,
                                   start, end, text[start:end])
                result[(relative, item.key, item.field)].append(item)
                cursor = end
    return result


def normalize(expression: str) -> str:
    if expression.startswith("COMPOUND_STRING("):
        return "_(" + expression[len("COMPOUND_STRING("):]
    return expression


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    target_root = Path(__file__).resolve().parent.parent
    target = collect(target_root)
    source = collect(args.source.resolve())
    edits: dict[Path, list[tuple[int, int, str, str]]] = defaultdict(list)

    for identity in sorted(set(target) & set(source)):
        if len(target[identity]) != 1 or len(source[identity]) != 1:
            continue
        old = target[identity][0]
        translated = normalize(source[identity][0].expression)
        if (CJK_RE.search(translated) and not CJK_RE.search(old.expression)
                and translated != old.expression):
            edits[old.path].append((old.start, old.end, translated,
                                    f"{old.key}.{old.field}"))

    changed_files = []
    changed_entries = []
    for path, path_edits in sorted(edits.items(), key=lambda item: str(item[0])):
        text = path.read_text(encoding="utf-8")
        for start, end, replacement, identity in sorted(path_edits, reverse=True):
            text = text[:start] + replacement + text[end:]
            changed_entries.append(identity)
        changed_files.append(str(path.relative_to(target_root)))
        if args.apply:
            path.write_text(text, encoding="utf-8")

    report = {
        "source": str(args.source),
        "apply": args.apply,
        "changed_file_count": len(changed_files),
        "changed_entry_count": len(changed_entries),
        "changed_files": changed_files,
    }
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
