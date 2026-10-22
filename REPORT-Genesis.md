# REPORT-Genesis

Slot 1. Prod configuration: NetServerMaxTickRate stock (0), tick rate clamp stock (fixclamp 0), the five optimizations enabled (fncache, iscache, cachename, nochart, overlaptrim 2). Launched with the prod line from `Saved/Config/WindowsServer/RunServer.cmd`.

NetServerMaxTickRate: stock (0). Actual t/s of P0/P1: **9.99**. Tick rate clamp: stock. CPU measurements: GameThread, tid 11668, pid 16396. All windows except those marked were taken outside world saves.

## Answers to the watch's questions

**1. Cost of a real save without players.**

| Metric | Value |
|---|---|
| ticks/s | **9.99** |
| GameThread CPU | 0.098 s/s (9.8% of one core) |
| ms CPU per tick | **9.77** |
| total process CPU | 0.07-0.14 s/s |
| world save | every 15 min (`AutoSavePeriodMinutes=15`), freeze ~4.3 s |

Main point: **the frame lasts ~100 ms but consumes under 10 ms of CPU** - not compute-bound but tick-rate-bound; the whole process used 7-14% of a core. The ~10 t/s limit is set by padding, not load.

**2. Do large bases eat the GameThread through O(n^2) overlap.**

| Mode | ms CPU/tick | t/s | CPU GameThread, s/s |
|---|---|---|---|
| overlaptrim off | 21.97 | 9.96 | 0.219 |
| overlaptrim=2 | 9.00 | 9.98 | 0.090 |
| **delta** | **-59.0%** | +0.2% | -58.9% |

Yes: trimming overlap lists of components with >=2 overlaps removes 12.97 ms per tick - 59% of frame cost. t/s does not rise (frame is padding-bound, not CPU-bound).

**3. SaveWorld freeze cost.**

Runs: 4308 and 4371 ms (spread 63 ms). **The ToR threshold of 500 ms is exceeded by a factor of 8.7.** Task added to the ToR backlog.

## P2 - A/B overlaptrim (300 s windows, outside saves)

| Window | ms/tick | t/s | note |
|---|---|---|---|
| A-1 | 24.97 | 9.86 | **contaminated by autosave** - excluded from backlog |
| A-2 | 21.97 | 9.96 | clean |
| B-1 | 14.65 | 9.86 | **contaminated by autosave** - excluded from backlog |
| B-2 | 9.00 | 9.98 | clean |

Side observation from the contaminated windows: during a world save the frame cost rises from 9.8 to 25.0 ms/tick - **the save itself costs ~15 ms per tick**, more than the rest of the frame combined.

## Censuses (free data of the matrix)

levels 142; actors 106 255; components 404 819; ticking components 1995; `AllEnabledTickFunctions` 1 264 462; components with `bGenerateOverlapEvents` 247 447 of 271 331; total overlaps 199 380.

## Profile (steady-state, 60 s, 30 463 samples)

Idle (Sleep/Wait in ntdll) 83.8% wall; executable code 4932 samples.

| Share | Symbol |
|---|---|
| 7.40% | `UVictoryCore::ServerOctreeOverlapActors` |
| 6.47% | `TOctree<UPrimitiveComponent*>::AdvanceToNextIntersectingElement` |
| 5.76% | `UObjectBaseUtility::IsA` |
| 3.97% | `UObject::execLocalVariable` |
| 3.33% | `TickProf.dll+0x258CF` (profiler's own overhead) |
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

Rolled up by classes: `UObject` (Blueprint interpreter) **22.8%**, `UVictoryCore` 7.4%, `TOctree` 8.2%, `UObjectBaseUtility` (IsA) 5.8%, `UPrimalInventoryComponent`+`UPrimalItem` 3.9%.

Three largest optimization directions on Genesis: (1) Blueprint interpreter 22.8% - the main reserve; (2) octree + `ServerOctreeOverlapActors` 15.7% - full octree traversal plus AI-overlap calls with `AddUnique`, the known O(n^2); (3) `IsA` 5.8% - the technique that already gave -13% on `UStruct::IsChildOf` (iscache).

## Observations on tools and the bench

1. **Autosave contaminates any measurement.** The first Genesis profile was taken on top of a world save: all executable code is serialization (`UStruct::SerializeTaggedProperties` 3.81%, `FSaveFileObjectWriter` 2.89%, `UWorld::SaveToFile` 0.82%). Measurements ignoring this are unusable.
2. `.ark` shrank at the autosave: 102.72 -> 96.93 MB (01:21); related to overlap trimming and GC; loading unaffected.
3. **The profiler crash did not reproduce** - earlier the server died right after a profile (twice, no crash stack, no dump); this time it survived. Conclusion: the crash was tied to the profile landing on a world save, not to the profiler as such.
4. Slot steps executed manually, one by one, bench health check after each (`manual.py state|ready|config|idle-after|window|census|profile|saveworld`).

## A6 - report hygiene (reviewer edit)

### Census states

| Report | Census taken in | Meaning |
|---|---|---|
| REPORT-Genesis.md | **restored state** - `TickProf.overlapall 0`, then `overlaptrim 2` | `overlaptrim 2` does not re-sweep live components; overlap/flag numbers refer to the restored state |
| REPORT-TheIsland.md | **restored state** - same sequence | same |
| REPORT-Fjordur.md | **deploy state** - `overlaptrim 2` from prod config, `overlapall 0` not applied | the only census matching the prod configuration |

Censuses are **not directly comparable across maps** (Genesis/TheIsland taken in a different state than Fjordur); within one map they are comparable.

### SaveWorld freeze spread

Across all six runs: 3738, 3866, 3991, 4026, 4308, 4371 ms vs the 500 ms threshold. Spread by maximum: **x7.5 - x8.7** (the earlier "x8.6" wording referred only to Genesis, not the maximum).

### P0/P1 comparability footnote

P0/P1 on all maps was taken ~2 minutes after world readiness; P2 windows right after the autosave. Absolute values comparable only within one map and one protocol.

### Autosave cost

**The autosave adds +15 ms/tick for the duration of the save and causes a freeze of 3.9-4.3 s** (on Genesis: frame 9.8 -> 25.0 ms/tick in the window captured by the save; the save alone costs more than the rest of the frame).

### "Fresh world" mechanism - a HYPOTHESIS, not an established fact

Right after the autosave the frame is cheaper (TheIsland: 3.91 vs 10.17 ms/tick). Unverified explanations: actor stasis after the save; transient initialization processes; GC/cleanup (objects accumulate before save, fewer after). A separate measurement is required (profile right after save and 10 min later, comparing `APrimalCharacter::Tick`, `FTickTaskManager::RunTickGroup`, GC symbols). **Until then, "after save" numbers must not be treated as an improvement of the map.**

### Starting save before P0/P1 - checked against raw data

`*_AntiCorruptionBackup.bak` is created **during world loading** (a copy of the read .ark); the `.ark` itself is rewritten only on an actual save.

| Map | launch | RCON ready | P0/P1 window | `.bak` | `.ark` rewritten |
|---|---|---|---|---|---|
| Genesis | 00:32:48 | 00:40:03 | 00:42:26-00:46:46 | 00:37:54 (during load) | first at 01:21:38 |
| TheIsland | 01:33:43 | 01:39:53 | 01:42:13-01:46:32 | 01:37:56 (during load) | first at 02:07 |
| Fjordur | 02:19:19 | 02:26:01 | 02:28:29-02:32:49 | 02:23:59 (during load) | first at 02:38 |

**Conclusion: no completed starting save before P0/P1 on any map.** The waiting in the Genesis/TheIsland slots was file quiescence, not a save; the reviewer's premise is **not supported by the data**. Comparability of the values is limited by different map contents, not different measurement conditions.

## Dense phase study (phases)

Date 20.10.2026: offline analysis of existing artifacts (no patches, no live boots). Tools: TickProf `.bin/.ret/.wait` profile analysis + `.pdata` bounds (173 540 functions) + PDB names (Ghidra function dump of `/v361_ShooterGameServer.exe`, MD5 path = our Server1 exe, 222 401 functions, verified by anchors: GetMaxTickRate@0x253b1c0, SetActorTickEnabled@0x24696b0, AdvanceToNextIntersectingElement@0x276a0b0, size 537 = the PDB size). Judge-grade absolute numbers only from external Python (plugin busy/ms/tick inflated x1.9-2.4; plugin series used relatively - the distortion is multiplicative, the "CPU-bound vs blocked" diagnosis is preserved).

### Phenomenon No. 1. Accumulative phases (ms/tick 36->93 ms, decay 1-5.5 min, present without a player)

Data: TickProf.log, boot #39 of 20.10 (07:19:26-12:55, Genesis): 5160 mon lines, 21 save cycles, 30 detected phases (t/s<45 for >=3 lines). The first 8 phases are BEFORE any player connection (first login per SrvDiag 09:34:32).

Facts:
1. Key phase 08:49:04-08:50 series (full lines, 1 Hz): ramp-up busy 60->89% and ms/tick 11->16 ms with a FREE frame of 16 ms (t/s still 59) over ~8 s; plateau t/s 21-27, frm~36-46 ms, busy 96-103%, ~1 min; release: t/s jumps to 57-60 instantly, ms/tick stays 15-17 ms and linearly decays to 3-4 over ~44 s (busy 101->65->21%) - a "residual" load band 15->3 ms/tick at full 60 t/s. Shape symmetric: rise ~8-10 s, plateau 60-90 s, decay 30-45 s - not a single tick spike but an INCREASE in the cost of EVERY tick over 1.5-2 min.
2. Cadence of phase starts (empty world, mon 07:48-08:56): 07:48:59, 07:56:30, 08:11:35, 08:19:12, 08:26:59, 08:34:03, 08:41:40, 08:49:09 - intervals 7.5 / 15 / 7.6 / 7.8 / 7.1 / 7.6 / 7.5 min. Same periodicity in other empty boots of the same day: 15:08:51->15:15:51 (7.0m), 15:31:26->15:38:16 (6.8m), 15:59:35->16:06:42 (7.1m)->16:14:14 (7.5m). Gaps are multiples of 15 min -> the true period is 7.5-8 min (every second event sometimes merges / is masked).
3. No save linkage: of 12 mid-session phases - 0 starts within +/-90 s of save markers; the 21 saves (~every 15.3 min, ~3 s per wall marker) fell inside 2 phases as random coincidences. A save otherwise safe: mon lines with save=saving show the same profile.
4. Separate kind - multi-second stalls of a SINGLE frame: frame_ms 1177-1687 ms at t/s=0: 08:52:59 (busy 99%), 08:53:07 (busy 0% !), 10:05 (1656 ms, busy 93%), 09:58 (344 ms), 12:37:59 (404 ms, busy 96%). The "busy=0%" case = a pure BLOCK of the thread (not work) for 1.7 s.
5. Early warm-up 07:27-07:46: t/s strictly 29.8+/-0.1, frame exactly 33.0 ms, busy 24-51% - NOT a phase: default pacing of maxfps 30 (`TickProf.maxfps 60` applied only at 07:48 -> immediately 58-59 t/s). The "shaking" of the first 20 min is a config artifact.
6. Typology (by plugin busy, ~x2 underestimation of real CPU): CPU-bound phases busy 96-103% => external ~(43-50)% of one core, ~28 phases - the majority; BLOCKED phases (busy<60%): up to 9 short ones (the 09:59 series, 10:32:34-10:34:47 2.2 min busy49%) + post-phase windows.
7. Cross-data of the 240-s perf windows (whole process): 12:43-12:47 cpu=654/240=**272%**, 12:49:33-12:53:33 cpu=712/240=**296%** - the process eats ~3 cores while playing at ~10 t/s; parallel threads work but ticks are sparse => limited by a non-CPU resource first of all.

Attribution: the named mechanism is **a periodic background source of work with "accumulation -> consumption"** (window of elevated tick cost, smooth ramps; picture = a queue with periodic draining). NOT related: the player (0 of the first 8 phases), the saves (0 of 12 mid-session), BattlEye (disabled), our plugin (TickProf.dll = 0.9% of the leaf, only the sampler itself). Candidates by indirect profile data (object creation while processing the accumulated backlog): InitInternal_FindOrAddNameEntry (unrealnames.cpp), AllocateSerialNumber (uobjectarray.cpp), octree inserts/overlaps, PrimalDinoCharacter::Tick - a typical NPC SPAWN/update plus incremental-work picture; THESE ARE ONLY CANDIDATES - the exact culprit requires a live profile INSIDE the phase (60-s sampler at phase start) + tick list before/after. **No categorical verdict for phenomenon No. 1 yet: not "fixable-by-plugin" (mechanism unnamed; it explains the early boot but not the phases at 60 t/s).**

### Phenomenon No. 2. Non-CPU limit of a dense base (frame 43-49+ ms, external 43.5% of a core, ceiling ~21-24 t/s)

Data: prof_512222984 (12:53:23-12:54:23, 3866 samples, step ~15.5 ms, wait=762=19.7%); ticklist/overlapsizes of 12:52 (right before sampling); perf windows 12:43-12:53; mon 12:35-12:49.

World composition (ticklist 12:52): levels=142, actors=106 556 (registered tick=1507), components=404 117 (ticking=3374). overlapsizes: 270 538 components, 6527 with bGenerateOverlapEvents, total overlaps (OverlappingComponents records) **199 422**; the top-20 overlaps are ALL `/Script/Engine.BrushComponent` (largest x5118, then x5001, x4986, x3785...). After overlaptrim (at 12:05, 28 842 components/526 770 records disabled; at 12:29 another 13 783/111 745) the overlap base remains large and concentrated in Engine-BrushComponents - the thinning did not fully help: a "hard core" of overlaps hangs around, mostly from the brush/volume geometry of the map around the player's building.

Profile (named): modules of the leaf - exe 70.8%, ntdll 18.9%, PhysX3+Common 5.5%, MSVCR 2.1%, TickProf.dll 0.9%. Hot exe functions (leaf): AdvanceToNextIntersectingElement (genericoctree.h) **7.7%**, TagFriendlyStructures (primalcharacter.cpp) 3.5%, Tick primaldinocharacter.cpp 2.6%, FindId (set.h) 2.4%, ProcessChildren+0x11c (genericoctree.h) 1.7%, InitInternal_FindOrAddNameEntry 1.4%, then PrimalCharacter ticks, ExecuteTask, Malloc, IncrementalPurgeGarbage, QueueAllTicks, etc. Octree overlaps (AdvanceToNextIntersectingElement+ProcessChildren+neighbors) ~10%+ of samples - the only large cluster; PhysX 5.5% secondary; plus FName/hash sets.

Wait blocks: 762 records. Dominant: ZwWaitForSingleObject <- KERNELBASE WaitForSingleObjectEx (624 = 81.9% of blocks = **16.1% of window time**). Verified BY DISASSEMBLY: return address 0x1EA897D = **ProcessTasksNamedThread+0x32d, call 0x1EA8978 -> Stall(0x1EA9080)** (taskgraph.cpp): the game thread really stands in the named-task Stall (FEvent) - waiting for the tick's TURN (tick-group synchronization / waiting on workers' tasks), NOT an inter-tick Sleep; **ZwDelayExecution is completely absent from the dense-base profile**, whereas in all other (empty/TheIsland) profiles it is 79-99% (ordinary Sleep pacing). Remaining waits (533, ~72.8%) are deeper than the 4 recorded stack words - not attributed; 79 "candidates" of CallRemoteFunction are junk stacks (its bytes contain no wait call) - rejected.

Frame decomposition (rough): plugin busy 82-93% =~ external 43.5% of a core (known x~2); wait-in-tick ~16% of window ~ 7-8 ms/tick; the remainder "in the exe" without CPU - a possible artifact of the suspend sampler (ready-but-not-running) - NOT proven. Confounder: at 12:47:24 fncache was DISABLED, at 12:53:50 enabled INSIDE the sampling window: the first 27 s include the fncache miss path (FindFunctionByName) - part of the FindId/hash load may be an artifact of this toggle.

**Verdict No. 2:** the ~21-24 t/s ceiling is **NOT computational** - external CPU of a core is 43.5% at frame 45-49 ms; the thread stands in event-waits INSIDE the tick (TaskGraph Stall - proven by name and stack) and probably is partially preempted / contends with the workers (not final). No work the config would disable/simplify (maxfps/fixclamp already checked; fncache already a cache). Fixable by plugin: PARTIALLY - overlaptrim/keep-list repeatedly reduces overlaps (verified: 527k->200k records on other maps), but the "core" (map BrushComponents + octree ops of dense building) is not removable by the plugin. Engine: the fork/join synchronization of tick groups (Stall) and work distribution to workers is an engine feature; acceleration only by reducing work per tick. Content: main controllable sources are brush/volume geometry around the base and the count of bGenerateOverlapEvents components of parking/base structures (199 422 overlaps across 6527 components - ~31 per component); reducing structure/overlaps in these zones is the only content-side lever. Live continuation plan: sample directly INTO a dense phase, ticklist before/after trim, overlapsizes during a phase; better: run TickProf.sampler for TWO phases in a row (one inside, one outside) for a formal contrast.

### Methodological notes

mon busy% is plugin, x~1.9-2.4 relative to the external CPU of one core (agrees: 82-93% plugin vs 43.5% ext at 12:53); plugin ms/tick = busy part of a tick in ms (frame separate in frame_ms). The SuspendThread+GetContext sampler: loop step ~15.5 ms in the 12:53 profile; overheads do not bias performance during the profile or skew the RIP sample, but the sampling loop itself is a slowdown. Old profiles 15-19.10 (30k samples) are mostly idle windows: ZwDelayExecution 79-99% - Sleep pacing in empty worlds; the module attribution of some profiles does not match the exe (60% "outside modules") - unusable for comparing file leaves. Ghidra: program v358 = Server2 exe, v361 = Server1 exe - name confusions inside Ghidra happened; the dump was made from v361, path confirmed by printing getExecutablePath(). The bridge tool get_functions is broken; scripts via ~/ghidra_scripts work.
