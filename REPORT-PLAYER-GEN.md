# REPORT-PLAYER-GEN.md — final report of slot DOIT-5 «Genesis with one player @ 60 t/s»

Slot: 19.10.2026 23:46 — 20.10.2026 12:55 (ending: server self-death after the profile).
Rules: doit5.txt (+§0–§6 of doit4.txt). Report rule: only actually captured numbers; "ms/tick"
in the table is the external Python only; plugin values are listed separately as defective (see §6.4).

---

## 1. MAIN ANSWER (§4.3, one paragraph)

**Does Genesis hold 60 t/s with one player: NO in the observed configurations.** An empty world
at the target of 60 holds 59 t/s in stable stretches (frame 16 ms, ms/tick by the CPU scheme
~8–12), but the world periodically enters "accumulation phases" (ms/tick grows 36→93, t/s falls
to 10–17, busy 98–101% per the plugin, then decay for 1–5.5 minutes; with a player one phase
once pushed t/s down to 2 at ms/tick 240), so a continuous clean 240-s window of an empty world
does not exist even without players; the best window G02v5 gave an average of 54.8 t/s. A static
player near spawn (cheats gcm+leavemealone) establishes a regime of ~56.9 t/s; over the clean
86-s prefix the plugin ms/tick is 9.8 at busy 58%. **The cost of a bare player by the external
CPU-rate: +0.0836 core (≈ +1.5 ms/tick at 56.9 t/s)** — several times cheaper than on TheIsland
(+12 ms/tick there). **On a large base the rate falls to 20.9 t/s (7–27)**: the external ms/tick
over the window is 20.8 at an external core occupancy of only 43.5%; **the base adds +0.1653
core of external CPU-rate (≈ +7.9 ms/tick at the observed rate of 20.9)**. The observed limit on
the base is best described by the "wall time of a tick": the plugin ms/tick 42.4 and the actual
frame 49.2 ms give a ceiling of ~21 t/s, i.e. about half the tick time is not core CPU but
waiting/synchronization (in the profile, syscall wait is 19%). Deficit against the 16.6 ms/tick
budget: by pure CPU, empty+player+base ≈ 3.1+1.5+2.8 = 7.3 ms/tick at 60 t/s — that would fit
the budget, but in fact the base does not let you go above ~21 t/s due to non-CPU constraints;
the slot did not attribute the cause of the discrepancy (candidates — locks/IO/streaming;
profile captured). Forecast for a dedicated machine: on a dedicated box we expect no worse;
CPU headroom 16.6−7.3 ≈ 9.3 ms/tick at 60 t/s — an upper bound, conditional on solving the
non-CPU limit.

## 2. Slot timeline

| Time | Fact |
|---|---|
| 19.10 23:29 | the engine rewrote GameUserSettings.ini Server1; of the RCON keys only RCONPort survived — RCONEnabled=True and ServerAdminPassword lost (root of all RCON failures) |
| 19.10 23:46 – 20.10 07:15 | five boots with failed RCON; ini went to UTF-16 during the owner's edits; I restarted Server1 twice in vain while fixing the key insertion (recorded honestly) |
| 07:17 | Server1 up: Genesis (deploy of 19.10), pid 6260; core split §1.1 post-start via SetProcessAffinityMask: server 0x000FFF (cores 0–11), client 0xFFF000 (12–23) |
| 07:24:53 | RCON on 32330 responds (keys returned to the ini) |
| 07:26 | §2 applied: fixclamp 0 (the plugin returned its own ceiling of 100000→120), fncache 1, iscache 1, cachename 1, nochart 1, overlaptrim 2 (4905 components, 43724 markers); arkstate BEFORE (17 .ark files; Genesis.ark 101.7 MB) |
| 07:38 | autosave №1 3000 ms; then every 15 min (the detector sometimes misses: the 08:53 cycle was not captured) |
| 07:47:55 | TickProf.maxfps 60 — the plugin log says «NetServerMaxTickRate 30 → 60»: the NetServerMaxTickRate=60 value from the ini did not apply at runtime (runtime was 30 t/s, frame 33 ms) |
| 07:48–08:56 | gate: 59–60 t/s in large stretches; the accumulation-phase phenomenon observed: 07:49:07→50:36, 07:56:38→58:17, 08:11:46→08:17:05 (5.3 min), 08:19:33→20:39, 08:34:12→53 (peak 93), 08:40-41, 08:49:2x, 08:56:31+; six attempts of window G0.2 captured, G02v5 accepted |
| 08:59 | connect command issued to the bot's client (by the owner's sanction); connectPending=true, session2 is looking for sessions |
| 09:32–09:35 | first sign of player entry: the detector sees the 18th .ark file at 09:32:57; game-log SetPlayerPos isquzee1 at 09:33:02 — the bot's connect apparently got the client to loading Genesis; after that the client died (process absent per the 09:35:40 check; no dump taken) |
| 09:35:52 | client restarted by the owner (pid 7000); manual join |
| 09:49:40 | PLAYER-IN marker: listplayers → «0. isquzee1, 76561199331214868»; the owner entered the cheats gcm and leavemealone |
| 09:53–11:23 | first eight saves with the player: 8375 / 15766 / 7437 / 3015 / 9156 / 7859 / 8563 / 3563 ms (empty ones were 2016–3016); from 11:53 back to 2016–3016 |
| 09:57–10:07 | window G0.4: attempt 09:57:25–10:01:31 rejected (accumulation phase 09:57:29–10:00:12, ~2.7 min, ms/tick up to 240, t/s down to 2); attempt G04b 10:03:22–10:07:28 rejected (phase 10:04:22) |
| 10:30–10:35 | window G04c accepted (owner standing still at spawn) |
| 12:44–12:49 | window G06 accepted (owner standing on a large base; the base regime is steadily saturated on frame) |
| 12:52 | G0.9 census on the dense base: 142 levels, 106 534 actors (registered in tick 1485), 404 117 components (3374 ticking); ticksets: AllEnabled=1 264 433, FastPath=7 478 592 801, FastPathTickAfter=14 028 876 021, AllDisabled=12 929 146 766, NewlySpawned=16 103 559 480; overlapsizes: 270 538 components, of them with bGenerateOverlapEvents 6527, total overlaps 199 422 |
| 12:53:17 | arkhash BEFORE: Genesis.ark 101 794 264 bytes, sha256 86936d47… (and TheIsland/Fjordur — see worklog) |
| 12:53:23–12:54:23 | profile G0.10 (strictly the last measurement step): prof_512222984.bin, 3866 samples, tid 18080 (game thread), syscall wait 762/3866 = 19%; the server was alive at the time the result was written |
| 12:54:23–12:55:15 | the server died on its own: last plugin record 12:54:23; at 12:54:56 arkstate AFTER returned None; at 12:55:15–19 there is no process, RCON refuses the connection. No crashstack/dump — a known "death after profile" pattern (per the rules, not to be counted as a crash) |
| 12:58 | report and worklog finished; slot parked |

## 3. Main table (§4.2)

Notation: t/s avg — average over 240 rows of the mon-plugin (one row = 1 s); ext rate — CPU
seconds of the game thread (tid 18080) over 240 s (threadcpu, external Python); ext ms/tick =
ext rate / t/s-avg × 1000; ext busy = ext rate / 240 s × 100%. Plugin values are a separate
column for comparison. CONT — documented "dirt" of the window.

| Window | Regime | Window time | t/s avg (min–max) | busy plugin → ext | ext rate, CPU-s/240 s (core share) | ms/tick ext | ms/tick plugin | CONT — window dirt |
|---|---|---|---|---|---|---|---|---|
| G0.2 empty @60 | world without players, §2 active, maxfps 60 | 08:45:38–08:49:44 (G02v5) | 54.8 (21–60) | 44% → 18.6% (0.186 core) | 44.67 | 3.4 | 10.1 | 38 of 240 rows t/s<55 — mostly "sluggish pacing" (ms/tick 2–4, busy<45); an accumulation phase started in the very tail of the window (08:49:2x). No autosaves (№5 at 08:38) |
| G0.4 player off base (spawn), static | cheats gcm+leavemealone | 10:30:56–10:35:01 (G04c) | 44.6 (25–59) | 54% → 27.0% (0.270 core) | 64.73 | 6.0 | 12.3 | clean prefix 10:30:57–10:32:24 (86 s): t/s 56.9 (54–59), plugin ms/tick 9.8, busy 58%; accumulation phase 10:34:47–10:34:59 (12 s, ms/tick 20→38); the rest — "sluggish pacing" (t/s 32–47, busy 15–47%) without saturation. No autosaves (№13 at 10:38) |
| G0.6 player on a large base, static | base regime | 12:44:53–12:48:59 (G06) | 20.9 (7–27) | 84% → 43.5% (0.435 core) | 104.41 | 20.8 | 42.4 | no accumulation phases: the regime itself is saturated on frame (frame avg 49.2 ms). No autosaves (№21 at 12:38) |

Breakdown per §4.3 (external CPU-rate deltas; independent of pacing):
- bare player (G0.4 minus G0.2) = +0.0836 core ≈ +1.5 ms/tick at 56.9 t/s;
- dense base (G0.6 minus G0.4) = +0.1653 core ≈ +7.9 ms/tick at 20.9 t/s;
- total world+player+base = 0.435 core versus empty 0.186 (2.34 times more).

Interpretation of the "deficit against 16.6": by pure CPU the empty world costs 3.1 ms/tick at
60 t/s (0.186×1000/60); the player adds ~+1.4, the base ~+2.8 — total ≈ 7.3 ms/tick against a
budget of 16.6, i.e. by pure CPU everything fits. But the actual ceiling on the base (~21 t/s)
is described by the tick's wall time ≈ 42–49 ms (see plugin ms/tick 42.4 and frame 49.2), i.e.
about half of the tick is not core CPU; the slot did not attribute the cause of this limit.
Deficit in the two ways of counting: the CPU version on the base at 20.8 ms/tick (at the rate
of 20.9) exceeds the budget by 4.2 ms/tick; the wall version ~42–49 ms/tick exceeds the budget
by roughly 26–32 ms/tick. Outcome: holding 60 t/s with such a base is unreachable under both
interpretations.

## 4. Comparison with TheIsland (§4.4)

| Metric | TheIsland (REPORT-PLAYER, 19.10) | Genesis (this slot) |
|---|---|---|
| Empty world @60 | 5–6 ms/tick (CPU scheme), steadily 59–60 | 8–12 ms/tick (CPU scheme), 59–60 in stretches; periodic phases (ms/tick 36–93) |
| Bare player | 17.7 ms/tick (16.8–18.4) over empty 5–6 → +12 | external CPU-rate: +0.0836 core ≈ +1.5 ms/tick at 56.9 t/s; caveats: God/Invis/InfiniteStats enabled, location is spawn, player is static |
| Dense base | not measured | +0.165 core ≈ +7.9 ms/tick at 20.9 t/s; wall version ~42–49 ms/tick |
| Save freeze | 3000 ms without players | empty 2016–3016; the first eight with the player 3563–15766 (peak 15766 at 10:08); after 11:53 normalized to 2016–3016 |

Portability of the player cost across maps in absolute ms/tick: NO. On Genesis a stationary
player costs +45% over empty by external CPU-rate (0.186 → 0.270 core); on TheIsland the
empty/player ratio was triple in ms/tick. The comparison is not clean (factor in cheats,
location, stativeness; the measurement method changed between slots) — mandatory caveat.
The dense base is the dominant term for N-player forecasts: one player on a large base
≈ minus 39 t/s from the achievable 60; cross-replication (the quadratic term) is the subject
of a future slot.

## 5. Forecast for a dedicated machine (§4.5)

On a dedicated box we expect no worse than the current figures: shared LLC/memory on this
machine could only worsen results. By pure CPU an empty world with a player fits the budget
(headroom ~9–10 ms/tick at 60 t/s); on the base the observed ceiling of 21 t/s is limited by a
non-CPU factor (waits; syscall share 19% in the profile), which may change on dedicated
(disk, latency) — a possible improvement direction, without guarantees.

## 6. Honesty attributes

6.1 Core split §1.1: applied post-start via SetProcessAffinityMask (not start /affinity —
the client could not be restarted); server 0x000FFF (cores 0–11), client 0xFFF000 (12–23);
LLC/memory shared — distortion is possible only in the worsening direction.
6.2 Manual join: the owner; first sign of join ~09:32–09:33 (18th .ark file, SetPlayerPos in
the log); the client died after that; restarted by the owner 09:35:52; join completed manually;
my first listplayers observations — 09:49:40. The stated ~10-minute budget was kept.
6.3 NetServerMaxTickRate: ini=60, but runtime 60 is only achieved by the command
TickProf.maxfps 60 after each boot; without it the server starts at 30 t/s. Must be
included in future checklists.
6.4 Cross-check of numbers: plugin busy/ms/tick are systematically inflated (44%→18.6%;
54%→27.0%; 84%→43.5%; 10.1→3.4; 12.3→6.0; 42.4→20.8) — a previously documented defect; only
the external Python is fit for judging numbers.
6.5 Window dirt: no window is perfectly clean (the cause is the world's accumulation phases,
present even in an empty world); windows are given with a layer-by-layer breakdown.
No autosave intrusions into the windows.
6.6 Bot and client: connect was launched by sanction; the join seemingly happened
(save marker 09:33), then the client died; after the restart the bot API (8082/8083) did not
come up; state Active not reached (not critical for §4.1 — the join was manual).
6.7 Server2: the process was absent by 08:44 (I did not touch or stop it); it does not affect
the measurements.
6.8 Death after the profile: 12:54:23–12:55:15, without crashstack/dump; per the rules not a
crash; artifacts preserved.
6.9 arkstate AFTER not captured (the server died; at 12:54:56 the answer was None); arkstate
BEFORE captured 07:26:53. Hash verification is limited to the profile window (12:53:17 and
12:55:01 identical — the world was not rewritten in this window).
6.10 BattlEye: never enabled (−NoBattlEye always).
6.11 Server1 without NoDinos: full live Genesis world (106 534 actors per the census).
6.12 Save detector: missed cycles noted (08:53); take into account when reading the numeric series.

## 7. Parking and artifacts

- Server1 died on its own 12:54–12:55; no restarts; slot closed per G0.11.
- The client is alive (pid 7000, started 09:35:52); the bot API did not come up.
- Server2: process absent since ~08:44 (not my stop).
- Artifacts in C:\Dev\_research\: threadcpu_g02*.txt, threadcpu_g04*.txt, threadcpu_g06.txt,
  plugin_tail_after_death_20261020.txt, serverlog_tail_after_death_20261020.txt; in the Server1
  plugin directory — prof_512222984.{bin,csv,ret,wait,modules.txt}; worklog.md (append-only) is complete.
- Push: I did not change code in this slot — nothing to push.
- G0.7/G0.8 and the @120 window — optional, not captured.

## 8. Not done / deviations

1. There is no fully clean 240-s window — the strict letter of §4.1 is not satisfied by a
   single window; the main request for the next slot is attribution of the accumulation phenomenon.
2. Bot connection not brought to state Active (the client died; after the restart the API did
   not come up).
3. arkstate AFTER not captured (death happened first); hash verification is limited to the
   profile window.
4. Causes of death after profile (as in previous slots) not attributed.
5. Cross-map player comparison is not clean (cheats/location/stativeness; incomparable
   contexts), stated with the caveat.

## 9. Tasks for the next slot

1. Attribution of the accumulation phenomenon (candidate №1): ms/tick growth 36→93, decay;
   more frequent and stronger with a player; the data is already available (profile, syscall
   stacks, censuses) — the main goal of the next slot.
2. Attribution of the base's non-CPU limit (waits/IO/streaming) — goal: explain the ceiling of
   ~21 t/s at 43.5% core occupancy.
3. Resume the full gate of the empty world @60 on a fresh boot with mandatory
   TickProf.maxfps 60 and §2.
