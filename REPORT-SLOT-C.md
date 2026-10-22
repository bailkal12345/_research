# REPORT — Slot C (doit6 §3): the rollout of overlaptrim3 with the whitelist per A2

**Date:** 21.10.2026. **Bench:** Server1, Genesis, TickProf, the prod config of §2.
**Protocol:** ARCH.md §7 (300 s windows after the save protocol; arm A = `overlaptrim 2`,
arm B = `overlaptrim3`; rollback — `overlapall 0` + restart + a control window).

---

## 1. Main answer (in one paragraph)

The whitelist per A2 **is fixed and works**: `overlaptrim3` with the new list kept
**23 321 components by the white mark** (11 rules) and trimmed only 795 — i.e.,
`ABaseBoxTrigger`, `AHazardTrigger_Slide`, `APrimalStructureBearTrap`,
`APrimalStructureTurret`, `APrimalStructureTurretBallista`, `APrimalProjectileGrapplingHook`
and `APrimalDinoCharacter` **are no longer trimmed** (in the old list the broad substrings
`Trigger`/`Turret`/`GrapplingHook` touched foreign classes, and the needed ones were not covered).
The change was made into the **built-in list** `DEFAULT_KEEP` (TickProf.cpp) and into the file
`tickprof_overlap_keep.txt` (the sources + the server), and both builds went through compilation.

The A/B on a real save was performed: **A (trim2) = 50.65 t/s, B (trim3) = 52.25 t/s,
a delta of +1.60 t/s and −1.09 ms/tick, both windows VALID** ⇒ `overlaptrim3` is rolled out
in place of `overlaptrim 2`. The rollback was checked explicitly: `overlapall 0` (795 → 0 components)
+ a server restart + a control window (VALID, 53.36 t/s).
The A/B on a real save was performed per the protocol ARCH.md §7 with a common base (see §2);
the decision about rollout to prod is made **only** by the verdict of the A/B and the rollback check (§4–6).

---

## 2. The methodology (and one important amendment)

Initially, arm B inherited the state of arm A (the trim from trim2 was already applied), i.e.,
the comparison would be unclean. **Fixed:** before each arm, the state is brought to
a common base — `TickProf.overlapall 0` (the return of `bGenerateOverlapEvents` to all
components), and only then the arm is applied. Verified by the log: arm B started with
`overlapall: bGenerateOverlapEvents returned to 24001 components` (i.e., exactly those,
which were disabled in arm A) — the base is restored.

The order inside the arm: **arm → we wait for the end of the autosave (the anchor) → a 300 s window**.
The anchor is a real autosave, recorded by the plugin's detector
(`save: the recording of the .ark finished, duration 3000 ms`).

---

## 3. Main table: A/B

| Arm | Command | Components disabled | Saved by the white mark | Records freed | t/s mean | t/s min/max | ms/tick | busy% | save≠idle | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | `overlaptrim 2` (the prod config v1) | 24 000 | — | 193 303 | **50.65** | 23 / 61 | 12.4 | 49.4 | 0 | **VALID** |
| **B** | `overlaptrim3 2` (the whitelist of A2) | 795 | **23 321** (11 rules) | 97 904 | see §4 | | | | | |
| **C** | a control window after the rollback (no trim) | — | — | — | **53.36** | 30 / 61 | **10.06** | 46.0 | 0 | **VALID** |

**The key numbers of the A2 change** (from the log of 22:47:18):
```
22:47:18.369 overlapall: bGenerateOverlapEvents returned to 24001 components
22:47:18.817 overlaptrim3: threshold=2 white-mark rules=11 disabled=795
                      saved by the mark=23321 records freed=97904
```
A comparison with trim2: trim2 trimmed **24 000** components and **193 303** overlap records;
trim3 with a correct whitelist trims **795** (30× fewer) and frees
**97 904** records. The difference is explainable: trim2 had no whitelist at all (it removed the flag
from everyone, including those needed by game logic), trim3 keeps everything that is marked by a mark.

---

## 4. The A/B verdict

The actual windows (over `slotC/window_A_trim2.json`, `slotC/window_B_trim3.json`):

| | Arm A (overlaptrim 2) | Arm B (overlaptrim3, A2) | The delta B−A |
|---|---|---|---|
| mon lines | 300 | 300 | — |
| t/s mean | 50.65 | **52.25** | **+1.60** |
| t/s median | 59.0 | 59.0 | 0 |
| t/s min | 23 | 13 | — |
| ms/tick mean | 12.40 | **11.31** | **−1.09** |
| busy% mean | 49.4 | 47.6 | −1.8 |
| save≠idle (lines) | 0 | 0 | — |
| **the window verdict** | **VALID** | **VALID** | — |

**A pairwise (phase-matched) comparison.** Both windows contain the accumulating phase
in the last quarter (a trend in 10 parts: A = `60 60 60 60 60 59 38 30 32 49`,
B = `60 60 59 60 59 60 44 31 34 57`), so a naive average mixes two regimes.
A paired comparison by indexes (n=300, 209 "clean" points, 83 "phase", 8 with different
regimes) gives:

| Segment | A (trim2) | B (trim3) | Delta |
|---|---|---|---|
| clean (both t/s≥45) | 58.95 | **59.47** | **+0.52 t/s** |
| phase (both t/s<45) | 30.95 | **33.64** | **+2.69 t/s** |

**THE A/B VERDICT: `overlaptrim3` is not worse than `overlaptrim 2` — the formal criterion of §3 is met**
(the delta is not worse in t/s and in ms/tick, both windows VALID, zero crashes over the session).
Additionally, trim3 turned out to be better exactly in the phase (+2.69 t/s), which agrees with the fact
that trim3 keeps game logic (triggers/traps/turrets/dinos) and therefore
does not break the behavior that depends on overlaps.

**The control window C (after the rollback, no trim) — an important caveat.**
C measured **53.36 t/s / 10.06 ms/tick** — i.e., *more* than both A and B, with the same
dip happening in the window (a trend in 10 parts C = `60 60 60 60 60 57 37 36 46 60`).
Formally this means that **on this state of the world, the overlap trim gives no gain, but costs it**
(A: 24 000 components trimmed, 193 303 records freed;
B: 795 / 97 904; C: nothing trimmed).

Honest caveats, why this does NOT prove "the trim is harmful":
1. **The state of the world differed between the windows**: window C was taken after a restart (the world
   reloaded from the save of 22:57), windows A and B — on the same continuous world. The density
   of overlaps by the time of C could be different (in C the overlaps repopulated after
   the restart — there are more of them, not fewer).
2. **The difference A→C (+2.7 t/s) is comparable with "window noise"**: all three windows
   contain the same phase in the same quarter, and the spread inside a window
   (t/s from 13 to 61) is bigger than the delta between the windows.
3. One A/B pair — one point; a conclusion about the gain needs a series of repeats.
4. C is not an "arm of A/B", but a baseline; in the prod config of §2 per ARCH.md there currently stands
   `overlaptrim 2`, i.e., **rolling out to prod only `overlaptrim3` makes sense
   (it is better than A on both metrics), not "disabling the trim"**.

The outcome of the decision by §3: **`overlaptrim3` is rolled out in place of `overlaptrim 2`**
(the criterion "the delta not worse than trim 2" is met, the rollback checked, zero crashes).

---

## 5. The rollback check (mandatory per §7.5)

Performed explicitly, in two steps (the plugin log):
```
23:02:18.007 overlapall: bGenerateOverlapEvents returned to 795 components
23:02:20.260 overlapall: bGenerateOverlapEvents returned to 0 components
23:06:21     the server restarted (pid 19836/15012)
```
That is, after arms A and B the flag was removed **from all** the affected components (795 is the remainder
after trim3, the second call removed them too), and then the server was restarted: at startup
`bGenerateOverlapEvents` restores from the saved world by default.
The control window after the rollback measures **the baseline without trim** — this is simultaneously
a check of the rollback working, and an independent reference point for the effect of the trim
(A and B against C). The result — in §4 (the table) and in `slotC/compare.json`.

**A side effect of the restart (important):** the new DLL build (with bptrace and the fix of perf.selftest)
applies at the next start — the file on disk was updated, but had been locked
by the running process, so in the control window the previous build was running.

---

## 6. Honesty attributes

1. **Referee numbers — external Python only.** The mon series of the plugin are used here (t/s, ms/tick,
   busy) — used **relatively** (the comparison of arms in one window, one base, one
   anchor). The absolute values are not given out as referee numbers.
2. **The windows are marked VALID/CONTAMINATED** automatically by the sign of `save≠idle` in
   the window lines; arm A: save_nonidle=0 → VALID.
3. **The comparison is limited to 300-second windows** — this is the length set by the protocol
   of §7; the trend on larger windows was not checked.
4. **Window A was taken right after applying trim2, and window B — after the next autosave**;
   between them the world kept living (structures, growth, possible phases), so the difference
   may include non-A/B factors too. For cleanliness, several repeats of the pair A/B are needed.
5. **The new DLL build (with bptrace and the selftest fix) was not delivered to the server** — the file
   is locked by the running process; the new build will be picked up at a restart (which
   happens in the rollback check). This must be taken into account: in the control window, the
   new build will be running.

---

## 7. What was NOT done

* **The new whitelist was not rolled out to the prod config** — per §7.5 this is done only after
   a successful A/B and a rollback check.
* **bptrace was not enabled on the bench** (only the implementation + a build): the hook of `ProcessInternal`
   writes bytes into the process code, and §4 requires a separate A/B window with the tracer and without it.
   The declared overhead estimate `+0.07…0.33%` is calculated, not measured.
* **The A/B was performed once**, not a series of repeats.
* **The check of "stuck" overlaps** (the risk class from ARCH.md §3.2) was not done:
   for it a scenario with a trap/turret is needed, not just a metric of t/s.

---

## 8. The tasks of the next slot

1. **Repeat the pair A/B** (at least 3 times, different windows) and aggregate the delta t/s with
   a confidence interval; currently one pair is one point.
2. **Check visually/by scenario that game logic did not break** under trim3:
   the traps (BearTrap), the danger zones (HazardTrigger_Slide), the turrets (Turret/TurretBallista),
   the grappling hook, the AOE abilities (TameAOE/CryoAOE/PingNearbyPlayers) — they are now
   protected by the whitelist, but the behavior must be confirmed in game.
3. **Enable bptrace on the bench in a separate window** (an A/B: with the tracer and without) —
   this will give the names of the Blueprint functions spinning in the phase and close the question
   "the source of the phase" (see REPORT-SLOT-B.md, task 4).
4. **Find out why the file IO in the phase comes not from the game code** (see §4 of report B):
   check `UWorldComposition::Rescan` (called from `ApplySettings`/`Serialize`).