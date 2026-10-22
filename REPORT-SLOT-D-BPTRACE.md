# Slot D - bptrace via a data patch of `UFunction::Func` (+ the attribution of file IO, the profiler crash bug)

Date: 22.10.2026. Bench: `Server1` (Genesis, full dense base). Prod config sec 2
(`maxfps 60`, `fixclamp 0`, `fncache 1`, `iscache 1`, `cachename 1`, `nochart 1`, `overlaptrim 2`).

---

## 1. Main answer

Priority 1 closed: **the Blueprint tracer was built without a single patch byte in process code** - it
scans engine data (`UFunction+0xA8` = the field `Func`; for script functions it holds `&ProcessInternal`,
RVA `0x1FC0270`; on the dense base **40 638 of 40 639 UFunction** are script ones). Substituting `Func`
takes **1.4 s**; process code and the security cookie untouched; rollback writes the original `Func`
back (verified by re-enumeration). Phase top-5 of calls: **`Ichthyornis_Character_BP_C:InitializeLandingVariables`
(283 556, 40.7%)**, `Buff_Grappled_BogSpider_C:BuffTickServer` (164 164), `MissionSpline_Base_C:ReceiveTick`
(115 661), `VRBattle_CodeKeyTumbler_C:ReceiveTick` (26 117), `InsectSwarmChar_BP_C:ReceiveTick` (16 451).
Incidentally but important: **the server crash was found and eliminated** (the bench was lost three
times) - `delete[]` on scalar-`new` objects corrupted the heap, and a repeated `std::thread` on a
joinable thread gave `std::terminate`; after the fix, three windows ran without falls. Priority 2:
**all visible file IO in the profile is our own monitor** (333 `ZwQueryDirectoryFileEx` records with
`.ark` polling vs **0** without); in the engine, `UWorldComposition::Rescan` runs only at world
load/save, not in the tick loop. Priority 3: **4 valid A/B pairs out of 6, all one sign - `overlaptrim3`
faster than `overlaptrim 2` by +3...+6 t/s (median +3.5) and -3...-5 ms/tick**; the prod config switched to
`overlaptrim3` (verified: traps/turrets/grapples keep their overlap events, +23 312 components).

---

## 2. Main table

### 2.1 bptrace: the full cycle on the live server

`TickProf.bptrace 2` - enumeration, no patch: UFunction total **40 639**, script
(`Func==&ProcessInternal`) **40 638**; `TickProf.bptrace 1` - **40 638 substituted in 1.4 s**, process
code not patched; `TickProf.bptrace.report` - **695 851 calls, 76 distinct functions** (names via
`GetFullName`); `TickProf.bptrace 0` - rollback: "disabled (calls 0), the substitutions lifted from
40638 UFunctions"; a re-enumeration gives 40 638 / 40 639.

### 2.2 The phase top-5 UFunctions (a 132 s window, the tracer on)

| # | Function | Calls | Share |
|---|---|---|---|
| 1 | `/Game/PrimalEarth/Dinos/Ichthyornis/Ichthyornis_Character_BP.Ichthyornis_Character_BP_C:InitializeLandingVariables` | **283 556** | 40.7% |
| 2 | `/Game/Genesis/Dinos/BogSpider/Buff_Grappled_BogSpider.Buff_Grappled_BogSpider_C:BuffTickServer` | **164 164** | 23.6% |
| 3 | `/Game/Genesis/Missions/MissionSpline_Base.MissionSpline_Base_C:ReceiveTick` | **115 661** | 16.6% |
| 4 | `/Game/Genesis/Missions/VRBattle/VRBattle_CodeKeyTumbler.VRBattle_CodeKeyTumbler_C:ReceiveTick` | **26 117** | 3.8% |
| 5 | `/Game/Genesis/Dinos/Swarms/InsectSwarmChar_BP.InsectSwarmChar_BP_C:ReceiveTick` | **16 451** | 2.4% |

An independent 112 s window gave the same leaders: 255 816 / 148 104 / 104 346 / 23 562 / 10 098. The
leader's rate: **~2.1 thousand calls/s** (283 556 / 132 s); script calls overall ~5.3 thousand/s.

### 2.3 The A/B: tracer off / on (both VALID, in the phase)

| Window | t/s | ms/tick | CPU over the window | busy | mark |
|---|---|---|---|---|---|
| OFF (no tracer) | **25** | 205 | 635 s | 529% | VALID |
| ON (with the tracer) | **28** | 191 | 653 s | 540% | VALID |

No measurable degradation (the difference is phase noise; the tracer adds one hash lookup + an atomic
increment per call, name resolved once per function).

### 2.4 Priority 2 - file IO: the deciding experiment

| Window | Polling `.ark` (our monitor) | Records of `ZwQueryDirectoryFileEx` | Share of waits |
|---|---|---|---|
| A (14:21-14:22:25) | enabled | **333** | 5.0% |
| B (14:22:34-14:24:04) | disabled (`TickProf.arkpoll 0`) | **0** | 0% |

Other wait leaves in B: `ZwDelayExecution` 32 192 (91%), `ZwWaitForSingleObject` 1 352,
`ZwQueryInformationProcess` 413.

**The owners of `FWindowsPlatformFile::IterateDirectory` in the exe (Ghidra, `v361_ShooterGameServer.exe`)**

| Caller | Address | Comment |
|---|---|---|
| `FFileManagerGeneric::FindFiles` | `0x141EBAF0` | the call is **virtual** -> no direct xrefs, static analysis does not catch it |
| `FPluginManager::FindPluginsRecursively` | `0x141F64200` | scanning plugin directories (<- `FindPluginsIn` `0x141F64DA0`), start-time activity |
| `FFileManagerGeneric::IterateDirectory` | `0x141EBB710` | the second interface implementation |
| `UWorldComposition::Rescan` | `0x14275BF00` | called from `ApplySettings` (`0x140DAA7C0`) and `Serialize` (`0x14275B780`) -> **only world load/save**, not the tick loop |

### 2.5 Plugins and mods (an inventory)

Server1 (the bench): `FastRejoin`, `Mimalloc` (restored by the owner 22.10 10:11 - untouched), `NoGC`,
`NoSteam`, `TickProf` (+`_backup`); 6 empty mod folders (`CrystalIsles`, `FjordurOfficial`,
`LostIsland`, `Ragnarok`, `TheCenter`, `Valguero`), `ActiveMods=` empty. Server2 (the user's,
untouched): `_EasyAI`, `FastRejoin`, `Mimalloc.off`, `NetGuard`, `NoSteam`; 7 folders, including
`111111111`.

### 2.6 Priority 5 - the phase profile on the full dense base

`prof_682363640` (12:07:35-12:10:05): **76 747 samples / 4 480 frames** (~29.9 t/s); **106 703 actors**,
454 992 components (142 levels); waits in syscalls 60 205 (78%). CPU top: `AdvanceToNextIntersectingElement`
1.4%, `ServerOctreeOverlapActors` 1.2%, `FindId` 0.8%, `execDynamicCast` 0.7%, `ProcessContextOpcode`
0.5%, `Invoke` 0.5%, `ProcessInternal+0x95` 0.5%. Conclusion: the phase CPU = **the Blueprint VM**
(bptrace agreement: the first three functions give 81% of script calls).

### 2.7 Priority 3 - A/B series `overlaptrim 2` vs `overlaptrim3`

Protocol: each arm on a common base (`overlapall 0` -> pause -> its trim -> pause -> 300 s window),
automatic VALID/CONTAMINATED mark, decisions over valid windows only. Round 2 synchronized to a clean
interval between autosaves (the autosave period on the bench is exactly 15 min; a 300 s window +
preparation ~11.5 min => both arms fit between saves).

| Pair | A (`overlaptrim 2`) | B (`overlaptrim3`) | d t/s | d ms/tick | Verdict |
|---|---|---|---|---|---|
| 1 | 50 t/s, 9 ms/tick, VALID | 54 t/s, 6 ms/tick, **CONTAMINATED** (178 of 16 459 frames) | +4.00 | -3.00 | not accepted |
| 2 | 56 t/s, 4 ms/tick, VALID | 50 t/s, 9 ms/tick, **CONTAMINATED** (60 of 15 002 frames) | -6.00 | +5.00 | not accepted |
| 3 | 51 t/s, 9 ms/tick, VALID | 54 t/s, 6 ms/tick, VALID | **+3.00** | **-3.00** | **accepted** |
| 4 | 51 t/s, 9 ms/tick, VALID | 55 t/s, 6 ms/tick, VALID | **+4.00** | **-3.00** | **accepted** |
| 5 | 50 t/s, 10 ms/tick, VALID | 56 t/s, 5 ms/tick, VALID | **+6.00** | **-5.00** | **accepted** |
| 6 | 52 t/s, 9 ms/tick, VALID | 55 t/s, 5 ms/tick, VALID | **+3.00** | **-4.00** | **accepted** |

**Over the 4 accepted pairs (the >=3 requirement met):** t/s = **+3.00 ... +6.00** (median **+3.50**);
ms/tick = **-3.00 ... -5.00** (median **-3.50**); one sign => **trim3 confirmed** (agrees with slot C:
+1.60 t/s).

From the log: `overlaptrim 2` disables `bGenerateOverlapEvents` for **24 059** components and frees
**194 462** records; `overlaptrim3` (A2, 11 rules) - **796** disabled, **23 263** kept by the mark,
**97 990** freed.

**Live class check of the whitelist:**

| State | components | with `bGenerateOverlapEvents` | total overlaps |
|---|---|---|---|
| `overlaptrim 2` | 270 567 | 246 508 | 199 756 |
| `overlaptrim3` | 270 616 | **269 820 (+23 312)** | 199 756 |

Under trim3 the whitelisted classes keep their overlap events (`ABaseBoxTrigger`,
`AHazardTrigger_Slide`, `APrimalStructureBearTrap`, `APrimalStructureTurret`,
`APrimalStructureTurretBallista`, `APrimalProjectileGrapplingHook`, `APrimalDinoCharacter`,
`Shape/Sphere/Box/CapsuleComponent`). **Applied:** the prod config switched to `TickProf.overlaptrim3`
(`stand_config.py`; log: `white-mark rules=11 disabled=796 saved by the mark=23263`).

### 2.8 The crash found and fixed (three bench losses)

| Symptom | Diagnostics | Cause | Fix |
|---|---|---|---|
| 2.4-3.0 s after a sampler window ends the process fell: `AV (c0000005)` in `TickProf.dll+0x26166` (4 sessions in a row) | unhandled-exception filter: `tid 6816` (**not the game thread**), `RSP` points at string data -> heap corrupted | (1) `delete[] g_wait_stacks` / `g_samples` / `g_returns` - objects created by a **scalar** `new std::vector<uint64_t>` and freed as arrays (UB); (2) a repeated `g_sampler = std::thread(...)` on a joinable thread -> `std::terminate` | `delete` instead of `delete[]`; in `CmdStart` - `join()` the previous thread, free the old buffers |
| the window did not stop by itself | `g_auto_stop_at` - a `std::atomic<int>`; `GetTickCount64()` overflows `int32` on day 25 of uptime | the type `int` | `std::atomic<int64_t>` |

After the fix: **three windows in a row** (20 s each) - alive, `crashfilter` silent.

---

## 3. Honesty attributes

1. Plugin numbers (`t/s`, `ms/tick`, `cpu` in `TickProf.window`, from `GetThreadTimes` of the game
   thread) are inflated; relative comparisons correct, absolute ones not - referee numbers came from
   external Python (as in A-C).
2-3. Windows carry the automatic VALID/CONTAMINATED mark (a `.ark` record => CONTAMINATED); no
   decisions over such windows, no manual mark edits; `bAllowConcurrentTicks=0` untouched in this slot.
4-7. The UFunction top is **by calls, not by time** (Blueprint VM dominates the CPU per sec 2.6; the CPU
   contribution of `InitializeLandingVariables` not measured). A phase is not reproducible on a
   schedule (t/s 59->28 when the base accumulates); at 13:41/13:57/14:00 it was sometimes active (87%
   of waits), sometimes not - all A/B windows of this slot were in one and the same phase (checked by
   mark and t/s). The phase profile is on the full base (106 703 actors vs 106 305 in slot B; density
   +0.4%). The crash is a plugin bug, not an engine bug; before the fix, measurements after a sampling
   window were unreliable.
8-9. Ghidra numbers from the v361 base (`ghidra_funcs_v361.tsv`, 222 401 functions), exe addresses match
   `Server1`; `Mimalloc` active on the bench (owner's experiment) may shift absolute timings, the A/B
   state is identical in both arms. The bptrace OFF/ON windows (12:02 / 12:04) are different 120-second
   phase segments - the +3 t/s is noise; "no overheads" rests on the cost model (one hash lookup + one
   atomic increment per call; ~5.3 thousand calls/s => ~10 thousand atomics/s). Server2 ran in parallel
   13:13-13:56 (RCON 32331); the A/B windows (14:25+) were unaffected.

---

## 4. Not done / next slot

1. **trim3 in the prod config** is decided over 4 valid pairs and applied (`stand_config.py`), but the
   actual firing of a trap/turret/grapple was **not checked in game** (a player needed); only that the
   overlap events of these classes are not disabled (+23 312 components). Confirm on a real session.
2. **Dissect No. 1** `Ichthyornis_Character_BP_C:InitializeLandingVariables` - ~2.1 thousand calls/s; why
   is an "initialization" called so often (a tick init in `ReceiveTick`? a call from
   `Buff`/`BuffTickServer`?); needs a counter by caller or an `Ichthyornis` tick hook.
3. **Check `Buff_Grappled_BogSpider_C:BuffTickServer` (23.6%)** - if it ticks over all grazed entities,
   reducing the frequency gives a direct gain.
4. **The engine's file-IO caller was never named** - impossible by stack (tail-call chain, no exe frame
   in the 12 words) and `FindFiles` is called virtually; in the measured windows there was no engine IO
   at all (the whole observed volume was our monitor). A Win32 API trace, or a profile strictly during
   a save (a check of `UWorldComposition::Rescan`) - would explain the slot-B IO of 21.10. Also
   unmeasured: the CPU contribution of specific UFunctions (calls only). Housekeeping: the crash filter
   left in the code (easily removed), `Mimalloc` left active, an earlier version of this report (the
   code-based bptrace variant) kept untouched.
5. Embed the rule "a window after sampling = 60 s of silence" permanently; optionally a permanent
   weekly `bptrace` window.

---

## 5. Appendices (files)

`C:\Dev\_research\slotD\ab_pairs.json` + `ab_pairs2.json` (raw A/B windows, rounds 1-2);
`slotD\bptrace_and_crash_log.txt` (plugin log: bptrace + crashfilter);
`slotB\prof_phase_full\prof_682363640.*` + `prof_named_report_682363640.txt` (phase profile on the full
base + named breakdown); `slotD_fileio.py` / `slotD_fileseq.py` / `slotD_ab.py` (wait analysis by
stack / leaf sequence / A/B automaton); `fix_bptrace_core.py` / `fix_bptrace_scan2.py` (enumeration via
`GetObjectsOfClass`, counter rewrite); `disasm_crash.py` / `disasm_func.py` / `id_func.py` /
`sym_line.py` (crash analysis); `C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp` (the plugin
source: bptrace, crash filter, `arkpoll`, `.wait` v2).
