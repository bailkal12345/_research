# REPORT-Genesis

Slot 1. Prod configuration: NetServerMaxTickRate stock (0), tick rate clamp stock,
the five optimizations enabled (fncache, iscache, cachename, nochart, overlaptrim 2).
The bench launched with the prod line from `Saved/Config/WindowsServer/RunServer.cmd`.

NetServerMaxTickRate: stock (0). Actual t/s of P0/P1: **9.99**.
Tick rate clamp: stock (fixclamp 0). CPU measurements — the GameThread, tid 11668,
pid 16396. All windows, except those marked, were taken outside world saves.

## Answers to the watch's questions

**1. How much does a real save cost without players.**

| Metric | Value |
|---|---|
| ticks/s | **9.99** |
| GameThread CPU | 0.098 s/s (9.8% of one core) |
| ms CPU per tick | **9.77** |
| total process CPU | 0.07–0.14 s/s |
| world save | every 15 min (`AutoSavePeriodMinutes=15`), freeze ~4.3 s |

The main point: **the frame lasts ~100 ms but consumes under 10 ms of CPU**. The server is not
compute-bound — it is bound by the tick rate: in total the process
used 7–14% of a core. The t/s limit (~10) is set by padding, not by load.

**2. Do large bases eat the GameThread through O(n²) overlap.**

| Mode | ms CPU/tick | t/s | CPU GameThread, s/s |
|---|---|---|---|
| overlaptrim off | 21.97 | 9.96 | 0.219 |
| overlaptrim=2 | 9.00 | 9.98 | 0.090 |
| **delta** | **−59.0%** | +0.2% | −58.9% |

Yes. On Genesis trimming the overlap lists of components with ≥2 overlaps
removes 12.97 ms per tick — 59% of the frame cost. Ticks/s do not rise, because
the frame is already bottlenecked by padding, not by CPU.

**3. How much does the SaveWorld freeze cost.**

| Run | freeze, ms |
|---|---|
| 1 | 4308 |
| 2 | 4371 |

**The ToR threshold of 500 ms is exceeded by a factor of 8.7.** Both runs are stable (a spread of 63 ms).
Task added to the ToR backlog.

## P2 — A/B overlaptrim (300 s windows, outside saves)

| Window | ms/tick | t/s | note |
|---|---|---|---|
| A-1 | 24.97 | 9.86 | **contaminated by autosave** — excluded from the backlog |
| A-2 | 21.97 | 9.96 | clean |
| B-1 | 14.65 | 9.86 | **contaminated by autosave** — excluded from the backlog |
| B-2 | 9.00 | 9.98 | clean |

As a side observation from the contaminated windows: during a world save the frame cost rises
from 9.8 to 25.0 ms/tick — i.e. **the save itself costs ~15 ms per tick**,
more than the rest of the frame combined.

## Censuses (free data of the matrix)

| Metric | Value |
|---|---|
| levels | 142 |
| actors | 106 255 |
| components | 404 819 |
| ticking components | 1 995 |
| `AllEnabledTickFunctions` | 1 264 462 |
| components with `bGenerateOverlapEvents` | 247 447 of 271 331 |
| total overlaps | 199 380 |

## Profile (steady-state, 60 s, 30 463 samples)

Idle (Sleep/Wait in ntdll) — 83.8% wall. Executable code — 4 932 samples.

| Share | Symbol |
|---|---|
| 7.40% | `UVictoryCore::ServerOctreeOverlapActors` |
| 6.47% | `TOctree<UPrimitiveComponent*>::AdvanceToNextIntersectingElement` |
| 5.76% | `UObjectBaseUtility::IsA` |
| 3.97% | `UObject::execLocalVariable` |
| 3.33% | `TickProf.dll+0x258CF` (the profiler's own overhead) |
| 2.82% | `UObject::execDynamicCast` |
| 2.60% | `UPrimalInventoryComponent::GetItemTemplateQuantity` |
| 2.17% | `UObject::ProcessInternal` |
| 2.13% | `UObject::ProcessContextOpcode` |
| 1.91% | `UObject::execLetBool` |
| 1.89% | `UFunction::Invoke` |
| 1.80% | `UObject::CallFunction` |
| 1.76% | `TOctree<UPrimitiveComponent*>::ProcessChildren` |
| 1.76% | `UObject::execLet` |
| 1.74% | `UObjectPropertyBase::CopyCompleteValueToScriptVM` |
| 1.62% | `UProperty::CopyCompleteValueFromScriptVM` |
| 1.24% | `UPrimalItem::IsValidForCrafting` |

Rolled up by classes: `UObject` (the Blueprint interpreter) **22.8%**,
`UVictoryCore` 7.4%, `TOctree` 8.2%, `UObjectBaseUtility` (IsA) 5.8%,
`UPrimalInventoryComponent`+`UPrimalItem` 3.9%.

The three largest optimization directions on Genesis:
1. **Blueprint interpreter — 22.8%.** The top symbols `execLocalVariable`,
   `execDynamicCast`, `ProcessContextOpcode`, `execLet` are bytecode
   executed every frame. The main reserve.
2. **Octree and `UVictoryCore::ServerOctreeOverlapActors` — 15.7%.** The octree
   is traversed in full, plus AI-overlap calls with `AddUnique` — the known O(n²).
3. **`UObjectBaseUtility::IsA` — 5.8%.** Type checks on the hot path;
   the same technique that already gave −13% on `UStruct::IsChildOf` (iscache).

## Observations on tools and the bench

1. **Autosave contaminates any measurement.** The first Genesis profile was taken
   on top of a world save: all the executable code is serialization
   (`UStruct::SerializeTaggedProperties` 3.81%, `FSaveFileObjectWriter` 2.89%,
   `UWorld::SaveToFile` 0.82%). Measurements without accounting for this are unusable.
2. **`.ark` shrank at the autosave:** 102.72 → 96.93 MB (01:21).
   Related to the trimming of overlap lists and garbage collection; it does not affect loading,
   the file opens normally.
3. **The profiler crash did not reproduce.** Earlier the server died right after
   a profile was taken (twice, with no crash stack and no dump). This time the same profile
   ran cleanly and the server survived. Conclusion: the crash was not tied to the profiler as such,
   but to its landing on a world save.
4. **The slot steps were executed manually, one by one, with a bench health check
   after each one** (`manual.py state|ready|config|idle-after|window|census|profile|saveworld`).
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
