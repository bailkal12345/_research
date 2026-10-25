# RE.md - offline reverse engineering (merged)

Image: `ShooterGameServer.exe` v361.7 (ARK: Survival Evolved), Win64 x64, image base `0x140000000`. Symbols: `C:\Dev\_research\v361.sqlite` (PDB v361.7), tables `fn`/`sym`. Decompilation/xrefs: Ghidra 7.0.0, program `/v361_ShooterGameServer.exe`. Every claim annotated with an RVA or symbol; whatever was not determined is explicitly listed.

## Timeline

- 2026-10-19: join-path RE in Ghidra on `v361_ShooterGame.exe` (client) - motivated by the bot auto-connect blocker found in the player slot (see REPORT-PLAYER.md); result in "RE session" below. Only the analysis was done.
- Stage A (offline RE, bench untouched): tasks A1-A7; results recorded in the "RE2" section; deep dives A3 (inventory) and A5 (BP machine/tracer) in their own sections.
- A1 IsA / A2 VictoryCore overlap / A4 SaveWorld / A6 report hygiene / A7 ARCH.md - all offline notes and verdicts below.
- 2026-10-25: ETW capture of a real RCON SaveWorld on Genesis (capture1) - the 4.8 s freeze decomposed into serialization (~3.8 s CPU) + SavedArks directory enumeration (~1.0 s IO); result in "A8" below. A4 refined accordingly (3.9-4.3 s figure was serialization-only).

## RE2 (stage A results)

### Summary: what changed in the understanding of the tasks

| Task | Outcome |
|---|---|
| A1 IsA | hook covers **only 73%** of sites: 1360 calls + 510 inlined copies. `iscache` covers **not a single** `IsA` site - zero overlap |
| A2 VictoryCore | **the O(n^2) hypothesis about `ServerOctreeOverlapActors` is REFUTED**; the real O(n^2) is in `BeginComponentOverlap` |
| A3 Inventory | `GetItemTemplateQuantity` is O(N) with no cache, but only 5 per-tick paths, all narrow - see "A3 inventory" |
| A4 SaveWorld | **the freeze is serialization into memory, not a disk flush**; disk writes already asynchronous on a TaskGraph worker |
| A5 BP machine | tracer hook point determined: `ProcessInternal` - see "A5 (RE2 section)" |
| A6 Report hygiene | done; **the reviewer's claim about the starting save is refuted by the data** |
| A7 ARCH | `ARCH.md` created |

### A1. UObjectBaseUtility::IsA

Symbols: `UObjectBaseUtility::IsA` 0x01FCDAB0 (36 B), `UStruct::IsChildOf` 0x001DCC80 (25 B), `UClass::SetSuperStruct` 0x01F84F30 (43 B), `UStruct::SetSuperStruct` 0x01F811D0 (5 B), `UClass::ImplementsInterface` 0x01F85530. `IsA_Static` and `IsA_InContainer` are **absent** from the image - no such API in UE4.5.

Implementation: a walk of the `SuperStruct` chain, field **+0x30**. Full body 13 instructions (`mov rax,[rcx+0x10]` Class; `cmp rax,rdx`; `mov rax,[rax+0x30]`; loop). **Single early exit** on `Class == nullptr`; on `TargetClass == nullptr` the loop walks the whole chain. No property access by pointer. Hierarchy depth across 1587 native classes: **maximum 8 levels**, 5-6 for real ARK classes = 25-40 loops per call with dependent loads.

Call sites: Ghidra xref vs `E8 rel32` byte scan agree - IsA 1360 = 1360; IsChildOf 3411 = 3411. The compiler inlined the loop: regex on the loop signature gives 906 inlined copies - 510 of IsA (with the Class load) + 394 of IsChildOf. **Real IsA sites = 1360 + 510 = 1870; a function hook covers 73%, the remaining 27% bypass it.** `IsChildOf` is NOT called inside `IsA` (zero CALL instructions in the body - proven at machine level); two independent copies of the same loop => **the `iscache` cache covers not a single IsA site**.

iscache2 sketch: key `(UClass* Source, UClass* Target)` 16 B (Source = Obj->Class +0x10); open addressing 2^16 slots x 24 B = 1.5 MB in `.data`, no runtime allocations; hash `(src>>4)*0x9E3779B1 ^ (tgt>>4)*0x85EBCA77`, index `& 0xFFFF`; **invalidation: hook on `UClass::SetSuperStruct` (0x01F84F30) bumps the epoch - the only place that changes the chain**; negative result **safe in this build** (interfaces live in a separate array - `ImplementsInterface`, `GetInterfaceAddress` - not part of SuperChain, verified in code); writes of 24 B must be atomic (otherwise torn reads -> silent misclassification), reads without locks; dangling pointers after GC: medium risk (treat with a `~UObjectBase` hook or store a `GUObjectArray` index instead of a pointer); hot reload **impossible** on the server (`SupportsDynamicReloading` stub 0x001B5330, 3 B; no BP compiler in the image). **Risk class: LOW-MEDIUM.**

**Recommendation A1: a hook on 0x01FCDAB0 gives 73% coverage and almost certainly less than 73% of the win.** Full coverage requires patching the loop itself (writing code into hot `.text`). Expected gain low for both reasons.

Not found/unchecked: iscache modification mechanism not verified (plugin sources not found; claim from old REPORT.md); **the "-13%" figure of iscache is not confirmed** (REPORT.md:709 gives combined effect of three caches as "-7%", no per-cache breakdown); runtime IsA frequency not measured (1870 sites are static data); whether IsA runs on TaskGraph workers not verified (510 inlined copies not attributed per thread); whether interfaces are added to the SuperChain when BP classes load from pak at runtime; BP-class hierarchy depth not counted (not in the exe); 424 classes not recovered because of `_NoRegister`-decls (does not affect max depth); indirect IsA calls through function pointers not detected (only `E8`/`E9` scanned); cache-table cost not measured (2^16 chosen theoretically).

### A2. UVictoryCore::ServerOctreeOverlapActors

Symbols: `UVictoryCore::ServerOctreeOverlapActors` 0x012871E0 (1945), `...ActorsBitMask` 0x01287980 (1706), `...ActorsClass` 0x01288030 (2080), `...ActorsClassBitMask` 0x01288850 (1841), `UVictoryCore::FindNearbyCharactersOfClass` 0x01288F90 (1354), `APrimalStructureTurret::GetAmmoNearby` 0x00A2A950 (3267), `TArray<FOverlapInfo>::AddUniqueImpl` 0x024E3050 (138), `UPrimitiveComponent::BeginComponentOverlap` 0x02644000 (719).

**MAIN RESULT: the O(n^2) hypothesis is REFUTED.** `AddUniqueImpl` (0x024E3050) is **not called from any** of the four `ServerOctreeOverlapActors*` functions; inside there is only `Emplace` (0x001CFE60) - amortized O(1). Verified three ways: callee lists of all four functions, full decompilation of 0x012871E0, and `get_xrefs_to(0x024E3050)` - the **only** call in the entire image at 0x0264418D.

**The real O(n^2) is in `UPrimitiveComponent::BeginComponentOverlap` (0x02644000):** `Emplace<FOverlapInfo>(&this->OverlappingComponents, p1)` (asymmetry - duplicates allowed) paired with `AddUniqueImpl<FOverlapInfo>(&OtherComp->OverlappingComponents, &Tmp)` at 0x0264418D - a linear scan with **stride 0x98** (152 bytes per FOverlapInfo). Exactly this pairing bloats O(n^2).

Periodicity: `APrimalStructureTurret::Tick` -> `GetAmmoNearby` (call 0x00A3A129) - **every tick**, no timer between the flag check and the call; inside `OctreeType=0xF`, `bForce=true`. `ServerOctreeOverlapActors` call sites: 21 total; significant: `CountCharactersResolvingGroundLocationInSphere` 0x012B0185, `GetAmmoNearby` 0x00A2AE89, `Ballista::GetAmmoNearby` 0x00A58FAB, `APrimalCharacter::TakeDamage` 0x009454FE (on every damage event), `PingNearbyPlayers` 0x00EC789B, `ServerDownloadDino` 0x00E700B7; the other 10 are AOE cheat-command calls. The result is a local `TArray<AActor*>` (sret), not stored in an actor field: GetAmmoNearby linear-passes the return; TakeDamage passes within the hit radius; ServerDownloadDino checks the count (`CMP EAX,0x3`).

Optimization sketch: deduplicate octree output by hooking call site 0x00A3A129 - **medium** (one-tick miss on the target); **patch `BeginComponentOverlap`** at 0x0264418D (replace the scan with a TSet-side structure keyed on `(CachedCompPtr, Item)`) - **medium -> high**: requires a synchronized change of `EndComponentOverlap` 0x026442D0, otherwise "stuck" overlaps; patch `ServerOctreeOverlapActors` 0x012871E0 - **low** but the gain is close to zero. **Final risk: MEDIUM** if only the hot paths (GetAmmoNearby and/or BeginComponentOverlap) are touched; do NOT touch the `TakeDamage` and `exec*` paths - there the risk is HIGH.

Mandatory whitelist (RVAs confirmed in the PDB): `ABaseBoxTrigger::BPOnTriggerBeginOverlap` 0x01368850 (199), `BPOnTriggerEndOverlap` 0x01368920 (111), `OnTriggerBeginOverlap` 0x001EF970 (91), `IsCharacterTouchingTrigger` 0x001EF930 (63), `AHazardTrigger_Slide::UpdateActive` 0x002CD490 (5046), `APrimalStructureBearTrap::TakeDamage` 0x009814D0 (655), `AActor::IsPrimalStructureTurret` 0x001B5330 (3), `APrimalStructureTurret::GetAmmoNearby` 0x00A2A950 (3267), `APrimalStructureTurretBallista::GetAmmoNearby` 0x00A58C20 (1934), `APrimalCharacter::CanIgnoreImmobilizationTrap` 0x004C4DB0 (524), `APrimalProjectileGrapplingHook::Tick` 0x00887220 (36), `UPrimitiveComponent::BeginComponentOverlap` 0x02644000 (719), `EndComponentOverlap` 0x026442D0 (682). The current `tickprof_overlap_keep.txt` is insufficient: `Trigger`/`Turret` as substrings too broad; `ABaseBoxTrigger`/`AHazardTrigger_Slide`/`APrimalStructureBearTrap` not covered explicitly.

Not found: `AddUnique` inside `ServerOctreeOverlapActors*` (the refutation itself); C++ calls of `ServerOctreeOverlapActorsClassBitMask` - none, only the exec-thunk 0x0168A199; direct C++ calls of `UpdateOverlaps` - none (39 xrefs, all DATA/exec-thunk tables); no timer between flag and GetAmmoNearby (every tick); `APrimalStructureTrap::*` - 0 PDB matches (real trap classes listed above); an actor field for the result - none; hooks on `ServerOctreeOverlapActors*` in the installed ArkApi plugins - 0 matches; the order of `EServerOctreeGroup` <-> mask index - only the mask values are reliably established, not the names.

### A4. SaveWorld: where the 3.9-4.3 s go

**MAIN RESULT: SERIALIZATION, not a disk flush.** Symbols: `UShooterCheatManager::execSaveWorld` 0x016CDF70 (26), `UShooterCheatManager::SaveWorld` 0x00BC95F0 (183), `AShooterGameMode::SaveWorld(bool)` 0x00CDC220 (4291), `UWorld::SaveToFile` 0x02755CC0 (8788, `AllowSaving` call at 0x0275738F), `WorldSerializedObject::SerializeHeaders` 0x01FD8340 (2082), `SerializeObjectData` 0x01FD8FA0 (380), `UStruct::SerializeTaggedProperties` 0x01F7E900 (8666), `UProperty::ShouldSerializeValue` 0x01FB2000 (444), `FWriteFileTask::GetDesiredThread` 0x00D66650 (6), `FWriteFileTask::DoTask` 0x02746940 (614), `FFileHelper::SaveArraysToFile` 0x01F1E200 (159).

Disk writing is already offloaded: `FWriteFileTask::GetDesiredThread()` decompiles to `{ return AnyNormalThreadNormalTask; }`; the file handle is opened **only** in `DoTask`, i.e. in the worker. `FlushFileBuffers` is absent from the PDB; `FArchiveFileWriterGeneric::Flush` 0x01EBD280 has 0 callers (user-buffer flush, not disk flush). RCON `saveworld` passes `bForceWaitOnSaveToComplete = 0`, and there are no LocalPlayers on a dedicated server -> the function returns right after dispatching the task. So the measured 3.9-4.3 s is exactly serialization of objects into memory. **Caveat:** with `bForceWaitOnSaveToComplete = true` (shutdown) or a LocalPlayer present, the wait loop `FGraphEvent::IsComplete` 0x00CDD195 + `Sleep(0.01)` 0x00CDD1C2 executes and the time **including** the disk write is measured; that branch needs a separate measurement.

**ARK has NO incremental saving.** The chain `UPackage::SavePackage` / `FSavePackage` / `FArchiveState` is entirely absent from the PDB; globals `GSavePackageFileName` 0x04937D08 and `SavePackageState` 0x0491C6A8 have 0 live xrefs. The world save uses ARK's own format, not UE packaging. Switch `-newsaveformat` -> `GCurrentWorldSaveVersion` 0x048B2AE4: 9 by default, 11 with the flag (a version change, not a delta).

Hook points: batched saving by actors at 0x00CDC220 - gain ~0, **high** risk, **no**; asynchronous writing - **already in stock** (0x02746940, dispatch 0x02757DFF), low risk, polishing only; byte cache per actors at the `AllowSaving` filter (call 0x0275738F) - up to ~50%, **high**, only with a fallback. **Red line (batched):** `WorldSerializedObject::SerializedObjectsStack` is a global built in pass 1 and consumed in pass 2; gameplay mutates it between frames; the format is flat, headers linked by `DataOffset`, loader `UObjectSerializer::DeSerializeObject` 0x003C2C90 walks that offset. Corruption = **an unreadable `.ark` after a restart**; skipping an actor in `.ark` **silently** loses objects without a crash - the worst outcome. **Red line (byte cache):** `SerializeObjectData` 0x01FD8FA0 already dedups within **one** file only; there is no "reference to previous file" format; correct dirty-tracking is impossible - mutations come from native code, Blueprint, inventory and physics.

Not found: `UWorld::SaveWorld`, `UPackage::SavePackage`, `FSavePackage`, `FMemoryWriter`, `FlushFileBuffers` - no symbols; RCON/cvar/GameUserSettings for an incremental save - none (no strings in the binary); the virtual `vtable+0x9F8` called at 0x027573AB - name undetermined, and in **all** 208 vtable slots the value is the same 0x01401BCBB0 (3 bytes, `ret`), no overlaps - an empty extension point; `UPrimalItem::IsValidForCrafting` - 0 direct callers and `GetItemTemplateQuantity` - 51 direct callers, **none in the save path**, so the 2.86%+2.52% of the profile come from a Blueprint hook (probably `SHOOTERGAME_BPPreSerializeSaveGame` 0x04934050) via `ProcessEvent`; the native owner is not identified; what is written into each of the 5-6 `FWriteFileTaskInfo` buffers - not verified by name; which call initiates the autosave (SaveWorld has 0 native xrefs; the trigger is Blueprint); how long the disk write itself takes - no direct measurement.

### A6. Report hygiene

Done; all edits applied to REPORT-Genesis.md, REPORT-TheIsland.md, REPORT-Fjordur.md (each with a separate A6 section). **Key result:** a completed initial save before P0/P1 existed on none of the maps (see the full tables in REPORT-Genesis.md). Evidence: `*_AntiCorruptionBackup.bak` is created during world loading while the `.ark` is rewritten only on an actual save - Genesis 00:32:48 start / .bak 00:37:54 / .ark first 01:21:38; TheIsland 01:33:43 / 01:37:56 / 02:07; Fjordur 02:19:19 / 02:23:59 / 02:38. **The reviewer's claim that "Genesis waited for the end of the initial save" is not confirmed by the data.**

### A7. ARCH.md

Created separately: 5 active optimizations, 4 new patches with risk classes, configuration, built-in monitoring with the `CONTAMINATED` flag, the specification of the `perf.selftest` command and the deployment order.

### A8. SaveWorld freeze decomposition (capture1, Genesis)

**MAIN RESULT: the ~4.8 s freeze = ~3.8 s serialization (CPU-bound, ~1 core) + ~1.0 s of SavedArks directory enumeration (IO-blocked).** Evidence: ETW `capture1_merged.etl` (WPR CPU -filemode, merged via xperf), t = seconds of trace; RCON `saveworld` issued at t≈31.7; main-thread tid17180.

**Timeline** (per-second stack reports `ps_*_SaveWorld/IterateDirectory.html`, root-hit counts from TblP):

| t (s) | SaveWorld stacks | IterateDirectory stacks | phase |
|---|---|---|---|
| 33 | 0 | 0 | no save yet (RCON auth+polling delay ~2.5 s - not a freeze) |
| 34 | 611 | 0 | serialization |
| 35 | 998 | 0 | serialization (peak) |
| 36 | 995 | 0 | serialization |
| 37 | 803 | 0 | serialization |
| 38 | 604 | **529 (88%)** | directory enumeration; whole second only ~255 ms CPU -> ~75% blocked in IO |
| 39+ | 0 | 0 | save finished at t≈39; tail CPU 39-46 ≈ baseline (~130 ms/s) |

Freeze window: t≈34.2-39.0 (~4.8 s). Refines A4: the old 3.9-4.3 s figure was the serialization part only; the invariant "file write is already async" holds (FWriteFileTask: 127 hits process-wide on workers, only 16 on tid17180).

**CPU hotspots of the serialization spike 34-38** (exclusive hits, tid17180, `tid17180_spike.html`; ShooterGameServer module = 3.08 s of the 3.22 s window): `UProperty::ShouldSerializeValue` 691 / 19.82%, `TMemoryWriter<32>::Serialize` 553 / 15.86%, `UStruct::SerializeTaggedProperties` 291 excl (2796 incl), `FSaveFileObjectWriter::operator<<` 184+62, `UBoolProperty::Identical` 103, `TArray<...,TSizedDefaultAllocator<32>>::AddUninitialized` 102, `TProperty_WithEqualityAndSerializer<...>::Identical` family ~6%, `ShouldSerializeTransform` 50, `APrimalCharacter::AllowSaving` 50, `StaticFindObjectFastInternalThreadSafe` 46, `FArchive::IsSaveGame` 42. Consistent with A4 (serialization into memory, not disk).

**NEW FINDING: `SerializeForSaveFile` enumerates the whole save directory on every save.** Decompilation of `AShooterGameMode::SerializeForSaveFile` (0x140D2C4C0, save branch `ArIsLoading==false`): `GetSaveDirectoryName(Profile)` (0x140D1FF40) + `FPaths::GameSavedDir` -> `IFileManager::FindFiles("*.arkproftemp")` (vtable+0x68) -> loop of `Delete` (vtable+0x30) over the results. Proven stack chain (529 samples in t=38): `RCONClientConnection::ProcessRCONPacket -> AShooterGameMode::SaveWorld -> UWorld::SaveToFile -> SerializeForSaveFile -> FWindowsPlatformFile::IterateDirectory -> FFileManagerGeneric::FindFiles -> FindNextFileW -> NtQueryDirectoryFileEx -> NtfsQueryDirectory -> NtfsWaitOnIo`. Enumerated directory = `ShooterGame/Saved/SavedArks` (the only directory under `Saved/` with a meaningful file count; Config=10, Logs=17).

**Cost breakdown of the IO second:** SavedArks holds **1395 files / 3.15 GB** (1116 `.arktributetribe`, 250 `.arkprofile`, 23 `.ark`, 6 `.bak`) and **zero `*.arkproftemp`** -> the Delete loop runs 0 times; the cost is the pure scan. Blocking evidence: `NtfsWaitOnIo` 501 of 529 stacks (372 under `NtfsQueryDirectory`, 147 under `FindNextIndexEntry2`), `NtfsFsdRead`/`IoPageReadEx` 512. Hot local benchmark (`os.scandir`, 20 runs) = **7.2 ms/scan** -> the in-save ~1 s is cold NTFS index + ~500 blocking waits, not file count arithmetic. Storage: QEMU QEMU HARDDISK SSD SAS 400 GB, NTFS healthy, 31 GB free, no compression/sparse (wof.sys in stacks is only a filter callback; `fsutil wof` unsupported on this build).

**Levers inside the allowed area (storage environment + world volume):** (1) shrink SavedArks file count - archive stale `.arktributetribe`/`.arkprofile`, drop old `.ark`/`.bak` (scan is O(entries), cold-index dominated); (2) scheduled directory index warm-up (a periodic scan keeps the index hot: 7 ms hot vs ~1 s cold per save); (3) serialization spike stays ~3.8 s - reducible only via world volume (actor/property count), not via storage.

Artifacts: `etl/capture1_merged.etl`, `etl/cap1_sec_cpu.csv`, `etl/cap1_phase_timeline.csv`, `etl/tid17180_{phA,phB,phC,spike,save}.html`, `etl/ps_*_{SaveWorld,IterateDirectory}.html`, `etl/phC_{ntfs,fltp}.html`; parsers `etl/{parse_excl,parse_ps,butterfly_tree,butterfly_ctx}.py`.

## A3 inventory: GetItemTemplateQuantity / IsValidForCrafting

Profile: `...\ArkApi\Plugins\TickProf\prof_298529359.bin` (30 463 samples).

### Symbols

Targets:

| Symbol | RVA | Size | VA | Note |
|---|---|---|---|---|
| `UPrimalInventoryComponent::GetItemTemplateQuantity` | 0x777E70 | 1305 | 0x140777E70 | pure function, 74 static call sites |
| `UPrimalInventoryComponent::execGetItemTemplateQuantity` | 0x179BFD0 | 914 | 0x14179BFD0 | Blueprint-thunk (74th call site) |
| `Z_Construct_UFunction_UPrimalInventoryComponent_GetItemTemplateQuantity` | 0x152C4A0 | 2379 | 0x14152C4A0 | source of names/parameter order |
| `UPrimalItem::IsValidForCrafting` | 0x81D4B0 | 1665 | 0x14081D4B0 | **virtual**, vtable slot 0x3A8 |
| `UPrimalItem::execIsValidForCrafting` | 0x17AA660 | 47 | 0x1417AA660 | `MOV RAX,[RCX]; CALL [RAX+0x3A8]` @ +0x21 |
| `UPrimalItem::BPIsValidForCrafting` | 0x1366680 | 110 | 0x141366680 | -> `ProcessEvent` (vtable +0x1E0) |
| `Z_Construct_UFunction_UPrimalItem_IsValidForCrafting` | 0x149D210 | 658 | | |
| `UPrimalItem::GetItemQuantity` | 0x7F2F70 | 17 | 0x1407F2F70 | virtual, slot 0x2E8; `return this+0x648` |

Related `UPrimalInventoryComponent::*` (RVA/size/role): `GetItemTemplateQuantity` 0x777E70/1305 target; `GetCraftQueueResourceCost` 0x777960/1282 nested Q x R loop + FindItem; `GetItemOfTemplate` 0x7760E0/4324 linear search of a single item; `IncrementItemTemplateQuantity` 0x775310/2388 mutator; `FindItem` 0x75F990/6154 mutator/search; `HasResources` 0x79A350/351 loop R x GetItemTemplateQuantity; `execHasResources` 0x179BAC0/203 Blueprint only; `HasItemOfSameType` 0x75F700/648; `HasItemsEquipped` 0x794970/711; `AllowAddInventoryItem` 0x754580/1203 calls GetItemTemplateQuantity; `AddItem` 0x754A40/1644 mutator (-> UPrimalItem::AddToInventory); `RemoveItem` 0x7574B0/832 mutator (-> RemoveItemFromInventory); `EjectItem` 0x7577F0/953 mutator; `TickComponent` 0x77B3C0/794 **per-tick**; `TickCraftQueue` 0x77B6E0/936 **per-tick**; `IsValidCraftingResource` 0x796BF0/339 called from IsValidForCrafting; `RemoteInventoryAllowAddItems` 0x766F80/3240 transfer/trade; `ConsumeResources` 0x79A4B0/458 mutator; `LoadedFromSaveGame` 0x781330/7642 mass restore; `InitializeInventory` 0x762F20/5184 rebuild; `ServerCraftItem` 0x7798E0/992 server crafting; `ServerMakeRecipeItem_Implementation` 0x773640/5985 server crafting.

Related `UPrimalItem::*` (RVA/size; calls GetItemTemplateQuantity?): `MeetBlueprintCraftingRequirements` 0x7F8710/4057 yes 1x (+ GetCraftQueueResourceCost); `MeetRepairingRequirements` 0x7FB320/1422 yes 2x; `TestMeetsCraftingRequirementsPercent` 0x7F96F0/1560 yes 2x; `ConsumeCraftingRequirementsPercent` 0x7F9D10/1598 no (via IncrementItemTemplateQuantity); `GetCraftingRequirementsString` 0x7FA350/4034 yes 2x; `GetRepairingRequirementsString` 0x7FB8B0/9422 yes **7x**; `IterateCraftingRequirements` 0x7FE790/882 yes 1x; `IterateRepairingRequirements` 0x7FDD80/2569 yes 3x; `MakeRepairingRequirementsString` 0x831F60 yes 1x; `GetMiscInfoString` 0x7F30B0/5024 yes 1x (virtual, slot 0x2F0); `CheckForInventoryDupes` 0x826100/13506 called from GetItemTemplateQuantity; `TickCraftingItem` 0x80B760/5227 virtual slot 0x338 **per-tick**; `CanCraft` 0x816970/5715 virtual slot 0x350; `CanFullyCraft` 0x8033C0/482 indirectly; `GetMaximumAdditionalCrafting` 0x824D40/446 indirectly; `SetQuantity` 0x80D4C0/8562 quantity mutator; `IncrementItemQuantity` 0x7F4D60/8631 quantity mutator; `AddToInventory` 0x7AC9A0/12407 **array mutator**; `RemoveItemFromInventory` 0x7AFCA0/9604 **array mutator**; `calcResourceQuantityRequired` 0x7F1490/1126.

Adjacent low-level: `UObjectBaseUtility::IsA` 0x1FCDAB0/36; `UStruct::IsChildOf` 0x1DCC80/25; `UPrimalItem::StaticClass` 0x1DCC70/12 (jmp -> GetPrivateStaticClass 0x1364F00, 69 B); `UPrimalItem::GetPrivateStaticClass` 0x1364F00/69; `UPrimalItem::IsBroken` 0x7D0900/95; `UPrimalItem::GetDurabilityPercentage` 0x801750/149; `FWeakObjectPtr::IsValid` 0xDA8030/105; `FWeakObjectPtr::Get` 0x1FD7730/94.

Vtable `UPrimalItem::$_VTable` (RVA 0x3FD2058, `.rdata`), verified by reading the file directly (4 copies of the IsValidForCrafting pointer at RVAs 0x3FD2400, 0x3FD2870, 0x3FD2CE0, 0x3FDC9C0): +0x000 = 0x1407A6770 scalar deleting destructor; +0x2E8 = 0x1407F2F70 GetItemQuantity; +0x2F0 = 0x1407F30B0 GetMiscInfoString; +0x338 = 0x14080B760 TickCraftingItem; +0x350 = 0x140816970 CanCraft; +0x3A0 = 0x14081AA90 CanSpoil; +0x3A8 = 0x14081D4B0 **IsValidForCrafting**. Separately: 0x144A1ED38 (the only "non-vtable" DATA xref on IsValidForCrafting) is a `.pdata` record `RUNTIME_FUNCTION{Begin=0x81D4B0, End=0x81DB31, Unwind=0x435A5E0}`, not a reference.

### What is scanned

`GetItemTemplateQuantity` (0x777E70, 1305 B) - signature (param names from `Z_Construct_UFunction_...` 0x14152C4A0 + reading order in the exec 0x179BFD0):
`int GetItemTemplateQuantity(UPrimalInventoryComponent* this, TSubclassOf<UPrimalItem> ItemTemplate, UPrimalItem* IgnoreItem, bool bIgnoreBlueprints, bool bCheckValidForCrafting, bool bRequireExactClassMatch, bool bForceCheckForDupes)`.

Body: (1) `ItemTemplate == nullptr` -> 0; else `UPrimalItem::StaticClass()` (0x1401DCC70) + `UStruct::IsChildOf` (0x1401DCC80) - a non-UPrimalItem class also -> 0. (2) **Two duplicated loops over `this->InventoryItems`** (`TArray<UPrimalItem*>`, offset **+0x118 in the object**, confirmed by `MOV RAX,[RSP+0xE0]; ADD RAX,0x118` @ 0x140777EF6): `bForceCheckForDupes == false` -> forward pass 0..ArrayNum-1 (labels LAB_140777F39...); `== true` -> reverse pass (labels LAB_140778155...) plus the extra filter `UPrimalItem::CheckForInventoryDupes(item) || (item->OwnerInventory == this)` (0x140826100; operator== 0x1401FF150). (3) Per item: null check; if `bRequireExactClassMatch` and `!item->bOverrideExactClassCraftingRequirement` -> compare the **exact** `item->Class` (item+0x0) with ItemTemplate; otherwise `IsChildOf(ItemTemplate, StaticClass())` + `IsA(item, ItemTemplate)` (0x141FCDAB0) - a **linear walk of the SuperStruct chain**; filters `bIgnoreBlueprints && item->bIsBlueprint`, `IgnoreItem && item == IgnoreItem`; if `bCheckValidForCrafting` -> **virtual call [vtable+0x3A8] = IsValidForCrafting** (addresses 0x1407780F7 and 0x140778319); `sum += [vtable+0x2E8]()` = GetItemQuantity (addresses 0x140778111 and 0x140778366). **No cache/memoization**: no global/static accesses, no state fields; the sum is recomputed fully per call; no indexes, hash tables or auxiliary structures in UPrimalInventoryComponent for this.

`IsValidForCrafting` (0x81D4B0, 1665 B) - early exits in order: (1) `!bValidCraftingResource` -> false; (2) `bIsBlueprint` -> false; (3) `IsBroken(this)` (0x1407D0900) -> false; (4) `bUseItemDurability && GetDurabilityPercentage() < MinDurabilityForCraftingResource` -> requires non-null OwnerInventory with flag `(uint)(Owner+0x50) >> 6 & 1`, else false; (5) `bPreventCraftingResourceAtFullDurability && GetDurabilityPercentage() >= 1.0f` -> same owner flag check, else false; (6) `OwnerInventory != null` -> `IsValidCraftingResource(OwnerInventory, this)` (0x140796BF0) -> false if it fails (inside: **two virtual calls on the Owner** at +0x888 and +0xCC8, plus an optional BPIsValidCraftingResource); (7) `bUseBPIsValidForCrafting` -> `BPIsValidForCrafting(this)` (0x14081DD00, 0x141366680) -> **ProcessEvent (slot +0x1E0), a full entry into the Blueprint VM**; (8) true. Per item total: **up to 3x `FWeakObjectPtr::IsValid` + 3x a dereference of `GUObjectArray`, 2-3x `GetDurabilityPercentage`, up to 2 entries into the Blueprint VM** (BPIsValidForCrafting and BPIsValidCraftingResource).

### Complexity

| Scenario | Formula |
|---|---|
| one GetItemTemplateQuantity | **O(N)** linear pass over InventoryItems; per-item constant 1-2x StaticClass, 1x IsChildOf, 1x IsA (SuperStruct walk), optionally 1x IsValidForCrafting (1665 B) + 1x GetItemQuantity |
| bForceCheckForDupes=true | same + CheckForInventoryDupes (13506 B) per item |
| MeetBlueprintCraftingRequirements | loop over CraftingResourceRequirements (**R**) x GetItemTemplateQuantity -> **O(R-N)** |
| MeetRepairingRequirements / HasResources / TestMeetsCraftingRequirementsPercent | **O(R-N)** (2 call sites each for the item-side ones) |
| GetCraftingRequirementsString / GetRepairingRequirementsString | **O(R-N)**; repairing string has 7 call sites |
| GetCraftQueueResourceCost (0x777960) | **O(Q x (N_find + R))**, Q = ItemCraftQueueEntries |
| TickCraftingItem per tick | up to 3x MeetBlueprintCraftingRequirements + 1x MeetRepairingRequirements -> **O(R-N) per tick per active blueprint** |
| TickCraftQueue per tick | per repair-queue entry -> MeetRepairingRequirements -> **O(R-N) per tick per entry** |

No nested loops INSIDE GetItemTemplateQuantity - nesting appears at the caller level (crafting/repair/inventory UI). This matters for optimization: **the bottleneck is not the pass but the cost of filtering one item** (IsA + IsValidForCrafting).

### All call sites: GetItemTemplateQuantity - 74 direct sites in 57 functions (all from `.text`)

Per-event / per-action / per-tick periodicity is marked. The five narrow **per-tick** paths are detailed in the next subsection; everything else is per-event or Blueprint:

| Call site | Containing function (RVA) | Periodicity |
|---|---|---|
| 0x2D2CC8 | UHexagonTradableOption::GetAmountInInventory 0x2D2C60 | per trade click |
| 0x38821F | AMissionType::RemoveItemsFromInventory_Balanced 0x387FC0 | per mission event |
| 0x38A6A6 | AMissionType::CountInventoryItems 0x38A610 | per mission event |
| 0x38A815 | AMissionType::CountInventoryItemsFromAllPlayersInMission 0x38A6B0 | per mission event |
| 0x3EFE57 | UPrimalAbility::CanConsumeFuel 0x3EFC40 | per ability tick |
| 0x3F073A | UPrimalAbility::ConsumeFuel 0x3EFE80 | per event |
| 0x3F1327 | UPrimalAbility::GetAvailableFuelConfig 0x3F11C0 | on demand |
| 0x3F14AC | UPrimalAbility::GetAvailableFuel 0x3F13A0 | on demand |
| 0x6A8383 | APrimalDinoCharacter::TamedDinoUnstasisConsumeFood 0x6A75C0 | per event (unstasis) |
| 0x7547D4 | UPrimalInventoryComponent::AllowAddInventoryItem 0x754580 | **every add attempt** |
| 0x767B3B | UPrimalInventoryComponent::RemoteInventoryAllowAddItems 0x766F80 | per transfer/trade RPC |
| 0x79A491 | UPrimalInventoryComponent::HasResources 0x79A350 | Blueprint (exec 0x179BAC0), O(R-N) |
| 0x7F395E | UPrimalItem::GetMiscInfoString 0x7F30B0 (virtual 0x2F0) | per UI/info request |
| 0x7F9586 | UPrimalItem::MeetBlueprintCraftingRequirements 0x7F8710 | see per-tick paths |
| 0x7F99F3, 0x7F9CEA | UPrimalItem::TestMeetsCraftingRequirementsPercent 0x7F96F0 | inventory opening/multi-use |
| 0x7FAA1D, 0x7FAD85 | UPrimalItem::GetCraftingRequirementsString 0x7FA350 | tooltip opening |
| 0x7FB6F2, 0x7FB889 | UPrimalItem::MeetRepairingRequirements 0x7FB320 | see per-tick paths |
| 0x7FC058, 0x7FC317, 0x7FC794, 0x7FCF59, 0x7FD289, 0x7FD774, 0x7FDAA5 | UPrimalItem::GetRepairingRequirementsString 0x7FB8B0 | tooltip opening (7x) |
| 0x7FE05C, 0x7FE39A, 0x7FE68C | UPrimalItem::IterateRepairingRequirements 0x7FDD80 | tooltip (3x) |
| 0x7FE982 | UPrimalItem::IterateCraftingRequirements 0x7FE790 | tooltip |
| 0x83247E | UPrimalItem::MakeRepairingRequirementsString 0x831F60 | tooltip |
| 0x8BDBD7 | APrimalShip::CanConsumeFuel 0x8BD9F0 | per ship tick |
| 0x8BDFEC, 0x8BE069 | APrimalShip::ConsumeFuel 0x8BDC00 | per tick/event |
| 0x8BE49D | APrimalShip::GetCurrentFuelInterval 0x8BE300 | per tick |
| 0x8BE898 | APrimalShip::CacheFirstFoundShipFuel 0x8BE530 | per event |
| 0x8BEEDE | APrimalShip::UpdateCachedFuelInfo 0x8BECC0 | per event |
| 0x8E27A3 | APrimalStingerShip::CanConsumeFuel 0x8E2610 | per tick |
| 0x8E2B58, 0x8E2BC5 | APrimalStingerShip::ConsumeFuel 0x8E27D0 | per tick/event |
| 0x8E2FD9 | APrimalStingerShip::GetCurrentFuelInterval 0x8E2E50 | per tick |
| 0x8E324A | APrimalStingerShip::CacheFirstFoundShipFuel 0x8E3070 | per event |
| 0x8E362A | APrimalStingerShip::UpdateCachedFuelInfo 0x8E3460 | per event |
| 0x94E225 | APrimalStructure::GetMultiUseEntries 0x94BE80 | structure inventory opening |
| 0x94FA9D | APrimalStructure::TryMultiUse 0x94F790 | per player action |
| 0x9BD9E7 | APrimalStructureItemContainer::NotifyItemAdded 0x9BD750 | per event |
| 0x9BE0F6 | APrimalStructureItemContainer::NotifyItemRemoved 0x9BDDD0 | per event |
| 0x9BE44E, 0x9BE55F | APrimalStructureItemContainer::RefreshFuelState 0x9BE2E0 | per event |
| 0x9CBD15 | ...ItemContainer_CropPlot::AllowRemoteAddItemToInventory 0x9CBBA0 | per event |
| 0x9D3C51 | ...ItemContainer_CropPlot::GetPhaseInventoryItemCount 0x9D3AA0 | per event |
| 0x9D4E74 | ...ItemContainer_CropPlot::RefreshFertilized 0x9D4E20 | per event |
| 0x9D50B0 | ...ItemContainer_CropPlot::NotifyItemRemoved 0x9D5020 | per event |
| 0x9D5213 | ...ItemContainer_CropPlot::NotifyItemAdded 0x9D5160 | per event |
| 0x9DACFD | ...CropPlot_VisualItems::NotifyItemRemoved 0x9DABB0 | per event |
| 0x9DAF0B | ...CropPlot_VisualItems::NotifyItemAdded 0x9DADB0 | per event |
| 0x9DF7CA | ...ItemContainer_VisualItems::NotifyItemRemoved 0x9DF6B0 | per event |
| 0x9DFB68 | ...ItemContainer_VisualItems::NotifyItemAdded 0x9DFA40 | per event |
| 0x9ECDD7 | APrimalStructurePlacer::Tick 0x9ECC80 (+0x157) | **per-tick while the placement "ghost" is active** |
| 0x9F6484 | APrimalStructurePlacer::FinalStructurePlacement 0x9F3E30 | per placement event |
| 0xA2B3E3, 0xA2B473 | APrimalStructureTurret::GetAmmoNearby 0xA2A950 | **per turret tick** |
| 0xA3F05F | APrimalStructureTurret::UpdateNumBullets 0xA3F020 | per event |
| 0xA45B81 | APrimalStructureTurretBallista::DoFire 0xA45AA0 | per shot |
| 0xA544D9 | APrimalStructureTurretBallista::DoFireProjectile 0xA54060 | per shot |
| 0xA58CE2, 0xA591B4 | APrimalStructureTurretBallista::GetAmmoNearby 0xA58C20 | per event |
| 0xA5969F, 0xA598AC | APrimalStructureTurretBallista::GetAmmoAmount 0xA59640 | **per ballista tick** (via CanFire/CanReload) |
| 0xAACF98 | APrimalWeaponBoomerang::OnBoomerangReturn 0xAACCC0 | per event |
| 0xF4D680 | AShooterWeapon::RefreshAmmoItemQuantity 0xF4D480 | from Blueprint |
| 0xFEFCFD | UStructuresPlus::SP_GetInventoryCapacityForItem 0xFEFAB0 | on request |
| 0x179C341 | UPrimalInventoryComponent::execGetItemTemplateQuantity 0x179BFD0 | **from Blueprint graphs** |

### IsValidForCrafting - call sites and per-tick verdict

**0 direct (static) calls in the binary** (verified with an `E8 rel32` scanner over the entire `.text`). All 5 DATA-xrefs: 1 `.pdata` record (0x144A1ED38), 4 vtable copies (0x3FD2400 / 0x3FD2870 / 0x3FD2CE0 / 0x3FDC9C0). Actual entry points: 0x1407780F7 (GetItemTemplateQuantity forward pass, bCheckValidForCrafting==true), 0x140778319 (reverse pass, bForceCheckForDupes), 0x1417AA681 (execIsValidForCrafting 0x17AA660, from Blueprint) - both GetItemTemplateQuantity calls happen per inventory item when bCheckValidForCrafting==true, exactly what `MeetBlueprintCraftingRequirements` passes (`ItemClass, IgnoreItem=this, bIgnoreBlueprints=true, bCheckValidForCrafting=true, bRequireExactClassMatch, bForceCheckForDupes=false`), while `MeetRepairingRequirements`, `HasResources`, `TestMeetsCraftingRequirementsPercent`, `GetCraftingRequirementsString` pass `false` - there IsValidForCrafting is NOT called.

**CRITICAL - not "for every actor on every tick":** no direct call from a generic actor tick; exactly five per-tick paths, all narrow:
1. `UPrimalInventoryComponent::TickComponent` (0x77B3C0, 794 B) -> `TickCraftQueue` (0x77B6E0) -> `MeetRepairingRequirements` (0x7FB320, call 0x77B996 +0x2B6) -> 2x GetItemTemplateQuantity per requirement. Gates: `bUseCraftQueue != 0`, non-empty `ItemCraftQueueEntries`, `CraftingItems` empty - **only with an active repair queue**.
2. `TickComponent` -> for each element of `CraftingItems`, the virtual `UPrimalItem::TickCraftingItem` (slot 0x338) -> up to 3x `MeetBlueprintCraftingRequirements` (calls 0x80C077, 0x80C2B8, 0x80C54A) + 1x `MeetRepairingRequirements` (0x80BCF9). Gate: only actively crafting blueprints - **per active crafting job, every tick**.
3. `APrimalStructureTurret::Tick` (0xA39740) -> `GetAmmoNearby` (0xA2A950, call 0xA3A129 +0x9E9) -> 2x GetItemTemplateQuantity. **Every turret, every tick** (behind a conditional jump).
4. `APrimalStructureTurretBallista::Tick` (0xA4CE60) -> `CanFire` (0xA532E0, call 0xA4FE93 +0x3033) -> 2x `GetAmmoAmount` (0xA59640) -> GetItemTemplateQuantity; also `CanReload` (0xA53880) and `UpdateAmmoCount` (0xA53AB0). **Every ballista, every tick.**
5. `APrimalStructurePlacer::Tick` (0x9ECC80, +0x157) - only while the player drags a placement ghost.

The remaining 69 call sites are per-event (item add/remove, inventory opening, transfer/trade RPC, tooltip) or from Blueprint graphs. Profile confirmation: `prof_298529359.bin` contains `TickCraftingItem` (19 samples) and `MeetBlueprintCraftingRequirements` (19 samples) - paths 1-2 are actually active in steady state. Caveat: `UUI_*`, `UPrimalItemToolTipWidget::InitToolTip`, `UDataListEntryButton_PrimalItem::DrawItemPart_Background`, `UInventoryPanelWidget::OnInventoryItemDoubleClicked` are present in the binary (server build contains all UI code) but on a dedicated server they are **not executed**.

### Optimization sketch: index/cache

Where to store: `InventoryItems` lives in the component, not in the actor (+0x118; +0x0 data, +0x8 ArrayNum, +0xC ArrayMax). The index state must hang **on the component** (side-map `UPrimalInventoryComponent* -> FInvIndex`), not on the actor and not globally - each player, tamed dino, container structure, turret has its own component/index. GetItemTemplateQuantity is often called with the component resolved from `item->OwnerInventory` (e.g. MeetBlueprintCraftingRequirements 0x7F8710 dereferences OwnerInventory when param_1 == nullptr) - look the index up by the passed `this`, not by the actor/item.

Structure: not "one sum per class" but **a bucket per EXACT class** - otherwise `bRequireExactClassMatch` (instance flag `bOverrideExactClassCraftingRequirement`) and `bIgnoreBlueprints` (`bIsBlueprint`, also an instance flag) cannot be accounted for. `FInvBucket` per exact UClass: `TArray<UPrimalItem*, TInlineAllocator<8>> Items`, `int32 TotalQuantity` (sum GetItemQuantity), `int32 ExactClassQuantity` (sum over !bOverrideExactClassCraftingRequirement), `int32 NonBlueprintQty` (sum over !bIsBlueprint), `uint32 Gen` (lazy invalidation). `FInvIndex`: `uint32 Gen`, `uint32 ItemsGen` (changes at SetQuantity/IncrementItemQuantity), `TMap<UClass*, FInvBucket> ByClass`, `TArray<UClass*, TInlineAllocator<8>> MatchCache` (derived "which buckets match"). Query: (1) `ByClass.Num() == 0` -> 0 (fast exit, no worse than current code); (2) from MatchCache (or rebuild in O(number of distinct classes)) the buckets whose class `IsA(ItemTemplate)`; (3) walk only those, applying the remaining predicates (bIsBlueprint, item == IgnoreItem, IsValidForCrafting) per item. Distinct classes in a real inventory: usually 3-15 vs N in tens/hundreds - the gain replaces O(N) with O(number of classes + matching items).

Invalidation hooks: the minimal safe hook intercepts **4 addresses** - `AddToInventory` 0x7AC9A0 (12407 B; **1** call site: AddItem 0x754A40 +0x362), `RemoveItemFromInventory` 0x7AFCA0 (9604 B; **5** sites: RemoveItem 0x7575B7, EjectItem 0x757897, ClientStartReceivingItems 0x75EEA5 and 0x75EF19, APrimalStructure::PickupStructureAndDependingLinkedStructures 0x97B342), `SetQuantity` 0x80D4C0 (8562 B; 7 sites), `IncrementItemQuantity` 0x7F4D60 (8631 B; 15 sites) - and rebuilds/updates the bucket of the component the call came from. Full rebuild at `LoadedFromSaveGame` 0x781330 (7642), `InitializeInventory` 0x762F20 (5184), `InitDefaultInventory` 0x762010 (3590), `OnComponentCreated` 0x796D50 (1653). All other quantity increasers (`IncrementItemTemplateQuantity` 0x775310, `ConsumeResources` 0x79A4B0, `ServerSplitItemStack_Implementation` 0x77C600, `ServerMergeItemStack_Implementation` 0x77CBF0, `ServerForceMergeItemStack_Implementation` 0x77D0B0, `TransferAllItemsToInventory*`, trade via `AShooterPlayerController::Server*RemoteInventory*`) transitively go through these four points - no separate hooks needed.

Invalidation risk by data type: items in backpacks/containers/on dinos each have their **own** component and index - no problem if addressed by component. `IsValidForCrafting` is NOT inventory state: it depends on durability (GetDurabilityPercentage), IsBroken, bPreventCraftingResourceAtFullDurability, OwnerInventory (changes at TransferItemToInventory/pickup), the parent structure (`bUseParentStructureIsValidCraftingResource` -> IsValidCraftingResource 0x796BF0) and the Blueprint (`bUseBPIsValidForCrafting` -> ProcessEvent) - **none of these mutate InventoryItems**, so the "sum of only craft-valid items" cannot be cached without separate durability-based invalidation. Trading/transfer goes through AddItem/RemoveItem -> covered; crafting/repair (ConsumeResources, IncrementItemTemplateQuantity, FinishCraftingBlueprint, RepairItem) goes through IncrementItemQuantity/RemoveItemFromInventory -> covered; load/save (`LoadedFromSaveGame` + `ClientStartReceivingItems`) is mass insertion - a rebuild, not a point edit. The function is exported as a UFunction (exec 0x179BFD0) - any semantic change is observable in scripts.

What breaks with a stale cache: (1) understated -> `MeetBlueprintCraftingRequirements` returns false -> in `TickCraftQueue` (0x77B6E0, branch +0x2B6) when `MeetRepairingRequirements()==false` the entry is **removed from ItemCraftQueueEntries via TArray::RemoveAt** -> the repair/craft queue is silently lost - loss of player progress, irregular; (2) overstated -> `ServerCraftItem` (0x7798E0) / `ServerMakeRecipeItem_Implementation` (0x773640) authoritatively consume non-existent resources -> dupe/desync (craft is server-side; the client trusts the answer); (3) a missed SetQuantity/IncrementItemQuantity -> the quantity "sticks", items can be spent repeatedly; (4) a bucket not rebuilt at LoadedFromSaveGame -> all aggregates zero after world load -> same as (1).

Risk class: **LOW** - buckets per exact class without accounting for IsValidForCrafting (predicates applied to bucket items on the spot); invalidation fully covered by the 4 points + rebuild at load; a semantic violation is possible only through a bug in the hook itself. **HIGH** - the same plus aggregating "the sum of only craft-valid items" (not invalidated by inventory mutation events; durability/break/Blueprint flags change independently; plus the silent loss of the repair queue). **MEDIUM** - a cache without buckets, one sum per class (breaks bRequireExactClassMatch / bOverrideExactClassCraftingRequirement). **Recommendation: the LOW-risk variant.**

### Gain estimate (prof_298529359.bin, 30 463 samples; in-image 4265 = 14.0%, external 86.0%)

| Symbol | Samples | % of wall | % of executed (4265) |
|---|---|---|---|
| UObjectBaseUtility::IsA | 284 | 0.93% | 6.66% |
| **UPrimalInventoryComponent::GetItemTemplateQuantity** | **128** | **0.42%** | **3.00%** |
| FWeakObjectPtr::Get | 64 | 0.21% | 1.50% |
| **UPrimalItem::IsValidForCrafting** | **61** | **0.20%** | **1.43%** |
| FWeakObjectPtr::IsValid | 59 | 0.19% | 1.38% |
| UPrimalItem::GetPrivateStaticClass | 21 | 0.07% | 0.49% |
| UPrimalItem::TickCraftingItem | 19 | 0.06% | 0.45% |
| UPrimalItem::MeetBlueprintCraftingRequirements | 19 | 0.06% | 0.45% |
| UBlueprintFunctionLibrary::GetFunctionCallspace | 18 | 0.06% | 0.42% |
| UPrimalInventoryComponent::IsValidCraftingResource | 12 | 0.04% | 0.28% |
| UPrimalItem::GetItemQuantity | 8 | 0.03% | 0.19% |
| UPrimalInventoryComponent::GetItemOfTemplate | 7 | 0.02% | 0.16% |

Notes: `2.60% + 1.24%` from REPORT-Genesis.md is the share **of the 4932 "executed" samples** by that methodology; on the 4265 in-image base the same symbols give **3.00% + 1.43% = 4.43%** - the discrepancy is in the base; the share is comparable. `GetPrivateStaticClass` (21) is `UPrimalItem::StaticClass()` (0x1DCC70, 12 B jmp), called 1-2 times per item in the body of GetItemTemplateQuantity - part of the function's own cost. Full A3 cluster (GetItemTemplateQuantity + IsValidForCrafting + GetPrivateStaticClass + TickCraftingItem + MeetBlueprintCraftingRequirements + IsValidCraftingResource + GetItemQuantity + GetItemOfTemplate) = **275 samples = 0.90% wall = 6.45% of executed code**; by classes: UPrimalInventoryComponent 156 + UPrimalItem 138 = 294 samples = 0.96% wall. Ceiling: `IsA` provides another 284 samples (6.66% executed) and GetItemTemplateQuantity is one of its callers (2 of **1360** call sites in the whole binary); offline this contribution cannot be separated - conservatively **not credited**. Realistic estimate: replacing O(N) with O(number of classes) removes most of both passes and their IsA; with an 80% reduction of the A3 cluster -> **~220 samples ~ 0.72% wall** (~4.3% of active, non-sleeping time) - real, but **not the main reserve of Genesis**: Blueprint VM is the dominant share (22.8% executed per REPORT-Genesis.md), IsA is 6.66% executed with A3 only a small part of its 1360 calls, and `ServerOctreeOverlapActors` + `AdvanceToNextIntersectingElement` = 365 + 319 samples. The magnitude of A3 depends on the load (active craftings/ballistas/turrets); prof_298529359.bin is "a steady state with active crafting" (TickCraftingItem in the top).

### Explicitly NOT found

1. `UPrimalInventoryComponent::HasItem` - no symbol (nearest: HasResources 0x79A350/351, HasItemOfSameType 0x75F700/648, HasItemsEquipped 0x794970/711).
2. `GetInventoryItems` - no symbol (0 matches in `fn`).
3. `UPrimalInventoryComponent::GetItemQuantity` - no symbol (only UPrimalItem::GetItemQuantity 0x7F2F70/17).
4. `GetCraftingCost` - no symbol (nearest: GetCraftQueueResourceCost 0x777960/1282).
5. No cache/memoization in GetItemTemplateQuantity - confirmed by decompilation; no ready index structure in the component either.
6. 0 direct (static) calls of IsValidForCrafting - reachable only through vtable slot 0x3A8 (4 copies in .rdata) and the Blueprint-thunk.
7. The distribution of calls among the 74 call sites was not measured (TickProf gives self-time per function, not per site) - unavailable offline.
8. The actual N (InventoryItems.ArrayNum) and R (CraftingResourceRequirements.ArrayNum) on Genesis were not measured - unavailable offline.
9. Which Blueprint graphs call execGetItemTemplateQuantity (0x179BFD0) / execIsValidForCrafting (0x17AA660) was not established - bytecode in `.uasset`, unreadable offline; the 18 samples of GetFunctionCallspace and a significant part of `UObject::Process*` may come from there.
10. The value of `bUseCraftQueue` in the CDO was not checked (a component flag; whether per-tick path 1 is active depends on it).
11. Whether `bUseBPIsValidForCrafting` is enabled for real item classes on the map was not checked - whether the 2 ProcessEvent calls per item enter the hot path depends on it.
12. The share of IsA (284 samples) attributable specifically to GetItemTemplateQuantity was not isolated (2 of its 1360 call sites).
13. A3-adjacent symbols (GetInventoryItems, HasItem, GetCraftingCost) are entirely absent from `fn` (verified with LIKE queries over the whole table, 737 108 rows).

## A5 (RE2 section): BP machine and tracer

### Symbols and globals

| Symbol | RVA | VA | size |
|---|---|---|---|
| `UObject::ProcessInternal` | 0x01FC0270 | 0x141FC0270 | 344 |
| `UObject::ProcessContextOpcode` | 0x01FC1FA0 | 0x141FC1FA0 | 184 |
| `UObject::CallFunction` | 0x01FBFEF0 | 0x141FBFEF0 | 889 |
| `UObject::ProcessEvent` | 0x01FC0DB0 | 0x141FC0DB0 | 664 |
| `UFunction::Invoke` | 0x01F867C0 | 0x141F867C0 | 792 |
| `UFunction::Bind` | 0x01F86D30 | 0x141F86D30 | 160 |
| `UFunction::GetReturnProperty` | 0x01F86CB0 | 0x141F86CB0 | 119 |
| `FFrame::FFrame` (ctor) | 0x01FA57E0 | 0x141FA57E0 | 382 |
| `FFrame::~FFrame` | 0x01FA56A0 | 0x141FA56A0 | 266 |
| `FFrame::ReadVariableSize` | 0x01FA5960 | 0x141FA5960 | 416 |
| `UObject::SkipFunction` | 0x01FBFD10 | 0x141FBFD10 | 480 |
| `UObjectBaseUtility::GetInterfaceAddress` | 0x01FCDAE0 | 0x141FCDAE0 | 259 |
| `UObject::ExecuteUbergraph` | 0x001C0ED0 | 0x141C0ED0 | 63 |
| `UObjectBaseUtility::GetName` | 0x001F0FE0 | 0x141F0FE0 | 45 |
| `FName::GetNames` | 0x01F427D0 | 0x141F427D0 | 107 |
| `FName::ToString` (wrapper) | 0x01F432B0 | 0x141F432B0 | 58 |
| `FName::ToString` (real) | 0x01F432F0 | 0x141F432F0 | 130 |
| `FName::AppendString` | 0x01F43380 | 0x141F43380 | 197 |

Globals (data): `GNatives` 0x0491C6B0 - opcode dispatcher table (`MOV [RDI+RAX*8]` at 0x141FC0309/033C, 0x141FC00BE/0108); `GNativeDuplicate` 0x0491C89C - duplicate-opcode flag (0x141FA013A); `GScriptStack` 0x04937F00 - BP stack: +0x0 allocator, +0x8 ArrayNum, +0xC ArrayMax, stride 0x10 (0x141FA58A8..0x141FA5922); `GPrevScriptStack` 0x04937F10 (0x141FA58AA/0x141FA58C8); `GFullStackTrace` 0x04909C17 - byte flag (0x141FA5869); `NamePoolData` 0x0498A1C8 - FNameEntry pool, blocks of 0x800 slots (0x141F427D4/0x141F42812).

Xrefs to `UFunction::Invoke` (0x01F867C0) - 3 total: 0x141FBFFA2 (from CallFunction), 0x141FC0FA7 (from ProcessEvent), 0x141F869EB (recursion "BreakHitResult_OLD" inside Invoke itself). Xrefs to `ProcessInternal` (0x01FC0270): 0x141FC01F4 UNCONDITIONAL_CALL (from CallFunction); 0x141F86D7A and 0x141F86D81 DATA (from UFunction::Bind: `MOV [R9+0xA8], RAX`, RAX = 0x141FC0270); 0x144A7F044 DATA (vtable/table). **Conclusion: ProcessInternal has no caller call site in code - invoked indirectly via `UFunction::Func`; the call point cannot be patched, only a detour of the function body. Invoke does have call sites (3).**

### The set of `UObject::exec*`

**68** distinct PDB symbols `UObject::exec*`; one continuous block **0x01FC1050 ... 0x01FC36B6** (61 unique addresses, **8776 bytes**). **5 debug opcodes collapse onto a single 3-byte stub 0x001BCBB0**: execBreakpoint, execNothing, execNothingOp4a, execTracepoint, execWireTracepoint (aliases in the PDB). **63** are registered in `GNatives` as opcodes. **4 have code but no slot**: execUndefined (0x01FC1050 - table filler), execObjectToBool (0x01FC3480), execInterfaceToBool (0x01FC34D0), execObjectToInterface (0x01FC3520) - the static names of the last three are `...CastTemp`/`...Registar`, not `...BytecodeTemp` (the bytecode compiler does not produce them). Separately: `UObject::ExecuteUbergraph` (0x001C0ED0, 63 B) - not an opcode but a tunnel-UFunction.

Full list (RVA, size): 0x01FC1050 29 execUndefined; 0x01FC1070 53 execLocalVariable; 0x01FC10B0 55 execInstanceVariable; 0x01FC10F0 73 execLocalOutVariable; 0x01FC1140 72 execInterfaceContext; 0x01FC1190 219 execEndOfScript; 0x01FC1270 5 execEndFunctionParms; 0x01FC1280 29 execJump; 0x01FC12A0 76 execComputedJump; 0x01FC12F0 98 execJumpIfNot; 0x01FC1360 247 execAssert; 0x01FC1460 132 execPushExecutionFlow; 0x01FC14F0 114 execPopExecutionFlow; 0x01FC1570 165 execPopExecutionFlowIfNot; 0x01FC1620 485 execLet; 0x01FC1810 604 execLetObj; 0x01FC1A70 604 execLetWeakObjPtr; 0x01FC1CD0 325 execLetBool; 0x01FC1E20 169 execLetDelegate; 0x01FC1ED0 164 execLetMulticastDelegate; 0x01FC1F80 4 execSelf; 0x01FC1F90 5 execContext / execContext_FailSilent; 0x01FC2060 497 execStructMemberContext; 0x01FC2260 110 execVirtualFunction; 0x01FC22D0 21 execFinalFunction; 0x01FC24C0 8 execCallMulticastDelegate; 0x01FC24D0 140 execAddMulticastDelegate; 0x01FC2560 140 execRemoveMulticastDelegate; 0x01FC25F0 78 execClearMulticastDelegate; 0x01FC2640 19 execIntConst / execSkipOffsetConst; 0x01FC2660 23 execFloatConst; 0x01FC2680 23 execDoubleConst; 0x01FC26A0 213 execStringConst; 0x01FC2780 217 execUnicodeStringConst; 0x01FC2860 609 execStringLocConst; 0x01FC2AD0 602 execTextConst; 0x01FC2D30 20 execObjectConst; 0x01FC2D50 90 execInstanceDelegate; 0x01FC2DB0 188 execBindDelegate; 0x01FC2E70 53 execNameConst; 0x01FC2EB0 15 execByteConst; 0x01FC2EC0 45 execRotationConst / execVectorConst; 0x01FC2EF0 129 execTransformConst; 0x01FC2F80 201 execStructConst; 0x01FC3050 458 execSetArray; 0x01FC3220 8 execIntZero; 0x01FC3230 8 execIntOne; 0x01FC3240 5 execTrue; 0x01FC3250 5 execFalse; 0x01FC3260 8 execNoObject; 0x01FC3270 15 execIntConstByte; 0x01FC3280 244 execDynamicCast; 0x01FC3380 208 execMetaCast; 0x01FC3450 31 execPrimitiveCast; 0x01FC3470 11 execInterfaceCast; 0x01FC3480 71 execObjectToBool (no slot); 0x01FC34D0 72 execInterfaceToBool (no slot); 0x01FC3520 200 execObjectToInterface (no slot); 0x01FC35F0 198 execInterfaceToInterface.

### Layout of the interpreter frame

`FFrame` - confirmed by the ctor 0x141FA57E0; canonical call from `CallFunction` (0x141FC0029): `FFrame::FFrame(this=&stack, Owner=this, Function=UFunction*, Locals=buf, PreviousFrame=param_1, PropertyChainForCompiledIn=*(UFunction+0x38))`.

| Offset | Field | Proof |
|---|---|---|
| +0x00 | void** vftable = 0x144073EB0 | `MOV [RCX],RAX` 0x141FA5815 |
| +0x08 | uint16 = 0x100 | `MOV word [RCX+8],0x100` 0x141FA5808 |
| +0x10 | **UFunction* Node** | `MOV [RCX+0x10],R8` 0x141FA5818 |
| +0x18 | **UObject* Object** | `MOV [RCX+0x18],RDX` 0x141FA581C |
| +0x20 | **uint8* Code** (PC) | `MOV [RCX+0x20],RAX`, RAX=[R8+0x48] 0x141FA5820/24 |
| +0x28 | **uint8* Locals** | `MOV [RCX+0x28],R9` 0x141FA5828 |
| +0x30 | UProperty* MostRecentProperty | `MOV [RCX+0x30],0` 0x141FA582E; write 0x141FC107E |
| +0x38 | uint8* MostRecentPropertyAddress | `MOV [RCX+0x38],0` 0x141FA5832; write 0x141FC108E |
| +0x60 | inline-heap allocator TArray FlowStack | `ADD RCX,0x60; CALL 0x1401BF260` 0x141FA5836/3A |
| +0x68/+0x6C | FlowStack.ArrayNum=0 / ArrayMax=8 | 0x141FA583F/42 |
| +0x70 | FFrame* PreviousFrame | `MOV [RBX+0x70],RAX` 0x141FA584E |
| +0x78 | FOutParmRec* OutParms | `MOV [RBX+0x78],0` 0x141FA5852 |
| +0x80 | UField* PropertyChainForCompiledIn | `MOV [RBX+0x80],RAX` 0x141FA585B |
| +0x88 | **UFunction* CurrentNativeFunction** | `MOV [RBX+0x88],0` 0x141FA5862; written with `this` in UFunction::Invoke 0x141F86AA0 |

`Locals` is **neither a TArray<uint8*> nor a list of pointers**: a **flat uint8* buffer** addressed by offsets from UProperty, no "Stride" (execLocalVariable 0x141FC1070: code literal UProperty* at `[RAX]`, `Code += 8`, `MOVSXD R8,[RCX+0x4C]` = `UProperty::Offset_Internal`, `ADD R8,[RDX+0x28]` = Locals + Offset_Internal). Outcome: **`Locals[Prop->Offset_Internal]`, UProperty+0x4C = Offset_Internal (int32)**.

`UFunction` - confirmed by `Bind` (0x141F86D30) and the FFrame ctor: **+0x18 `FName Name`** (ComparisonIndex @+0x18, Number @+0x1C; proofs: GetName `MOV RAX,[RCX+0x18]` at 0x141F0FE0+6; Invoke compares NAME_BreakHitResult.ComparisonIndex/Number 0x141F86946..958; script stack writes `[RSI+0x18]` 0x141FA58DA); **+0x20 `UObject* Outer`** (for a UFunction - the owning UClass, walked as `UClass*` via `Super` +0x30 looking for UInterface::StaticClass, 0x141F869F5..0x141F86A20); **+0x38 `UProperty* PropertyChainForCompiledIn`** (CallFunction `MOV RAX,[R14+0x38]`, passed as 6th argument to the ctor, 0x141FC000E/0012/0029); **+0x40 `int32 ParmsSize`** (`MOVSXD RDX,[R9+0x40]`, then memset of that size, 0x141FBFFBF/0011); **+0x48 `uint8* Script`** (ctor `MOV RAX,[R8+0x48]; MOV [RCX+0x20],RAX` 0x141FA5820/24; the pair (FName@+0x18, Script@+0x48) written to GScriptStack 0x141FA58DA, 0x141FA58EB+0x141FA5922); **+0x90 `uint32 FunctionFlags`** (`TEST dword [R9+0x90],0x400` FUNC_Native - 0x141FBFF36, 0x141F86D6D; `TEST [R14+0x90],0x400000` FUNC_HasOutParms - 0x141FC0036); **+0xA8 `FNativeFuncPtr Func`** (`CALL qword [RBP+0xA8]` 0x141F86AB2; `LEA RAX,[0x141FC0270]; MOV [R9+0xA8],RAX` 0x141F86D7A/81).

**Key fact for the tracer** (UFunction::Bind, 0x141F86D6D): `TEST dword ptr [R9+0x90], 0x400` (FUNC_Native) / `JNZ 0x141f86d89` / `LEA RAX,[0x141FC0270]` / `MOV qword ptr [R9+0xA8],RAX` - **for any scripted (non-native) UFunction the field `Func` = `&UObject::ProcessInternal`**. `Invoke` is exactly `Func(Obj, FFrame&, RESULT)` plus a small prologue (BreakHitResult shims, an interface lookup, `GProgressBarAddQuanta`). Other useful UProperty offsets (context only): +0x30 ArrayDim, +0x34 ElementSize, +0x38 uint64 PropertyFlags, +0x4C Offset_Internal, +0x60 Next (from 0x141FC039C/03A4, 0x141FC0386, 0x141FC012C, the chain in ProcessEvent).

### Opcode dispatcher

Pointer table **`GNatives[256]` (2048 bytes)**, index = opcode byte; no switch/jumptable. The loop of ProcessInternal (0x141FC0320-0x141FC0369), verbatim:

```asm
141fc0320  MOV  RAX,[RBX+0x20]          ; Code
141fc0324  LEA  R8,[RSP+0x30]           ; &scratchResult (64 bytes, local buffer)
141fc032c  MOVZX ECX,byte ptr [RAX]     ; op = *Code
141fc032f  INC  RAX                     ; Code++ BEFORE the call
141fc0332  MOV  [RBX+0x20],RAX
141fc0338  MOV  RCX,[RBX+0x18]          ; FFrame->Object (1st argument)
141fc033c  CALL qword ptr [RDI+RAX*0x8] ; RDI=0x14491C6B0 -> GNatives[op]
141fc0343  CMP  byte ptr [RAX],0x4      ; op == 0x04 (EX_Return)?
141fc0346  JNZ  0x141fc0320
141fc0348  INC  qword ptr [RBX+0x20]    ; skip the 0x04 byte
141fc0354  MOVZX EDX,byte ptr [RAX]     ; the last opcode
141fc035a  MOV  R8,RSI                  ; the REAL RESULT (param_2)
141fc0366  CALL qword ptr [RDI+RAX*0x8] ; GNatives[op](Object, Frame, RESULT)
```

Meaning: the **3rd argument** of each exec* is a pointer to a **64-byte local scratch** (RSP+0x30), zeroed at the start (where exec* writes the value for the consuming opcode - the UE4 "Property Copy" mechanism). The transition to the next instruction is done by **the dispatcher itself** (Code++ before the call); handlers do not move the PC except execJump/execJumpIfNot/execComputedJump/execEndOfScript (which set FFrame->Code themselves). Symbolic constants/UProperty pointers lie inline in the stream, consumed via `Code += 8` (execLocalVariable 0x141FC107A). exec* handlers often **tail-jump** (`JMP qword ptr [RAX+0x288]` - 0x141FC109D), i.e. no frame bloat. The same dispatcher is duplicated in `CallFunction` (`LEA R13,[0x14491C6B0]` 0x141FC00BE; `CALL [R13+RAX*0x8]` 0x141FC0108); there the terminator is **0x16** (`CMP byte [RAX],0x16` 0x141FC00B5) = EX_EndFunctionParms, after which out-parms are copied and ProcessInternal is called. `ProcessContextOpcode` (0x141FC1FA0, 184 B) is **not an opcode** but a helper: called from `execContext` (0x141FC1F90, the only xref - a UNCONDITIONAL_JUMP); it reads the opcode through GNatives (0x141FC1F9x), then ReadVariableSize and sets `Code += uint32@Code` (0x141FC205x).

GNatives population: 63 static initializers `dynamic initializer for 'UObjectexec<Name>BytecodeTemp'()` (RVAs 0x000A0080 ... 0x000A39C0, size 126-130 B each). Example ('UObjectexecLocalVariableBytecodeTemp', RVA 0x000A00D0, 127 B): guard `CMP byte [0x1448EA529],0`; `MOV ECX,0x20` -> for i in 0x20..1, 8 stores of `&execUndefined` (`GNatives[i*8+j] = &execUndefined`, filler); `if (GNatives[0] != &execUndefined) GNativeDuplicate = 0` (`CMP [0x14491C6B0],RDX; CMOVNE`); `GNatives[0] = &UObject::execLocalVariable` (the opcode binding). Hence **GNatives is exactly 256 slots (2048 bytes)**; the second static of each pair, `...Registar`, calls `UClass::AddNativeFunction(UObject::StaticClass, "execLocalVariable", &execLocalVariable)` - registering the same name in `UClass::FuncMap`.

**Recovered opcode map (read from PE bytecode, not invented):**

| op | exec | op | exec | op | exec |
|---|---|---|---|---|---|
| 0x00 | LocalVariable | 0x24 | ByteConst | 0x4C | PushExecutionFlow |
| 0x01 | InstanceVariable | 0x25 | IntZero | 0x4D | PopExecutionFlow |
| 0x06 | Jump | 0x26 | IntOne | 0x4E | ComputedJump |
| 0x07 | JumpIfNot | 0x27 | True | 0x4F | PopExecutionFlowIfNot |
| 0x09 | Assert | 0x28 | False | 0x50 | Breakpoint* |
| 0x0B | Nothing* | 0x29 | TextConst | 0x51 | InterfaceContext |
| 0x0F | Let | 0x2A | NoObject | 0x52 | InterfaceCast |
| 0x13 | MetaCast | 0x2B | TransformConst | 0x53 | EndOfScript |
| 0x14 | LetBool | 0x2C | IntConstByte | 0x54 | InterfaceToInterface |
| 0x16 | EndFunctionParms | 0x2E | DynamicCast | 0x5A | WireTracepoint* |
| 0x17 | Self | 0x2F | StructConst | 0x5B | SkipOffsetConst |
| 0x19 | Context | 0x31 | SetArray | 0x5C | AddMulticastDelegate |
| 0x1A | Context_FailSilent | 0x34 | UnicodeStringConst | 0x5D | ClearMulticastDelegate |
| 0x1B | VirtualFunction | 0x38 | PrimitiveCast | 0x5E | Tracepoint* |
| 0x1C | FinalFunction | 0x42 | StructMemberContext | 0x5F | LetObj |
| 0x1D | IntConst | 0x43 | LetMulticastDelegate | 0x60 | LetWeakObjPtr |
| 0x1E | FloatConst | 0x44 | LetDelegate | 0x61 | BindDelegate |
| 0x1F | StringConst | 0x48 | LocalOutVariable | 0x62 | RemoveMulticastDelegate |
| 0x20 | ObjectConst | 0x4A | NothingOp4a* | 0x63 | CallMulticastDelegate |
| 0x21 | NameConst | 0x4B | InstanceDelegate | 0x64 | DoubleConst |
| 0x22 | RotationConst | 0x23 | VectorConst | 0x65 | StringLocConst |

`*` - all five debug opcodes point to the common stub 0x001BCBB0 (3 bytes). Vacant slots (remain execUndefined): 0x02, 0x03, 0x04, 0x05, 0x08, 0x0A, 0x0C, 0x0D, 0x0E, 0x10, 0x11, 0x12, 0x15, 0x18, 0x45, 0x46, 0x47, 0x49, 0x55..0x59, 0x66..0xFF. **0x04 is the terminator EX_Return**: its handler is never called (ProcessInternal checks `*Code != 0x04` and exits; CallFunction uses 0x16). Consistency check: the recovered map **exactly matches** the canonical UE4 `EExprToken` (EX_Let=0x0F, EX_LetBool=0x14, EX_DynamicCast=0x2E, EX_EndFunctionParms=0x16, EX_Self=0x17, EX_Context=0x19, EX_EndOfScript=0x53, EX_LetObj=0x5F...). Separately noted: **not a single arithmetic opcode exists in this build** - no `execAdd/Sub/Mul/...` symbols in the PDB, and slots 0x45, 0x46, 0x47, 0x49 are not registered.

### UFunction::Invoke (0x141F867C0)

Signature (per disassembly): `void __fastcall UFunction::Invoke(UFunction* this /*RCX*/, UObject* Obj /*RDX*/, FFrame& Stack /*R8*/, void* RESULT /*R9*/)` - the `ProcessDelegate`/`ProcessEvent`-compatible form of `FNativeFuncPtr`: `void(UObject* Obj, FFrame& Stack, RESULT_DECL)`. Owner: UFunction is an ordinary UObject (`UFunction : UStruct : UField : UObject`); for a concrete UFunction the owner (Outer, +0x20) is the **owning UClass** - walked via the Super chain (UClass+0x30) looking for UInterface (0x141F869F5...0x141F86A20). There is no global "invoke owner" - Invoke is a method of the UFunction instance itself. Bytecode is at `UFunction+0x48`; the frame already carries `Code` (FFrame+0x20): the ctor does `Code = Function->Script` (0x141FA5820/24), and ProcessEvent/CallFunction create a local FFrame from a UFunction* before the call - `Function->Script == Frame->Code` for any properly constructed frame. The convenient points where both UFunction and frame are known: the entry of `Invoke` itself (RCX = UFunction*, R8 = FFrame*) and, even better, **ProcessInternal** - RDX = FFrame*, and `FFrame->Node` (+0x10) is the same UFunction (passed to `GetFunctionCallspace` 0x141FC02B7 and `UFunction::GetReturnProperty` 0x141FC036B). Invoke does **not** write `FFrame->Node` before the call to Func (already set by the ctor), and it additionally saves/restores `FFrame->CurrentNativeFunction` (+0x88) - 0x141F86A8C...0x141F86AB9. Profile: **Invoke 1.89%, ProcessInternal 2.17% of frame**; ProcessInternal > Invoke because into it come both the `Invoke -> Func` path (scripted functions) and the **direct** path `CallFunction -> ProcessInternal` (0x141FC01F4), bypassing Invoke.

### Tracer sketch

Hook point - **`UObject::ProcessInternal` (0x01FC0270), the first 12 bytes.** Justification: hit frequency - once per entry into a scripted UFunction (per BP function) vs once per any UFunction call including native (invoked from every bytecode instruction for Invoke); coverage - a **superset** (both `Invoke->Func` and the direct `CallFunction->ProcessInternal`), while Invoke does not see `CallFunction->ProcessInternal` (0x141FC01F4); input data - ProcessInternal gets `RDX = FFrame*` with `Node` (+0x10) = UFunction, `Code` (+0x20) = bytecode, `Object` (+0x18) = object, vs two registers (RCX=UFunction, R8=FFrame) for Invoke; added cost - lower by ~K times (K = average number of bytecode instructions per BP call); risk - a general detour (no call sites) vs patchable call sites (2). Key argument: **Invoke is semantically "per UFunction call", ProcessInternal is per BP function entry** - the needed granularity at minimal frequency. Hooking GNatives/each exec* is impossible - that frequency is an order of magnitude higher. Lower-risk fallback: hook on Invoke by patching **two** call sites (0x141FBFFA2 from CallFunction, 0x141FC0FA7 from ProcessEvent) - but then the direct path is lost.

What we log: **exactly one thing** - the full UFunction name + a call counter. No arguments, no parameter values, no behavior change. Name at `UFunction+0x18` (FName: ComparisonIndex u32, Number u32). **FName -> str is never done in the hot path**: the ring record is `(timestamp u64, UFunction* u64, ComparisonIndex u32, Number u32)` = 24 bytes; string resolution at flush time via `NamePoolData` (RVA 0x0498A1C8) -> `FNameEntry* = block[ComparisonIndex]`, string at `entry+0x10` (ASCII) or UTF-16 if `*(BYTE*)entry & 1` (see FName::ToString 0x141F4330F-0x141F43338; the same path used by `UObjectBaseUtility::GetName`). "Full name" = the Outer chain: `UFunction->Outer` (+0x20) is a UClass; class name + function name concatenated at flush time (class string from +0x18 of that UClass). **Cache key hash: `(UFunction*, ComparisonIndex)`** - a pair, so address reuse after GC does not produce a false hit.

Buffering: a fixed-size ring buffer in the plugin's `.data` (static array, size fixed at link time - e.g. `1<<20` records x 24 bytes = 24 MB; for a 60-s window at ~50k calls/s, `1<<18` = 6 MB is enough; the size is chosen empirically by calibration). **The write index is thread-local (`__declspec(thread)`), no atomics, no locks.** Ring overflow is recorded by a `dropped` flag (a counter of lost records) - silently losing is not allowed. Call counters: a separate table `slot -> uint64`, accessed by slot index from the direct cache; the hot path only READS it. Flush to disk: a separate plugin thread every N seconds (an RCON command sets N, default 30 s); it works in query mode - stops/swaps the write pointer, serializes raw records + counter dumps, then resolves strings and writes a text report; name resolution is outside the hot path.

Hot-path overhead (cache hit, estimated by instruction count, not measured):

```asm
mov  rax,[rdx+0x10]            ; FFrame->Node
test byte ptr [g_Enabled],0
jz   out
mov  rcx,gs:[g_TlsSlots]       ; per-thread counter base
mov  rdx,[rax+0x18]            ; FName.ComparisonIndex
mov  rsi,rcx; shr rsi,4
and  rsi,8191                  ; direct-mapped cache index (8192 slots)
mov  r8,[rsi*16+cache+0]       ; saved UFunction*
cmp  r8,rax
jne  miss
mov  r8,[rsi*16+cache+4]
cmp  r8,edx
jne  miss
inc  qword ptr [rsi*16+counters+8]
out:
ret
```

About **10-12 instructions, ~5-7 cycles** per hit + ~5-10 cycles of detour overhead (JMP + Indirect Branch Target Buffer). **FName->string on this path: zero.** Baseline: ProcessInternal is 344 bytes of code; per BP function entry it executes a prologue+epilogue with `__security_check_cookie` (~25-30 instructions) plus the dispatcher loop - at least one iteration (~12 instructions) per bytecode instruction; a real BP function runs tens to hundreds of bytecode instructions, i.e. hundreds of instructions per call - a detour pays off once per function. Estimate as % of frame: the hook adds to ProcessInternal (2.17% of frame) about **5-15%** of its cost (a rough upper bound for very short BP functions; typical 3-8%), total **~ +0.07...0.33% of frame = 3-14% of the 1.1% budget, <= 0.17x of Invoke itself (1.89%)**. The target criterion "<5% of 22.8% (i.e. <1.1% of frame)" is **met with a x3...x15 margin**. **Caveat: a calculated estimate, not a measurement** (no profiler/counter offline). It is self-checking: the first tracer run yields `N_PI` = the number of ProcessInternal calls per window; then `overhead % = N_PI x 12_cycles / (T_frame_sec x 3e9) x 100`, and an A/B run (off/on) per the A5 protocol gives the actual delta. **Without that measurement this figure must not be written down as measured.**

Kill switch: RCON commands `bptrace 0|1` (default **0**), `bptrace flush` (force flush), `bptrace reset` (reset counters), `bptrace stat` (dump counters without reset). **By default the detour IS NOT INSTALLED AT ALL**: at load the plugin only registers the RCON command and the point 0x141FC0270; the `E9` patch is applied by `bptrace 1` and removed by `bptrace 0` - literally zero influence in production (no modified bytes -> no influence on instruction cache, branch predictor, CET/ENDBR, no code-change trigger). All state (ring, counters, TLS base) allocated lazily at the first `bptrace 1`. Enable on production only for a 30-60 s window.

Thread-safety requirements: (1) the hot path is read-only - no atomics for reads (x64 atomic 8/16-byte reads); nobody writes the direct cache `UFunction* -> slot` or name tables after warm-up; (2) the slot index is per-thread (`__declspec(thread) uint32 TlsSlotBase;` read once, ~1 cycle on L1); per-thread size fixed (e.g. 4096 slots x 8 bytes = 32 KB) allocated in `DllMain(THREAD_ATTACH)` from VirtualAlloc (not the heap, to avoid depending on engine state); (3) the ring buffer is per-thread, no locks; the flush thread uses `InterlockedExchange` on the "end of window" pointer or reads a copy (writes go only forward - no tearing if copy first, then mark); (4) the cold path (cache miss) is under `SRWLOCK` in exclusive mode; misses decrease monotonically and are bounded by the number of distinct UFunctions (tens of thousands, all created at load); fully excluded during warm-up at the first `bptrace 1` (a walk over all UFunctions); (5) counter merging at flush: `InterlockedExchange64` per counter within the window, then added to the global - dropping counters is unacceptable; (6) TLS in the DLL: static TLS (`__declspec(thread)`), not manual `TlsAlloc` (a TLS index has a module-count limit); in the "off" state TLS is not touched at all; (7) reentrancy: the hook calls no UE API (no FName::ToString, no allocations, no logs) - only its own arrays and Interlocked* - otherwise a recursion risk (a call from a log destructor); (8) no FP/SSE: the hook does not touch XMM so as not to corrupt the SSE context (compile without SSE registers; do not apply `-Oi` to the hook).

Risk class: **MEDIUM.** Why not low: the entry point is the hottest function of the scripting core; an error (a stack shift, clobbering unsaved RBX/RSI/RDI, a wrong trampoline length) manifests **immediately and on 100% of calls**. A 12-byte detour for a 344-byte function is safe by length; ProcessInternal is not a hot-patch candidate and has no `ENDBR64` in those 12 bytes (verified: the first instructions are `PUSH RBX; PUSH RSI; PUSH RDI; SUB RSP,0x80`) - with CET enabled this would require disabling it or a shadow-stack-compatible variant: **a separate item to check before deployment**. Why not high: no behavior change, no arguments, no writes into game memory; by default **not installed at all**; rollback = restoring 12 bytes back from `E9`; the plugin state is only its own buffers. Mitigations: build with a CET-compatible trampoline (or `mov r11,imm64; jmp r11` = 12 bytes, does not touch the stack); remove the ASLR dependency via RVA; run A/B on Genesis with `bptrace 1` for 30-60 s and compare t/s per the A5 protocol.

### A5 explicitly NOT found / not checked

1. The real per-second count of ProcessInternal/Invoke calls was **not measured** - all overhead percentages are instruction-count calculations.
2. The enablement/state of `GFullStackTrace` (0x044909C17) in a working server and the actual cost of enabling `GScriptStack` - not tried.
3. The exact offsets FFrame+0x00..0x0F, +0x40..0x5F, +0x90 and beyond - not determined; the full size of FFrame is not confirmed (assumed 0x90).
4. UObject offsets +0x00, +0x08, +0x10, +0x20 as typed fields - determined only indirectly by usage: +0x08 = 32-bit flags (bit 14 tested in ProcessEvent 0x141FC0Dxx, bit 26 in Invoke 0x141F8697A), +0x10 = UClass* (execDynamicCast 0x141FC339x, Invoke 0x141F8696B), +0x20 = Outer; +0x18 = FName Name - **confirmed directly** (0x141F0FE0, 0x141F86946).
5. `UFunction+0x20` = Outer precisely - an inference from the Super-chain walk in Invoke and Bind, not a PDB type.
6. The runtime contents of `GNatives` - the map was recovered from static initializers in the PE, not read from memory; the match with UE4 EExprToken is a strong but indirect check.
7. How many GNatives slots actually occur in ARK Blueprint bytecode - not checked; a runtime statistical dump is needed.
8. Behavior under CET/shadow stack - not checked (see risk class).
9. No `UObject::exec*` for arithmetic (`execAdd`, `execSub`, `execMul`, `execDiv`, `execLess`, `execJumpIf`, `execSwitch`, `execClassContext`, `execSuper`, `execSeek`, `execPop`, `execDuplicate`, `execStringSwitch`, `execArrayIndex`, `execEmptyArray`) - absent from the PDB and from GNatives; **the reason is undetermined** (bytecode-compiler implementation of this UE version or a removal); the conclusion "arithmetic is not supported" must NOT be drawn.
10. The symbol called by `UObjectBaseUtility::GetName` (0x141F1004 + disp32 -> RVA 0x03C632B0; no entry in `fn`/`sym`) - probably an ICCU-generated helper; FName::ToString itself was found (0x01F432B0 / 0x01F432F0).
11. Whether ProcessContextOpcode is called from anywhere besides execContext - only 2 xrefs (1 call + 1 data), and the data xref is unresolved.
12. `dump_index.json` for ProcessContextOpcode and CallFunction returns `None` (the index is incomplete); all information on them came directly from Ghidra.

## RE session: the join path in the ARK v361 server browser

Disassembled in Ghidra on `v361_ShooterGame.exe` (client), 2026-10-19.

**Conclusion in one paragraph:** the working join goes **not through a direct `Browse`** but through the online session. The bot reproduced only the last step and therefore kept hitting a timeout: the server is a Steam server and the authorization token is issued by the session layer. A direct travel departs with a request carrying no valid token, and the server never completes the handshake.

### Chain (class `UUI_ListSessions`)

| Function | Address | Role |
|---|---|---|
| `SlotButtonSelected` | 141560d70 | only enables the Join button |
| `JoinSelectedSession` | 14154fcf0 | takes the selected list entry; `local_1a8._40_8_ = &JoiningSessionOwnerName` |
| `DoJoinSession` | 141551220 | **the JoinSession call** |
| `QueueJoinSession` | 14154dda0 | join queue |
| `JoinFromQueue` | 14154f5f0 | leaving the queue |
| `RetryJoin` | 14154bc60 | retry |
| `OnJoinSessionComplete` | 14154c9a0 | result; `SaveJoiningSessionName`, FName `SESSIONNAME` |
| `OnJoinTimedOut` | 14154c0b0 | timeout |

`DoJoinSession` (entry point): `UWorld* w` -> `Cast<UShooterGameInstance>(w->GetGameInstance())` -> `AShooterGameSession* gs = gi->GetGameSession()`; `ULocalPlayer* lp = gi->GetFirstGamePlayer()`; `lp->GetPreferredUniqueNetId(pid)`; `FName name(this->JoiningSessionOwnerName)` - session name = owner; for a Steam server this is the SteamID64 string (when JoiningSessionOwnerName is empty, the string 0x14473fcc8 is substituted, which in the binary turns out to be a path from the PDB - i.e. garbage; the proper name always comes from the list entry); then `gs->JoinSession(pid, name, &this->JoiningSessionSearchResult)`.

Requirements for `JoinSession` (ARK SDK, GameState.h:344): two overloads `JoinSession(TSharedPtr<FUniqueNetId,0> UserId, FName SessionName, FOnlineSessionSearchResult* SearchResult)` and `JoinSession(..., int SessionIndexInSearchResults)`, plus `TravelToSession(int ControllerId, FName SessionName)`. The implementation (14102b160) requires: `IOnlineSubsystem::Get()` non-null; the session interface (vtable +0x198) non-null; `UserId->Object != nullptr` - a valid local player FUniqueNetId.

The step after the join - `AGameSession::TravelToSession` (142acfe60): (1) `IOnlineSubsystem::Get()`; (2) `FindSession(SessionName, &HostAddress)` - vtable +800; (3) `APlayerController::ClientTravelInternal(HostAddress)`. The URL is taken from the session's own `HostAddress`, not from a string the player typed.

What the bot already matches: after manual join, the `ctx` command showed a FURL the bot now builds field by field: `proto=unreal host=192.168.8.218 port=7777 valid=1 map=/Game/Maps/TheIslandSubMaps/TheIsland Op[0]=ModId=0 Op[1]=game=/Game/PrimalEarth/CoreBlueprints/TestGameMode.TestGameMode_C`. The engine accepts such a URL (`valid=1`) but the handshake never completes - the session layer is missing.

What is missing for full automation (ArkApi SDK status): `UShooterGameInstance::GetGameSession()` - **present** (GameMode.h:387); `AShooterGameSession::JoinSession(...)` - **present** (GameState.h); a valid player `TSharedPtr<FUniqueNetId>` - **absent** (`GetPreferredUniqueNetId` not declared); `FOnlineSessionSearchResult` - **absent** (only an empty forward-decl); `IOnlineSubsystem` - **empty struct** (Base.h:184), methods only via the vtable; `IOnlineSubsystem::GetSessionInterface` (vtable +0x198) - not declared, but known from the disassembler.

Implementation options: (1) **via the UI class** - find/create `UUI_ListSessions`, fill `EntryWidgets`/`SearchSettings`, call `JoinSelectedSession()`; requires none of the missing types but needs an entry point to the widget and list population; (2) **via the session layer directly** - take `IOnlineSubsystem` from `AShooterPlayerController::OnlineSubField()` (Actor.h:2405), invoke the sessions vtable method, implement `IOnlineSession::JoinSession` by hand; requires knowing the layout of `FOnlineSessionSearchResult` and `FUniqueNetIdUInt64`; (3) **assemble `FOnlineSessionSearchResult` manually and call the first JoinSession** - struct layout from the PDB (present in the binary), `FUniqueNetIdUInt64` described in UE.h:272; the most direct path but requires careful reconstruction. Any option requires RE work; only the analysis has been done so far.

## Summary

Join automation: the correct path is `UUI_ListSessions` -> `DoJoinSession` 141551220 -> `AShooterGameSession::JoinSession` (Steam session name = SteamID64) -> `TravelToSession` 142acfe60 -> `ClientTravelInternal(HostAddress)`; a direct Browse cannot work (no token). IsA: 1870 real sites, a hook covers 73%; `iscache` overlap zero. Overlap O(n^2): refuted in `ServerOctreeOverlapActors`, the real pair is `BeginComponentOverlap` Emplace/AddUnique (stride 0x98). Inventory: `GetItemTemplateQuantity` O(N) with no cache; 74 call sites in 57 functions but only 5 narrow per-tick paths; cluster 275 samples = 0.90% wall / 6.45% executed; the LOW-risk bucket-per-exact-class cache with 4 invalidation hooks (0x7AC9A0, 0x7AFCA0, 0x80D4C0, 0x7F4D60) yields ~0.72% wall at 80% reduction. SaveWorld: the 3.9-4.3 s freeze is serialization into memory; writes already async on a TaskGraph worker; no incremental-saving machinery exists. BP tracer: hook `ProcessInternal` 0x01FC0270 (no call sites; `Func` = &ProcessInternal for any scripted UFunction); overhead estimated +0.07-0.33% of frame, kill switch `bptrace 0|1`, risk MEDIUM, CET check required. Report hygiene: no starting save before P0/P1 on any map; the reviewer's premise refuted. ARCH.md created (5 active optimizations, 4 new patches, CONTAMINATED monitoring, perf.selftest spec).
