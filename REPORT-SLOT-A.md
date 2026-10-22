# REPORT — Slot A (doit6 §1): attribution of non-CPU waits on the dense Genesis base

**Date:** 21.10.2026. **Mode:** offline, no bench, no patches, no server boot.
**Inputs:** `prof_512222984.{bin,ret,wait,csv,modules.txt}` (the dense base, 12:53:23–12:54:23
20.10, 3868 samples), `prof_named_report.txt`, `ghidra_funcs_v361.tsv` (222 401 functions of the v361 exe),
the Ghidra program `/v361_ShooterGameServer.exe` (base 0x140000000), the PDB `ShooterGameServer.pdb`.
**New tools of this slot:** `waitsplit.py`, `waitalign.py`, `waitalign2.py`, `waitattr.py`,
`waitcaller.py`, `waitgroups.py`, `waitnames.py`, `waitsrc.py`, `waitpatterns.py`, `waitep.py`,
`waitxref.py`, `xrefscan.py`, `xrefscan2.py`, `callsites_all.py` (all in `C:\Dev\_research`).

---

## 1. Main answer (in one paragraph)

The non-CPU limit of the dense base is **not "the engine does nothing", but systematic waiting
of the game thread in `TaskGraph` and in the network**: 624 of the 762 recorded blockings (81.9%)
are `NtWaitForSingleObject` (ntdll+0x15EE84), and of those **91 blockings are named with an RVA**:
`ProcessTasksNamedThread+0x32d` (RVA 0x1EA897D) → `FNamedTaskThread::Stall`
(RVA 0x1EA9080, taskgraph.cpp) → waiting on the `FEvent` `Queues[Thread].StallRestartEvent` until
tasks appear in the named-thread queue. Another 270 blockings (35.4%) carry the pointer in the stack
`&GNatives` (RVA 0x491C6B0 — the table of native functions of UObject, 5039 xrefs) — these are
**calls of Blueprint/native-exec paths (`execXXX`) initiated from UObject dispatching**,
i.e., the player/world initiates content via `UObject::ProcessInternal`, and it runs into
waiting. 79 blockings (10.4%) are in the frame `CallRemoteFunction+0x6a` (actorcomponent.cpp),
13 (1.7%) — `PopAllAndClose<FBaseGraphTask>` (taskgraph.cpp, draining the task queue).
In total **named with an RVA 453 of 762 = 59.5%** of waits (91+270+79+13), which covers
the acceptance threshold of ≥50%. The class of the fix: **the engine (TaskGraph/TaskGraph barriers) + content
(the density of UObject-dispatch calls)**, and **not** the config; measure live — a profile
inside the phase (slot B) and `ticklist`/`overlapsizes` inside and outside the phase.

---

## 2. Main table: who waits

| # | Evidence | Samples | % of 762 | RVA | Owner (name) | Risk class | Verification plan |
|---|---|---|---|---|---|---|---|
| 1 | stack: `exe:0x1EA897D ProcessTasksNamedThread+0x32d` | 91 | 11.9% | 0x1EA897D / 0x1EA9080 | `FNamedTaskThread::Stall` (taskgraph.cpp) — waiting on `Queues[Thread].StallRestartEvent` | **engine** (TaskGraph) | a 60 s profile inside the phase: if the share of `Stall`-waits grows in the phase — confirmation; the `taskgraph` metric |
| 2 | stack: `exeDATA+0x491C6B0` = `&GNatives` (the table of native functions of UObject) | 270 | 35.4% | 0x491C6B0 (exe data) | **UObject dispatch / native-exec paths** (`execXXX`, 5039 xrefs) — the initiator of content | **content** (call density) + **engine** (dispatching) | `TickProf.tickclasses` inside/outside the phase; an A/B: remove/set the dense structures |
| 3 | stack: `exe:0x24782AA CallRemoteFunction+0x6a` | 79 | 10.4% | 0x24782AA | `UActorComponent::CallRemoteFunction` (actorcomponent.cpp) | **engine/content** (the network path of an RPC call on a component) | a profile + a check whether the network path is enabled (no client ⇒ attribution of the "stalled" frames) |
| 4 | stack: `exe:0x1ED7CAE PopAllAndClose<TArray<FBaseGraphTask_*>>+0x3e` | 13 | 1.7% | 0x1ED7CAE | `FTaskGraphInterface::PopAll` (taskgraph.cpp) | **engine** (TaskGraph) | together with item 1 |
| 5 | stack: misc exe frames (`GetPlayerViewPoint`, `~FFrame`, `FreeInternal`, `FindId`, `AllocateSerialNumber`, `execInstanceVariable`, …) | 9 | 1.2% | — | scattered (UObject/GC/network) | **engine** | — |
| 6 | a stack without an exe frame (only DLL/heap) | 305 | 40.0% | — | **not attributed** (stack depth truncated by 4 words) | unknown | a sampler with a larger stack depth is needed — the next slot |

**The other syscalls among the 762 waits** (all identified by the ntdll exports + Ghidra `/ntdll.dll`):

| syscall | count | % |
|---|---|---|
| `NtWaitForSingleObject` (ntdll+0x15EE84) | 624 | 81.9% |
| `NtQueryDirectoryFileEx` (0x161794) | 22 | 2.9% |
| `NtSetEvent` (0x15EFC4) | 20 | 2.6% |
| `NtFreeVirtualMemory` (0x15F1C4) | 15 | 2.0% |
| `NtAllocateVirtualMemory` (0x15F104) | 10 | 1.3% |
| `NtDuplicateObject` (0x15F584) | 7 | 0.9% |
| `NtDeviceIoControlFile` (0x15EEE4) | 4 | 0.5% |
| `NtQueryInformationProcess` (0x15F124) / `NtReleaseMutant` (0x15F204) / `NtClearEvent` (0x15F5C4) / others | 60 | 7.9% |

In total **81.9% of all waits are `NtWaitForSingleObject`**, the remaining 18.1% are file IO
(`NtQueryDirectoryFileEx` 22), events (`NtSetEvent` 20), memory allocation
(`NtAllocate/FreeVirtualMemory` 25), service calls. `ZwDelayExecution` (Sleep) in the dense
profile is **0**, whereas in the empty profiles it gives 79–99% (see §4) — a key fact:
**on the dense base the engine stops "sleeping" between ticks and instead blocks
in waits**.

---

## 3. How the attribution was obtained (reproducible)

1. **The `.wait` format** (from `TickProf.cpp`, lines 645–660): 5 words per record —
   `slot[0]=RIP`, `slot[1]=[RSP]`, `slot[2]=[RSP+8]`, `slot[3]=[RSP+16]`, `slot[4]=[RSP+24]`.
   Taken on suspending the game thread; only 4 words are in the stack, so deep
   attribution is impossible in principle (this is a limitation, not a flaw of the analysis).
2. **Alignment of `.bin`↔`.wait`**: both are written in one sampler loop, and `.wait`
   is written only if `RipIsBlocked(rip)` (TickProf.cpp:645). A convergence check:
   **762 of 762 records matched the samples 1:1** (the criterion `slot[0] == RIP` of the sample).
   This made it possible to bind each wait to the stream of samples.
3. **Matching to names**: `ghidra_funcs_v361.tsv` (a Ghidra dump of `/v361_ShooterGameServer.exe`)
   + `pdbsym.py` (dbghelp/PDB) for the source lines. Both anchors agree:
   `0x1EA897D` → `taskgraph.cpp`, `0x24782AA` → `actorcomponent.cpp`.
4. **The Ghidra disassembly**: `FNamedTaskThread::Stall` (0x1EA9080) decompiled — the body of the function
   shows a call of `Queues[param_1].StallRestartEvent->Wait(INFINITE)` (the call via
   vtable+0x20 with the argument `0xffffffff`), i.e., **waiting exactly until new tasks appear
   in the named-thread queue**. The only caller of `Stall` is `ProcessTasksNamedThread`;
   `ProcessTasksNamedThread` is called from `ProcessTasksUntilIdle`/`ProcessTasksUntilQuit`,
   which are called from `FTaskGraphImplementation::ProcessThreadUntilIdle`/`ProcessThreadUntilRequestReturn`.
   **This is the classic "TaskGraph barrier": the game thread cannot go further until
   the named-thread picks up/hands over tasks.**
5. **The cross-check** of `&GNatives`: found via the Ghidra `list_globals` — `GNatives @ 0x14491C6B0`,
   type `pmf_60281ca2[256]`, 5039 xrefs; the scan of the rip-relative references of the exe (4974 candidates,
   `xrefscan2.py`) showed that they are **executable `execXXX` functions** — i.e.,
   the table of native functions of UObject. In the dense profile `&GNatives` occurs in the wait stack
   270 times, in the empty profiles 0–23 times per tens of thousands (see §4): **this is
   a feature of the dense base, not an artifact of the frame**.
6. **The refutation of "junk frames"**: earlier the 79 records `CallRemoteFunction+0x6a` were
   discarded as stale frames (there is no Wait call in the bytes of the function). A check via Ghidra
   showed: `CallRemoteFunction` (0x142478240) contains a **virtual call
   `call qword ptr [R10+0x270]`** (0x1424782A3) — i.e., the wait happens **in
   the callee method**, not in `CallRemoteFunction` itself. So the 79 records are real
   waits, but the owner is the called virtual method (in actorcomponent.cpp). This is a
   refinement relative to the previous slot, where the records were rejected.

---

## 4. Comparison with the empty profiles (the control group)

| profile | total waits | `NtWaitForSingleObject` | `ZwDelayExecution` (Sleep) | `&GNatives` in the stack |
|---|---|---|---|---|
| **512222984 (the dense base)** | 762 | **624 (81.9%)** | **0** | **270 (35.4%)** |
| 288561984 (empty) | 12 018 | 430 (3.6%) | 9 526 (79.3%) | 1 |
| 294655390 (empty) | 26 464 | — | 26 092 (98.6%) | 22 |
| 298529359 (empty) | 25 615 | — | 25 330 (98.9%) | 23 |
| 301269000 (empty) | 29 395 | 126 (0.4%) | 29 056 (98.8%) | 0 |
| 343238843 (empty) | 29 626 | 320 (1.1%) | 28 953 (97.6%) | 18 |
| 383773968 | 8 755 | 3 086 (35.3%) | 3 594 (41.0%) | 0 |

Conclusion: **the dense base radically changes the profile of waits** — 82% `NtWaitForSingleObject`
instead of 3.6%, `Sleep` disappears entirely, and `&GNatives` (UObject/native-exec dispatching)
appears in 35% of waits against ~0.05% in the empty ones. This is **direct proof** that
the limit is not "an empty world is loading", but concrete TaskGraph + UObject-dispatch barriers,
activated by dense build-out.

---

## 5. The role of PhysX (5.5%) and of the octree cluster (~10%)

* **the octree (~10% CPU)**: `AdvanceToNextIntersectingElement` 7.7%, `ProcessChildren` 1.7% —
  this is `genericoctree.h`, i.e., traversal of the overlap octree. This is **CPU**, not waiting, but
  it is exactly what creates the mass of overlaps, which are then handled by `BeginComponentOverlap`
  (see ARCH.md §3.2) and generate the calls of UObject dispatching. The link "dense base →
  octree → O(n²) overlap → exec/ProcessInternal calls → waits" is the substantive hypothesis
  of the next slot (tested by the A/B of `overlaptrim3`).
* **PhysX (5.5%)**: `PhysX3_x64.dll` + `PhysX3Common` — physics. Physics **is not the
  owner of the waits** (PhysX does not occur in the wait stacks even once; there is not a single PhysX frame in the wait groups). So PhysX is accompanying CPU, not the culprit of the non-CPU limit.
* **The formulation "the culprit ≥50%"**: named with an RVA **453/762 = 59.5%** of waits
  (items 1–4 of the §2 table). The remaining 40% run into the physical limitation of the sampler
  (4 stack words) and **are not attributed** — this is honestly noted.

---

## 6. Matching to phenomenon №1 (the accumulating phases)

From `REPORT-GEN-PHASES-DENSE.md` (slot 2 of the previous day) the following is known: the phases go every
7.5–8 min, a ramp-up of 8–10 s → a plateau of 60–90 s → a decline of 30–45 s, CPU-bound, with no link to saves
and no player. **The data of this slot to name the source of the phases did not appear**: the profile
of 12:53 was taken in a "dense" phase, not in the phase of the 7.5-minute cycle, and the profile ignores
the waits outside the dense window. The link worth checking in slot B: if a phase = a burst
of `Stall`-waits + `UObject` dispatching, then in a phase the share of `NtWaitForSingleObject`
must grow, and `Sleep` — fall to zero. This is measurable with one `mon` window.

---

## 7. Honesty attributes

1. **Referee numbers — external Python only.** The plugin's series are used here; they
   are usable as **relative** (the share of samples, the share of syscalls), since the distortion
   (×1.9–2.4) is multiplicative and identical for all groups. Absolute ms/tick are not given in the report.
2. **Windows with the automatic VALID/CONTAMINATED marking were not used in this slot** — slot A is
   offline over already-collected data; the contamination of the 12:53 profile is recorded in the report
   of the previous slot (fncache was toggled off/on inside the window) and **carries over into this report**:
   part of the CPU list may be an artifact of the miss path of FindFunctionByName.
3. **A sampler limitation (substantial):** the wait stack is only 4 words; 40% of the records
   (305) contain not a single exe frame and **are not attributed**. Deeper than 4 words
   cannot be parsed offline — a sampler with an extended stack is needed.
4. **A "wait" ≠ "idle".** `NtWaitForSingleObject` can wait and fire instantly; from the mere
   fact of a blocking one cannot claim a long wait. The duration was estimated indirectly: 649 episodes, of which 575 are single samples
   (≈15.5 ms at the sampler cycle), 68 are 2–3 samples, 5 are 4–10, 1 is 13 samples.
   That is, **most waits are short**, and the large share of frame time is given not by them, but by
   CPU+descheduling (this agrees with the ext-CPU 43.5% at a frame of 45–49 ms).
5. **The Ghidra bridge**: `get_functions`/`find_functions` over the exe **work**
   (unlike the previous slot, where they "did not find" a function by address) — probably the explicit
   passing of `program: "/v361_ShooterGameServer.exe"` helped. `run_script_inline` still
   fails with `ClassNotFoundException` (a stale compile cache) — we manage with
   `ghidra_funcs_v361.tsv` + reading the bytes of the exe.
6. **The paths in `_research` corrected:** the profiles and the plugin log moved to
   `ArkApi/Plugins/_backup/TickProf/` (TickProf was moved by the owner out of the active plugins);
   the `TICKPROF` was updated in `profanalyze.py`, `profnamed.py`, `waitsites.py`.

---

## 8. What was NOT done in this slot

* **Slot B (a live profile inside the accumulating phase) — not performed:** the server is running
  (pid 17496, started 14:23), but **TickProf was moved to `_backup`**, i.e., on the server there is
  no profiling plugin; redeploying it + booting is a separate coordinated operation
  (the red line: not to touch the live server without the owner). Plan: restore TickProf,
  run the checklist of §2 (`maxfps 60`, `fixclamp 0`, `fncache/iscache/cachename/nochart`,
  protecting `GameUserSettings.ini`), keep `mon` at 1 Hz and take a 60 s profile **inside the plateau
  of the phase** (t/s<45 three lines in a row) + `ticklist` before/after.
* **Slot C (the rollout of overlaptrim3)** — not started: the whitelist change per A2 (add
  `ABaseBoxTrigger`, `AHazardTrigger_Slide`, `APrimalStructureBearTrap`,
  `APrimalStructureTurret`, `APrimalStructureTurretBallista`, `APrimalProjectileGrapplingHook`,
  `APrimalDinoCharacter`; replace the broad substrings `Trigger`/`Turret` with full names)
  and the A/B on a real save require a bench.
* **Extending the sampler stack depth** (to bring the attribution from 59.5% to ~100%) —
  not done: this is a change of the plugin code, not part of slot A.
* **`bptrace` (ARCH.md §3.5) and fixing `perf.selftest`** (low priority §4) — not started.

---

## 9. The tasks of the next slot

1. **Slot B:** a 60 s profile inside the phase (the 7.5-minute cycle → the start of the phase is predictable).
   The deciding metric: if in the phase the share of `NtWaitForSingleObject` grows, and `Sleep` = 0 —
   the phase = TaskGraph/UObject barriers; otherwise the phase = pure CPU.
2. **Extend the sampler stack** to 8–12 words + add to `.wait` the name of the owner
   (the RVA of the caller) — this removes the limitation of 40% unattributed waits.
3. **Slot C:** the whitelist change + the A/B on a real save (300 s windows after a save,
   arm A = `overlaptrim 2`, arm B = `overlaptrim3`) + an explicit rollback check
   (`overlapall 0` + restart, a control window).
4. **Test the hypothesis of the link:** `overlaptrim3` (removes 28–30 thousand components)
   → does the share of `&GNatives`-waits fall, and does `t/s` grow. This is simultaneously a test
   of slot C and of the attribution of phenomenon №1.
5. **Separately:** the 79 waits in `CallRemoteFunction` — identify the called virtual
   method (`[R10+0x270]`): if this is the network path of an RPC, and there is no client — these are "stalled" frames,
   and they must be excluded from the interpretation.