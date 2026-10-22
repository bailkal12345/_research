# REPORT-B1 — decay curve (TheIsland)

Slot B-1 of directive doit2.txt. Map TheIsland, save 134.2 MB, 250 profiles.
Deploy from `c:/saves` via `deploy_map.py`, prod launch line.
T0 = 12:03:45 (RCON responsive). GameThread tid 5436, pid 2320.
Prod configuration before T0: NetServerMaxTickRate stock, fixclamp 0, fncache 1,
iscache 1, cachename 1, nochart 1, overlaptrim 2, bAllowConcurrentTicks 0.

## Result

| Window | moment | ms CPU/tick | t/s | CPU GameThread, s/s | status |
|---|---|---|---|---|---|
| 1 | T0+2…4 | **21.97** | 9.07 | 0.199 | clean |
| 2 | T0+5…7 | **7.76** | 9.07 | 0.070 | clean |
| 3 | T0+8…10 | **5.35** | 8.76 | 0.047 | clean |
| 4 | T0+11…13 | (6.21) | 8.81 | 0.055 | **contaminated — discarded** |
| 5 | after autosave | **4.31** | 9.07 | 0.039 | clean |

Formula: ms CPU/tick = (thread CPU, s/s) / (t/s), i.e. 0.199 / 9.07 × 1000 = 21.97.

## Answers to the B-1 questions

**Is the freshly loaded world more expensive.** Yes, by **5.1×**: 21.97 ms/tick two minutes
after lift-off versus 4.31 ms/tick in the settled state. That is 4.5× more than
P0/P1 of the first watch on this same map (10.17 ms/tick) — meaning the first window of that
watch also fell into the not-yet-settled regime.

**How it decays.** Quickly and exponentially: 21.97 → 7.76 → 5.35 ms/tick.
The main drop is between the second and fifth minute; by T0+8…10 the curve reaches a plateau.

| Interval | Drop |
|---|---|
| T0+2…4 → T0+5…7 | −64.7% |
| T0+5…7 → T0+8…10 | −31.1% |
| T0+8…10 → settled | −19.4% |

Half of the cost decays in roughly 2.5 minutes after lift-off.

**Which number to count as the worst case for the ToR.** **21.97 ms/tick** — the window T0+2…4.
This is the worst realistic scenario without players: a server start on a real save.
For the ToR target of 60 t/s (≤16.6 ms/tick) this means: **a freshly lifted server without players
already exceeds the budget; only the settled state fits within it**.

## What this closes

The P0/P1 anomaly of the first watch is explained. In the TheIsland slot of the previous watch
P0/P1 was taken at 01:42–01:46, i.e. ~2 minutes after world readiness — **exactly in the zone
of maximal decay**. Therefore P0/P1 = 10.17 ms/tick reflects not the "cost of the map"
but a transient regime.

**Consequence for the reporting of the previous watch:** the P0/P1 numbers (Genesis 9.77,
TheIsland 10.17, Fjordur 9.00) are the cost of the map in the transient regime.
Settled values are lower: TheIsland 4.31 ms/tick. So a map in the settled regime
is **1.8–2.4× cheaper** than P0/P1 showed, and the question "how much does a real
save without players cost" in the settled regime has the answer **4.31 ms/tick**, not 10.17.

Cross-check by file dates (A6, item 6): a completed starting save before P0/P1
happened on none of the maps, so the decay is explained **not** by a save but by the
world's own warm-up after loading.

## Caveats

1. The window T0+11…13 was discarded: it landed on the autosave. The curve is built from three clean
   windows before the first autosave and one clean window after.
2. The decay mechanism is not established — candidates: actor stasis, transient
   initialization processes, accumulation and collection of garbage. This is a **hypothesis** (see A6, item 5).
3. One map, one run. For the ToR we need the same windows on Genesis and Fjordur.
4. t/s in window 3 sagged to 8.76 — probably the start of the autosave was already affecting the padding,
   even though the files had not changed yet. The cleanliness of this window should be treated as conditional.
