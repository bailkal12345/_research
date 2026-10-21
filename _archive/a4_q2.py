import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')

qs = [
 ("UWorld::Save%", "name like 'UWorld::Save%'"),
 ("UWorld::SaveWorld", "name like '%SaveWorld%'"),
 ("World::%Save", "name like 'UWorld::%Save%'"),
 ("FSaveToFileTask all", "name like '%FSaveToFileTask%'"),
 ("TGraphTask<FSaveToFileTask>", "name like 'TGraphTask<FSaveToFileTask>%' and name not like '%dtor%'"),
 ("FSavePackage", "name like '%FSavePackage%'"),
 ("UPackage%", "name like 'UPackage::%'"),
 ("CollectGarbage", "name like '%CollectGarbage%' and name not like '%dtor%'"),
 ("AsyncSave", "name like '%Async%Save%' or name like '%Save%Async%'"),
 ("SaveGame", "name like '%SaveGame%' and name not like '%dtor%'"),
]
for tag, w in qs:
    q = "select name,rva,size,tag from fn where " + w + " order by rva"
    print("=== " + tag)
    rows = c.execute(q).fetchall()
    if not rows:
        print("   <none>")
    for r in rows[:60]:
        print("  %08X %6d t%d  %s" % (r[1], r[2] or 0, r[3], r[0]))
    print("   total=%d" % len(rows))
