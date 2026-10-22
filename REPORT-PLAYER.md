# REPORT-PLAYER.md -- player-bot slots (merged)

## Summary

A single static player roughly triples tick cost on TheIsland (60 -> 51 t/s, +12 ms/tick; slot 2026-10-19, target unreachable, gate never passed). Genesis (slot 19.10.2026 23:46 - 20.10.2026 12:55) does NOT hold 60 t/s with a player either: bare player costs only +0.0836 core (+1.5 ms/tick), but a dense base caps the server at ~20.9-21 t/s via a non-CPU limit (TaskGraph Stall waits, 19% syscall wait). Accumulation phases (ms/tick 36 -> 93, decay 1-5.5 min) exist even in an empty world and were not attributed. Bot join automation remains unsolved (session layer required; auto-connect uses the wrong path); manual join works.

## Player slot (The Island/older stand)

Date: 2026-10-19, bench 24 cores / 65 GB. Directive: `C:\Users\Admin\Desktop\doit4.txt`, phase S -> slot B0. Map: TheIsland (bench owner's choice, to test the "Genesis DLC missing" hypothesis - NOT confirmed: player joined without DLC, zero Join/Kick/DLC mentions in server log).

### Main answer

**One player in the world roughly triples the tick load, 60 t/s -> ~51 t/s.**

| Metric | no player | one player | Delta |
|---|---|---|---|
| t/s | 59-60 | 49-54 (avg 51) | **-15%** |
| CPU per tick | 5-6 ms | 16.8-18.4 ms (avg 17.7) | **x3.2** |
| frame | 16 ms | 19-20 ms | +20% |
| game-thread busy | 35-40% | 87-95% | x2.3 |

Target configuration (60 t/s at 5-9 ms/tick) **unreachable with a player**: the "world loaded" gate never passed once. Windows taken at 47-54 t/s / 16.8-20 ms/tick with explicit note that this is the player's consequence, not a gate.

### Measurements (player static: `moveActive: false`, 1304 m from spawn unchanged)

| Window | Duration | Start | t/s (plugin) | Game-thread CPU (external Python) | ms CPU/tick | Verdict |
|---|---|---|---|---|---|---|
| W1 | 200 s | 00:50:53 | 50 | 0.922 s/s | 18.44 | VALID |
| W2 | 240 s | 00:58:34 | 49 | 0.871 s/s | 17.78 | VALID |
| W3 | 240 s | 01:08:34 | 54 | 0.906 s/s | 16.78 | VALID |

Average: **51 t/s, 0.900 s/s, 17.7 ms/tick**. t/s from plugin frame counter, CPU from external Python; ms/tick = CPU / t/s (W2: 0.871 / 49 = 17.78). Plugin monitor held 18-20 ms/tick in the same minutes; discrepancy within 10% tolerance - **no discrepancy**.

Caveats: plugin `window summary:` columns `cpu=`/`ms/tick=` are unreliable - base CPU offset not subtracted (`cpu=1841s`, `ms/tick=153`); reliable: `t/s`, `frame_ms`, `save`, `VALID/CONTAMINATED`. First window initially read "t/s = 0": parser looked for obsolete label `perf window` instead of `window summary`; parser fixed (`slot_measure.py`).

Empty baseline (earlier, before the player): 59-60 t/s, 5-6 ms/tick.

### Profile (last step, 60 s, player in world)

30 557 samples, idle (Sleep/Wait) 25.4%.

Modules: ShooterGameServer.exe **56.6%**, PhysX3_x64.dll 5.4%, PhysX3Common_x64.dll 5.1%, MSVCR120.dll 2.7%, ntdll.dll 2.1%, TickProf.dll 0.8%; PhysX total **10.5%**.

Game subsystems: APrimalDinoCharacter 4.8%, APrimalCharacter 3.7%, FMallocBinned 2.9%, UCharacterMovementComponent 2.4%, Octree<UPrimitiveComponent> iterators 2.3+0.9+0.8%, FName 2.0%, TSet FoliageMeshInfo 1.6%, UObject/FUObjectArray/FWeakObjectPtr 1.4/0.7/0.6%, AActor/UWorld/AAIController 1.1/0.7/0.9%. Reading: the player is a full pipeline (character + movement + PhysX/octree collisions + allocation/object growth); dinos alone are noticeable but not dominant.

### Deviations from directive

1. TheIsland, not Genesis (DLC hypothesis test).
2. Manual join: bot auto-connect does not work (see below); player joined via UI; bot adopted the session fully (`state: Active`, pawn, coordinates, inventory 699 stacks).
3. Gate never passed (see above).
4. Window set reduced: no B0.2 (baseline taken earlier), no B0.4b (base travel), no B0.6 - 3 windows instead of the full set.
5. `arkstate` before/after not captured.
6. No redeploy at slot start - server had been raised on TheIsland at 00:29 for the DLC test.

### Auto-join blocker (verified and ruled out)

* Bot offsets correct in v361 (Ghidra on `v361_ShooterGame.exe`): `FURL` 96 B (Protocol 0x00, Host 0x10, Port 0x20, Map 0x28, Op 0x38, Portal 0x48, Valid 0x58 - layout identical), `FWorldContext::World = 0x260` (11 refs `[RSI+0x260]` in `TickWorldTravel`), `TravelURL = 0xB8`.
* Networking fine: same subnet, host pings; inbound UDP firewall rule cannot be created (no admin rights) but manual join works -> no actual blocking.
* DLC is not the issue (see deviations).
* Steam emulators do not solve it: Goldberg (installed, `[app::dlcs] unlock_all=1`) substitutes the Steam API client-side only; the server is genuine and requires a genuine Steam ticket. RUNE not installed (bypasses licensing).
* Address: A2S on QueryPort 27015 alive -> `P2PADDR = 90295185431854102`, `P2PPORT = 7777`. Travel URL from this SteamID rejected (`FURL::Parse -> valid=0`, `Browse -> Failure`); manual join on 7777 works -> address correct; specifically the automatic `SetClientTravel` path breaks.
* Outcome: manual join -> world -> bot sees and controls the session (`Active`). Join automation = separate task (see "RE session" in RE.md).

### Bot changes (git, all pushed; tree clean, no force-push)

`93f4b3c` bench address 192.168.8.218:7777 | `f1c8011` two-stage connect (QueryPort, then game port) | `8ee20b3` `autoConnect`+`autoSpawn` (documented autonomous loop) | `78f4144` direct game-port connect, rejection handler disabled | `35c9c9a` travel via SteamID64 | `7f9701b` return to QueryPort with long rejection handler | `79e7286` **REVERT** of `BotPlayer.json` to the pre-session state.

### Tool defects found

1. `TickProf.perf.selftest` hot loop: phase set with bare `g_st.store(...)` without timestamp reset, condition holds every frame -> 11 MB of log per minute. Not fixed in-slot (rule S2).
2. `ArgInt(packet, N)` means "the last token, or N", not "the N-th argument"; `TickProf.overlaptrim 7` produced a threshold of 2. Fixed (`ArgN`/`ArgLast`), verified on the bench.
3. `selftest` called RCON handlers with a `nullptr` packet -> NULL dereference, a server crash. Fixed: logic moved into `DoOverlapAll`/`DoOverlapTrim`/`DoOverlapsCensus`.
4. Window parser looked for the obsolete label `perf window` instead of `window summary` -> fixed in `slot_measure.py` (this is what lost the first two t/s readings).

### Attributions

Measured: the three valid windows above + the no-player baseline + a 60-s profile. Not measured: player vs Pawn contributions (inseparable in this profile), base travel, warm-up, harvesting, second point - not captured. Errors: (1) treated the firewall as a blocker (inbound traffic not blocked, manual join works); (2) changed the connection address repeatedly instead of testing with a control experiment on a DLC-free map; (3) mixed up the window-row label and declared the first window defective because of my parser, not the data. Unverified: automatic bot join (needs a separate attempt); server behavior with a player on Genesis; whether DLC unlocking works on a genuinely DLC map.

## Player slot (Genesis)

Slot DOIT-5 "Genesis with one player @ 60 t/s": 19.10.2026 23:46 - 20.10.2026 12:55 (ending: server self-death after the profile). Rules: doit5.txt (+sec. 0-6 of doit4.txt). Only actually captured numbers; "ms/tick" in the main table is the external Python only; plugin values listed separately as defective.

### Main answer

**Genesis holds 60 t/s with one player: NO in the observed configurations.** Empty world at the target of 60: 59 t/s in stable stretches (frame 16 ms, CPU-scheme ms/tick ~8-12), but the world periodically enters "accumulation phases" (ms/tick grows 36 -> 93, t/s falls to 10-17, busy 98-101% per the plugin, then decay for 1-5.5 min; one phase with a player once pushed t/s down to 2 at ms/tick 240) - so a continuous clean 240-s window of an empty world does not exist even without players; the best window G02v5 gave an average of 54.8 t/s. A static player near spawn (cheats gcm+leavemealone) establishes a regime of ~56.9 t/s; over the clean 86-s prefix the plugin ms/tick is 9.8 at busy 58%. **The cost of a bare player by the external CPU-rate: +0.0836 core (~ +1.5 ms/tick at 56.9 t/s)** - several times cheaper than on TheIsland (+12 ms/tick there). **On a large base the rate falls to 20.9 t/s (7-27)**: external ms/tick over the window is 20.8 at an external core occupancy of only 43.5%; **the base adds +0.1653 core of external CPU-rate (~ +7.9 ms/tick at the observed rate of 20.9)**. The observed limit on the base is best described by the "wall time of a tick": plugin ms/tick 42.4 and actual frame 49.2 ms give a ceiling of ~21 t/s - about half the tick time is not core CPU but waiting/synchronization (in the profile, syscall wait is 19%). Deficit against the 16.6 ms/tick budget: by pure CPU, empty+player+base ~ 3.1+1.5+2.8 = 7.3 ms/tick at 60 t/s - that would fit the budget, but in fact the base does not allow above ~21 t/s due to non-CPU constraints; the slot did not attribute the cause (candidates: locks/IO/streaming; profile captured). Forecast for a dedicated machine: no worse expected (shared LLC/memory could only worsen results); CPU headroom 16.6-7.3 ~ 9.3 ms/tick at 60 t/s - an upper bound, conditional on solving the non-CPU limit (disk/latency may change on dedicated; an improvement direction, no guarantees).

### Timeline

| Time | Fact |
|---|---|
| 19.10 23:29 | engine rewrote GameUserSettings.ini Server1; of the RCON keys only RCONPort survived (RCONEnabled=True and ServerAdminPassword lost - root of all RCON failures) |
| 19.10 23:46 - 20.10 07:15 | five boots with failed RCON; ini went UTF-16 during the owner's edits; Server1 restarted twice in vain while fixing the key insertion |
| 07:17 | Server1 up: Genesis (deploy of 19.10), pid 6260; core split sec.1.1 post-start via SetProcessAffinityMask: server 0x000FFF (cores 0-11), client 0xFFF000 (12-23) |
| 07:24:53 | RCON on 32330 responds (keys returned to the ini) |
| 07:26 | sec.2 applied: fixclamp 0 (the plugin returned its own ceiling of 100000 -> 120), fncache 1, iscache 1, cachename 1, nochart 1, overlaptrim 2 (4905 components, 43724 markers); arkstate BEFORE (17 .ark files; Genesis.ark 101.7 MB) |
| 07:38 | autosave No.1 3000 ms; then every 15 min (the detector sometimes misses: the 08:53 cycle was not captured) |
| 07:47:55 | TickProf.maxfps 60 - plugin log: "NetServerMaxTickRate 30 -> 60": the NetServerMaxTickRate=60 value from the ini did not apply at runtime (runtime was 30 t/s, frame 33 ms) |
| 07:48-08:56 | gate: 59-60 t/s in large stretches; accumulation phases at 07:49:07 -> 50:36, 07:56:38 -> 58:17, 08:11:46 -> 08:17:05 (5.3 min), 08:19:33 -> 20:39, 08:34:12 -> 53 (peak 93), 08:40-41, 08:49:2x, 08:56:31+; six attempts of window G0.2 captured, G02v5 accepted |
| 08:59 | connect command issued to the bot's client (by the owner's sanction); connectPending=true, session2 looking for sessions |
| 09:32-09:35 | first sign of player entry: the detector sees the 18th .ark file at 09:32:57; game-log SetPlayerPos isquzee1 at 09:33:02 - the bot's connect apparently got the client loading Genesis; after that the client died (no process at the 09:35:40 check; no dump taken) |
| 09:35:52 | client restarted by the owner (pid 7000); manual join |
| 09:49:40 | PLAYER-IN marker: listplayers -> "0. isquzee1, 76561199331214868"; the owner entered the cheats gcm and leavemealone |
| 09:53-11:23 | first eight saves with the player: 8375 / 15766 / 7437 / 3015 / 9156 / 7859 / 8563 / 3563 ms (empty ones were 2016-3016); from 11:53 back to 2016-3016 |
| 09:57-10:07 | window G0.4: attempt 09:57:25-10:01:31 rejected (accumulation phase 09:57:29-10:00:12, ~2.7 min, ms/tick up to 240, t/s down to 2); attempt G04b 10:03:22-10:07:28 rejected (phase 10:04:22) |
| 10:30-10:35 | G04c accepted (owner standing still at spawn) |
| 12:44-12:49 | G06 accepted (owner standing on a large base; the base regime steadily saturated on frame) |
| 12:52 | G0.9 census on the dense base: 142 levels, 106 534 actors (registered in tick 1485), 404 117 components (3374 ticking); ticksets: AllEnabled=1 264 433, FastPath=7 478 592 801, FastPathTickAfter=14 028 876 021, AllDisabled=12 929 146 766, NewlySpawned=16 103 559 480; overlapsizes: 270 538 components, of them with bGenerateOverlapEvents 6527, total overlaps 199 422 |
| 12:53:17 | arkhash BEFORE: Genesis.ark 101 794 264 bytes, sha256 86936d47... (and TheIsland/Fjordur - see worklog) |
| 12:53:23-12:54:23 | profile G0.10 (strictly the last measurement step): prof_512222984.bin, 3866 samples, tid 18080 (game thread), syscall wait 762/3866 = 19%; the server was alive when the result was written |
| 12:54:23-12:55:15 | server died on its own: last plugin record 12:54:23; arkstate AFTER returned None at 12:54:56; no process at 12:55:15-19, RCON refuses the connection. No crashstack/dump - a known "death after profile" pattern (per the rules, not counted as a crash) |
| 12:58 | report and worklog finished; slot parked |

### Main table (t/s avg = average over 240 mon-plugin rows, 1 row = 1 s; ext rate = CPU seconds of the game thread tid 18080 over 240 s; ext ms/tick = ext rate / t/s x 1000; ext busy = ext rate / 240 s)

| Window | Regime | Time | t/s avg (min-max) | busy plugin -> ext | ext rate CPU-s/240 s (core share) | ms/tick ext | ms/tick plugin | CONT (window dirt) |
|---|---|---|---|---|---|---|---|---|
| G0.2 empty @60 | world without players, sec.2 active, maxfps 60 | 08:45:38-08:49:44 (G02v5) | 54.8 (21-60) | 44% -> 18.6% (0.186 core) | 44.67 | 3.4 | 10.1 | 38 of 240 rows t/s<55 - mostly "sluggish pacing" (ms/tick 2-4, busy<45); an accumulation phase in the very tail (08:49:2x). No autosaves (No.5 at 08:38) |
| G0.4 player static @ spawn | cheats gcm+leavemealone | 10:30:56-10:35:01 (G04c) | 44.6 (25-59) | 54% -> 27.0% (0.270 core) | 64.73 | 6.0 | 12.3 | clean prefix 10:30:57-10:32:24 (86 s): t/s 56.9 (54-59), plugin ms/tick 9.8, busy 58%; accumulation phase 10:34:47-10:34:59 (12 s, ms/tick 20 -> 38); the rest "sluggish pacing" (t/s 32-47, busy 15-47%) without saturation. No autosaves (No.13 at 10:38) |
| G0.6 player on large base | base regime | 12:44:53-12:48:59 (G06) | 20.9 (7-27) | 84% -> 43.5% (0.435 core) | 104.41 | 20.8 | 42.4 | no accumulation phases - the regime itself saturated on frame (frame avg 49.2 ms). No autosaves (No.21 at 12:38) |

Breakdown (external CPU-rate deltas; independent of pacing): bare player (G0.4 minus G0.2) = +0.0836 core ~ +1.5 ms/tick at 56.9 t/s; dense base (G0.6 minus G0.4) = +0.1653 core ~ +7.9 ms/tick at 20.9 t/s; total world+player+base = 0.435 core vs empty 0.186 (2.34x).

Deficit vs 16.6 ms/tick budget: by pure CPU the empty world costs 3.1 ms/tick at 60 t/s (0.186x1000/60); the player adds ~+1.4, the base ~+2.8 - total ~7.3 ms/tick, fits. But the actual base ceiling (~21 t/s) is described by the tick's wall time ~ 42-49 ms (plugin ms/tick 42.4, frame 49.2) - about half of the tick is not core CPU; the slot did not attribute the cause. Two ways of counting: the CPU version on the base (20.8 ms/tick at 20.9 t/s) exceeds the budget by 4.2 ms/tick; the wall version (~42-49 ms/tick) exceeds by roughly 26-32 ms/tick. Holding 60 t/s with such a base unreachable under both interpretations.

### Comparison with TheIsland (REPORT-PLAYER, 19.10)

| Metric | TheIsland | Genesis (this slot) |
|---|---|---|
| Empty world @60 | 5-6 ms/tick (CPU scheme), steadily 59-60 | 8-12 ms/tick (CPU scheme), 59-60 in stretches; periodic phases (ms/tick 36-93) |
| Bare player | 17.7 ms/tick (16.8-18.4) over empty 5-6 -> +12 | external CPU-rate: +0.0836 core ~ +1.5 ms/tick at 56.9 t/s; caveats: God/Invis/InfiniteStats enabled, location is spawn, player is static |
| Dense base | not measured | +0.165 core ~ +7.9 ms/tick at 20.9 t/s; wall version ~42-49 ms/tick |
| Save freeze | 3000 ms without players | empty 2016-3016; first eight with the player 3563-15766 (peak 15766 at 10:08); after 11:53 normalized to 2016-3016 |

Portability of the player cost across maps in absolute ms/tick: NO. On Genesis a stationary player costs +45% over empty by external CPU-rate (0.186 -> 0.270 core); on TheIsland the empty/player ratio was triple in ms/tick. The comparison is not clean (cheats, location, stativeness; the measurement method changed between slots) - mandatory caveat. The dense base is the dominant term for N-player forecasts: one player on a large base ~ minus 39 t/s from the achievable 60; cross-replication (the quadratic term) is the subject of a future slot.

### Honesty attributes

Core split sec.1.1 applied post-start via SetProcessAffinityMask (not start /affinity - the client could not be restarted); server 0x000FFF, client 0xFFF000; LLC/memory shared - distortion possible only in the worsening direction. Manual join: the owner; first sign of join ~09:32-09:33 (18th .ark file, SetPlayerPos in the log); the client died after that; restarted 09:35:52; first listplayers observation 09:49:40; the stated ~10-minute budget was kept. NetServerMaxTickRate: ini=60, but runtime 60 only achieved by the command `TickProf.maxfps 60` after each boot; without it the server starts at 30 t/s - must be in future checklists. Cross-check: plugin busy/ms/tick are systematically inflated (44% -> 18.6%; 54% -> 27.0%; 84% -> 43.5%; 10.1 -> 3.4; 12.3 -> 6.0; 42.4 -> 20.8) - a previously documented defect; only the external Python is fit for judging numbers. Window dirt: no window perfectly clean (the cause is the accumulation phases, present even in an empty world); no autosave intrusions into the windows. Bot/client: connect launched by sanction; the join seemingly happened (save marker 09:33), then the client died; after the restart the bot API (8082/8083) did not come up; state Active not reached (not critical - the join was manual). Server2: process absent by 08:44 (not touched or stopped by me); does not affect measurements. Death after the profile: 12:54:23-12:55:15, without crashstack/dump; per the rules not a crash; artifacts preserved. arkstate AFTER not captured (server died; None at 12:54:56); arkstate BEFORE captured 07:26:53; hash verification limited to the profile window (12:53:17 and 12:55:01 identical - the world was not rewritten in this window). BattlEye never enabled (-NoBattlEye always). Server1 without NoDinos: full live Genesis world (106 534 actors per the census). Save detector missed cycles (08:53) - account when reading the numeric series.

### Parking, artifacts, not done, next

Server1 died on its own 12:54-12:55, no restarts, slot closed per G0.11. Client alive (pid 7000, started 09:35:52); the bot API did not come up. Server2: process absent since ~08:44 (not my stop). Artifacts in C:\Dev\_research\: threadcpu_g02*.txt, threadcpu_g04*.txt, threadcpu_g06.txt, plugin_tail_after_death_20261020.txt, serverlog_tail_after_death_20261020.txt; in the Server1 plugin directory: prof_512222984.{bin,csv,ret,wait,modules.txt}; worklog.md (append-only) complete. No code changes in this slot - nothing to push. G0.7/G0.8 and the @120 window - optional, not captured. Not done / deviations: no fully clean 240-s window (the strict letter of sec.4.1 is not satisfied by a single window); bot connection not brought to state Active (client died; API did not come up); arkstate AFTER not captured (death first); hash verification limited to the profile window; causes of death after profile not attributed (as in previous slots); cross-map player comparison not clean (cheats/location/stativeness, incomparable contexts) - stated with the caveat. Tasks for the next slot: (1) attribution of the accumulation phenomenon (candidate No.1: ms/tick growth 36 -> 93, decay; more frequent and stronger with a player; data already available - profile, syscall stacks, censuses); (2) attribution of the base's non-CPU limit (waits/IO/streaming) - explain the ceiling of ~21 t/s at 43.5% core occupancy; (3) resume the full gate of the empty world @60 on a fresh boot with mandatory TickProf.maxfps 60 and sec.2.
