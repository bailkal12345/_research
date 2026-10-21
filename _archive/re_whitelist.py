import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
print("=== классы-кандидаты в белую метку (ловушки/турели/триггеры) ===")
for kw in ("Trap","Turret","Trigger","Poison","Snapshot","Grappling","Cannon","Tesla"):
    rows = con.execute("SELECT name FROM fn WHERE name LIKE ? AND name LIKE '%::%' GROUP BY name LIMIT 6",("A%"+kw+"%",)).fetchall()
    if rows:
        print("  [%s]" % kw)
        for (n,) in rows:
            print("     ", n[:78])
print()
print("=== компоненты, чьи overlap-события использует игровая логика ===")
for p in ("UShapeComponent%","USphereComponent%","UBoxComponent%","UCapsuleComponent%",
          "USplineComponent%","UStaticMeshComponent%","UInstancedStaticMeshComponent%",
          "USkeletalMeshComponent%","UCharacterMovementComponent%","UPrimalTrigger%","UShooterTrigger%"):
    rows = con.execute("SELECT name, rva FROM fn WHERE name LIKE ? LIMIT 1",(p,)).fetchall()
    for n,r in rows:
        print("   0x%08X %s" % (r, n[:70]))
con.close()
