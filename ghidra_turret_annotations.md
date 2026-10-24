# Ghidra annotations — turret RE (v361_ShooterGameServer.exe, project ARK_SE)

Backup of in-Ghidra annotations made 24.10.2026. The Ghidra DB is persisted
(`save_all_programs` OK), this file is the redundant copy in case the project
is rebuilt or annotations are lost.

Program: `C:\asmdata\ghidra\ARK_SE` → `/v361_ShooterGameServer.exe`
Server: ghidra-mcp tcp 127.0.0.1:8089

## In-Ghidra plate comments (set + saved)

### `FindTarget` @140a263e0 (plate comment, APrimalStructureTurret::FindTarget)

```
TURRET TARGETING (v361 RE): LOS gate lives HERE, not in IsValidToFire (angle-only).
FindTarget = 2 LOS sites: site1 CALL 140a28558/140a285ae (LineTrace) +140a28624/140a286a1
(Sweep), GetActor 140a286ae; site2 (alt-aim-socket 2nd chance) 140a29c1a/140a29c70/
140a29ce6/140a29d63, GetActor 140a29d70. Trace: turret pos+TargetingTraceOffset(+3860)
-> GetTargetFireAtLocation(target)+offset, channel 5. Hit actor != target -> REJECT
(goto LAB_140a26852) unless mount/carrier special-case (+0x888/+0x870/+0x860/+0x3c0 vs
weak ptrs target+0x1540/+0xbc0/+0x1398) = "dino on structure untargetable" bug.
PATCH POINT #1: 5-byte E8 redirect of trace CALLs -> wrapper clears FHitResult if hit
actor is APrimalStructure supporting target. Tribe/buff/PreventActorTargeting checks
stay untouched.
```

### `DoFire` @140a2b9b0 (plate comment, APrimalStructureTurret::DoFire)

```
TURRET DAMAGE PATH (v361 RE): DoFire (51877 B) has 3 own LOS traces 140a2f31b/
140a34bb0/140a35720 (GetActor follows each), ConsumeAmmo 140a35b60,
SpawnActor(ProjectileClass+3968) 140a36499 -> SpawnImpactEffects 140a365e5,
CalculateInterceptPosition 140a3777d, ApplyDamage 140a38406 (instant path:
victim=[RSP+0x17c8], turret instigator R9, FireDamageType via +0xf20).
bFireProjectiles (bit4 @+3936) selects projectile vs hitscan. PATCH POINT #2 (optional):
support-structure predicate in instant trace; projectile turrets need phase-2 impact
filter (ignore registered support actor ONLY - never blanket wallbang). Branch order
pending: DoFire decompile timed out in Ghidra (79K disasm done).
```

## Key addresses (labels come from exe's PDB — source IMPORTED, reappear on reimport)

| Address | Symbol / meaning |
|---|---|
| 140a23e70 | APrimalStructureTurret class registration (ctor region) |
| 140a39740 | `APrimalStructureTurret::Tick` (21 KB) → FindTarget/SetTarget/IsValidToFire/DoFire |
| 140a263e0 | `FindTarget` (79 KB, 2839 instr) — **PATCH POINT #1** (2 LOS sites) |
| 140a2a190 | `SetTarget` |
| 140a3bfe0 | `IsValidToFire` — angle-only, no trace |
| 140a2b9b0 | `DoFire` (51877 B) — **PATCH POINT #2** (3 traces + SpawnActor + ApplyDamage) |
| 140a28558 / 140a285ae | site1 LineTrace CALLs (1428292c0 / 142829810) |
| 140a28624 / 140a286a1 | site1 Sweep CALLs (1428293d0 / 142829920) |
| 140a286ae | site1 FHitResult::GetActor |
| 140a29c1a / 140a29c70 | site2 LineTrace CALLs (alt-aim-socket path) |
| 140a29ce6 / 140a29d63 | site2 Sweep CALLs |
| 140a29d70 | site2 FHitResult::GetActor |
| 140a26852 | reject-candidate label (goto = target rejected) |
| 140a290f7 | accept-target label (rotation setup) |
| 140a2f31b / 140a34bb0 / 140a35720 | DoFire trace sites |
| 140a36499 | SpawnActor (projectile) |
| 140a38406 | ApplyDamage (instant path) |
| 140a3f460 | UpdatedTargeting (emitter only) |
| 1428292c0 / 142829810 | UWorld::LineTraceSingle variants |
| 1428293d0 / 142829920 | UWorld::SweepSingle variants |
| 14281dd20 | FHitResult::GetActor |

## PDB field facts (fieldcheck.exe + ShooterGameServer.pdb)

APrimalStructureTurret: Target +3776, AmmoItemTemplate +3784, FireInterval +3800,
TargetingLocOffset +3832, TargetingRanges +3848, **TargetingTraceOffset +3860**,
FireDamageType +3872, FireDamageAmount +3880, AimTargetLocOffset +3908,
bitflags byte +3936 (bUseNoWarning 0, bUseNoAmmo 1, bOnlyUseAmmoOnDamage 2,
bHasOmniDirectionalFire 3, **bFireProjectiles 4**, bClientFireProjectile 5,
bIsTargeting 6, bInWaterOnlyTargetWater 7), +3937 (bTurretIgnoreProjectiles 0,
bUseBPTurretPreventsTargeting 1, bAimIgnoreSockets 2, bUseAmmoFromNearbyContainer 3,
bUseMaxInventoryForAmmoContainerReload 4), AISetting +3939, ProjectileClass +3968.
**No built-in LOS-ignore flag exists.**

## FindTarget callers / pipeline

Tick @140a39740 and GetAmmoNearby @140a2a950. Base class → Auto/Heavy/Ballista/Plant
inherit (verify per-type at impl time via xrefs).
