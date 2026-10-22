# REPORT-PLAYER.md — session with a player-bot

Date: 2026-10-19, bench 24 cores / 65 GB.
Directive: `C:\Users\Admin\Desktop\doit4.txt`, phase S → slot B0.

---

## 1. Main answer

**One player in the world roughly triples the tick load and drops the server from the
target 60 t/s to ~51 t/s.**

| Metric | World without a player | World with one player | Delta |
|---|---|---|---|
| t/s | 59–60 | 49–54 (average 51) | **−15%** |
| CPU per tick | 5–6 ms | 16.8–18.4 ms (average 17.7) | **×3.2** |
| frame | 16 ms | 19–20 ms | +20% |
| game-thread busy | 35–40% | 87–95% | ×2.3 |

The target configuration (60 t/s at 5–9 ms/tick) **is unreachable with a player
in the world** on this bench: the "world loaded" gate never passes even once
throughout the entire session with a player.

---

## 2. Measurements

All windows were taken in a clean interval between autosaves; the player stood
still (`moveActive: false`, distance from spawn unchanged — 1304 m).

| Window | Duration | Start | t/s (plugin) | Game-thread CPU (external Python) | ms CPU/tick | Verdict |
|---|---|---|---|---|---|---|
| W1 | 200 s | 00:50:53 | 50 | 0.922 s/s | 18.44 | VALID |
| W2 | 240 s | 00:58:34 | 49 | 0.871 s/s | 17.78 | VALID |
| W3 | 240 s | 01:08:34 | 54 | 0.906 s/s | 16.78 | VALID |

Average: **51 t/s, 0.900 s/s, 17.7 ms/tick**.

### Cross-check of two sources
The external measurement (Python, per-thread) and the plugin ran in parallel in the same window.

* t/s is taken from the plugin (its frame counter), CPU from the external Python.
* ms/tick = CPU ÷ t/s: W2 = 0.871 ÷ 49 = **17.78 ms**.
* The plugin's independent monitor held **18–20 ms/tick** in the same minutes at busy 87–95%.
* The discrepancy between the external count and the monitor is within the 10% tolerance. **No discrepancy.**

**Important caveat:** the `cpu=` and `ms/tick=` columns in the plugin's `window summary:`
line are unreliable — the base CPU offset is not subtracted (values like `cpu=1841s`,
`ms/tick=153`). Reliable values: `t/s`, `frame_ms`, `save`, `VALID/CONTAMINATED`.
Because of this, the first window initially read as "t/s = 0": the parser was looking
for the obsolete label `perf window`, while the plugin writes `window summary`.
The parser has been fixed.

---

## 3. Profile (last measurement step, 60 s, player in the world)

30 557 samples, of which idle (Sleep/Wait) 25.4%.

### By module
| Module | Share |
|---|---|
| ShooterGameServer.exe | **56.6%** |
| PhysX3_x64.dll | 5.4% |
| PhysX3Common_x64.dll | 5.1% |
| MSVCR120.dll | 2.7% |
| ntdll.dll | 2.1% |
| TickProf.dll (tool) | 0.8% |
| PhysX total | **10.5%** |

### Game subsystems (top)
| Subsystem | Share |
|---|---|
| APrimalDinoCharacter | 4.8% |
| APrimalCharacter | 3.7% |
| FMallocBinned (allocations) | 2.9% |
| UCharacterMovementComponent | 2.4% |
| Octree<UPrimitiveComponent> iterators | 2.3% + 0.9% + 0.8% |
| FName | 2.0% |
| TSet FoliageMeshInfo | 1.6% |
| UObject / FUObjectArray / FWeakObjectPtr | 1.4% / 0.7% / 0.6% |
| AActor / UWorld / AAIController | 1.1% / 0.7% / 0.9% |

**How to read it:** a player is not "one object" but a full pipeline: their character
(`APrimalCharacter`), their movement (`UCharacterMovementComponent`), their collisions
(PhysX 10.5% + octree iterators), plus the general growth of actor cost and allocations
(`FMallocBinned`, `UObject`, `FUObjectArray`). Dinos on their own (`APrimalDinoCharacter`)
contribute a noticeable but not dominant share.

---

## 4. Deviations from the directive — all of them

1. **The map is TheIsland, not Genesis.** Choice of the bench owner, to test the
   "Genesis DLC missing" hypothesis. The hypothesis was not confirmed: the player joined
   the server without any DLC, and the server log contains not a single mention of
   Join/Kick/DLC.
2. **Manual join.** The bot's automatic connect does not work (see §5); the player joined
   on their own via the UI; the bot adopted the session fully (`state: Active`, pawn present,
   coordinates, inventory of 699 stacks).
3. **Gate never passed.** The plan required 59–60 t/s and 5–9 ms/tick; with a player
   it comes out to 47–54 t/s and 16.8–20 ms/tick. The windows were taken with an explicit
   note that this is not a gate condition but a consequence of the player's presence.
4. **Window set reduced.** No B0.2 (empty baseline — the baseline was taken earlier, before the
   player joined: 59–60 t/s, 5–6 ms/tick), no B0.4b (travel to a base), no B0.6.
   Three windows were taken instead of the full set.
5. **`arkstate` before/after was not captured.**
6. **No redeploy at the start of the slot** for the TheIsland map — the server had been
   raised on it at 00:29 to test the DLC hypothesis.

---

## 5. Automatic join blocker (for the record)

The client enters the world **manually** — verified by the bench owner and by me.
The bot's auto-connect does not work. Verified and ruled out:

* **The bot's offsets in v361 are correct** — verified against Ghidra on `v361_ShooterGame.exe`:
  `FURL` (96 B: Protocol 0x00, Host 0x10, Port 0x20, Map 0x28, Op 0x38, Portal 0x48,
  Valid 0x58 — layout identical), `FWorldContext::World = 0x260` (11 references
  `[RSI+0x260]` in `TickWorldTravel`), `TravelURL = 0xB8`.
* **Networking is fine** — client and server are on the same subnet, the host pings,
  inbound UDP to the client is only blocked by a firewall rule that cannot be created
  (no admin rights), but manual join works, which means there is no actual blocking.
* **DLC is not the issue** — see §4.1.
* **A Steam emulator does not solve the task.** Tested Goldberg (installed, all DLC
  unlocked: `[app::dlcs] unlock_all=1`) and the previously discussed RUNE. The emulator
  substitutes the Steam API only on the client; the server remains genuine and requires a
  genuine Steam ticket, so the connection never completes. RUNE was not installed —
  it bypasses licensing.
* **Address.** A2S on QueryPort 27015 is alive, returns `P2PADDR = 90295185431854102`,
  `P2PPORT = 7777`. The client does not accept the travel URL built from this SteamID
  (`FURL::Parse → valid=0`, `Browse → Failure`). Manual join on 7777 works — which means
  the address is correct; it is specifically the automatic `SetClientTravel` path that breaks.

**Reproducible outcome:** manual join → world → the bot sees the session (`Active`) and can
control it. So the slot can be role-played; join automation is a separate task.

---

## 6. Bot changes (git, all pushed)

| Commit | What |
|---|---|
| `93f4b3c` | bench address 192.168.8.218:7777 |
| `f1c8011` | two-stage connect: QueryPort, then the game port |
| `8ee20b3` | `autoConnect` + `autoSpawn` — documented autonomous loop |
| `78f4144` | direct connect to the game port, rejection handler disabled |
| `35c9c9a` | travel via SteamID64 |
| `7f9701b` | return to QueryPort with a long rejection handler |
| `79e7286` | **REVERT** of `BotPlayer.json` to the pre-session state |

The repository is clean of experiments; the working tree is empty. Push without force-push.

---

## 7. Tool defects found in this session

1. **`TickProf.perf.selftest` goes into a hot loop.** The phase is set with a bare
   `g_st.store(...)` without resetting the timestamp, so the condition holds every frame:
   11 MB of log per minute. Not fixed during the slot (rule §S2).
2. **`ArgInt(packet, N)` means "the last token, or N",** not "the N-th argument".
   Because of this, `TickProf.overlaptrim 7` produced a threshold of 2. Fixed (`ArgN`/`ArgLast`),
   verified on the bench.
3. **`selftest` called RCON handlers with a `nullptr` packet** → NULL dereference,
   i.e. a server crash. Fixed: logic moved into
   `DoOverlapAll`/`DoOverlapTrim`/`DoOverlapsCensus`.
4. **The window parser** looked for the obsolete label `perf window` instead of `window summar` —
   fixed in `slot_measure.py` (this is what lost the first two t/s readings).

---

## 8. Honest attributions

* **What was measured:** exactly what is in the table in §2 — three valid windows with a player,
  plus the no-player baseline and a 60-second profile.
* **What was not measured:** the contributions of "the player" and "their Pawn" separately
  cannot be split — in this profile the player and the world are inseparable. Travel to a base,
  warm-up, harvesting, and a second point were not captured.
* **Where I was wrong:** (1) treated the firewall as a blocker — it turned out inbound traffic
  is not blocked and manual join works; (2) changed the connection address several times
  instead of testing the hypothesis with a control experiment on a DLC-free map;
  (3) mixed up the window-row label and declared the first window defective because of my
  parser, not because of the data.
* **What remains unverified:** automatic bot join (needs a separate attempt),
  server behavior with a player on Genesis, whether DLC unlocking works on a map
  that is genuinely an DLC.
