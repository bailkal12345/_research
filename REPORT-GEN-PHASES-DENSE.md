# Report: Genesis — accumulative phases (#1) and the non-CPU limit of a dense base (#2)

Date: 20.10.2026. Slot: offline analysis of existing artifacts (no patches, no live boots).
Tools: profile analysis of the TickProf `.bin/.ret/.wait` + `.pdata` bounds (173 540 functions) + PDB names
(function dump of the Ghidra program `/v361_ShooterGameServer.exe` — the MD5 path = our Server1 exe, 222 401 functions,
verified by anchors: GetMaxTickRate@0x253b1c0, SetActorTickEnabled@0x24696b0, AdvanceToNextIntersectingElement@0x276a0b0, size 537 = the PDB size).
The judge-grade absolute numbers come only from external Python (the plugin busy/ms/tick are inflated ×1.9–2.4); here the plugin
series are used relatively (the "CPU-bound vs blocked" diagnosis is preserved, since the distortion is multiplicative).

---

## Phenomenon No. 1. Accumulative phases (ms/tick 36→93 ms, decay 1–5.5 min, present without a player)

Data: TickProf.log, boot #39 of 20.10 (07:19:26 — 12:55, Genesis): 5160 mon lines, 21 save cycles, 30 detected
phases (t/s<45 for ≥3 lines). The first 8 phases are BEFORE any player connection (first login per SrvDiag 09:34:32).

### Facts
1. Series of the key phase 08:49:04–08:50 (full lines, 1 Hz):
   - ramp-up: busy 60→89% and ms/tick 11→16 ms with a FREE frame of 16 ms (t/s still 59) over ~8 s;
   - plateau: t/s 21–27, frm≈36–46 ms, busy 96–103% — ~1 min;
   - release: t/s jumps to 57–60 instantly, but ms/tick stays at 15–17 ms and LINEARLY decays to 3–4 over ~44 s
     (busy 101→65→21%). I.e. a "residual" load of a band 15→3 ms/tick at the full target of 60 t/s.
   Shape: symmetric (rise ~8–10 s, plateau 60–90 s, decay 30–45 s) — this is not a single tick spike,
   but an INCREASE in the cost of EVERY tick over a window of 1.5–2 min.
2. Cadence of phase starts (empty world, mon windows 07:48–08:56): 07:48:59, 07:56:30, 08:11:35, 08:19:12,
   08:26:59, 08:34:03, 08:41:40, 08:49:09 — intervals 7.5 / 15 / 7.6 / 7.8 / 7.1 / 7.6 / 7.5 min.
   The same periodicity in other empty boots of the same day: 15:08:51→15:15:51 (7.0m), 15:31:26→15:38:16 (6.8m),
   15:59:35→16:06:42 (7.1m)→16:14:14 (7.5m). The gaps are multiples of 15 min → the true period is 7.5–8 min
   (every second event sometimes merges / is masked).
3. No save linkage: out of 12 mid-session phases — 0 starts within ±90 s of the save markers; the saves
   (21 in the boot, every ~15.3 min, duration ~3 s per the wall marker) fell inside 2 phases as
   random coincidences. A save is otherwise safe: mon lines with save=saving show the same profile.
4. A separate kind — multi-second stalls of a SINGLE frame: frame_ms 1177–1687 ms at t/s=0:
   08:52:59 (busy 99%), 08:53:07 (busy 0% !), 10:05 (1656 ms, busy 93%), 09:58 (344 ms), 12:37:59 (404 ms, busy 96%).
   The "busy=0%" case = a pure BLOCK of the thread (not work) for 1.7 s.
5. The early boot warm-up 07:27–07:46: t/s strictly 29.8±0.1, the frame exactly 33.0 ms, busy 24–51% — this is NOT a phase:
   it is the default pacing of maxfps 30 (`TickProf.maxfps 60` was applied only at 07:48 → immediately 58–59 t/s).
   The "shaking" of the first 20 minutes is an artifact of the default config.
6. Typology of the phases (by the plugin busy, correspondingly ×~2 underestimation of real CPU):
   - CPU-bound phases: busy 96–103% ⇒ external ~ (43–50)% of one core; ~28 phases — the majority.
   - BLOCKED phases (busy<60%): up to 9 short ones (the 09:59 series, 10:32:34–10:34:47 2.2 min busy49%) + post-phase windows.
7. Cross-data of the 240-s perf windows (the whole process): 12:43–12:47 cpu=654/240=**272%**, 12:49:33–12:53:33
   cpu=712/240=**296%** — the process eats ~3 cores while playing at ~10 t/s. Parallel threads are working,
   but the game ticks are sparse ⇒ the program is limited by a non-CPU resource first of all.

### Attribution (what can and cannot be claimed)
- The named mechanism of the phase: **a periodic background source of work with "accumulation → consumption"**
  (a window of elevated tick cost, smooth ramps; the picture = a queue with periodic draining).
- NOT related: the player (0 of the first 8 phases), the saves (0 of 12 mid-session), BattlEye (disabled),
  our plugin (the TickProf.dll module = 0.9% of the leaf, only the sampler itself).
- Candidates by indirect profile data (object creation while processing the accumulated backlog):
  InitInternal_FindOrAddNameEntry (unrealnames.cpp), AllocateSerialNumber (uobjectarray.cpp),
  octree inserts/overlaps, PrimalDinoCharacter::Tick — a typical picture of NPC SPAWN/updating plus
  incremental work. But THESE are only candidates — the exact culprit of a phase requires a live profile
  INSIDE the phase (a 60-s sampler at the moment of phase start) + a tick list before/after.
- No categorical verdict is issued for phenomenon No. 1 yet: it is not "fixable-by-plugin" (the mechanism is unnamed;
  it explains the early boot, but not the phases at 60 t/s); the exact verdict — after an in-phase profile.

---

## Phenomenon No. 2. The non-CPU limit of a dense base (frame 43–49+ ms, external 43.5% of a core, ceiling ~21–24 t/s)

Data: prof_512222984 (12:53:23–12:54:23, 3866 samples, step ~15.5 ms, wait=762=19.7%);
ticklist/overlapsizes of 12:52 (right before the sample); perf windows 12:43–12:53; mon 12:35–12:49.

### Composition of the world (ticklist 12:52)
- levels=142, actors=106 556 (registered tick=1507), components=404 117 (ticking=3374).
- overlapsizes: 270 538 components, of which with bGenerateOverlapEvents=**6527**, total overlaps
  (OverlappingComponents records)=**199 422**; the top-20 overlaps are ALL `/Script/Engine.BrushComponent`
  (the largest x5118, then x5001, x4986, x3785...). After overlaptrim (at 12:05, 28 842
  components/526 770 records disabled; at 12:29 another 13 783/111 745) the overlap base remains large and
  concentrated in Engine-BrushComponents — i.e. the thinning did not fully help: a
  "hard core" of overlaps hangs around, mostly from the brush/volume geometry of the map around the player's building.

### Profile (named)
- Modules of the leaf: exe 70.8%, ntdll 18.9%, PhysX3+Common 5.5%, MSVCR 2.1%, TickProf.dll 0.9%.
- hot exe functions (leaf): AdvanceToNextIntersectingElement (genericoctree.h) **7.7%**,
  TagFriendlyStructures (primalcharacter.cpp) 3.5%, Tick primaldinocharacter.cpp 2.6%, FindId (set.h) 2.4%,
  ProcessChildren+0x11c (genericoctree.h) 1.7%, InitInternal_FindOrAddNameEntry 1.4%, then ticks
  of PrimalCharacter, the task graph's ExecuteTask, Malloc, IncrementalPurgeGarbage, QueueAllTicks, etc.
- Total: octree overlaps (AdvanceToNextIntersectingElement+ProcessChildren+neighbors) ≈ 10%+ of samples —
  the only large cluster; PhysX 5.5% — secondary/collision; plus FName/hash sets.
- Wait blocks: 762 records. The dominant one is ZwWaitForSingleObject ← KERNELBASE WaitForSingleObjectEx
  (624 = 81.9% of the blocks = **16.1% of the window's time**). Verified BY DISASSEMBLY: the return address
  0x1EA897D = **ProcessTasksNamedThread+0x32d, call 0x1EA8978 → Stall(0x1EA9080)** (taskgraph.cpp):
  the game thread really stands in the named-task Stall (FEvent). This is waiting for the tick's TURN
  (tick-group synchronization / waiting on the workers' tasks), NOT an inter-tick Sleep — **ZwDelayExecution is
  completely absent from the dense-base profile**, whereas in all the other (empty/TheIsland) profiles
  it is 79–99% (ordinary Sleep pacing). The remaining waits (533, ~72.8%) are deeper than the 4 recorded stack words —
  not attributed; 79 "candidates" of CallRemoteFunction are junk stacks (the bytes of CallRemoteFunction
  contain no wait call) — rejected.
- Frame decomposition (rough, with honesty): the plugin busy 82–93% ≍ external 43.5% of a core (the known ×~2);
  wait-in-tick ≈ 16% of the window ≈ 7–8 ms/tick; the remainder "in the exe" without CPU — a possible artifact of the suspend sampler
  (ready-but-not-running) — NOT considered proven.
- Profile confounder (important for the record): at 12:47:24 fncache was DISABLED, at 12:53:50 it was enabled
  INSIDE the sampling window: the first 27 s of the profile include the fncache miss path (FindFunctionByName) —
  part of the FindId/hash load may be an artifact of this toggle.

### Verdict No. 2
- The cause of the ~21–24 t/s ceiling is **NOT computational**: the external CPU of a core is 43.5% at a frame of 45–49 ms;
  the thread stands in event-waits INSIDE the tick (a TaskGraph Stall — proven by name and stack) and,
  probably, is partially preempted / contends with the workers (not final).
- There is no work that the config would disable/simplify (maxfps/fixclamp — already checked earlier; fncache — already a cache).
- Fixable by plugin: PARTIALLY — the existing overlaptrim/keep-list repeatedly reduces the overlaps
  (verified: 527k→200k records on other maps), but the "core" (the map's BrushComponents + the
  octree operations of dense building themselves) is not removed by the plugin.
- Engine: the 'fork/join' synchronization of the tick groups (Stall) and the distribution of work to the workers is an engine
  feature; acceleration is possible only by reducing the work per tick.
- Content: the main controllable sources are the Brush/volume geometry of the map around the base and the number
  of bGenerateOverlapEvents components of parking/base structures (199 422 overlaps across 6 527 components — ~31 per
  one component, on production content around the base). Reducing structure/overlaps in these zones is the only
  lever from the content side.
- Live continuation (when the owner brings Server1 up): the plan is to sample directly INTO a dense phase, ticklist
  before/after the trim, overlapsizes during a phase; and better: run TickProf.sampler for TWO phases in a row — one inside a phase,
  one outside — for a formal contrast.

---

## Methodological notes (for judging)
- mon series: busy% — plugin, ×~1.9–2.4 relative to the external CPU of one core (it agrees: 82–93% plugin vs
  43.5% ext at 12:53). The plugin's ms/tick — the busy part of a tick in ms (the frame separately in frame_ms).
- The SuspendThread+GetContext sampler: the loop step ~15.5 ms in the 12:53 profile; the overheads do not bias
  performance during the profile and do not skew the RIP sample, but the sampling loop itself is
  a slowdown
- The old profiles 15–19.10 (30k samples) are mostly idle windows: ZwDelayExecution 79–99% — Sleep pacing
  in empty worlds; the module attribution of some profiles does not match the exe (60% "outside modules") —
  unusable for comparing file leaves.
- Ghidra: program v358 = the Server2 exe, v361 = the Server1 exe — name confusions inside Ghidra happened;
  the dump was made from v361, the path confirmed by printing getExecutablePath(). The bridge tool get_functions is
  broken; the scripts via ~/ghidra_scripts work.
