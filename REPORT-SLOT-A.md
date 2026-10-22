# REPORT - Slot A (doit6 sec 1): attribution of non-CPU waits on the dense Genesis base

**Date:** 21.10.2026. Offline: no bench, no patches, no server boot.
**Inputs:** `prof_512222984.{bin,ret,wait,csv,modules.txt}` (dense base, 12:53:23-12:54:23 20.10, 3868
samples), `prof_named_report.txt`, `ghidra_funcs_v361.tsv` (222 401 functions of the v361 exe), the
Ghidra program `/v361_ShooterGameServer.exe` (base 0x140000000), the PDB `ShooterGameServer.pdb`.
**New tools:** `waitsplit.py`, `waitalign.py`, `waitalign2.py`, `waitattr.py`, `waitcaller.py`,
`waitgroups.py`, `waitnames.py`, `waitsrc.py`, `waitpatterns.py`, `waitep.py`, `waitxref.py`,
`xrefscan.py`, `xrefscan2.py`, `callsites_all.py` (all in `C:\Dev\_research`).

---

## 1. Main answer

The non-CPU limit of the dense base is **systematic waiting of the game thread in `TaskGraph` and the
network**: of 762 blockings, 624 (81.9%) are `NtWaitForSingleObject` (ntdll+0x15EE84). Of those, **91
named with an RVA**: `ProcessTasksNamedThread+0x32d` (RVA 0x1EA897D) -> `FNamedTaskThread::Stall` (RVA
0x1EA9080, taskgraph.cpp) -> waiting on the `FEvent` `Queues[Thread].StallRestartEvent` until tasks
appear in the named-thread queue. Another 270 (35.4%) carry `&GNatives` (RVA 0x491C6B0 - the table of
native functions of UObject, 5039 xrefs) in the stack - **calls of Blueprint/native-exec paths
(`execXXX`) initiated from UObject dispatching** (`UObject::ProcessInternal`). 79 (10.4%) in
`CallRemoteFunction+0x6a` (actorcomponent.cpp); 13 (1.7%) in `PopAllAndClose<FBaseGraphTask>`
(taskgraph.cpp). Named with an RVA: **453 of 762 = 59.5%** (the >=50% threshold is met). Fix class:
**engine (TaskGraph barriers) + content (density of UObject-dispatch calls)**, not config; measure
live - a profile inside the phase (slot B) and `ticklist`/`overlapsizes` in/out of the phase.

---

## 2. Main table: who waits

| # | Samples (% of 762) | RVA | Owner | Risk class | Verification |
|---|---|---|---|---|---|
| 1 | 91 (11.9%) | 0x1EA897D / 0x1EA9080 | `FNamedTaskThread::Stall` (taskgraph.cpp), stack `exe:0x1EA897D ProcessTasksNamedThread+0x32d`, waiting on `Queues[Thread].StallRestartEvent` | **engine** (TaskGraph) | a 60 s profile in the phase - `Stall`-waits must grow; the `taskgraph` metric |
| 2 | 270 (35.4%) | 0x491C6B0 (exe data) | **UObject dispatch / native-exec** (`execXXX`, 5039 xrefs); stack `exeDATA+0x491C6B0` = `&GNatives` | **content** (density) + **engine** (dispatching) | `TickProf.tickclasses` in/out; an A/B on dense structures |
| 3 | 79 (10.4%) | 0x24782AA | `UActorComponent::CallRemoteFunction` (actorcomponent.cpp); stack `exe:0x24782AA CallRemoteFunction+0x6a` | **engine/content** | profile + check whether the network path is on (no client => "stalled" frames) |
| 4 | 13 (1.7%) | 0x1ED7CAE | `FTaskGraphInterface::PopAll` (taskgraph.cpp); stack `exe:0x1ED7CAE PopAllAndClose<TArray<FBaseGraphTask_*>>+0x3e` | **engine** | with item 1 |
| 5 | 9 (1.2%) | - | misc exe frames (`GetPlayerViewPoint`, `~FFrame`, `FreeInternal`, `FindId`, `AllocateSerialNumber`, `execInstanceVariable`, ...) | **engine** | - |
| 6 | 305 (40.0%) | - | **not attributed** - no exe frame (stack truncated to 4 words) | unknown | a sampler with a deeper stack |

Other syscalls (ntdll exports + Ghidra `/ntdll.dll`): `NtWaitForSingleObject` (ntdll+0x15EE84) 624 =
81.9%; `NtQueryDirectoryFileEx` (0x161794) 22 (2.9%); `NtSetEvent` (0x15EFC4) 20 (2.6%);
`NtFreeVirtualMemory` (0x15F1C4) 15 (2.0%); `NtAllocateVirtualMemory` (0x15F104) 10 (1.3%);
`NtDuplicateObject` (0x15F584) 7 (0.9%); `NtDeviceIoControlFile` (0x15EEE4) 4 (0.5%);
`NtQueryInformationProcess` (0x15F124) / `NtReleaseMutant` (0x15F204) / `NtClearEvent` (0x15F5C4) /
others 60 (7.9%). `ZwDelayExecution` (Sleep) on the dense base: **0** vs 79-99% on empty profiles (sec 4)
- **the engine stops "sleeping" between ticks and blocks in waits**.

---

## 3. How the attribution was obtained (reproducible)

1. **The `.wait` format** (`TickProf.cpp` 645-660): 5 words per record - `slot[0]=RIP`,
   `slot[1]=[RSP]`, `slot[2]=[RSP+8]`, `slot[3]=[RSP+16]`, `slot[4]=[RSP+24]`; taken on suspending the
   game thread; only 4 stack words - deep attribution impossible in principle (a limitation).
2. **Alignment `.bin`<->`.wait`**: one sampler loop, `.wait` written only if `RipIsBlocked(rip)`
   (`TickProf.cpp:645`); check: **762 of 762 matched 1:1** (criterion `slot[0]==RIP`).
3. **Names**: `ghidra_funcs_v361.tsv` + `pdbsym.py` (source lines); both anchors agree: `0x1EA897D` ->
   taskgraph.cpp, `0x24782AA` -> actorcomponent.cpp.
4. **Ghidra disassembly**: `Stall` (0x1EA9080) calls `Queues[param_1].StallRestartEvent->Wait(INFINITE)`
   (vtable+0x20, arg `0xffffffff`); chain `Stall` <- `ProcessTasksNamedThread` <- `ProcessTasksUntilIdle/
   ProcessTasksUntilQuit` <- `FTaskGraphImplementation::ProcessThreadUntilIdle/
   ProcessThreadUntilRequestReturn` - **the classic TaskGraph barrier**.
5. **Cross-check of `&GNatives`**: `GNatives @ 0x14491C6B0`, type `pmf_60281ca2[256]`, 5039 xrefs; the
   rip-relative scan (`xrefscan2.py`, 4974 candidates) showed only executable `execXXX` functions; dense
   base 270 of 762 waits vs 0-23 per tens of thousands on empty profiles.
6. **Refutation of "junk frames"**: the 79 `CallRemoteFunction+0x6a` records were earlier discarded;
   Ghidra showed `CallRemoteFunction` (0x142478240) contains a virtual `call qword ptr [R10+0x270]`
   (0x1424782A3) - the wait is in the callee method; the records are real (owner: the called virtual
   method, actorcomponent.cpp).

---

## 4. Comparison with the empty profiles (the control group)

| profile | total waits | `NtWaitForSingleObject` | `ZwDelayExecution` (Sleep) | `&GNatives` in the stack |
|---|---|---|---|---|
| **512222984 (the dense base)** | 762 | **624 (81.9%)** | **0** | **270 (35.4%)** |
| 288561984 (empty) | 12 018 | 430 (3.6%) | 9 526 (79.3%) | 1 |
| 294655390 (empty) | 26 464 | - | 26 092 (98.6%) | 22 |
| 298529359 (empty) | 25 615 | - | 25 330 (98.9%) | 23 |
| 301269000 (empty) | 29 395 | 126 (0.4%) | 29 056 (98.8%) | 0 |
| 343238843 (empty) | 29 626 | 320 (1.1%) | 28 953 (97.6%) | 18 |
| 383773968 | 8 755 | 3 086 (35.3%) | 3 594 (41.0%) | 0 |

Direct proof that the limit is TaskGraph + UObject-dispatch barriers activated by dense build-out, not
"an empty world loading".

---

## 5. PhysX (5.5%) and the octree cluster (~10%)

* **The octree (~10% CPU)**: `AdvanceToNextIntersectingElement` 7.7%, `ProcessChildren` 1.7%
  (`genericoctree.h`) - overlap-octree traversal. CPU, not waiting, but it creates the overlap mass
  handled by `BeginComponentOverlap` (ARCH.md sec 3.2) and generates UObject-dispatch calls. "Dense base ->
  octree -> O(n^2) overlap -> exec/ProcessInternal -> waits" is the hypothesis to test in slot C's A/B of
  `overlaptrim3`.
* **PhysX (5.5%)** (`PhysX3_x64.dll` + `PhysX3Common`): not the owner of the waits - no PhysX frame in
  the wait groups; accompanying CPU only.
* Attribution: **453/762 = 59.5%**; the remaining 40% is the sampler's 4-word stack limit.

---

## 6. Phenomenon No. 1 (the accumulating phases)

From `REPORT-GEN-PHASES-DENSE.md`: phases every 7.5-8 min - ramp 8-10 s -> plateau 60-90 s -> decline
30-45 s, CPU-bound, no link to saves, no player. **This slot did not name the phase source** (the profile
was taken in a "dense" phase, not a 7.5-min-cycle phase, and ignores waits outside the dense window).
Test for slot B: if a phase = `Stall`-waits + UObject dispatching, `NtWaitForSingleObject` must grow in
a phase and `Sleep` fall to zero - one `mon` window.

---

## 7. Honesty attributes

1. Plugin series used **relatively**; distortion x1.9-2.4, multiplicative, identical for all groups; no
   absolute ms/tick given. Referee numbers - external Python only.
2. The 12:53 profile was **contaminated** (fncache toggled in-window, per the previous slot's report);
   part of the CPU list may be a `FindFunctionByName` miss-path artifact. No VALID/CONTAMINATED
   machinery used here (offline analysis).
3. Sampler limitation: 4-word wait stack; 305 records (40%) without an exe frame, unattributed.
4. A "wait" is not "idle": 649 episodes - 575 single (~15.5 ms at the sampler cycle), 68 of 2-3 samples,
   5 of 4-10, 1 of 13. Most waits short; the large frame-time share is CPU+descheduling (ext-CPU 43.5%
   at a frame of 45-49 ms).
5. Ghidra bridge: `get_functions`/`find_functions` work with the explicit
   `program: "/v361_ShooterGameServer.exe"`; `run_script_inline` fails (`ClassNotFoundException`,
   stale compile cache) - work via `ghidra_funcs_v361.tsv` + exe bytes.
6. Paths corrected: profiles + plugin log moved to `ArkApi/Plugins/_backup/TickProf/` (TickProf moved by
   the owner); `TICKPROF` updated in `profanalyze.py`, `profnamed.py`, `waitsites.py`.

---

## 8. Not done / next slot

* **Slot B** (live profile in the phase): server running (pid 17496, started 14:23) but TickProf moved
  to `_backup` - redeploy+boot is a coordinated operation (red line: not to touch the live server
  without the owner). Plan: restore TickProf; checklist `maxfps 60`, `fixclamp 0`,
  `fncache/iscache/cachename/nochart`, protect `GameUserSettings.ini`; `mon` 1 Hz; 60 s profile inside
  the plateau (t/s<45 in three lines in a row) + `ticklist` before/after; deciding metric -
  `NtWaitForSingleObject` up and `Sleep` = 0 in the phase => engine barriers; otherwise pure CPU.
* **Extend the sampler stack** to 8-12 words + owner RVA in `.wait` (removes the 40% unattributed).
* **Slot C** - not started: whitelist per A2 (add `ABaseBoxTrigger`, `AHazardTrigger_Slide`,
  `APrimalStructureBearTrap`, `APrimalStructureTurret`, `APrimalStructureTurretBallista`,
  `APrimalProjectileGrapplingHook`, `APrimalDinoCharacter`; replace the broad `Trigger`/`Turret`
  substrings) + an A/B on a real save (300 s windows after a save; A = `overlaptrim 2`,
  B = `overlaptrim3`; rollback `overlapall 0` + restart + a control window).
* **Test the link**: `overlaptrim3` (removes 28-30 thousand components) -> does the `&GNatives`-wait
  share fall and t/s grow - a test of slot C and of the attribution of No. 1.
* **Identify the callee of the 79 `CallRemoteFunction` waits** (`[R10+0x270]`): if it is an RPC network
  path with no client - "stalled" frames, to be excluded.
* **`bptrace` (ARCH.md sec 3.5)** and fixing `perf.selftest` - not started.
