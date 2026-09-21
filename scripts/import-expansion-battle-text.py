#!/usr/bin/env python3
"""Import expansion battle translations while retaining vanilla placeholders."""

import argparse
import re
import subprocess
from pathlib import Path

from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parent.parent
helper = SourceFileLoader("semantic", str(Path(__file__).with_name("import-expansion-semantic-text.py"))).load_module()
TOKEN = re.compile(r"\{(B_[A-Z0-9_]+)\}")


def table_values(path):
    result = {}
    for key, (_start, _end, block) in helper.blocks(path).items():
        item = helper.value(block)
        if key.startswith("STRINGID_") and item:
            result[key] = helper.normalized(item[2])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--english-source", type=Path, required=True)
    args = parser.parse_args()

    chinese = table_values(args.source / "src/battle_message.c")
    english = table_values(args.english_source / "src/battle_message.c")
    baseline = subprocess.run(
        ["git", "show", "HEAD:src/battle_message.c"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    current_path = ROOT / "src/battle_message.c"
    current = current_path.read_text(encoding="utf-8")

    pointers = {}
    for match in re.finditer(r"\[(STRINGID_[A-Z0-9_]+)(?:\s*-\s*[A-Z0-9_]+)?\]\s*=\s*(\w+)", baseline):
        pointers[match.group(1)] = match.group(2)

    edits = []
    skipped = []
    for key, symbol in pointers.items():
        if key not in chinese or key not in english:
            continue
        base_item = helper.declaration_expr(baseline, symbol)
        current_item = helper.declaration_expr(current, symbol)
        if not base_item or not current_item:
            continue
        source_tokens = TOKEN.findall(english[key])
        target_tokens = TOKEN.findall(base_item[2])
        if len(source_tokens) != len(target_tokens):
            skipped.append(key)
            replacement = base_item[2]
        else:
            mapping = {}
            valid = True
            for source_token, target_token in zip(source_tokens, target_tokens):
                if source_token in mapping and mapping[source_token] != target_token:
                    valid = False
                mapping[source_token] = target_token
            replacement = chinese[key]
            if valid:
                replacement = TOKEN.sub(lambda m: "{" + mapping.get(m.group(1), m.group(1)) + "}", replacement)
            else:
                skipped.append(key)
                replacement = base_item[2]
        edits.append((current_item[0], current_item[1], replacement))

    for start, end, replacement in sorted(edits, reverse=True):
        current = current[:start] + replacement + current[end:]
    current_path.write_text(current, encoding="utf-8")
    print(f"imported={len(edits) - len(skipped)} restored={len(skipped)}")


if __name__ == "__main__":
    main()
