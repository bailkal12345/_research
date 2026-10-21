import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
qs = [
 ("FObjectWriter", "name like '%FObjectWriter%' and name not like '%dtor%'"),
 ("FArchiveFileWriter%", "name like 'FArchiveFileWriter%' and name not like '%dtor%'"),
 ("FFileManagerGeneric%", "name like 'FFileManagerGeneric::%' and name not like '%dtor%'"),
 ("FWindowsPlatformFile", "name like '%PlatformFile%' and name like '%CreateFileWriter%'"),
 ("FlushFileBuffers", "name like '%FlushFileBuffers%'"),
 ("WriteFile", "name like '%WriteFile%' and name not like '%dtor%'"),
 ("FMemoryWriter", "name like 'FMemoryWriter%'"),
 ("FSaveGameSystem", "name like '%SaveGameSystem%'"),
 ("UGameplayStatics::SaveGame", "name like 'UGameplayStatics::SaveGame%'"),
 ("SaveWorld callers-ish", "name like '%ServerSaveWorld%'"),
 ("GWorldIsSaveGame", "name like '%GWorldIsSaveGame%'"),
 ("SavingWorld/IsSavingWorld", "name like '%IsSavingWorld%' or name like '%SavingWorld%' or name like '%bIsSavingWorld%'"),
 ("IncrementalSave", "name like '%Incremental%'"),
 ("Hibernate", "name like '%Hibernat%' and name not like '%dtor%'"),
]
for tag, w in qs:
    q = "select name,rva,size,tag from fn where " + w + " order by rva"
    print("=== " + tag)
    rows = c.execute(q).fetchall()
    if not rows: print("   <none>")
    n=0
    for r in rows[:45]:
        if '::`1\'::dtor' in r[0]: continue
        print("  %08X %6d t%d  %s" % (r[1], r[2] or 0, r[3], r[0])); n+=1
    print("   total=%d shown=%d" % (len(rows), n))
