# -*- coding: utf-8 -*-
"""Грузит TSV из pdbsym.exe в SQLite: rva -> имя функции, с индексами."""
import sqlite3
import sys
import time

tsv = sys.argv[1] if len(sys.argv) > 1 else r"C:\Dev\_research\v361.tsv"
db = sys.argv[2] if len(sys.argv) > 2 else r"C:\Dev\_research\v361.sqlite"

con = sqlite3.connect(db)
con.execute("PRAGMA journal_mode=OFF")
con.execute("PRAGMA synchronous=OFF")
con.execute("DROP TABLE IF EXISTS fn")
con.execute("CREATE TABLE fn(name TEXT, rva INT, size INT, tag INT)")

t0 = time.time()
rows = []
n = 0
with open(tsv, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 4:
            continue
        try:
            rows.append((parts[0], int(parts[1]), int(parts[2]), int(parts[3])))
        except ValueError:
            continue
        if len(rows) >= 100000:
            con.executemany("INSERT INTO fn VALUES(?,?,?,?)", rows)
            con.commit()
            n += len(rows)
            rows.clear()
if rows:
    con.executemany("INSERT INTO fn VALUES(?,?,?,?)", rows)
    n += len(rows)
con.commit()

con.execute("CREATE INDEX IF NOT EXISTS ix_rva ON fn(rva)")
con.execute("CREATE INDEX IF NOT EXISTS ix_name ON fn(name)")
con.commit()

print("rows:", n, "in %.1fs" % (time.time() - t0))
for q in (
    "SELECT count(*) FROM fn WHERE tag=5",
    "SELECT count(*) FROM fn WHERE tag=7",
):
    print(q, "->", con.execute(q).fetchone()[0])

# проверка: ключевые функции тика
for name in ("UWorld.Tick", "UWorld::Tick", "FEngineLoop::Tick", "UGameEngine::Tick",
             "FTickTaskManager::StartFrame", "FTickTaskManager::RunTickGroup",
             "UNetDriver::TickDispatch", "UObject::CollectGarbage", "UWorld::RunTickGroup"):
    row = con.execute("SELECT name, rva, size FROM fn WHERE name=? LIMIT 1", (name,)).fetchone()
    print("  %-32s %s" % (name, row))
con.close()