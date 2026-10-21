# RE2.md — результаты этапа A (офлайн RE, стенд не трогался)

Образ: `ShooterGameServer.exe` v361.7 (ARK: Survival Evolved), Win64 x64,
image base `0x140000000`. Символы — `C:\Dev\_research\v361.sqlite` (PDB v361.7).
Декомпиляция и xref — Ghidra, программа `/v361_ShooterGameServer.exe`.

Каждый тезис снабжён RVA или именем символа. Что не удалось выяснить —
перечислено явно в каждом разделе. Ничего не домысливается.

## Сводка: что изменилось в понимании задач

| Задача директивы | Итог |
|---|---|
| A1 IsA | хук покрывает **только 73%** мест: 1360 вызовов + 510 инлайн-копий. `iscache` **не покрывает ни одного** места `IsA` — нулевое пересечение |
| A2 VictoryCore | **гипотеза об O(n²) в `ServerOctreeOverlapActors` ОПРОВЕРГНУТА**. Настоящий O(n²) — в `BeginComponentOverlap` |
| A3 Инвентарь | `GetItemTemplateQuantity` = O(N) без кэша, но per-tick путей всего 5 и все узкие |
| A4 SaveWorld | **фриз — это сериализация в память, а не сброс на диск**. Диск уже асинхронный, на TaskGraph-воркере |
| A5 BP-машина | точка зацепа трассировщика определена: `ProcessInternal` |
| A6 Гигиена отчётов | выполнена; **посылка ревьюера про стартовый сейв опровергнута данными** |
| A7 ARCH | `ARCH.md` создан |

---

## A1. UObjectBaseUtility::IsA

### Символы

| Символ | RVA | Размер |
|---|---|---|
| `UObjectBaseUtility::IsA` | `0x01FCDAB0` | 36 |
| `UStruct::IsChildOf` | `0x001DCC80` | 25 |
| `UClass::SetSuperStruct` | `0x01F84F30` | 43 |
| `UStruct::SetSuperStruct` | `0x01F811D0` | 5 |
| `UClass::ImplementsInterface` | `0x01F85530` | — |

`IsA_Static` и `IsA_InContainer` в образе **отсутствуют** — такого API в UE4.5 нет.

### Реализация

Обход цепочки `SuperStruct`, поле `+0x30`. Полное тело — 13 инструкций:

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

Свойств по указателю нет. **Ранний выход один** — на `Class == nullptr`;
на `TargetClass == nullptr` раннего выхода нет (цикл пройдёт цепочку целиком).

Глубина иерархии по 1587 нативным классам: **максимум 8 уровней**, для реальных
ARK-классов 5–6. То есть 25–40 циклов на вызов, с зависимыми загрузками.

### Call-site и главный вывод

| Цель | Ghidra xref | байт-скан `E8 rel32` |
|---|---|---|
| `IsA` `0x01FCDAB0` | 1360 | 1360 |
| `IsChildOf` `0x001DCC80` | 3411 | 3411 |

**Но компилятор встроил цикл в тела функций.** Регексп по сигнатуре цикла даёт
906 инлайн-копий: 510 копий `IsA` (с загрузкой `Class`) и 394 копии `IsChildOf`.

**Итог: реальных мест `IsA` = 1360 + 510 = 1870.** Хук на функцию накрывает 73%.
Оставшиеся 27% уйдут в обход.

**`IsChildOf` внутри `IsA` не вызывается** — доказано на уровне машинного кода:
тело `IsA` содержит ноль инструкций `CALL`. Это две независимые копии одного цикла.
Следовательно, **кэш `iscache` не покрывает ни одного места `IsA`**.

### Эскиз iscache2

| Аспект | Решение |
|---|---|
| Ключ | `(UClass* Source, UClass* Target)`, 16 Б; Source = `Obj->Class` (`+0x10`) |
| Структура | открытая адресация `2^16` слотов × 24 Б = 1.5 МБ в `.data`, без аллокаций в рантайме |
| Хэш | `(src>>4)*0x9E3779B1 ^ (tgt>>4)*0x85EBCA77`, индекс `& 0xFFFF` |
| **Инвалидация** | хук `UClass::SetSuperStruct` (`0x01F84F30`) поднимает epoch. Это **единственное** место, меняющее цепочку |
| Отрицательный результат | **безопасен в этой сборке**: интерфейсы лежат в отдельном массиве (`ImplementsInterface`, `GetInterfaceAddress`), в `SuperChain` **не входят** — проверено в коде, а не по документации |
| Потоки | запись 24 Б атомарно (иначе torn read → **тихая неверная классификация объектов**); чтение без блокировок |
| Висячие указатели после GC | средний риск; лечится либо хуком `~UObjectBase`, либо хранением индекса `GUObjectArray` вместо указателя |
| Горячая перегрузка | на сервере **невозможна**: `SupportsDynamicReloading` — заглушки `0x001B5330` (3 байта), BP-компилятора в образе нет |
| **Риск-класс** | **НИЗКИЙ–СРЕДНИЙ** |

**Рекомендация A1: хук на `0x01FCDAB0` даёт 73% покрытия и почти наверняка меньше
73% выигрыша.** Полное покрытие требует патча самого цикла, а это запись кода в
горячие пути `.text`. Ожидаемый выигрыш низкий по обеим причинам.

### Не найдено

1. Механизм правки `iscache` не проверен — исходников плагина не найдено, утверждение взято из старого `REPORT.md`.
2. **Цифра «−13%» от iscache не подтверждается.** В `REPORT.md:709` указан совокупный эффект трёх кэшей «−7%», разбивки по iscache нет.
3. Фактическая частота вызовов `IsA` в рантайме не измерена — 1870 мест это статика, не профиль.
4. Не проверено, вызывается ли `IsA` из воркер-потоков TaskGraph (510 инлайн-копий по потокам не атрибутированы).
5. Не проверено, добавляются ли интерфейсы в SuperChain при загрузке BP-классов из pak в рантайме.
6. Глубина иерархии BP-классов не посчитана — их нет в exe.
7. 424 класса не восстановлены из-за `_NoRegister`-декоев (на максимум глубины не влияет).
8. Косвенные вызовы `IsA` через указатель не детектировались (сканировались только `E8`/`E9`).
9. Стоимость таблицы кэша не оценена замером: размер `2^16` выбран теоретически.

---

## A2. UVictoryCore::ServerOctreeOverlapActors

### Символы

| Символ | RVA | Размер |
|---|---|---|
| `UVictoryCore::ServerOctreeOverlapActors` | `0x012871E0` | 1945 |
| `...ServerOctreeOverlapActorsBitMask` | `0x01287980` | 1706 |
| `...ServerOctreeOverlapActorsClass` | `0x01288030` | 2080 |
| `...ServerOctreeOverlapActorsClassBitMask` | `0x01288850` | 1841 |
| `UVictoryCore::FindNearbyCharactersOfClass` | `0x01288F90` | 1354 |
| `APrimalStructureTurret::GetAmmoNearby` | `0x00A2A950` | 3267 |
| `TArray<FOverlapInfo>::AddUniqueImpl` | `0x024E3050` | 138 |
| `UPrimitiveComponent::BeginComponentOverlap` | `0x02644000` | 719 |

### ГЛАВНЫЙ РЕЗУЛЬТАТ: гипотеза об O(n²) ОПРОВЕРГНУТА

`AddUniqueImpl` (`0x024E3050`) **не вызывается ни из одной** из четырёх функций
`ServerOctreeOverlapActors*`. Внутри только `Emplace` (`0x001CFE60`) — амортизированный
O(1). Проверено тремя способами: список callees всех четырёх функций, полная
декомпиляция `0x012871E0`, и `get_xrefs_to(0x024E3050)` — **единственный** вызов во всём
образе, адрес `0x0264418D`.

**Настоящий O(n²)** — в `UPrimitiveComponent::BeginComponentOverlap` (`0x02644000`):

```c
TArray<FOverlapInfo>::Emplace<FOverlapInfo>(&this->OverlappingComponents, p1);   // асимметрия
FOverlapInfo Tmp(&local_b8, this, -1);
TArray<FOverlapInfo>::AddUniqueImpl<FOverlapInfo>(&OtherComp->OverlappingComponents, &Tmp);  // 0x0264418D
```

`AddUniqueImpl` — линейный скан со **шагом 0x98** (152 байта на `FOverlapInfo`).
Обратите внимание на асимметрию: в свою сторону `Emplace` (дубликаты допускаются),
в сторону партнёра `AddUnique` (скан). Именно эта связка раздувает O(n²).

### Периодичность вызовов

`APrimalStructureTurret::Tick` → `GetAmmoNearby` (`0x00A3A129`) — **каждый тик**,
таймера между проверкой флага и вызовом нет. Внутри `OctreeType=0xF`, `bForce=true`.

Полный список call-site `ServerOctreeOverlapActors` — 21, из них значимые:
`CountCharactersResolvingGroundLocationInSphere` `0x012B0185`, `GetAmmoNearby`
`0x00A2AE89`, `Ballista::GetAmmoNearby` `0x00A58FAB`, `APrimalCharacter::TakeDamage`
`0x009454FE` (на каждый урон), `PingNearbyPlayers` `0x00EC789B`, `ServerDownloadDino`
`0x00E700B7`, остальные — 10 вызовов AOE-чит-команд.

### Результат не сохраняется в поле актора

Это локальный `TArray<AActor*>` (sret), потребляемый вызывающим на месте:
`GetAmmoNearby` делает линейный проход по возврату; `TakeDamage` — проход в радиусе
точки удара; `ServerDownloadDino` — проверку количества (`CMP EAX,0x3`).

### Эскиз оптимизации

| Вариант | Точка | Риск |
|---|---|---|
| дедупликация на выходе октавы | хук call-site `0x00A3A129` | **средний** — промах по цели на 1 тик |
| **патч `BeginComponentOverlap`** | `0x0264418D`, заменить скан на `TSet`-сайд-структуру по `(CachedCompPtr, Item)` | **средний → высокий**: нужна синхронная правка `EndComponentOverlap` `0x026442D0`, иначе «прилипшие» пересечения |
| патч `ServerOctreeOverlapActors` | `0x012871E0` | **низкий**, но выигрыш близок к нулю |

**Итоговый риск-класс: СРЕДНИЙ**, если трогать только горячий путь `GetAmmoNearby`
и/или `BeginComponentOverlap`. Пути `TakeDamage` и `exec*` не трогать — там ВЫСОКИЙ.

### Обязательный белый список (RVА подтверждены в PDB)

| Что | RVA | Размер |
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

Текущий `tickprof_overlap_keep.txt` недостаточен: `Trigger` и `Turret` как подстроки
слишком широки, `ABaseBoxTrigger`/`AHazardTrigger_Slide`/`APrimalStructureBearTrap`
не покрыты явно.

### Не найдено

1. `AddUnique` внутри `ServerOctreeOverlapActors*` — **не найдено** (это и есть опровержение).
2. Вызовов `ServerOctreeOverlapActorsClassBitMask` из C++ — нет, только exec-thunk `0x0168A199`.
3. Прямых C++-вызовов `UpdateOverlaps` — нет: 39 xref, все DATA (таблицы exec-thunk'ов).
4. Таймера между флагом и `GetAmmoNearby` — нет, частота = каждый тик.
5. `APrimalStructureTrap::*` — 0 совпадений по PDB; реальные классы ловушек перечислены выше.
6. Поле актора для результата — не найдено; результат только стековый `TArray` + out-парам Blueprint.
7. Хуков на `ServerOctreeOverlapActors*` в установленных ArkApi-плагинах — 0 совпадений.
8. Порядок `EServerOctreeGroup` ↔ индекс в таблице масок — достоверно установлены только **значения масок**, не имена.

---

## A3. Инвентарь: GetItemTemplateQuantity / IsValidForCrafting

### Символы

| Символ | RVA | Размер |
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

### Что сканируется

`GetItemTemplateQuantity` — **O(N)** линейный проход по `InventoryItems`
(`TArray` по смещению `+0x118` **в компоненте**, не в акторе). Кэша и мемоизации
нет: ни глобальных обращений, ни полей состояния.

Вложенных циклов внутри нет — вложенность появляется у вызывающих:
`MeetBlueprintCraftingRequirements`, `MeetRepairingRequirements`, `HasResources`,
`TestMeetsCraftingRequirementsPercent` — все **O(R·N)**.

Узкое место — не проход, а **стоимость фильтрации одного элемента**: на элемент
приходится 1–2× `StaticClass()`, 1× `IsChildOf()`, 1× `IsA()` и опционально
виртуальный `IsValidForCrafting` (1665 Б, внутри до 2 входов в Blueprint-VM).

### Per-tick или по событию — КРИТИЧНО

**Не «для каждого актора каждый тик».** Per-tick путей ровно пять, все узкие:

1. `TickComponent` → `TickCraftQueue` → `MeetRepairingRequirements` → 2× `GetItemTemplateQuantity`.
   Гейт: активная очередь ремонта.
2. `TickComponent` → `TickCraftingItem` (virtual `0x338`) → до 3× `MeetBlueprintCraftingRequirements`.
   Гейт: на каждый **активно крафтящийся** blueprint — каждый тик.
3. `APrimalStructureTurret::Tick` → `GetAmmoNearby` → 2× `GetItemTemplateQuantity` — каждая турель каждый тик.
4. `APrimalStructureTurretBallista::Tick` → `CanFire`/`CanReload` → `GetAmmoAmount` — каждая баллиста каждый тик.
5. `APrimalStructurePlacer::Tick` — только пока игрок тянет призрак постройки.

Остальные 69 call-site — по событию (добавление/удаление, открытие инвентаря, RPC).

`IsValidForCrafting` вызывается только при `bCheckValidForCrafting == true`; его
передаёт лишь `MeetBlueprintCraftingRequirements`. Остальные передают `false`.

### Эскиз индекса

| Аспект | Решение |
|---|---|
| Где хранить | side-map **`UPrimalInventoryComponent*` → индекс** (не актор, не глобально) |
| Структура | `ByClass: TMap<UClass*, FInvBucket>` по **точному** классу + `MatchCache` (производный) |
| Почему корзины, а не одна сумма | иначе нельзя корректно посчитать `bRequireExactClassMatch` (`bOverrideExactClassCraftingRequirement`) и `bIgnoreBlueprints` (`bIsBlueprint` — инстанс-флаги) |
| **Точки инвалидации** | ровно **4**: `AddToInventory` `0x7AC9A0`, `RemoveItemFromInventory` `0x7AFCA0`, `SetQuantity` `0x80D4C0`, `IncrementItemQuantity` `0x7F4D60` + rebuild при `LoadedFromSaveGame` `0x781330` |
| Что можно кэшировать | корзины **без** учёта `IsValidForCrafting`; предикаты применяются к конкретным предметам на месте |
| Что **нельзя** | сумму «только валидных для крафта»: она зависит от прочности, `IsBroken`, `OwnerInventory`, родительской структуры и Blueprint — **ни одно из этого не мутирует `InventoryItems`** |

**Риск-класс: НИЗКИЙ** для варианта с корзинами без `IsValidForCrafting`;
**ВЫСОКИЙ** при попытке агрегировать «сумму только валидных».

Что сломается при устаревшем кэше: занижено → `MeetRepairingRequirements()==false` →
запись **удаляется из `ItemCraftQueueEntries`** — тихая потеря очереди ремонта;
завышено → `ServerCraftItem` спишет ресурсы, которых нет → дюп/рассинхрон.

### Оценка выигрыша

Полный кластер A3 = **275 сэмплов = 6.45% исполняемого кода** Genesis.
При 80% сокращении — около **0.72% wall**. Реально, но не главный резерв:
Blueprint-VM (22.8%) и `IsA` (6.66%) больше.

### Не найдено

1. `UPrimalInventoryComponent::HasItem`, `GetInventoryItems`, `GetItemQuantity`, `GetCraftingCost` — символов нет.
2. Прямых вызовов `IsValidForCrafting` — **0**; только vtable-слот `0x3A8` и exec-thunk.
3. Распределение вызовов по 74 call-site не измерено (профиллер даёт self-time по функции).
4. Фактические N и R на Genesis не измерены офлайн.
5. Какие Blueprint-графы вызывают `execGetItemTemplateQuantity` `0x179BFD0` — байткод в `.uasset` офлайн не читается.
6. Значение `bUseCraftQueue` в CDO не проверено.
7. Вклад `IsA`, приходящийся именно на `GetItemTemplateQuantity`, офлайн не выделен (2 call-site из 1360).

---

## A4. SaveWorld: где уходят 3.9–4.3 с

### ГЛАВНЫЙ РЕЗУЛЬТАТ: это СЕРИАЛИЗАЦИЯ, а не сброс на диск

| Символ | RVA | Размер |
|---|---|---|
| `UShooterCheatManager::execSaveWorld` | `0x016CDF70` | 26 |
| `UShooterCheatManager::SaveWorld` | `0x00BC95F0` | 183 |
| `AShooterGameMode::SaveWorld(bool)` | `0x00CDC220` | 4291 |
| `UWorld::SaveToFile` | `0x02755CC0` | 8788 |
| `WorldSerializedObject::SerializeHeaders` | `0x01FD8340` | 2082 |
| `WorldSerializedObject::SerializeObjectData` | `0x01FD8FA0` | 380 |
| `UStruct::SerializeTaggedProperties` | `0x01F7E900` | 8666 |
| `UProperty::ShouldSerializeValue` | `0x01FB2000` | 444 |
| `UWorld::SaveToFile`: вызов `AllowSaving` | `0x0275738F` | — |
| **`FWriteFileTask::GetDesiredThread`** | `0x00D66650` | 6 |
| `FWriteFileTask::DoTask` | `0x02746940` | 614 |
| `FFileHelper::SaveArraysToFile` | `0x01F1E200` | 159 |

**Дисковая запись уже вынесена в отдельный поток TaskGraph.**
`FWriteFileTask::GetDesiredThread()` декомпилируется в `{ return AnyNormalThreadNormalTask; }`.
Файловый дескриптор открывается **только** в `FWriteFileTask::DoTask`, то есть в воркере.
`FlushFileBuffers` в PDB **отсутствует**; `FArchiveFileWriterGeneric::Flush` `0x01EBD280`
имеет 0 вызывающих — это flush пользовательского буфера, не диска.

RCON `saveworld` передаёт `bForceWaitOnSaveToComplete = 0`, LocalPlayer'ов на
выделенном сервере нет → функция возвращается сразу после диспатча задачи.
Значит замеренные 3.9–4.3 с = ровно сериализация объектов в память.

**Оговорка:** при `bForceWaitOnSaveToComplete = true` (шутдаун) или при наличии
LocalPlayer выполняется цикл ожидания `FGraphEvent::IsComplete` `0x00CDD195` +
`Sleep(0.01)` `0x00CDD1C2`, и тогда измеренное время **включает** запись на диск.
Для этой ветки нужен отдельный замер.

### Инкрементального сохранения в ARK НЕТ

Цепочка `UPackage::SavePackage` / `FSavePackage` / `FArchiveState` в PDB **отсутствует
полностью**. Глобалы `GSavePackageFileName` `0x04937D08` и `SavePackageState` `0x0491C6A8`
имеют 0 живых xref. Сейв мира использует **самописный формат ARK**, не UE-пакетный.

Ключ `-newsaveformat` → `GCurrentWorldSaveVersion` `0x048B2AE4`: 9 по умолчанию,
11 при флаге. Это **смена версии, не дельта**.

### Точки зацепа

| Вариант | Точка | Выигрыш | Риск | Вердикт |
|---|---|---|---|---|
| порционное сохранение по акторам | `0x00CDC220` | ~0 | **высокий** | **нет** |
| асинхронная запись | `0x02746940`, диспатч `0x02757DFF` | **уже есть в штате** | низкий | только полировка |
| кэш байтов по акторам | фильтр `AllowSaving`, вызов `0x0275738F` | до ~50% | **высокий** | только с fallback |

**Красная линия (порционное):** `WorldSerializedObject::SerializedObjectsStack` —
глобальный, строится в проходе 1 и потребляется в проходе 2; между кадрами геймплей
его мутирует. Формат плоский, заголовки связаны `DataOffset`; загрузчик
`UObjectSerializer::DeSerializeObject` `0x003C2C90` идёт по этому смещению.
Порча = **нечитаемый `.ark` после рестарта**. Пропуск актора в `.ark` **молча**
теряет объекты — без падения, что хуже всего.

**Красная линия (кэш байтов):** `SerializeObjectData` `0x01FD8FA0` уже имеет внутренний
дедуп, но только в пределах **одного** файла. Формата «ссылка на предыдущий файл» нет.
Корректный dirty-tracking невозможен: мутации идут из натива, Blueprint, инвентаря и физики.

### Не найдено

1. `UWorld::SaveWorld`, `UPackage::SavePackage`, `FSavePackage`, `FMemoryWriter`, `FlushFileBuffers` — символов нет.
2. RCON/cvar/GameUserSettings для инкрементального сейва — не найдено (строк в бинарнике нет).
3. Виртуальный `vtable+0x9F8`, вызываемый в `0x027573AB` — имя не определено; во **всех** 208 vtable слотов значение одинаково `0x01401BCBB0` (3 байта, `ret`), перекрытий нет — пустая точка расширения.
4. `UPrimalItem::IsValidForCrafting` — 0 прямых вызывающих. `GetItemTemplateQuantity` — 51 прямой вызывающий, **ни один не в сейв-пути**. Значит 2.86%+2.52% профиля приходят из Blueprint-хука (вероятно `SHOOTERGAME_BPPreSerializeSaveGame` `0x04934050`) через `ProcessEvent`. Нативный владелец **не идентифицирован**.
5. Что именно пишется в каждый из 5–6 буферов `FWriteFileTaskInfo` — поимённо не верифицировано.
6. Какой вызов инициирует автосейв — у `SaveWorld` 0 нативных xref; триггер Blueprint.
7. Сколько времени занимает сама дисковая запись — прямого замера не было.

---

## A5. BP-машина и трассировщик

### Символы и раскладка

| Что | RVA |
|---|---|
| `UObject::ProcessInternal` | `0x01FC0270` (344 Б) |
| `UObject::ProcessContextOpcode` | `0x01FC1FA0` |
| `UObject::CallFunction` | `0x01FBFEF0` |
| `UFunction::Invoke` | `0x01F867C0` |
| `FFrame::FFrame` | `0x01FA57E0` |
| `GNatives` | `0x0491C6B0` |
| `GScriptStack` | `0x04937F00` |
| `NamePoolData` | `0x0498A1C8` |

**Раскладка `FFrame`:** `Node +0x10`, `Object +0x18`, `Code +0x20`, `Locals +0x28`,
`MostRecentProperty +0x30`, `MostRecentPropertyAddress +0x38`, `OutParms +0x78`.
`Locals` — **не** `TArray<uint8*>`, а плоский буфер; адресация `Locals[Prop->Offset_Internal]`,
`UProperty+0x4C = Offset_Internal`.

**Раскладка `UFunction`:** `Name +0x18`, `Outer +0x20`, `ParmsSize +0x40`,
`Script +0x48`, `FunctionFlags +0x90`, `Func +0xA8`.

### Ключевой факт

```asm
; UFunction::Bind, 0x141F86D6D
TEST dword ptr [R9+0x90], 0x400   ; FUNC_Native
JNZ   ...
LEA   RAX,[0x141FC0270]           ; &UObject::ProcessInternal
MOV   qword ptr [R9+0xA8],RAX    ; UFunction->Func
```

**Для любой скриптовой `UFunction` поле `Func == &ProcessInternal`.**

### Диспетчер

`GNatives[256]` (2048 байт), индекс = байт опкода, `CALL [RDI+RAX*8]`.
Заполняется 63 статик-инициализаторами, которые сначала забивают все 256 слотов
значением `execUndefined`. Переход к следующей инструкции делает сам диспетчер
(`Code++` **до** вызова). 68 символов `exec*` лежат блоком `0x01FC1050…0x01FC36B6`.

**Арифметических опкодов в этом билде нет вообще** — слоты `0x45,0x46,0x47,0x49` пусты.

### Точка зацепа трассировщика

| Критерий | `ProcessInternal` | `Invoke` |
|---|---|---|
| Частота | 1 раз на вход в скриптовую UFunction | 1 раз на **любой** вызов, включая native |
| Покрытие | **надмножество** | не видит прямой `CallFunction→ProcessInternal` |
| Данные | `RDX = FFrame*`, известен `FFrame->Node` | `RCX = UFunction` |
| Call-site | **нет** (косвенный вызов через `Func`) | есть (2 шт.) |

**Выбор: хук тела `ProcessInternal` (`0x01FC0270`).** Это ровно нужная гранулярность
при минимальной частоте. Встраивать в `GNatives` или каждый `exec*` нельзя —
частота на порядок выше.

### Эскиз трассировщика

| Аспект | Решение |
|---|---|
| Точка | detour первых 12 байт `ProcessInternal` |
| Что логируем | **только** полное имя `UFunction` (`+0x18`, FName) и счётчик. Аргументы не пишем |
| Хот-путь | 10–12 инструкций, ~5–7 циклов; `FName→str` **никогда** в хот-пути, резолв при сбросе |
| Буферизация | фиксированный кольцевой буфер в `.data`; индекс записи `__declspec(thread)` — без атомик; счётчики — отдельная таблица |
| Сброс | отдельный поток раз в N сек; сырые записи + резолв строк |
| Потоки | хот-путь только читает; cold path (промах) — `SRWLOCK`; TLS статический, не `TlsAlloc` |
| Реентерабельность | хук **не зовёт ни одного API UE** — нет риска рекурсии из лога |
| Выключатель | `bptrace 0|1`, по умолчанию **0**; в выключенном состоянии байты патча **не ставятся вообще** (буквальный ноль влияния) |
| Оценка накладных | +0.07…0.33% кадра — **в 3…15 раз дешевле бюджета 1.1%**. Расчётная, не измеренная |
| **Риск-класс** | **СРЕДНИЙ** — вход в самую горячую функцию; ошибка проявляется немедленно |

**Пункт обязательной проверки перед выкаткой:** `ENDBR64` в первых инструкциях
`ProcessInternal` **отсутствует**. При включённом CET нужен CET-совместимый
trampoline `mov r11, imm64; jmp r11` (12 байт, стек не трогает).

### Не найдено

1. Фактическое число вызовов `ProcessInternal`/`Invoke` в секунду **не измерено** — проценты накладных расчётные.
2. Состояние `GFullStackTrace` и цена `GScriptStack` не проверены.
3. Размер `FFrame` целиком не подтверждён (предположительно `0x90`).
4. `UFunction+0x20 = Outer` — **вывод** из обхода Super-цепочки, не тип из PDB.
5. Содержимое `GNatives` в рантайме не проверено — карта восстановлена из статик-инициализаторов.
6. Поведение под CET/shadow stack не проверено.
7. Причина отсутствия арифметических опкодов **не выяснена**; вывод «арифметика не поддерживается» делать нельзя.

---

## A6. Гигиена отчётов

Выполнено, все правки внесены в `REPORT-Genesis.md`, `REPORT-TheIsland.md`,
`REPORT-Fjordur.md`. Отдельный раздел A6 в каждом файле.

**Ключевой результат проверки:** завершённого стартового сохранения перед П0/П1
**не было ни на одной карте**. Свидетельство — `*_AntiCorruptionBackup.bak` создаётся
**во время загрузки мира**, а сам `.ark` переписывается только при реальном сохранении:

| Карта | запуск | `.bak` | `.ark` переписан впервые |
|---|---|---|---|
| Genesis | 00:32:48 | 00:37:54 (в загрузке) | 01:21:38 |
| TheIsland | 01:33:43 | 01:37:56 (в загрузке) | 02:07 |
| Fjordur | 02:19:19 | 02:23:59 (в загрузке) | 02:38 |

**Посылка ревьюера «Genesis ждал конца стартового сейва» не подтверждается данными.**

## A7. ARCH.md

Создан отдельный документ: 5 действующих оптимизаций, 4 новых патча с риск-классами,
конфигурация, встроенный мониторинг с признаком `CONTAMINATED`, спецификация
команды `perf.selftest` и порядок выкатки.