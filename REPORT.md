# GameThread parallelization - ARK: Survival Evolved v361 (ShooterGameServer.exe)

Analysis 2026-10-16/17. Xeon E5-2697 v2, **24 logical cores**, 64 GB RAM. Verified by disassembly of
`ShooterGameServer.exe` (v361 dump in Ghidra), the UE4.5 sources in `C:\Dev\UnrealEngine-4.5`, or
measurement on the live server `C:\asmdata\Servers\Server1`.

## Master summary

1. **The server is physically single-threaded** (GameThread 0.93-0.97 of 24 cores; the other 23 cores
   and 30 process threads idle), proven at machine-code level: `SingleThreadedMode()` folded into
   `bAllowConcurrentTicks = false` (RVA `0x270B500`); `bRunOnAnyThread` never set anywhere in UE4.5.
2. **The bottleneck is not actor ticks (~5.5%)** but collision/overlap ~29%, name/UObject resolution
   ~7%, allocations ~6.5%.
3. **Four caches + overlaptrim: -79% GameThread CPU** (0.871 -> 0.180 s/s), 15.5 -> 29.9 ticks/s = the
   `NetServerMaxTickRate` limit; with a player 88.30 -> 19.69 ms CPU/tick (-77.7%). Safe set:
   `TickProf.fncache 1`, `iscache 1`, `cachename 1`, `overlaptrim 2`, `nochart 1`.
4. **The 1-byte async-tick patch (RVA `0x270B53A`) slows the server** (33.4 -> 42-46 ms/frame): tool
   only, not to be applied.
5. **The tick ceiling is a clamp [10; 120] (`0x78`) in `UGameEngine::GetMaxTickRate`** (RVA
   `0x253B26E`); with `TickProf.maxfps 200000` the real one-thread ceiling is **204 t/s**.
6. **Control A/B: 115.5 t/s** (clamp 120, 33% core load) vs **221.4 t/s** (lifted) = **x1.9**; `fixclamp`
   now applied automatically at plugin load (P12).
7. **The 120-clamp ceiling is wall time, not CPU**: 2.5-4 ms CPU of the 8.96 ms frame (`StartFrame`
   3.05 ms = 34%); removing ~90% of ticking components: CPU/tick -21%, 0 extra t/s.
8. **223 tasks enqueued per frame, not ~52 780** - P1/P2 refuted/cancelled; StartFrame 2.748 ms at
   12.3 us/enqueue is not explained by task count.
9. **Mass disabling of actor ticks crashes the server** (`TickProf.cull`, `TickProf.actortickoff`):
   both blocked behind `force`.
10. With a player the clamp does not bind (29.6 t/s at 24.4 ms/tick = a ~41 t/s ceiling at 100%), so
    lower ms/tick first, then raise the limit.

---

## 1. Environment

- `ShooterGameServer.exe`, 80 MB, 223 355 functions; UE 4.5 (PhysX, `Engine/Content`,
  HoudiniEngine/RuntimeMeshComponent plugins), not UE5.
- Full `ShooterGameServer.pdb` (382 MB), RSDS age 1, GUID `1ea687d3-de66-46b6-9539-7c3a51eb5a46`.
- ArkApi V3.56 (`version.dll` + PolyHook2); NoGC, NoSteam, FastRejoin installed.
- Launch `TheIsland?listen?Port=7777?QueryPort=27015?MaxPlayers=70 ... -nosteamclient -NoHangDetection`;
  104 levels, the server spawns wild dinos itself.
- No separate `Core`/`Engine`/`ShooterGame` modules; hooks by name (`UWorld.Tick`), resolved from the
  PDB at runtime.

---

## 2. Why everything runs on a single thread

`SingleThreadedMode()` (`TickTaskManager.cpp:93`) = `IsRunningDedicatedServer() ||
FPlatformMisc::NumberOfCores() < 3` - the only dispatcher switch: `StartFrame()` then sets
`bAllowConcurrentTicks = false` (the `AllowAsyncComponentTicks` branch is never executed),
`StartTickTask()` publishes `UseContext.Thread = ENamedThreads::GameThread`, `RunTickGroup()` waits
inline on `bBlockTillComplete || SingleThreadedMode()`. Confirmed in v361 -
`FTickTaskSequencer::StartFrame`, RVA `0x270B500` (tag `tickpath`):

```c
this->bLogTicks = iVar4 != 0;               // TAutoConsoleVariable CVarLogTicks
this->bAllowConcurrentTicks = false;        // <- literal, no checks
```

Neither `IsRunningDedicatedServer()` nor a read of `CVarAllowAsyncComponentTicks` exists in the binary;
the string `AllowAsyncComponentTicks` is present (CVar registration) but never read;
`FTickTaskManager::StartFrame` (RVA `0x270DB60`) contains `(this->Context).Thread = GameThread;`.

Second lock: the only read of `bRunOnAnyThread` (`TickTaskManager.cpp:117`) selects AnyThread only if
`bRunOnAnyThread && bAllowConcurrentTicks && bIsOriginalTickGroup`. Exactly three occurrences in all
`Engine\Source` (the UPROPERTY, `false` in the constructor at line 951, and this read);
`RegisterComponentTickFunctions` / `SetupActorComponentTickFunction` (line 477) never set it;
`bAllowConcurrentTick` is unused there. **Even with this lifted, only ticks with a manually set flag go
to a worker.**

---

## 3. Measurements on the live server

### 3.1 Thread load (no players, after InitWorld)

```
thread      cpu_s/s   % of core
GameThread   0.934     93.4%     <- right after the world starts
GameThread   0.25      25%       <- settled regime
the rest     ~0.00     <0.5% each, 30 threads in the process
```

33% of its time the GameThread **sleeps** (`NtDelayExecution`) or waits (`NtWaitForSingleObject`) -
the pause between ticks, not work.

### 3.2 Sampling profile of the GameThread

61 165 samples over 150 s (~410 Hz); 33.0% `Sleep`/`Wait`, 41 004 executing code; symbolization 100%.
Modules: `ShooterGameServer.exe` 41.8%, `PhysX3_x64.dll` 10.4%, `PhysX3Common_x64.dll` 7.8%,
`MSVCR120.dll` (memcpy/memset) 4.3%, `ntdll.dll` 1.8%, rest ~1% - **PhysX total 18.3%** (pure
collision/overlap). Top self time (of executing code): 7.70 `TArray<FOverlapInfo>::AddUniqueImpl<FOverlapInfo>`
(linear search -> quadratic, accumulating overlap results); 2.50 `TSet<TPair<FName,FFoliageMeshInfo*>>::FindId`
(foliage by name, every frame); 2.42 `FName::InitInternal_FindOrAddNameEntry`; 1.58 / 1.27
`MSVCR120 +0x3C963 / +0x3C3F9` (memcpy/memset); 1.39 / 1.20 / 0.47 `FMallocBinned::Malloc /
FreeInternal / Realloc`; 1.38 `SetHitResultFromShapeAndFaceIndex(physx::...)`; 1.28 / 0.63
`TOctree<UPrimitiveComponent>` iterators; 1.04 / 0.83 `APrimalDinoCharacter::Tick` /
`APrimalCharacter::Tick`; 0.65 `FPostConstructInitializeProperties::InitProperties`; 0.58
`FindFaceIndex` (PhysX); 0.54 / 0.50 `RtlLeaveCriticalSection` / `RtlTryEnterCriticalSection`; 0.52
`StaticFindObjectFastInternalThreadSafe`; 0.43 / 0.40 `GeomSweepMulti_PhysX` /
`GeomOverlapMulti_PhysX`; 0.40 `FUObjectArray::AllocateSerialNumber`.

Grouped by subsystem: **collision/overlap ~29%** (PhysX 18.3% + `FOverlapInfo::AddUnique` 5.4% + glue
SetHitResult 0.9, FindFaceIndex 0.6, GeomSweep/Overlap 0.8, FPxQueryFilterCallback 0.4, FBodyInstance
0.4 + octree 1.7%); **name/object resolution ~7%** (Foliage TSet 1.7, FName 1.8, UObject 1.1,
FPostConstruct 0.6, UStruct 0.6, StaticFindObject 0.5, IsA/IsChildOf); **memory ~6.5%** (FMallocBinned
2.2% + memcpy/memset 4.3%); **entity ticks ~5.5%** (APrimalDinoCharacter 1.6, APrimalCharacter 1.4,
UCharacterMovementComponent 0.8, UPrimalCharacterStatusComponent 0.4, ANPCZoneManager 0.4,
UActorComponent 0.4, USkeletalMeshComponent 0.4); sync/dispatcher ~2% (Rtl*CriticalSection 1.0,
FLockFreeVoidPointerList 0.4, FTickTaskManager 0.4).

---

## 4. What was done and where it lives

Tools (`C:\Dev\_research`): `pdbsym.cpp` (DIA dump of 710 205 functions and 26 903 globals to TSV in
1061 s - dbghelp cannot read this PDB, DIA can); `load_syms.py` (TSV -> SQLite `v361.sqlite` in 8 s);
`symbolize.py` (RIP -> names, `--exclude-idle`); `bymodule.py`; `stackdump.py`; `threadcpu.py`
(`GetThreadDescription`); `rcon.py` (Source RCON client); `addrcheck.cpp` (DIA `addressOffset` vs real
RVA); `dllsym.py`, `probe.cpp`, `pe_dbg.py`; `run_measure.py`.

Plugin `TickProf` (`C:\Dev\ARK-Server-Plugins\TickProf`): phase timers on hooks + GameThread sampling
profiler (`SuspendThread` + `GetThreadContext`), hooks probed one by one with `TickProf.hook <0..11>`.
Ghidra dump: 24 key functions renamed from the PDB, tagged `gamethread`/`tickpath`
(`FEngineLoop::Tick`, `UWorld::Tick`, `UWorld::RunTickGroup`, `UWorld::TickNetClient`,
`FTickTaskManager::{StartFrame,RunTickGroup,EndFrame,RunPauseFrame}`,
`FTickTaskSequencer::{StartFrame,ReleaseTickGroup}`,
`FTickTaskLevel::{QueueAllTicks,QueueNewlySpawned,RunPauseFrame}`,
`UNetDriver::{TickDispatch,TickFlush}`, `UActorChannel::ReplicateActor`, `CollectGarbage`,
`AShooterGameMode::Tick`, `AShooterGameState::Tick` and others); `ntdll.dll` imported, identifying
`NtDelayExecution` (sleep) and `NtWaitForSingleObject` (waiting).

---

## 5. What failed and why

`dbghelp` returns 0 symbols on this PDB (valid RSDS) - DIA (`msdia140.dll`) is the working path. Hooks
on `FEngineLoop.Tick` / `UWorld.Tick` bring the server down (address resolves correctly - DIA gives
`addressOffset = RVA - 0x1000`; ArkApi computes `imageBase + BaseOfCode + offset`; `UWorld.Tick` also
carries ArkApi's `CheckOnTickCallbacks` and the chain breaks): the GameThread settles into
`ReportCrash -> ReportCrashUsingCrashReportClient -> FMessageDialog::Open`. `AShooterGameMode.Tick` /
`UWorld.TickNetClient` hooks are unstable; verified working: `UWorld.RunTickGroup`,
`FTickTaskManager.StartFrame`, `FTickTaskManager.EndFrame`, `UNetDriver.TickDispatch`,
`Global.CollectGarbage`. No synthetic load (`UShooterCheatManager::SpawnDino` / `UWorld::SpawnActor`
crash the same way) - natural profiles, no players; no phase timers (the RIP-based profile obtained
instead).

---

## 6. The parallelization plan

**Step 1** - patch the `bAllowConcurrentTicks = false` write (RVA `0x270B500`) to `true`. **Step 2** -
set `bRunOnAnyThread` for whitelisted, prerequisite-free tick functions in
`FTickTaskLevel::AllEnabledTickFunctions` (~5.5% + some components; `AddPrerequisite` ticks stay on the
GameThread; `TG_StartPhysics/TG_EndPhysics` order preserved via group barriers; components writing
`GUObjectArray` or touching `UWorld` excluded). **Step 3** - collision/overlap ~29%: replace
`AddUniqueImpl` (O(n^2)) with `TInlineAllocator` + sorting or a bitset; batch one `GeomOverlapMulti` per
actor set; cache overlap results for static geometry. **Step 4** - a `FName -> pointer` cache
(`FindId` 1.7%, `FName::FindOrAddNameEntry` 1.8%, `InitProperties`, `StaticFindObject`, ~7%).
**Step 5** - memory ~6.5% shrinks after step 3; raise batch-allocation limits. **Step 6** - prepare
`UActorChannel::ReplicateActor` serialization on workers; `CollectGarbage` incrementally on a worker
(NoGC installed). Full parallelization is impossible (`UWorld::Tick` has global ordering dependencies:
UObject accounting, level states, replication order, physics-group barriers); the realistic goal is
removing collision, name-resolution and memory work.

---

## 6a. What was actually done and measured

All changes live in `TickProf`, enabled via RCON with rollback. Offsets from the PDB via
`fieldcheck.exe` (DIA): `FTickFunction` bitfield dword @ +12 (`bRunOnAnyThread` = bit 4, 0x10),
`Prerequisites` TArray @ +40, `TickGroup` +8; `FTickTaskSequencer::bAllowConcurrentTicks` +560;
`AActor::PrimaryActorTick` +40; `UActorComponent::PrimaryComponentTick` +48; `ULevelBase::Actors`
TArray @ +136; `UPrimitiveComponent::OverlappingComponents` TArray @ +1312, `bGenerateOverlapEvents`
bit 10 in dword @ +500; `UObjectBase::Class` +16.

**Tool 1 - `bAllowConcurrentTicks` patch.** Instruction `C6 86 30 02 00 00 00` (`MOV byte ptr [RSI+0x230], 0`)
at RVA `0x270B534` (immediate byte at RVA `0x270B53A`); all 7 opcode bytes verified first - once it
saved the server from a wrong-offset patch. `TickProf.fix concurrent 1|0`, verify:
`TickProf.verify`.
**Tool 2 - marking tick functions.** Walk of all 104 levels' actors + all components via
`GetObjectsOfClass(UActorComponent::StaticClass)`; bit write; modes 0 clear / 1 all / 2
`TG_DuringPhysics` without prerequisites / 3 `TG_PrePhysics` / 4 actors / 5 all without prerequisites;
class whitelist from a file. Census: **52 780 of 276 292**, 5 281 with prerequisites; ticking actors
424, components 599.
**Tool 3 - the Kismet canvas cache.** 2.5% of the profile = `TSet<FName,FFoliageMeshInfo*>::FindId`
via `DoGetCanvasByName` / `GetCanvasByName` / `FindFunctionByName`; hook on `Global.DoGetCanvasByName`
(`UCanvas* __cdecl DoGetCanvasByName(FName)`), 1024 slots, negatives cached.
**Tool 4 - overlaptrim.** `BeginComponentOverlap` does linear `IsOverlappingComponent` + linear
`AddUnique` into `OverlappingComponents` - O(n^2); `TickProf.overlaptrim <threshold>` clears arrays
above the threshold and removes `bGenerateOverlapEvents`.

**Results (external GameThread CPU, 40 s window):**

| Step | CPU, s/s | ticks/s | frame time |
|---|---|---|---|
| BASELINE | 0.746 | 14.2 | 70.7 ms |
| + the canvas cache | 0.605 | 28.3 | 35.3 ms |
| + the overlap trim (threshold 32) | 0.402 | 29.7 | 33.7 ms |
| + the overlap trim (threshold 8) | 0.254 | 29.8 | 33.6 ms |

**-66% CPU, x2.1** (14.2 -> 29.8 ticks/s); trim removed 495 051 overlap records from 24 369 components
(threshold 32: 260 278 records from 787 components). 29.8 ticks/s = the `NetServerMaxTickRate` limit.

---

## 6b. The ARK dump and the second round

`C:\Dev\ARK_SE_code_dump\game_aquatica.c` - Binary Ninja decompilation of the client binary, 2.3
million lines, **51 377 named functions** (game code = server code; addresses from the server PDB;
index `dump_index.json`). (1) Second O(n^2): `UVictoryCore::ServerOctreeOverlapActorsBitMask` calls
`AddUnique` **twice per result** (dino + structure-container lists). (2) Root of 3.3% of the profile:
`UObject::ExecuteUbergraph` calls `UClass::FindFunctionByName(this->Class, (FName)0xe0,
InIncludeSuper)` with a **constant** FName on every blueprint tick (`TSet::FindId` per class level)
- a cache candidate. (3) >=2 `AddUniqueImpl` calls: 38 functions, rest are `GetLifetimeReplicatedProps`
and `InitRHI` - no other hot O(n^2) sites.

---

## 7. Top-10 decisions and their results

| # | Decision | Profile share | Result |
|---|---|---|---|
| 1 | The cache of `UClass::FindFunctionByName` | 3.3% | **works: -40% CPU, ticks 15.5 -> 28.0/s** |
| 2 | `overlaptrim` threshold 2 | 8-12% | **works: -41% CPU, ticks -> 29.9/s** |
| 3 | The cache of `UStruct::IsChildOf` | 1.35% | **works: -13% CPU** |
| 4 | The cache of `DoGetCanvasByName` | 2.3% | **works: -33% CPU, ticks -> 29.7/s** |
| 5 | `overlaptrim` threshold 1 | 8-12% | works (stricter than threshold 2) |
| 6 | `p.bTickPhysicsAsync 1` (the standard UE CVar) | - | **works: -12% CPU, does not hang the server** (90 s observation) |
| 7 | Full disabling of overlap events (`overlapall 1`) | 8% | works, but **breaks gameplay** - do not apply |
| 8 | The patch of `bAllowConcurrentTicks` + `bRunOnAnyThread` | - | **slows down** (33.4 -> 42-46 ms/frame) |
| 9 | A cache of `ServerOctreeOverlapActorsBitMask` | ~1% | not implemented: a stub with out-parameters is needed |
| 10 | Suppressing `FPostConstructInitializeProperties` etc. | 2.6% | not implemented: the source of object creation not found |

**Cycle 5** (35 s windows): base 0.773 s/s / 14.0 t/s -> +FindFunctionByName 0.570 / 28.2 -> +trim 2
0.422 / 29.5 -> +trim 1 0.273 / 29.8 -> +all-overlap-events-off 0.207 / 29.9.
**Cycle 6** (clean start, 35 s windows): 0.871 / 15.5 -> 0.523 / 28.0 (-40%) -> +IsChildOf 0.457 / 29.0
(-13%) -> +canvas 0.305 / 29.7 (-33%) -> +trim 2 0.180 / 29.9 (-41%) - **in total -79%, 15.5 -> 29.9**.
Clean-start "final" cycle (40 s windows): 0.688 -> 0.328 s/s (-52%), 28.4 -> 29.6 t/s. Load after
`InitWorld` decays on its own - the primary metric is ticks/s and sequential increments within a run.

**Profile after all changes:** idle samples 33.0% -> **92.6%**; executing-code samples 40 301 ->
**3 385**; `AddUniqueImpl<FOverlapInfo>` 8.25% -> not in top-16;
`TSet<FName,FFoliageMeshInfo*>::FindId` 2.26% -> not in top-16. Remaining: `RunTickGroup`,
`TGraphTask`, `APrimalDinoCharacter::Tick`, `FTimerManager` - irreducible game logic.

**Async ticks:** the patch works (field reads `1`, tens of thousands marked) but is **negative**:
33.4 -> 42.2 ms ("components of TG_DuringPhysics"), 45.9 ms (all without prerequisites), ticks
29.9 -> 23.7/s; CPU moved to workers, the frame got more expensive. Engine's own note
(`TickTaskManager.cpp:611`): "the parallel case doesn't ever seem to be faster, so it disabled by
default". Keep as a tool; do not apply.

---

## 8. The final assessment

**Apply:** `TickProf.fncache 1` (a class's function set is unchanged; negatives cached), `TickProf.iscache 1`
(hierarchy fixed on the server), `TickProf.cachename 1` (canvases fixed per session),
`TickProf.overlaptrim 2` (only bloated overlap lists touched), `p.bTickPhysicsAsync 1` (standard CVar,
tested separately). Script: `python C:\Dev\_research\apply_recommended.py` (rollback `--revert`).
**Not to apply:** the async-tick patch (33.4 -> 42-46 ms/frame), full overlap disabling (breaks gameplay
for ~0.07 s/s). **Conclusion:** full parallelization is impossible in this build - the engine turned
the path off, our attempt confirmed it; the real result is **removing extra work**: -79% GameThread
CPU, 15.5 -> 29.9 ticks/s, then 92.6% idle. Hanging note: one run hung after `p.bTickPhysicsAsync 1`;
an isolated recheck (30 s control, 60 s with async physics, 30 s return) did not reproduce it - the
culprit was combining with `overlapall` on 139 745 components; `p.bTickPhysicsAsync` alone is safe.

---

## 9. Lifting the tick limit: dynamics

The limiter is `UNetDriver::NetServerMaxTickRate` (**int32**, offset 72; decompilation:
`MOV EDX,[RAX+0x48]` -> `CMP/CMOVL` -> `CVTDQ2PS`). CVar `net.MaxNetTickRate` is **absent**;
`UEngine::GetMaxTickRate` returns 0 (only `t.MaxFPS` and hitch sleeping). `TickProf.maxfps <N>` writes
the field directly, re-set every 5 s; `TickProf.maxfps 0` restores the default. Measurement (30 s
window, external GameThread CPU, settled regime):

| Limit | ticks/s | CPU, s/s | ms CPU per tick |
|---|---|---|---|
| 30 (standard) | 15.5* | 0.961 | 62.00 |
| 60 | 53.8 | 0.977 | 18.14 |
| 120 | 53.8 | 0.938 | 17.41 |
| 300 | 82.9 | 0.898 | 10.83 |
| 1000 | 110.2 | 0.672 | 6.10 |
| **200000** | **114.1** | **0.531** | **4.66** |

\* first window on world streaming; time per tick overstated. Ceiling not 30 but ~114 t/s = 4.66
ms/tick; the server uses 0.53 of 24 cores = 2% of the machine. At a limit of 30 everything hits the
ceiling; further comparisons used the lifted limit (also a stress test).

### 9a. Optimizations at the lifted limit

30 s windows, caches one by one: no optimizations 117.7 t/s / 0.328 s/s / 2.79 ms/tick;
+FindFunctionByName 116.1 / 0.484 / 4.17 (-1%); +IsChildOf 116.2 / 0.297 / 2.55 (-1%); +canvas
112.3 / 0.375 / 3.34 (-5%); +overlaptrim 116.0 / 0.297 / 2.56 (-1%); async physics 115.1 / 0.359 /
3.12 (-2%); async ticks 117.5 / 0.266 / 2.26 (-0%). **Not a single optimization raises throughput** -
valid only while the clamp at 120 (section 13) is active; t/s is blind at 112-118, only ms CPU/tick is
informative; after the lift, CPU converts into speed. +/-5% is noise; per-tick CPU 2.26-4.17 ms.

### 9b. Where the frame time goes

Phase timers (40 s window, 4465 frames, 111.6 ticks/s, 8.96 ms/frame): `FTickTaskManager::StartFrame`
4465 calls, 13612.7 ms - **3.05 ms (34%) per frame**; `UWorld.RunTickGroup` 40194 calls, 8036.5 ms -
1.80 ms (20%); `UNetDriver.TickDispatch` 4465, 26.2 ms - 0.006 ms (0.1%); `EndFrame` 4466, 14.2 ms -
0.003 ms (0%); `CollectGarbage` 0 (NoGC). Measured phases = 21.7 of 40 s = 54%; ~46% outside the hooks
(main loop, network, worker waits, limiter sleep). **Strategy change:** the ~117 t/s ceiling is not
CPU - throughput rises only by shortening **waiting time** (sleep granularity, task-graph barriers).
At the standard 30 ticks/s the optimizations remain meaningful (-79%).

### 9c. The tick-task queue

Census (`TickProf.tickclasses`):

```
ticking components = 264, unique classes = 2
   SkeletalMeshComponent        x132
   ShooterCharacterMovement    x132
```

Plus 424 ticking actors = **700 tick functions**. `TickProf.tickoff` for 28 058 decorative components
(StaticMesh 26 485, Landscape 1472, Spline 101) changed nothing - not registered, never in the queue.
Real ticking components: 264 tick -> 119.3 t/s / 0.422 s/s / 3.54 ms/tick; 14 tick -> 117.2 / 0.328 /
**2.80** - **~90% removed: CPU per tick -21%, 0 extra ticks.** Final timers (109 t/s, 9.2 ms/frame):
`StartFrame` **3.78 ms (41%)**, `RunTickGroup` 1.41 ms (15%), `TickDispatch` 0.002 ms, `EndFrame`
0.001 ms, `CollectGarbage` 0. `StartFrame` = enqueueing ~700 tasks over 104 levels - **5 us/task with
104 levels traversed**; fixable only by repacking levels or editing `FTickTaskManager::StartFrame` in
the engine.

### 9d. New tools

`TickProf.maxfps <N>` / `.maxfps 0`; `TickProf.tickclasses`; `TickProf.tickoff <substring>`;
`TickProf.cull <radius>` / `TickProf.cullstat` - `cull` disabled by default (no players, empty position
list). PDB symbols dumped once (~18 min) via `pdbsym.cpp` + DIA (`msdia140.dll`) to `v361.tsv`, indexed
by `load_syms.py`; measurement via `run_measure.py --sample-seconds 150`, analysis via
`symbolize.py '<Plugins\TickProf\prof_*.bin>' --top 40 --exclude-idle` and `bymodule.py`.

---

## 10. Tests with a connected player

GameThread grew 0.53 -> 0.65 s/s calm (up to 3.34 s/s at activity). Profile, no optimizations (90 s
window, 45 817 samples): `TSet<TPair<FName,FFoliageMeshInfo*>>::FindId` 2.70%,
`APrimalDinoCharacter::Tick` 2.69%, `APrimalCharacter::Tick` 2.38%,
`FName::InitInternal_FindOrAddNameEntry` 2.10%, `FMallocBinned::FreeInternal / Malloc` 3.08%,
`FTickTaskManager::StartFrame` 1.03%, `UEngine::TickFPSChart` 0.47%, `IncrementalPurgeGarbage` 0.52%;
classes: APrimalDinoCharacter 6.4%, APrimalCharacter 4.7%, UCharacterMovementComponent 3.5%,
AAIController 1.7% - **~17% is dino AI**.

Measurements (tickrate 30, 30 s windows): no optimizations 0.651 s/s / 21.77 ms/tick; +caches 0.604 /
20.23 (-7%); +trim 0.557 / 18.66 (-14%); cull 50 km (deliberately ineffective) 0.573 / 19.18.

**Distance culling crashes the server:** `TickProf.cull 15000` drove the GameThread to 1.7 s/s, RCON
dead, restart needed (the player disconnects). Cause: skipping `AActor::TickActor` breaks engine
invariants (deferred operations, timers, replication state unserviced while the actor stays visible).
**`TickProf.cull` is blocked** (requires `force`). `TickProf.nochart 1` is safe (removes
`UEngine::TickFPSChart`, 0.47%); `tickoff` works but not applied live.

**Dangerous operations found:**

| Operation | Consequence |
|---|---|
| `plugins.unload TickProf` with active phase hooks | the server hangs (reproduced twice) |
| `TickProf.cull` | the GameThread hangs |
| `TickProf.actortickoff` | the GameThread hangs (mass disabling of actor ticks) |
| `TickProf.hook 5` (`FillLevelList`) | a hang on installing the hook |
| `TickProf.overlapall 1` | breaks game mechanics |
| `TickProf.fix concurrent 1` + `tickflags` | slows the frame 1.3-fold |
| unloading the plugin with a player connected | not tested, risky |

**Final run, only safe changes** (30 s windows, tickrate 30, player connected; streaming inflates
absolute values - sequential increments comparable): base 0.995 s/s / 88.30 ms/tick -> +caches 0.859 /
49.87 (-43.5%) -> +trim 2 0.693 / 23.40 (-73.5%) -> +nochart 0.578 / 19.69 (**-77.7%**). Control in the
settled regime: **29.6 t/s, 0.722 s/s, 24.4 ms CPU per tick**, responsive. Post-change profile:
APrimalCharacter 5.8%, APrimalDinoCharacter 4.5%, UCharacterMovementComponent 2.6% - dino AI; name
lookup, `AddUniqueImpl<FOverlapInfo>`, name resolution left the top.

Final configuration:

```
TickProf.fncache 1        the cache of UClass::FindFunctionByName
TickProf.iscache 1        the cache of UStruct::IsChildOf
TickProf.cachename 1      the cache of DoGetCanvasByName
TickProf.overlaptrim 2    trimming the bloated overlap lists
TickProf.nochart 1        disabling FPS chart maintenance
```

Not enabled: `cull` (crashes), `overlapall` (breaks gameplay), the async-tick patch (slows), unloading
(hangs).

---

## 11. Round P1: how many tasks are actually enqueued

| Level | What it means | Value |
|---|---|---|
| 1 | actors and components that **have** a tick function | 52 780 |
| 2 | entries in `AllEnabledTickFunctions` - what the manager walks | **3 510** |
| 3 | tasks enqueued per frame (counter `QueueTickFunction`) | **223** |

Neither explains 2.7 ms: 3 510 x 72 ns = 0.25 ms; 223 x 5.4 us is absurdly much. **Brief hypothesis:**
StartFrame (~2.7-3.8 ms) accounts ~52 780 registered tick functions, mostly stasised dinosaurs
enqueued and exiting immediately (~72 ns/task); forecast: StartFrame ~0.1 ms, ceiling 117 -> 250-400
t/s. **Measured** - `FTickFunction::QueueTickFunction` over 30 s:

```
tickq: frames=465 total tasks=255043 on average 223 per frame
```

**223 tasks per frame, not ~52 780 - refuted.** StartFrame 2.748 ms; 12.3 us per enqueue (~0.07
expected) - not explained by task count. **Stasis gives nothing:** `APrimalCharacter::Stasis` /
`APrimalDinoCharacter::Stasis` touch no tick function (flag checks only: `bDestroyOnStasis`,
`bUseBPPreventStasis`, `BPPreventStasis`); stasis is a buff (`APrimalBuff_Grappled`,
`APrimalBuff::Stasis`); no `bIsStasised` field - only `LastUnstasisTime`, `NotifyStasis`,
`NotifyUnstasis`; nothing to remove from `AllEnabledTickFunctions` - **P2 cancelled**.
**P1 take-three infeasible:** stopping the ticks of 379 ticking dinosaurs out of 212 tasks = the same
hang as `cull`; `TickProf.actortickoff` blocked like `cull`.

| Item | Result |
|---|---|
| P1 "how many tasks are in the queue" | **223 per frame**, not ~52 780 - refuted |
| P1 take-two | own code of `StartFrame` - 0.6% of samples |
| P1 take-three | infeasible: mass disabling of ticks crashes the server |
| P2 "remove stasis from the queue" | **cancelled**: nothing to remove, stasis touches no tick function |
| P3 "decode the wall" | partially: `UpdateTimeAndHandleMaxTickRate` does not sleep (returns 0), `UNetDriver::TickFlush` has no sleep - limiter further down |
| P4 "the fncache line" | defect fixed: single-slot cache evicted keys with more live pairs than the table; 8-slot probe + hit counters added |
| P5 "AI under the player" | not started |
| P6 "hygiene" | not started |

Either explain the 12-28 us per enqueue (implausible), or accept that the StartFrame measurement
includes time outside enqueueing.

---

## 12. Unraveling "the wall": NtDelayExecution and the clamp of 120

Profile of the same window (40 s, 20 170 samples, 111.6 t/s, no `--exclude-idle`): **24.37%
`NtDelayExecution`** (ntdll+0x15F484) - the thread sleeps; 4.14% `NtWaitForSingleObject`
(ntdll+0x15EE84); 1.76% `APrimalDinoCharacter::Tick`; 1.62% `NtQueryInformationProcess`
(ntdll+0x15F124); 1.56% `NtSetEvent` (ntdll+0x15EFC4); 1.40% `NtQuerySystemInformation`
(ntdll+0x15F4C4); 1.21% `NtDeviceIoControlFile` (ntdll+0x15EEE4); 0.57%
`FTickTaskManager::StartFrame`. External modules 53.8%, our image 45.9%, unknown 0.2%. **No
symbolization hole:** StartFrame's own code is 0.57% and honest.

**The ceiling found - a clamp of 120 in `UGameEngine::GetMaxTickRate`.**
`UEngine::UpdateTimeAndHandleMaxTickRate` calls the getter virtually (vtable slot +0x290). The override
(RVA `0x253B1C0`, 287 bytes):

```c
int32_t MaxTickRate = *(int32_t *)(Driver + 0x48);      // NetServerMaxTickRate
int32_t Clamped = (MaxTickRate < 10) ? 10
               : ((MaxTickRate < 0x78) ? MaxTickRate : 0x78);
Rate = (float)Clamped;
```

`0x78` = **120**: "200000" is clamped into [10; 120]; the observed 114-117 t/s ceiling runs into this
number. Instruction RVA `0x253B26E`: `B9 78 00 00 00` = `MOV ECX, 0x78`, then `CMP EDX,ECX` /
`CMOVL ECX,EDX`. The patch raises the upper bound to 100000 (`A0 86 01 00`), lower (10) untouched.
`TickProf.fixclamp 1` / `TickProf.fixclamp 0` with opcode checks - the first removable cause of the
ceiling.

**Scan hypothesis closed:** `AllEnabledTickFunctions` = **3510**, tasks per frame = **223** - neither
3510 x 72 ns (0.25 ms) nor 223 x 5.4 us yields 2.7 ms. Census garbage for
FastPath/AllDisabled/NewlySpawned (`FTickTaskLevel` offsets read wrongly - recheck via `fieldcheck`);
`AllEnabledTickFunctions` read correctly (3510). **Dangerous hooks found:** `FillLevelList`
(installation hangs - signature unknown, argument registers lost); `QueueAllTicks` / `QueueNewlySpawned`
untested, probably the same - removed from the hook table; the dispatcher is measured with the
`StartFrame` window flag + a stack sampler inside it (`prof_*.sfstack`, `sfstack.py`).

### 12a. Lifting the clamp (DRAFT, requires a control)

**Not to be published:** back-to-back windows on a decaying load; the indirect proof is strong (no
settled run over the round exceeded 120: 114.1 / 117.7 / 119.3, plus the `0x78` decompilation); the
direct A/B is in section 13. 30 s windows, `NetServerMaxTickRate` = 200000: standard clamp 32.2 t/s /
0.969 s/s / 30.12 ms; **clamp raised to 100000: 64.8 / 0.974 / 15.02**; **lifted + caches + trim: 85.0
/ 0.958 / 11.28**. Effects: the clamp lift **+102%** (decaying load - invalid, later retracted); "+ our
optimizations" **+31%** (also needs a control). Mechanism: thread CPU stays ~0.96 s/s (saturated),
per-tick cost 30 -> 15 -> 11.3 ms - 2.6x more ticks from the same budget; at 30 ticks the -77% CPU was
locked in idle. First-window streaming distortion (9.9 t/s at the standard limit).
`TickProf.fixclamp 1` + `TickProf.maxfps <N>` is the only pair found that moves the ceiling; at 200000
after the lift the server is CPU-bound (~85 t/s) and CPU optimizations convert (+31%). In memory only -
does not survive a reboot.

---

## 13. The control A/B of the clamp (P8) - CONFIRMED

Method: settled regime (server start, 600 s streaming cooldown, 60 s warm-up), 30 s windows with the
clamp alternating on -> off -> on -> off; `NetServerMaxTickRate` = 200000 everywhere; all optimizations on.

| Window | clamp | ticks/s | CPU, s/s | ms CPU/tick | thread load |
|---|---|---|---|---|---|
| warm-up | 120 | 118.6 | 0.333 | 2.81 | 33% |
| **A0** | **120** | **114.9** | 0.328 | 2.85 | **33%** |
| **B0** | **lifted** | **158.4** | 0.958 | 6.05 | 96% |
| **A1** | **120** | **116.1** | 0.833 | 7.18 | 83% |
| **B1** | **lifted** | **284.5** | 0.865 | 3.04 | 86% |

Averages: A (clamp 120) **115.5 t/s**; B (lifted) **221.4 t/s**; gain **x1.9**; sustained >120 - **YES**.
**Deciding argument:** A0 gives 114.9 t/s at 33% thread load - the limit cannot be CPU; A1 at 83% load
gives the same 116.1 (a 2.5-fold load change does not move the speed - the clamp presses it); in B
windows speed follows load (158 t/s at 96% CPU, 284 t/s at 86%) - the bottleneck after the lift is real.

**The sweep with the clamp lifted:**

| `NetServerMaxTickRate` | ticks/s | CPU | load |
|---|---|---|---|
| 150 | 142.6 | 0.771 | 77% |
| 200 | 180.8 | 0.911 | 91% |
| 400 | **204.0** | 0.953 | 95% |

The one-thread ceiling is **~204 t/s**, CPU-limited; growth only by lowering tick cost. The **"+102%"
is retracted** (decaying load, 32 -> 65 t/s within 90 s of startup); correct figure **x1.9** from
alternating windows; "the clamp of 120 blocks all previous CPU work" stands, grew to almost x2.
**Production arithmetic:** with a player 29.6 t/s at 24.4 ms/tick = ~41 t/s at 100% - **in combat the
clamp of 120 does not bind**; the value there is per-tick cost (88 -> 20-24 ms, nearly halved);
`fixclamp` matters for the empty/stress regime. Priority: lower ms/tick first, then raise the limit.

**P7 status - tool ready, culprit not found.** `exp_idle.py` (RIP + stack to a 48-word depth),
`sfstack.py` (stack samples inside the `StartFrame` window). Known: `NtDelayExecution` 24.4%,
`NtWaitForSingleObject` 4.1%, StartFrame own 0.57%. Failed: the external sampler never hit the waiting
state - `GetModuleHandleW` got a Python string instead of `c_wchar_p` (NULL), and for a thread inside a
syscall `GetThreadContext` returns a kernel RIP (0xFFFFF8xx) which the ntdll-range filter discarded.
After fixes still zero hits -> the hand-written `CONTEXT` in Python does not match the Windows layout;
working path: `stackdump.py` + a deep-stack parsing loop. **P7 open** - ~a quarter of GameThread time
idle; at 120 and a 8.96 ms frame the pacing sleep should not trigger at a budget of 8.33 ms; if not
regular pacing, it yields up to x1.5-2 of throughput for free.

**P12:** `TickProf.fixclamp` is applied automatically at plugin load (opcode checks); disabled by
`tickprof_noclamp.txt` next to the plugin or `TickProf.fixclamp 0`.

**Server state after the round:** clamp 120, `NetServerMaxTickRate` = 0 (standard, 30 t/s),
optimizations on, async ticks off; GameThread 0.13 s/s (3.3%).
