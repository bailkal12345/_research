# Summary table of the doit2 watch (RE-2 + benchmark without a client)

Watch date: 2026-10-18. All slots started with a deploy from `c:/saves` via `deploy_map.py`.
Prod configuration on all maps: NetServerMaxTickRate at default, fixclamp 0,
fncache 1, iscache 1, cachename 1, nochart 1, overlaptrim 2, bAllowConcurrentTicks 0.
CPU is the GameThread thread. The ms/tick formula = (CPU, s/s) / (t/s).

## Slots

| Slot | Map | What was done | Result |
|---|---|---|---|
| B-1 | TheIsland | decay curve, 5 windows of 120 s | a fresh world is **5.1×** more expensive, worst number **21.97 ms/tick** |
| B-2 | Genesis | attribution of the five optimizations, 7 windows of 240 s | 3 of 5 measured, **drift ±1 ms/tick** |
| B-3 | Fjordur | census in the arm-A state + a 60 s profile | the dominant cluster is **garbage collection ~16%** |

## B-1 — Decay curve (TheIsland)

| Window | ms/tick | t/s | status |
|---|---|---|---|
| T0+2…4 | **21.97** | 9.07 | clean |
| T0+5…7 | **7.76** | 9.07 | clean |
| T0+8…10 | **5.35** | 8.76 | clean |
| T0+11…13 | (6.21) | 8.81 | **distorted — discarded** |
| after autosave | **4.31** | 9.07 | clean |

A freshly loaded world is **5.1×** more expensive than a settled one; half of the cost
decays within ~2.5 minutes. **The worst number for the ToR: 21.97 ms/tick** — starting
the server on a real save. For the 60 t/s target (≤16.6 ms/tick) a freshly started server
without players **does not fit**; only a settled one fits.

**This redefines the answer to question 1 of the first watch.** There, P0/P1 was taken
~2 minutes after startup — right in the zone of maximum decay. That means P0/P1
(Genesis 9.77 / TheIsland 10.17 / Fjordur 9.00 ms/tick) is a **transient regime**.
The settled values are lower: TheIsland 4.31, Genesis 7.04 ms/tick — **1.8–2.4×
cheaper** than the first watch showed.

## B-2 — Attribution of the five optimizations (Genesis)

| Optimization | off | on | contribution | status |
|---|---|---|---|---|
| reference (all 5) | — | **7.04** | — | — |
| `fncache` | 10.95 | 7.04 | **−3.91 ms (−35.7%)** | measured |
| `iscache` | 14.07 | 8.99 | **−5.08 ms (−36.1%)** | measured |
| `cachename` | 11.72 | 7.05 | **−4.67 ms (−39.8%)** | measured |
| `nochart` | — | — | — | **not completed** (slot ceiling) |
| `overlaptrim` | — | — | — | **not completed** (slot ceiling) |

**Drift: with an unchanged configuration, 7.04 / 8.99 / 7.05 ms/tick were measured — a
spread of ±1.0 ms (up to +28%).** This is comparable to the size of the contributions,
so the numbers are suitable only for estimating order of magnitude, not for planning
the ToR budget. Possible causes (both unverified): non-additivity of the caches
and overlap with drift.

Counters: `fncache` 45 336 557 / 4 678 (99.990%), `iscache` 957 894 518 / 1 857 (99.9998%).

**Diff of `.ark`:** 107 713 327 → 101 508 597 bytes (−5.8%), `sha256` recorded before and
after. The cause — `overlaptrim 2` disabled 13 783 components and freed 111 745
records. Fjordur.ark and TheIsland.ark did not change: the effect is local to the map.

## B-3 — Census and profile (Fjordur)

The census was taken in the **restored state** (after `overlapall 0`): the flag
`bGenerateOverlapEvents` on **206 780 of 206 780** components (100%), overlaps 325 896.
In the deploy state there were 4 594 of 206 502 (2.2%) and 326 946 overlaps.

**The total number of overlaps almost did not change (0.3%)** when the flag was
removed from 97.8% of the components. This is direct proof of the mechanism of the
`overlaptrim` gain: it removes not the number of overlaps but the cost of processing them.

## Profiles: three maps — three different profiles

| Dominant cluster | Genesis | TheIsland | Fjordur |
|---|---|---|---|
| 1st | BP interpreter **22.8%** | octree traversal **15.4%** | **garbage collection ~16%** |
| idle | 83.8% wall | 96.4% wall | 95.1% wall |
| executable code | 4 932 samples | 1 093 | 1 518 |

**There is no single hot spot for all maps.** Priorities diverge between maps:
the BP interpreter (Genesis), the octree traversal (TheIsland), GC (Fjordur).
None of the five active patches touches GC — this is an unoccupied niche.

## Answers to the three watch questions (updated)

| Question | Answer |
|---|---|
| 1. Cost of saving without players | Settled regime: **TheIsland 4.31, Genesis 7.04 ms/tick**; in the worst case (right after startup) **21.97 ms/tick**. The limit is pacing, not CPU: 9.99 t/s at 4–14% of a core |
| 2. O(n²) overlap | Yes, but the gain is determined by the **concentration** of overlaps, not their number: −59.0% / −9.1% / −39.0% at 199k / 528k / 327k overlaps |
| 3. SaveWorld freeze | 3.9–4.3 s = **×7.5–8.7** of the 500 ms threshold. Per RE (A4) it is **serialization into memory**, not a flush to disk: writing already happens on a TaskGraph worker (`FWriteFileTask::GetDesiredThread` `0x00D66650`) |

## What RE-2 newly established

| Thesis | Status |
|---|---|
| O(n²) in `ServerOctreeOverlapActors` | **REFUTED**. The real O(n²) is `BeginComponentOverlap` `0x02644000`, the call to `AddUniqueImpl` at `0x0264418D` |
| `iscache` covers `IsA` | **NO**. Zero intersection: in the body of `IsA` there are zero `CALL` instructions. The iscache contribution comes from `IsChildOf` |
| The `IsA` hook covers all sites | **NO**, 73%: 1360 calls + **510 inline copies** of the loop |
| The figure "−13% from iscache" | **not confirmed**: the old report held the combined effect of three caches at "−7%" |
| The SaveWorld freeze is a flush to disk | **NO**. The disk is asynchronous, the freeze is serialization |
| Incremental saving in ARK | **NO**. `SavePackage` is entirely absent, `-newsaveformat` changes the version, not the delta |
| A starter save before P0/P1 of the first watch | **THERE WAS NONE** on any map; the reviewer's premise is not confirmed |

## What this watch failed to deliver

1. **`nochart` and `overlaptrim` were not attributed on Genesis** — a ceiling of 60 min per slot.
2. **The combined effect of "all five off" was not measured**, so the non-additivity
   of the contributions was not verified quantitatively.
3. **The ±1 ms/tick drift was not investigated** — the cause not established.
4. **The cause of the decay was not established** — stasis / transients / GC remain a hypothesis.
5. **There are still no measurements with a player connected.**
6. **The ms/tick windows in B-3 were not taken** (the slot went to the census and profile).
7. The Fjordur profile was taken only in the restored state; to evaluate the contribution
   of `overlaptrim` a second one, in the deploy state, is needed.
8. The conditional tasks **B-4** (iscache2) and **B-5** (BP tracer) were not performed:
   sketches are ready (RE2.md, ARCH.md), but there is no plugin implementation.
9. Parking for the player (section 5) was not needed — no client connected.