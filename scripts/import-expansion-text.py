#!/usr/bin/env python3
"""Import same-symbol Chinese text without importing expansion game logic."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


LABEL_RE = re.compile(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)(?:::|:)\s*$")
STRING_LINE_RE = re.compile(r"(?m)^[ \t]*\.string[ \t]+.*(?:\n|$)")
CJK_RE = re.compile(r"[\u3400-\u9fff]")


def collect_blocks(root: Path) -> dict[str, list[tuple[Path, str]]]:
    blocks: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for path in root.rglob("*.inc"):
        text = path.read_text(encoding="utf-8")
        labels = list(LABEL_RE.finditer(text))
        for index, match in enumerate(labels):
            end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
            block = text[match.start():end]
            if STRING_LINE_RE.search(block):
                blocks[match.group(1)].append((path, block))
    return blocks


def translated_string_lines(block: str) -> str:
    return "".join(match.group(0) for match in STRING_LINE_RE.finditer(block))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    target_root = Path(__file__).resolve().parent.parent
    source_root = args.source.resolve()
    target = collect_blocks(target_root)
    source = collect_blocks(source_root)
    replacements: dict[Path, dict[str, str]] = defaultdict(dict)
    skipped_ambiguous: list[str] = []

    for symbol in sorted(set(target) & set(source)):
        if len(target[symbol]) != 1 or len(source[symbol]) != 1:
            skipped_ambiguous.append(symbol)
            continue
        translated = translated_string_lines(source[symbol][0][1])
        if not CJK_RE.search(translated):
            continue
        replacements[target[symbol][0][0]][symbol] = translated

    changed_symbols: list[str] = []
    changed_files: list[str] = []
    for path, symbol_map in sorted(replacements.items(), key=lambda item: str(item[0])):
        text = path.read_text(encoding="utf-8")
        labels = list(LABEL_RE.finditer(text))
        edits: list[tuple[int, int, str, str]] = []
        for index, match in enumerate(labels):
            symbol = match.group(1)
            if symbol not in symbol_map:
                continue
            end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
            block = text[match.start():end]
            string_matches = list(STRING_LINE_RE.finditer(block))
            if not string_matches:
                continue
            start_in_block = string_matches[0].start()
            end_in_block = string_matches[-1].end()
            edits.append((match.start() + start_in_block,
                          match.start() + end_in_block,
                          symbol_map[symbol], symbol))

        for start, end, replacement, symbol in reversed(edits):
            text = text[:start] + replacement + text[end:]
            changed_symbols.append(symbol)
        if edits:
            changed_files.append(str(path.relative_to(target_root)))
            if args.apply:
                path.write_text(text, encoding="utf-8")

    report = {
        "source": str(source_root),
        "apply": args.apply,
        "changed_file_count": len(changed_files),
        "changed_symbol_count": len(changed_symbols),
        "changed_files": changed_files,
        "skipped_ambiguous_symbols": skipped_ambiguous,
    }
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
