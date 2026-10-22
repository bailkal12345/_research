# REPORT-C — dissecting the t/s clamp and reaching 60 t/s

Watch doit2, stage C (research and changes before the player test).
Map Genesis, deploy from `c:/saves` via `deploy_map.py`, prod launch line.

## 1. Main result: 60 t/s is a question of CONFIGURATION, not code

### Dissection in Ghidra (UGameEngine::GetMaxTickRate, RVA `0x0253B1C0`)

```asm
14253b25f  MOV  EDX,dword ptr [RAX+0x48]   ; NetDriver->NetServerMaxTickRate (int32, @+0x48=72)
14253b262  CMP  EDX,0xa                      ; < 10 ?
14253b265  JGE  14253b26e
14253b267  MOV  ECX,0xa                      ; yes -> 10   (FLOOR)
14253b26c  JMP  14253b278
14253b26e  MOV  ECX,0x78                     ; no  -> 120 (CEILING)
14253b273  CMP  EDX,ECX
14253b275  CMOVL ECX,EDX                     ; min(rate,120)
14253b278  MOVD XMM6,ECX
14253b27c  CVTDQ2PS XMM6,XMM6
14253b2ae  CALL UEngine::GetMaxTickRate
14253b2c3  UCOMISS XMM0,XMM7                 ; XMM7 = 0
14253b2d0  JNZ  14253b2d5
14253b2d2  MOVAPS XMM0,XMM6                  ; UEngine == 0 -> return the clamp
```

With `NetServerMaxTickRate = 0` (stock) the **floor** triggers: `0 < 10` → the result
is exactly 10 t/s. Measured 9.99 t/s, frame 100.1 ms = 1/10. Agreement to 0.1%.

**Consequence:** `TickProf.fixclamp` (patch `0x78 → 0x186A0` at RVA `0x253B26F`)
raises only the **ceiling** of 120. It is needed for values above 120 t/s and is **redundant
for the 60 t/s target**.

### Empirical check (the decisive test)

`TickProf.maxfps 60` with the **stock** clamp (`fixclamp 0`), Genesis, no player:

| Metric | Value |
|---|---|
| t/s (instantaneous, settled regime) | **59–60** |
| t/s (average over 1000 s) | **54** |
| frame | **16–18 ms** |
| **ms CPU per tick** | **5–9** |
| core occupancy | **31–50%** |
| code patches | **zero** |

**The 60 t/s target was achieved with a single configuration change.** The ToR budget — ≤16.6 ms/tick —
is met with headroom: 9 ms against 16.6.

## 2. Correction to the previous watch's wording

Both watches wrote "the limit is pacing". More precisely: **the frame is set by the target tick rate,
not by the amount of work**. In the settled regime the GameThread is busy on 4–14% of a core, and the frame
is still 100 ms. That is the clamp.

Additionally clarified: while the world is not fully loaded (the first ~10 minutes)
the work exceeds the budget — the GameThread is busy on 98–100%, and t/s drops to 7–9 regardless
of the target rate. I.e. the clamp is visible only in the settled regime.

## 3. What was changed in the plugin

Built, deployed and verified on the bench. All new commands **read or control the state
of the meter**; not one changes server behavior:

| Command | Purpose | Verified |
|---|---|---|
| `TickProf.mon <sec>` | monitor once per second: t/s, ms/tick, frame, occupancy, save state | yes |
| `TickProf.window <sec>` | measurement window **with a self-validity check** | yes |
| `TickProf.arkstate` | `.ark` state for the rollback protocol (item 1.1) | yes |
| `TickProf.perf.selftest` | automated run of the slot protocol without manual steps | built, detailed run not executed |

### Auto-flagging of contamination — the key change

The window flags itself:

```
16:57:01  window: t/s=54 cpu=506s ms/tick=9 frame_ms=18 busy=50% save=idle CONTAMINATED
16:57:01  window: contaminated by world save, 179 of 54822 frames
```

179 of 54 822 frames (0.33%) landed on a save. Now a spoiled window cannot be accepted by oversight —
earlier this was done manually, and in the first watch three windows were spoiled exactly that way.

### Save detector

```
16:35:00.491  save: start of .ark write (7 files)
16:35:03.491  save: .ark write finished, duration 3000 ms, total saves 1
16:50:00.448  save: start of .ark write (7 files)
16:50:03.449  save: .ark write finished, duration 3000 ms, total saves 2
```

Both autosaves were caught. The 3000 ms duration agrees with the independent measurement of the SaveWorld
freeze (3.9–4.3 s by RCON unavailability): the file write goes asynchronously
on a TaskGraph worker (see RE2.md, A4), so `.ark` is finalized at the end.

## 4. Measurement defects found and fixed

| Defect | Symptom | Fix |
|---|---|---|
| `GetThreadTimes` without a baseline reading | `cpu=570s` at `wall=240s`, `busy=237%` — physically impossible | subtract the window baseline |
| `ms/tick = cpu/tps` instead of `cpu_total/frames` | overstatement by `wall_s` times (over 240 s — by 240 times) | formula `cpu_total / frames` |
| `PollArk` always returned `changed=false` | the save was never detected | comparison of `.ark` snapshots |
| the detector's first trigger was silent | loss of the first autosave | "start → end" logic |
| the `*.ark` filter caught `.arkprofile` and `.arktributetribe` | false "saves" | excluded by extension |
| the monitor and detector were placed after the early exit of `OnTickPerf` | they did not work without an active window | moved to `OnTickFrame` |
| the `{:.2f}` format was not supported by `S()` | `t/s=A`, clipped values | replaced with `{}` |

**Important:** the first watch's numbers taken from the plugin's `perf window` line
(`busy=237%`, `cpu=570s`) were wrong. All decisions in the first- and second-watch reports
were made on the **external** measurement (Python, `threadcpu.py`), which computed
the delta correctly. Therefore the conclusions of both watches stand, but the
`busy` column in the plugin log must not be cited.

## 5. What remains out of scope

| Item | Status |
|---|---|
| Reaching 60 t/s | **closed**: 9 ms/tick at the target 60 |
| `bptrace` — Blueprint tracer | **not implemented.** The hook point and design exist (RE2.md A5, ARCH.md 3.5); no code |
| `perf.selftest` — detailed run | command built, scenario not exercised on the bench |
| Attribution of `nochart` and `overlaptrim` | not closed (the ceiling of slot B-2) |
| Test with a player | not conducted — no client connected |

## 6. Recommendation for the session with a player

Target configuration: `NetServerMaxTickRate = 60`, `fixclamp 0` (the patch is not needed),
the five optimizations on. The starting baseline — **9 ms/tick** on an empty server at
the target 60 t/s, i.e. **headroom ≈ 7.6 ms/tick** for the player.

The historical figure with a player — 24.4 ms/tick — **does not fit this budget**.
So the optimizations are still needed: about 8 ms/tick must be cut.
Candidates in descending order of expected payoff: the Blueprint interpreter (22.8%
on Genesis), the genuine O(n²) in `BeginComponentOverlap`, GC (~16% on Fjordur).
