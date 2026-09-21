#!/usr/bin/env python3
"""Import translated table fields from expansion into vanilla split tables."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

CJK = re.compile(r"[\u3400-\u9fff]")
DESIGNATOR = re.compile(r"(?m)^\s*\[(?P<key>[A-Z][A-Z0-9_]*)(?:\s*-\s*(?:1|[A-Z][A-Z0-9_]*))?\]\s*=")
MACROS = ("COMPOUND_STRING", "ITEM_NAME", "_")


@dataclass
class Expr:
    path: Path
    start: int
    end: int
    text: str


def matching(text: str, opening: int, left: str, right: str) -> int | None:
    depth = 0
    quoted = escaped = False
    for pos in range(opening, len(text)):
        ch = text[pos]
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"':
            quoted = True
        elif ch == left:
            depth += 1
        elif ch == right:
            depth -= 1
            if depth == 0:
                return pos + 1
    return None


def blocks(path: Path) -> dict[str, tuple[int, int, str]]:
    text = path.read_text(encoding="utf-8")
    result = {}
    for match in DESIGNATOR.finditer(text):
        cursor = match.end()
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor < len(text) and text[cursor] == "{":
            end = matching(text, cursor, "{", "}")
        else:
            opening = text.find("(", cursor, cursor + 64)
            end = matching(text, opening, "(", ")") if opening >= 0 else None
            if end is not None and end < len(text) and text[end] == ",":
                end += 1
        if end is not None:
            result.setdefault(match.group("key"), (match.start(), end, text[match.start():end]))
    return result


def macro_at(text: str, start: int, limit: int) -> tuple[int, int, str] | None:
    while start < limit and text[start].isspace():
        start += 1
    macro = next((name for name in MACROS if text.startswith(name + "(", start)), None)
    if macro is None:
        return None
    end = matching(text, start + len(macro), "(", ")")
    if end is None or end > limit:
        return None
    return start, end, text[start:end]


def field(block: str, name: str) -> tuple[int, int, str] | None:
    match = re.search(r"\." + re.escape(name) + r"\s*=\s*", block)
    return macro_at(block, match.end(), len(block)) if match else None


def value(block: str) -> tuple[int, int, str] | None:
    match = re.match(r"\s*\[[^]]+\]\s*=\s*", block)
    return macro_at(block, match.end(), len(block)) if match else None


def first_macro(block: str) -> tuple[int, int, str] | None:
    """Return the first translation macro in an entry, including tuple entries."""
    starts = [pos for name in MACROS if (pos := block.find(name + "(")) >= 0]
    return macro_at(block, min(starts), len(block)) if starts else None


def normalized(expression: str) -> str:
    opening = expression.find("(")
    expression = "_(" + expression[opening + 1:]
    expression = re.sub(r"(?m)^\s*#(?:if|ifdef|ifndef|else|elif|endif).*\n?", "", expression)
    # Expansion distinguishes article-bearing battle names with a PREFIX2 token;
    # vanilla has only the corresponding PREFIX token. Chinese does not use the
    # English article distinction, so the vanilla token is semantically correct.
    return expression.replace("_NAME_WITH_PREFIX2}", "_NAME_WITH_PREFIX}")


def source_table(paths: list[Path], wanted_fields: tuple[str, ...]) -> dict[tuple[str, str], str]:
    result = {}
    for path in paths:
        for key, (_start, _end, block) in blocks(path).items():
            for name in wanted_fields:
                item = field(block, name)
                if item and CJK.search(item[2]):
                    result[(key, name)] = normalized(item[2])
    return result


def replace_direct(path: Path, translations: dict[tuple[str, str], str],
                   field_name: str, key_prefix: str, source_field: str) -> int:
    text = path.read_text(encoding="utf-8")
    edits = []
    for key, (block_start, _block_end, block) in blocks(path).items():
        if not key.startswith(key_prefix):
            continue
        item = value(block) if field_name == "$value" else field(block, field_name)
        translated = translations.get((key, source_field))
        if item and translated and not CJK.search(item[2]):
            edits.append((block_start + item[0], block_start + item[1], translated))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    if edits:
        path.write_text(text, encoding="utf-8")
    return len(edits)


def declaration_expr(text: str, symbol: str) -> tuple[int, int, str] | None:
    match = re.search(r"(?m)^\s*(?:static\s+)?const\s+u8\s+" + re.escape(symbol)
                      + r"\s*\[[^]]*\]\s*=\s*", text)
    return macro_at(text, match.end(), len(text)) if match else None


def replace_pointed_descriptions(data_path: Path, pointer_path: Path,
                                 translations: dict[tuple[str, str], str],
                                 prefix: str) -> int:
    data = data_path.read_text(encoding="utf-8")
    pointers = pointer_path.read_text(encoding="utf-8")
    key_to_symbol = {}
    # Pointer arrays (moves and abilities).
    for match in re.finditer(r"\[(" + prefix + r"[A-Z0-9_]+)(?:\s*-\s*1)?\]\s*=\s*(\w+)", pointers):
        key_to_symbol[match.group(1)] = match.group(2)
    # Struct fields (items).
    if prefix in {"ITEM_", "NATIONAL_DEX_"}:
        for key, (_start, _end, block) in blocks(pointer_path).items():
            match = re.search(r"\.description\s*=\s*(\w+)", block)
            if match:
                key_to_symbol[key] = match.group(1)
    edits = []
    for key, symbol in key_to_symbol.items():
        translated = translations.get((key, "description"))
        item = declaration_expr(data, symbol)
        if translated and item and not CJK.search(item[2]):
            edits.append((item[0], item[1], translated))
    for start, end, replacement in sorted(edits, reverse=True):
        data = data[:start] + replacement + data[end:]
    if edits:
        data_path.write_text(data, encoding="utf-8")
    return len(edits)


def replace_pointed_field(data_path: Path, pointer_path: Path,
                          translations: dict[tuple[str, str], str], field_name: str) -> int:
    data = data_path.read_text(encoding="utf-8")
    edits = []
    for key, (_start, _end, block) in blocks(pointer_path).items():
        pointer = re.search(r"\." + re.escape(field_name) + r"\s*=\s*(\w+)", block)
        translated = translations.get((key, field_name))
        item = declaration_expr(data, pointer.group(1)) if pointer else None
        if translated and item and not CJK.search(item[2]):
            edits.append((item[0], item[1], translated))
    for start, end, replacement in sorted(set(edits), reverse=True):
        data = data[:start] + replacement + data[end:]
    if edits:
        data_path.write_text(data, encoding="utf-8")
    return len(set(edits))


def tuple_values(path: Path, prefix: str) -> dict[tuple[str, str], str]:
    result = {}
    for key, (_start, _end, block) in blocks(path).items():
        item = first_macro(block)
        if key.startswith(prefix) and item and CJK.search(item[2]):
            result[(key, "$value")] = normalized(item[2])
    return result


def replace_pointer_table(data_path: Path, pointer_path: Path,
                          translations: dict[tuple[str, str], str], prefix: str) -> int:
    """Replace declarations referenced by an enum-indexed pointer table."""
    data = data_path.read_text(encoding="utf-8")
    pointers = pointer_path.read_text(encoding="utf-8")
    edits = []
    for match in re.finditer(r"\[(" + prefix + r"[A-Z0-9_]+)(?:\s*-\s*[A-Z0-9_]+)?\]\s*=\s*(\w+)", pointers):
        translated = translations.get((match.group(1), "$value"))
        item = declaration_expr(data, match.group(2))
        if translated and item and not CJK.search(item[2]):
            edits.append((item[0], item[1], translated))
    for start, end, replacement in sorted(set(edits), reverse=True):
        data = data[:start] + replacement + data[end:]
    if edits:
        data_path.write_text(data, encoding="utf-8")
    return len(set(edits))


def party_trainer_names(path: Path) -> dict[tuple[str, str], str]:
    """Read trainerproc's keyed `trainers.party` format."""
    result = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"===\s*(TRAINER_[A-Z0-9_]+)\s*===", line)
        if match:
            current = match.group(1)
            continue
        match = re.match(r"Name:\s*(.*)\s*$", line)
        if current and match and CJK.search(match.group(1)):
            result[(current, "trainerName")] = '_("' + match.group(1) + '")'
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    source = args.source.resolve()

    moves = source_table([source / "src/data/moves_info.h"], ("name", "description"))
    items = source_table([source / "src/data/items.h"], ("name", "description"))
    item_aliases = {
        "ITEM_X_DEFEND": "ITEM_GUARD_SPEC",
        "ITEM_X_SPECIAL": "ITEM_X_SP_ATK",
        "ITEM_UP_GRADE": "ITEM_UPGRADE",
        "ITEM_STICK": "ITEM_LEEK",
        "ITEM_ITEMFINDER": "ITEM_DOWSING_MACHINE",
        "ITEM_DEVON_GOODS": "ITEM_DEVON_PARTS",
        "ITEM_ROOM_1_KEY": "ITEM_KEY_TO_ROOM_1",
        "ITEM_ROOM_2_KEY": "ITEM_KEY_TO_ROOM_2",
        "ITEM_ROOM_4_KEY": "ITEM_KEY_TO_ROOM_4",
        "ITEM_ROOM_6_KEY": "ITEM_KEY_TO_ROOM_6",
        "ITEM_OAKS_PARCEL": "ITEM_PARCEL",
    }
    for target_key, source_key in item_aliases.items():
        for field_name in ("name", "description"):
            if (source_key, field_name) in items:
                items[(target_key, field_name)] = items[(source_key, field_name)]
    abilities = source_table([source / "src/data/abilities.h"], ("name", "description"))
    species_files = list((source / "src/data/pokemon/species_info").glob("gen_*_families.h"))
    species = source_table(species_files, ("categoryName", "description"))
    battle = source_table([source / "src/battle_message.c"], ("$value",))
    # gBattleStringsTable uses direct enum-indexed expressions rather than structs.
    battle = {}
    for key, (_start, _end, block) in blocks(source / "src/battle_message.c").items():
        item = value(block)
        if key.startswith("STRINGID_") and item and CJK.search(item[2]):
            battle[(key, "$value")] = normalized(item[2])
    natures = source_table([source / "src/pokemon.c"], ("name",))
    trainers = party_trainer_names(source / "src/data/trainers.party")
    berries = source_table([source / "src/berry.c"], ("name", "description1", "description2"))
    trainer_classes = tuple_values(source / "src/battle_main.c", "TRAINER_CLASS_")

    counts = {}
    counts["move_names"] = replace_direct(root / "src/data/text/move_names.h", moves, "$value", "MOVE_", "name")
    counts["move_descriptions"] = replace_pointed_descriptions(
        root / "src/data/text/move_descriptions.h", root / "src/data/text/move_descriptions.h", moves, "MOVE_")
    counts["item_names"] = replace_direct(root / "src/data/items.h", items, "name", "ITEM_", "name")
    counts["item_descriptions"] = replace_pointed_descriptions(
        root / "src/data/text/item_descriptions.h", root / "src/data/items.h", items, "ITEM_")
    counts["ability_names"] = replace_direct(root / "src/data/text/abilities.h", abilities, "$value", "ABILITY_", "name")
    counts["ability_descriptions"] = replace_pointed_descriptions(
        root / "src/data/text/abilities.h", root / "src/data/text/abilities.h", abilities, "ABILITY_")

    # Species names are deliberately excluded. Only category and Pokédex prose are imported.
    national = {(key.replace("SPECIES_", "NATIONAL_DEX_"), field): value
                for (key, field), value in species.items()}
    counts["categories"] = replace_direct(root / "src/data/pokemon/pokedex_entries.h",
                                           national, "categoryName", "NATIONAL_DEX_", "categoryName")
    counts["pokedex_descriptions"] = replace_pointed_descriptions(
        root / "src/data/pokemon/pokedex_text.h", root / "src/data/pokemon/pokedex_entries.h",
        national, "NATIONAL_DEX_")
    # Battle strings require placeholder remapping; use
    # import-expansion-battle-text.py instead of direct replacement.
    counts["nature_names"] = replace_pointer_table(
        root / "src/data/text/nature_names.h", root / "src/data/text/nature_names.h",
        {(key, "$value"): value for (key, field), value in natures.items() if field == "name"},
        "NATURE_")
    counts["trainer_names"] = replace_direct(
        root / "src/data/trainers.h", trainers, "trainerName", "TRAINER_", "trainerName")
    counts["berry_names"] = replace_direct(
        root / "src/berry.c", berries, "name", "ITEM_", "name")
    counts["berry_description1"] = replace_pointed_field(
        root / "src/berry.c", root / "src/berry.c", berries, "description1")
    counts["berry_description2"] = replace_pointed_field(
        root / "src/berry.c", root / "src/berry.c", berries, "description2")
    counts["trainer_classes"] = replace_direct(
        root / "src/data/text/trainer_class_names.h", trainer_classes,
        "$value", "TRAINER_CLASS_", "$value")
    print("\n".join(f"{key}: {value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
