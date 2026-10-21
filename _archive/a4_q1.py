import sqlite3, sys
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')

qs = [
 ("SaveToFile", "%SaveToFile%"),
 ("SaveFileObjectWriter", "%SaveFileObjectWriter%"),
 ("SerializeTaggedProperties", "%SerializeTaggedProperties%"),
 ("SavePackage", "%SavePackage%"),
 ("IncrementalPurgeGarbage", "%IncrementalPurgeGarbage%"),
 ("CleanupWorld", "%UWorld::CleanupWorld%"),
 ("UObject::Serialize", "%UObject::Serialize%"),
 ("FArchive::Flush", "%::Flush%"),
 ("SaveArrayToFile", "%SaveArrayToFile%"),
 ("TMemoryWriter::Serialize", "%TMemoryWriter%Serialize%"),
]
for tag, pat in qs:
    q = "select name,rva,size,tag from fn where name like ?"
    print("=== " + tag)
    rows = c.execute(q, (pat,)).fetchall()
    if not rows:
        print("   <none>")
    for r in rows[:40]:
        print("  %08X %6d t%d  %s" % (r[1], r[2] or 0, r[3], r[0]))
    print("   total=%d" % len(rows))
