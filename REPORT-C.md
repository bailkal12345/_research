# REPORT-C - dissecting the t/s clamp and reaching 60 t/s

Watch doit2, stage C: research and changes before the player test. Map Genesis, deploy from
`c:/saves` via `deploy_map.py`, prod launch line.

## 1. Main result: 60 t/s is a question of CONFIGURATION, not code

### Ghidra dissection (UGameEngine::GetMaxTickRate, RVA `0x0253B1C0`)

```asm
14253b25f  MOV  EDX,dword ptr [RAX+0x48]   ; NetDriver->NetServerMaxTickRate (int32, @+0x48=72)
14253b267  MOV  ECX,0xa                    ; < 10 ? yes -> 10 (FLOOR)        (JGE skips from 14253b262)
14253b26e  MOV  ECX,0x78                   ; no -> min(rate,120) (CEILING)   CMP EDX,ECX / CMOVL ECX,EDX
14253b27c  CVTDQ2PS XMM6,XMM6              ; from MOVD XMM6,ECX
14253b2ae  CALL UEngine::GetMaxTickRate
14253b2d2  MOVAPS XMM0,XMM6                ; UEngine == 0 (UCOMISS XMM0,XMM7) -> return the clamp
```

With `NetServerMaxTickRate = 0` (stock) the floor triggers: `0 < 10` -> exactly 10 t/s. Measured
9.99 t/s, frame 100.1 ms = 1/10 - agreement to 0.1%. `TickProf.fixclamp` (patch `0x78 -> 0x186A0` at
RVA `0x253B26F`) raises only the ceiling of 120: needed for >120 t/s, redundant for the 60 t/s target.

### The decisive test

`TickProf.maxfps 60` with the **stock** clamp (`fixclamp 0`), Genesis, no player:

| Metric | Value |
|---|---|
| t/s (instantaneous, settled regime) | **59-60** |
| t/s (average over 1000 s) | **54** |
| frame | **16-18 ms** |
| **ms CPU per tick** | **5-9** |
| core occupancy | **31-50%** |
| code patches | **zero** |

**60 t/s achieved with a single configuration change.** The ToR budget - <=16.6 ms/tick - is met with
headroom: 9 ms against 16.6.

## 2. Correction to the previous watches' wording

More precise than "the limit is pacing": **the frame is set by the target tick rate, not by the amount
of work** - in the settled regime the GameThread is busy 4-14% of a core while the frame is still
100 ms. While the world is not fully loaded (the first ~10 minutes) the work exceeds the budget: the
GameThread is busy 98-100% and t/s drops to 7-9 regardless of the target rate; the clamp is visible
only in the settled regime.

## 3. Plugin changes (metering only - none changes server behavior)

Built, deployed, bench-verified: `TickProf.mon <sec>` (1 Hz monitor: t/s, ms/tick, frame, occupancy,
save state - verified); `TickProf.window <sec>` (measurement window **with a self-validity check** -
verified); `TickProf.arkstate` (the `.ark` state for the rollback protocol, item 1.1 - verified);
`TickProf.perf.selftest` (automated slot protocol - built, detailed run not executed).

The window flags itself:

```
16:57:01  window: t/s=54 cpu=506s ms/tick=9 frame_ms=18 busy=50% save=idle CONTAMINATED
16:57:01  window: contaminated by world save, 179 of 54822 frames
```

179 of 54 822 frames (0.33%) landed on a save - a spoiled window can no longer be accepted by oversight
(three were spoiled that way in the first watch).

The save detector caught both autosaves:

```
16:35:00.491  save: start of .ark write (7 files)
16:35:03.491  save: .ark write finished, duration 3000 ms, total saves 1
16:50:00.448  save: start of .ark write (7 files)
16:50:03.449  save: .ark write finished, duration 3000 ms, total saves 2
```

The 3000 ms duration agrees with the SaveWorld freeze measured independently (3.9-4.3 s by RCON
unavailability): the write goes to a TaskGraph worker (RE2.md, A4), so `.ark` is finalized at the end.

## 4. Measurement defects found and fixed

| Defect | Symptom | Fix |
|---|---|---|
| `GetThreadTimes` without a baseline reading | `cpu=570s` at `wall=240s`, `busy=237%` - physically impossible | subtract the window baseline |
| `ms/tick = cpu/tps` instead of `cpu_total/frames` | overstatement by `wall_s` times (over 240 s - by 240 times) | formula `cpu_total / frames` |
| `PollArk` always returned `changed=false` | the save was never detected | comparison of `.ark` snapshots |
| the detector's first trigger was silent | loss of the first autosave | "start -> end" logic |
| the `*.ark` filter caught `.arkprofile` and `.arktributetribe` | false "saves" | excluded by extension |
| the monitor and detector were placed after the early exit of `OnTickPerf` | they did not work without an active window | moved to `OnTickFrame` |
| the `{:.2f}` format was not supported by `S()` | `t/s=A`, clipped values | replaced with `{}` |

**Important:** the first watch's numbers from the plugin `perf window` line (`busy=237%`, `cpu=570s`)
were wrong. All decisions in both watch reports came from the **external** measurement (Python,
`threadcpu.py`) - the conclusions stand, but the `busy` column in the plugin log must not be cited.

## 5. Out of scope

Reaching 60 t/s - **closed** (9 ms/tick at the target 60). `bptrace` - **not implemented** (hook point
and design exist: RE2.md A5, ARCH.md 3.5; no code). `perf.selftest` - command built, detailed run not
exercised. Attribution of `nochart` and `overlaptrim` - not closed (the ceiling of slot B-2). Test with
a player - not conducted (no client connected).

## 6. Recommendation for the session with a player

Configuration: `NetServerMaxTickRate = 60`, `fixclamp 0` (the patch is not needed), the five
optimizations on. Baseline **9 ms/tick** on an empty server at 60 t/s - headroom ~7.6 ms/tick. The
historical figure with a player - 24.4 ms/tick - **does not fit the budget**: ~8 ms/tick must be cut,
in descending payoff order: the Blueprint interpreter (22.8% on Genesis), the genuine O(n^2) in
`BeginComponentOverlap`, GC (~16% on Fjordur).
