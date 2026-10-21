import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
rows = c.execute("select name,rva,size from fn where name in ('AActor::AActor','AActor::PostInitProperties','AActor::StaticClass','AActor::PreInitializeComponents','AActor::PostInitializeComponents','AActor::BeginPlay') ").fetchall()
for r in rows: print("%08X %5d %s"%(r[1],r[2],r[0]))
print('---- APawn / AShooterCharacter ctors')
rows = c.execute("select name,rva,size from fn where name like 'AActor::%' and size>50 order by rva limit 60").fetchall()
for r in rows: print("%08X %5d %s"%(r[1],r[2],r[0]))
