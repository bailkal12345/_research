import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
for p in ["%GetItemTemplateQuantity%","%IsValidForCrafting%","%UObject::SerializeScriptProperties%",
          "%UStruct::SerializeTaggedProperties%","%UProperty::SerializeItem%","%UPrimalInventoryComponent%Save%",
          "%SerializeBinProperty%","%UProperty::ShouldSerializeValue%","%FMemory::Memcpy%","%ShouldSave%"]:
    rows = c.execute("select name,rva,size from fn where name like ? and name not like '%dtor%' order by rva limit 20",(p,)).fetchall()
    print("=== "+p)
    for r in rows: print("  %08X %5d  %s"%(r[1],r[2],r[0]))
    if not rows: print("   <none>")
