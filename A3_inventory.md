# A3. Инвентарь: GetItemTemplateQuantity / IsValidForCrafting

Образ: `C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe` (v361.7, image base `0x140000000`).
Символы: `C:\Dev\_research\v361.sqlite`, таблица `fn(name,rva,size,tag)`.
Декомпиляция/листинг/xref: Ghidra 7.0.0, программа `/v361_ShooterGameServer.exe`.
Профиль: `...\ArkApi\Plugins\TickProf\prof_298529359.bin` (30 463 сэмпла).

---

## 1. Таблица символов

### 1.1 Целевые

| Символ | RVA | Размер | VA | Примечание |
|---|---|---|---|---|
| `UPrimalInventoryComponent::GetItemTemplateQuantity` | `0x777E70` | 1305 | `0x140777E70` | чистая функция, 74 статических call-site |
| `UPrimalInventoryComponent::execGetItemTemplateQuantity` | `0x179BFD0` | 914 | `0x14179BFD0` | Blueprint-thunk (74-й call-site) |
| `Z_Construct_UFunction_UPrimalInventoryComponent_GetItemTemplateQuantity` | `0x152C4A0` | 2379 | `0x14152C4A0` | источник имён и порядка параметров |
| `UPrimalItem::IsValidForCrafting` | `0x81D4B0` | 1665 | `0x14081D4B0` | **virtual**, vtable-слот `0x3A8` |
| `UPrimalItem::execIsValidForCrafting` | `0x17AA660` | 47 | `0x1417AA660` | `MOV RAX,[RCX]; CALL [RAX+0x3A8]` @ `+0x21` |
| `UPrimalItem::BPIsValidForCrafting` | `0x1366680` | 110 | `0x141366680` | → `ProcessEvent` (vtable `+0x1E0`) |
| `Z_Construct_UFunction_UPrimalItem_IsValidForCrafting` | `0x149D210` | 658 | | |
| `UPrimalItem::GetItemQuantity` | `0x7F2F70` | 17 | `0x1407F2F70` | virtual, слот `0x2E8`; `return this+0x648` |

### 1.2 Близкие символы `UPrimalInventoryComponent::*`

| Символ | RVA | Размер | Роль |
|---|---|---|---|
| `GetItemTemplateQuantity` | `0x777E70` | 1305 | цель |
| `GetCraftQueueResourceCost` | `0x777960` | 1282 | вложенный цикл Q×R + `FindItem` |
| `GetItemOfTemplate` | `0x7760E0` | 4324 | линейный поиск одного предмета |
| `IncrementItemTemplateQuantity` | `0x775310` | 2388 | мутатор |
| `FindItem` | `0x75F990` | 6154 | мутатор/поиск |
| `HasResources` | `0x79A350` | 351 | цикл R × `GetItemTemplateQuantity` |
| `execHasResources` | `0x179BAC0` | 203 | только из Blueprint |
| `HasItemOfSameType` | `0x75F700` | 648 | — |
| `HasItemsEquipped` | `0x794970` | 711 | — |
| `AllowAddInventoryItem` | `0x754580` | 1203 | вызывает `GetItemTemplateQuantity` |
| `AddItem` | `0x754A40` | 1644 | мутатор (→ `UPrimalItem::AddToInventory`) |
| `RemoveItem` | `0x7574B0` | 832 | мутатор (→ `UPrimalItem::RemoveItemFromInventory`) |
| `EjectItem` | `0x7577F0` | 953 | мутатор |
| `TickComponent` | `0x77B3C0` | 794 | **per-tick** |
| `TickCraftQueue` | `0x77B6E0` | 936 | **per-tick** |
| `IsValidCraftingResource` | `0x796BF0` | 339 | вызывается из `IsValidForCrafting` |
| `RemoteInventoryAllowAddItems` | `0x766F80` | 3240 | передача/торговля |
| `ConsumeResources` | `0x79A4B0` | 458 | мутатор |
| `LoadedFromSaveGame` | `0x781330` | 7642 | массовый restore |
| `InitializeInventory` | `0x762F20` | 5184 | rebuild |
| `ServerCraftItem` | `0x7798E0` | 992 | серверный крафт |
| `ServerMakeRecipeItem_Implementation` | `0x773640` | 5985 | серверный крафт |

### 1.3 Близкие символы `UPrimalItem::*` (крафт/ресурсы)

| Символ | RVA | Размер | Вызывает `GetItemTemplateQuantity`? |
|---|---|---|---|
| `MeetBlueprintCraftingRequirements` | `0x7F8710` | 4057 | да, 1× (+ `GetCraftQueueResourceCost`) |
| `MeetRepairingRequirements` | `0x7FB320` | 1422 | да, 2× |
| `TestMeetsCraftingRequirementsPercent` | `0x7F96F0` | 1560 | да, 2× |
| `ConsumeCraftingRequirementsPercent` | `0x7F9D10` | 1598 | нет (через `IncrementItemTemplateQuantity`) |
| `GetCraftingRequirementsString` | `0x7FA350` | 4034 | да, 2× |
| `GetRepairingRequirementsString` | `0x7FB8B0` | 9422 | да, **7×** |
| `IterateCraftingRequirements` | `0x7FE790` | 882 | да, 1× |
| `IterateRepairingRequirements` | `0x7FDD80` | 2569 | да, 3× |
| `MakeRepairingRequirementsString` | `0x831F60` | — | да, 1× |
| `GetMiscInfoString` | `0x7F30B0` | 5024 | да, 1× (virtual, слот `0x2F0`) |
| `CheckForInventoryDupes` | `0x826100` | 13506 | вызывается из `GetItemTemplateQuantity` |
| `TickCraftingItem` | `0x80B760` | 5227 | virtual, слот `0x338` — **per-tick** |
| `CanCraft` | `0x816970` | 5715 | virtual, слот `0x350` |
| `CanFullyCraft` | `0x8033C0` | 482 | косвенно (`MeetBlueprintCraftingRequirements`) |
| `GetMaximumAdditionalCrafting` | `0x824D40` | 446 | косвенно |
| `SetQuantity` | `0x80D4C0` | 8562 | мутатор количества |
| `IncrementItemQuantity` | `0x7F4D60` | 8631 | мутатор количества |
| `AddToInventory` | `0x7AC9A0` | 12407 | **мутатор массива** |
| `RemoveItemFromInventory` | `0x7AFCA0` | 9604 | **мутатор массива** |
| `calcResourceQuantityRequired` | `0x7F1490` | 1126 | — |

Смежные низкоуровневые:

| Символ | RVA | Размер |
|---|---|---|
| `UObjectBaseUtility::IsA` | `0x1FCDAB0` | 36 |
| `UStruct::IsChildOf` | `0x1DCC80` | 25 |
| `UPrimalItem::StaticClass` | `0x1DCC70` | 12 (jmp → `GetPrivateStaticClass` `0x1364F00`, 69 B) |
| `UPrimalItem::GetPrivateStaticClass` | `0x1364F00` | 69 |
| `UPrimalItem::IsBroken` | `0x7D0900` | 95 |
| `UPrimalItem::GetDurabilityPercentage` | `0x801750` | 149 |
| `FWeakObjectPtr::IsValid` | `0xDA8030` | 105 |
| `FWeakObjectPtr::Get` | `0x1FD7730` | 94 |

### 1.4 vtable `UPrimalItem::$_VTable` (RVA `0x3FD2058`, в `.rdata`)

Проверено чтением по файлу (4 копии указателя на `IsValidForCrafting`: RVA `0x3FD2400`, `0x3FD2870`, `0x3FD2CE0`, `0x3FDC9C0`):

| Слот | Значение | Символ |
|---|---|---|
| `+0x000` | `0x1407A6770` | `UPrimalItem::`scalar deleting destructor'` |
| `+0x2E8` | `0x1407F2F70` | `UPrimalItem::GetItemQuantity` |
| `+0x2F0` | `0x1407F30B0` | `UPrimalItem::GetMiscInfoString` |
| `+0x338` | `0x14080B760` | `UPrimalItem::TickCraftingItem` |
| `+0x350` | `0x140816970` | `UPrimalItem::CanCraft` |
| `+0x3A0` | `0x14081AA90` | `UPrimalItem::CanSpoil` |
| `+0x3A8` | `0x14081D4B0` | **`UPrimalItem::IsValidForCrafting`** |

Отдельно: `0x144A1ED38` (единственный «не-vtable» DATA-xref на `IsValidForCrafting`) — это запись `.pdata` `RUNTIME_FUNCTION{Begin=0x81D4B0, End=0x81DB31, Unwind=0x435A5E0}`, а не ссылка.

---

## 2. Что именно сканируется

### 2.1 `UPrimalInventoryComponent::GetItemTemplateQuantity` (`0x777E70`, 1305 B)

Сигнатура (имена параметров восстановлены из `Z_Construct_UFunction_...` @ `0x14152C4A0` + порядок чтения в `execGetItemTemplateQuantity` @ `0x179BFD0`):

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

Тело:

1. `ItemTemplate == nullptr` → `return 0`; иначе `UPrimalItem::StaticClass()` (`0x1401DCC70`) + `UStruct::IsChildOf` (`0x1401DCC80`) — если класс не `UPrimalItem`, тоже `0`.
2. **Два дублированных цикла по `this->InventoryItems`** (`TArray<UPrimalItem*>`, смещение **в объекте `0x118`**, подтверждено `MOV RAX,[RSP+0xE0]; ADD RAX,0x118` @ `0x140777EF6`):
   * `bForceCheckForDupes == false` → **прямой проход** `0 … ArrayNum-1` (метки `LAB_140777F39…`);
   * `bForceCheckForDupes == true` → **обратный проход** `ArrayNum-1 … 0` (метки `LAB_140778155…`) + дополнительный фильтр `UPrimalItem::CheckForInventoryDupes(item) || (item->OwnerInventory == this)` (`0x140826100`, `operator==` `0x1401FF150`).
3. На каждый элемент:
   * проверка `!= nullptr`;
   * если `bRequireExactClassMatch` и `!item->bOverrideExactClassCraftingRequirement` → сравнение **точного** `item->Class` (`item+0x0`) с `ItemTemplate`;
   * иначе → `UStruct::IsChildOf(ItemTemplate, UPrimalItem::StaticClass())` + `UObjectBaseUtility::IsA(item, ItemTemplate)` (`0x141FCDAB0`) — **линейный обход цепочки `SuperStruct`**;
   * фильтры: `bIgnoreBlueprints && item->bIsBlueprint`, `IgnoreItem && item == IgnoreItem`;
   * если `bCheckValidForCrafting` → **виртуальный вызов `[vtable+0x3A8]` = `UPrimalItem::IsValidForCrafting`** (адреса `0x1407780F7` и `0x140778319`);
   * `sum += [vtable+0x2E8]()` = `UPrimalItem::GetItemQuantity` (адреса `0x140778111` и `0x140778366`).

**Кэша/мемоизации нет**: ни одного обращения к глобальной/статической переменной, ни одного поля состояния. Функция полностью пересчитывает сумму при каждом вызове. Индексов, хэш-таблиц и побочных структур в `UPrimalInventoryComponent` под это нет.

### 2.2 `UPrimalItem::IsValidForCrafting` (`0x81D4B0`, 1665 B)

Последовательность ранних выходов:

1. `!bValidCraftingResource` → `false`;
2. `bIsBlueprint` → `false`;
3. `UPrimalItem::IsBroken(this)` (`0x1407D0900`) → `false`;
4. `bUseItemDurability && GetDurabilityPercentage() < MinDurabilityForCraftingResource` → требует, чтобы `OwnerInventory` резолвился в ненулевой объект с флагом `(uint)(Owner+0x50) >> 6 & 1`, иначе `false`;
5. `bPreventCraftingResourceAtFullDurability && GetDurabilityPercentage() >= 1.0f` → требует `OwnerInventory` с флагом `(uint)(Owner+0x50) >> 6 & 1`, иначе `false`;
6. `OwnerInventory != null` → `UPrimalInventoryComponent::IsValidCraftingResource(OwnerInventory, this)` (`0x140796BF0`) → если `false`, то `false`. Внутри — **два виртуальных вызова на Owner** (`+0x888`, `+0xCC8`) и опциональный `BPIsValidCraftingResource`;
7. `bUseBPIsValidForCrafting` → `BPIsValidForCrafting(this)` (`0x14081DD00`, `0x141366680`) → **`ProcessEvent` (слот `+0x1E0`), полноценный вход в Blueprint-VM**;
8. `true`.

Итого на один предмет: **до 3× `FWeakObjectPtr::IsValid` + 3× разыменование `GUObjectArray`**, **2–3× `GetDurabilityPercentage`**, до **2 входов в Blueprint-VM** (`BPIsValidForCrafting` и `BPIsValidCraftingResource`).

---

## 3. Сложность

| Сценарий | Формула |
|---|---|
| Один `GetItemTemplateQuantity` | **O(N)** — один линейный проход по `InventoryItems` (N = `ArrayNum`), константа на элемент: 1–2× `StaticClass()`, 1× `IsChildOf()`, 1× `IsA()` (обход `SuperStruct`), опционально 1× `IsValidForCrafting()` (1665 B) + 1× `GetItemQuantity()` |
| `bForceCheckForDupes=true` | то же + `CheckForInventoryDupes` (13506 B) на элемент |
| `UPrimalItem::MeetBlueprintCraftingRequirements` (`0x7F8710`) | цикл по `CraftingResourceRequirements` (**R**) × `GetItemTemplateQuantity` → **O(R·N)** |
| `UPrimalItem::MeetRepairingRequirements` (`0x7FB320`) | **O(R·N)** (2 call-site) |
| `UPrimalInventoryComponent::HasResources` (`0x79A350`) | **O(R·N)** |
| `UPrimalItem::TestMeetsCraftingRequirementsPercent` (`0x7F96F0`) | **O(R·N)** (2 call-site) |
| `GetCraftingRequirementsString` / `GetRepairingRequirementsString` | **O(R·N)**, причём 7 call-site у repairing-строки |
| `GetCraftQueueResourceCost` (`0x777960`) | **O(Q·(N_find + R))**, Q = `ItemCraftQueueEntries` |
| `TickCraftingItem` за тик | до **3×** `MeetBlueprintCraftingRequirements` + 1× `MeetRepairingRequirements` → **O(R·N) за тик на каждый активный blueprint** |
| `TickCraftQueue` за тик | на каждую запись очереди ремонта → `MeetRepairingRequirements` → **O(R·N) за тик на запись** |

Вложенных циклов «внутри GetItemTemplateQuantity» нет — вложенность появляется на уровне вызывающего кода (крафт/ремонт/инвентарь-UI). Это важно для оптимизации: **узкое место — не сам проход, а стоимость фильтрации одного элемента** (`IsA` + `IsValidForCrafting`).

---

## 4. Все call-site и периодичность

### 4.1 `GetItemTemplateQuantity` — 74 прямых call-site в 57 функциях

Полный список (адрес call-site → содержащая функция; все из `.text`):

| Call-site | Содержащая функция | Периодичность |
|---|---|---|
| `0x2D2CC8` | `UHexagonTradableOption::GetAmountInInventory` (`0x2D2C60`) | по клику трейда |
| `0x38821F` | `AMissionType::RemoveItemsFromInventory_Balanced` (`0x387FC0`) | по событию миссии |
| `0x38A6A6` | `AMissionType::CountInventoryItems` (`0x38A610`) | по событию миссии |
| `0x38A815` | `AMissionType::CountInventoryItemsFromAllPlayersInMission` (`0x38A6B0`) | по событию миссии |
| `0x3EFE57` | `UPrimalAbility::CanConsumeFuel` (`0x3EFC40`) | по тику способности |
| `0x3F073A` | `UPrimalAbility::ConsumeFuel` (`0x3EFE80`) | по событию |
| `0x3F1327` | `UPrimalAbility::GetAvailableFuelConfig` (`0x3F11C0`) | по запросу |
| `0x3F14AC` | `UPrimalAbility::GetAvailableFuel` (`0x3F13A0`) | по запросу |
| `0x6A8383` | `APrimalDinoCharacter::TamedDinoUnstasisConsumeFood` (`0x6A75C0`) | по событию (unstasis) |
| `0x7547D4` | `UPrimalInventoryComponent::AllowAddInventoryItem` (`0x754580`) | **на каждую попытку добавления** |
| `0x767B3B` | `UPrimalInventoryComponent::RemoteInventoryAllowAddItems` (`0x766F80`) | по RPC передачи/торговли |
| `0x79A491` | `UPrimalInventoryComponent::HasResources` (`0x79A350`) | **Blueprint (exec `0x179BAC0`), O(R·N)** |
| `0x7F395E` | `UPrimalItem::GetMiscInfoString` (`0x7F30B0`, virtual `0x2F0`) | по запросу UI/инфо |
| `0x7F9586` | `UPrimalItem::MeetBlueprintCraftingRequirements` (`0x7F8710`) | **см. 4.3** |
| `0x7F99F3`, `0x7F9CEA` | `UPrimalItem::TestMeetsCraftingRequirementsPercent` (`0x7F96F0`) | открытие инвентаря/мульти-использование |
| `0x7FAA1D`, `0x7FAD85` | `UPrimalItem::GetCraftingRequirementsString` (`0x7FA350`) | открытие тултипа |
| `0x7FB6F2`, `0x7FB889` | `UPrimalItem::MeetRepairingRequirements` (`0x7FB320`) | **см. 4.3** |
| `0x7FC058`, `0x7FC317`, `0x7FC794`, `0x7FCF59`, `0x7FD289`, `0x7FD774`, `0x7FDAA5` | `UPrimalItem::GetRepairingRequirementsString` (`0x7FB8B0`) | открытие тултипа (7×) |
| `0x7FE05C`, `0x7FE39A`, `0x7FE68C` | `UPrimalItem::IterateRepairingRequirements` (`0x7FDD80`) | тултип (3×) |
| `0x7FE982` | `UPrimalItem::IterateCraftingRequirements` (`0x7FE790`) | тултип |
| `0x83247E` | `UPrimalItem::MakeRepairingRequirementsString` (`0x831F60`) | тултип |
| `0x8BDBD7` | `APrimalShip::CanConsumeFuel` (`0x8BD9F0`) | по тику корабля |
| `0x8BDFEC`, `0x8BE069` | `APrimalShip::ConsumeFuel` (`0x8BDC00`) | по тику/событию |
| `0x8BE49D` | `APrimalShip::GetCurrentFuelInterval` (`0x8BE300`) | по тику |
| `0x8BE898` | `APrimalShip::CacheFirstFoundShipFuel` (`0x8BE530`) | по событию |
| `0x8BEEDE` | `APrimalShip::UpdateCachedFuelInfo` (`0x8BECC0`) | по событию |
| `0x8E27A3` | `APrimalStingerShip::CanConsumeFuel` (`0x8E2610`) | по тику |
| `0x8E2B58`, `0x8E2BC5` | `APrimalStingerShip::ConsumeFuel` (`0x8E27D0`) | по тику/событию |
| `0x8E2FD9` | `APrimalStingerShip::GetCurrentFuelInterval` (`0x8E2E50`) | по тику |
| `0x8E324A` | `APrimalStingerShip::CacheFirstFoundShipFuel` (`0x8E3070`) | по событию |
| `0x8E362A` | `APrimalStingerShip::UpdateCachedFuelInfo` (`0x8E3460`) | по событию |
| `0x94E225` | `APrimalStructure::GetMultiUseEntries` (`0x94BE80`) | открытие инвентаря структуры |
| `0x94FA9D` | `APrimalStructure::TryMultiUse` (`0x94F790`) | по действию игрока |
| `0x9BD9E7` | `APrimalStructureItemContainer::NotifyItemAdded` (`0x9BD750`) | по событию |
| `0x9BE0F6` | `APrimalStructureItemContainer::NotifyItemRemoved` (`0x9BDDD0`) | по событию |
| `0x9BE44E`, `0x9BE55F` | `APrimalStructureItemContainer::RefreshFuelState` (`0x9BE2E0`) | по событию |
| `0x9CBD15` | `APrimalStructureItemContainer_CropPlot::AllowRemoteAddItemToInventory` (`0x9CBBA0`) | по событию |
| `0x9D3C51` | `APrimalStructureItemContainer_CropPlot::GetPhaseInventoryItemCount` (`0x9D3AA0`) | по событию |
| `0x9D4E74` | `APrimalStructureItemContainer_CropPlot::RefreshFertilized` (`0x9D4E20`) | по событию |
| `0x9D50B0` | `APrimalStructureItemContainer_CropPlot::NotifyItemRemoved` (`0x9D5020`) | по событию |
| `0x9D5213` | `APrimalStructureItemContainer_CropPlot::NotifyItemAdded` (`0x9D5160`) | по событию |
| `0x9DACFD` | `APrimalStructureItemContainer_CropPlot_VisualItems::NotifyItemRemoved` (`0x9DABB0`) | по событию |
| `0x9DAF0B` | `APrimalStructureItemContainer_CropPlot_VisualItems::NotifyItemAdded` (`0x9DADB0`) | по событию |
| `0x9DF7CA` | `APrimalStructureItemContainer_VisualItems::NotifyItemRemoved` (`0x9DF6B0`) | по событию |
| `0x9DFB68` | `APrimalStructureItemContainer_VisualItems::NotifyItemAdded` (`0x9DFA40`) | по событию |
| `0x9ECDD7` | `APrimalStructurePlacer::Tick` (`0x9ECC80`, +`0x157`) | **per-tick, пока активен «призрак» постройки** |
| `0x9F6484` | `APrimalStructurePlacer::FinalStructurePlacement` (`0x9F3E30`) | по событию установки |
| `0xA2B3E3`, `0xA2B473` | `APrimalStructureTurret::GetAmmoNearby` (`0xA2A950`) | **per-tick турели** (см. 4.3) |
| `0xA3F05F` | `APrimalStructureTurret::UpdateNumBullets` (`0xA3F020`) | по событию |
| `0xA45B81` | `APrimalStructureTurretBallista::DoFire` (`0xA45AA0`) | по выстрелу |
| `0xA544D9` | `APrimalStructureTurretBallista::DoFireProjectile` (`0xA54060`) | по выстрелу |
| `0xA58CE2`, `0xA591B4` | `APrimalStructureTurretBallista::GetAmmoNearby` (`0xA58C20`) | по событию |
| `0xA5969F`, `0xA598AC` | `APrimalStructureTurretBallista::GetAmmoAmount` (`0xA59640`) | **per-tick баллисты** (через `CanFire`/`CanReload`) |
| `0xAACF98` | `APrimalWeaponBoomerang::OnBoomerangReturn` (`0xAACCC0`) | по событию |
| `0xF4D680` | `AShooterWeapon::RefreshAmmoItemQuantity` (`0xF4D480`) | из Blueprint |
| `0xFEFCFD` | `UStructuresPlus::SP_GetInventoryCapacityForItem` (`0xFEFAB0`) | по запросу |
| `0x179C341` | `UPrimalInventoryComponent::execGetItemTemplateQuantity` (`0x179BFD0`) | **из Blueprint-графов** |

### 4.2 `UPrimalItem::IsValidForCrafting` — call-site

**Прямых (статических) вызовов в бинарнике НЕТ (0 шт.)** — проверено сканером `E8 rel32` по всему `.text`. Все 5 DATA-xref: 1 — запись `.pdata` (`0x144A1ED38`), 4 — копии vtable (`0x144A1ED38`-family: RVA `0x3FD2400`, `0x3FD2870`, `0x3FD2CE0`, `0x3FDC9C0`).

Фактические точки входа:

| Адрес | Откуда | Периодичность |
|---|---|---|
| `0x1407780F7` | `GetItemTemplateQuantity`, прямой проход, `bCheckValidForCrafting==true` | наследует периодичность вызывающего |
| `0x140778319` | `GetItemTemplateQuantity`, обратный проход (`bForceCheckForDupes`) | то же |
| `0x1417AA681` | `execIsValidForCrafting` (`0x17AA660`) | из Blueprint |

Оба вызова из `GetItemTemplateQuantity` выполняются **на каждый элемент инвентаря** при `bCheckValidForCrafting==true`. Именно это значение передаёт `MeetBlueprintCraftingRequirements`:

```
GetItemTemplateQuantity(inv, ItemClass, /*IgnoreItem=*/this,
                        /*bIgnoreBlueprints=*/true,
                        /*bCheckValidForCrafting=*/true,   // <—
                        bRequireExactClassMatch,
                        /*bForceCheckForDupes=*/false);
```

а `MeetRepairingRequirements`, `HasResources`, `TestMeetsCraftingRequirementsPercent`, `GetCraftingRequirementsString` передают `bCheckValidForCrafting = false` — там `IsValidForCrafting` **не** вызывается.

### 4.3 КРИТИЧНО: per-tick или по событию?

**Не «для каждого актора на каждом тике».** Прямого вызова из generic actor tick нет. Per-tick путей ровно пять, и все узкие:

1. **`UPrimalInventoryComponent::TickComponent` (`0x77B3C0`, 794 B) → `TickCraftQueue` (`0x77B6E0`) → `UPrimalItem::MeetRepairingRequirements` (`0x7FB320`, call `0x77B996` `+0x2B6`) → 2× `GetItemTemplateQuantity` на требование.**
   Гейты: `bUseCraftQueue != 0`, непустой `ItemCraftQueueEntries`, `CraftingItems` пуст. Т.е. **только когда есть активная очередь ремонта**.
2. **`TickComponent` → для каждого элемента `CraftingItems` виртуальный `UPrimalItem::TickCraftingItem` (слот `0x338`) → до 3× `MeetBlueprintCraftingRequirements` (`0x80C077`, `0x80C2B8`, `0x80C54A`) + 1× `MeetRepairingRequirements` (`0x80BCF9`).**
   Гейт: `CraftingItems` содержит только активно крафтящиеся blueprint'ы. Т.е. **на каждый активный крафт — каждый тик**.
3. **`APrimalStructureTurret::Tick` (`0xA39740`) → `APrimalStructureTurret::GetAmmoNearby` (`0xA2A950`, call `0xA3A129` `+0x9E9`) → 2× `GetItemTemplateQuantity`.** На каждую турель, каждый тик (за call-site стоит условный переход).
4. **`APrimalStructureTurretBallista::Tick` (`0xA4CE60`) → `CanFire` (`0xA532E0`, call `0xA4FE93` `+0x3033`) → 2× `GetAmmoAmount` (`0xA59640`) → `GetItemTemplateQuantity`.** Также `CanReload` (`0xA53880`) и `UpdateAmmoCount` (`0xA53AB0`). На каждую баллисту, каждый тик.
5. **`APrimalStructurePlacer::Tick` (`0x9ECC80`, `+0x157`).** Только пока игрок тащит призрак постройки.

Остальные 69 call-site — по событию (добавление/удаление предмета, открытие инвентаря, RPC передачи/торговли, тултип) либо из Blueprint-графов.

Профиль это подтверждает: в `prof_298529359.bin` присутствуют `UPrimalItem::TickCraftingItem` (19 сэмплов) и `UPrimalItem::MeetBlueprintCraftingRequirements` (19 сэмплов) — т.е. пути 1–2 реально активны в стационарном состоянии.

Отдельная оговорка: `UUI_*`, `UPrimalItemToolTipWidget::InitToolTip`, `UDataListEntryButton_PrimalItem::DrawItemPart_Background`, `UInventoryPanelWidget::OnInventoryItemDoubleClicked` присутствуют в этом бинарнике (серверная сборка содержит весь UI-код), но на выделенном сервере **не исполняются**.

---

## 5. Эскиз оптимизации: индекс/кэш

### 5.1 Где хранить

Массив `InventoryItems` живёт **в компоненте**, а не в акторе: `UPrimalInventoryComponent` + `0x118` (`TArray<UPrimalItem*>`; `+0x0` = data, `+0x8` = ArrayNum, `+0xC` = ArrayMax). Поэтому состояние индекса должно висеть **на компоненте** (side-map `UPrimalInventoryComponent* → FInvIndex`), а не на акторе и не глобально:

* у игрока, у каждого прирученного динозавра, у каждой структуры-контейнера, у turret'а — свой компонент и свой индекс;
* `GetItemTemplateQuantity` очень часто вызывается с компонентом, **резолвнутым из `item->OwnerInventory`** (например, `MeetBlueprintCraftingRequirements` `0x7F8710` при `param_1 == nullptr` разыменовывает `OwnerInventory`), поэтому индекс искать по переданному `this`, а не по актору/предмету.

### 5.2 Структура

Не «одна сумма на класс», а **корзина по точному классу** — иначе нельзя корректно посчитать `bRequireExactClassMatch` (у предметов есть инстанс-флаг `bOverrideExactClassCraftingRequirement`) и `bIgnoreBlueprints` (`bIsBlueprint` — тоже инстанс-флаг).

```c
struct FInvBucket {                        // на ТОЧНЫЙ UClass предмета
    TArray<UPrimalItem*, TInlineAllocator<8>> Items;   // или только счётчик + ptr-массив
    int32 TotalQuantity;      // sum GetItemQuantity()
    int32 ExactClassQuantity; // sum по item с !bOverrideExactClassCraftingRequirement
    int32 NonBlueprintQty;    // sum по item с !bIsBlueprint
    uint32 Gen;               // ленивая инвалидация
};

struct FInvIndex {
    uint32 Gen;                            // монотонный счётчик
    uint32 ItemsGen;                       // меняется при SetQuantity/IncrementItemQuantity
    TMap<UClass*, FInvBucket> ByClass;     // ключ — точный класс
    TArray<UClass*, TInlineAllocator<8>>   // производный кэш «какие бакета подходят»:
        , TInlineAllocator<8>> MatchCache;// UClass* запроса -> список бакетов
};
```

Запрос `GetItemTemplateQuantity(ItemTemplate, …)`:

1. если `ByClass.Num() == 0` → 0 (быстрый выход, не хуже текущего кода);
2. взять из `MatchCache` (или пересобрать за O(число различных классов)) список баскетов, чей класс `IsA(ItemTemplate)`;
3. пройти **только по ним**, применяя оставшиеся предикаты (`bIsBlueprint`, `item == IgnoreItem`, `IsValidForCrafting`) к конкретным предметам.

Число различных классов в реальном инвентаре обычно 3–15, тогда как N — десятки и сотни. Выигрыш — замена O(N) на O(число классов + число совпавших предметов).

### 5.3 Точки зацепа для инвалидации

| Действие | Функция-мутатор | RVA / размер | Число call-site |
|---|---|---|---|
| **добавление в массив** | `UPrimalItem::AddToInventory` | `0x7AC9A0` / 12407 | **1** (`UPrimalInventoryComponent::AddItem` `0x754A40` `+0x362`) |
| **удаление из массива** | `UPrimalItem::RemoveItemFromInventory` | `0x7AFCA0` / 9604 | **5**: `RemoveItem` `0x7575B7`, `EjectItem` `0x757897`, `ClientStartReceivingItems` `0x75EEA5` и `0x75EF19`, `APrimalStructure::PickupStructureAndDependingLinkedStructures` `0x97B342` |
| **изменение количества** | `UPrimalItem::SetQuantity` | `0x80D4C0` / 8562 | 7 |
| **изменение количества** | `UPrimalItem::IncrementItemQuantity` | `0x7F4D60` / 8631 | 15 |
| **полный rebuild** | `UPrimalInventoryComponent::LoadedFromSaveGame` | `0x781330` / 7642 | — |
| | `UPrimalInventoryComponent::InitializeInventory` | `0x762F20` / 5184 | — |
| | `UPrimalInventoryComponent::InitDefaultInventory` | `0x762010` / 3590 | — |
| | `UPrimalInventoryComponent::OnComponentCreated` | `0x796D50` / 1653 | — |

Все прочие «увеличиватели» (`UPrimalInventoryComponent::IncrementItemTemplateQuantity` `0x775310`, `ConsumeResources` `0x79A4B0`, `ServerSplitItemStack_Implementation` `0x77C600`, `ServerMergeItemStack_Implementation` `0x77CBF0`, `ServerForceMergeItemStack_Implementation` `0x77D0B0`, `TransferAllItemsToInventory*`, торговля через `AShooterPlayerController::Server*RemoteInventory*`) транзитивно идут через эти четыре точки — отдельно хукить не нужно.

**Минимальный безопасный хук — перехватить 4 адреса** (`0x7AC9A0`, `0x7AFCA0`, `0x80D4C0`, `0x7F4D60`) и перестроить/обновить корзину компонента, из которого пришёл вызов.

### 5.4 Риск инвалидации — по типам данных

| Источник риска | Оценка |
|---|---|
| Предметы в рюкзаках / контейнерах / у динозавров | Каждый имеет **свой** `UPrimalInventoryComponent` и, следовательно, свой индекс. Проблемы нет, если индекс адресуется по компоненту, а не по актору |
| `IsValidForCrafting` **не является состоянием инвентаря** | Зависит от прочности (`GetDurabilityPercentage`), `IsBroken`, `bPreventCraftingResourceAtFullDurability`, от `OwnerInventory` (владелец меняется при `TransferItemToInventory`/подборе), от родительской структуры (`bUseParentStructureIsValidCraftingResource` → `IsValidCraftingResource` `0x796BF0`), от Blueprint (`bUseBPIsValidForCrafting` → `ProcessEvent`). **Ни одно из этого не мутирует `InventoryItems`** → «сумму только валидных для крафта» кэшировать нельзя без отдельной инвалидации по прочности |
| Торговля / передача между инвентарями | Идёт через `AddItem`/`RemoveItem` → `AddToInventory`/`RemoveItemFromInventory`, покрыто |
| Крафт / ремонт | `ConsumeResources`, `IncrementItemTemplateQuantity`, `FinishCraftingBlueprint`, `RepairItem` → идут через `IncrementItemQuantity`/`RemoveItemFromInventory`, покрыто |
| Загрузка/сохранение | `LoadedFromSaveGame` + `ClientStartReceivingItems` — массовая вставка, нужен rebuild, а не точечная правка |
| Blueprint-видимость | Функция экспортирована как UFunction (`execGetItemTemplateQuantity` `0x179BFD0`) — любое изменение семантики наблюдаемо в скриптах |

### 5.5 Что конкретно сломается при устаревшем кэше

1. **Занижено** → `MeetBlueprintCraftingRequirements` вернёт `false` → в `UPrimalInventoryComponent::TickCraftQueue` (`0x77B6E0`, ветка `+0x2B6`) при `MeetRepairingRequirements()==false` запись **удаляется из `ItemCraftQueueEntries`** через `TArray::RemoveAt` → **очередь ремонта/крафта молча теряется**. Это не «глюк UI», а потеря прогресса игрока, и она будет нерегулярной.
2. **Завышено** → `UPrimalInventoryComponent::ServerCraftItem` (`0x7798E0`) / `ServerMakeRecipeItem_Implementation` (`0x773640`) авторитетно спишут ресурсы, которых нет → дюп/рассинхрон клиента и сервера (крафт серверный, клиент доверяет ответу).
3. **Пропущен `SetQuantity`/`IncrementItemQuantity`** → количество «залипнет»: предмет можно будет крафтить/тратить повторно.
4. **Не пересобрали корзину при `LoadedFromSaveGame`** → после загрузки мира все агрегаты нулевые → то же, что п.1.

### 5.6 РИСК-КЛАСС

| Вариант оптимизации | Риск |
|---|---|
| **Корзина по точному классу** (`ByClass`) + агрегаты **без** учёта `IsValidForCrafting`; предикаты `IsValidForCrafting`/`bIsBlueprint`/`IgnoreItem` применяются к предметам из корзины на месте | **НИЗКИЙ.** Инвалидация полностью покрывается 4 точками (§5.3) + rebuild при загрузке. Нарушение семантики возможно только при ошибке в самом хуке; логика «должно быть достаточно» сохраняется точь-в-точь, потому что агрегат пересчитывается из тех же предметов теми же предикатами |
| То же + **агрегировать «сумму только валидных для крафта»** | **ВЫСОКИЙ.** Не инвалидируется событиями мутации инвентаря; прочность/брейк/Blueprint-флаги меняются независимо. Плюс риск п.1 выше (тихая потеря очереди ремонта) |
| Кэш без корзин, только одна сумма на класс (без различения exact/subclass) | **СРЕДНИЙ.** Ломает `bRequireExactClassMatch` и `bOverrideExactClassCraftingRequirement` |

**Рекомендация: НИЗКИЙ-рисковый вариант (корзины без учёта `IsValidForCrafting`).**

---

## 6. Оценка потенциального выигрыша

Символизация `prof_298529359.bin` (30 463 сэмпла; in-image 4 265 = 14.0 %, внешних 86.0 %):

| Символ | Сэмплов | % от wall | % от исполняемого (4 265) |
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

* 2.60 % + 1.24 % = 3.84 % из `REPORT-Genesis.md` — это доля **от 4 932 «исполняемых» сэмплов** по их методике; при моей базе (4 265 in-image) те же символы дают **3.00 % + 1.43 % = 4.43 %**. Расхождение — в базе, доля сопоставима.
* `GetPrivateStaticClass` (21) — это `UPrimalItem::StaticClass()` (`0x1DCC70`, 12 B, `jmp`), вызываемый 1–2 раза **на каждый элемент** прямо в теле `GetItemTemplateQuantity`. То есть это часть стоимости самой функции, а не отдельная нагрузка.
* Полный кластер A3 (`GetItemTemplateQuantity` + `IsValidForCrafting` + `GetPrivateStaticClass` + `TickCraftingItem` + `MeetBlueprintCraftingRequirements` + `IsValidCraftingResource` + `GetItemQuantity` + `GetItemOfTemplate`) = **275 сэмплов = 0.90 % wall = 6.45 % исполняемого кода**. По классам: `UPrimalInventoryComponent` 156 + `UPrimalItem` 138 = 294 сэмпла = 0.96 % wall.

**Потолок.** `UObjectBaseUtility::IsA` даёт ещё 284 сэмпла (6.66 % исполняемого), и `GetItemTemplateQuantity` — один из её вызывателей (2 call-site из **1360** по всему бинарнику). Офлайн разделить этот вклад нельзя; консервативно его **не зачитываем**.

**Реалистичная оценка.** Замена O(N) на O(число классов) убирает большую часть обоих проходов и сопутствующий `IsA` на них. При 80 % сокращении кластера A3 получаем **≈ 220 сэмплов ≈ 0.72 % wall** (или ≈ 4.3 % от активного, не-сонного времени). Это реально, но **это не главный резерв Genesis**:

* Blueprint-VM (`execLocalVariable`, `execDynamicCast`, `ProcessInternal`, `execLetBool`, `Invoke`, `CallFunction`) — суммарно доминирующая доля (по `REPORT-Genesis.md` 22.8 % исполняемого);
* `UObjectBaseUtility::IsA` — 6.66 % исполняемого, и A3 отвечает лишь за малую часть её 1360 вызовов;
* `UVictoryCore::ServerOctreeOverlapActors` + `TOctree::AdvanceToNextIntersectingElement` — 365 + 319 сэмплов.

Порядок величины A3 зависит от нагрузки: если на карте много активных крафтов (пути 4.3.1–4.3.2) или балист/турелей (4.3.3–4.3.4), доля A3 растёт; если всё простаивает — падает. Профиль `prof_298529359.bin` — это «steady state с активным крафтом» (TickCraftingItem в топе).

---

## 7. Явно НЕ найдено

1. **`UPrimalInventoryComponent::HasItem` — символа нет.** Ближайшие: `HasResources` `0x79A350` (351 B), `HasItemOfSameType` `0x75F700` (648 B), `HasItemsEquipped` `0x794970` (711 B).
2. **`UPrimalInventoryComponent::GetInventoryItems` — символа нет** (0 совпадений по `fn`).
3. **`UPrimalInventoryComponent::GetItemQuantity` — символа нет.** Есть только `UPrimalItem::GetItemQuantity` `0x7F2F70` (17 B, `return this+0x648`).
4. **`GetCraftingCost` — символа нет.** Ближайшее: `UPrimalInventoryComponent::GetCraftQueueResourceCost` `0x777960` (1282 B).
5. **Кэша/мемоизации в `GetItemTemplateQuantity` нет** — подтверждено декомпиляцией: ни глобальных, ни статических обращений, ни полей состояния. Готовой структуры-индекса в `UPrimalInventoryComponent` под это тоже нет.
6. **Прямых (статических) вызовов `UPrimalItem::IsValidForCrafting` в бинарнике 0** — функция достижима только через vtable-слот `0x3A8` (4 копии в `.rdata`) и Blueprint-thunk.
7. **Не измерено распределение вызовов между 74 call-site.** Профайллер TickProf даёт self-time по функции, а не по call-site; офлайн это недоступно.
8. **Не измерено фактическое N (`InventoryItems.ArrayNum`) и R (`CraftingResourceRequirements.ArrayNum`)** на Genesis — зависит от данных мира/блюпринтов, офлайн недоступно.
9. **Не установлено, какие Blueprint-графы вызывают `execGetItemTemplateQuantity` (`0x179BFD0`)** и `execIsValidForCrafting` (`0x17AA660`) — байткод лежит в `.uasset`, офлайн не читается. Соответственно, 18 сэмплов `UBlueprintFunctionLibrary::GetFunctionCallspace` и значительная часть `UObject::Process*` могут приходить оттуда.
10. **Не проверено значение `bUseCraftQueue` в CDO** — флаг на компоненте, от него зависит, активен ли путь 4.3.1.
11. **Не проверено, включён ли `bUseBPIsValidForCrafting` у реальных item-классов** на карте — офлайн из `.uasset` недоступно; от этого зависит, входят ли 2 `ProcessEvent` на предмет в горячий путь.
12. **Вклад `UObjectBaseUtility::IsA` (284 сэмпла), приходящийся именно на `GetItemTemplateQuantity`, не выделен** — офлайн не разделяется; из 1360 её call-site в этой функции только 2.
13. **`A3`-смежные символы вида `GetInventoryItems`, `HasItem`, `GetCraftingCost` в `fn` отсутствуют полностью** (проверено `LIKE`-запросами по всей таблице, 737 108 строк).
