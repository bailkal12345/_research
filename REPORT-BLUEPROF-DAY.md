# BlueprintProf prod analysis 23.10 morning (06:57-12:04, 13 servers x 5 h)

Source: `C:\Users\Admin\Desktop\bp_` (bp_history/bp_candidates/bp_cumulative downloads; 13 unique
proc ids at 06:57-06:58 start, 10-min intervals; one download name covers two maps when a proc
snapshot repeats - handled by dedup on (proc, ts, function)). Tool: `_research/bp_day.py`.

## Per-server BP load (BP-VM share of GameThread CPU, mean/p85 of interval sums)

| map | tps | ms/tick | BP cpu mean | p85 | key contributors |
|---|---|---|---|---|---|
| Genesis | 13.3 | 21.3 | 16.6% | 21.1% | Buff_UnderwaterCyclone 60% of ALL BP load |
| Extinction | 4.4 | 7.3 | 22.7% | 27.1% | IceJumper TryNextAbility, Scout FindAggressors |
| CrystalIsles | 6.9 | 11.0 | 20.1% | 23.2% | mod FloatingObject_2 74% of ALL BP load |
| Gen2 | 12.4 | 17.1 | 7.9% | 9.0% | Dynamic_PhysicsVolume_Hazard Tick, BrainSlug |
| Aquatica | 9.7 | 6.7 | 6.5% | 8.5% | WaterWyvern FallingTick, Aquatica_C ReceiveTick |
| Ragnarok | 7.0 | 9.6 | 7.0% | 10.5% | mod Spike_Trap Raise/LowerSpikes |
| TheCenter | 13.0 | 13.8 | 5.2% | 8.2% | |
| Fjordur | 8.8 | 10.0 | 5.5% | 6.7% | LionfishLion ReceiveTick, Mammoth ThrottledTick |
| LostIsland | 10.7 | 13.3 | 5.5% | 6.7% | LionfishLion, Dino_AIController_BP ReceiveBeginPlay |
| Valguero_P | 13.1 | 10.9 | 3.8% | 4.7% | |
| Aberration_P | 12.1 | 19.8 | 3.4% | 4.4% | 45 candidates/interval - the "noisiest" graph |
| TheIsland | 11.5 | 14.5 | 2.4% | 2.9% | |
| ScorchedEarth_P | 3.6 | 2.7 | 2.8% | 5.9% | BP ~ 0 cost BY THE LIMITER IS NOT THE BP VM |

## Headline costs (self time, the fleet)

1. **Buff_UnderwaterCyclone_C:BuffTickServer (Genesis)** - 594 s self total, 1.37M calls,
   75-87% of an interval's whole BP load for the entire morning (~90-100 calls/s steady).
   The single biggest BP-VM item seen on prod. Recommended: throttle/disable the cyclone
   buff tick (whales event?) or move to C++.
2. **BP_FloatingObject_2_C:Transform__UpdateFunc (CrystalIsles mod)** - 191 s, 15.4M calls
   (~380-390/s), 71-75% of every interval. A mod asset ticking per object per frame.
3. **Dino_AIController_BP_C:ReceiveBeginPlay** - 86 s over 11 servers; 300-500 us per call;
   76% spikes only in spawn bursts (13K calls/600 s = a respawn wave) - correlates with
   spawn/respawn events, not an overhead source by itself.
4. Chronic 60/60-interval candidates (permanent, small but always on):
   Mammoth ThrottledTick, EggIncubator ThrottledTick (Genesis2), TekStrider BPTimerServer,
   TekArmor Gloves/Shirt/Boots BuffTickServer, BrainSlug wantsToRun (14667626 calls/2 srv),
   MilkGlider BPTimerServer (10 srv), LionfishLion ReceiveTick (7 srv), Bee Queen BPTimerServer,
   Trike CheckRivalryTick, IceJumper TickStaminaRegen.
   This chronically on group = the fabricated "Blueprint VM tax" all servers pay.
5. **StorageBox_TekShield_C:CheckForPawnPushing** - 27 s, up to 8.6% share/interval on
   Extinction (3.5-8.5K calls/interval); many box instances each polling per passive tick.
6. GameMode/TestGameMode_C:ReceiveTick - on 11 servers (up to 42.8% spike), the base game
   mode itself is a chronic BP tick.

## Observations

- BP TOTAL per 600 s interval: 0.3-29 s (Genesis) = 0.05-4.9% of wall; as % of GameThread
  CPU: Genesis/CrystalIsles/Extinction > 16%; rest <= 8%.
- tps trend by hour (fleet mean): 9.3 -> 9.5 -> 9.8 -> 10.2 -> 9.7 (07-11h), players <= 2.3.
- **The BP VM is NOT the tps limiter on a dozen servers**: ScorchedEarth runs 3.6 tps
  with ~0% BP load; Ragnarok 7.0 / CrystalIsles 6.9 have load concentrated in screening
  elements (CrystalIsles IS mod). Those three need TickProf window/mon followups
  (native engine phases), not BP fixes.
- Aberration_P stands out with 45.2 candidates/interval while its TOTAL share is low -
  class-level BP churn (many small graphs), best handled by graph-level pruning, not a
  hotspot hunt.

## Recommended actions

1. Genesis: throttle/limit Buff_UnderwaterCyclone (candidate kill list or rate config) -
   it pays ~60% of the stacked Genesis+TheCenter file total (75%+ on Genesis proper) and up to
   87% of a single interval; ~100 ms/s CPU at peaks.
2. CrystalIsles: contact mod author / drop or C++-ize FloatingObject_2; 231K calls/interval
   of a mod asset is the entire CrystalIsles BP cost.
3. IceJumper TryNextAbility + Scout FindAggressors (Extinction): classic AI poll loops in BP;
   candidates for C++/native rewrites or lower rates.
4. CheckForPawnPushing on TekShield storage: fewer server box instances or a lower
   tick rate for that graph.
5. For the servers with low tps and low BP load - move to TickProf (window/overlaps/ticksets).
