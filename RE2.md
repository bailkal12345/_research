# RE2.md — results of stage A (offline RE, the bench was not touched)

Image: `ShooterGameServer.exe` v361.7 (ARK: Survival Evolved), Win64 x64,
image base `0x140000000`. Symbols — `C:\Dev\_research\v361.sqlite` (PDB v361.7).
Decompilation and xref — Ghidra, program `/v361_ShooterGameServer.exe`.

Every claim is annotated with an RVA or symbol name. Whatever could not be determined
is listed explicitly in each section. Nothing is speculated.

## Summary: what changed in the understanding of the tasks

| Directive task | Outcome |
|---|---|
| A1 IsA | the hook covers **only 73%** of sites: 1360 calls + 510 inlined copies. `iscache` covers **not a single** `IsA` site — zero overlap |
| A2 VictoryCore | **the O(n²) hypothesis about `ServerOctreeOverlapActors` is REFUTED**. The real O(n²) is in `BeginComponentOverlap` |
| A3 Inventory | `GetItemTemplateQuantity` is O(N) with no cache, but there are only 5 per-tick paths and they are all narrow |
| A4 SaveWorld | **the freeze is serialization into memory, not a flush to disk**. Disk writes are already asynchronous, on a TaskGraph worker |
| A5 BP machine | the tracer's hook point is determined: `ProcessInternal` |
| A6 Report hygiene | done; **the reviewer's claim about the starting save is refuted by the data** |
| A7 ARCH | `ARCH.md` created |

---

## A1. UObjectBaseUtility::IsA

### Symbols

| Symbol | RVA | Size |
|---|---|---|
| `UObjectBaseUtility::IsA` | `0x01FCDAB0` | 36 |
| `UStruct::IsChildOf` | `0x001DCC80` | 25 |
| `UClass::SetSuperStruct` | `0x01F84F30` | 43 |
| `UStruct::SetSuperStruct` | `0x01F811D0` | 5 |
| `UClass::ImplementsInterface` | `0x01F85530` | — |

`IsA_Static` and `IsA_InContainer` are **absent** from the image — no such API exists in UE4.5.

### Implementation

A walk of the `SuperStruct` chain, field `+0x30`. Full body — 13 instructions:

```asm
01FCDAB0  mov  rax,[rcx+0x10]      ; rax = this->Class
01FCDAB4  test rax,rax
01FCDAB7  jz   false
01FCDAC0  cmp  rax,rdx             ; Class == TargetClass?
01FCDAC3  jz   true
01FCDAC5  mov  rax,[rax+0x30]      ; Class->SuperStruct
01FCDAC9  test rax,rax
01FCDACC  jnz  loop
```

No property access by pointer. **There is a single early exit** — on `Class == nullptr`;
on `TargetClass == nullptr` there is no early exit (the loop will walk the whole chain).

Hierarchy depth across 1587 native classes: **maximum 8 levels**, 5–6 for real
ARK classes. That is 25–40 loops per call, with dependent loads.

### Call sites and the main conclusion

| Target | Ghidra xref | byte scan `E8 rel32` |
|---|---|---|
| `IsA` `0x01FCDAB0` | 1360 | 1360 |
| `IsChildOf` `0x001DCC80` | 3411 | 3411 |

**But the compiler inlined the loop into function bodies.** A regex on the loop signature
gives 906 inlined copies: 510 copies of `IsA` (with the `Class` load) and 394 copies of
`IsChildOf`.

**Outcome: the real number of `IsA` sites = 1360 + 510 = 1870.** A function hook covers 73%.
The remaining 27% will bypass it.

**`IsChildOf` is not called inside `IsA`** — proven at the machine-code level:
the body of `IsA` contains zero `CALL` instructions. These are two independent copies of
the same loop. Consequently, **the `iscache` cache covers not a single `IsA` site**.

### iscache2 sketch

| Aspect | Decision |
|---|---|
| Key | `(UClass* Source, UClass* Target)`, 16 B; Source = `Obj->Class` (`+0x10`) |
| Structure | open addressing `2^16` slots × 24 B = 1.5 MB in `.data`, no runtime allocations |
| Hash | `(src>>4)*0x9E3779B1 ^ (tgt>>4)*0x85EBCA77`, index `& 0xFFFF` |
| **Invalidation** | the hook on `UClass::SetSuperStruct` (`0x01F84F30`) bumps the epoch. This is the **only** place that changes the chain |
| Negative result | **safe in this build**: interfaces live in a separate array (`ImplementsInterface`, `GetInterfaceAddress`) and are **not part** of `SuperChain` — verified in code, not from documentation |
| Threads | write 24 B atomically (otherwise torn reads → **silent misclassification of objects**); reads without locks |
| Dangling pointers after GC | medium risk; treated either with a `~UObjectBase` hook or by storing a `GUObjectArray` index instead of a pointer |
| Hot reload | **impossible** on the server: `SupportsDynamicReloading` — stubs `0x001B5330` (3 bytes), no BP compiler in the image |
| **Risk class** | **LOW–MEDIUM** |

**Recommendation A1: a hook on `0x01FCDAB0` gives 73% coverage and almost certainly
less than 73% of the win.** Full coverage requires patching the loop itself, which means
writing code into hot `.text` paths. Expected gain is low for both reasons.

### Not found

1. The `iscache` modification mechanism was not verified — the plugin's sources were not
   found; the claim comes from the old `REPORT.md`.
2. **The "−13%" figure from iscache is not confirmed.** In `REPORT.md:709` the combined
   effect of three caches is given as "−7%", with no breakdown per iscache.
3. The actual runtime call frequency of `IsA` was not measured — 1870 sites is static data,
   not a profile.
4. Not verified whether `IsA` is called from TaskGraph worker threads (the 510 inlined
   copies are not attributed per thread).
5. Not verified whether interfaces are added to the SuperChain when BP classes are loaded
   from pak at runtime.
6. The hierarchy depth of BP classes was not counted — they are not in the exe.
7. 424 classes were not recovered because of `_NoRegister`-decls (does not affect the
   maximum depth).
8. Indirect `IsA` calls through a function pointer were not detected (only `E8`/`E9` were scanned).
9. The cost of the cache table was not measured: the size `2^16` was chosen theoretically.

---

## A2. UVictoryCore::ServerOctreeOverlapActors

### Symbols

| Symbol | RVA | Size |
|---|---|---|
| `UVictoryCore::ServerOctreeOverlapActors` | `0x012871E0` | 1945 |
| `...ServerOctreeOverlapActorsBitMask` | `0x01287980` | 1706 |
| `...ServerOctreeOverlapActorsClass` | `0x01288030` | 2080 |
| `...ServerOctreeOverlapActorsClassBitMask` | `0x01288850` | 1841 |
| `UVictoryCore::FindNearbyCharactersOfClass` | `0x01288F90` | 1354 |
| `APrimalStructureTurret::GetAmmoNearby` | `0x00A2A950` | 3267 |
| `TArray<FOverlapInfo>::AddUniqueImpl` | `0x024E3050` | 138 |
| `UPrimitiveComponent::BeginComponentOverlap` | `0x02644000` | 719 |

### MAIN RESULT: the O(n²) hypothesis is REFUTED

`AddUniqueImpl` (`0x024E3050`) is **not called from any** of the four
`ServerOctreeOverlapActors*` functions. Inside there is only `Emplace` (`0x001CFE60`) —
amortized O(1). Verified in three ways: the callee list of all four functions, full
decompilation of `0x012871E0`, and `get_xrefs_to(0x024E3050)` — the **only** call in
the entire image, at address `0x0264418D`.

**The real O(n²)** is in `UPrimitiveComponent::BeginComponentOverlap` (`0x02644000`):

```c
TArray<FOverlapInfo>::Emplace<FOverlapInfo>(&this->OverlappingComponents, p1);   // asymmetry
FOverlapInfo Tmp(&local_b8, this, -1);
TArray<FOverlapInfo>::AddUniqueImpl<FOverlapInfo>(&OtherComp->OverlappingComponents, &Tmp);  // 0x0264418D
```

`AddUniqueImpl` is a linear scan with **stride 0x98** (152 bytes per `FOverlapInfo`).
Note the asymmetry: toward itself `Emplace` (duplicates allowed), toward the partner
`AddUnique` (a scan). It is exactly this pairing that bloats O(n²).

### Call periodicity

`APrimalStructureTurret::Tick` → `GetAmmoNearby` (`0x00A3A129`) — **every tick**,
there is no timer between the flag check and the call. Inside `OctreeType=0xF`,
`bForce=true`.

Full call-site list of `ServerOctreeOverlapActors` — 21, the significant ones:
`CountCharactersResolvingGroundLocationInSphere` `0x012B0185`, `GetAmmoNearby`
`0x00A2AE89`, `Ballista::GetAmmoNearby` `0x00A58FAB`, `APrimalCharacter::TakeDamage`
`0x009454FE` (on every damage event), `PingNearbyPlayers` `0x00EC789B`,
`ServerDownloadDino` `0x00E700B7`, the rest — 10 AOE cheat-command calls.

### The result is not stored in an actor field

It is a local `TArray<AActor*>` (sret), consumed by the caller in place:
`GetAmmoNearby` does a linear pass over the return value; `TakeDamage` — a pass
within the radius of the hit point; `ServerDownloadDino` — a count check
(`CMP EAX,0x3`).

### Optimization sketch

| Option | Point | Risk |
|---|---|---|
| deduplication on the octree output | hook the call site `0x00A3A129` | **medium** — a one-tick miss on the target |
| **patch `BeginComponentOverlap`** | `0x0264418D`, replace the scan with a `TSet`-side structure keyed on `(CachedCompPtr, Item)` | **medium → high**: requires a synchronized change of `EndComponentOverlap` `0x026442D0`, otherwise "stuck" overlaps |
| patch `ServerOctreeOverlapActors` | `0x012871E0` | **low**, but the gain is close to zero |

**Final risk class: MEDIUM**, if only the hot path `GetAmmoNearby`
and/or `BeginComponentOverlap` is touched. Do not touch the `TakeDamage` and `exec*`
paths — there the risk is HIGH.

### Mandatory whitelist (RVAs confirmed in the PDB)

| What | RVA | Size |
|---|---|---|
| `ABaseBoxTrigger::BPOnTriggerBeginOverlap` | `0x01368850` | 199 |
| `ABaseBoxTrigger::BPOnTriggerEndOverlap` | `0x01368920` | 111 |
| `ABaseBoxTrigger::OnTriggerBeginOverlap` | `0x001EF970` | 91 |
| `ABaseBoxTrigger::IsCharacterTouchingTrigger` | `0x001EF930` | 63 |
| `AHazardTrigger_Slide::UpdateActive` | `0x002CD490` | 5046 |
| `APrimalStructureBearTrap::TakeDamage` | `0x009814D0` | 655 |
| `AActor::IsPrimalStructureTurret` | `0x001B5330` | 3 |
| `APrimalStructureTurret::GetAmmoNearby` | `0x00A2A950` | 3267 |
| `APrimalStructureTurretBallista::GetAmmoNearby` | `0x00A58C20` | 1934 |
| `APrimalCharacter::CanIgnoreImmobilizationTrap` | `0x004C4DB0` | 524 |
| `APrimalProjectileGrapplingHook::Tick` | `0x00887220` | 36 |
| `UPrimitiveComponent::BeginComponentOverlap` | `0x02644000` | 719 |
| `UPrimitiveComponent::EndComponentOverlap` | `0x026442D0` | 682 |

The current `tickprof_overlap_keep.txt` is insufficient: `Trigger` and `Turret` as
substrings are too broad; `ABaseBoxTrigger`/`AHazardTrigger_Slide`/`APrimalStructureBearTrap`
are not covered explicitly.

### Not found

1. `AddUnique` inside `ServerOctreeOverlapActors*` — **not found** (this is the refutation).
2. Calls of `ServerOctreeOverlapActorsClassBitMask` from C++ — none, only the exec-thunk `0x0168A199`.
3. Direct C++ calls of `UpdateOverlaps` — none: 39 xrefs, all DATA (exec-thunk tables).
4. No timer between the flag and `GetAmmoNearby` — the frequency is every tick.
5. `APrimalStructureTrap::*` — 0 PDB matches; the real trap classes are listed above.
6. An actor field for the result — not found; the result is only a stack `TArray` + an out-parameter in Blueprint.
7. Hooks on `ServerOctreeOverlapActors*` in the installed ArkApi plugins — 0 matches.
8. The order of `EServerOctreeGroup` ↔ index in the mask table — only the **mask values** are reliably established, not the names.

---

## A3. Inventory: GetItemTemplateQuantity / IsValidForCrafting

### Symbols

| Symbol | RVA | Size |
|---|---|---|
| `UPrimalInventoryComponent::GetItemTemplateQuantity` | `0x777E70` | 1305 |
| `UPrimalInventoryComponent::TickComponent` | `0x77B3C0` | 794 |
| `UPrimalInventoryComponent::TickCraftQueue` | `0x77B6E0` | 936 |
| `UPrimalItem::IsValidForCrafting` | `0x81D4B0` | 1665 |
| `UPrimalItem::TickCraftingItem` | `0x80B760` | 5227 |
| `UPrimalItem::MeetBlueprintCraftingRequirements` | `0x7F8710` | 4057 |
| `UPrimalItem::AddToInventory` | `0x7AC9A0` | 12407 |
| `UPrimalItem::RemoveItemFromInventory` | `0x7AFCA0` | 9604 |
| `UPrimalItem::SetQuantity` | `0x80D4C0` | 8562 |
| `UPrimalItem::IncrementItemQuantity` | `0x7F4D60` | 8631 |

### What is scanned

`GetItemTemplateQuantity` is an **O(N)** linear pass over `InventoryItems`
(a `TArray` at offset `+0x118` **in the component**, not in the actor). There is no cache
or memoization: no global accesses, no state fields.

There are no nested loops inside — the nesting appears at the callers:
`MeetBlueprintCraftingRequirements`, `MeetRepairingRequirements`, `HasResources`,
`TestMeetsCraftingRequirementsPercent` — all **O(R·N)**.

The bottleneck is not the pass but **the cost of filtering one item**: per item
it is 1–2× `StaticClass()`, 1× `IsChildOf()`, 1× `IsA()` and optionally the
virtual `IsValidForCrafting` (1665 B, containing up to 2 entries into the Blueprint VM).

### Per-tick or per-event — CRITICAL

**Not "for every actor every tick".** There are exactly five per-tick paths, all narrow:

1. `TickComponent` → `TickCraftQueue` → `MeetRepairingRequirements` → 2× `GetItemTemplateQuantity`.
   Gate: an active repair queue.
2. `TickComponent` → `TickCraftingItem` (virtual `0x338`) → up to 3× `MeetBlueprintCraftingRequirements`.
   Gate: for every **actively crafting** blueprint — every tick.
3. `APrimalStructureTurret::Tick` → `GetAmmoNearby` → 2× `GetItemTemplateQuantity` — every turret every tick.
4. `APrimalStructureTurretBallista::Tick` → `CanFire`/`CanReload` → `GetAmmoAmount` — every ballista every tick.
5. `APrimalStructurePlacer::Tick` — only while the player drags a placement ghost.

The remaining 69 call sites are per-event (add/remove, inventory opening, RPC).

`IsValidForCrafting` is called only when `bCheckValidForCrafting == true`; only
`MeetBlueprintCraftingRequirements` passes that. The rest pass `false`.

### Index sketch

| Aspect | Decision |
|---|---|
| Where to store | a side-map **`UPrimalInventoryComponent*` → index** (not per actor, not global) |
| Structure | `ByClass: TMap<UClass*, FInvBucket>` keyed on **exact** class + `MatchCache` (derived) |
| Why buckets, not one sum | otherwise `bRequireExactClassMatch` (`bOverrideExactClassCraftingRequirement`) and `bIgnoreBlueprints` (`bIsBlueprint` — instance flags) cannot be counted correctly |
| **Invalidation points** | exactly **4**: `AddToInventory` `0x7AC9A0`, `RemoveItemFromInventory` `0x7AFCA0`, `SetQuantity` `0x80D4C0`, `IncrementItemQuantity` `0x7F4D60` + rebuild at `LoadedFromSaveGame` `0x781330` |
| What can be cached | buckets **without** accounting for `IsValidForCrafting`; predicates are applied to specific items on the spot |
| What **must not** be cached | a sum "only valid for crafting": it depends on durability, `IsBroken`, `OwnerInventory`, the parent structure and the Blueprint — **none of these mutate `InventoryItems`** |

**Risk class: LOW** for the buckets-without-`IsValidForCrafting` variant;
**HIGH** when attempting to aggregate "the sum of only valid ones".

What breaks with a stale cache: understated → `MeetRepairingRequirements()==false` →
the entry is **removed from `ItemCraftQueueEntries`** — a silent loss of the repair queue;
overstated → `ServerCraftItem` will consume resources that do not exist → dupe/desync.

### Gain estimate

The full A3 cluster = **275 samples = 6.45% of executed code** of Genesis.
With an 80% reduction — about **0.72% wall**. Real, but not the main reserve:
Blueprint VM (22.8%) and `IsA` (6.66%) are larger.

### Not found

1. `UPrimalInventoryComponent::HasItem`, `GetInventoryItems`, `GetItemQuantity`,
   `GetCraftingCost` — no symbols.
2. Direct calls of `IsValidForCrafting` — **0**; only vtable slot `0x3A8` and the exec-thunk.
3. The distribution of calls across the 74 call sites was not measured (the profiler
   gives self-time per function).
4. The actual N and R on Genesis were not measured offline.
5. Which Blueprint graphs call `execGetItemTemplateQuantity` `0x179BFD0` — bytecode in
   `.uasset` cannot be read offline.
6. The value of `bUseCraftQueue` in the CDO was not checked.
7. The share of `IsA` attributable specifically to `GetItemTemplateQuantity` was not
   isolated offline (2 call sites out of 1360).

---

## A4. SaveWorld: where the 3.9–4.3 s go

### MAIN RESULT: this is SERIALIZATION, not a disk flush

| Symbol | RVA | Size |
|---|---|---|
| `UShooterCheatManager::execSaveWorld` | `0x016CDF70` | 26 |
| `UShooterCheatManager::SaveWorld` | `0x00BC95F0` | 183 |
| `AShooterGameMode::SaveWorld(bool)` | `0x00CDC220` | 4291 |
| `UWorld::SaveToFile` | `0x02755CC0` | 8788 |
| `WorldSerializedObject::SerializeHeaders` | `0x01FD8340` | 2082 |
| `WorldSerializedObject::SerializeObjectData` | `0x01FD8FA0` | 380 |
| `UStruct::SerializeTaggedProperties` | `0x01F7E900` | 8666 |
| `UProperty::ShouldSerializeValue` | `0x01FB2000` | 444 |
| `UWorld::SaveToFile`: `AllowSaving` call | `0x0275738F` | — |
| **`FWriteFileTask::GetDesiredThread`** | `0x00D66650` | 6 |
| `FWriteFileTask::DoTask` | `0x02746940` | 614 |
| `FFileHelper::SaveArraysToFile` | `0x01F1E200` | 159 |

**Disk writing is already offloaded to a separate TaskGraph thread.**
`FWriteFileTask::GetDesiredThread()` decompiles to `{ return AnyNormalThreadNormalTask; }`.
The file handle is opened **only** in `FWriteFileTask::DoTask`, i.e. in the worker.
`FlushFileBuffers` is **absent** from the PDB; `FArchiveFileWriterGeneric::Flush`
`0x01EBD280` has 0 callers — it is a user-buffer flush, not a disk flush.

RCON `saveworld` passes `bForceWaitOnSaveToComplete = 0`, and there are no
LocalPlayers on a dedicated server → the function returns right after dispatching the task.
So the measured 3.9–4.3 s is exactly the serialization of objects into memory.

**Caveat:** with `bForceWaitOnSaveToComplete = true` (shutdown) or when a
LocalPlayer is present, the wait loop `FGraphEvent::IsComplete` `0x00CDD195` +
`Sleep(0.01)` `0x00CDD1C2` executes, and then the measured time **includes**
the disk write. This branch needs a separate measurement.

### ARK has NO incremental saving

The chain `UPackage::SavePackage` / `FSavePackage` / `FArchiveState` is **entirely absent**
from the PDB. The globals `GSavePackageFileName` `0x04937D08` and `SavePackageState`
`0x0491C6A8` have 0 live xrefs. The world save uses **ARK's own format**, not UE packaging.

The switch `-newsaveformat` → `GCurrentWorldSaveVersion` `0x048B2AE4`: 9 by default,
11 with the flag. This is **a version change, not a delta**.

### Hook points

| Option | Point | Gain | Risk | Verdict |
|---|---|---|---|---|
| batched saving by actors | `0x00CDC220` | ~0 | **high** | **no** |
| asynchronous writing | `0x02746940`, dispatch `0x02757DFF` | **already in stock** | low | polishing only |
| byte cache per actors | the `AllowSaving` filter, call `0x0275738F` | up to ~50% | **high** | only with a fallback |

**Red line (batched):** `WorldSerializedObject::SerializedObjectsStack` — global,
built in pass 1 and consumed in pass 2; gameplay mutates it between frames. The format is
flat, headers are linked by `DataOffset`; the loader
`UObjectSerializer::DeSerializeObject` `0x003C2C90` walks that offset.
Corruption = **an unreadable `.ark` after a restart**. Skipping an actor in `.ark`
**silently** loses objects — without a crash, which is the worst outcome.

**Red line (byte cache):** `SerializeObjectData` `0x01FD8FA0` already has an internal
dedup, but only within **one** file. There is no "reference to previous file" format.
Correct dirty-tracking is impossible: mutations come from native code, Blueprint,
inventory and physics.

### Not found

1. `UWorld::SaveWorld`, `UPackage::SavePackage`, `FSavePackage`, `FMemoryWriter`,
   `FlushFileBuffers` — no symbols.
2. RCON/cvar/GameUserSettings for an incremental save — not found (no strings in the binary).
3. The virtual `vtable+0x9F8`, called at `0x027573AB` — name undetermined; in **all** 208
   vtable slots the value is the same `0x01401BCBB0` (3 bytes, `ret`), no overlaps — an empty
   extension point.
4. `UPrimalItem::IsValidForCrafting` — 0 direct callers. `GetItemTemplateQuantity` — 51
   direct callers, **none in the save path**. So the 2.86%+2.52% of the profile come from a
   Blueprint hook (probably `SHOOTERGAME_BPPreSerializeSaveGame` `0x04934050`) via
   `ProcessEvent`. The native owner is **not identified**.
5. What exactly is written into each of the 5–6 `FWriteFileTaskInfo` buffers — not verified
   by name.
6. Which call initiates the autosave — `SaveWorld` has 0 native xrefs; the trigger is Blueprint.
7. How long the disk write itself takes — no direct measurement.

---

## A5. BP machine and tracer

### Symbols and layout

| What | RVA |
|---|---|
| `UObject::ProcessInternal` | `0x01FC0270` (344 B) |
| `UObject::ProcessContextOpcode` | `0x01FC1FA0` |
| `UObject::CallFunction` | `0x01FBFEF0` |
| `UFunction::Invoke` | `0x01F867C0` |
| `FFrame::FFrame` | `0x01FA57E0` |
| `GNatives` | `0x0491C6B0` |
| `GScriptStack` | `0x04937F00` |
| `NamePoolData` | `0x0498A1C8` |

**`FFrame` layout:** `Node +0x10`, `Object +0x18`, `Code +0x20`, `Locals +0x28`,
`MostRecentProperty +0x30`, `MostRecentPropertyAddress +0x38`, `OutParms +0x78`.
`Locals` is **not** a `TArray<uint8*>`, but a flat buffer; addressing is
`Locals[Prop->Offset_Internal]`, `UProperty+0x4C = Offset_Internal`.

**`UFunction` layout:** `Name +0x18`, `Outer +0x20`, `ParmsSize +0x40`,
`Script +0x48`, `FunctionFlags +0x90`, `Func +0xA8`.

### Key fact

```asm
; UFunction::Bind, 0x141F86D6D
TEST dword ptr [R9+0x90], 0x400   ; FUNC_Native
JNZ   ...
LEA   RAX,[0x141FC0270]           ; &UObject::ProcessInternal
MOV   qword ptr [R9+0xA8],RAX    ; UFunction->Func
```

**For any scripted `UFunction`, field `Func == &ProcessInternal`.**

### Dispatcher

`GNatives[256]` (2048 bytes), index = opcode byte, `CALL [RDI+RAX*8]`.
Populated by 63 static initializers, which first fill all 256 slots with
`execUndefined`. The jump to the next instruction is made by the dispatcher itself
(`Code++` **before** the call). 68 `exec*` symbols lie in one block
`0x01FC1050…0x01FC36B6`.

**There are no arithmetic opcodes in this build at all** — slots `0x45,0x46,0x47,0x49`
are empty.

### Tracer hook point

| Criterion | `ProcessInternal` | `Invoke` |
|---|---|---|
| Frequency | once per entry into a scripted UFunction | once per **any** call, including native |
| Coverage | a **superset** | does not see the direct `CallFunction→ProcessInternal` |
| Data | `RDX = FFrame*`, `FFrame->Node` known | `RCX = UFunction` |
| Call sites | **none** (indirect call via `Func`) | present (2) |

**Choice: hook the body of `ProcessInternal` (`0x01FC0270`).** This is exactly the needed
granularity at minimal frequency. Hooking into `GNatives` or each `exec*` is impossible —
the frequency is an order of magnitude higher.

### Tracer sketch

| Aspect | Decision |
|---|---|
| Point | detour of the first 12 bytes of `ProcessInternal` |
| What we log | **only** the full `UFunction` name (`+0x18`, FName) and a counter. No arguments logged |
| Hot path | 10–12 instructions, ~5–7 cycles; `FName→str` **never** in the hot path, resolution at flush |
| Buffering | fixed ring buffer in `.data`; write index `__declspec(thread)` — no atomics; counters — a separate table |
| Flush | a separate thread every N seconds; raw records + string resolution |
| Threads | the hot path only reads; cold path (miss) — `SRWLOCK`; TLS static, not `TlsAlloc` |
| Reentrancy | the hook **calls no UE API** — no recursion risk from the log |
| Kill switch | `bptrace 0|1`, default **0**; when off, patch bytes are **not installed at all** (literally zero influence) |
| Overhead estimate | +0.07…0.33% of frame — **3…15 times cheaper than the 1.1% budget**. Calculated, not measured |
| **Risk class** | **MEDIUM** — entry into the hottest function; an error manifests immediately |

**Mandatory pre-deployment check:** `ENDBR64` is **absent** from the first instructions
of `ProcessInternal`. With CET enabled, a CET-compatible
trampoline `mov r11, imm64; jmp r11` is needed (12 bytes, does not touch the stack).

### Not found

1. The actual per-second call count of `ProcessInternal`/`Invoke` was **not measured** —
   the overhead percentages are calculated.
2. The state of `GFullStackTrace` and the cost of `GScriptStack` were not checked.
3. The full size of `FFrame` is not confirmed (assumed `0x90`).
4. `UFunction+0x20 = Outer` — an **inference** from the Super-chain walk, not a type from
   the PDB.
5. The runtime contents of `GNatives` were not checked — the map was recovered from static
   initializers.
6. Behavior under CET/shadow stack not checked.
7. The reason for the absence of arithmetic opcodes is **unknown**; the conclusion
   "arithmetic is not supported" cannot be drawn.

---

## A6. Report hygiene

Done; all edits applied to `REPORT-Genesis.md`, `REPORT-TheIsland.md`,
`REPORT-Fjordur.md`. A separate section A6 in each file.

**Key result of the check:** a completed initial save before P0/P1 **existed on none
of the maps**. Evidence — `*_AntiCorruptionBackup.bak` is created **during world
loading**, while the `.ark` itself is rewritten only on an actual save:

| Map | start | `.bak` | `.ark` first rewritten |
|---|---|---|---|
| Genesis | 00:32:48 | 00:37:54 (during loading) | 01:21:38 |
| TheIsland | 01:33:43 | 01:37:56 (during loading) | 02:07 |
| Fjordur | 02:19:19 | 02:23:59 (during loading) | 02:38 |

**The reviewer's claim that "Genesis waited for the end of the initial save" is not
confirmed by the data.**

## A7. ARCH.md

A separate document created: 5 active optimizations, 4 new patches with risk classes,
configuration, built-in monitoring with the `CONTAMINATED` flag, the specification of
the `perf.selftest` command and the deployment order.
