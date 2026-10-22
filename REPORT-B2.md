# REPORT-B2 — attribution of the five optimizations (Genesis)

Slot B-2 of directive doit2.txt. Map Genesis, deploy from `c:/saves` via `deploy_map.py`.
T0 = 12:29:36 (RCON responsive). GameThread tid 6588, pid 2612.
Prod configuration before the first window: NetServerMaxTickRate stock, fixclamp 0, fncache 1,
iscache 1, cachename 1, nochart 1, overlaptrim 2, bAllowConcurrentTicks 0 (verified).

Formula: ms CPU/tick = (GameThread CPU, s/s) / (t/s).
Window protocol: wait for the end of the autosave → a 240 s window → check the "contaminated" flag.
**All windows are clean.** None landed on a save.

## Result

| Optimization | off, ms/tick | on, ms/tick | contribution | t/s |
|---|---|---|---|---|
| **baseline (all 5 on)** | — | **7.04** | — | 9.98 |
| `fncache` | 10.95 | 7.04 | **−3.91 ms (−35.7%)** | 9.99 |
| `iscache` | 14.07 | 8.99 | **−5.08 ms (−36.1%)** | 9.99 |
| `cachename` | 11.72 | 7.05 | **−4.67 ms (−39.8%)** | 10.00 |
| `nochart` | **not completed** | — | — | — |
| `overlaptrim` | **not completed** | — | — | — |

Order of measurement: baseline → fncache(0/1) → iscache(0/1) → cachename(0/1).
`nochart` and `overlaptrim` were not finished: the 60-minute ceiling of the slot expired at 13:29,
and the last window closed at 13:32. Both tasks are marked "not completed" and not replaced by
estimates — see the section "What this slot did not deliver".

## Main caveat: drift between windows

With an **unchanged** configuration (all 5 on) measured three times:

| moment | ms/tick |
|---|---|
| 12:42–12:47 (baseline) | 7.04 |
| 13:12–13:17 (after returning iscache) | 8.99 |
| 13:27–13:32 (after returning cachename) | 7.05 |

The spread is **7.04 … 8.99 ms/tick, i.e. ±1.0 ms (up to +28%)** in the same state.
This is comparable to the size of the contributions themselves. Therefore:

* the contributions are computed **over adjacent pairs** (off → on back-to-back, within one save cycle) —
  they are the most reliable;
* **the sum of the contributions does not add up to a reliable value.** The sum of the three measured:
  3.91 + 5.08 + 4.67 = **13.66 ms/tick**, whereas the difference between the "baseline" (7.04)
  and "everything off" was never measured, and the profile is known to show that the three caches
  together gave about −7% in the earlier run. This is a direct contradiction.

**Conclusion on the causes of the contradiction (two possibilities, neither verified):**
1. The contributions are non-additive: the caches work on intersecting paths (`FindFunctionByName`
   and `IsChildOf` both serve Blueprint calls), so leave-one-out
   overstates the individual contributions.
2. Drift of +1 ms/tick between windows smears the difference; part of the measured "gain"
   may be drift in reverse, not an effect.

Until a re-run with alternating order (on/off/on/off within one save cycle),
these numbers **must not be used for ToR budget planning**.

## Cache counters (13:32, after all the toggles)

| Cache | hits | misses | hit ratio |
|---|---|---|---|
| `fncache` | 45 336 557 | 4 678 | 99.990% |
| `iscache` | 957 894 518 | 1 857 | 99.9998% |

Per A1 this is expected and important: `iscache` caches `UStruct::IsChildOf`, which has
3411 call sites + 394 inline copies, whereas `IsA` (matching a profile share of 5.8%) is
**1870 sites, and not one of them is covered by `iscache`**.
That is, the iscache contribution comes from `IsChildOf`, not from `IsA`.

## Diff of .ark (item 1.1 of the rollback protocol)

| moment | Genesis.ark | sha256 (first 24) |
|---|---|---|
| B-2 start (12:30) | 107 713 327 | `5a26823265e4c77e219f7491` |
| B-2 end (13:32) | **101 508 597** | `15699c5ed86df02c7d04bfcd` |

**−6 204 730 bytes (−5.8%).** The cause is established: `overlaptrim 2` at start
disabled `bGenerateOverlapEvents` on **13 783 components** and freed
**111 745 overlap records**; the autosave then wrote the trimmed state.
The file remains valid — the server works on it normally. Fjordur.ark and
TheIsland.ark did not change (hashes match before and after), i.e. the side effect
is local to the map, not global.

## Reconciliation with the first watch

The baseline window of 7.04 ms/tick versus P0/P1 of the first watch, 9.77 ms/tick on the same map.
The difference is explained by the regime: P0/P1 was taken 2 minutes after lift-off, i.e.
in the decay zone (see REPORT-B1). **The settled state of Genesis = 7.04 ms/tick.**
That is 1.8× cheaper than previously reported.

## What this slot did not deliver

1. **`nochart` — not attributed.** Expected to be small (it disables FPS chart keeping),
   but it was not measured.
2. **`overlaptrim` — not attributed on Genesis.** In the first watch it measured −59.0%
   (21.97 → 9.00 ms/tick), but those windows ran in a different regime (P0/P1 of the first watch —
   transient) and by a different protocol. In this slot the pair for it was not run.
3. **The combined effect of "all five off" was not measured**, so the additivity of the
   contributions was not verified quantitatively.
4. **The drift was not investigated.** The cause of the ±1 ms/tick (time since world start, accumulation
   of state, periodicity of the autosave) is not established.
5. **One run on one map.** All numbers are Genesis, no player.

## What is closed

Attribution of three out of five optimizations on a real archived save, with byte-level
capture of `.ark` before and after, and with hit/miss counter verification.
