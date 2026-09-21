#!/usr/bin/env python3
"""Build an English-to-Chinese translation memory from synchronized trees."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

CJK = re.compile(r"[\u3400-\u9fff]")
LITERAL = re.compile(r'"((?:\\.|[^"\\])*)"')
MACRO = re.compile(r"(?<![A-Za-z0-9_])(?:COMPOUND_STRING|ITEM_NAME|_)\s*\(")
ASM_STRING = re.compile(r"(?m)^\s*\.string\s+(.+)$")


@dataclass
class Unit:
    normalized: str
    expression: str
    context: str


def close_paren(text: str, opening: int) -> int | None:
    depth = 0
    quoted = escaped = False
    for pos in range(opening, len(text)):
        char = text[pos]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return pos + 1
    return None


def normalized(expression: str) -> str:
    return "".join(LITERAL.findall(expression))


def c_units(text: str) -> list[Unit]:
    units = []
    for index, match in enumerate(MACRO.finditer(text)):
        end = close_paren(text, text.find("(", match.start(), match.end()))
        if end is None:
            continue
        expression = text[match.start():end]
        value = normalized(expression)
        if not value:
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        prefix = text[line_start:match.start()].strip()
        units.append(Unit(value, expression, f"c:{index}:{prefix[-80:]}"))
    return units


def asm_units(text: str) -> list[Unit]:
    units = []
    label = ""
    index = 0
    for line in text.splitlines():
        label_match = re.match(r"^([A-Za-z_]\w*)(?:::|:)$", line.strip())
        if label_match:
            label = label_match.group(1)
        string_match = re.match(r"^\s*\.string\s+(.+)$", line)
        if string_match:
            expression = string_match.group(1)
            units.append(Unit(normalized(expression), expression, f"asm:{label}:{index}"))
            index += 1
    return units


def collect(root: Path) -> dict[str, tuple[str, list[Unit]]]:
    result = {}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in {".git", "build", "tools"} for part in path.parts):
            continue
        relative = str(path.relative_to(root))
        if path.suffix in {".c", ".h"}:
            result[relative] = ("c", c_units(path.read_text(encoding="utf-8", errors="ignore")))
        elif path.suffix == ".inc":
            result[relative] = ("asm", asm_units(path.read_text(encoding="utf-8", errors="ignore")))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--chinese", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    english = collect(args.english.resolve())
    chinese = collect(args.chinese.resolve())
    candidates: dict[str, list[dict]] = defaultdict(list)
    mismatched_files = []

    for relative in sorted(set(english) & set(chinese)):
        kind, en_units = english[relative]
        zh_kind, zh_units = chinese[relative]
        if kind != zh_kind or len(en_units) != len(zh_units):
            if en_units or zh_units:
                mismatched_files.append({"file": relative, "english": len(en_units), "chinese": len(zh_units)})
            continue
        for en, zh in zip(en_units, zh_units):
            if en.normalized == zh.normalized or not CJK.search(zh.normalized) or CJK.search(en.normalized):
                continue
            candidates[en.normalized].append({
                "english_expression": en.expression,
                "chinese_expression": zh.expression,
                "file": relative,
                "kind": kind,
                "context": en.context,
            })

    entries = []
    ambiguous = []
    for original, records in sorted(candidates.items()):
        translations = {normalized(record["chinese_expression"]) for record in records}
        if len(translations) == 1:
            entries.append({"english": original, "chinese": next(iter(translations)), "sources": records})
        else:
            ambiguous.append({"english": original, "translations": sorted(translations), "sources": records})
    output = {
        "english_commit": "4c680433909c7fb2219cc9e755f05cdd081d4778",
        "chinese_commit": "df4fbd3594aba62baff2cd1bb04a009a728821bf",
        "entry_count": len(entries),
        "ambiguous_count": len(ambiguous),
        "mismatched_file_count": len(mismatched_files),
        "entries": entries,
        "ambiguous": ambiguous,
        "mismatched_files": mismatched_files,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"entries={len(entries)} ambiguous={len(ambiguous)} mismatched_files={len(mismatched_files)}")


if __name__ == "__main__":
    main()
