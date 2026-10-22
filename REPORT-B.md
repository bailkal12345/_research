# REPORT-B - Slots B-1/B-2/B-3 (directive doit2.txt, merged)

## Summary

- B-1 (TheIsland, T0 12:03:45): fresh-world decay measured; settled cost of a real save without players = **4.31 ms/tick**, fresh window = **21.97 ms/tick** (5.1x). Explains the first watch's P0/P1 (10.17) as transient regime.
- B-2 (Genesis, T0 12:29:36): 3 of 5 optimizations attributed (fncache ?3.91, iscache ?5.08, cachename ?4.67 ms/tick), but contributions are non-additive / drift-contaminated (+-1.0 ms/tick) - must not be used for ToR budgeting. Genesis settled = 7.04 ms/tick. `overlaptrim 2` shrank Genesis.ark by ?6 204 730 bytes (?5.8%).
- B-3 (Fjordur, T0 13:39:54): census + profile in restored state. Third concentration point closed: **GC ~16% of executable code** is Fjordur's dominant cluster; no single hot spot across the three maps.

## Slot B1: decay curve (TheIsland)

Slot B-1 of doit2.txt. Map TheIsland, save 134.2 MB, 250 profiles. Deploy from `c:/saves` via `deploy_map.py`, prod launch line. T0 = 12:03:45 (RCON responsive). GameThread tid 5436, pid 2320. Config before T0: NetServerMaxTickRate stock, fixclamp 0, fncache 1, iscache 1, cachename 1, nochart 1, overlaptrim 2, bAllowConcurrentTicks 0.

| Window | moment | ms CPU/tick | t/s | CPU GameThread, s/s | status |
|---|---|---|---|---|---|
| 1 | T0+2...4 | **21.97** | 9.07 | 0.199 | clean |
| 2 | T0+5...7 | **7.76** | 9.07 | 0.070 | clean |
| 3 | T0+8...10 | **5.35** | 8.76 | 0.047 | clean (conditional - see caveats) |
| 4 | T0+11...13 | (6.21) | 8.81 | 0.055 | **contaminated - discarded** |
| 5 | after autosave | **4.31** | 9.07 | 0.039 | clean |

Formula: ms CPU/tick = (thread CPU, s/s) / (t/s) x 1000 (0.199 / 9.07 x 1000 = 21.97).

- Fresh world is more expensive by **5.1x**: 21.97 vs settled 4.31 ms/tick; 4.5x more than P0/P1 of the first watch on this map (10.17), which therefore also fell into the not-yet-settled regime.
- Decay is quick and exponential: 21.97 ? 7.76 ? 5.35; plateau by T0+8...10; half of the cost decays in ~2.5 min after lift-off. Steps: T0+2...4?T0+5...7 **?64.7%**; T0+5...7?T0+8...10 **?31.1%**; ?settled **?19.4%**.
- ToR worst case = **21.97 ms/tick** (T0+2...4): a freshly lifted server without players already exceeds the ToR budget of 60 t/s (?16.6 ms/tick); only the settled state fits.
- Closes the first watch's P0/P1 anomaly: P0/P1 was taken at 01:42-01:46 (~2 min after readiness), in the maximal decay zone - a transient regime, not "cost of the map". Consequence: first-watch P0/P1 (Genesis 9.77, TheIsland 10.17, Fjordur 9.00) are transient costs; settled is 1.8-2.4x cheaper, and the settled answer to "real save without players" is **4.31 ms/tick**, not 10.17.
- Cross-check (A6 item 6): no completed starting save before P0/P1 on any map, so the decay is explained not by a save but by the world's own warm-up.
- Caveats: (1) window 4 discarded - landed on the autosave; curve built from 3 clean windows before + 1 after. (2) Decay mechanism unestablished - hypotheses: actor stasis, transient init, garbage (A6 item 5). (3) One map, one run; needs the same windows on Genesis and Fjordur. (4) t/s sagged to 8.76 in window 3 - likely early autosave effect; cleanliness conditional.

## Slot B2: attribution of the five optimizations (Genesis)

Slot B-2 of doit2.txt. Map Genesis, deploy from `c:/saves` via `deploy_map.py`. T0 = 12:29:36 (RCON responsive). GameThread tid 6588, pid 2612. Prod config verified before first window (same list as B1). Protocol: wait for end of autosave ? 240 s window ? check "contaminated" flag. **All windows clean.**

| Optimization | off, ms/tick | on, ms/tick | contribution | t/s |
|---|---|---|---|---|
| **baseline (all 5 on)** | - | **7.04** | - | 9.98 |
| `fncache` | 10.95 | 7.04 | **?3.91 ms (?35.7%)** | 9.99 |
| `iscache` | 14.07 | 8.99 | **?5.08 ms (?36.1%)** | 9.99 |
| `cachename` | 11.72 | 7.05 | **?4.67 ms (?39.8%)** | 10.00 |
| `nochart` | **not completed** | - | - | - |
| `overlaptrim` | **not completed** | - | - | - |

Order: baseline ? fncache(0/1) ? iscache(0/1) ? cachename(0/1). `nochart` and `overlaptrim` unfinished: the 60-min slot ceiling expired at 13:29, last window closed 13:32; not replaced by estimates.

**Main caveat - drift between windows.** Same configuration (all 5 on) measured three times: 12:42-12:47 = 7.04; 13:12-13:17 (after returning iscache) = 8.99; 13:27-13:32 (after returning cachename) = 7.05. Spread **+-1.0 ms/tick (up to +28%)**, comparable to the contributions. Contributions over adjacent pairs (off ? on back-to-back) are the most reliable; the **sum is not** (3.91 + 5.08 + 4.67 = **13.66 ms/tick**, contradicting the earlier-run profile showing the three caches together gave about ?7%; "all off" was never measured). Causes (neither verified): (1) non-additive caches - `FindFunctionByName` and `IsChildOf` both serve Blueprint calls, leave-one-out overstates; (2) +1 ms/tick drift smears the difference. Until a re-run with alternating order, these numbers **must not be used for ToR budget planning**.

**Cache counters (13:32, after all toggles):** `fncache` 45 336 557 hits / 4 678 misses = 99.990%; `iscache` 957 894 518 / 1 857 = 99.9998%. Per A1: `iscache` caches `UStruct::IsChildOf` (3411 call sites + 394 inline copies), whereas `IsA` (profile share 5.8%) has 1870 sites, **none** covered by `iscache` - the iscache contribution comes from `IsChildOf`, not `IsA`.

**Diff of .ark (rollback-protocol item 1.1):** Genesis.ark 107 713 327 bytes at B-2 start (12:30), sha256 (first 24 chars) `5a26823265e4c77e219f7491` ? **101 508 597** at B-2 end (13:32), sha256 `15699c5ed86df02c7d04bfcd`; **?6 204 730 bytes (?5.8%)**. Cause: `overlaptrim 2` at start disabled `bGenerateOverlapEvents` on **13 783 components** and freed **111 745 overlap records**; the autosave wrote the trimmed state. File stays valid; Fjordur.ark and TheIsland.ark unchanged (hashes match) - side effect local to the map.

Reconciliation with first watch: settled Genesis = **7.04 ms/tick** vs P0/P1 9.77 taken 2 min after lift-off (decay zone, see B1) - **1.8x cheaper** than previously reported.

Not delivered: `nochart` unattributed (expected small, not measured); `overlaptrim` unattributed on Genesis (first watch measured ?59.0%, 21.97 ? 9.00 ms/tick, but in a transient regime and different protocol); combined all-five-off effect unmeasured (additivity unverified); drift cause unestablished; one run, one map, no player.

Closed: attribution of 3/5 optimizations on a real archived save, with byte-level `.ark` capture before/after and hit/miss counter verification.

## Slot B3: census in hand-A state + profile (Fjordur)

Slot B-3 of doit2.txt. Map Fjordur, deploy from `c:/saves` via `deploy_map.py`. T0 = 13:39:54 (RCON responsive). GameThread tid 17672, pid 14996. Prod config as B1. Protocol order: wait for autosave ? `TickProf.overlapall 0` ? census ? 60 s profile last; the profile ran, the server survived. **The ms/tick windows were not taken** - the slot was for the census and profile.

Census taken 2.5 min after `TickProf.overlapall 0` - **STATE: RESTORED** (labeled explicitly as the directive requires):

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

Key observation: total overlaps barely changed (325 896 vs 326 946, 0.3%) though the flag was removed from 97.8% of components - direct confirmation that **`overlaptrim` removes not the number of overlaps but their concentration on individual components**; trimmed lists refill, the gain comes only from trimming being cheaper than re-`AddUnique` in `BeginComponentOverlap` (RE2.md, A2).

Profile (steady-state, 60 s, 31 039 samples; restored state, so `UpdateOverlaps` cost is maximal): idle 95.1% wall, executable code 1 518 samples. `FArchiveRealtimeGC::PerformReachabilityAnalysis` 5.86%, `IncrementalPurgeGarbage` 4.55%, `TOctree<UPrimitiveComponent*>::AdvanceToNextIntersectingElement` 3.56%, `FName::InitInternal_FindOrAddNameEntry<char>` 3.49%, `CollectGarbage` 2.24%, `TSet<FMaterialRenderProxy*>::Remove` 2.11%, `TOctree<UPrimitiveComponent*>::ProcessChildren` 2.04%, `FTickTaskLevel::QueueNewlySpawned` 1.71%, `FTickTaskManager::RunTickGroup` 1.65%, `TGraphTask<FTickTaskSequencer::FTickFunctionTask>::ExecuteTask` 1.38%, `AActor::GetWorld` 1.25%, `FMallocBinned::FreeInternal` 1.19%, `APrimalDinoCharacter::Tick` 0.86%.

**Main conclusion: third concentration point is GC.** GC cluster ? 16% of executable code (`PerformReachabilityAnalysis` 5.86 + `IncrementalPurgeGarbage` 4.55 + `CollectGarbage` 2.24 + `TSet<FMaterialRenderProxy*>::Remove` 2.11 + `FMallocBinned::FreeInternal` 1.19) - dominant on Fjordur and absent from the other two maps' tops; `TSet<FMaterialRenderProxy*>::Remove` signals reachability traversal through materials.

Three maps - three different profiles:

| | Genesis | TheIsland | Fjordur |
|---|---|---|---|
| 1st cluster | Blueprint interpreter **22.8%** | octree traversal **15.4%** | **GC ~16%** |
| 2nd | `UVictoryCore::ServerOctreeOverlapActors` 7.4% | `FName` 2.7% | `FName` 3.5% |
| 3rd | `IsA` 5.8% | `FSet<FFoliageMeshInfo*>` 2.4% | octree traversal 5.6% |
| idle | 83.8% wall | 96.4% wall | 95.1% wall |
| executable code | 4932 samples | 1093 | 1518 |

ToR consequence: no single hot spot for all maps. BP interpreter hits Genesis only; GC hits Fjordur and is **not covered by any of the five patches** (unclaimed niche); `overlaptrim` works on all three with different effect: ?59.0% / ?9.1% / ?39.0%.

Closed: third concentration point (Fjordur = GC, not overlaps/Blueprint); the only open item of first-watch slot 3 (Fjordur profile taken and symbolized); protocol-required census with explicit label; `overlaptrim` mechanism confirmed.

Caveats: (1) profile in restored state only (100% flagged); evaluating `overlaptrim` needs both states profiled. (2) Profile ~20 min after world lift; GC share depends on GC-cycle phase, varies between runs. (3) One run, no player.
