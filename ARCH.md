# ARCH.md — target architecture of the TickProf v2 plugin

This document describes the target state of the plugin: five active optimizations,
new patches based on the RE-2 results, rollback requirements, configuration,
built-in monitoring, and the automated run command for the watch-duty protocol.

Image: `ShooterGameServer.exe` v361.7, Win64 x64, image base `0x140000000`.
All RVAs come from `v361.sqlite` and were confirmed by Ghidra disassembly.

## 1. Principles

1. **Every feature = an enable command + a rollback command.** No optimization is
   applied at plugin startup without an explicit command.
2. **Byte patches are installed and removed in pairs.** Rollback must restore the
   original bytes byte-for-byte, not "restart just in case".
3. **Server behavior does not change without A/B.** Every new feature must have a
   measured gain on a real save from the archive.
4. **A whitelist is mandatory** for any patch that affects gameplay events.
5. **Monitoring is built into the plugin.** Decisions are made based on the
   plugin's numbers, not on external samplers.
6. **Asynchronous ticking is forbidden.** We never touch
   `bAllowConcurrentTicks`: confirmed regression 33.4 → 42–46 ms/tick.

## 2. Active optimizations (v1)

| # | Feature | Command | Rollback | What it does |
|---|---|---|---|---|
| 1 | `fncache` | `TickProf.fncache 1` | `TickProf.fncache 0` | cache of `UClass::FindFunctionByName` |
| 2 | `iscache` | `TickProf.iscache 1` | `TickProf.iscache 0` | cache of `UStruct::IsChildOf` |
| 3 | `cachename` | `TickProf.cachename 1` | `TickProf.cachename 0` | cache of `DoGetCanvasByName` |
| 4 | `nochart` | `TickProf.nochart 1` | `TickProf.nochart 0` | disables `UEngine::TickFPSChart` |
| 5 | `overlaptrim` | `TickProf.overlaptrim <N>` | `TickProf.overlapall 0` + restart | removes `bGenerateOverlapEvents` from components with ≥N intersections |

Utility commands of v1: `fixclamp`, `maxfps`, `ticklist`, `ticksets`, `overlapsizes`,
`cachestat`, `tickq`, `tickqreport`, `tickflags`, `verify`, `perf`, `start`.

### Known v1 limitation

`overlaptrim` **is not reversible without a restart**: `TickProf.overlapall 0` restores
the `bGenerateOverlapEvents` flag, but does not restore the trimmed overlap lists
(components must repopulate them). Hence the "restored" state in the
censuses of the first watch.

## 3. New patches based on the RE-2 results

### 3.1 `overlaptrim3` — trimming with a whitelist (medium risk)

* Already built offline, not deployed.
* Command `TickProf.overlaptrim3 <threshold>`, whitelist from
  `tickprof_overlap_keep.txt` (substrings of the full class name, one per line).
* **Whitelist rework required by A2.** The current file contains
  `ShapeComponent`, `SphereComponent`, `BoxComponent`, `CapsuleComponent`,
  `Trigger`, `Turret`, `GrapplingHook`. Per the A2 results this is insufficient,
  and some of it is excessive:
  * add `ABaseBoxTrigger`, `AHazardTrigger_Slide`, `APrimalStructureBearTrap`,
    `APrimalStructureTurret`, `APrimalStructureTurretBallista`,
    `APrimalProjectileGrapplingHook`, `APrimalDinoCharacter`;
  * `Trigger` and `Turret` as substrings are too broad — replace them with full class names.
* RVAs of anchor points: `BeginComponentOverlap` `0x02644000`, `EndComponentOverlap`
  `0x026442D0`, `UpdateOverlaps` `0x02644CA0`.

### 3.2 `overlapcache` — eliminating the quadratic behavior (medium risk)

Per A2 the real O(n²) is not in the octree but in `UPrimitiveComponent::BeginComponentOverlap`
(`0x02644000`): for every new overlap there is a linear scan of `OverlappingComponents`
with a stride of `0x98` (the call to `AddUniqueImpl` `0x024E3050` at address `0x0264418D`).

* Patch point: `0x0264418D` — replace the linear scan with a `TSet` side structure keyed
  by `(CachedCompPtr, Item)` — exactly the two fields `AddUniqueImpl` compares by.
* Mandatory condition: a synchronous change to `EndComponentOverlap` (`0x026442D0`),
  otherwise the correspondence of the two overlap lists falls apart.
* Rollback: restoring the original call rel32 + removing the side structure.
* **Risk class MEDIUM (up to HIGH on a sync error).** Field failure symptom:
  "stuck" overlaps — the trap does not release the victim, the turret shoots at ghosts.
  The whitelist of 3.1 is mandatory.

### 3.3 `turrettick` — removing per-tick octree re-evaluation by the turret (medium risk)

Per A2: `APrimalStructureTurret::Tick` (`0x00A3A129`) calls
`APrimalStructureTurret::GetAmmoNearby` (`0x00A2A950`) **every tick, with no timer**,
and the latter calls `UVictoryCore::ServerOctreeOverlapActors` (`0x012871E0`) with
`OctreeType=0xF`. The function is already linear, but is called on every tick of every turret.

* Option: cache the result per tick keyed by `(component SerialNumber, quantized
  position and radius, OctreeType, bForce)`. Quantization is mandatory — otherwise a
  1 cm shift invalidates the cache.
* Store not a `TArray` (the pointer to a local sret lives one frame), but a
  `std::unordered_set<AActor*>` and rebuild the array on a cache hit.
* **Risk class MEDIUM.** An expired re-evaluation = a miss on the target by one
  tick (≈110 ms at 9 t/s). The `APrimalCharacter::TakeDamage` path (`0x009454FE`) and
  Blueprint exec paths **must not be touched** — caching there is unacceptable (risk HIGH).

### 3.4 `iscache2` — cache of `UObjectBaseUtility::IsA` (waiting on A1)

* A separate structure from `iscache` (the latter caches `UStruct::IsChildOf`).
* Main risks: caching a negative result when interfaces are added dynamically,
  invalidation on `UClass` creation/destruction and on package load.

### 3.5 `bptrace` — Blueprint tracer (medium risk)

Per A5: a hook of the body of `UObject::ProcessInternal` (`0x01FC0270`). For any script
`UFunction` the field `Func == &ProcessInternal`, so the hook covers both call paths.

* Log only the full name of the `UFunction` and the call counter. Arguments are not
  written, behavior is not changed.
* By default **disabled, no patch bytes are installed at all** — that is literally zero
  impact (no modified code), not a "zero branch".
* The record index is `__declspec(thread)`, a per-thread buffer, no locks.
  The cold (miss) path is `SRWLOCK`.
* **Mandatory pre-rollout check:** `ENDBR64` is absent in the first instructions
  of `ProcessInternal`; with CET enabled a CET-compatible
  trampoline `mov r11, imm64; jmp r11` is needed (12 bytes, does not touch the stack).
* The overhead estimate `+0.07…0.33%` of a frame is **calculated, not measured**;
  it is confirmed by an A/B window with and without the tracer.

### 3.6 Asynchronous/portioned save (waiting on A4)

The direction of the ToR task "SaveWorld freeze 3.9–4.3 s". A separate document on
integrity: a byte-for-byte rollback is unacceptable, the save must remain valid.

## 4. Configuration

| File | Purpose |
|---|---|
| `tickprof_overlap_keep.txt` | whitelist of classes for `overlaptrim3` / `overlapcache` / `turrettick`, one full class name per line, `#` is a comment |
| `tickprof_noclamp.txt` | if it exists — the plugin does not lift the tick-rate clamp at load |
| `TickProf.log` | log: every command, its result, counters |

Config priority: an RCON command overrides the file. The current state of each
feature is published by the `TickProf.status` command, one line per feature.

## 5. Monitoring inside the plugin

The command `TickProf.mon` prints once per second:

```
t/s=9.99 cpu_tick=9.77ms frame_cpu=98.0ms busy=10% save=idle overlaps=199380 fn=1264462
```

| Field | Source |
|---|---|
| `t/s` | frames counter / window |
| `cpu_tick` | CPU of GameThread / t/s — **the primary ToR metric** |
| `frame_cpu` | frame duration |
| `busy` | GameThread busy fraction |
| `save` | `idle` / `saving` / `saved` — autosave state |
| `overlaps` | total number of overlaps |
| `fn` | `AllEnabledTickFunctions` |

**Measurement window rule (item 1.2 of the directive).** The ms/tick window is published
as `VALID` only if: the plugin observed no autosave inside the window **and** the `.ark`
flags did not change. Otherwise — `CONTAMINATED`. This removes the main source of
distortion of the previous watch, where a third of the windows landed on a save.

## 6. `perf.selftest` — automated run of the watch-duty protocol

```
TickProf.perf.selftest <Map> [--budget-min 45]
```

Fully repeats the slot protocol without manual steps and prints the outcome as one table:

| Phase | What it does | Stop criterion |
|---|---|---|
| 1. `wait-world` | waits for `game thread tid` and an RCON response | 15 min, otherwise `SKIP` |
| 2. `apply-prod` | applies the prod config, compares the list, prints the actual state | any item mismatched → `FAIL` |
| 3. `wait-save` | waits for the start of an autosave, then its end | limit 15 min |
| 4. `window-base` | a 240 s window, publishes `VALID/CONTAMINATED` | — |
| 5. `ab-overlap` | `overlapall 0` → window → `overlaptrim 2` → window, each per the save protocol | — |
| 6. `saveworld x2` | two runs, the freeze measured by RCON unavailability | — |
| 7. `census` | `ticklist`, `ticksets`, `overlapsizes` | — |
| 8. `report` | prints `REPORT-<map>.md` into the plugin directory | — |
| 9. `profile` | **last**, 60 s, unless `--no-profile` is given | — |

The output format is a Markdown table, ready to be inserted into a report without edits.
The `profile` phase goes strictly last: historically the sampler on top of an autosave
has twice brought down the server with no crash backtrace and no dump.

## 7. Rollout order for new features

1. A feature is built offline and is not deployed to the bench.
2. The whitelist is checked against the class list from A2.
3. Bench: deploy from `c:/saves`, prod config, a reference window.
4. A/B on a real save: arm A — disabled, arm B — enabled, a 300 s window
   after the save protocol. The acceptance criterion is the declared delta, no crashes.
5. Rollback is verified explicitly: the rollback command, then a control window.
6. A feature is included in the prod config only after the rollback check.