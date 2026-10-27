#!/usr/bin/env python3
"""Safely apply source-controlled SefraMC *economic* settings to live Jobs YAML.

Requires PyYAML. Dry-run by default; --apply backs up every changed file.
Never replaces quests, GUI settings, reward commands, earned progress or storage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import yaml

JOBS = ("Miner", "Woodcutter", "Hunter", "Fisherman", "Farmer",
        "Digger", "Cook", "Builder", "Weaponsmith", "Brewer")
GENERAL = {
    ("max-jobs",): 2,
    ("disable-payment-if-max-level-reached",): False,
    ("enable-pay-near-spawner",): False,
    ("enable-pay-creative",): False,
    ("ExploitProtections", "General", "PlaceAndBreak", "Enabled"): True,
    ("ExploitProtections", "General", "PlaceAndBreak", "NewMethod"): True,
    ("ExploitProtections", "Smelt", "PreventHopperFillUps"): True,
    ("ExploitProtections", "Brew", "PreventBrewingStandFillUps"): True,
    ("ExploitProtections", "Furnaces", "MaxDefaultAvailable"): 5,
    ("ExploitProtections", "BlastFurnaces", "MaxDefaultAvailable"): 2,
    ("ExploitProtections", "Smokers", "MaxDefaultAvailable"): 2,
    ("ExploitProtections", "BrewingStands", "MaxDefaultAvailable"): 5,
    ("ExploitProtections", "McMMO", "TreeFellerMultiplier"): 0.2,
    ("ExploitProtections", "McMMO", "gigaDrillMultiplier"): 0.2,
    ("ExploitProtections", "McMMO", "superBreakerMultiplier"): 0.2,
}
KEY = re.compile(r'^(\s*)([^\s#][^:]*):(?:\s*(.*))?$')
SCALAR_KEYS = ("max-level", "vip-max-level", "leveling-progression-equation",
               "experience-progression-equation")
ACTION_KEYS = ("Break", "Place", "Kill", "Fish", "Smelt", "Craft", "Repair", "Brew")


def load(source: str, name: str):
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a YAML mapping")
    return data


def scalar_patch(source: str, edits: dict):
    """Update only existing scalar nodes, preserving all other config text."""
    stack = []
    found = set()
    output = []
    for line in source.splitlines(keepends=True):
        m = KEY.match(line)
        if m is None:
            output.append(line)
            continue
        indent, name, raw = m.groups()
        depth = len(indent.expandtabs(2))
        while stack and stack[-1][0] >= depth:
            stack.pop()
        path = tuple(name for _, name in stack) + (name,)
        if path in edits:
            if raw is None or not raw.strip() or raw.lstrip().startswith("#"):
                raise ValueError(f"Expected scalar {path!r}")
            # Preserve original quoting/formatting when the semantic value is
            # already correct; this makes the migration exactly idempotent.
            existing = yaml.safe_load(raw)
            if existing != edits[path]:
                value = yaml.safe_dump(edits[path], default_flow_style=True).strip()
                if value.endswith("..."):
                    value = value[:-3].strip()
                line = f"{indent}{name}: {value}\n"
            found.add(path)
        elif raw is None or not raw.strip():
            stack.append((depth, name))
        output.append(line)
    return "".join(output), found


def tune_job(original: str, template: str, job: str):
    live = load(original, f"live {job}")
    model = load(template, f"source {job}")
    if job not in live or job not in model:
        raise ValueError(f"{job}: top-level YAML job name does not match source")
    base = live[job]
    selected = model[job]
    edits = {(job, key): selected[key] for key in SCALAR_KEYS if key in selected}
    # The live default might not define vip-max-level; add only that scalar.
    revised, found = scalar_patch(original, edits)
    if (job, "vip-max-level") in edits and (job, "vip-max-level") not in found:
        pattern = re.compile(r"(^  max-level:\s*\d+[^\n]*\n)", re.M)
        if not pattern.search(revised):
            raise ValueError(f"{job}: cannot locate max-level for VIP cap")
        revised = pattern.sub(lambda m: m.group(0) +
                              f"  vip-max-level: {selected['vip-max-level']}\n",
                              revised, count=1)
        found.add((job, "vip-max-level"))
    if found != set(edits):
        raise ValueError(f"{job}: missing progression config keys: {set(edits)-found}")

    # Change paid actions only within their named Jobs action category.
    # This prevents, for example, the Miner Break/stone price accidentally
    # replacing TNTBreak/stone or another profession activity with the same key.
    for action in ACTION_KEYS:
        source_entries = selected.get(action)
        if not isinstance(source_entries, dict):
            continue
        category = re.search(r"^  " + re.escape(action) + r":\s*$", revised, re.M)
        if category is None:
            continue
        suffix = revised[category.end():]
        following = re.search(r"^  [A-Za-z][\w-]*:\s*$", suffix, re.M)
        stop = category.end() + (following.start() if following else len(suffix))
        section = revised[category.end():stop]

        for key, values in source_entries.items():
            if key == "materials" and isinstance(values, list):
                for spec in values:
                    parts = str(spec).split(";")
                    if len(parts) < 4:
                        continue
                    material, amount = parts[0], parts[1]
                    pat = re.compile(r"(^\s*-\s*" + re.escape(material) +
                                     r";)-?\d+(?:\.\d+)?(;[^\n]+)", re.I | re.M)
                    section = pat.sub(lambda m: m.group(1) + str(amount) +
                                      m.group(2), section, count=1)
                continue
            if not isinstance(values, dict) or "income" not in values:
                continue
            keypattern = re.escape(str(key))
            block = re.compile(r"(^    " + keypattern +
                               r":\s*\n      income:\s*)-?\d+(?:\.\d+)?",
                               re.I | re.M)
            section = block.sub(lambda m: m.group(1) + str(values["income"]),
                                section, count=1)
            # Cook uses compact one-line entries like
            # "cooked_beef: {income: 1.0, points: 1, experience: 1.5}".
            compact = re.compile(r"(^    " + keypattern +
                                 r":\s*\{\s*income:\s*)-?\d+(?:\.\d+)?",
                                 re.I | re.M)
            section = compact.sub(lambda m: m.group(1) + str(values["income"]),
                                  section, count=1)
            # The owner specifically requested higher Guardian XP in the Jobs
            # balance post; this is the sole existing per-action EXP override.
            if job == "Hunter" and action == "Kill" and str(key).upper() == "GUARDIAN":
                xp = re.compile(r"(^    " + keypattern +
                                r":\s*\n(?:      [^\n]*\n)*?      experience:\s*)"
                                r"-?\d+(?:\.\d+)?", re.I | re.M)
                section = xp.sub(lambda m: m.group(1) + str(values["experience"]),
                                 section, count=1)
        revised = revised[:category.end()] + section + revised[stop:]

    # The only NEW gameplay actions: missing Elder Guardian and Glow Squid
    # (the owner-provided info post explicitly called these out).
    if job == "Hunter":
        existing = load(revised, job)["Hunter"].get("Kill", {})
        for mob in ("ELDER_GUARDIAN", "GLOW_SQUID"):
            if any(str(k).casefold() == mob.casefold() for k in existing):
                continue
            entry = selected.get("Kill", {}).get(mob)
            if entry is None:
                continue
            marker = re.search(r"^  Kill:\s*$", revised, re.M)
            if marker is None:
                raise ValueError("Hunter: no Kill section")
            remaining = revised[marker.end():]
            next_section = re.search(r"^  [A-Za-z][\w-]*:\s*$", remaining, re.M)
            stop = marker.end() + (next_section.start() if next_section else len(remaining))
            lines = (f"    {mob}:\n" +
                     "".join(f"      {k}: {v}\n" for k, v in entry.items()))
            revised = revised[:stop] + lines + revised[stop:]
            existing[mob] = entry

    validated = load(revised, job)[job]
    for key in SCALAR_KEYS:
        if key in selected and validated.get(key) != selected[key]:
            raise ValueError(f"{job}: failed to configure {key}")
    # Quests, GUI, reward commands and non-economic settings remain intact.
    for field in base:
        if field not in ACTION_KEYS and field not in SCALAR_KEYS:
            if base[field] != validated[field]:
                raise ValueError(f"{job}: unintended change to {field}")
    return revised


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("live_jobs", type=Path, help="Live plugins/Jobs directory")
    parser.add_argument("--apply", action="store_true", help="Write files after backups")
    args = parser.parse_args()
    root = args.live_jobs
    source_root = Path(__file__).resolve().parents[1] / "src/main/resources/jobs"
    if not (root / "jobs").is_dir():
        parser.error(f"Jobs directory is missing: {root / 'jobs'}")
    updates = {}
    for job in JOBS:
        target = root / "jobs" / (job.lower() + ".yml")
        source = source_root / (job.lower() + ".yml")
        template = source.read_text(encoding="utf-8")
        if not target.exists():
            if job == "Cook":
                print("Cook is missing: will create only its owned Jobs definition")
                updates[target] = template
            else:
                print(f"SKIPPING missing {job}; no unrelated Jobs definition will be invented")
            continue
        original = target.read_text(encoding="utf-8")
        revised = tune_job(original, template, job)
        if revised != original:
            updates[target] = revised
        print(f"{job}: {'change' if revised != original else 'already aligned'}")
    general = root / "generalConfig.yml"
    if general.is_file():
        old = general.read_text(encoding="utf-8")
        candidate, found = scalar_patch(old, GENERAL)
        missing = set(GENERAL) - found
        if missing:
            print("General settings not present in this Jobs version (left untouched):",
                  ", ".join(".".join(x) for x in sorted(missing)))
        load(candidate, "generalConfig")
        if candidate != old:
            updates[general] = candidate
    else:
        print("WARNING: generalConfig.yml missing; no limits applied")
    print(f"Changed files: {len(updates)}; no source player progress or unrelated config changed")
    if not args.apply:
        print("DRY RUN: apply nothing. Re-run with --apply to save backups and update files.")
        return
    if not updates:
        print("No changes needed.")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = root / ".sefra-backups" / stamp
    for target in updates:
        if target.exists():
            dest = backup / target.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
    for target, content in updates.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print("Applied. Original configs backed up under:", backup)
    print("Restart Jobs and SePathways; test levels, XP, payouts and limits.")


if __name__ == "__main__":
    main()
