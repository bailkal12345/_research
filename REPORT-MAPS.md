# REPORT-MAPS - TheIsland (slot 2) & Fjordur (slot 3), first watch (merged)

## Summary

- Both maps: server bound by tick rate, not computation (~100 ms frame, single-digit CPU ms). P0/P1 t/s = 9.99 on both.
- `overlaptrim` delta: TheIsland **?9.1%** (3.91 vs 4.30 ms/tick, 0.39 ms/tick saved); Fjordur **?39.0%** (4.30 vs 7.05, 2.75 ms/tick saved) vs Genesis ?59.0%.
- SaveWorld freeze ~3.7-4.4 s vs 500 ms ToR threshold (TheIsland x7.9, Fjordur x8.1).
- TheIsland profile: octree traversal dominates (15.4%); Fjordur: 208 levels, `AllEnabledTickFunctions` 525 271; profile not taken in first watch.
- Cost of large bases is set by overlap concentration on individual components, not total overlap count.

## Fjordur:

Slot 3. Prod configuration: NetServerMaxTickRate stock (0), tick rate clamp stock, five optimizations enabled. Bench launched with the prod line, deploy only via `deploy_map.py`. Save: 98.1 MB, 250 player profiles, 414 files. GameThread tid 14148, pid 16888. Steps executed manually with a bench health check after each.

**Q1 - cost of a real save without players:** ticks/s 9.99; GameThread CPU (240 s window) 0.090 s/s; ms CPU/tick (240 s window) **9.00**; after a save **4.30**; total process CPU 0.04-0.07 s/s; world save every 15 min, freeze ~3.9 s.

**Q2 - O(n^2) overlap of large bases:** overlaptrim off 7.05 ms/tick / 9.97 t/s / 0.070 s/s; overlaptrim=2 4.30 / 9.99 / 0.043; delta **?39.0%** t/s +0.2%, GameThread ?38.6%. Yes - the trim removes 2.75 ms per tick; smaller than Genesis (?59.0%), larger than TheIsland (?9.1%).

**Q3 - SaveWorld freeze:** 4026 and 3738 ms ? **ToR 500 ms threshold exceeded x~8.1**; task added to ToR backlog.

P2 - A/B overlaptrim (300 s windows, both after the end of a save, none landed on a save): A (overlap events returned) 7.05 / 9.97, clean; B (overlaptrim=2) 4.30 / 9.99, clean.

Census (deploy state): levels 208, actors 79 122, registered tick functions 468, components 327 161, ticking components 475, `AllEnabledTickFunctions` **525 271**, components with `bGenerateOverlapEvents` 4 594 of 206 502, total overlaps 326 946. `AllEnabledTickFunctions` is an order of magnitude above TheIsland (3 510) and comparable to Genesis (1 264 462) - the 208-level cave system yields many sublevels while only 475 components tick. After `overlaptrim 2`, the flag remained on 4 594 of 206 502 components (removed from 98%, almost all with 1-2 overlaps each).

Profile: **not taken** - the only uncompleted item of slot 3; the 60-min slot ceiling fit only without it (the profiler crashed the server twice on Genesis and needs a separate time reserve). Genesis and TheIsland profiles attached.

Map conclusion: most multi-level map (208 levels), but ms/tick noticeably lower than Genesis - the registered-tick-function count alone does not set frame cost; Genesis is expensive because of the logic invoked (Blueprint interpreter, VictoryCore).

## The Island:

Slot 2. Prod configuration: NetServerMaxTickRate stock (0), tick rate clamp stock, five optimizations enabled. Bench launched with the prod line, deploy only via `deploy_map.py`. Save: 134.2 MB, 152 player profiles. GameThread tid 6204, pid 5096. Steps executed manually with a bench health check after each.

**Q1 - cost of a real save without players:** ticks/s 9.99; GameThread CPU after start 0.102 s/s; ms CPU/tick after start **10.17**; at idle after a save **3.91**; total process CPU 0.06-0.08 s/s; world save every 15 min, freeze ~3.9 s. P0/P1 was taken 2 min after world lift, P2 windows right after a save (the world is "fresh", ticks cheaper) - **P0/P1 and P2 windows on this map are not directly comparable**; only P2-A vs P2-B.

**Q2 - O(n^2) overlap of large bases:** overlaptrim off 4.30 ms/tick / 9.99 t/s / 0.043 s/s; overlaptrim=2 3.91 / 9.99 / 0.039; delta **?9.1%**, t/s 0.0%, GameThread ?9.3%. Yes, but 6.5x weaker than Genesis (?59.0%): 0.39 ms/tick vs 12.97 on Genesis. There are even more overlaps here (527 778 vs 199 380), but they are distributed differently - Genesis's cost comes from components with large lists, not the total number of events.

**Q3 - SaveWorld freeze:** 3991 and 3866 ms ? **ToR 500 ms threshold exceeded x~7.9**; task added to ToR backlog.

P2 - A/B overlaptrim (300 s windows, protocol: wait for autosave start, then end, then measure; none landed on a save): A 4.30 / 9.99, clean; B 3.91 / 9.99, clean.

Census (restored state): levels 104, actors 76 907, registered tick functions 286, components 281 478, ticking components 268, `AllEnabledTickFunctions` 3 510, components with `bGenerateOverlapEvents` 151 091 of 179 980, total overlaps 527 778. `AllEnabledTickFunctions` = 3 510, the same as on an empty world - the heavy ticks come from the logic the functions invoke, and TheIsland has almost none.

Profile (steady-state, 60 s, 30 403 samples): idle 96.4% wall, executable code 1 093 samples. `TOctree<UPrimitiveComponent*>::AdvanceToNextIntersectingElement` 9.97%, `TOctree<UPrimitiveComponent*>::ProcessChildren` 5.40%, `FName::InitInternal_FindOrAddNameEntry<char>` 2.65%, `TSet<FFoliageMeshInfo*>::FindId` 2.38%, `TIndexedContainerIterator<TArray<UPrimitiveComponent*>>::operator*` 2.29%, `APrimalDinoCharacter::Tick` 1.56%, `FTickTaskManager::RunTickGroup` 1.46%, `APrimalCharacter::Tick` 1.28%, `FActorTickFunction::ExecuteTick` 1.19%, `FTickTaskManager::StartFrame` 1.19%. Unlike Genesis: **neither the Blueprint interpreter nor `UVictoryCore::ServerOctreeOverlapActors`**; octree traversal dominates (15.4% of executable code) - the fundamental cost of spatial work, not application logic.

Map conclusion: expensive in object count (527 thousand overlaps), cheap in tick time - confirming **cost of large bases is determined not by the number of overlaps but by their concentration on individual components**, exactly what `overlaptrim` cuts.

## A6 - report hygiene (reviewer edit; identical in both source reports, kept once)

### 1. State of each census

| Report | Census taken in | Meaning |
|---|---|---|
| REPORT-Genesis.md | **restored state** - after `TickProf.overlapall 0`, then `overlaptrim 2` | `overlaptrim 2` does not re-sweep live components, so overlap/flag numbers refer to the restored state |
| REPORT-TheIsland.md | **restored state** - same sequence | same |
| REPORT-Fjordur.md | **deploy state** - `overlaptrim 2` from prod config, `overlapall 0` not applied | only census matching the prod configuration |

Censuses are **not directly comparable across maps** (Genesis/TheIsland taken in a different state than Fjordur); within one map they are comparable.

### 2. SaveWorld freeze spread

All six runs: 3738, 3866, 3991, 4026, 4308, 4371 ms against the 500 ms threshold. Spread by maximum: **x7.5 - x8.7** (the earlier "x8.6" referred only to Genesis and did not reflect the maximum).

### 3. Incomparability of P0/P1

P0/P1 on all maps was taken ~2 min after world readiness; P2 windows right after the autosave ended. Absolute values are comparable only within one map and one protocol.

### 4. Autosave cost

The autosave adds **+15 ms/tick** for the save duration and freezes 3.9-4.3 s. On Genesis the frame cost in the captured-save window rose from 9.8 to 25.0 ms/tick - the save alone costs more than the rest of the frame.

### 5. "Fresh world" mechanism - HYPOTHESIS

After the autosave the frame is cheaper (TheIsland: 3.91 vs 10.17 ms/tick). Unverified candidates: actor stasis (actors reset to "sleeping"), transient init processes, garbage/cleanup. Required: a profile right after the autosave and 10 min later comparing `APrimalCharacter::Tick`, `FTickTaskManager::RunTickGroup`, GC shares. Until then, "after the save" numbers must not be treated as a map improvement.

### 6. No starting save before P0/P1

`*_AntiCorruptionBackup.bak` is created during world loading (copy of the read .ark); the `.ark` is rewritten only on an actual save.

| Map | launch | RCON ready | P0/P1 window | `.bak` | `.ark` rewritten |
|---|---|---|---|---|---|
| Genesis | 00:32:48 | 00:40:03 | 00:42:26-00:46:46 | 00:37:54 (during load) | first at 01:21:38 |
| TheIsland | 01:33:43 | 01:39:53 | 01:42:13-01:46:32 | 01:37:56 (during load) | first at 02:07 |
| Fjordur | 02:19:19 | 02:26:01 | 02:28:29-02:32:49 | 02:23:59 (during load) | first at 02:38 |

**No completed starting save before P0/P1 on any map.** The "waiting for the end of the starting save" in the Genesis/TheIsland slots was waiting for file quiescence. The reviewer's premise that "Genesis waited for the end of a starting save" is **not supported by the data**: P0/P1 was taken in comparable conditions (~2 min after lift-off, no preceding save); comparability is limited only by differing map contents.
