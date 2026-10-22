# REPORT-TheIsland

Slot 2. Prod configuration: NetServerMaxTickRate stock (0), tick rate clamp stock,
the five optimizations enabled. The bench launched with the prod line, deploy only via `deploy_map.py`.
Save: 134.2 MB, 152 player profiles. GameThread tid 6204, pid 5096.

NetServerMaxTickRate: stock (0). Actual t/s of P0/P1: **9.99**.
The slot steps were executed manually, one by one, with a bench health check after each one.

## Answers to the watch's questions

**1. How much does a real save cost without players.**

| Metric | Value |
|---|---|
| ticks/s | **9.99** |
| GameThread CPU after start | 0.102 s/s |
| ms CPU per tick (after start) | **10.17** |
| ms CPU per tick (at idle, after a save) | **3.91** |
| total process CPU | 0.06–0.08 s/s |
| world save | every 15 min, freeze ~3.9 s |

As on Genesis, the frame lasts ~100 ms at single-digit CPU milliseconds:
the server is bound by the tick rate, not by computation.

**An important caveat on comparability.** P0/P1 was taken 2 minutes after the world lift,
while the P2 windows — right after the end of a save. After a save the world is "fresh":
actors are reset to the state from the file and tick cheaper: 10.17 → 3.91 ms/tick.
Therefore **P0/P1 and the P2 windows on this map are not directly comparable**; only
P2-A versus P2-B can be compared, as they were taken under one protocol.

**2. Do large bases eat the GameThread through O(n²) overlap.**

| Mode | ms CPU/tick | t/s | CPU GameThread, s/s |
|---|---|---|---|
| overlaptrim off | 4.30 | 9.99 | 0.043 |
| overlaptrim=2 | 3.91 | 9.99 | 0.039 |
| **delta** | **−9.1%** | 0.0% | −9.3% |

Yes, but on TheIsland the effect is 6.5× weaker than on Genesis (−59.0%):
the trim gives 0.39 ms per tick versus 12.97 ms on Genesis. There are even more
overlaps here (527 778 versus 199 380), but they are distributed differently — on Genesis the
contribution comes from components with large lists, not from the total number of events.

**3. How much does the SaveWorld freeze cost.**

| Run | freeze, ms |
|---|---|
| 1 | 3991 |
| 2 | 3866 |

**The ToR threshold of 500 ms is exceeded by a factor of ~7.9.** Task added to the ToR backlog.

## P2 — A/B overlaptrim (300 s windows, both after the end of a save)

Protocol: wait for the start of the autosave, then its end, then measure.

| Hand | ms/tick | t/s | clean window |
|---|---|---|---|
| A — overlap events returned | 4.30 | 9.99 | yes |
| B — overlaptrim=2 | 3.91 | 9.99 | yes |

None of the TheIsland windows landed on a save.

## Censuses

| Metric | Value |
|---|---|
| levels | 104 |
| actors | 76 907 |
| registered tick functions | 286 |
| components | 281 478 |
| ticking components | 268 |
| `AllEnabledTickFunctions` | 3 510 |
| components with `bGenerateOverlapEvents` | 151 091 of 179 980 |
| total overlaps | 527 778 |

`AllEnabledTickFunctions` = 3 510 — the same number as on an empty world.
The heavy ticks come not from the registered functions themselves but from the logic
they invoke; on TheIsland there is almost none of it.

## Profile (steady-state, 60 s, 30 403 samples)

Idle — **96.4% wall**, executable code only 1 093 samples. A light map.

| Share | Symbol |
|---|---|
| 9.97% | `TOctree<UPrimitiveComponent*>::AdvanceToNextIntersectingElement` |
| 5.40% | `TOctree<UPrimitiveComponent*>::ProcessChildren` |
| 2.65% | `FName::InitInternal_FindOrAddNameEntry<char>` |
| 2.38% | `TSet<FFoliageMeshInfo*>::FindId` |
| 2.29% | `TIndexedContainerIterator<TArray<UPrimitiveComponent*>>::operator*` |
| 1.56% | `APrimalDinoCharacter::Tick` |
| 1.46% | `FTickTaskManager::RunTickGroup` |
| 1.28% | `APrimalCharacter::Tick` |
| 1.19% | `FActorTickFunction::ExecuteTick` |
| 1.19% | `FTickTaskManager::StartFrame` |

The comparison with Genesis is fundamental: here there is **neither the Blueprint interpreter
nor `UVictoryCore::ServerOctreeOverlapActors`**. The octree traversal dominates — 15.4%
of executable code, i.e. the fundamental cost of working with space,
not application logic.

## Map conclusion

TheIsland is expensive in object count (527 thousand overlaps) and cheap in tick time.
This confirms that **the cost of large bases is determined not by the number of overlaps,
but by their concentration on individual components** — which is exactly what `overlaptrim` cuts.
---

## A6 — report hygiene (reviewer edit)

### 1. The state in which each census was taken

| Report | Census taken in | What it means |
|---|---|---|
| REPORT-Genesis.md | **restored state** — after `TickProf.overlapall 0`, then `overlaptrim 2` | `overlaptrim 2` does not re-sweep live components, so the overlap and flag numbers refer to the restored state |
| REPORT-TheIsland.md | **restored state** — the same sequence | same |
| REPORT-Fjordur.md | **deploy state** — `overlaptrim 2` from the prod config, `overlapall 0` was not applied | the only census matching the prod configuration |

The censuses are **not directly comparable across maps**: Genesis and TheIsland were taken in a different
state than Fjordur. Within one map the censuses are comparable with each other.

### 2. The spread of the SaveWorld freeze

Across all six runs: 3738, 3866, 3991, 4026, 4308, 4371 ms against the 500 ms threshold.
Spread by the maximum: **×7.5 – ×8.7**. The earlier wording "×8.6" referred
only to Genesis and did not reflect the maximum.

### 3. Footnote on the incomparability of P0/P1

> P0/P1 on all maps was taken ~2 minutes after world readiness, while the P2 windows were
> taken right after the end of the autosave. The absolute values of P0/P1 and of the P2 windows
> are comparable only within one map and one protocol.

### 4. The cost of the autosave operation

> **The autosave adds +15 ms/tick for the duration of the save and causes a freeze of 3.9–4.3 s.**
> On Genesis, in the window captured by the save, the frame cost rose from 9.8 to
> 25.0 ms/tick. The save alone costs more than the rest of the frame.

### 5. The "fresh world" mechanism is a HYPOTHESIS, not an established fact

Observation: right after the autosave the frame is cheaper (TheIsland: 3.91 versus 10.17 ms/tick).
Possible explanations, none verified:
- **actor stasis** — after the save some actors are reset into a "sleeping" state;
- **transient processes** — after a fresh load there are initialization phases that then die down;
- **garbage collection and cleanup** — before the autosave new objects accumulate, after the reset there are fewer of them.

A separate measurement is required: a profile right after the autosave and 10 minutes later,
comparing the shares of `APrimalCharacter::Tick`, `FTickTaskManager::RunTickGroup`, and GC symbols.
**Until then, the "after the save" numbers must not be treated as an improvement of the map.**

### 6. Was there a starting save before P0/P1 — a check against the raw data

Evidence: `*_AntiCorruptionBackup.bak` is created **during world loading**
(a copy of the read .ark), while the `.ark` itself is rewritten only on an actual save.

| Map | launch | RCON ready | P0/P1 window | `.bak` | `.ark` rewritten |
|---|---|---|---|---|---|
| Genesis | 00:32:48 | 00:40:03 | 00:42:26–00:46:46 | 00:37:54 (during load) | first at 01:21:38 |
| TheIsland | 01:33:43 | 01:39:53 | 01:42:13–01:46:32 | 01:37:56 (during load) | first at 02:07 |
| Fjordur | 02:19:19 | 02:26:01 | 02:28:29–02:32:49 | 02:23:59 (during load) | first at 02:38 |

**Conclusion: there was no completed starting save before P0/P1 on any map.**
The waiting for "the end of the starting save" in the Genesis/TheIsland slots was waiting
for file quiescence, not for a save: the `.ark` was not changing at that time.

Consequence: the reviewer's premise that "Genesis waited for the end of a starting save" is **not
supported by the data**. P0/P1 on the three maps was taken in comparable conditions (~2 minutes
after the world lift, with no preceding save). The comparability of the values themselves
is limited by the different contents of the maps, not by different measurement conditions.
