import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
paths = {
 "октри/обновление пересечений": ["UPrimitiveComponent::UpdateOverlaps%","AActor::UpdateOverlaps%",
    "UWorld::OverlapMultiInternalOctree%","UPrimitiveComponent::BeginComponentOverlap%",
    "UPrimitiveComponent::GetOverlappingComponents%","AActor::GetOverlappingActors%"],
 "списки пересечений": ["UPrimitiveComponent::EndComponentOverlap%","UPrimitiveComponent::IsOverlappingComponent%",
    "TArray<FOverlapInfo,TSizedDefaultAllocator<32> >::AddUniqueImpl%"],
 "дорманс": ["AActor::IsNetRelevant%","AActor::SetNetDormancy%","UNetConnection::%","UNetDriver::%",
    "UWorld::FlushNetDormancy%","AActor::FlushNetDormancy%","UNetDriver::ConditionalFlushNetDormancy%"],
 "SaveWorld и GC": ["UWorld::SaveWorld%","UWorld::SavePackage%","CollectGarbage%",
    "IncrementalPurgeGarbage%","UObject::BeginDestroy%","UWorld::CleanupWorld%"],
}
for title, pats in paths.items():
    print("== ПУТЬ:", title)
    for p in pats:
        rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 2",(p,)).fetchall()
        for n,r,s in rows:
            print("   0x%08X %-58s %d" % (r, n[:58], s))
        if not rows:
            print("   --- %s : НЕТ" % p[:56])
    print()
con.close()
