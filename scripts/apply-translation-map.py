#!/usr/bin/env python3
"""Apply unique content translations without depending on source symbol names."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from importlib.machinery import SourceFileLoader

helpers = SourceFileLoader("translation_map_helpers", str(Path(__file__).with_name("build-translation-map.py"))).load_module()

PRESERVE_SYMBOLS = {
    "gText_Hello", "gText_Pokemon2", "gText_Trade", "gText_Battle", "gText_Lets",
    "gText_Ok", "gText_Sorry", "gText_YaySmileEmoji", "gText_ThankYou", "gText_ByeBye",
    "gText_Peekaboo",
}


def enclosing_symbol(text: str, position: int) -> str | None:
    start = text.rfind("\n", 0, position) + 1
    prefix = text[start:position]
    match = re.search(r"(?:const\s+u8|u8)\s+(\w+)\s*\[", prefix)
    return match.group(1) if match else None


def apply_c(path: Path, translations: dict[str, str], do_apply: bool) -> int:
    if path.as_posix().endswith("src/data/text/species_names.h"):
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    edits = []
    for match in helpers.MACRO.finditer(text):
        end = helpers.close_paren(text, text.find("(", match.start(), match.end()))
        if end is None:
            continue
        expression = text[match.start():end]
        original = helpers.normalized(expression)
        translated = translations.get(original)
        if not translated or helpers.CJK.search(original):
            continue
        if enclosing_symbol(text, match.start()) in PRESERVE_SYMBOLS:
            continue
        edits.append((match.start(), end, '_("' + translated + '")'))
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    if edits and do_apply:
        path.write_text(text, encoding="utf-8")
    return len(edits)


def apply_asm(path: Path, translations: dict[str, str], do_apply: bool) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    edits = []
    for match in helpers.ASM_STRING.finditer(text):
        expression = match.group(1)
        original = helpers.normalized(expression)
        translated = translations.get(original)
        if translated and not helpers.CJK.search(original):
            edits.append((match.start(1), match.end(1), '"' + translated + '"'))
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    if edits and do_apply:
        path.write_text(text, encoding="utf-8")
    return len(edits)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    data = json.loads(args.map.read_text(encoding="utf-8"))
    translations = {entry["english"]: entry["chinese"] for entry in data["entries"]}
    counts = Counter()
    files = []
    for path in list((root / "src").rglob("*.c")) + list((root / "src").rglob("*.h")):
        count = apply_c(path, translations, args.apply)
        if count:
            files.append(str(path.relative_to(root)))
            counts["c"] += count
    for base in (root / "data/maps", root / "data/scripts", root / "data/text"):
        for path in base.rglob("*.inc"):
            count = apply_asm(path, translations, args.apply)
            if count:
                files.append(str(path.relative_to(root)))
                counts["asm"] += count
    report = {"apply": args.apply, "counts": dict(counts), "file_count": len(set(files)), "files": sorted(set(files))}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
