# GameThread parallelization — ARK: Survival Evolved v361 (ShooterGameServer.exe)

Analysis performed 2026-10-16/17 on a machine: Xeon E5-2697 v2, **24 logical cores**, 64 GB RAM.

All statements were verified in one of three ways: disassembling
`ShooterGameServer.exe` (the v361 dump in Ghidra), the UE4.5 sources in
`C:\Dev\UnrealEngine-4.5`, or measuring on the live server
`C:\asmdata\Servers\Server1`.

---

## 0. Main conclusion

1. The ARK SE v361 dedicated server is physically single-threaded: **GameThread 0.93–0.97 of 24 cores**,
   the remaining 23 cores and all 30 threads of the process idle.
2. The cause was found and **proven at machine-code level**: `FTickTaskSequencer::SingleThreadedMode()`
   returns `true` on a dedicated server, the compiler folded it into a constant,
   and `bAllowConcurrentTicks` is written as `false`. All tick functions of actors and components
   are published as GameThread tasks. The second lock: `FTickFunction::bRunOnAnyThread`
   is **never set** anywhere in UE4.5 — async ticks are dead in stock.
3. The profile shows that the bottleneck is **not actor ticks** but collision/overlap queries,
   name/UObject resolution, and allocations. This fundamentally changes the plan of work.

---

## 1. Environment

| Parameter | Value |
|---|---|
| Image | `ShooterGameServer.exe`, 80 MB, 223 355 functions — engine and game code linked into a monolith |
| Engine | UE 4.5 (PhysX, `Engine/Content`, HoudiniEngine/RuntimeMeshComponent plugins), not UE5 |
| Symbols | full `ShooterGameServer.pdb` (382 MB), RSDS age 1, GUID `1ea687d3-de66-46b6-9539-7c3a51eb5a46` |
| ArkApi | V3.56 (`version.dll` + PolyHook2); NoGC, NoSteam, FastRejoin installed on the server |
| Launch | `TheIsland?listen?Port=7777?QueryPort=27015?MaxPlayers=70 ... -nosteamclient -NoHangDetection` |
| World | 104 levels, the server spawns wild dinos itself |

There are no separate `Core`/`Engine`/`ShooterGame` modules on disk, so any hook
is addressed by a name like `UWorld.Tick`, and ArkApi resolves it from the PDB at runtime.

---

## 2. Why everything runs on a single thread

### 2.1 The UE4.5 sources

`Engine/Source/Runtime/Engine/Private/TickTaskManager.cpp:93`

```cpp
FORCEINLINE static bool SingleThreadedMode()
{
    if (IsRunningDedicatedServer() || FPlatformMisc::NumberOfCores() < 3)
        return true;
    return false;
}
```

This is the only switch of the entire tick dispatcher:

* `StartFrame():` with `SingleThreadedMode()` → `bAllowConcurrentTicks = false`,
  the branch with the CVar `AllowAsyncComponentTicks` is never executed at all;
* `StartTickTask():` `UseContext.Thread = ENamedThreads::GameThread` — tick tasks
  are published as GameThread;
* `RunTickGroup():` `if (bBlockTillComplete || SingleThreadedMode())` — the groups
  are waited on inline.

### 2.2 Confirmed by disassembling v361

`FTickTaskSequencer::StartFrame`, RVA `0x270B500` (renamed in the dump, tag `tickpath`):

```c
iVar4 = TAutoConsoleVariable<int>::GetValueOnGameThread(&CVarLogTicks);
this->bLogTicks = iVar4 != 0;
this->bAllowConcurrentTicks = false;        // ← literal, no checks
```

Neither `IsRunningDedicatedServer()` nor a read of `CVarAllowAsyncComponentTicks` exists in the
code: the compiler evaluated `SingleThreadedMode()` when building the server binary.
The string `AllowAsyncComponentTicks` exists in the binary (CVar registration), but its value is
never read. `FTickTaskManager::StartFrame` (RVA `0x270DB60`) contains
`(this->Context).Thread = GameThread;`.

### 2.3 The second lock: `bRunOnAnyThread` is dead

`TickTaskManager.cpp:117` — the only read of the flag:

```cpp
if (TickFunction->bRunOnAnyThread && bAllowConcurrentTicks && bIsOriginalTickGroup)
    UseContext.Thread = ENamedThreads::AnyThread;
```

A scan of all `Engine\Source` gives exactly three occurrences of `bRunOnAnyThread`:
the UPROPERTY declaration, initialization to `false` in the constructor (line 951), and this read.
Neither `UActorComponent::RegisterComponentTickFunctions` nor
`UActorComponent::SetupActorComponentTickFunction` (line 477) sets the flag;
the field `bAllowConcurrentTick` is unused in them.

**Consequence:** even after item 2.2 is lifted, a tick will go to a worker only for those
tick functions whose flag is set manually.

---

## 3. Measurements on the live server

### 3.1 Thread load (no players, after InitWorld)

```
thread      cpu_s/s   % of core
GameThread   0.934     93.4%     ← right after the world starts
GameThread   0.25      25%       ← settled regime
the rest     ~0.00     <0.5% each, 30 threads in the process
```

Peak load right after `UWorld::InitWorld` — 93% of one core; in the settled
regime the GameThread is busy about a third. The remaining 23 cores are never used.
Additionally: for 33% of its time the GameThread **sleeps** (`NtDelayExecution`) or waits
(`NtWaitForSingleObject`) — that is the pause between ticks, not work.

### 3.2 Sampling profile of the GameThread

61 165 samples over 150 s (~410 Hz), of which 33.0% are `Sleep`/`Wait`, the remaining 41 004 are
actually executing code. Symbolization 100% (the module map is written together with the profile).

**By modules:**

| Module | Share |
|---|---|
| `ShooterGameServer.exe` (engine + game) | 41.8% |
| `PhysX3_x64.dll` | 10.4% |
| `PhysX3Common_x64.dll` | 7.8% |
| `MSVCR120.dll` (memcpy/memset) | 4.3% |
| `ntdll.dll` (critical sections, atomics) | 1.8% |
| the rest | ~1% |

**PhysX totals 18.3%** — pure collision/overlap.

**Top functions (self time, of executing code):**

| % | Function | What it is |
|---|---|---|
| 7.70 | `TArray<FOverlapInfo>::AddUniqueImpl<FOverlapInfo>` | accumulating overlap-query results, a linear search → quadratic |
| 2.50 | `TSet<TPair<FName,FFoliageMeshInfo*>>::FindId` | looking up foliage info by name, every frame |
| 2.42 | `FName::InitInternal_FindOrAddNameEntry` | name resolution |
| 1.58 / 1.27 | `MSVCR120 +0x3C963 / +0x3C3F9` | memcpy / memset |
| 1.39 / 1.20 / 0.47 | `FMallocBinned::Malloc / FreeInternal / Realloc` | the allocator |
| 1.38 | `SetHitResultFromShapeAndFaceIndex(physx::…)` | parsing PhysX hits |
| 1.28 / 0.63 | `TOctree<UPrimitiveComponent>` iterators | traversal of the collision octree |
| 1.04 / 0.83 | `APrimalDinoCharacter::Tick` / `APrimalCharacter::Tick` | the dino ticks themselves |
| 0.65 | `FPostConstructInitializeProperties::InitProperties` | property initialization at load |
| 0.58 | `FindFaceIndex` | PhysX |
| 0.54 / 0.50 | `RtlLeaveCriticalSection` / `RtlTryEnterCriticalSection` | synchronization |
| 0.52 | `StaticFindObjectFastInternalThreadSafe` | object lookup by name |
| 0.43 / 0.40 | `GeomSweepMulti_PhysX` / `GeomOverlapMulti_PhysX` | the queries themselves |
| 0.40 | `FUObjectArray::AllocateSerialNumber` | object creation |

**Grouped by subsystem:**

| Subsystem | GameThread share | Composition |
|---|---|---|
| **Collision / overlap queries** | **≈29%** | PhysX 18.3% + `FOverlapInfo::AddUnique` 5.4% + the PhysX glue (SetHitResult 0.9, FindFaceIndex 0.6, GeomSweep/Overlap 0.8, FPxQueryFilterCallback 0.4, FBodyInstance 0.4) + octree 1.7% |
| **Name and object resolution** | **≈7%** | Foliage TSet 1.7 + FName 1.8 + UObject 1.1 + FPostConstruct 0.6 + UStruct 0.6 + StaticFindObject 0.5 + IsA/IsChildOf |
| **Memory** | **≈6.5%** | FMallocBinned 2.2% + MSVCR120 memcpy/memset 4.3% |
| **The ARK entity ticks themselves** | **≈5.5%** | APrimalDinoCharacter 1.6 + APrimalCharacter 1.4 + UCharacterMovementComponent 0.8 + UPrimalCharacterStatusComponent 0.4 + ANPCZoneManager 0.4 + UActorComponent 0.4 + USkeletalMeshComponent 0.4 |
| Synchronization, the tick dispatcher | ≈2% | Rtl*CriticalSection 1.0, FLockFreeVoidPointerList 0.4, FTickTaskManager 0.4 |

---

## 4. What was done and where it lives

### 4.1 Tools (`C:\Dev\_research`)

| File | Purpose |
|---|---|
| `pdbsym.cpp` | dumping all 710 205 functions and 26 903 globals of the PDB via DIA to TSV (1061 s). dbghelp cannot read this PDB — DIA works |
| `load_syms.py` | TSV → SQLite `v361.sqlite` (8 s), indexes by rva and name |
| `symbolize.py` | RIP samples → function names; `--exclude-idle` drops `Sleep`/`Wait`; reads the module map |
| `bymodule.py` | aggregation of the profile by modules and classes |
| `stackdump.py` | RIP and stack of any thread of a live process with symbolization from the PDB |
| `threadcpu.py` | CPU by threads, thread names from `GetThreadDescription` |
| `rcon.py` | a Source RCON client |
| `addrcheck.cpp` | checking `addressOffset` from DIA against the real RVA (verification of ArkApi resolving) |
| `dllsym.py`, `probe.cpp`, `pe_dbg.py` | PE/DLL parsing, checking the PDB format |
| `run_measure.py` | an automated measurement run |

### 4.2 The `TickProf` plugin (`C:\Dev\ARK-Server-Plugins\TickProf`)

Phase timers on hooks + a sampling profiler of the GameThread (`SuspendThread` +
`GetThreadContext`, offline symbolization). Hooks are installed one by one with the command
`TickProf.hook <0..11>` — this is how we determined which one breaks the tick.

### 4.3 The Ghidra dump

24 key functions renamed from the PDB and tagged `gamethread`, `tickpath`:
`FEngineLoop::Tick`, `UWorld::Tick`, `UWorld::RunTickGroup`, `UWorld::TickNetClient`,
`FTickTaskManager::{StartFrame,RunTickGroup,EndFrame,RunPauseFrame}`,
`FTickTaskSequencer::{StartFrame,ReleaseTickGroup}`,
`FTickTaskLevel::{QueueAllTicks,QueueNewlySpawned,RunPauseFrame}`,
`UNetDriver::{TickDispatch,TickFlush}`, `UActorChannel::ReplicateActor`,
`CollectGarbage`, `AShooterGameMode::Tick`, `AShooterGameState::Tick`, and others.
The dump is saved. Additionally, `ntdll.dll` was imported — it identified
the hot addresses (`NtDelayExecution` = sleep, `NtWaitForSingleObject` = waiting).

---

## 5. What failed and why

* **`dbghelp` does not read this PDB**: `SymEnumSymbols`/`SymFromAddr` return 0 symbols
  with a valid RSDS record. The working path — DIA (`msdia140.dll`), as used by ArkApi.
* **The `FEngineLoop.Tick` hook brings down the server.** The address resolves correctly: DIA returns
  `addressOffset = RVA − 0x1000`, ArkApi sums `imageBase + BaseOfCode + offset`
  and gets the correct VA. After the hook is installed the GameThread settles into
  `ReportCrash → ReportCrashUsingCrashReportClient → FMessageDialog::Open` —
  the modal window of the crash reporter; the process is alive, but does not tick.
* **A second hook on `UWorld.Tick` also brings down the server**: that function already carries
  the hook of ArkApi itself (`CheckOnTickCallbacks`), and the chain of detection breaks.
* **Hooks on `AShooterGameMode.Tick` / `UWorld.TickNetClient` are unstable**: in some
  runs they hold, in others they bring the server down. Working and verified:
  `UWorld.RunTickGroup`, `FTickTaskManager.StartFrame`, `FTickTaskManager.EndFrame`,
  `UNetDriver.TickDispatch`, `Global.CollectGarbage`.
* **Synthetic load cannot be created**: both `UShooterCheatManager::SpawnDino`
  and `UWorld::SpawnActor` by a dino class bring the server down with the same crash reporter.
  Therefore the profile was taken on natural load (no players).
* **Phase timers were not obtained**: the working hooks were installed, but the run managed
  to fall on `AShooterGameMode.Tick` before the second sampling phase started. The RIP-based
  profile was obtained, and it is more informative.

---

## 6. The parallelization plan

### Step 1. Lift the prohibition on async ticks (a 1-byte patch)

`FTickTaskSequencer::StartFrame`, RVA `0x270B500`: the instruction writing
`this->bAllowConcurrentTicks = false` is changed to write `true`.

The CVar `AllowAsyncComponentTicks` is useless — the compiler removed its read.
Expected effect: `StartTickTask` will start choosing `ENamedThreads::AnyThread`
for all tick functions with `bRunOnAnyThread`.

### Step 2. Mark safe tick functions

Walk `FTickTaskLevel::AllEnabledTickFunctions`, and for each tick function check:
no prerequisites, the component class is in the whitelist (no access to the UObject registry,
no net/GC), and set `bRunOnAnyThread`. The expected share — the current ~5.5%
(entity ticks) plus some of the components.

Restrictions that cannot be ignored:
* any tick function with `AddPrerequisite` stays on the GameThread — the task waits
  for its predecessor, and this does not parallelize;
* the order relative to `TG_StartPhysics/TG_EndPhysics` is preserved
  (each group has its own barrier);
* components that write to `GUObjectArray` or touch `UWorld` are to be excluded.

### Step 3. The main gain per the profile: collision/overlap ≈29%

This is not ticks, this is queries — so instead of "spreading them out" it is cheaper
to remove their cost:

1. `TArray<FOverlapInfo>::AddUniqueImpl` — a linear search for every element,
   i.e., O(n²) per query result. Replacing it with `TInlineAllocator` + sorting
   or with a bitset yields an independent gain without parallelization.
2. Batching: one `GeomOverlapMulti` for a set of actors instead of N queries.
   The physics scenario must not be touched — it is not thread-safe, but grouping
   queries is safe.
3. Caching results between ticks for static geometry (the ARK world is static).

### Step 4. Name and object resolution ≈7%

`TSet<TPair<FName,FFoliageMeshInfo*>>::FindId` (1.7%) and `FName::FindOrAddNameEntry`
(1.8%) are called every frame with the same names. A cache
of `FName → pointer`, living longer than one frame, is needed; the same for
`FPostConstructInitializeProperties::InitProperties` and `StaticFindObject`.

### Step 5. Memory ≈6.5%

`FMallocBinned` (2.2%) plus memcpy/memset in MSVCR120 (4.3%) — a consequence
of the above: the queries constantly create and copy arrays. After step 3
this will shrink on its own; separately, it makes sense to raise the batch-allocation limits.

### Step 6. Replication and GC

`UActorChannel::ReplicateActor` must run in a fixed order on the GameThread,
but property serialization can be prepared on workers between ticks.
GC (`CollectGarbage`) is a candidate for incremental moving to a worker; on the server
the NoGC plugin is already installed.

### What cannot be achieved

"Fully" parallelizing the GameThread — moving the world tick onto several threads —
cannot be done without rewriting the engine: `UWorld::Tick` has global dependencies
of order (creation and accounting of UObject, level states, replication order,
the physics-group barriers). A realistic goal: remove the main mass
of work from the GameThread — and the profile shows that this is collision, name
resolution, and memory, not actor ticks at all.

---

## 6a. What was actually done and measured

All changes are implemented in the `TickProf` plugin and are enabled on the live server
with RCON commands, with the possibility of rollback.

Structure offsets were obtained from the PDB with the `fieldcheck.exe` utility (DIA):

| What | Offset |
|---|---|
| `FTickFunction` bitfield | dword @ +12, `bRunOnAnyThread` = bit 4 (0x10) |
| `FTickFunction::Prerequisites` | TArray @ +40 |
| `FTickFunction::TickGroup` | +8 |
| `FTickTaskSequencer::bAllowConcurrentTicks` | +560 |
| `AActor::PrimaryActorTick` | +40 |
| `UActorComponent::PrimaryComponentTick` | +48 |
| `ULevelBase::Actors` | TArray @ +136 |
| `UPrimitiveComponent::OverlappingComponents` | TArray @ +1312 |
| `UPrimitiveComponent::bGenerateOverlapEvents` | bit 10 in dword @ +500 |
| `UObjectBase::Class` | +16 |

### Tool 1: the `bAllowConcurrentTicks` patch

The instruction `C6 86 30 02 00 00 00` (`MOV byte ptr [RSI+0x230], 0`) in
`FTickTaskSequencer::StartFrame` (RVA `0x270B534`); the immediate operand is
the byte at RVA `0x270B53A`. Before the patch, all 7 bytes of the opcode are verified (`C6 86 disp32 imm8`) — on
any mismatch the patch is cancelled (during operation the check once saved the
server from patching at a wrong offset).

Commands: `TickProf.fix concurrent 1|0`, verification — `TickProf.verify`.

### Tool 2: marking tick functions

A walk over the actors of all 104 levels (`ULevelBase::Actors`) and over all components
with one engine call (`GetObjectsOfClass(UActorComponent::StaticClass)`),
then direct reading/writing of the bits. Modes: 0 clear, 1 all, 2 components of
`TG_DuringPhysics` without prerequisites, 3 `TG_PrePhysics`, 4 only the ticks
of actors, 5 all without prerequisites. There is a variant with a whitelist of classes from a file.

The census showed: **52 780 tick functions out of 276 292**, among them 5 281 with
prerequisites; ticking actors 424, ticking components 599.

### Tool 3: the Kismet canvas cache

2.5% of the profile went into `TSet<FName,FFoliageMeshInfo*>::FindId`, which is called by
`DoGetCanvasByName` / `GetCanvasByName` / `FindFunctionByName` — a lookup of the canvases
of Kismet graphs. On a dedicated server canvases are not drawn. A hook on
`Global.DoGetCanvasByName` (`UCanvas* __cdecl DoGetCanvasByName(FName)`) with
a table of 1024 slots, negative answers are cached too.

### Tool 4: trimming overloaded intersections

`UPrimitiveComponent::BeginComponentOverlap` for each event does
a linear `IsOverlappingComponent` and a linear `AddUnique` into
`OverlappingComponents` of the second component — i.e., O(n²) per component.
The command `TickProf.overlaptrim <threshold>` finds components with the number of records above the
threshold, clears the array, and removes `bGenerateOverlapEvents`.

### Results (external CPU of the GameThread, a 40 s window)

| Step | CPU, s/s | ticks/s | frame time |
|---|---|---|---|
| BASELINE | 0.746 | 14.2 | 70.7 ms |
| + the canvas cache | 0.605 | 28.3 | 35.3 ms |
| + the overlap trim (threshold 32) | 0.402 | 29.7 | 33.7 ms |
| + the overlap trim (threshold 8) | 0.254 | 29.8 | 33.6 ms |

In total for the two changes: **GameThread −66% CPU, throughput ×2.1**
(14.2 → 29.8 ticks/s). The trim removed 495 051 overlap records from 24 369
components; the trim at threshold 32 — 260 278 records from 787 components.

The number of ticks per second bottomed out at 29.8 — this is the standard limit
of `NetServerMaxTickRate`, i.e., after these changes the GameThread stopped being
the bottleneck, and further unloading of it without growing the tick rate is pointless.

---

## 6b. Analysis of the ARK dump and the second round of changes

The dump `C:\Dev\ARK_SE_code_dump\game_aquatica.c` is a decompilation (Binary Ninja)
of the ARK client binary, 2.3 million lines, **51 377 functions with real names**.
The server and game code coincide, so the dump was used as a source on the
algorithms of the ARK game code, while addresses and offsets were taken from the server PDB.

An index of names was built (`dump_index.json`), function bodies are extracted by name.

### What the dump analysis gave

**1. A second O(n²) site.** `UVictoryCore::ServerOctreeOverlapActorsBitMask`
(the server AI helper of "who can I attack") inside its loop over the results of
the octree search calls `AddUnique` **twice per result** — into the list of dinos and into
the list of structure containers. The same antipattern as in
`OverlappingComponents`, but in ARK-specific code.

**2. The root cause of 3.3% of the profile in the name lookup.** `UObject::ExecuteUbergraph`
— the dispatcher of blueprint graphs — calls
`UClass::FindFunctionByName(this->Class, (FName)0xe0, InIncludeSuper)`
with a **constant** FName on every tick of a blueprint object. The search walks
the chain of classes and the interfaces, doing a `TSet::FindId` at each level. The result for a pair
of (class, name) is unchanged — an ideal candidate for a cache.

**3. A systematic search** for all functions with ≥2 calls of `AddUniqueImpl` gave
38 functions; all the others — `GetLifetimeReplicatedProps` (once at registration of
a class) and `InitRHI` (rendering, not executed on the server). No new hot
O(n²) sites in the dump.

---

## 7. Top-10 decisions and their results

| # | Decision | Profile share | Result |
|---|---|---|---|
| 1 | The cache of `UClass::FindFunctionByName` | 3.3% | **works: −40% CPU, ticks 15.5 → 28.0/s** |
| 2 | `overlaptrim` threshold 2 | 8–12% | **works: −41% CPU, ticks → 29.9/s** |
| 3 | The cache of `UStruct::IsChildOf` | 1.35% | **works: −13% CPU** |
| 4 | The cache of `DoGetCanvasByName` | 2.3% | **works: −33% CPU, ticks → 29.7/s** |
| 5 | `overlaptrim` threshold 1 | 8–12% | works (stricter than threshold 2; the gain is almost that of the extreme mode) |
| 6 | `p.bTickPhysicsAsync 1` (the standard UE CVar) | — | **works: −12% CPU, does not hang the server** (tested separately, 90 s of observation) |
| 7 | Full disabling of overlap events (`overlapall 1`) | 8% | works, but **breaks gameplay** — do not apply |
| 8 | The patch of `bAllowConcurrentTicks` + `bRunOnAnyThread` | — | **does not work: it slows down** (33.4 → 42–46 ms/frame) |
| 9 | A cache of AI queries `ServerOctreeOverlapActorsBitMask` | ~1% | not implemented: a stub with out-parameters is needed |
| 10 | Suppressing `FPostConstructInitializeProperties` and other copies of properties | 2.6% | not implemented: the source of object creation was not found |

### Summary of measurements

Cycle 5 (one session, 35 s windows, the load decays on its own):

| State | GameThread CPU, s/s | ticks/s |
|---|---|---|
| base (canvas + trim 8) | 0.773 | 14.0 |
| + the cache of FindFunctionByName | 0.570 | 28.2 |
| + the overlap trim, threshold 2 | 0.422 | 29.5 |
| + the overlap trim, threshold 1 | 0.273 | 29.8 |
| + disabling all overlap events | 0.207 | 29.9 |

Cycle 6 (a clean start, changes accumulate, 35 s windows):

| State | CPU, s/s | ticks/s | gain |
|---|---|---|---|
| no changes | 0.871 | 15.5 | — |
| + the cache of FindFunctionByName | 0.523 | 28.0 | −40% |
| + the cache of IsChildOf | 0.457 | 29.0 | −13% |
| + the canvas cache | 0.305 | 29.7 | −33% |
| + the overlap trim, threshold 2 | 0.180 | 29.9 | −41% |
| **in total** | **−79%** | **15.5 → 29.9** | the ticks are pinned at the limit |

A clean start, 40 s windows (the "final" cycle): 0.688 → 0.328 s/s (−52%),
ticks 28.4 → 29.6.

**A methodology caveat.** Server load after `InitWorld` decays on its own
(streaming), so absolute CPU values fall even without changes. Therefore
the primary metric is taken to be the **number of ticks per second** (throughput)
and *sequential* increments within one run.

### The profile after all changes

| | before | after |
|---|---|---|
| samples idle (Sleep/Wait) | 33.0% | **92.6%** |
| samples in executing code | 40 301 | **3 385** |
| `AddUniqueImpl<FOverlapInfo>` | 8.25% | not in top-16 |
| `TSet<FName,FFoliageMeshInfo*>::FindId` | 2.26% | not in top-16 |

There remains only the tick core: `FTickTaskManager::RunTickGroup`, the dispatcher
`TGraphTask`, `APrimalDinoCharacter::Tick`, `FTimerManager` — that is, work
that cannot be removed without disabling game logic.

### On async ticks — a separate conclusion

The patch of `bAllowConcurrentTicks` (1 byte, RVA `0x270B53A`) works correctly:
the field reads as `1`, and the marking of `bRunOnAnyThread` is set for tens of thousands
of tick functions. But the measured effect is **negative**: frame time grew from
33.4 to 42.2 ms (the "components of TG_DuringPhysics" mode) and up to 45.9 ms (all tick functions
without prerequisites), and the number of ticks fell from 29.9 to 23.7/s. The GameThread CPU
nearly zeroed out — the work went to the workers, but the frame in total cost
more. This is exactly what the engine itself warns about in `TickTaskManager.cpp:611`:
"the parallel case doesn't ever seem to be faster, so it disabled by default".
Leaving the patch is possible only as a tool; applying it is not advised.

---

## 8. The final assessment of expediency

**To apply (safe, confirmed by measurements):**

| Change | Command | Why it is safe |
|---|---|---|
| The cache of `FindFunctionByName` | `TickProf.fncache 1` | the function set of a class is unchanged; negative answers are cached |
| The cache of `IsChildOf` | `TickProf.iscache 1` | the class hierarchy does not change on the server |
| The cache of `DoGetCanvasByName` | `TickProf.cachename 1` | the set of canvases does not change during a session |
| The overlap trim, threshold 2 | `TickProf.overlaptrim 2` | only components with an already-bloated overlap list are touched |
| Async physics | `p.bTickPhysicsAsync 1` | a standard engine CVar; tested separately — it does not hang the server |

A ready script: `python C:\Dev\_research\apply_recommended.py`
(rollback — `apply_recommended.py --revert`).

**Not to apply:**

| Change | Why |
|---|---|
| The patch of `bAllowConcurrentTicks` + `bRunOnAnyThread` | adds parallelism, but slows the server: 33.4 → 42–46 ms/frame |
| Full disabling of overlap events | breaks gameplay (traps, AI perception, triggers) for ~0.07 s/s |

**Overall conclusion.** Fully parallelizing the GameThread by moving ticks onto workers
is impossible in this build: the engine deliberately turned this path off, and our attempt
at enabling it confirmed its verdict. The real result is given by **not parallelism but
the removal of extra work**: four caches plus the overlap trim lower the CPU
of GameThread by 79% and raise throughput from 15.5 to 29.9 ticks/s —
bringing the server to its standard `NetServerMaxTickRate` limit. After that
the GameThread idles 92.6% of the time, and further CPU reduction is possible
only at the price of disabling game logic.

Separately about hanging: in one run the server stopped responding after
`p.bTickPhysicsAsync 1`. A repeated isolated check (a 30 s control,
60 s with async physics, a 30 s return) did not reproduce the hanging — the culprit
was the combination with the full disabling of overlap events on 139 745 components.
Conclusion: `p.bTickPhysicsAsync` by itself is safe, but combining it with
`overlapall` is not allowed.

---

## 9. Lifting the tick limit: dynamics

The standard limitation is `UNetDriver::NetServerMaxTickRate` (**int32**, offset 72 per the PDB;
decompilation: `MOV EDX,[RAX+0x48]` → integer `CMP/CMOVL` → `CVTDQ2PS`).
The Cvar `net.MaxNetTickRate` is **absent** in this build (the string is not in the binary), and
`UEngine::GetMaxTickRate` returns 0 and occupies itself only with `t.MaxFPS` and sleeping on a
hitch — it is not the limiter.

The command `TickProf.maxfps <N>` writes the field directly and re-sets it every
5 s (the driver may re-initialize). `TickProf.maxfps 0` returns the standard
behavior.

A measurement: a 30 s window, external CPU of the GameThread thread, the server in the settled regime.

| Limit | ticks/s | CPU, s/s | ms CPU per tick |
|---|---|---|---|
| 30 (standard) | 15.5* | 0.961 | 62.00 |
| 60 | 53.8 | 0.977 | 18.14 |
| 120 | 53.8 | 0.938 | 17.41 |
| 300 | 82.9 | 0.898 | 10.83 |
| 1000 | 110.2 | 0.672 | 6.10 |
| **200000** | **114.1** | **0.531** | **4.66** |

\* the first window landed on the world-streaming phase, so the time per tick is overstated.

**What the dynamics shows.** The ceiling is not 30, but **114 ticks/s**: this is the real
throughput of the GameThread in the settled regime, i.e., **4.66 ms
of work per one world tick**. The server at standard settings uses 0.53 of the 24 cores —
this is 2% of the machine.

The main practical conclusion: after the ceiling is lifted, the metric "ticks/s" stops
being useless and becomes a direct measure of the effect of any optimization. At a limit of 30, all
measurements hit the ceiling, and the changes are invisible; at a limit of 200000, every millisecond
per tick turns into a throughput gain. That is why all further
comparisons were made with the limit lifted.

A side effect for diagnostics: a lifted tick limit is useful by itself as
a stress test — at a limit of 200000 things invisible at 30 are exposed.

### 9a. A benchmark of optimizations at the lifted limit

The same server, 30 s windows, the caches enabled one by one.

| Variant | ticks/s | CPU, s/s | ms/tick | vs base |
|---|---|---|---|---|
| no optimizations | 117.7 | 0.328 | 2.79 | — |
| + the cache of FindFunctionByName | 116.1 | 0.484 | 4.17 | −1% |
| + the cache of IsChildOf | 116.2 | 0.297 | 2.55 | −1% |
| + the canvas cache | 112.3 | 0.375 | 3.34 | −5% |
| + the overlap trim | 116.0 | 0.297 | 2.56 | −1% |
| async physics | 115.1 | 0.359 | 3.12 | −2% |
| async ticks | 117.5 | 0.266 | 2.26 | −0% |

**A result nobody expected: not a single optimization raises
throughput.** *A caveat important for reading: this conclusion holds
only while the clamp at 120 (section 13) is active. Then the ticks stand at 112–118 at any
CPU, the t/s metric is blind, and only ms CPU/tick is informative. After the clamp is lifted, CPU
again becomes the bottleneck and the optimizations convert into speed.* The spread ±5% is noise. The CPU time per tick fluctuates
(2.26–4.17 ms), and the number of ticks per second stands at 112–118.

### 9b. Where the frame time actually goes

Phase timers (a 40 s window, 4465 frames, 111.6 ticks/s, 8.96 ms per frame):

| Phase | calls | total, ms | per frame | the share of the window |
|---|---|---|---|---|
| `FTickTaskManager::StartFrame` | 4465 | 13612.7 | **3.05 ms** | **34%** |
| `UWorld.RunTickGroup` | 40194 | 8036.5 | 1.80 ms | 20% |
| `UNetDriver.TickDispatch` | 4465 | 26.2 | 0.006 ms | 0.1% |
| `FTickTaskManager.EndFrame` | 4466 | 14.2 | 0.003 ms | 0% |
| `Global.CollectGarbage` | 0 | 0 | 0 | GC disabled by the NoGC plugin |

In total, the measured phases occupy **21.7 s out of 40 s**, i.e., 54% of the frame.
The remaining ~46% is outside our hooks: the engine main loop, the network code,
waiting on workers, and the sleep of the timing limiter.

**A conclusion changing the strategy.** The ceiling of ~117 ticks/s is not CPU: on it
only 2.5–4 ms of the 8.96 ms frame are spent. The rest is the wall (waiting and sleep).
Therefore lifting the tick limit did not give the expected gain from optimizations:
to raise throughput one needs to shorten **not CPU but waiting time**, and it is set by
sleep granularity and the barriers of the task graph.

Meanwhile, at the standard limit of 30 ticks/s all the optimizations remain meaningful:
there they lower the load by 79% and completely remove the GameThread from the bottlenecks
of profiling. The two conclusions do not contradict each other — they answer different
questions: "how much CPU is needed" and "what speed is achievable".

### 9c. What lies in the tick-task queue

A census of ticking components (`TickProf.tickclasses`):

```
ticking components = 264, unique classes = 2
   SkeletalMeshComponent        x132
   ShooterCharacterMovement    x132
```

Plus 424 ticking actors. In total about **700 tick functions** for the whole world.

A test of "is it about excess ticks": with the command `TickProf.tickoff` the tick
was turned off for 28 058 decorative components (StaticMesh 26 485, Landscape 1472,
Spline 101) — they were not registered and did not get into the queue, therefore
throughput did not change. Then the tick was turned off for the real
ticking components:

| State | ticks/s | CPU, s/s | ms/tick |
|---|---|---|---|
| 264 components tick | 119.3 | 0.422 | 3.54 |
| 14 components tick | 117.2 | 0.328 | **2.80** |

**Removing ~90% of ticking components lowers CPU per tick by 21% and gives not a
single additional tick per second.** This is the final confirmation:
the ceiling of ~117 ticks/s is set not by computation but by waiting.

Final phase timers (109 ticks/s, 9.2 ms per frame):

| Phase | per frame | the share of the frame |
|---|---|---|
| `FTickTaskManager::StartFrame` | **3.78 ms** | **41%** |
| `UWorld.RunTickGroup` | 1.41 ms | 15% |
| `UNetDriver.TickDispatch` | 0.002 ms | 0% |
| `FTickTaskManager.EndFrame` | 0.001 ms | 0% |
| `Global.CollectGarbage` | 0 | GC disabled |

`StartFrame` is the enqueueing of ~700 tasks over 104 levels, i.e.
**5 µs per task with 104 levels traversed**. Almost all levels are empty, but
are traversed every frame. To reduce this from outside is possible only by repacking
the levels (changing the map) or by editing `FTickTaskManager::StartFrame` itself in the engine —
from a plugin this is unattainable.

### 9d. New tools added based on the results

| Command | Purpose |
|---|---|
| `TickProf.maxfps <N>` / `.maxfps 0` | lifting and returning the tick limit |
| `TickProf.tickclasses` | a census of ticking components by classes |
| `TickProf.tickoff <substring>` | turning the tick off for components by class |
| `TickProf.cull <radius>` | skipping the tick of actors farther than the radius from players |
| `TickProf.cullstat` | a counter of skipped ticks |

`TickProf.cull` is built and disabled by default: on the test server there are no
players, the list of positions is empty and the culling does not trigger, so measuring
its effect here is impossible — a server with connected players is needed.


```powershell
# the PDB symbols (once, ~18 minutes)
cd C:\Dev\_research
& "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
cl /nologo /std:c++17 /EHsc /O2 /utf-8 /I"%ProgramFiles%\Microsoft Visual Studio\18\Community\DIA SDK\include" `
   pdbsym.cpp /link /LIBPATH:"%ProgramFiles%\Microsoft Visual Studio\18\Community\DIA SDK\lib\amd64" `
   diaguids.lib ole32.lib oleaut32.lib advapi32.lib /OUT:pdbsym.exe
$env:DIA_DLL = 'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\msdia140.dll'
.\pdbsym.exe 'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.pdb' v361.tsv
py -3.14 load_syms.py

# measurement on the live server
py -3.14 run_measure.py --sample-seconds 150
py -3.14 symbolize.py '<Plugins\TickProf\prof_*.bin>' --top 40 --exclude-idle
py -3.14 bymodule.py
```


---

## 10. Tests with a connected player

Connecting a player changes everything: the GameThread grew from 0.53 to 0.65 s/s in the calm
regime (and up to 3.34 s/s at the moment of player activity), and the profile restructured.

The profile with a player, without optimizations (a 90 s window, 45 817 samples):

| Function | Share |
|---|---|
| `TSet<TPair<FName,FFoliageMeshInfo*>>::FindId` | 2.70% |
| `APrimalDinoCharacter::Tick` | 2.69% |
| `APrimalCharacter::Tick` | 2.38% |
| `FName::InitInternal_FindOrAddNameEntry` | 2.10% |
| `FMallocBinned::FreeInternal` / `Malloc` | 3.08% |
| `FTickTaskManager::StartFrame` | 1.03% |
| `UEngine::TickFPSChart` | 0.47% |
| `IncrementalPurgeGarbage` | 0.52% |

In total by classes: `APrimalDinoCharacter` 6.4%, `APrimalCharacter` 4.7%,
`UCharacterMovementComponent` 3.5%, `AAIController` 1.7% — **about 17% is taken by the
AI of dinos**. The first item of the profile is the very lookup of functions by name,
which the cache of `FindFunctionByName` removes.

### Measurements (tickrate 30, 30 s windows)

| State | CPU, s/s | ms CPU per tick |
|---|---|---|
| without optimizations | 0.651 | 21.77 |
| + the caches (fn/iscache/canvas) | 0.604 | 20.23 (−7%) |
| + the overlap trim | 0.557 | 18.66 (−14%) |
| cull 50 km (deliberately without effect) | 0.573 | 19.18 |

### Distance-based tick culling — crashes the server

`TickProf.cull 15000` (skipping the tick of actors farther than 15 km from the player) after
a few seconds leads to the GameThread going to 1.7 s/s, and RCON
stops responding. To roll back by command is already impossible — a server restart is needed
(the player disconnects in the process).

The cause is understood: skipping `AActor::TickActor` breaks the engine invariants. For
an actor, the tick is not only "behavior" but also the servicing of state: deferred
operations, timers, updating of the replication state. Actors whose tick is skipped
remain visible to the tick system and the network checks, but stop
being serviced — and an inconsistency accumulates, which brings down the GameThread.

**The decision: the command is blocked.** Now `TickProf.cull` requires an explicit
`force` argument and by default refuses, printing a warning.
Applying it is not allowed.

### What was added based on the results

| Command | What it does | Status |
|---|---|---|
| `TickProf.nochart 1` | disables `UEngine::TickFPSChart` — the maintenance of FPS charts on the server | safe |
| `TickProf.cull` | distance-based tick culling | **blocked, crashes the server** |
| `TickProf.tickoff` | turning the tick off for components by class | works, but was not applied on the live server |

`TickProf.nochart` removes purely server work (0.47% of the profile): on the
dedicated server nobody can look at the frame charts, and `TickFPSChart` counts them
every frame.

### Dangerous operations found along the way

| Operation | Consequence |
|---|---|
| `plugins.unload TickProf` with active phase hooks | the server hangs (reproduced twice) |
| `TickProf.cull` | the GameThread hangs |
| `TickProf.actortickoff` | the GameThread hangs (mass disabling of actor ticks) |
| `TickProf.hook 5` (`FillLevelList`) | a hang on installing the hook |
| `TickProf.overlapall 1` | breaks game mechanics |
| `TickProf.fix concurrent 1` + `tickflags` | slows the frame 1.3-fold |
| unloading the plugin with a player connected | not tested, risky |


### The final run with only safe changes

30 s windows, tickrate 30, the server with a connected player. The measurements ran soon
after the start of the world, so the absolute values are overstated (streaming), but
the sequential increments within the run are comparable.

| State | CPU, s/s | ms CPU per tick | change |
|---|---|---|---|
| base | 0.995 | 88.30 | — |
| + the caches FindFunctionByName / IsChildOf / canvases | 0.859 | 49.87 | −43.5% |
| + the overlap trim (threshold 2) | 0.693 | 23.40 | −73.5% |
| + disabling the FPS statistics | 0.578 | 19.69 | **−77.7%** |

A control measurement in the settled regime with a player: **29.6 ticks/s,
0.722 s/s, 24.4 ms CPU per tick**, the server responds.

The profile after all changes: the top places — `APrimalCharacter` (5.8%),
`APrimalDinoCharacter` (4.5%), `UCharacterMovementComponent` (2.6%),
i.e., the AI of dinos. The lookup of functions by name, `AddUniqueImpl<FOverlapInfo>`
and name resolution have left the top completely.

### The final server configuration

Enabled and safe:

```
TickProf.fncache 1        the cache of UClass::FindFunctionByName
TickProf.iscache 1        the cache of UStruct::IsChildOf
TickProf.cachename 1      the cache of DoGetCanvasByName
TickProf.overlaptrim 2    trimming the bloated overlap lists
TickProf.nochart 1        disabling FPS chart maintenance
```

Not enabled: `cull` (crashes the server), `overlapall` (breaks gameplay),
the patch of async ticks (slows down), unloading the plugin (hangs the server).


---

## 11. Round P1: how many tasks are actually enqueued

### A summary of numbers for tick functions (one chain)

| Level | What it means | Value |
|---|---|---|
| 1 | actors and components that **have** a tick function (a census by objects) | 52 780 |
| 2 | entries in `AllEnabledTickFunctions` — what the manager actually walks | **3 510** |
| 3 | tasks actually enqueued per frame (the counter `QueueTickFunction`) | **223** |

The transition 52 780 → 3 510 happens on tick registration, and 3 510 → 223 on the filters
(fast-path, prerequisites, disabled). None of these quantities explains
2.7 ms of `StartFrame`: 3 510 × 72 ns = 0.25 ms, and 223 × 5.4 µs is absurdly much.


### What was assumed

The hypothesis of the brief: `FTickTaskManager::StartFrame` (~2.7–3.8 ms per frame) is the accounting
of ~52 780 registered tick functions, of which the majority belongs to stasised
dinosaurs; they are enqueued every frame and exit immediately. Hence an estimate of 72 ns per task — a plausible price of creating
a task node. Hence also the forecast: remove the dead functions → StartFrame falls
to ~0.1 ms, the ceiling grows from 117 to 250–400 ticks/s.

### What was measured

The counter of calls of `FTickFunction::QueueTickFunction` over a 30 s window:

```
tickq: frames=465 total tasks=255043 on average 223 per frame
```

**223 tasks per frame, and not ~52 780.** The hypothesis is refuted.

| Quantity | Value |
|---|---|
| tasks enqueued per frame | **223** |
| StartFrame | 2.748 ms/frame |
| the cost of one enqueue | 12.3 µs |

12.3 µs per enqueue — an absurd value for creating a task node
(about 0.07 µs was expected). That means the `StartFrame` time is **not explained by the number of tasks**.

### Why stasis gives nothing

Checked on the dump: `APrimalCharacter::Stasis` and `APrimalDinoCharacter::Stasis`
do not touch the tick function at all — their bodies consist of checks of flags
(`bDestroyOnStasis`, `bUseBPPreventStasis`, `BPPreventStasis`). The stasis mechanism
is implemented as a buff (`APrimalBuff_Grappled`, `APrimalBuff::Stasis`),
and not as removal of a tick. There is no separate field `bIsStasised` in `APrimalCharacter`
— there are only `LastUnstasisTime`, `NotifyStasis`, `NotifyUnstasis`.

Practical meaning: even if one could identify the stasised, there is nothing to remove them
from `AllEnabledTickFunctions` — they are not there anyway. Their tick functions
run, but do almost nothing, and there are 223 tasks for the whole world.

### The conclusion on P2

**P2 in its original form is cancelled: there is nothing to fix.** The hypothesis "the dispatcher
enumerates ~52k dead tick functions" was not confirmed by the number of tasks,
nor by the stasis path. P2 could be reformulated as "reduce
the 223 tasks", but that is a ceiling of 12 µs per task — and 2.7 ms of the frame at 223
tasks means the main cost lies outside enqueueing.

### P1 take-three: linearity not verified — the command crashes the server

The attempt to stop the ticks of 379 ticking dinosaurs out of 212 tasks led to the same thing
as `cull`: the GameThread hung, RCON stopped responding, recovery only
by a restart. Mass disabling of the ticks of actors is unsafe for this build
regardless of the way — by skipping in a hook or by clearing a flag.

The conclusion is the same as for `cull`: **reducing the number of ticking actors on a live
server must not be done.** The command `TickProf.actortickoff` is blocked the same way as
`cull` (it requires `force` and refuses by default).

### The summary on the brief

| Item | Result |
|---|---|
| P1 "how many tasks are in the queue" | **223 tasks per frame**, and not ~52 780 — the hypothesis refuted |
| P1 take-two | the own code of `StartFrame` — 0.6% of samples, the rest in the callees |
| P1 take-three | infeasible: mass disabling of ticks crashes the server |
| P2 "remove stasis from the queue" | **cancelled**: there is nothing to remove, and stasis does not touch the tick functions |
| P3 "decode the wall" | partially: `UpdateTimeAndHandleMaxTickRate` does not sleep (returns 0), `UNetDriver::TickFlush` contains no sleep — the limiter must be sought further |
| P4 "the fncache line" | a defect fixed: the cache was single-lot, with more live pairs than the table it evicted keys; a probe at 8 slots and counters of hits added |
| P5 "AI under the player" | not started |
| P6 "hygiene" | not started |

**The key thought of the brief was not confirmed.** We did not run into the accounting of ~52k dead
tick functions: there are only 223 of them in the queue. A different hypothesis is needed next — either
explain the 12–28 µs per enqueueing (which is implausible), or acknowledge
that the measurement of `StartFrame` includes time outside the enqueueing.


---

## 12. Unraveling "the wall": NtDelayExecution and the clamp of 120

### The top of the profile from the same window where the 41% was measured

A 40 s window, 20 170 samples, 111.6 ticks/s (without `--exclude-idle`):

| Share | Address | What it is |
|---|---|---|
| **24.37%** | `ntdll+0x15F484` | **`NtDelayExecution`** — the thread sleeps |
| 4.14% | `ntdll+0x15EE84` | `NtWaitForSingleObject` |
| 1.76% | `APrimalDinoCharacter::Tick` | the AI of dinos |
| 1.62% | `ntdll+0x15F124` | `NtQueryInformationProcess` |
| 1.56% | `ntdll+0x15EFC4` | `NtSetEvent` |
| 1.40% | `ntdll+0x15F4C4` | `NtQuerySystemInformation` |
| 1.21% | `ntdll+0x15EEE4` | `NtDeviceIoControlFile` |
| 0.57% | `FTickTaskManager::StartFrame` | the dispatcher's own code |

Total: external modules 53.8%, our image 45.9%, unknown 0.2%.

**The third exit from the brief: there is no hole in symbolization.** The "hidden 40%" —
these are not callees of StartFrame, but `NtDelayExecution`: the GameThread lies
in the sleep syscall for a quarter of the time. The own code of StartFrame is 0.57% — and it is honest.

### The ceiling found: the clamp of 120 in `UGameEngine::GetMaxTickRate`

`UEngine::UpdateTimeAndHandleMaxTickRate` calls the getter **virtually**
(a vtable slot +0x290). The override `UGameEngine::GetMaxTickRate`
(RVA `0x253B1C0`, 287 bytes) is fully decompiled:

```c
int32_t MaxTickRate = *(int32_t *)(Driver + 0x48);      // NetServerMaxTickRate
int32_t Clamped = (MaxTickRate < 10) ? 10
               : ((MaxTickRate < 0x78) ? MaxTickRate : 0x78);
Rate = (float)Clamped;
```

`0x78` = **120**. The limit is clamped into the range **[10; 120]**, and the request "200000"
turns into 120. The observed ceiling of 114–117 ticks/s suspiciously precisely
runs into this number.

The instruction (RVA `0x253B26E`): `B9 78 00 00 00` = `MOV ECX, 0x78`, then
`CMP EDX,ECX` / `CMOVL ECX,EDX`. The patch raises the upper bound to 100000
(`A0 86 01 00`), the lower one (10) is not touched — the clamp semantics are preserved.

The command: `TickProf.fixclamp 1` / `TickProf.fixclamp 0`, with opcode checking.

This is the first found cause of the ceiling that can be removed by a patch, and it
converts all the CPU-optimization work into throughput: if
the ceiling moves above 120, our −77% CPU will start converting into ticks.

### The scan hypothesis is closed for good

Two independent measurements:

| What | Value |
|---|---|
| entries in `AllEnabledTickFunctions` over 104 levels | **3510** |
| tasks enqueued per frame | **223** |

Neither 3510 × 72 ns (0.25 ms), nor 223 × 5.4 µs gives 2.7 ms. The scan is not guilty.

A note on the tool: the census gave garbage for FastPath/AllDisabled/
NewlySpawned — their offsets in `FTickTaskLevel` are read incorrectly (needs
a recheck via `fieldcheck`). This does not affect the output: `AllEnabledTickFunctions`
was read correctly (3510).

### Dangerous hooks found in this round

| Hook | What it does |
|---|---|
| `FTickTaskManager.FillLevelList` | **the installation hangs the server** (the signature unknown, the argument registers are lost) |
| `FTickTaskLevel.QueueAllTicks` | not tested — probably the same cause |
| `FTickTaskLevel.QueueNewlySpawned` | not tested |

They were removed from the hook table; the dispatcher is measured with the `StartFrame` window flag
plus a stack sampler inside that window (`prof_*.sfstack`, the analyzer
`sfstack.py`).


### 12a. The measurement of lifting the clamp (DRAFT, requires a control)

> **Status: not to be published.** The windows ran back-to-back on a load decaying after
> the start, so the gain is inseparable from the streaming cooldown. The proof
> of the clamp is now indirect, but strong: over the entire round no settled
> run exceeded 120 t/s (114.1 / 117.7 / 119.3), plus the decompilation with the constant
> `0x78`. There is no direct measurement of "clamp lifted → sustainably >120 t/s" yet —
> see the control A/B in section 13.

One run, 30 s windows, the limit `NetServerMaxTickRate` = 200000 in all rows:

| State | ticks/s | CPU, s/s | ms CPU per tick |
|---|---|---|---|
| the standard clamp (120) | 32.2 | 0.969 | 30.12 |
| **the clamp raised to 100000** | **64.8** | 0.974 | 15.02 |
| **the clamp lifted + the caches + the trim** | **85.0** | 0.958 | **11.28** |

| Effect | Value |
|---|---|
| lifting the clamp | **+102%** — but on a decaying load, the figure is invalid |
| plus our optimizations on top of the lifted clamp | +31%, also requiring a control |

The mechanism is the one all the work of the previous rounds predicts: the CPU of the thread
remains ~0.96 s/s (the thread is saturated), but the cost of a tick falls 30 → 15 → 11.3 ms,
and the same CPU budget manages to serve 2.6× more ticks.

**Why this was not visible before.** While the clamp of 120 holds the ceiling, the GameThread
idles, and any CPU saving goes into the idle and does not turn into speed.
The optimizations collected over two rounds (−77% CPU on the standard 30 ticks) were
**locked by the engine** and could not manifest in anything except the load on the
process. Lifting the clamp is not an optimization but the removal of a lock, and only
after it does the CPU work convert into ticks.

A caveat: the absolute values in this run are understated by the streaming of the world
(the first window — 9.9 t/s at the standard limit of 30), so the relative sequence
within the run matters, not the absolute numbers. The large jumps
(×2 and ×1.3) are above the startup noise.

### The practical meaning

`TickProf.fixclamp 1` + `TickProf.maxfps <N>` — the only found pair,
which moves the ceiling of throughput. Next, a selection of
`NetServerMaxTickRate` is needed: at 200000 the server runs into the CPU (~85 t/s), i.e.,
after the clamp is lifted the bottleneck is again real, and it can be moved
by CPU optimizations — which is what we saw (+31%).

The patch operation survives a restart only as long as the process is not rebooted:
the change is in memory, not written to disk.

---

## 13. The control A/B of the clamp (P8) — CONFIRMED

### The method

Settled regime: the server started, 600 s of streaming cooldown, a 60 s warm-up,
then 30 s windows with the alternating clamp on → off → on → off. The limit
`NetServerMaxTickRate` = 200000 in all windows. All optimizations enabled.

### The result

| Window | clamp | ticks/s | CPU, s/s | ms CPU/tick | **thread load** |
|---|---|---|---|---|---|
| warm-up | 120 | 118.6 | 0.333 | 2.81 | 33% |
| **A0** | **120** | **114.9** | 0.328 | 2.85 | **33%** |
| **B0** | **lifted** | **158.4** | 0.958 | 6.05 | 96% |
| **A1** | **120** | **116.1** | 0.833 | 7.18 | 83% |
| **B1** | **lifted** | **284.5** | 0.865 | 3.04 | 86% |

| Result | Value |
|---|---|
| the average of A (the clamp 120) | **115.5 t/s** |
| the average of B (the clamp lifted) | **221.4 t/s** |
| the gain | **×1.9** |
| a sustained exceeding of 120 | **YES** |

### The deciding argument

The window **A0: 114.9 ticks/s at a thread load of 33%**. Two thirds of the core are free —
so the limitation is not the CPU, and it cannot be. This is exactly the form of
proof missing in the first measurement. The reverse window A1 at
83% load gives the same 116.1 ticks/s: with a change of load 2.5-fold the speed
does not move — it is pressed by the clamp.

With the B windows the relation is inverse: the speed follows the load (158 at 96% CPU,
284 at 86% — the spread of the tick cost from the state of the world), i.e., after the clamp
is lifted the bottleneck is real.

### The sweep of the limit with the clamp lifted — the real ceiling

| `NetServerMaxTickRate` | ticks/s | CPU | load |
|---|---|---|---|
| 150 | 142.6 | 0.771 | 77% |
| 200 | 180.8 | 0.911 | 91% |
| 400 | **204.0** | 0.953 | 95% |

The ceiling of the server on one thread is **~204 ticks/s**, and it is CPU-limited.
Growing further is possible only by lowering the cost of a tick.

### The status of the earlier figure

**The "+102%" is retracted.** That measurement ran on a load decaying after the start:
the windows 32 → 65 t/s went within 90 seconds after the start of the world, streaming was still cooling.
The correct figure by the control A/B is **×1.9** (115.5 → 221.4 t/s), and it
rests on the alternation of windows in the settled regime, not on a trend.

The conclusion "the clamp of 120 blocks all the previous CPU work" was **confirmed**,
but it grew numerically: not +102%, but almost ×2.

### The production arithmetic (with no speculation made up)

With a player: 29.6 t/s at 24.4 ms CPU/tick. At 100% occupancy the ceiling would be
about 41 t/s. That is, **in combat the clamp of 120 does not bind at all** — the value
of the changes there is measured by lowering ms/tick (from 88 to 20–24, almost twice),
and `fixclamp` is relevant for the empty and stress regime. This changes the priority of deployment:
first lower the cost of a tick, then raise the limit.


### P7: the status — the tool is ready, the culprit not found

What was done: `exp_idle.py` (sampling the RIP of the thread + parsing the stack to a depth
of 48 words) and `sfstack.py` (parsing the stack samples from the `StartFrame` window).

What is known: `NtDelayExecution` — 24.4% of samples, `NtWaitForSingleObject` — 4.1%.
The own share of `StartFrame` — 0.57%.

What failed: the external sampler never hit the waiting state.
Two causes in the tool, both found and one fixed:
* `GetModuleHandleW` was given a Python string instead of `c_wchar_p` and returned NULL;
* for a thread blocked in a syscall, `GetThreadContext` gives RIP in the kernel
  (0xFFFFF8xx), not in ntdll — a filter over the ntdll range discarded such samples.

After the fixes there are still zero hits, even though the profile shows sleep.
That means it was the state capture that failed (the hand-written `CONTEXT` structure
in Python does not match the Windows layout), not the classification. The working path —
to take `stackdump.py` as is and add a loop with deep stack parsing to it.

**P7 remains open.** It is still the largest unclaimed prize:
about a quarter of the GameThread time lies idle, and if it is not the regular pacing-sleep
(and at a limit of 120 and a frame of 8.96 ms it should not trigger at a budget of
8.33 ms), then the source gives up to ×1.5–2 of throughput for free.

### P12: the clamp patch became persistent

`TickProf.fixclamp` is now applied automatically at plugin load
(with opcode checks). It is disabled by the file `tickprof_noclamp.txt` next
to the plugin or by the command `TickProf.fixclamp 0`.

### The state of the server after the round

The clamp returned to 120, `NetServerMaxTickRate` = 0 (standard, 30 t/s),
optimizations enabled, async ticks disabled. GameThread 0.13 s/s (3.3%).
