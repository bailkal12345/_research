# Slot D — bptrace via a data patch of `UFunction::Func` (+ the attribution of file IO, the profiler crash bug)

Date: 22.10.2026 · bench: `Server1` (Genesis, the full dense base) · prod config §2 (`maxfps 60`, `fixclamp 0`, `fncache 1`, `iscache 1`, `cachename 1`, `nochart 1`, `overlaptrim 2`)

---

## 1. Main answer (one paragraph)

Priority 1 is closed: **the Blueprint tracer was built without a single patch byte in the process code** — the scan goes over
the engine data (`UFunction+0xA8` = the field `Func`), for script functions there it holds `&ProcessInternal` (RVA `0x1FC0270`); of such functions on the dense base there turned out to be **40 638 of 40 639 UFunction**. Substituting `Func` with our own handler takes **1.4 s**, the process code and the security cookie are not touched, the rollback is writing the original `Func` back (verified by enumeration: after the substitution is lifted, again 40 638 script functions, the server alive). The phase top-5 of calls obtained point-blank: **`Ichthyornis_Character_BP_C:InitializeLandingVariables` (283 556 calls, 40.7% of all script calls over the window)**, `Buff_Grappled_BogSpider_C:BuffTickServer` (164 164), `MissionSpline_Base_C:ReceiveTick` (115 661), `VRBattle_CodeKeyTumbler_C:ReceiveTick` (26 117), `InsectSwarmChar_BP_C:ReceiveTick` (16 451). Incidentally, but important: **the cause of the server crash was found and eliminated**, because of which the bench was lost three times in this slot — `delete[]` on objects created by scalar `new` corrupted the heap, and a repeated `std::thread` on top of a joinable thread gave `std::terminate`; after the fix, three windows in a row ran without falls. By priority 2: **all the visible file IO in the profile is our own monitor** (the deciding experiment: 333 records of `ZwQueryDirectoryFileEx` with the polling of `.ark` and **0** without it), and in the engine the owners of `FWindowsPlatformFile::IterateDirectory` are four callers, of which `UWorldComposition::Rescan` only runs at world load/save, not in the tick loop. By priority 3: **a series of A/B of 6 pairs gave 4 valid pairs, all of one sign — `overlaptrim3` is faster than `overlaptrim 2` by +3…+6 t/s (a median of +3.5) and −3…−5 ms/tick**, and the prod config of the bench was switched to `overlaptrim3` (verified by class: the components of traps/turrets/grapples keep their overlap events enabled, +23 312 components).

---

## 2. Main table

### 2.1 bptrace: the full cycle on the live server

| Step | Command | Result | Verification |
|---|---|---|---|
| Enumeration (no patch) | `TickProf.bptrace 2` | UFunction total **40 639**, script (`Func==&ProcessInternal`) **40 638** | the plugin log, the server alive |
| The substitution of `Func` | `TickProf.bptrace 1` | **40 638** UFunctions substituted in **1.4 s** | the process code is not patched |
| Collecting the statistics | `TickProf.bptrace.report` | **695 851** calls, **76** distinct functions | the names via `GetFullName` |
| Rollback | `TickProf.bptrace 0` | "disabled (calls 0), the substitutions lifted from 40638 UFunctions" | the control: the enumeration again gives 40 638 script |
| Enumeration again | `TickProf.bptrace 2` | 40 638 / 40 639 | functionality preserved |

### 2.2 The phase top-5 UFunctions (a 132 s window, the tracer enabled)

| # | Function | Calls | Share |
|---|---|---|---|
| 1 | `/Game/PrimalEarth/Dinos/Ichthyornis/Ichthyornis_Character_BP.Ichthyornis_Character_BP_C:InitializeLandingVariables` | **283 556** | 40.7% |
| 2 | `/Game/Genesis/Dinos/BogSpider/Buff_Grappled_BogSpider.Buff_Grappled_BogSpider_C:BuffTickServer` | **164 164** | 23.6% |
| 3 | `/Game/Genesis/Missions/MissionSpline_Base.MissionSpline_Base_C:ReceiveTick` | **115 661** | 16.6% |
| 4 | `/Game/Genesis/Missions/VRBattle/VRBattle_CodeKeyTumbler.VRBattle_CodeKeyTumbler_C:ReceiveTick` | **26 117** | 3.8% |
| 5 | `/Game/Genesis/Dinos/Swarms/InsectSwarmChar_BP.InsectSwarmChar_BP_C:ReceiveTick` | **16 451** | 2.4% |

The first (independent) window of 112 s gave the same leaders with the same orders of magnitude: 255 816 / 148 104 / 104 346 / 23 562 / 10 098 — i.e., the picture is stable, not the noise of one window. The rate of the leader: **≈2.1 thousand calls/s** (283 556 / 132 s), in total the script calls go at ≈5.3 thousand/s.

### 2.3 The A/B: the tracer off / on (both windows in the phase, VALID)

| Window | t/s | ms/tick | CPU over the window | busy | mark |
|---|---|---|---|---|---|
| OFF (no tracer) | **25** | 205 | 635 s | 529% | VALID |
| ON (with the tracer) | **28** | 191 | 653 s | 540% | VALID |

Conclusion: there is no measurable degradation from the substitution of 40 638 `Func` (the difference lies in the phase noise; the tracer spends one hash lookup + an atomic increment per call; the name is resolved once per function).

### 2.4 Priority 2 — the attribution of file IO: the deciding experiment

| Window | Polling `.ark` (our monitor) | Records of `ZwQueryDirectoryFileEx` | The share of waits |
|---|---|---|---|
| A (14:21–14:22:25) | enabled | **333** | 5.0% |
| B (14:22:34–14:24:04) | disabled (`TickProf.arkpoll 0`) | **0** | 0% |

The other leaves of the waits (window B): `ZwDelayExecution` 32 192 (91%), `ZwWaitForSingleObject` 1 352, `ZwQueryInformationProcess` 413.

**The owners of `FWindowsPlatformFile::IterateDirectory` in the exe (Ghidra, `v361_ShooterGameServer.exe`)**

| Caller | Address | Comment |
|---|---|---|
| `FFileManagerGeneric::FindFiles` | `0x141EBAF0` | the call is **virtual** → no direct xrefs, static analysis does not catch it |
| `FPluginManager::FindPluginsRecursively` | `0x141F64200` | scanning the plugin directories (← `FindPluginsIn` `0x141F64DA0`), start-time activity |
| `FFileManagerGeneric::IterateDirectory` | `0x141EBB710` | the second implementation of the interface |
| `UWorldComposition::Rescan` | `0x14275BF00` | called from `ApplySettings` (`0x140DAA7C0`) and `Serialize` (`0x14275B780`) → **only world load/save**, not the tick loop |

### 2.5 Plugins and mods (an inventory)

| Server | Plugins | Mods |
|---|---|---|
| Server1 (the bench) | `FastRejoin`, `Mimalloc` (restored by the owner 22.10 10:11 — not touched), `NoGC`, `NoSteam`, `TickProf` (+`_backup`) | 6 empty mod folders (`CrystalIsles`, `FjordurOfficial`, `LostIsland`, `Ragnarok`, `TheCenter`, `Valguero`), `ActiveMods=` empty |
| Server2 (the user's, not touched) | `_EasyAI`, `FastRejoin`, `Mimalloc.off`, `NetGuard`, `NoSteam` | 7 folders, including `111111111` |

### 2.6 Priority 5 — the phase profile on the full dense base

| Parameter | Value |
|---|---|
| Profile | `prof_682363640` (12:07:35–12:10:05) |
| Samples / frames | **76 747** / 4 480 (≈29.9 t/s) |
| Base | **106 703 actors**, 454 992 components (142 levels) |
| Waits in syscalls | 60 205 (78%) |
| The top of the list (CPU) | `AdvanceToNextIntersectingElement` 1.4%, `ServerOctreeOverlapActors` 1.2%, `FindId` 0.8%, `execDynamicCast` 0.7%, `ProcessContextOpcode` 0.5%, `Invoke` 0.5%, `ProcessInternal+0x95` 0.5% |
| Conclusion | the phase CPU = **the Blueprint VM** (agrees with the bptrace picture: the first three functions give 81% of the script calls) |

### 2.7 Priority 3 — a series of A/B `overlaptrim 2` vs `overlaptrim3`

Protocol: each arm with a common base (`overlapall 0` → a pause → its trim → a pause → a 300 s window), a 300 s window, automatic VALID/CONTAMINATED marking, a decision only over the valid windows. Round 1 ran "as it turns out", round 2 was synchronized with a clean interval between autosaves (the autosave period on the bench is exactly 15 minutes, a 300 s window + preparation ≈11.5 min ⇒ both arms of a pair fit between the saves).

| Pair | A (`overlaptrim 2`) | B (`overlaptrim3`) | Δ t/s | Δ ms/tick | Verdict |
|---|---|---|---|---|---|
| 1 | 50 t/s, 9 ms/tick, VALID | 54 t/s, 6 ms/tick, **CONTAMINATED** (178 of 16 459 frames) | +4.00 | −3.00 | not accepted |
| 2 | 56 t/s, 4 ms/tick, VALID | 50 t/s, 9 ms/tick, **CONTAMINATED** (60 of 15 002 frames) | −6.00 | +5.00 | not accepted |
| 3 | 51 t/s, 9 ms/tick, VALID | 54 t/s, 6 ms/tick, VALID | **+3.00** | **−3.00** | **accepted** |
| 4 | 51 t/s, 9 ms/tick, VALID | 55 t/s, 6 ms/tick, VALID | **+4.00** | **−3.00** | **accepted** |
| 5 | 50 t/s, 10 ms/tick, VALID | 56 t/s, 5 ms/tick, VALID | **+6.00** | **−5.00** | **accepted** |
| 6 | 52 t/s, 9 ms/tick, VALID | 55 t/s, 5 ms/tick, VALID | **+3.00** | **−4.00** | **accepted** |

**The total over the accepted pairs (4 items, the requirement of ≥3 is met):** Δ t/s = **+3.00 … +6.00**, a median of **+3.50**; Δ ms/tick = **−3.00 … −5.00**, a median of **−3.50**. All four pairs are of the same sign ⇒ **trim3 confirmed as the better variant** (agrees with the pair of slot C: +1.60 t/s).

What trim3 does exactly (from the log): `overlaptrim 2` disables `bGenerateOverlapEvents` for **24 059** components and frees **194 462** overlap records; `overlaptrim3` (the whitelist of A2, 11 rules) disables only **796**, keeps by the mark **23 263** and frees **97 990** records.

**A live class-based check of the whitelist:**

| State | components | of them with `bGenerateOverlapEvents` | total overlaps |
|---|---|---|---|
| `overlaptrim 2` | 270 567 | 246 508 | 199 756 |
| `overlaptrim3` | 270 616 | **269 820 (+23 312)** | 199 756 |

That is, under trim3 the overlap events are kept for the components from the whitelist (`ABaseBoxTrigger`, `AHazardTrigger_Slide`, `APrimalStructureBearTrap`, `APrimalStructureTurret`, `APrimalStructureTurretBallista`, `APrimalProjectileGrapplingHook`, `APrimalDinoCharacter`, `Shape/Sphere/Box/CapsuleComponent`) — exactly the part responsible for the traps, turrets, and grapples.

**The decision applied:** the prod config of the bench was switched from `TickProf.overlaptrim 2` to `TickProf.overlaptrim3` (`stand_config.py`, the live application confirmed by the log: `white-mark rules=11 disabled=796 saved by the mark=23263`).

### 2.8 The crash found and fixed (the bench was lost three times)

| Symptom | Diagnostics | Cause | Fix |
|---|---|---|---|
| 2.4–3.0 s after the end of a sampler window the process fell: `AV (c0000005)` in `TickProf.dll+0x26166` (4 sessions in a row) | the unhandled-exception filter in the plugin: `tid 6816` (**not the game thread**), `RSP` points at string data → the heap is corrupted | (1) `delete[] g_wait_stacks` / `g_samples` / `g_returns` — the objects were created by a **scalar** `new std::vector<uint64_t>`, and were freed as arrays (UB → heap corruption); (2) a repeated `g_sampler = std::thread(...)` on top of a joinable thread → `std::terminate` | `delete` instead of `delete[]`; in `CmdStart` — `join()` of the previous thread and freeing the old buffers |
| the window did not stop by itself | `g_auto_stop_at` — a `std::atomic<int>`, and `GetTickCount64()` overflows `int32` on day 25 of uptime | the type `int` | `std::atomic<int64_t>` |

The check after the fix: **three windows in a row** (20 s each) — the server alive, `crashfilter` silent.

---

## 3. Honesty attributes (how to read the numbers)

1. **The plugin numbers are inflated.** `t/s`, `ms/tick`, `cpu` inside the plugin (the windows `TickProf.window`) are computed from `GetThreadTimes` of the game thread; the external control (the whole process) gives other values. The relative comparisons (A against B, the tracer on/off) are correct, the absolute ones are not. As in slots A–C, the referee numbers for the decisions were taken from external Python.
2. **The windows are marked by the automatic marking.** All the windows in this report are `VALID`/`CONTAMINATED` by the automatic mark (a record of `.ark` ⇒ `CONTAMINATED`, no decision was taken over such windows). No manual edits of the marks were made.
3. **`bAllowConcurrentTicks=0` was not touched** in any measurement of this slot.
4. **The top of UFunctions — by the number of calls, not by time.** The tracer counts the calls of script functions; one call can be cheap, another expensive. "A top by calls" ≠ "a top by CPU": the cross-matching with the sample profile (§2.6) shows that the Blueprint VM really dominates the CPU, but the concrete contribution of `InitializeLandingVariables` to the CPU was not measured.
5. **A phase is not reproducible on a schedule.** A phase (t/s 59→28) comes when the base accumulates; in the windows 13:41/13:57/14:00 it was sometimes active (87% of waits), sometimes not. All the A/B windows of this slot were taken in one and the same phase — this was checked by the window mark and by `t/s`.
6. **The phase profile was taken on the full base** (106 703 actors against 106 305 in slot B), but it is not an "ultra-dense" base — the density grew by 0.4%.
7. **The crash in slots B/D is a bug of our own plugin, not of the engine.** It was fixed and verified; before the fix, any measurements after the end of a sampling window were unreliable.
8. **The Ghidra numbers are from the v361 base** (`ghidra_funcs_v361.tsv`, 222 401 functions); the exe addresses correspond to `Server1`.
9. On the bench the `Mimalloc` plugin is active (restored by the owner 22.10 at 10:11, after my backup) — the allocator differs from the standard CRT, this may slightly affect the absolute timings; the A/B comparisons are not affected (the state is identical in both arms).
10. **The bptrace OFF/ON windows (12:02 and 12:04) were taken over the same period**, but not at the same moment — these are different 120-second segments of the phase, so the difference (+3 t/s in favor of the tracer) is noise, not an effect. The conclusion "no overheads" rests on the fact that the tracer adds one hash lookup and one atomic increment to every script call (≈5.3 thousand calls/s ⇒ ≈10 thousand atomic operations/s), not on the t/s number itself. In the period 13:13–13:56 the user's Server2 was running on the machine in parallel (RCON 32331) — the windows of the A/B series (14:25 and beyond) were not affected by this: Server2 was stopped.

---

## 4. What was not done (an honest list)

1. **The prod config switched to `overlaptrim3`** — the A/B series gave 4 valid pairs with a delta of +3…+6 t/s (a median of +3.5) and −3…−5 ms/tick, all of one sign; the switch was made both on the bench and in `stand_config.py`. **But the actual firing of a trap/turret/grapple in game was not checked** (a player is needed in the world) — it was checked only that the overlap events of these classes are not disabled (+23 312 components with `bGenerateOverlapEvents` enabled).
3. **The direct caller of the file IO in the engine was never named** — attribution by the stack is impossible (the waits go on a chain with tail calls: in the 12 words of the stack there is no exe frame), and `FindFiles` is called virtually. It was established that in the measured windows there was no file IO at all, and the whole observed volume was our own monitor. For the residual question "who in the engine scans the directories", a different tool is needed (a Win32 API trace), not a stack.
4. **`UWorldComposition::Rescan` was not checked live** (i.e., it was not confirmed that it storm-spikes during a world save) — this would explain the file IO of slot B (21.10), but would require a profile taken exactly during the save.
5. **The contribution of the specific UFunctions to the CPU was not measured** — only the number of calls.
6. **The crash filter left in the code** (useful, but it is a change in the plugin beyond the task of the slot; if needed, it is easily removed).
7. **The `Mimalloc` plugin on the bench is active** — left as is (the owner's experiment), the A/B results are not affected by this.
8. `REPORT-SLOT-D-BPTRACE.md` — this file; an earlier version of the report (about the first, code-based variant of bptrace) was not overwritten, in order to keep the history of the conclusions.

---

## 5. The tasks of the next slot

1. **The prod config switched to `overlaptrim3`** (see §2.7): the decision taken over 4 valid pairs. It remains to confirm on a real game session that the traps (`ABaseBoxTrigger`, `AHazardTrigger_Slide`), the turrets (`APrimalStructureTurret`, `APrimalStructureTurretBallista`) and the grapple (`APrimalProjectileGrapplingHook`) fire as they should — on the bench it was checked only that the overlap events of these classes are not disabled.
2. **Dissect leader №1:** `Ichthyornis_Character_BP_C:InitializeLandingVariables` — ≈2.1 thousand calls/s on the dense base. Why is an "initialization" function called so often; the candidates — a tick initialization in `ReceiveTick`, or a call from `Buff`/`BuffTickServer` (a grapple/trap throw). One needs an either-profile (a counter by the caller) or a hook of the `Ichthyornis` tick.
3. **Check `Buff_Grappled_BogSpider_C:BuffTickServer` (23.6%)** — the link to the grapples/traps: if the function ticks over all grazed entities of bog spiders, disabling the excessive frequency will give a direct gain.
4. **Finish the IO attribution to the end** (if necessary): a trace of Win32 `FindFirstFile/FindNextFile` with the name of the caller, or a profile taken strictly during a save (a check of `UWorldComposition::Rescan`).
5. **Embed into the permanent monitoring** the rule "a window after sampling = 60 s of silence" (currently the crash was found manually; the automation did not trigger).
6. **Optionally:** enable `bptrace` in a permanent mode with a weekly window (the tracer showed a zero cost by t/s) — this will give the names of the functions in the phase without manual measurements.

---

## 6. Appendices (files)

| File | What |
|---|---|
| `C:\Dev\_research\slotD\ab_pairs.json`, `ab_pairs2.json` | the raw windows of the A/B series (round 1 and round 2) |
| `C:\Dev\_research\slotD\bptrace_and_crash_log.txt` | an excerpt of the plugin log: bptrace (enumeration/substitution/report/rollback) and crashfilter |
| `C:\Dev\_research\slotB\prof_phase_full\prof_682363640.*` | the phase profile on the full base + a named breakdown |
| `C:\Dev\_research\slotB\prof_phase_full\prof_named_report_682363640.txt` | a named breakdown of the phase profile |
| `C:\Dev\_research\slotD_fileio.py`, `slotD_fileseq.py` | the analysis of waits: the owner by the stack, the sequence of leaves |
| `C:\Dev\_research\slotD_ab.py` | the automaton of the A/B series |
| `C:\Dev\_research\fix_bptrace_core.py`, `fix_bptrace_scan2.py` | the transfer of the enumeration to `GetObjectsOfClass`, rewriting the core of the counters |
| `C:\Dev\_research\disasm_crash.py`, `disasm_func.py`, `id_func.py`, `sym_line.py` | the crash analysis (disassembly + finding the owner of a function by lines) |
| `C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp` | the plugin source (bptrace, the crash filter, `arkpoll`, `.wait` v2) |