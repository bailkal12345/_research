import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')

qs = [
 ("FWriteFileTaskInfo", "name like '%FWriteFileTaskInfo%'"),
 ("FWriteFileTask", "name like '%FWriteFileTask%'"),
 ("SerializeObjectData", "name like '%SerializeObjectData%'"),
 ("SerializeHeaders", "name like '%SerializeHeaders%'"),
 ("WorldSerializedObject", "name like '%WorldSerializedObject%'"),
 ("ShouldSerializeTransform", "name like '%ShouldSerializeTransform%'"),
 ("FArchiveState", "name like '%FArchiveState%' and name not like '%dtor%'"),
 ("ShouldSerializeValue", "name like '%ShouldSerializeValue%'"),
 ("SerializeBin", "name like '%SerializeBin%' or name like '%SerializeInt%' or name like '%SerializeName%'"),
 ("AsyncFileWriter", "name like '%AsyncFileWriter%' or name like '%AsyncWrite%'"),
 ("ArchiveFromStructured", "name like '%Structured%'"),
 ("FPackageMap", "name like '%FPackageMap%'"),
 ("FLinkerSave", "name like '%Linker%'"),
 ("CreateFileWriter", "name like '%CreateFileWriter%' or name like '%FileHelper%'"),
]
seen=set()
for tag, w in qs:
    q = "select name,rva,size,tag from fn where " + w + " order by rva"
    print("=== " + tag)
    rows = c.execute(q).fetchall()
    if not rows:
        print("   <none>")
    n=0
    for r in rows[:60]:
        if '::`1\'::dtor' in r[0]: continue
        print("  %08X %6d t%d  %s" % (r[1], r[2] or 0, r[3], r[0]))
        n+=1
    print("   total=%d shown=%d" % (len(rows), n))
