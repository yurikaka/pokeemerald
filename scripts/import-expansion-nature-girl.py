#!/usr/bin/env python3
"""Map expansion's nine Battle Palace behavior texts to vanilla nature labels."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "pokeemerald_expansion_chs" / "data/maps/BattleFrontier_Lounge5/scripts.inc"
TARGET = ROOT / "data/maps/BattleFrontier_Lounge5/scripts.inc"

GROUPS = {
    "Hardy": "AttackHighAttackLow", "Lonely": "SupportHighAttackLow",
    "Brave": "AttackHighDefenseLow", "Adamant": "AttackHighAttackLow",
    "Naughty": "DefenseHighAttackLow", "Bold": "SupportHighDefenseLow",
    "DocileNaiveQuietQuirky": "AttackHighAttackLow",
    "Relaxed": "SupportHighAttackLow", "Impish": "AttackHighDefenseLow",
    "Lax": "SupportHighSupportLow", "Timid": "AttackHighSupportLow",
    "Hasty": "AttackHighAttackLow", "Serious": "SupportHighSupportLow",
    "Jolly": "SupportHighDefenseLow", "Modest": "DefenseHighDefenseLow",
    "Mild": "DefenseHighSupportLow", "Bashful": "DefenseHighDefenseLow",
    "Rash": "SupportHighSupportLow", "Calm": "DefenseHighDefenseLow",
    "Gentle": "DefenseHighAttackLow", "Sassy": "AttackHighSupportLow",
    "Careful": "DefenseHighSupportLow",
}

LABEL = re.compile(r"(?m)^(BattleFrontier_Lounge5_Text_NatureGirl\w+)::\s*$")
STRING = re.compile(r"(?m)^[ \t]*\.string[ \t]+.*(?:\n|$)")


def blocks(text):
    labels = list(LABEL.finditer(text))
    return {m.group(1): (m.start(), labels[i + 1].start() if i + 1 < len(labels) else len(text))
            for i, m in enumerate(labels)}


source_text = SOURCE.read_text(encoding="utf-8")
target_text = TARGET.read_text(encoding="utf-8")
source_blocks = blocks(source_text)
target_blocks = blocks(target_text)
edits = []
for nature, group in GROUPS.items():
    source_label = "BattleFrontier_Lounge5_Text_NatureGirl" + group
    target_label = "BattleFrontier_Lounge5_Text_NatureGirl" + nature
    source_start, source_end = source_blocks[source_label]
    target_start, target_end = target_blocks[target_label]
    translated = "".join(m.group(0) for m in STRING.finditer(source_text, source_start, source_end))
    matches = list(STRING.finditer(target_text, target_start, target_end))
    edits.append((matches[0].start(), matches[-1].end(), translated))

for start, end, replacement in sorted(edits, reverse=True):
    target_text = target_text[:start] + replacement + target_text[end:]
TARGET.write_text(target_text, encoding="utf-8")
print(f"nature girl texts: {len(edits)}")
