# SefraMC Jobs — economic tuning v0.1

This is an **initial balancing baseline**, not a verified match for another server. The owner-provided information post supplies the leveling equation and 0.46 XP multiplier. The owner's purchased Jobs.zip was inspected for action and **relative payout ideas only**: its reward tracks, quests, GUIs, menus, and assets were **not imported**.

## Level progression

The same formula applies to every SefraMC Jobs profession:

~~~text
(10*(joblevel)+(joblevel*(joblevel*1.3)*110))*(joblevel*0.03)
~~~

The owner's reference post supplied the equation with X instead of joblevel. Approximate XP per level: level 1 = 4, 6 = 937, 9 = 3,151, 19 = 29,533, 29 = 104,881, 49 = 505,434, 69 = 1,410,731, 79 = 2,117,009 and 99 = 4,165,523.

For the Jobs XP dampener (not wages):

~~~text
baseexperience*0.46*(1-((numjobs-1)*0.01))
~~~

The 0.46 multiplier is applied **once** through the job's experience-progression-equation, *not* by scaling each action's configured experience value. The existing small second-job XP adjustment remains. The separate Jobs income-progression-equation is retained and remains under Jobs' control. SePathways no longer supplies wage bonuses.

**Important:** the reference post describes levels up to 70. SefraMC uses Sequence gates reaching Jobs level 99, so levels 71–99 are an unverified extension of this steep curve. Level 1–9 requires about 8,768 XP before the 0.46 factor; for someone gaining 1 raw Jobs XP per action, that equates to roughly 19,061 actions. This is illustrative, not a play-time prediction.

## Initial currency payout examples

Values below are newly selected **SefraMC base payouts in Embers**. They are not exact measurements of the reference server.

| Backend / action | Selected base earnings |
|---|---|
| Miner / BREAK | Stone 0.12; iron ore 0.65; diamond ore 4.0 |
| Woodcutter / BREAK | Logs 0.40; stripped logs 0.24 |
| Hunter / KILL | Guardian 4.0; Squid 0.8; Glow Squid 1.2; Elder Guardian 40 |
| Fisherman / FISH | Cod 0.80; salmon 1.45; tropical fish 1.95; pufferfish 1.65 |
| Farmer / BREAK | Ripe wheat 0.28; ripe carrots and potatoes 0.25 |
| Digger / BREAK | Dirt 0.08; sand 0.14; gravel 0.13 |
| Cook / SMELT / CRAFT | Cooked beef 0.18; bread 0.16; cake 0.70 |
| Builder / PLACE | Stone 0.04; oak planks 0.09 |
| Weaponsmith / CRAFT | Iron sword 3; diamond sword 6 |
| Brewer / BREW | Nether wart 1.0; redstone 1.25; glowstone 1.25 |

Other payouts and per-action XP are retained from existing job files **except Guardian XP**, raised from 2 to 10 per kill per the owner-provided post. Hunter already supported Guardian/Squid; Elder Guardian and Glow Squid are explicitly added. A distinct Cook definition is provided in the Jobs fork. No paid-preset content is reproduced verbatim.

## Payout protections and operating limits

The migration proposes max-jobs = 2, paying players at their current Jobs cap (a necessary SePathways rule), no creative/spawner payment, modern placed-block protection, no hopper-funded furnace/brewing payouts, and paid-workstation counts of 5 furnaces, 2 blast furnaces, 2 smokers, 5 brewing stands. Tree Feller/Giga Drill/Super Breaker activity payouts use a 0.2 multiplier. These match relevant options found in the paid preset, while retaining original configuration structures and unrelated settings. No purchased restrictedBlocks.yml, reward/quest/menu files, or shop data are copied. An hourly money cap is deliberately deferred until pay-per-hour data exists.

## Applying to the existing server safely

Simply rebuilding Jobs.jar will **not overwrite existing live Jobs YAML files**. Use the included script to inspect the changes; it reads tuned values from this GitHub fork and applies only economic keys, preserving other settings.

After merging the Jobs PR:

~~~bash
cd ~/ReiGrove/github-src/Jobs
git pull --ff-only

# Read-only preview:
python3 scripts/sefra-tune-live-jobs.py "$LIVE/plugins/Jobs"
~~~

When you are ready to commit the configuration changes, **stop the Minecraft server**, then run:

~~~bash
cd ~/ReiGrove/github-src/Jobs
sudo python3 scripts/sefra-tune-live-jobs.py "$LIVE/plugins/Jobs" --apply

cd ~/ReiGrove/github-src/SePathways
git pull --ff-only
python3 scripts/check-rewards.py
bash scripts/build-staged-plugins.sh both

sudo cp -f "$STAGE/Jobs.jar" "$LIVE/plugins/Jobs.jar"
sudo cp -f "$STAGE/SePathways.jar" "$LIVE/plugins/SePathways.jar"
~~~

The script backs up each existing file under "$LIVE/plugins/Jobs/.sefra-backups/<UTC timestamp>/" first, creates the new Cook job only when absent, and never changes Jobs player or SQLite data. Restart Jobs and SePathways and verify the payouts, action types, EXP per level, per-job caps and anti-exploit behavior in game.

### Validation priorities

Check the Jobs 0.46 multiplier once, not twice; level-9 full XP cap; non-OP natural leveling; Guardian/Elder Guardian/Squid/Glow Squid kills; fishing payouts; replantable crop tracking; woodcutter Tree Feller income; user-placed ore break protection; furnace and hopper restrictions. We need observed activity and money/XP gain rates before calling the high-level pacing balanced.
