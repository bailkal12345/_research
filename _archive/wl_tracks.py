import io, datetime
# белая метка для overlaptrim v3 — из RE-находок
keep = """# Классы, чьи overlap-события обязаны остаться (doit.txt §6, Агент-2).
# Подстрока полного имени класса. Пустой файл = встроенный список.
ShapeComponent
SphereComponent
BoxComponent
CapsuleComponent
Trigger
Turret
GrapplingHook
"""
io.open(r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\tickprof_overlap_keep.txt",
        "w", encoding="utf-8").write(keep)

p = r"C:\Dev\_research\worklog.md"
add = """
## {ts} Треки Агент-2 и Агент-3 (параллельно слоту 1)

Агент-2 «Статика/RE» — четыре пути «больших баз» верифицированы по v361.sqlite:
  * октри/обновление пересечений: UPrimitiveComponent::UpdateOverlaps 0x02644CA0 (2373 б),
    BeginComponentOverlap 0x02644000, EndComponentOverlap 0x026442D0,
    IsOverlappingComponent 0x02643C80, UWorld::OverlapMultiInternalOctree 0x0275ABB0;
  * списки пересечений: TArray<FOverlapInfo>::AddUniqueImpl 0x024E3050;
  * дорманс: AActor::IsNetRelevantFor 0x0247B570, AActor::FlushNetDormancy 0x0246B880;
    UWorld::FlushNetDormancy и UNetDriver::ConditionalFlushNetDormancy в PDB ОТСУТСТВУЮТ;
  * SaveWorld/GC: UWorld::SaveWorld и UWorld::SavePackage в PDB ОТСУТСТВУЮТ
    (вероятно инлайнятся) — понадобится иной способ для ТЗ по П3;
    CollectGarbage 0x01F8B2A0, IncrementalPurgeGarbage 0x01F8ACD0,
    UObject::BeginDestroy 0x01FA7B90, UWorld::CleanupWorld 0x0274F7C0.

Белая метка overlaptrim (RE-основание): ABaseBoxTrigger::BPOnTriggerBeginOverlap /
BPOnTriggerEndOverlap (ловушки обязаны получать overlap), AActor::IsPrimalStructureTurret,
APrimalCharacter::CanIgnoreImmobilizationTrap, APrimalProjectileGrapplingHook.
Форменные компоненты: UShapeComponent 0x00A13F80, USphereComponent 0x003EBA30,
UBoxComponent 0x001F0CB0, UCapsuleComponent 0x004407D0.

Агент-3 «Код» — overlaptrim v3 собран оффлайн: команда TickProf.overlaptrim3 <порог>,
белая метка из файла tickprof_overlap_keep.txt (подстроки полного имени класса),
встроенный список по умолчанию. Ключ отката revert_optimizations.py
(выключает кэши, возвращает кламп 120 и штатный NetServerMaxTickRate;
снятые overlap-события требуют перезапуска).
НЕ РАЗВЁРНУТ на стенде — красная линия §8 «поведенческие патчи в этой вахте
не применяются». Поведенческий A/B — следующее окно.

Агент-4 «Аналитика» — make_report.py (REPORT-<карта>.md) и summary_table.py
(SUMMARY.md) готовы, ждут данные слотов.
""".replace("{ts}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
io.open(p, "a", encoding="utf-8").write(add)
print("worklog дописан; белая метка развёрнута")
