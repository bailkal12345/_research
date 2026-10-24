# BlueprintProf fleet report: 13 servers x 2 days (23-24.10.2026)

Source: `C:\Users\Admin\Desktop\csv` - `bp_history*.csv` (13 files, one per server; two proc ids
serve two maps each, so 13 maps total), `bp_candidates*.csv`, `bp_cumulative_*.csv`.
Recomputed with `_research/bp_fleet.py` (cross-file dedup on `proc_id, ts, function`).

Raw volume: 376 758 deduped rows, **2 689 intervals** (13 maps x ~207 ten-minute intervals),
988 unique BP functions, window 23.10 07:15 -> 24.10 ~12:00.

**The earlier read of "2 processes" was wrong**: `bp_history.csv` alone is one server
(LostIsland); the full fleet lives in the numbered copies. All conclusions below use the
whole folder.

## Method note (important for reading frame_pct)

`frame_pct` is the share of the 16.6 ms frame budget, not of the real frame. Reconstructing
`sum(self_ms * frame_pct / 100)` per interval gives a median of 15.0 ms, matching median
`ms_tick` 14.5 ms. So "bp/frame %" reads as "ms of BP per frame / 16.6".

## Fleet summary

| map | intervals | tps | ms/tick | players | BP self, s | BP ms/frame | BP % of GT CPU | save, s |
|---|---|---|---|---|---|---|---|---|
| Genesis | 207 | 11.42 | 20.79 | 2.2 | 5404.8 | 3.811 | 18.3% | 1.13 |
| CrystalIsles | 207 | 10.00 | 12.00 | 1.2 | 2712.3 | 2.184 | 18.2% | 1.12 |
| Gen2 | 206 | 12.49 | 19.68 | 2.3 | 2250.8 | 1.458 | 7.4% | 1.13 |
| Extinction | 207 | 10.47 | 14.44 | 1.8 | 2008.7 | 1.545 | 10.7% | 1.11 |
| Fjordur | 207 | 13.69 | 16.23 | 3.5 | 1526.2 | 0.897 | 5.5% | 1.13 |
| Aberration_P | 207 | 10.94 | 16.42 | 1.3 | 1208.8 | 0.890 | 5.4% | 1.14 |
| Aquatica | 207 | 12.50 | 12.42 | 2.6 | 1195.7 | 0.770 | 6.2% | 1.15 |
| LostIsland | 207 | 12.10 | 15.21 | 2.8 | 1186.7 | 0.790 | 5.2% | 1.14 |
| TheCenter | 207 | 11.79 | 13.65 | 2.3 | 1174.9 | 0.803 | 5.9% | 1.13 |
| TheIsland | 208 | 12.80 | 20.74 | 3.5 | 1070.1 | 0.670 | 3.2% | 1.16 |
| Valguero_P | 207 | 12.94 | 13.64 | 2.2 | 842.4 | 0.524 | 3.8% | 1.14 |
| Ragnarok | 207 | 9.95 | 11.32 | 1.7 | 770.2 | 0.623 | 5.5% | 1.13 |
| ScorchedEarth_P | 205 | 5.91 | 4.11 | 0.3 | 121.0 | 0.167 | 4.1% | 1.12 |

Fleet total: **21 472 s of BP self time over 18 247 860 s of wall = 0.118%**.
Median BP share of a frame is **4.8%** (min 2.7%, max 8.2%); median tick 14.5 ms of a
16.6 ms budget.

## The BP VM is not the tps limiter

- ScorchedEarth_P runs **5.9 tps with 0.167 ms/frame of BP** (~0% load).
- Reverse correlation between BP time and tps: intervals with tps<5 average 0.85 s BP self
  per 600 s; intervals with tps>13 average 6.52 s. More players and actors produce more BP
  work *and* higher tps.
- Low tps on near-empty servers (SE 3.6, Ragnarok 7.0) is the prod plugin's power-saving
  throttle, as established earlier - not lag.

Consequence: optimizing BP can recover at most a few percent of frame time. The remaining
budget sits in the native part (AI, physics, replication) and in saves.

## Function-family split (all maps)

```
 5033.5 s  23.4%  108 426 110  BuffTickServer
 3749.1 s  17.5%  1 040 075 144  ReceiveTick
 2096.1 s   9.8%  240 410 365  Transform__UpdateFunc
 1929.2 s   9.0%  165 263 600  BlueprintUpdateAnimation
 1586.3 s   7.4%   92 487 860  BPTimerServer
  701.5 s   3.3%   16 522 050  ThrottledTick
  522.3 s   2.4%  166 761 606  ReceiveExecute
  470.3 s   2.2%  191 780 898  BlueprintOverrideWantsToRun
  396.5 s   1.8%    7 700 993  TryNextAbility
  367.8 s   1.7%   12 349 160  Tick
  333.2 s   1.6%  254 477 206  ReceiveConditionCheck
```

Ticking families (`BuffTickServer` + `ReceiveTick` + `BPTimerServer` + `ThrottledTick` +
`Tick`) = **58% of all BP time**. Throttle lists should target these families rather than
individual classes.

Mods: **12.5%** of BP self overall, concentrated as CrystalIsles 2310 s, Ragnarok 268 s,
Fjordur 46 s, LostIsland 42 s. The other nine maps are essentially vanilla-only.

## Per-map hotspots (top 5, self time)

### Genesis - 5404.8 s
```
3940.4 s 72.9%  8 104 995  Buff_UnderwaterCyclone_C:BuffTickServer
 159.6 s  3.0% 22 484 270  Desmodus_Character_BP_C:ReceiveTick
  90.0 s  1.7% 23 124 550  Buff_Grappled_BogSpider_C:BuffTickServer
  77.0 s  1.4%  2 270 446  BaseHumanAnimBP_C:BlueprintUpdateAnimation
  74.5 s  1.4%    258 844  BogSpider_Character_BP_C:BPTimerServer
```

### CrystalIsles - 2712.3 s
```
2027.2 s 74.7% 158 172 121  BP_FloatingObject_2_C:Transform__UpdateFunc   (mod)
  67.2 s  2.5%   1 718 010  Volume_Shock_C:ApplyEffects
  50.6 s  1.9%  40 982 634  BP_FloatingObject_MedSlow_C:ExecuteUbergraph_...  (mod)
  43.2 s  1.6%  41 119 122  BP_FloatingObject_SmallFast_C:Transform__UpdateFunc (mod)
  40.9 s  1.5%   1 240 573  Mammoth_Character_BP_C:ThrottledTick
```

### Gen2 - 2250.8 s
```
 375.1 s 16.7% 112 764 100  BrainSlug_Character_BP_C:BlueprintOverrideWantsToRun
 367.8 s 16.3%  12 349 160  Dynamic_PhysicsVolume_Hazard_C:Tick
  92.7 s  4.1%  25 680 965  Buff_Grappled_BogSpider_C:BuffTickServer
  65.6 s  2.9%   1 741 783  LionfishLion_Character_BP_C:ReceiveTick
  59.9 s  2.7%   1 712 062  BaseHumanAnimBP_C:BlueprintUpdateAnimation
```

### Extinction - 2008.7 s
```
 277.2 s 13.8%   3 801 391  IceJumper_AIController_BP_C:TryNextAbility
 235.5 s 11.7%  14 662 772  Scout_AIController_BP_C:FindAggressors
 155.7 s  7.8%     406 930  BogSpider_Character_BP_C:BPTimerServer
 131.4 s  6.5%  16 045 720  Desmodus_Character_BP_C:ReceiveTick
  84.7 s  4.2%   6 049 987  FindEnemyTargetConditional_SRV_C:ReceiveTick
```

### Fjordur - 1526.2 s
```
 179.4 s 11.8%   8 078 564  LionfishLion_Character_BP_C:ReceiveTick
  96.5 s  6.3%   1 573 229  Mammoth_Character_BP_C:ThrottledTick
  82.2 s  5.4%   1 322 935  MilkGlider_Character_BP_C:BPTimerServer
  65.8 s  4.3%   2 140 291  BaseHumanAnimBP_C:BlueprintUpdateAnimation
  57.3 s  3.8%   2 427 506  Desmodus_Character_BP_C:ReceiveTick
```

### Aberration_P - 1208.8 s
```
 150.2 s 12.4%     628 470  StorageBox_TekShield_C:CheckForPawnPushing
 148.1 s 12.3%   1 101 222  EggIncubator_C:ThrottledTick
  85.6 s  7.1%       2 925  Buff_TekStrider_Harvester_C:passed-in foliage
  61.4 s  5.1%   1 027 184  Buff_ChargeManager_C:BuffTickServer
  54.6 s  4.5%     138 654  Dino_Character_BP_Climber_C:BPTimerServer
```

### Aquatica - 1195.7 s
```
 158.7 s 13.3%   5 735 258  LionfishLion_Character_BP_C:ReceiveTick
  69.9 s  5.8%   1 552 230  Aquatica_C:ReceiveTick
  66.6 s  5.6%   1 464 363  Buff_ChargeManager_C:BuffTickServer
  59.4 s  5.0%   1 866 327  BaseHumanAnimBP_C:BlueprintUpdateAnimation
  55.2 s  4.6%   2 196 150  MilkGlider_Character_BP_C:BPTimerServer
```

### LostIsland - 1186.7 s
```
 141.9 s 12.0%   5 031 072  LionfishLion_Character_BP_C:ReceiveTick
 106.3 s  9.0%  12 215 294  Desmodus_Character_BP_C:ReceiveTick
  54.8 s  4.6%   1 343 957  IceJumper_AIController_BP_C:TryNextAbility
  52.6 s  4.4%     851 611  MilkGlider_Character_BP_C:BPTimerServer
  50.2 s  4.2%   1 678 185  BaseHumanAnimBP_C:BlueprintUpdateAnimation
```

### TheCenter - 1174.9 s
```
 193.5 s 16.5%  10 346 052  LionfishLion_Character_BP_C:ReceiveTick
 116.8 s  9.9%   6 875 214  Desmodus_Character_BP_C:ReceiveTick
  75.1 s  6.4%   2 437 396  BaseHumanAnimBP_C:BlueprintUpdateAnimation
  70.5 s  6.0%   2 594 975  MilkGlider_Character_BP_C:BPTimerServer
  47.6 s  4.0%   1 432 397  Mammoth_Character_BP_C:ThrottledTick
```

### TheIsland - 1070.1 s
```
  70.7 s  6.6%   7 633 561  Desmodus_Character_BP_C:ReceiveTick
  67.6 s  6.3%   2 099 978  BaseHumanAnimBP_C:BlueprintUpdateAnimation
  45.6 s  4.3%     569 476  MilkGlider_Character_BP_C:BPTimerServer
  44.8 s  4.2%   1 531 058  Mammoth_Character_BP_C:ThrottledTick
  39.2 s  3.7%   7 984 512  Bee_Queen_Character_BP_C:BPTimerServer
```

### Valguero_P - 842.4 s
```
  54.9 s  6.5%   1 586 414  Mammoth_Character_BP_C:ThrottledTick
  48.3 s  5.7%   1 375 719  BaseHumanAnimBP_C:BlueprintUpdateAnimation
  32.6 s  3.9%     763 316  MilkGlider_Character_BP_C:BPTimerServer
  30.3 s  3.6%   5 667 489  Bee_Queen_Character_BP_C:BPTimerServer
  25.8 s  3.1%   2 339 709  Desmodus_Character_BP_C:ReceiveTick
```

### Ragnarok - 770.2 s
```
  69.1 s  9.0%     812 815  MilkGlider_Character_BP_C:BPTimerServer
  61.5 s  8.0%  22 114 986  Spike_Trap_C:RaiseSpikes__UpdateFunc        (mod)
  58.7 s  7.6%  22 115 774  Spike_Trap_C:LowerSpikes__UpdateFunc       (mod)
  54.3 s  7.0%  28 416 615  LaunchingZone_C:ReceiveTick
  49.3 s  6.4%   1 235 280  Mammoth_Character_BP_C:ThrottledTick
```

### ScorchedEarth_P - 121.0 s
```
  10.7 s  8.8%     277 931  BaseHumanAnimBP_C:BlueprintUpdateAnimation
   8.6 s  7.1%         333  Buff_TekStrider_Harvester_C:passed-in foliage
   8.3 s  6.9%     726 568  TestGameMode_C:ReceiveTick
   5.4 s  4.4%      15 715  Dino_AIController_BP_C:ReceiveBeginPlay
   4.2 s  3.5%     155 244  Hyaenodon_Character_BP_C:BPTimerServer
```

## Fleet-wide top-25 by self time

```
self_s   pct     calls        us/call  function
3940.4  18.35%    8 104 995   486.2   Buff_UnderwaterCyclone_C:BuffTickServer (Genesis)
2027.2   9.44%  158 172 121    12.8   BP_FloatingObject_2_C:Transform__UpdateFunc (CI, mod)
 375.1   1.75%  112 764 100     3.3   BrainSlug_Character_BP_C:BlueprintOverrideWantsToRun
 367.8   1.71%   12 349 160    29.8   Dynamic_PhysicsVolume_Hazard_C:Tick
 277.2   1.29%    3 801 391    72.9   IceJumper_AIController_BP_C:TryNextAbility (Ext)
 235.5   1.10%   14 662 772    16.1   Scout_AIController_BP_C:FindAggressors (Ext)
 193.5   0.90%   10 346 052    18.7   LionfishLion_Character_BP_C:ReceiveTick (Center)
 179.4   0.84%    8 078 564    22.2   LionfishLion_Character_BP_C:ReceiveTick (Fjordur)
 158.7   0.74%    5 735 258    27.7   LionfishLion_Character_BP_C:ReceiveTick (Aquatica)
 155.7   0.73%      406 930   382.6   BogSpider_Character_BP_C:BPTimerServer (Ext)
 150.2   0.70%      628 470   239.0   StorageBox_TekShield_C:CheckForPawnPushing (Aberr)
 148.1   0.69%    1 101 222   134.5   EggIncubator_C:ThrottledTick (Aberr)
 141.9   0.66%    5 031 072    28.2   LionfishLion_Character_BP_C:ReceiveTick (Lost)
 131.4   0.61%   16 045 720     8.2   Desmodus_Character_BP_C:ReceiveTick (Ext)
 116.8   0.54%    6 875 214    17.0   Desmodus_Character_BP_C:ReceiveTick (Center)
 106.3   0.49%   12 215 294     8.7   Desmodus_Character_BP_C:ReceiveTick (Lost)
  96.5   0.45%    1 573 229    61.3   Mammoth_Character_BP_C:ThrottledTick (Fjordur)
  92.7   0.43%   25 680 965     3.6   Buff_Grappled_BogSpider_C:BuffTickServer (Gen2)
  90.0   0.42%   23 124 550     3.9   Buff_Grappled_BogSpider_C:BuffTickServer (Genesis)
  85.6   0.40%       2 925 29261.9   Buff_TekStrider_Harvester_C:passed-in foliage (Aberr)
  84.7   0.39%    6 049 987    14.0   FindEnemyTargetConditional_SRV_C:ReceiveTick (Ext)
  82.2   0.38%    1 322 935    62.1   MilkGlider_Character_BP_C:BPTimerServer (Fjordur)
  77.0   0.36%    2 270 446    33.9   BaseHumanAnimBP_C:BlueprintUpdateAnimation (Genesis)
  75.1   0.35%    2 437 396    30.8   BaseHumanAnimBP_C:BlueprintUpdateAnimation (Center)
  74.5   0.35%    0.258M  287.9   BogSpider_Character_BP_C:BPTimerServer (Genesis)
```

Cross-map summary by class: `LionfishLion` ~14%, `Buff_UnderwaterCyclone` 18.3%,
`BP_FloatingObject_*` (mod) ~10%, `Desmodus` ~8%, `IceJumper_AI`+`Scout` ~2.4%,
`MilkGlider` ~5%, `BaseHumanAnimBP` ~8%, `Mammoth` ~3%.

## Conclusions

1. **BP is not the bottleneck anywhere in the fleet.** 0.118% of wall, ~5% of frame budget.
   Even the worst servers (Genesis 18.3%, CrystalIsles 18.2% of GT CPU) leave the tick
   dominated by native work.
2. **The single highest-leverage BP item on the fleet is `Buff_UnderwaterCyclone`**
   (18.4% of all BP time, 486 us/call, 72.9% of Genesis load). Throttle or disable it first.
3. **`BP_FloatingObject_2` is a mod problem**, not an engine one - 9.4% of fleet BP time,
   74.7% of CrystalIsles. Contact the author or replace the asset.
4. **Extinction AI poll loops** (`IceJumper TryNextAbility`, `Scout FindAggressors`) are
   cheap per call but numerous; they are the best native-rewrite candidates.
5. **Chronic vanilla tax** (always-on across many maps, small individually):
   `Mammoth ThrottledTick`, `MilkGlider BPTimerServer`, `LionfishLion ReceiveTick`,
   `Desmodus ReceiveTick`, `Bee_Queen BPTimerServer`, `BaseHumanAnimBP`. Together ~25% of
   BP time and present on 8-11 maps each.
6. **ScorchedEarth_P / Ragnarok / CrystalIsles low tps is not a BP issue** - SE has 0.167
   ms/frame of BP at 5.9 tps. These need TickProf window/overlap work, not BP fixes.

## Suggested actions

1. Genesis: throttle `Buff_UnderwaterCyclone` (candidate kill list or rate config); it alone
   removes ~18% of fleet BP time and up to ~87% of a single Genesis interval.
2. CrystalIsles: drop / replace / C++-ize `BP_FloatingObject_2` (+ MedSlow / SmallFast variants);
   together they are ~10% of fleet BP time.
3. Extinction: lower poll rate or native-ize `IceJumper TryNextAbility` and
   `Scout FindAggressors`.
4. Build the throttle list around function families, not classes: `BuffTickServer`,
   `ReceiveTick`, `BPTimerServer`, `ThrottledTick` = 58% of BP time.
5. `StorageBox_TekShield CheckForPawnPushing` + `EggIncubator ThrottledTick` on Aberration:
   fewer instances or lower tick rate, combined 24.7% of that map's BP load.
6. For all servers: keep BP work in perspective - the real gains remain in saves
   (NVMe, AV exclusion, write caching) and native tick, per REPORT-BLUEPROF-DAY.md.
