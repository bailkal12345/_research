# A3. Inventory: GetItemTemplateQuantity / IsValidForCrafting

Image: `C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe` (v361.7, image base `0x140000000`).
Symbols: `C:\Dev\_research\v361.sqlite`, table `fn(name,rva,size,tag)`.
Decompilation/listing/xref: Ghidra 7.0.0, program `/v361_ShooterGameServer.exe`.
Profile: `...\ArkApi\Plugins\TickProf\prof_298529359.bin` (30 463 samples).

---

## 1. Symbol table

### 1.1 Targets

| Symbol | RVA | Size | VA | Note |
|---|---|---|---|---|
| `UPrimalInventoryComponent::GetItemTemplateQuantity` | `0x777E70` | 1305 | `0x140777E70` | pure function, 74 static call sites |
| `UPrimalInventoryComponent::execGetItemTemplateQuantity` | `0x179BFD0` | 914 | `0x14179BFD0` | Blueprint-thunk (74th call site) |
| `Z_Construct_UFunction_UPrimalInventoryComponent_GetItemTemplateQuantity` | `0x152C4A0` | 2379 | `0x14152C4A0` | source of names and parameter order |
| `UPrimalItem::IsValidForCrafting` | `0x81D4B0` | 1665 | `0x14081D4B0` | **virtual**, vtable slot `0x3A8` |
| `UPrimalItem::execIsValidForCrafting` | `0x17AA660` | 47 | `0x1417AA660` | `MOV RAX,[RCX]; CALL [RAX+0x3A8]` @ `+0x21` |
| `UPrimalItem::BPIsValidForCrafting` | `0x1366680` | 110 | `0x141366680` | → `ProcessEvent` (vtable `+0x1E0`) |
| `Z_Construct_UFunction_UPrimalItem_IsValidForCrafting` | `0x149D210` | 658 | | |
| `UPrimalItem::GetItemQuantity` | `0x7F2F70` | 17 | `0x1407F2F70` | virtual, slot `0x2E8`; `return this+0x648` |

### 1.2 Related symbols `UPrimalInventoryComponent::*`

| Symbol | RVA | Size | Role |
|---|---|---|---|
| `GetItemTemplateQuantity` | `0x777E70` | 1305 | target |
| `GetCraftQueueResourceCost` | `0x777960` | 1282 | nested Q×R loop + `FindItem` |
| `GetItemOfTemplate` | `0x7760E0` | 4324 | linear search of a single item |
| `IncrementItemTemplateQuantity` | `0x775310` | 2388 | mutator |
| `FindItem` | `0x75F990` | 6154 | mutator/search |
| `HasResources` | `0x79A350` | 351 | loop R × `GetItemTemplateQuantity` |
| `execHasResources` | `0x179BAC0` | 203 | Blueprint only |
| `HasItemOfSameType` | `0x75F700` | 648 | — |
| `HasItemsEquipped` | `0x794970` | 711 | — |
| `AllowAddInventoryItem` | `0x754580` | 1203 | calls `GetItemTemplateQuantity` |
| `AddItem` | `0x754A40` | 1644 | mutator (→ `UPrimalItem::AddToInventory`) |
| `RemoveItem` | `0x7574B0` | 832 | mutator (→ `UPrimalItem::RemoveItemFromInventory`) |
| `EjectItem` | `0x7577F0` | 953 | mutator |
| `TickComponent` | `0x77B3C0` | 794 | **per-tick** |
| `TickCraftQueue` | `0x77B6E0` | 936 | **per-tick** |
| `IsValidCraftingResource` | `0x796BF0` | 339 | called from `IsValidForCrafting` |
| `RemoteInventoryAllowAddItems` | `0x766F80` | 3240 | transfer/trade |
| `ConsumeResources` | `0x79A4B0` | 458 | mutator |
| `LoadedFromSaveGame` | `0x781330` | 7642 | mass restore |
| `InitializeInventory` | `0x762F20` | 5184 | rebuild |
| `ServerCraftItem` | `0x7798E0` | 992 | server crafting |
| `ServerMakeRecipeItem_Implementation` | `0x773640` | 5985 | server crafting |

### 1.3 Related symbols `UPrimalItem::*` (crafting/resources)

| Symbol | RVA | Size | Calls `GetItemTemplateQuantity`? |
|---|---|---|---|
| `MeetBlueprintCraftingRequirements` | `0x7F8710` | 4057 | yes, 1× (+ `GetCraftQueueResourceCost`) |
| `MeetRepairingRequirements` | `0x7FB320` | 1422 | yes, 2× |
| `TestMeetsCraftingRequirementsPercent` | `0x7F96F0` | 1560 | yes, 2× |
| `ConsumeCraftingRequirementsPercent` | `0x7F9D10` | 1598 | no (via `IncrementItemTemplateQuantity`) |
| `GetCraftingRequirementsString` | `0x7FA350` | 4034 | yes, 2× |
| `GetRepairingRequirementsString` | `0x7FB8B0` | 9422 | yes, **7×** |
| `IterateCraftingRequirements` | `0x7FE790` | 882 | yes, 1× |
| `IterateRepairingRequirements` | `0x7FDD80` | 2569 | yes, 3× |
| `MakeRepairingRequirementsString` | `0x831F60` | — | yes, 1× |
| `GetMiscInfoString` | `0x7F30B0` | 5024 | yes, 1× (virtual, slot `0x2F0`) |
| `CheckForInventoryDupes` | `0x826100` | 13506 | called from `GetItemTemplateQuantity` |
| `TickCraftingItem` | `0x80B760` | 5227 | virtual, slot `0x338` — **per-tick** |
| `CanCraft` | `0x816970` | 5715 | virtual, slot `0x350` |
| `CanFullyCraft` | `0x8033C0` | 482 | indirectly (`MeetBlueprintCraftingRequirements`) |
| `GetMaximumAdditionalCrafting` | `0x824D40` | 446 | indirectly |
| `SetQuantity` | `0x80D4C0` | 8562 | quantity mutator |
| `IncrementItemQuantity` | `0x7F4D60` | 8631 | quantity mutator |
| `AddToInventory` | `0x7AC9A0` | 12407 | **array mutator** |
| `RemoveItemFromInventory` | `0x7AFCA0` | 9604 | **array mutator** |
| `calcResourceQuantityRequired` | `0x7F1490` | 1126 | — |

Adjacent low-level:

| Symbol | RVA | Size |
|---|---|---|
| `UObjectBaseUtility::IsA` | `0x1FCDAB0` | 36 |
| `UStruct::IsChildOf` | `0x1DCC80` | 25 |
| `UPrimalItem::StaticClass` | `0x1DCC70` | 12 (jmp → `GetPrivateStaticClass` `0x1364F00`, 69 B) |
| `UPrimalItem::GetPrivateStaticClass` | `0x1364F00` | 69 |
| `UPrimalItem::IsBroken` | `0x7D0900` | 95 |
| `UPrimalItem::GetDurabilityPercentage` | `0x801750` | 149 |
| `FWeakObjectPtr::IsValid` | `0xDA8030` | 105 |
| `FWeakObjectPtr::Get` | `0x1FD7730` | 94 |

### 1.4 vtable `UPrimalItem::$_VTable` (RVA `0x3FD2058`, in `.rdata`)

Verified by reading the file directly (4 copies of the pointer to `IsValidForCrafting`:
RVAs `0x3FD2400`, `0x3FD2870`, `0x3FD2CE0`, `0x3FDC9C0`):

| Slot | Value | Symbol |
|---|---|---|
| `+0x000` | `0x1407A6770` | `UPrimalItem::`scalar deleting destructor'` |
| `+0x2E8` | `0x1407F2F70` | `UPrimalItem::GetItemQuantity` |
| `+0x2F0` | `0x1407F30B0` | `UPrimalItem::GetMiscInfoString` |
| `+0x338` | `0x14080B760` | `UPrimalItem::TickCraftingItem` |
| `+0x350` | `0x140816970` | `UPrimalItem::CanCraft` |
| `+0x3A0` | `0x14081AA90` | `UPrimalItem::CanSpoil` |
| `+0x3A8` | `0x14081D4B0` | **`UPrimalItem::IsValidForCrafting`** |

Separately: `0x144A1ED38` (the only "non-vtable" DATA xref on `IsValidForCrafting`) is
a `.pdata` record `RUNTIME_FUNCTION{Begin=0x81D4B0, End=0x81DB31, Unwind=0x435A5E0}`, not
a reference.

---

## 2. What exactly is scanned

### 2.1 `UPrimalInventoryComponent::GetItemTemplateQuantity` (`0x777E70`, 1305 B)

Signature (parameter names recovered from `Z_Construct_UFunction_...` @ `0x14152C4A0`
plus the reading order in `execGetItemTemplateQuantity` @ `0x179BFD0`):

```c
int UPrimalInventoryComponent::GetItemTemplateQuantity(
      UPrimalInventoryComponent* this,
      TSubclassOf<UPrimalItem>  ItemTemplate,            // param_1
      UPrimalItem*               IgnoreItem,              // param_2
      bool                       bIgnoreBlueprints,       // param_3
      bool                       bCheckValidForCrafting,  // param_4
      bool                       bRequireExactClassMatch, // param_5
      bool                       bForceCheckForDupes);    // param_6
```

Body:

1. `ItemTemplate == nullptr` → `return 0`; otherwise `UPrimalItem::StaticClass()`
   (`0x1401DCC70`) + `UStruct::IsChildOf` (`0x1401DCC80`) — if the class is not
   `UPrimalItem`, also `0`.
2. **Two duplicated loops over `this->InventoryItems`** (`TArray<UPrimalItem*>`, offset
   **in the object `0x118`**, confirmed by `MOV RAX,[RSP+0xE0]; ADD RAX,0x118` @ `0x140777EF6`):
    * `bForceCheckForDupes == false` → **forward pass** `0 … ArrayNum-1` (labels `LAB_140777F39…`);
    * `bForceCheckForDupes == true` → **reverse pass** `ArrayNum-1 … 0` (labels `LAB_140778155…`)
      + the extra filter `UPrimalItem::CheckForInventoryDupes(item) || (item->OwnerInventory == this)`
      (`0x140826100`, `operator==` `0x1401FF150`).
3. Per item:
    * check `!= nullptr`;
    * if `bRequireExactClassMatch` and `!item->bOverrideExactClassCraftingRequirement` → compare the **exact** `item->Class` (`item+0x0`) with `ItemTemplate`;
    * otherwise → `UStruct::IsChildOf(ItemTemplate, UPrimalItem::StaticClass())` + `UObjectBaseUtility::IsA(item, ItemTemplate)` (`0x141FCDAB0`) — **a linear walk of the `SuperStruct` chain**;
    * filters: `bIgnoreBlueprints && item->bIsBlueprint`, `IgnoreItem && item == IgnoreItem`;
    * if `bCheckValidForCrafting` → **a virtual call `[vtable+0x3A8]` = `UPrimalItem::IsValidForCrafting`** (addresses `0x1407780F7` and `0x140778319`);
    * `sum += [vtable+0x2E8]()` = `UPrimalItem::GetItemQuantity` (addresses `0x140778111` and `0x140778366`).

**No cache/memoization**: not a single access to a global/static variable, not a single
state field. The function recomputes the sum fully on every call. There are no indexes,
hash tables or auxiliary structures in `UPrimalInventoryComponent` for this.

### 2.2 `UPrimalItem::IsValidForCrafting` (`0x81D4B0`, 1665 B)

The sequence of early exits:

1. `!bValidCraftingResource` → `false`;
2. `bIsBlueprint` → `false`;
3. `UPrimalItem::IsBroken(this)` (`0x1407D0900`) → `false`;
4. `bUseItemDurability && GetDurabilityPercentage() < MinDurabilityForCraftingResource` → requires that `OwnerInventory` resolve to a non-null object with the flag `(uint)(Owner+0x50) >> 6 & 1`, otherwise `false`;
5. `bPreventCraftingResourceAtFullDurability && GetDurabilityPercentage() >= 1.0f` → requires an `OwnerInventory` with the flag `(uint)(Owner+0x50) >> 6 & 1`, otherwise `false`;
6. `OwnerInventory != null` → `UPrimalInventoryComponent::IsValidCraftingResource(OwnerInventory, this)` (`0x140796BF0`) → if `false`, then `false`. Inside — **two virtual calls on the Owner** (`+0x888`, `+0xCC8`) and an optional `BPIsValidCraftingResource`;
7. `bUseBPIsValidForCrafting` → `BPIsValidForCrafting(this)` (`0x14081DD00`, `0x141366680`) → **`ProcessEvent` (slot `+0x1E0`), a full entry into the Blueprint VM**;
8. `true`.

Total per item: **up to 3× `FWeakObjectPtr::IsValid` + 3× a dereference of `GUObjectArray`**,
**2–3× `GetDurabilityPercentage`**, up to **2 entries into the Blueprint VM**
(`BPIsValidForCrafting` and `BPIsValidCraftingResource`).

---

## 3. Complexity

| Scenario | Formula |
|---|---|
| One `GetItemTemplateQuantity` | **O(N)** — one linear pass over `InventoryItems` (N = `ArrayNum`), per-item constant: 1–2× `StaticClass()`, 1× `IsChildOf()`, 1× `IsA()` (a `SuperStruct` walk), optionally 1× `IsValidForCrafting()` (1665 B) + 1× `GetItemQuantity()` |
| `bForceCheckForDupes=true` | the same + `CheckForInventoryDupes` (13506 B) per item |
| `UPrimalItem::MeetBlueprintCraftingRequirements` (`0x7F8710`) | a loop over `CraftingResourceRequirements` (**R**) × `GetItemTemplateQuantity` → **O(R·N)** |
| `UPrimalItem::MeetRepairingRequirements` (`0x7FB320`) | **O(R·N)** (2 call sites) |
| `UPrimalInventoryComponent::HasResources` (`0x79A350`) | **O(R·N)** |
| `UPrimalItem::TestMeetsCraftingRequirementsPercent` (`0x7F96F0`) | **O(R·N)** (2 call sites) |
| `GetCraftingRequirementsString` / `GetRepairingRequirementsString` | **O(R·N)**, and the repairing string has 7 call sites |
| `GetCraftQueueResourceCost` (`0x777960`) | **O(Q·(N_find + R))**, Q = `ItemCraftQueueEntries` |
| `TickCraftingItem` per tick | up to **3×** `MeetBlueprintCraftingRequirements` + 1× `MeetRepairingRequirements` → **O(R·N) per tick per active blueprint** |
| `TickCraftQueue` per tick | per repair-queue entry → `MeetRepairingRequirements` → **O(R·N) per tick per entry** |

There are no nested loops "inside GetItemTemplateQuantity" — the nesting appears at the
caller level (crafting/repair/inventory UI). This matters for optimization: **the
bottleneck is not the pass itself but the cost of filtering one item**
(`IsA` + `IsValidForCrafting`).

---

## 4. All call sites and periodicity

### 4.1 `GetItemTemplateQuantity` — 74 direct call sites in 57 functions

Full list (call-site address → containing function; all from `.text`):

| Call site | Containing function | Periodicity |
|---|---|---|
| `0x2D2CC8` | `UHexagonTradableOption::GetAmountInInventory` (`0x2D2C60`) | per trade click |
| `0x38821F` | `AMissionType::RemoveItemsFromInventory_Balanced` (`0x387FC0`) | per mission event |
| `0x38A6A6` | `AMissionType::CountInventoryItems` (`0x38A610`) | per mission event |
| `0x38A815` | `AMissionType::CountInventoryItemsFromAllPlayersInMission` (`0x38A6B0`) | per mission event |
| `0x3EFE57` | `UPrimalAbility::CanConsumeFuel` (`0x3EFC40`) | per ability tick |
| `0x3F073A` | `UPrimalAbility::ConsumeFuel` (`0x3EFE80`) | per event |
| `0x3F1327` | `UPrimalAbility::GetAvailableFuelConfig` (`0x3F11C0`) | on demand |
| `0x3F14AC` | `UPrimalAbility::GetAvailableFuel` (`0x3F13A0`) | on demand |
| `0x6A8383` | `APrimalDinoCharacter::TamedDinoUnstasisConsumeFood` (`0x6A75C0`) | per event (unstasis) |
| `0x7547D4` | `UPrimalInventoryComponent::AllowAddInventoryItem` (`0x754580`) | **every add attempt** |
| `0x767B3B` | `UPrimalInventoryComponent::RemoteInventoryAllowAddItems` (`0x766F80`) | per transfer/trade RPC |
| `0x79A491` | `UPrimalInventoryComponent::HasResources` (`0x79A350`) | **Blueprint (exec `0x179BAC0`), O(R·N)** |
| `0x7F395E` | `UPrimalItem::GetMiscInfoString` (`0x7F30B0`, virtual `0x2F0`) | per UI/info request |
| `0x7F9586` | `UPrimalItem::MeetBlueprintCraftingRequirements` (`0x7F8710`) | **see 4.3** |
| `0x7F99F3`, `0x7F9CEA` | `UPrimalItem::TestMeetsCraftingRequirementsPercent` (`0x7F96F0`) | inventory opening/multi-use |
| `0x7FAA1D`, `0x7FAD85` | `UPrimalItem::GetCraftingRequirementsString` (`0x7FA350`) | tooltip opening |
| `0x7FB6F2`, `0x7FB889` | `UPrimalItem::MeetRepairingRequirements` (`0x7FB320`) | **see 4.3** |
| `0x7FC058`, `0x7FC317`, `0x7FC794`, `0x7FCF59`, `0x7FD289`, `0x7FD774`, `0x7FDAA5` | `UPrimalItem::GetRepairingRequirementsString` (`0x7FB8B0`) | tooltip opening (7×) |
| `0x7FE05C`, `0x7FE39A`, `0x7FE68C` | `UPrimalItem::IterateRepairingRequirements` (`0x7FDD80`) | tooltip (3×) |
| `0x7FE982` | `UPrimalItem::IterateCraftingRequirements` (`0x7FE790`) | tooltip |
| `0x83247E` | `UPrimalItem::MakeRepairingRequirementsString` (`0x831F60`) | tooltip |
| `0x8BDBD7` | `APrimalShip::CanConsumeFuel` (`0x8BD9F0`) | per ship tick |
| `0x8BDFEC`, `0x8BE069` | `APrimalShip::ConsumeFuel` (`0x8BDC00`) | per tick/event |
| `0x8BE49D` | `APrimalShip::GetCurrentFuelInterval` (`0x8BE300`) | per tick |
| `0x8BE898` | `APrimalShip::CacheFirstFoundShipFuel` (`0x8BE530`) | per event |
| `0x8BEEDE` | `APrimalShip::UpdateCachedFuelInfo` (`0x8BECC0`) | per event |
| `0x8E27A3` | `APrimalStingerShip::CanConsumeFuel` (`0x8E2610`) | per tick |
| `0x8E2B58`, `0x8E2BC5` | `APrimalStingerShip::ConsumeFuel` (`0x8E27D0`) | per tick/event |
| `0x8E2FD9` | `APrimalStingerShip::GetCurrentFuelInterval` (`0x8E2E50`) | per tick |
| `0x8E324A` | `APrimalStingerShip::CacheFirstFoundShipFuel` (`0x8E3070`) | per event |
| `0x8E362A` | `APrimalStingerShip::UpdateCachedFuelInfo` (`0x8E3460`) | per event |
| `0x94E225` | `APrimalStructure::GetMultiUseEntries` (`0x94BE80`) | structure inventory opening |
| `0x94FA9D` | `APrimalStructure::TryMultiUse` (`0x94F790`) | per player action |
| `0x9BD9E7` | `APrimalStructureItemContainer::NotifyItemAdded` (`0x9BD750`) | per event |
| `0x9BE0F6` | `APrimalStructureItemContainer::NotifyItemRemoved` (`0x9BDDD0`) | per event |
| `0x9BE44E`, `0x9BE55F` | `APrimalStructureItemContainer::RefreshFuelState` (`0x9BE2E0`) | per event |
| `0x9CBD15` | `APrimalStructureItemContainer_CropPlot::AllowRemoteAddItemToInventory` (`0x9CBBA0`) | per event |
| `0x9D3C51` | `APrimalStructureItemContainer_CropPlot::GetPhaseInventoryItemCount` (`0x9D3AA0`) | per event |
| `0x9D4E74` | `APrimalStructureItemContainer_CropPlot::RefreshFertilized` (`0x9D4E20`) | per event |
| `0x9D50B0` | `APrimalStructureItemContainer_CropPlot::NotifyItemRemoved` (`0x9D5020`) | per event |
| `0x9D5213` | `APrimalStructureItemContainer_CropPlot::NotifyItemAdded` (`0x9D5160`) | per event |
| `0x9DACFD` | `APrimalStructureItemContainer_CropPlot_VisualItems::NotifyItemRemoved` (`0x9DABB0`) | per event |
| `0x9DAF0B` | `APrimalStructureItemContainer_CropPlot_VisualItems::NotifyItemAdded` (`0x9DADB0`) | per event |
| `0x9DF7CA` | `APrimalStructureItemContainer_VisualItems::NotifyItemRemoved` (`0x9DF6B0`) | per event |
| `0x9DFB68` | `APrimalStructureItemContainer_VisualItems::NotifyItemAdded` (`0x9DFA40`) | per event |
| `0x9ECDD7` | `APrimalStructurePlacer::Tick` (`0x9ECC80`, +`0x157`) | **per-tick, while the placement "ghost" is active** |
| `0x9F6484` | `APrimalStructurePlacer::FinalStructurePlacement` (`0x9F3E30`) | per placement event |
| `0xA2B3E3`, `0xA2B473` | `APrimalStructureTurret::GetAmmoNearby` (`0xA2A950`) | **per turret tick** (see 4.3) |
| `0xA3F05F` | `APrimalStructureTurret::UpdateNumBullets` (`0xA3F020`) | per event |
| `0xA45B81` | `APrimalStructureTurretBallista::DoFire` (`0xA45AA0`) | per shot |
| `0xA544D9` | `APrimalStructureTurretBallista::DoFireProjectile` (`0xA54060`) | per shot |
| `0xA58CE2`, `0xA591B4` | `APrimalStructureTurretBallista::GetAmmoNearby` (`0xA58C20`) | per event |
| `0xA5969F`, `0xA598AC` | `APrimalStructureTurretBallista::GetAmmoAmount` (`0xA59640`) | **per ballista tick** (via `CanFire`/`CanReload`) |
| `0xAACF98` | `APrimalWeaponBoomerang::OnBoomerangReturn` (`0xAACCC0`) | per event |
| `0xF4D680` | `AShooterWeapon::RefreshAmmoItemQuantity` (`0xF4D480`) | from Blueprint |
| `0xFEFCFD` | `UStructuresPlus::SP_GetInventoryCapacityForItem` (`0xFEFAB0`) | on request |
| `0x179C341` | `UPrimalInventoryComponent::execGetItemTemplateQuantity` (`0x179BFD0`) | **from Blueprint graphs** |

### 4.2 `UPrimalItem::IsValidForCrafting` — call sites

**There are NO direct (static) calls in the binary (0)** — verified with an `E8 rel32`
scanner over the entire `.text`. All 5 DATA-xrefs: 1 — a `.pdata` record (`0x144A1ED38`),
4 — vtable copies (`0x144A1ED38`-family: RVAs `0x3FD2400`, `0x3FD2870`, `0x3FD2CE0`,
`0x3FDC9C0`).

Actual entry points:

| Address | From | Periodicity |
|---|---|---|
| `0x1407780F7` | `GetItemTemplateQuantity`, forward pass, `bCheckValidForCrafting==true` | inherits the caller's periodicity |
| `0x140778319` | `GetItemTemplateQuantity`, reverse pass (`bForceCheckForDupes`) | same |
| `0x1417AA681` | `execIsValidForCrafting` (`0x17AA660`) | from Blueprint |

Both calls from `GetItemTemplateQuantity` happen **per inventory item** when
`bCheckValidForCrafting==true`. This is exactly the value that
`MeetBlueprintCraftingRequirements` passes:

```
GetItemTemplateQuantity(inv, ItemClass, /*IgnoreItem=*/this,
                        /*bIgnoreBlueprints=*/true,
                        /*bCheckValidForCrafting=*/true,   // <—
                        bRequireExactClassMatch,
                        /*bForceCheckForDupes=*/false);
```

while `MeetRepairingRequirements`, `HasResources`, `TestMeetsCraftingRequirementsPercent`,
`GetCraftingRequirementsString` pass `bCheckValidForCrafting = false` — there
`IsValidForCrafting` is **not** called.

### 4.3 CRITICAL: per-tick or per-event?

**Not "for every actor on every tick".** There is no direct call from a generic actor
tick. There are exactly five per-tick paths, and all are narrow:

1. **`UPrimalInventoryComponent::TickComponent` (`0x77B3C0`, 794 B) → `TickCraftQueue`
   (`0x77B6E0`) → `UPrimalItem::MeetRepairingRequirements` (`0x7FB320`,
   call `0x77B996` `+0x2B6`) → 2× `GetItemTemplateQuantity` per requirement.**
   Gates: `bUseCraftQueue != 0`, non-empty `ItemCraftQueueEntries`, `CraftingItems`
   empty. I.e. **only when there is an active repair queue**.
2. **`TickComponent` → for each element of `CraftingItems`, the virtual
   `UPrimalItem::TickCraftingItem` (slot `0x338`) → up to 3×
   `MeetBlueprintCraftingRequirements` (`0x80C077`, `0x80C2B8`, `0x80C54A`) +
   1× `MeetRepairingRequirements` (`0x80BCF9`).**
   Gate: `CraftingItems` contains only actively crafting blueprints. I.e. **per active
   crafting job — every tick**.
3. **`APrimalStructureTurret::Tick` (`0xA39740`) → `APrimalStructureTurret::GetAmmoNearby`
   (`0xA2A950`, call `0xA3A129` `+0x9E9`) → 2× `GetItemTemplateQuantity`.**
   Every turret, every tick (the call site is behind a conditional jump).
4. **`APrimalStructureTurretBallista::Tick` (`0xA4CE60`) → `CanFire` (`0xA532E0`,
   call `0xA4FE93` `+0x3033`) → 2× `GetAmmoAmount` (`0xA59640`) →
   `GetItemTemplateQuantity`.** Also `CanReload` (`0xA53880`) and `UpdateAmmoCount`
   (`0xA53AB0`). Every ballista, every tick.
5. **`APrimalStructurePlacer::Tick` (`0x9ECC80`, `+0x157`).** Only while the player
   drags a placement ghost.

The remaining 69 call sites are per-event (item add/remove, inventory opening,
transfer/trade RPC, tooltip) or from Blueprint graphs.

The profile confirms this: `prof_298529359.bin` contains
`UPrimalItem::TickCraftingItem` (19 samples) and
`UPrimalItem::MeetBlueprintCraftingRequirements` (19 samples) — i.e. paths 1–2 are
actually active in steady state.

A separate caveat: `UUI_*`, `UPrimalItemToolTipWidget::InitToolTip`,
`UDataListEntryButton_PrimalItem::DrawItemPart_Background`,
`UInventoryPanelWidget::OnInventoryItemDoubleClicked` are present in this binary
(the server build contains all UI code), but on a dedicated server they are **not
executed**.

---

## 5. Optimization sketch: index/cache

### 5.1 Where to store

The `InventoryItems` array lives **in the component**, not in the actor:
`UPrimalInventoryComponent` + `0x118` (`TArray<UPrimalItem*>`; `+0x0` = data,
`+0x8` = ArrayNum, `+0xC` = ArrayMax). Therefore the index state must hang **on the
component** (a side-map `UPrimalInventoryComponent* → FInvIndex`), not on the actor and
not globally:

* the player, each tamed dino, each container structure, each turret has its own
  component and thus its own index;
* `GetItemTemplateQuantity` is very often called with the component **resolved from
  `item->OwnerInventory`** (e.g. `MeetBlueprintCraftingRequirements` `0x7F8710`
  dereferences `OwnerInventory` when `param_1 == nullptr`), so the index should be looked
  up by the passed `this`, not by the actor/item.

### 5.2 Structure

Not "one sum per class" but **a bucket per exact class** — otherwise
`bRequireExactClassMatch` (items have the instance flag
`bOverrideExactClassCraftingRequirement`) and `bIgnoreBlueprints` (`bIsBlueprint` —
also an instance flag) cannot be accounted for correctly.

```c
struct FInvBucket {                        // per EXACT UClass of an item
    TArray<UPrimalItem*, TInlineAllocator<8>> Items;   // or just a counter + ptr array
    int32 TotalQuantity;      // sum GetItemQuantity()
    int32 ExactClassQuantity; // sum over items with !bOverrideExactClassCraftingRequirement
    int32 NonBlueprintQty;    // sum over items with !bIsBlueprint
    uint32 Gen;               // lazy invalidation
};

struct FInvIndex {
    uint32 Gen;                            // monotonic counter
    uint32 ItemsGen;                       // changes at SetQuantity/IncrementItemQuantity
    TMap<UClass*, FInvBucket> ByClass;     // key — exact class
    TArray<UClass*, TInlineAllocator<8>>   // derived cache "which buckets match":
        , TInlineAllocator<8>> MatchCache;// UClass* of the query -> bucket list
};
```

Query `GetItemTemplateQuantity(ItemTemplate, …)`:

1. if `ByClass.Num() == 0` → 0 (fast exit, no worse than the current code);
2. take from `MatchCache` (or rebuild in O(number of distinct classes)) the list of
   buckets whose class `IsA(ItemTemplate)`;
3. walk **only those**, applying the remaining predicates (`bIsBlueprint`,
   `item == IgnoreItem`, `IsValidForCrafting`) to the concrete items.

The number of distinct classes in a real inventory is usually 3–15, whereas N is tens
and hundreds. The gain is replacing O(N) with O(number of classes + number of matching
items).

### 5.3 Hook points for invalidation

| Action | Mutator function | RVA / size | Number of call sites |
|---|---|---|---|
| **addition to the array** | `UPrimalItem::AddToInventory` | `0x7AC9A0` / 12407 | **1** (`UPrimalInventoryComponent::AddItem` `0x754A40` `+0x362`) |
| **removal from the array** | `UPrimalItem::RemoveItemFromInventory` | `0x7AFCA0` / 9604 | **5**: `RemoveItem` `0x7575B7`, `EjectItem` `0x757897`, `ClientStartReceivingItems` `0x75EEA5` and `0x75EF19`, `APrimalStructure::PickupStructureAndDependingLinkedStructures` `0x97B342` |
| **quantity change** | `UPrimalItem::SetQuantity` | `0x80D4C0` / 8562 | 7 |
| **quantity change** | `UPrimalItem::IncrementItemQuantity` | `0x7F4D60` / 8631 | 15 |
| **full rebuild** | `UPrimalInventoryComponent::LoadedFromSaveGame` | `0x781330` / 7642 | — |
| | `UPrimalInventoryComponent::InitializeInventory` | `0x762F20` / 5184 | — |
| | `UPrimalInventoryComponent::InitDefaultInventory` | `0x762010` / 3590 | — |
| | `UPrimalInventoryComponent::OnComponentCreated` | `0x796D50` / 1653 | — |

All other increasers (`UPrimalInventoryComponent::IncrementItemTemplateQuantity`
`0x775310`, `ConsumeResources` `0x79A4B0`, `ServerSplitItemStack_Implementation`
`0x77C600`, `ServerMergeItemStack_Implementation` `0x77CBF0`,
`ServerForceMergeItemStack_Implementation` `0x77D0B0`, `TransferAllItemsToInventory*`,
trade via `AShooterPlayerController::Server*RemoteInventory*`) transitively go through
these four points — they do not need separate hooks.

**The minimal safe hook — intercept 4 addresses** (`0x7AC9A0`, `0x7AFCA0`, `0x80D4C0`,
`0x7F4D60`) and rebuild/update the bucket of the component the call came from.

### 5.4 Invalidation risk — by data types

| Risk source | Assessment |
|---|---|
| Items in backpacks / containers / on dinos | Each has its **own** `UPrimalInventoryComponent` and hence its own index. No problem if the index is addressed by component, not by actor |
| `IsValidForCrafting` is **not inventory state** | Depends on durability (`GetDurabilityPercentage`), `IsBroken`, `bPreventCraftingResourceAtFullDurability`, on `OwnerInventory` (the owner changes at `TransferItemToInventory`/pickup), on the parent structure (`bUseParentStructureIsValidCraftingResource` → `IsValidCraftingResource` `0x796BF0`), on the Blueprint (`bUseBPIsValidForCrafting` → `ProcessEvent`). **None of these mutate `InventoryItems`** → the "sum of only craft-valid items" cannot be cached without separate durability-based invalidation |
| Trading / transfer between inventories | Goes through `AddItem`/`RemoveItem` → `AddToInventory`/`RemoveItemFromInventory`, covered |
| Crafting / repair | `ConsumeResources`, `IncrementItemTemplateQuantity`, `FinishCraftingBlueprint`, `RepairItem` → go through `IncrementItemQuantity`/`RemoveItemFromInventory`, covered |
| Load/save | `LoadedFromSaveGame` + `ClientStartReceivingItems` — mass insertion, a rebuild is needed, not a point edit |
| Blueprint visibility | The function is exported as a UFunction (`execGetItemTemplateQuantity` `0x179BFD0`) — any semantic change is observable in scripts |

### 5.5 What exactly breaks with a stale cache

1. **Understated** → `MeetBlueprintCraftingRequirements` returns `false` → in
   `UPrimalInventoryComponent::TickCraftQueue` (`0x77B6E0`, branch `+0x2B6`), when
   `MeetRepairingRequirements()==false`, the entry is **removed from
   `ItemCraftQueueEntries`** via `TArray::RemoveAt` → **the repair/craft queue is silently
   lost**. This is not a "UI glitch" but a loss of player progress, and it will be
   irregular.
2. **Overstated** → `UPrimalInventoryComponent::ServerCraftItem` (`0x7798E0`) /
   `ServerMakeRecipeItem_Implementation` (`0x773640`) authoritatively consume resources
   that do not exist → dupe/desync of client and server (craft is server-side, the client
   trusts the answer).
3. **A missed `SetQuantity`/`IncrementItemQuantity`** → the quantity "sticks": the item
   can be crafted/spent repeatedly.
4. **The bucket not rebuilt at `LoadedFromSaveGame`** → after world load all aggregates
   are zero → the same as item 1.

### 5.6 RISK CLASS

| Optimization option | Risk |
|---|---|
| **Bucket per exact class** (`ByClass`) + aggregates **without** accounting for `IsValidForCrafting`; the predicates `IsValidForCrafting`/`bIsBlueprint`/`IgnoreItem` are applied to the items of the bucket on the spot | **LOW.** Invalidation is fully covered by 4 points (§5.3) + a rebuild at load. A semantic violation is possible only through a bug in the hook itself; the "must be sufficient" logic is preserved exactly, because the aggregate is recomputed from the same items by the same predicates |
| The same + **aggregating "the sum of only craft-valid items"** | **HIGH.** Not invalidated by inventory mutation events; durability/break/Blueprint flags change independently. Plus the risk of item 1 above (silent loss of the repair queue) |
| Cache without buckets, one sum per class (no exact/subclass distinction) | **MEDIUM.** Breaks `bRequireExactClassMatch` and `bOverrideExactClassCraftingRequirement` |

**Recommendation: the LOW-risk variant (buckets without accounting for
`IsValidForCrafting`).**

---

## 6. Estimate of potential gain

Symbolization of `prof_298529359.bin` (30 463 samples; in-image 4 265 = 14.0 %,
external 86.0 %):

| Symbol | Samples | % of wall | % of executed (4 265) |
|---|---|---|---|
| `UObjectBaseUtility::IsA` | 284 | 0.93 % | 6.66 % |
| **`UPrimalInventoryComponent::GetItemTemplateQuantity`** | **128** | **0.42 %** | **3.00 %** |
| `FWeakObjectPtr::Get` | 64 | 0.21 % | 1.50 % |
| **`UPrimalItem::IsValidForCrafting`** | **61** | **0.20 %** | **1.43 %** |
| `FWeakObjectPtr::IsValid` | 59 | 0.19 % | 1.38 % |
| `UPrimalItem::GetPrivateStaticClass` | 21 | 0.07 % | 0.49 % |
| `UPrimalItem::TickCraftingItem` | 19 | 0.06 % | 0.45 % |
| `UPrimalItem::MeetBlueprintCraftingRequirements` | 19 | 0.06 % | 0.45 % |
| `UBlueprintFunctionLibrary::GetFunctionCallspace` | 18 | 0.06 % | 0.42 % |
| `UPrimalInventoryComponent::IsValidCraftingResource` | 12 | 0.04 % | 0.28 % |
| `UPrimalItem::GetItemQuantity` | 8 | 0.03 % | 0.19 % |
| `UPrimalInventoryComponent::GetItemOfTemplate` | 7 | 0.02 % | 0.16 % |

* 2.60 % + 1.24 % from `REPORT-Genesis.md` is the share **of the 4 932 "executed"
  samples** by their methodology; on my base (4 265 in-image) the same symbols give
  **3.00 % + 1.43 % = 4.43 %**. The discrepancy is in the base; the share is comparable.
* `GetPrivateStaticClass` (21) is `UPrimalItem::StaticClass()` (`0x1DCC70`, 12 B, `jmp`),
  called 1–2 times **per item** right in the body of `GetItemTemplateQuantity`. I.e. it is
  part of the cost of the function itself, not a separate load.
* The full A3 cluster (`GetItemTemplateQuantity` + `IsValidForCrafting` +
  `GetPrivateStaticClass` + `TickCraftingItem` + `MeetBlueprintCraftingRequirements` +
  `IsValidCraftingResource` + `GetItemQuantity` + `GetItemOfTemplate`) = **275 samples =
  0.90 % wall = 6.45 % of executed code**. By classes: `UPrimalInventoryComponent` 156 +
  `UPrimalItem` 138 = 294 samples = 0.96 % wall.

**Ceiling.** `UObjectBaseUtility::IsA` provides another 284 samples (6.66 % executed),
and `GetItemTemplateQuantity` is one of its callers (2 of **1360** call sites in the whole
binary). Offline this contribution cannot be separated; conservatively we **do not credit
it**.

**Realistic estimate.** Replacing O(N) with O(number of classes) removes most of both
passes and the accompanying `IsA` on them. With an 80% reduction of the A3 cluster we get
**≈ 220 samples ≈ 0.72 % wall** (or ≈ 4.3 % of active, non-sleeping time). This is real,
but **this is not the main reserve of Genesis**:

* Blueprint VM (`execLocalVariable`, `execDynamicCast`, `ProcessInternal`, `execLetBool`,
  `Invoke`, `CallFunction`) — the overall dominant share (22.8 % executed per
  `REPORT-Genesis.md`);
* `UObjectBaseUtility::IsA` — 6.66 % executed, and A3 accounts for only a small part of
  its 1360 calls;
* `UVictoryCore::ServerOctreeOverlapActors` + `TOctree::AdvanceToNextIntersectingElement`
  — 365 + 319 samples.

The magnitude of A3 depends on the load: if the map has many active craftings
(paths 4.3.1–4.3.2) or ballistas/turrets (4.3.3–4.3.4), the share of A3 grows; if
everything idles, it falls. The profile `prof_298529359.bin` is "a steady state with
active crafting" (TickCraftingItem in the top).

---

## 7. Explicitly NOT found

1. **`UPrimalInventoryComponent::HasItem` — no symbol.** Nearest: `HasResources`
   `0x79A350` (351 B), `HasItemOfSameType` `0x75F700` (648 B), `HasItemsEquipped`
   `0x794970` (711 B).
2. **`UPrimalInventoryComponent::GetInventoryItems` — no symbol** (0 matches in `fn`).
3. **`UPrimalInventoryComponent::GetItemQuantity` — no symbol.** Only
   `UPrimalItem::GetItemQuantity` `0x7F2F70` (17 B, `return this+0x648`) exists.
4. **`GetCraftingCost` — no symbol.** Nearest: `UPrimalInventoryComponent::GetCraftQueueResourceCost` `0x777960` (1282 B).
5. **No cache/memoization in `GetItemTemplateQuantity`** — confirmed by decompilation:
   no global or static accesses, no state fields. There is also no ready index structure
   in `UPrimalInventoryComponent` for it.
6. **0 direct (static) calls of `UPrimalItem::IsValidForCrafting` in the binary** — the
   function is reachable only through vtable slot `0x3A8` (4 copies in `.rdata`) and the
   Blueprint-thunk.
7. **The distribution of calls among the 74 call sites was not measured.** The TickProf
   profiler gives self-time per function, not per call site; this is unavailable offline.
8. **The actual N (`InventoryItems.ArrayNum`) and R (`CraftingResourceRequirements.ArrayNum`)
   on Genesis were not measured** — it depends on world/Blueprint data; unavailable
   offline.
9. **It has not been established which Blueprint graphs call
   `execGetItemTemplateQuantity` (`0x179BFD0`)** and `execIsValidForCrafting`
   (`0x17AA660`) — the bytecode lies in `.uasset` and cannot be read offline.
   Accordingly, the 18 samples of `UBlueprintFunctionLibrary::GetFunctionCallspace` and a
   significant part of `UObject::Process*` may come from there.
10. **The value of `bUseCraftQueue` in the CDO was not checked** — a flag on the
    component; whether path 4.3.1 is active depends on it.
11. **It was not checked whether `bUseBPIsValidForCrafting` is enabled for real item
    classes** on the map — unavailable offline from `.uasset`; whether the 2 `ProcessEvent`
    calls per item enter the hot path depends on it.
12. **The share of `UObjectBaseUtility::IsA` (284 samples) attributable specifically to
    `GetItemTemplateQuantity` was not isolated** — not separable offline; of its 1360
    call sites only 2 are in this function.
13. **A3-adjacent symbols like `GetInventoryItems`, `HasItem`, `GetCraftingCost` are
    entirely absent from `fn`** (verified with `LIKE` queries over the whole table,
    737 108 rows).
