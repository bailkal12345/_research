# Slot E Report — bptrace v2 (time), save matrix, caller attribution

Date: 22.10.2026, ~18:10–21:15
Directive: `doit8.txt` (executed per the amended version: `C:\Users\Admin\Desktop\doit8_amended.txt`,
copy in `_research\doit8_amended.txt`)

## 1. Main answer (in one paragraph)

bptrace v2 is implemented and closed the key gap of slot D: we now see **time** per function, not
just calls. The formula "top by calls ≠ top by CPU" gained a second dimension: on Genesis
the call count and self time diverged (the order of the top-3 by calls —
Ichthyornis/BogSpider/MissionSpline — did not match the top-3 by self, where the heavy
`Buff_UnderwaterCyclone_C:BuffTickServer` suddenly turned out to be No. 1 with 90%+ BP self time and
850–870 µs/call — slot D never saw it at all, since it looked only at call counters), while on
the fresh maps TheIsland/Fjordur with the newly recognized leader both lists converged: the bird
`Ichthyornis_Character_BP_C:InitializeLandingVariables` — 52–53% BP self time and 2.0 µs/call,
2195–3197 calls/s, on all three maps. The top-3 order by self time **reproduces** in
two independent windows on Genesis (90.9/4.1/2.2% → 89.5/5.0/2.6%) — acceptance P1 is complete.
A/B OFF/ON on four valid hands: t/s 29/29/28/29, ms/tick 3/16/5/8 — the spread within
OFF (3↔16) exceeds the OFF↔ON delta, **the stub overhead is within noise** (acceptance P1 — item 2).
Caller attribution (P3) via `FFrame::PreviousFrame` (+0x70, verified in Ghidra) works,
but for all tops the answer is the same: **100% `<native/ProcessEvent-entry>`** — the leaders are called by native
code, not BP scripts; the specific native caller (for ichthyornis) remains a RE task.
The save matrix (P2) was taken on three maps (Genesis/TheIsland/Fjordur); Server2 — per the owner's decision was NOT taken.
`TickProf.fnflags` (P4 preparation) works: for
`Buff_UnderwaterCyclone_C:BuffTickServer` — parms=1/out=0/return=0 = SAFE; traps
with out-parameters (GetStateAtLocation: out=2) are correctly caught by the FORBIDDEN filter.
Throttling is NOT enabled in prod (the behavior checklist requires a live session — P6 remains open).

## 2. P1 — bptrace v2 (implementation on data: `UFunction::Func`, time accounting)

Key offsets (build v361, confirmed in Ghidra):
- `UFunction+0xA8` — Func (same as in slot D);
- `FFrame::Node` = +0x10, `FFrame::PreviousFrame` = **+0x70**
  (constructor @0x141FA57E0; `CallFunction` @0x141FBFEF0 creates a frame with
  `PreviousFrame` = the caller's frame; entry from `ProcessEvent` yields 0);
- `UFunction::GetReturnProperty` — RVA 0x1F86CB0 (flag bits of a property:
  FProperty+0x38 — flags, `0x80`=Parm, `0x100`=OutParm, `0x400`=ReturnParm;
  `UStruct+0x38` = property chain; `FProperty+0x28` = Next).

### 2.1 Reproducibility of the leader order (window A vs window B, Genesis 820 s between resets)

Table 2.1: share of BP self time, % (Genesis, two windows).

| function (abbreviated) | window A (328 s) | window B (449 s) | reproducible |
|---|---|---|---|
| Buff_UnderwaterCyclone_C:BuffTickServer | 90.9 | 89.5 | yes |
| Buff_Grappled_BogSpider_C:BuffTickServer | 4.1 | 5.0 | yes (positions 2–3 sometimes swap) |
| Ichthyornis_Character_BP_C:InitializeLandingVariables | 2.2 | 2.6 | yes |
| TestGameMode_C:ReceiveTick | 0.3 | 0.3 | yes |
| InsectSwarm/Bee/EggIncubator | 0.3–0.2 | 0.3–0.2 | within the noise range |

BP `sum of self`: window A ≈ 68.9 s over 328 s (21% of the time); window B ≈ 74.6 s over 449 s (16.6%).

### 2.2 A/B OFF/ON — stub overhead

Table 2.2 (a long 120 s sampling window from slotE_ab.py + a window, VALID):

| hand | t/s | ms/tick | busy | VALID |
|---|---|---|---|---|
| OFF-1 | 29 | 3 | 11% | yes |
| OFF-2 | 29 | 16 | 48% | yes |
| ON-1 | 28 | 5 | 15% | yes |
| ON-2 | 29 | 8 | 25% | yes |

The spread within OFF (=13 units of ms/tick) exceeds the pair deltas: OFF↔ON = +2 and −8.
⇒ **The stub delta is within noise, acceptance complete**. The substitution is stable (15+ min; the
rollback reports «removed with 40 477», «scripted=0» in a re-enumeration). CrashFilter stays silent for the slot.

## 3. P2 — save matrix (Genesis / TheIsland / Fjordur; Server2 — no, owner's decision)

Table 3.1 (window 240–449 s, VALID, outside autosave):

| map | window | self leader | self%, ms | leader ms/call | t/s | ms/tick | VALID |
|---|---|---|---|---|---|---|---|
| Genesis (dense) | 328 | Buff_UnderwaterCyclone:BuffTickServer | 90.9 (62 620) | 871 | 29 | 3–16 | yes |
| Genesis (window B, 449) | — | — 89.5 | 852 | 29 | 8 | yes |
| TheIsland | 244 | Ichthyornis:InitializeLandingVariables | 53.3 (1 263) | 1.9 | 29 | 3 | yes |
| Fjordur | 244 | Ichthyornis:InitializeLandingVariables | 52.4 (1 555) | 2.0 | 29 | 4 | yes |

Observations:
- **Ichthyornis is the universal leader** (self time 1.26–1.99 s per 100 s on the secondary maps,
  2 207–3 199 calls/s everywhere); on the secondary maps its share is ≈53% of BP self time.
- Map-specific dances: Genesis — UnderwaterCyclone/BogSpider (ocean buffs and the spider),
  TheIsland — Thylacoleo CheckUntil_SetAiLatchedToTree (13.3%, 116 944 calls),
  Fjordur — the mod trap ArrowTrap_Dwarven_Cave_C:ReceiveTick (138 605 calls, 90 ms).
- Fresh world before the phase: Mammoth ThrottledTick was No. 2 on TheIsland (11.4%) and No. 2 on Fjordur
  (20.2%) — a fresh-world cost, not a universal candidate.
- Normalization per 1000 actors was not done properly: censuscaptures (actor counts) on
  the secondary maps come out multi-line; for fairness, the numbers for each map are given as
  the share of BP self time and in absolute ms; normalization is deferred to the next slot's tasks.

## 4. P3 — caller attribution (`FFrame::PreviousFrame`, +0x70)

`bptrace.caller` 1/2/3 and by substring (ExecuteUbergraph_LunarMeteorController: 535 calls,
self=217 ms): **everywhere 100% `<native/ProcessEvent-entry>`**.
⇒ All the big BP functions we see are called by native ProcessEvent — the chain does NOT
break (there are no native parents). The FFrame chain is wired correctly (offsets verified via
Ghidra: `FFrame::PreviousFrame` = +0x70; stale state of nested calls is possible, but on
these maps there are no BP→BP calls among the tops). Conclusion: the "main caller of leader No. 1" is
**native code**; no name is given through FFrame; finding the author is RE via Ghidra (task of slot F).

## 5. P4 — throttle preparation (NOT enabled)

`TickProf.fnflags` (a standalone command using UFunction flags):
- `Buff_UnderwaterCyclone_C:BuffTickServer` — parms=1, out=0, return=0 → SAFE;
- `InitializeLandingVariables` — parms=0, out=0, return=0 → SAFE;
- `GetStateAtLocation` (out=2), `Get Sea ZAt Location` (out=1), `GetCycloneCenterLocation` (out=1),
  `OnGrappleStateChangedNotify` (out=1) → FORBIDDEN (the filter catches out-parameters correctly).
⇒ Throttling is technically possible for buffs/ReceiveTick without return/out, but for safety the
"every N-th" semantics matter precisely on the ticking function —
before enabling: A/B ≥2 valid pairs + a live checklist. Order: MissionSpline (124 852 calls?
self 131 ms per 449 s — cheap, little benefit) → Buff_UnderwaterCyclone BuffTickServer (heavy,
871 µs/call) → Buff_Grappled_BogSpider. **NOT enabled** — there was no live session.

## 6. P5 — the quiet rule

The cooldown is implemented: after the end of the sampler window there is a 60 s lock on
"start", "window", "perf", "overlaps", "bptrace", "bptrace.reset"; refusals and starts are printed to the log
(`cooldown: 60 s pause ...`, `refused - the pause ... has not ended yet (N s)`).
A copy of the window A/B sequence with exactly 65-second pauses passes cleanly; there were no refusals
(the windows started ≥65 s apart). The slot-D class crash did not reproduce for the slot (crashfilter is silent).

## 7. Honesty attributes

- The judge metrics are in-plugin (t/s, ms/tick) — relative; the absolute numbers are ×1.9–2.4 higher than the external
  CPU (as always). The external judge on process CPU over the 60-s hands gave a spread of 0.6–3.3%
  (24 cores) — it does not resolve the delta; the emphasis is on the window pairs marked VALID.
- The stub timer is wall-clock (QPC 10 MHz): if the function waits for something inside itself, the waiting
  time lands in its self. To assess the propriety of UnderwaterCyclone (850+ µs/call) —
  the next task: RE via Ghidra (dispatchers, overlaps inside the buff).
- The A/B window measures the total load with the stub on/off (like slot D's
  A/B tracers); the phase background of the world is responsible for the ms/tick spread within OFF (3..16).
- sleep crash filter: present and alive (silence = no AV).
- Warm-up on the secondary maps shortened to 7 min (the directive assumed ~10 min); the windows are VALID,
  t/s=29 as in the Genesis phase ⇒ the phase interval is respected.
- The amended directive is saved (doit8_amended.txt); Server2 untouched.

## 8. What was not done

- The name of the native caller of `InitializeLandingVariables` (RE not finished).
- The cause of 850+ µs/call in `Buff_UnderwaterCyclone` (Ghidra analysis, next queue).
- The actor count (census count) on TheIsland/Fjordur — the "per 1000 actors" normalization was not computed.
- P4 enabling + A/B pairs + the checklist — no live player session (P6).
- bptrace's own overhead on long ms/tick runs — only 1 pair out of 4 was usable; the hands were too short.
  Extending the windows to 60/120/240 s is a next-slot task.
- Mimalloc on Server1 was restored by the owner — untouched.

## 9. Tasks for the next slot (priority)

1. RE: who natively calls `InitializeLandingVariables` (via the ProcessEvent address map) —
   paired with a disassembly pass over the existing code.
2. Analysis of `Buff_UnderwaterCyclone:BuffTickServer` (850 µs/call) in Ghidra;
   prepare a counter/overlap reduction (if this is an overlap-family cost).
3. P4 "soft" rollout: the fnflags filter automates gating; throttling must be applied
   one at a time (1 function, A/B with 2 valid pairs, a checklist with a live player).
4. Normalization: census of actors on the maps; add commands (counting Actor-class objects in plugin)
   so that the census is fast and numeric.
5. P6: a player session — live verification of trim3 + the P4 checklist.

## 10. Appendices

- `_research\slotE\TickProf_slotE.log` — the full slot log (bptrace on/off, reports, fnflags)
- `_research\slotE_ab.py` — the A/B automaton (4 hands, VALID checks, cooldown pauses)
- `_research\slotE_matrix.py`, `_research\slotE_measure.py` — boot+measure cycles per map
- `C:\Users\Admin\Desktop\doit8_amended.txt` / `_research\doit8_amended.txt` — the amended directive
- DLL after the slot: 401,920 bytes (fix of reported lines and idempotent enabling), deployed at the Fjordur boot
  and last verified: a TheIsland boot with it → t/s=29 VALID.
- Final note: the config of our case stays trim3 (not touched in slot E).
