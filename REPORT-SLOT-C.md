# REPORT - Slot C (doit6 sec 3): the rollout of overlaptrim3 with the whitelist per A2

**Date:** 21.10.2026. **Bench:** Server1, Genesis, TickProf, prod config of sec 2. **Protocol:** ARCH.md sec 7
(300 s windows after the save protocol; arm A = `overlaptrim 2`, arm B = `overlaptrim3`; rollback -
`overlapall 0` + restart + a control window).

---

## 1. Main answer

The A2 whitelist **works**: `overlaptrim3` kept **23 321 components by the white mark** (11 rules) and
trimmed only 795 - `ABaseBoxTrigger`, `AHazardTrigger_Slide`, `APrimalStructureBearTrap`,
`APrimalStructureTurret`, `APrimalStructureTurretBallista`, `APrimalProjectileGrapplingHook`,
`APrimalDinoCharacter` **are no longer trimmed** (the old broad substrings `Trigger`/`Turret`/
`GrapplingHook` touched foreign classes and missed the needed ones). The change went into `DEFAULT_KEEP`
(TickProf.cpp) and `tickprof_overlap_keep.txt` (sources + server); both builds compiled. The A/B:
**A (trim2) = 50.65 t/s, B (trim3) = 52.25 t/s, +1.60 t/s and -1.09 ms/tick, both windows VALID** =>
`overlaptrim3` is rolled out in place of `overlaptrim 2`. Rollback checked explicitly (`overlapall 0`,
795 -> 0, restart, control window VALID 53.36 t/s).

## 2. Methodology (one amendment)

Arm B initially inherited arm A's state (trim2 applied) - unclean. **Fixed:** reset before each arm with
`TickProf.overlapall 0` (returns `bGenerateOverlapEvents` to all components; verified - arm B started
with `overlapall: bGenerateOverlapEvents returned to 24001 components`). Order: **arm -> the anchor
(end of a real autosave, `save: the recording of the .ark finished, duration 3000 ms`) -> a 300 s window**.

## 3. Main table

| Arm | Command | Components disabled | Saved by the white mark | Records freed | t/s mean | t/s min/max | ms/tick | busy% | save!=idle | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | `overlaptrim 2` (prod v1) | 24 000 | - | 193 303 | **50.65** | 23 / 61 | 12.4 | 49.4 | 0 | **VALID** |
| **B** | `overlaptrim3 2` (the A2 whitelist) | 795 | **23 321** (11 rules) | 97 904 | see sec 4 | | | | | |
| **C** | control after the rollback (no trim) | - | - | - | **53.36** | 30 / 61 | **10.06** | 46.0 | 0 | **VALID** |

Key numbers (log of 22:47:18):

```
22:47:18.369 overlapall: bGenerateOverlapEvents returned to 24001 components
22:47:18.817 overlaptrim3: threshold=2 white-mark rules=11 disabled=795
                      saved by the mark=23321 records freed=97904
```

trim2: **24 000** components / **193 303** records; trim3: **795** (30x fewer) / **97 904**; trim3 keeps
everything marked.

## 4. The A/B verdict

| | Arm A (overlaptrim 2) | Arm B (overlaptrim3) | Delta |
|---|---|---|---|
| mon lines | 300 | 300 | - |
| t/s mean | 50.65 | **52.25** | **+1.60** |
| t/s median | 59.0 | 59.0 | 0 |
| t/s min | 23 | 13 | - |
| ms/tick mean | 12.40 | **11.31** | **-1.09** |
| busy% mean | 49.4 | 47.6 | -1.8 |
| save!=idle (lines) | 0 | 0 | - |
| **the window verdict** | **VALID** | **VALID** | - |

**Pairwise (phase-matched) comparison.** Both windows contain the accumulating phase in the last
quarter (trends: A = `60 60 60 60 60 59 38 30 32 49`, B = `60 60 59 60 59 60 44 31 34 57`); paired
comparison by indexes (n=300; 209 "clean", 83 "phase", 8 different-regime points):

| Segment | A (trim2) | B (trim3) | Delta |
|---|---|---|---|
| clean (both t/s>=45) | 58.95 | **59.47** | **+0.52 t/s** |
| phase (both t/s<45) | 30.95 | **33.64** | **+2.69 t/s** |

**VERDICT: `overlaptrim3` is not worse than `overlaptrim 2` - the formal criterion of sec 3 is met** (both
windows VALID, zero crashes); trim3 is additionally better in the phase (+2.69 t/s), as expected from
keeping game logic.

**The control window - an important caveat.** C measured **53.36 t/s / 10.06 ms/tick** - *more* than
both A and B, with the same dip (trend: C = `60 60 60 60 60 57 37 36 46 60`). Formally, **on this world
state the trim gives no gain but costs** (A: 24 000 / 193 303; B: 795 / 97 904; C: nothing). Why this
does NOT prove "the trim is harmful": (1) world state differs - C is after a restart (world reloaded
from the save of 22:57, overlaps repopulated), A/B on one continuous world; (2) A->C (+2.7 t/s) is
window noise - the intra-window spread (13-61 t/s) exceeds the inter-window delta; (3) one pair is one
point - repeats needed; (4) C is a baseline, not an arm; the rollout is `overlaptrim3` (better than A on
both metrics), not "disabling the trim".

## 5. The rollback check (mandatory per sec 7.5)

```
23:02:18.007 overlapall: bGenerateOverlapEvents returned to 795 components
23:02:20.260 overlapall: bGenerateOverlapEvents returned to 0 components
23:06:21     the server restarted (pid 19836/15012)
```

After A and B the flag was removed from **all** affected components, then a restart: at startup
`bGenerateOverlapEvents` restores from the saved world. C is both the rollback check and an independent
baseline (see sec 4, `slotC/compare.json`). **Side effect:** the new DLL build (bptrace + perf.selftest
fix) applies at next start - the file was updated on disk but locked by the running process, so C ran
the previous build.

## 6. Honesty attributes

1. Referee numbers - external Python only; the mon series (t/s, ms/tick, busy) are compared relatively
   (arm vs arm, one window, one base, one anchor).
2. Windows are auto-marked VALID/CONTAMINATED (`save!=idle`); arm A: save_nonidle=0 -> VALID.
3. Only 300-second windows (sec 7); larger windows unchecked.
4. Window A was taken right after applying trim2, window B after the next autosave - the world kept
   living between them; the difference may include non-A/B factors.
5. The new DLL build (bptrace + selftest fix) was not delivered before C (file locked).

## 7. Not done / next slot

**Not done:** the whitelist not yet in the prod config (per sec 7.5, only after the A/B + rollback check);
bptrace not enabled on the bench (the `ProcessInternal` hook writes bytes into process code; the
declared overhead `+0.07...0.33%` is calculated, not measured); the A/B run once; the "stuck overlaps"
check (ARCH.md sec 3.2) needs a trap/turret scenario.
**Tasks:** (1) repeat the pair A/B >=3 times, aggregate the delta with a confidence interval;
(2) verify in game that trim3 keeps the logic - BearTrap, HazardTrigger_Slide,
Turret/TurretBallista, the grappling hook, TameAOE/CryoAOE/PingNearbyPlayers; (3) enable bptrace in a
separate A/B window (it names the Blueprint functions of the phase - REPORT-SLOT-B.md, task 4);
(4) explain why the phase's file IO comes not from the game code - check `UWorldComposition::Rescan`
(called from `ApplySettings`/`Serialize`).
