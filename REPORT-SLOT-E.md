# Slot E Report - bptrace v2 (time), save matrix, caller attribution

Date: 22.10.2026, ~18:10-21:15
Directive: `doit8.txt` (executed per the amended version: `C:\Users\Admin\Desktop\doit8_amended.txt`,
copy in `_research\doit8_amended.txt`)

## 1. Main answer

bptrace v2 gives **time** per function, closing slot D's key gap. On Genesis the call count and self
time diverged: the heavy `Buff_UnderwaterCyclone_C:BuffTickServer` is No. 1 by self (90%+ BP self time,
850-870 us/call) - slot D never saw it (call counters only) - while on the fresh maps
TheIsland/Fjordur both lists converged on `Ichthyornis_Character_BP_C:InitializeLandingVariables`
(52-53% BP self time, 2.0 us/call, 2195-3197 calls/s, on all three maps). The top-3 order by self
reproduces over two Genesis windows 820 s apart (90.9/4.1/2.2% -> 89.5/5.0/2.6%) - P1 complete. A/B
OFF/ON over four valid hands: t/s 29/29/28/29, ms/tick 3/16/5/8 - the OFF-internal spread (3<->16)
exceeds the OFF<->ON delta; **stub overhead within noise** (P1 item 2). Caller attribution (P3) via
`FFrame::PreviousFrame` (+0x70, verified in Ghidra) works: for all tops the answer is **100%
`<native/ProcessEvent-entry>`** - the leaders are called by native code; the native caller of
ichthyornis remains a RE task. Save matrix (P2) on three maps (Genesis/TheIsland/Fjordur); Server2 -
per the owner's decision, NOT taken. `TickProf.fnflags` (P4 prep) works:
`Buff_UnderwaterCyclone_C:BuffTickServer` parms=1/out=0/return=0 = SAFE; out-parameter traps
(GetStateAtLocation: out=2) are correctly FORBIDDEN. Throttling NOT enabled in prod (a live session is
required - P6 open).

## 2. P1 - bptrace v2 (implementation on data: `UFunction::Func`, time accounting)

Key offsets (build v361, Ghidra-confirmed): `UFunction+0xA8` - Func (as in slot D); `FFrame::Node`
+0x10, `FFrame::PreviousFrame` **+0x70** (constructor @0x141FA57E0; `CallFunction` @0x141FBFEF0 creates
a frame with `PreviousFrame` = the caller's frame; `ProcessEvent` entry yields 0);
`UFunction::GetReturnProperty` - RVA 0x1F86CB0 (flags: FProperty+0x38, `0x80`=Parm, `0x100`=OutParm,
`0x400`=ReturnParm; `UStruct+0x38` = property chain; `FProperty+0x28` = Next).

### 2.1 Reproducibility of the leader order (window A vs B, 820 s between resets)

| function (abbreviated) | window A (328 s) | window B (449 s) | reproducible |
|---|---|---|---|
| Buff_UnderwaterCyclone_C:BuffTickServer | 90.9 | 89.5 | yes |
| Buff_Grappled_BogSpider_C:BuffTickServer | 4.1 | 5.0 | yes (positions 2-3 sometimes swap) |
| Ichthyornis_Character_BP_C:InitializeLandingVariables | 2.2 | 2.6 | yes |
| TestGameMode_C:ReceiveTick | 0.3 | 0.3 | yes |
| InsectSwarm/Bee/EggIncubator | 0.3-0.2 | 0.3-0.2 | within noise |

BP `sum of self`: A ~68.9 s / 328 s (21%); B ~74.6 s / 449 s (16.6%).

### 2.2 A/B OFF/ON - stub overhead

(slotE_ab.py, 120 s sampling window + a window, VALID)

| hand | t/s | ms/tick | busy | VALID |
|---|---|---|---|---|
| OFF-1 | 29 | 3 | 11% | yes |
| OFF-2 | 29 | 16 | 48% | yes |
| ON-1 | 28 | 5 | 15% | yes |
| ON-2 | 29 | 8 | 25% | yes |

The OFF-internal spread (=13 ms/tick units) exceeds the pair deltas (+2 / -8). **The stub delta is
within noise, acceptance complete.** Substitution stable 15+ min (rollback reports "removed with
40 477", "scripted=0" in a re-enumeration); CrashFilter silent.

## 3. P2 - save matrix (Genesis / TheIsland / Fjordur; Server2 - no, owner's decision)

| map | window | self leader | self%, ms | leader ms/call | t/s | ms/tick | VALID |
|---|---|---|---|---|---|---|---|
| Genesis (dense) | 328 | Buff_UnderwaterCyclone:BuffTickServer | 90.9 (62 620) | 871 | 29 | 3-16 | yes |
| Genesis (window B, 449) | - | - 89.5 | 852 | 29 | 8 | yes |
| TheIsland | 244 | Ichthyornis:InitializeLandingVariables | 53.3 (1 263) | 1.9 | 29 | 3 | yes |
| Fjordur | 244 | Ichthyornis:InitializeLandingVariables | 52.4 (1 555) | 2.0 | 29 | 4 | yes |

- **Ichthyornis is the universal leader** (1.26-1.99 s per 100 s on the secondary maps, 2 207-3 199
  calls/s everywhere; ~53% of BP self time on the secondary maps).
- Map-specific dances: Genesis - UnderwaterCyclone/BogSpider; TheIsland - Thylacoleo
  CheckUntil_SetAiLatchedToTree (13.3%, 116 944 calls); Fjordur - the mod trap
  ArrowTrap_Dwarven_Cave_C:ReceiveTick (138 605 calls, 90 ms).
- Fresh world before the phase: Mammoth ThrottledTick No. 2 on TheIsland (11.4%) and on Fjordur (20.2%)
  - a fresh-world cost, not a universal candidate.
- Per-1000-actors normalization was not done properly (multi-line census captures on the secondary
  maps); figures are given as BP self share + absolute ms; normalization deferred.

## 4. P3 - caller attribution (`FFrame::PreviousFrame`, +0x70)

`bptrace.caller` 1/2/3 and by substring (ExecuteUbergraph_LunarMeteorController: 535 calls, self=217
ms): **everywhere 100% `<native/ProcessEvent-entry>`** - all big BP functions are called by native
ProcessEvent; the chain does not break (no native parents). The FFrame chain is wired correctly
(offsets Ghidra-verified; stale state of nested calls possible, but no BP->BP calls among the tops on
these maps). The main caller of leader No. 1 is **native code**; no name through FFrame - RE via Ghidra
(slot F).

## 5. P4 - throttle preparation (NOT enabled)

`TickProf.fnflags`: `Buff_UnderwaterCyclone_C:BuffTickServer` - parms=1/out=0/return=0 -> SAFE;
`InitializeLandingVariables` - parms=0/out=0/return=0 -> SAFE; `GetStateAtLocation` (out=2),
`Get Sea ZAt Location` (out=1), `GetCycloneCenterLocation` (out=1), `OnGrappleStateChangedNotify`
(out=1) -> FORBIDDEN (the filter catches out-parameters). Throttling is technically possible for
buffs/ReceiveTick without return/out; "every N-th" semantics must sit on the ticking function - before
enabling: an A/B of >=2 valid pairs + a live checklist. Order: MissionSpline (124 852 calls? self 131 ms
per 449 s - cheap) -> Buff_UnderwaterCyclone BuffTickServer (heavy, 871 us/call) ->
Buff_Grappled_BogSpider. **NOT enabled** - no live session.

## 6. P5 - the quiet rule

A 60 s lock after the sampler window ends on "start", "window", "perf", "overlaps", "bptrace",
"bptrace.reset"; refusals/starts logged (`cooldown: 60 s pause ...`, `refused - the pause ... has not
ended yet (N s)`). The A/B sequence copy with exactly 65-second pauses passes cleanly; no refusals. The
slot-D-class crash did not reproduce (crashfilter silent).

## 7. Honesty attributes

Judge metrics in-plugin (t/s, ms/tick) - relative; absolutes x1.9-2.4 above the external CPU. The
external judge on process CPU over the 60-s hands spread 0.6-3.3% (24 cores) - does not resolve the
delta; emphasis on the VALID window pairs. The stub timer is wall-clock (QPC 10 MHz): internal
waiting lands in self; assessing UnderwaterCyclone (850+ us/call) needs RE via Ghidra (dispatchers,
overlaps inside the buff). The A/B window measures the total load stub on/off (as in slot D); the
world's phase background explains the OFF-internal ms/tick spread (3..16). Sleep crash filter
present and alive (silence = no AV). Warm-up on the secondary maps shortened to 7 min (directive
assumed ~10); windows VALID, t/s=29 as in the Genesis phase => the phase interval respected. Amended
directive saved (doit8_amended.txt); Server2 untouched.

## 8. Not done / next slot

- The native caller of `InitializeLandingVariables` (RE via the ProcessEvent address map + a
  disassembly pass; slot F).
- The cause of 850+ us/call in `Buff_UnderwaterCyclone` (Ghidra; a counter/overlap reduction if this is
  an overlap-family cost).
- Actor census on TheIsland/Fjordur - "per 1000 actors" normalization not computed; add plugin commands
  counting Actor-class objects (fast, numeric census).
- P4 enabling + A/B pairs + the checklist - no live player session (P6); throttle one function at a
  time (A/B with 2 valid pairs).
- bptrace's own overhead on long ms/tick runs - only 1 of 4 pairs usable (hands too short); extend
  windows to 60/120/240 s.
- P6: a player session - live verification of trim3 + the P4 checklist. `Mimalloc` on Server1
  restored by the owner - untouched.

## 10. Appendices

`_research\slotE\TickProf_slotE.log` (the full slot log); `slotE_ab.py` (the A/B automaton: 4 hands,
VALID checks, cooldown pauses); `slotE_matrix.py` / `slotE_measure.py` (boot+measure cycles per map);
`doit8_amended.txt` (Desktop + `_research`). DLL after the slot: 401,920 bytes (fix of reported lines
and idempotent enabling), deployed at the Fjordur boot and verified on a TheIsland boot -> t/s=29 VALID.
Final note: the config of our case stays trim3 (not touched in slot E).
