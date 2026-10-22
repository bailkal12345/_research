# REPORT-B3 — census in hand-A state + profile (Fjordur)

Slot B-3 of directive doit2.txt. Map Fjordur, deploy from `c:/saves` via `deploy_map.py`.
T0 = 13:39:54 (RCON responsive). GameThread tid 17672, pid 14996.
Prod configuration: NetServerMaxTickRate stock, fixclamp 0, fncache 1, iscache 1,
cachename 1, nochart 1, overlaptrim 2, bAllowConcurrentTicks 0.

Order per protocol: wait for the autosave → `TickProf.overlapall 0` → census →
60 s profile **as the last step**. The profile ran; the server survived.

## Census — STATE: RESTORED

Taken 2.5 minutes after `TickProf.overlapall 0`, i.e. **the restored
state**, not the deploy state. This is labeled explicitly, as the directive requires.

| Metric | Restored (now) | Deploy state (first watch) |
|---|---|---|
| levels | 208 | 208 |
| actors | 79 059 | 79 122 |
| registered tick functions | 463 | 468 |
| components | 327 834 | 327 161 |
| ticking components | 468 | 475 |
| `AllEnabledTickFunctions` | 525 109 | 525 271 |
| components with `bGenerateOverlapEvents` | **206 780 of 206 780 (100%)** | **4 594 of 206 502 (2.2%)** |
| total overlaps | 325 896 | 326 946 |

**Key observation: the total number of overlaps barely changed**
(325 896 versus 326 946, a 0.3% difference), even though the flag was removed from 97.8% of components.

This is a direct confirmation of the first watch's conclusion: **`overlaptrim` removes not the number of
overlaps but their concentration on individual components.** The trimmed lists
refill with events, and the total counter returns to its previous value —
the gain comes only from the trimming being cheaper, for now, than re-`AddUnique`
in `BeginComponentOverlap` (see RE2.md, A2).

## Profile (steady-state, 60 s, 31 039 samples)

Idle (Sleep/Wait in ntdll) — **95.1% wall**. Executable code — 1 518 samples.
Taken in the restored state: the `bGenerateOverlapEvents` flag is on for all
components, so the cost of `UpdateOverlaps` here is at its maximum.

| Share | Symbol |
|---|---|
| 5.86% | `FArchiveRealtimeGC::PerformReachabilityAnalysis` |
| 4.55% | `IncrementalPurgeGarbage` |
| 3.56% | `TOctree<UPrimitiveComponent*>::AdvanceToNextIntersectingElement` |
| 3.49% | `FName::InitInternal_FindOrAddNameEntry<char>` |
| 2.24% | `CollectGarbage` |
| 2.11% | `TSet<FMaterialRenderProxy*>::Remove` |
| 2.04% | `TOctree<UPrimitiveComponent*>::ProcessChildren` |
| 1.71% | `FTickTaskLevel::QueueNewlySpawned` |
| 1.65% | `FTickTaskManager::RunTickGroup` |
| 1.38% | `TGraphTask<FTickTaskSequencer::FTickFunctionTask>::ExecuteTask` |
| 1.25% | `AActor::GetWorld` |
| 1.19% | `FMallocBinned::FreeInternal` |
| 0.86% | `APrimalDinoCharacter::Tick` |

### Main conclusion: the third "concentration" point — GARBAGE COLLECTION

**The GC cluster gives ~16% of executable code**:
`PerformReachabilityAnalysis` 5.86 + `IncrementalPurgeGarbage` 4.55 + `CollectGarbage`
2.24 + `TSet<FMaterialRenderProxy*>::Remove` 2.11 + `FMallocBinned::FreeInternal` 1.19.

This is the **dominant** cluster on Fjordur and it is absent from the tops of the two other maps.
`TSet<FMaterialRenderProxy*>::Remove` next to GC — a characteristic sign of
reachability-graph traversal passing through materials.

## Summary: three maps — three different profiles

| Dominant cluster | Genesis | TheIsland | Fjordur |
|---|---|---|---|
| 1st | Blueprint interpreter **22.8%** | octree traversal **15.4%** | **garbage collection ~16%** |
| 2nd | `UVictoryCore::ServerOctreeOverlapActors` 7.4% | `FName` 2.7% | `FName` 3.5% |
| 3rd | `IsA` 5.8% | `FSet<FFoliageMeshInfo*>` 2.4% | octree traversal 5.6% |
| idle | 83.8% wall | 96.4% wall | 95.1% wall |
| executable code | 4932 samples | 1093 | 1518 |

**Practical conclusion for the ToR: there is no single "hot spot" for all maps.**
Any optimization aimed at one map will have no effect on another:

* optimizing the BP interpreter hits Genesis and does not touch TheIsland;
* optimizing GC hits Fjordur — and this is **not covered by any of the five current
  patches**, i.e. it is an **unclaimed niche**;
* optimizing overlaps (`overlaptrim`) works on all three, but with a different
  effect: −59.0% / −9.1% / −39.0%.

## What this slot closed

1. **The third "concentration" point is closed:** Fjordur is GC, not overlaps
   and not Blueprint.
2. **The only open item of slot 3 of the first watch is closed:** the Fjordur profile
   was taken and symbolized.
3. The census was obtained in the state required by protocol, with an explicit label.
4. The mechanism of the `overlaptrim` gain confirmed: the total number of overlaps
   does not drop; the gain is in the cost of processing them.

## Caveats

1. The profile was taken **in the restored state** (100% of components with the flag),
   not in the deploy state (2.2%). To evaluate the contribution of `overlaptrim`,
   both states need profiling — only one was taken here.
2. The ms/tick windows in this slot **were not taken** — the slot, per protocol, was for the census
   and profile.
3. The profile reflects a state roughly 20 minutes after the world lift;
   the GC contribution depends on the phase of the garbage collection cycle and may vary between runs.
4. One run, no player.
