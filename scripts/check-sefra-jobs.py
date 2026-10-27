#!/usr/bin/env python3
"""Static source checks and isolated live-sync regression tests (PyYAML)."""
from pathlib import Path
import importlib.util
import tempfile
import yaml

root = Path(__file__).resolve().parents[1]
jobs = root / "src/main/resources/jobs"
plugin = root / "scripts/sefra-tune-live-jobs.py"
loader = importlib.util.spec_from_file_location("sefra_jobs_sync", plugin)
module = importlib.util.module_from_spec(loader)
loader.loader.exec_module(module)

expected = set(module.JOBS)
assert len(expected) == 10
for name in expected:
    path = jobs / (name.lower() + ".yml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert name in data, name
    config = data[name]
    assert config["leveling-progression-equation"] == "(10*(joblevel)+(joblevel*(joblevel*1.3)*110))*(joblevel*0.03)", name
    assert config["experience-progression-equation"] == "baseexperience*0.46*(1-((numjobs-1)*0.01))", name
    assert config["max-level"] == 9 and config["vip-max-level"] == 99, name

# No duplicate Hunter mob names, and the referenced information-post additions.
hunter = yaml.safe_load((jobs / "hunter.yml").read_text())["Hunter"]["Kill"]
assert {"GUARDIAN", "SQUID", "GLOW_SQUID", "ELDER_GUARDIAN"} <= set(hunter)
assert hunter["ELDER_GUARDIAN"]["income"] > hunter["GUARDIAN"]["income"]

# Sync must be idempotent, preserve TNTBreak, and never alter a quest/GUI.
miner = (jobs / "miner.yml").read_text()
first = module.tune_job(miner, miner, "Miner")
assert first == miner, "Sync should not alter an already-tuned source file"
unbalanced = miner.replace("  Break:\n    andesite:", "  Break:\n    andesite:").replace(
    "    stone:\n      income: 0.12", "    stone:\n      income: 3.5"
)
assert unbalanced != miner
fixed = module.tune_job(unbalanced, miner, "Miner")
assert fixed == miner
assert "  TNTBreak:\n    stone:\n      income: 0.25" in fixed

# Cook inline mapping must be supported without losing its other fields.
cook = (jobs / "cook.yml").read_text()
assert module.tune_job(cook, cook, "Cook") == cook
modified = cook.replace("cooked_beef: {income: 0.18,", "cooked_beef: {income: 8,")
assert modified != cook
assert module.tune_job(modified, cook, "Cook") == cook

# Unmodified reward, GUI and story configuration remains byte-for-byte intact.
for key in ("Quests", "Gui"):
    if key in yaml.safe_load(miner)["Miner"]:
        assert yaml.safe_load(miner)["Miner"][key] == yaml.safe_load(fixed)["Miner"][key]

print("OK: 10 Jobs curves and caps, Hunter mobs, safe/idempotent live sync, source actions.")
