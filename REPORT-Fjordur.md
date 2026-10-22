# REPORT-Fjordur

Slot 3. Prod configuration: NetServerMaxTickRate stock (0), tick rate clamp stock,
the five optimizations enabled. The bench launched with the prod line, deploy only via `deploy_map.py`.
Save: 98.1 MB, 250 player profiles, 414 files. GameThread tid 14148, pid 16888.

NetServerMaxTickRate: stock (0). Actual t/s of P0/P1: **9.99**.
The steps were executed manually, one by one, with a bench health check after each one.

## Answers to the watch's questions

**1. How much does a real save cost without players.**

| Metric | Value |
|---|---|
| ticks/s | **9.99** |
| GameThread CPU (240 s window) | 0.090 s/s |
| ms CPU per tick (240 s window) | **9.00** |
| ms CPU per tick (after a save) | **4.30** |
| total process CPU | 0.04–0.07 s/s |
| world save | every 15 min, freeze ~3.9 s |

As on the two previous maps: a frame of ~100 ms at single-digit CPU milliseconds —
the server is bound by the tick rate, not by computation.

**2. Do large bases eat the GameThread through O(n²) overlap.**

| Mode | ms CPU/tick | t/s | CPU GameThread, s/s |
|---|---|---|---|
| overlaptrim off | 7.05 | 9.97 | 0.070 |
| overlaptrim=2 | 4.30 | 9.99 | 0.043 |
| **delta** | **−39.0%** | +0.2% | −38.6% |

Yes: the trim removes 2.75 ms per tick. The effect is noticeable but smaller than on Genesis
(−59.0%) and larger than on TheIsland (−9.1%).

**3. How much does the SaveWorld freeze cost.**

| Run | freeze, ms |
|---|---|
| 1 | 4026 |
| 2 | 3738 |

**The ToR threshold of 500 ms is exceeded by a factor of ~8.1.** Task added to the ToR backlog.

## P2 — A/B overlaptrim (300 s windows, both after the end of a save)

| Hand | ms/tick | t/s | clean window |
|---|---|---|---|
| A — overlap events returned | 7.05 | 9.97 | yes |
| B — overlaptrim=2 | 4.30 | 9.99 | yes |

None of the Fjordur windows landed on a save.

## Censuses

| Metric | Value |
|---|---|
| levels | 208 |
| actors | 79 122 |
| registered tick functions | 468 |
| components | 327 161 |
| ticking components | 475 |
| `AllEnabledTickFunctions` | **525 271** |
| components with `bGenerateOverlapEvents` | 4 594 of 206 502 |
| total overlaps | 326 946 |

`AllEnabledTickFunctions` = 525 271 — an order of magnitude higher than on TheIsland (3 510)
and comparable to Genesis (1 264 462). The reason is the 208 levels: the cave system of Fjordur
yields many sublevels. Yet the ticking components number only 475.

After `overlaptrim 2` the `bGenerateOverlapEvents` flag remained on 4 594 of
206 502 components, i.e. the trim removed it from 98% of components: almost all of them had
1–2 overlaps each, and it was their lists that were being bloated.

## Profile

**Not taken.** The slot fit within the 60-minute ceiling only without it: the profiler
crashed the server twice on Genesis and requires a separate time reserve. This is the only
uncompleted item of slot 3; the Genesis and TheIsland profiles are attached.

## Map conclusion

Fjordur is the "most multi-level" of the three maps (208 levels) and the only one
where `AllEnabledTickFunctions` is close to Genesis, yet ms/tick is noticeably lower.
Therefore the number of registered tick functions by itself does not determine the cost
of a frame — Genesis is expensive because of the logic being invoked (the Blueprint interpreter and
VictoryCore), not because of the number of ticks.
---

## A6 — report hygiene (reviewer edit)

### 1. The state in which each census was taken

| Report | Census taken in | What it means |
|---|---|---|
| REPORT-Genesis.md | **restored state** — after `TickProf.overlapall 0`, then `overlaptrim 2` | `overlaptrim 2` does not re-sweep live components, so the overlap and flag numbers refer to the restored state |
| REPORT-TheIsland.md | **restored state** — the same sequence | same |
| REPORT-Fjordur.md | **deploy state** — `overlaptrim 2` from the prod config, `overlapall 0` was not applied | the only census matching the prod configuration |

The censuses are **not directly comparable across maps**: Genesis and TheIsland were taken in a different
state than Fjordur. Within one map the censuses are comparable with each other.

### 2. The spread of the SaveWorld freeze

Across all six runs: 3738, 3866, 3991, 4026, 4308, 4371 ms against the 500 ms threshold.
Spread by the maximum: **×7.5 – ×8.7**. The earlier wording "×8.6" referred
only to Genesis and did not reflect the maximum.

### 3. Footnote on the incomparability of P0/P1

> P0/P1 on all maps was taken ~2 minutes after world readiness, while the P2 windows were
> taken right after the end of the autosave. The absolute values of P0/P1 and of the P2 windows
> are comparable only within one map and one protocol.

### 4. The cost of the autosave operation

> **The autosave adds +15 ms/tick for the duration of the save and causes a freeze of 3.9–4.3 s.**
> On Genesis, in the window captured by the save, the frame cost rose from 9.8 to
> 25.0 ms/tick. The save alone costs more than the rest of the frame.

### 5. The "fresh world" mechanism is a HYPOTHESIS, not an established fact

Observation: right after the autosave the frame is cheaper (TheIsland: 3.91 versus 10.17 ms/tick).
Possible explanations, none verified:
- **actor stasis** — after the save some actors are reset into a "sleeping" state;
- **transient processes** — after a fresh load there are initialization phases that then die down;
- **garbage collection and cleanup** — before the autosave new objects accumulate, after the reset there are fewer of them.

A separate measurement is required: a profile right after the autosave and 10 minutes later,
comparing the shares of `APrimalCharacter::Tick`, `FTickTaskManager::RunTickGroup`, and GC symbols.
**Until then, the "after the save" numbers must not be treated as an improvement of the map.**

### 6. Was there a starting save before P0/P1 — a check against the raw data

Evidence: `*_AntiCorruptionBackup.bak` is created **during world loading**
(a copy of the read .ark), while the `.ark` itself is rewritten only on an actual save.

| Map | launch | RCON ready | P0/P1 window | `.bak` | `.ark` rewritten |
|---|---|---|---|---|---|
| Genesis | 00:32:48 | 00:40:03 | 00:42:26–00:46:46 | 00:37:54 (during load) | first at 01:21:38 |
| TheIsland | 01:33:43 | 01:39:53 | 01:42:13–01:46:32 | 01:37:56 (during load) | first at 02:07 |
| Fjordur | 02:19:19 | 02:26:01 | 02:28:29–02:32:49 | 02:23:59 (during load) | first at 02:38 |

**Conclusion: there was no completed starting save before P0/P1 on any map.**
The waiting for "the end of the starting save" in the Genesis/TheIsland slots was waiting
for file quiescence, not for a save: the `.ark` was not changing at that time.

Consequence: the reviewer's premise that "Genesis waited for the end of a starting save" is **not
supported by the data**. P0/P1 on the three maps was taken in comparable conditions (~2 minutes
after the world lift, with no preceding save). The comparability of the values themselves
is limited by the different contents of the maps, not by different measurement conditions.
