# ARK: Survival Evolved (v358) — network analysis of the Server2 bench

Date: 2026-10-19. Bench: `C:\asmdata\Servers\Server2` (ARK Version 358.24),
game port 7778, Steam query 27016, RCON 32331. All experiments only on
this bench and on loopback.

---

## 0. What was reused (nothing written from scratch)

| Asset | Path | What it provided |
|---|---|---|
| `ServerMonitor` (plugin, already built) | `C:\Dev\ark-bot-research\ServerMonitor` | the pattern for measuring TPS/tickMs/memory + a TCP-JSON interface on 127.0.0.1 |
| `SrvDiag` (plugin) | `C:\Dev\ARK-Server-Plugins\SrvDiag` | a ready ArkApi hook template (`PreLogin`, `NotifyControlMessage`, `ExtraPreLoginChecksBeforeWelcomePlayer`) |
| `TickProf` (plugin) | `C:\Dev\ARK-Server-Plugins\TickProf` | a vcxproj template for the **server** ARK-Server-API (`x64\Release\ArkApi.lib`) |
| `rcon.py`, `a2s.py`, `a2s2.py` | `C:\Dev\_research` | Source-RCON client and A2S/Steam query clients |
| `pdbsym.cpp` + `v361.tsv/sqlite` | `C:\Dev\_research` | a PDB symbol index (710k functions) |
| `game_aquatica.c` + `dump_index.json` | `C:\Dev\ARK_SE_code_dump` | a v361 decompilation (architecture, not measurements) |
| Ghidra-mcp, program `v358_ShooterGameServer.exe` | `C:\asmdata\ghidra\ARK_SE` | v358 analysis: RCON authorization, strings, absence of A2S |

New artifacts of this work:

* `C:\Dev\ARK-Server-Plugins\NetGuard\` — a server plugin (metrics + defense), built and
  **installed** on the bench.
* `C:\Dev\_research\security\` — the lab scripts (see §5).

---

## 1. The structure of the ARK v358 network stack (per the UE4.5 sources + Ghidra)

### 1.1 Game port (7778)

Datagram processing chain (UE 4.5,
`Engine/Source/Runtime/Online/OnlineSubsystemUtils/Private/IpNetDriver.cpp:255-277`):

```cpp
else {                                   // packet received
    if (!Connection) {                   // source address unknown to the server
        const bool bAcceptingConnection =
            Notify->NotifyAcceptingConnection() == EAcceptConnection::Accept;
        if (bAcceptingConnection) {
            Connection = ConstructObject<UIpConnection>(NetConnectionClass);   // NEW UObject
            Connection->InitRemoteConnection(this, Socket, FURL(), *FromAddr, USOCK_Open);
            Notify->NotifyAcceptedConnection(Connection);
            AddClientConnection(Connection);
        }
    }
    if (Connection) Connection->ReceivedRawPacket(Data, BytesRead);
}
```

* The source address is compared **together with the port**
  (`*TestConnection->RemoteAddr == *FromAddr`), so each new source port = a new connection.
* `UWorld::NotifyAcceptingConnection()` (`World.cpp:3351-3372`) **always returns Accept**
  if the server is up and not travelling between maps. There is no player-count check.
* A half-open connection lives until the timeout: on the bench
  `[/Script/OnlineSubsystemUtils.IpNetDriver] InitialConnectTimeout=300.0, ConnectionTimeout=300.0`.

**BUT.** In ARK the game port is not served by the raw UE4 socket but by
GameNetworkingSockets (Steam). In the bench log: `SteamSocketsOpenSource: gethostname failed ()`;
the v358 binary contains `USteamNetDriver`, `FSocketSubsystemSteamOpenSource`.
`USteamNetDriver` does not override `TickDispatch` — it inherits
`UIpNetDriver::TickDispatch`, but its socket is a Steam one, and GNS drops
invalid datagrams **before** UE4 ever sees them.

**Measured:** 24 000 arbitrary datagrams to 7778 → `connectionAttempts = 0`,
`packetsReceived = 0` (the NetGuard plugin counters). I.e. junk never reaches UE4.

### 1.2 Steam query port (27016)

* The `v358_ShooterGameServer.exe` has **no** strings `A2S`, `Source Engine Query`,
  `GETCHALLENGE` — there is no A2S protocol in the game binary (verified with Ghidra
  `search_strings` over the whole image).
* The strings `P2PADDR`, `CUSTOMSERVERNAME_s`, `OWNINGID`, `Networking_i` in the binary
  belong to the **client** side: `FillSessionFromServerRules`,
  `GetLobbyKeyValuePairsFromSessionInfo`, `FillSessionFromLobbyData`
  (`xrefs_to` in Ghidra). The client itself reads the rules from the response and takes
  `P2PPORT` from there.
* So the query port is served by the Steam server API (`SteamGameServer_Init` with
  `GameServerQueryPort`), i.e. the code sits **inside** steamclient64/GameNetworkingSockets,
  not in the game binary → the ARK-API plugin does not see this path.

The actual protocol on the bench (verified with `a2s_diag.py`):

| Request | Response |
|---|---|
| `FF FF FF FF 54 "Source Engine Query\0"` | `FF FF FF FF 41 <4-byte challenge>` |
| `FF FF FF FF 56 <challenge>` | `FF FF FF FF 45 <uint16 count=21> key\0value\0 …` (A2S_RULES) |
| `FF FF FF FF 55 <challenge>` | `FF FF FF FF 44 …` (A2S_PLAYER; 6 bytes on an empty server) |
| `FF FF FF FF 49 [challenge]` | **no response** (A2S_INFO not supported) |

The rules response on 7778/27016 confirms the bench:
`CUSTOMSERVERNAME_s = server2 - v358`, `P2PPORT = 7778`, `NUMOPENPUBCONN = 70`,
`SERVERUSESBATTLEYE_b = false`, `OWNINGID = 90295262070632470`.

### 1.3 RCON (32331)

`RCONClientConnection::ProcessRCONPacket` — v358 decompilation, address `0x140A6CC20`:

* password comparison is **case-insensitive** (`TChar<wchar_t>::ToLower` per character);
* on a wrong password: response `id = -1`, `IsClosed = true`, the connection closes;
* **no** failed-attempt counter, **no** delay, **no** blocking;
* an authorized command goes into `UShooterCheatManager` (vtable+0x1F8) — i.e. it executes
  **on the game thread**.

Side effect: an RCON command passes through the server tick (30 Hz), so any command
responds no faster than ~33 ms — measured: 33.0–34.6 ms for an empty command.

---

## 2. Measurements

Tool: the **NetGuard** plugin (see §4) — captures TPS, tickMs, live connections,
connection attempts, packets, logins per IP; the metrics are read over
TCP 127.0.0.1:27101. CPU is taken directly from the PID of the relevant server
instance (Server2).

### 2.1 Game port 7778 — junk datagrams

| Packets | Rate | Process CPU | tickMs | TPS | Memory |
|---|---|---|---|---|---|
| background | — | ~13% | 33.0 | 30.1 | 2491 MB |
| 1 000 | 4 000 pps | — | 33.3 | 30.1 | unchanged |
| 3 000 | — | — | 33.2 | 30.1 | — |
| 6 000 | — | — | 33.1 | 30.1 (min 25.2) | — |
| 10 000 | — | — | 33.4 | 30.1 | — |
| 15 000 | 4 392 pps | — | 33.5 | 30.0 | — |
| 24 000 | 6 772 pps | **23.7%** | 33.5 | 30.1 | 2491 MB |
| 30 000 | 3 443 pps | — | 33.7 | 30.1 (min 26.4) | — |
| 24 000 ×3 (repeat) | 4 000 pps | 19.9 / 10.5 / 13.4% | 32.9 → **47.9 → 47.1** | 30.1 → **20.7 → 21.3** | 2491 MB |

Key point: the dip is **reproducible** and **does not release** — 400 s after the last
volley the tick is still 47 ms instead of 33 ms (TPS 21.1 instead of 30.1).
Memory meanwhile grows slowly (2491 → 2559 MB, +68 MB) — state accumulates on the
Steam layer side (per the upstream sources).

Recovery curve (after the 24 000 ×3 series, 20 s interval):

```
t=  0s  22.4 TPS  45.6 ms   2491 MB
t= 60s  22.1 TPS  46.4 ms   2494 MB
t=140s  21.3 TPS  80.1 ms   ← a single 80 ms tick "freeze"
t=200s  21.6 TPS  44.6 ms   2499 MB
t=300s  21.9 TPS  46.8 ms   2499 MB
t=400s  21.1 TPS  47.1 ms   2499 MB
```

Second observation (one volley of 24 000 packets, `out/recovery3.txt`):

```
t=  0s  21.5 TPS  46.7 ms   2489 MB   (server in the degraded state)
t= 40s  22.7 TPS  34.3 ms   2489 MB   (recovery begins)
t= 60s  29.9 TPS  34.4 ms   2491 MB
t= 80s  30.1 TPS  32.7 ms   2491 MB   (normal regime restored)
t=120s  30.0 TPS  34.2 ms   2492 MB
```

Outcome: the degradation is **directly proportional to the amount of state accumulated in
the Steam layer**: one 24k volley - recovery in ~40-60 s, three volleys in a row -
holds longer than 400 s. The server itself does not crash and does not lose
contact with players - it simply ticks at 70% of its FPS, which on a live server means
ping spikes and "jittering" rendering for all players.

Outcome of the first observation: **the degradation holds for at least 400 s** (the server
ticks at 70% of its FPS). Later, on the same process, the FPS returned to the normal 30 —
i.e. the state **does recover**, but not immediately (the exact time is being clarified
with the `out/recovery3.txt` observation). A process restart restores the server
instantly in any case.

Cost per packet: ≈ +11 ms/tick for 24 000 packets ≈ 0.5 µs of game-thread time
per packet (≈ 2 000 packets per 1 ms of tick, ≈ 50 000 packets to halve the FPS).

### 2.2 Steam query port 27016

| Packets | Rate | tickMs | TPS | Conclusion |
|---|---|---|---|---|
| 4 000 | 20 pps (the client is throttled by 50-ms latency) | 34.2 → 34.1 | 29.6 → 29.3 | a dip within noise |
| 20 000 | 4 795 pps | 34.5 → 33.2 | 30.1 → 30.1 (min 29.3) | **no effect** |

A fixed response delay of ~50 ms per request (median 49.5 ms on one thread),
a 100% response rate, the server answers all requests.

### 2.3 RCON 32331 — testing excluded

By the client's request, RCON is **not tested**. Below are only the results of
static analysis (decompilation of `RCONClientConnection::ProcessRCONPacket`,
v358 @`0x140A6CC20`):

* password comparison is **case-insensitive** (`TChar<wchar_t>::ToLower` per character);
* on a wrong password: response `id = -1`, `IsClosed = true`, the connection closes;
* **no failed-attempt counter, delay, or blocking**;
* an authorized command goes into `UShooterCheatManager` (vtable+0x1F8) —
  i.e. it executes **on the game thread** (a 30 Hz tick quantum ⇒ response >= 33 ms).

---

## 3. Attack vectors

| # | Port/protocol | Essence | Impact (measured on the bench) | Complexity | Defense |
|---|---|---|---|---|---|
| V1 | **7778/UDP** — the game port | a storm of junk datagrams from different source ports | +11 ms/tick for 24k packets, TPS 30->21, CPU 13->24%; after the flood stops the server recovers on its own (one 24k volley - in ~40-60 s; three volleys in a row - >400 s, `out/recovery3.txt`), memory +68 MB | low | a network filter (WFP/firewall) on 7778; **cannot be fixed in-process** — the packets never reach UE4 |
| V2 | **7778/UDP** — GNS transport forgery | forging a SteamNetworkingSockets session (3 packets, **no Steam account and no crypto**) + data packets with an unreliable frame | **fully implemented**: 1 data packet = 1 `UNetConnection` (control by frame type, §16.8). Local bench: ~25 000 pps → **TPS 21.7 → 2.5**, collapse threshold ~100 k packets, recovery 15–20 s. **External VPS: the effect only from ~500 k packets** (100–300 k — no effect) ⇒ the magnitude of the effect is determined by the server's CPU headroom (§16.11). ~10× cheaper than a junk flood | low (plain UDP) | **firewall/rate limit on 7778**; a valve on `NotifyAcceptingConnection` **does not help** (all attempts rejected, yet the FPS still fell) |
| V3 | **27016/UDP** — Steam query | a flood of A2S requests | at 4 800 pps there is **no** effect; 446 B per 30-B request = **x15 amplification** (a reflection vector) | low | an OS-level limit (WFP/firewall) or not publishing the query port |
| V4 | **32331/TCP** — RCON | password brute force + command execution on the game thread | **active testing excluded by the client's request**; statically (decompilation of `ProcessRCONPacket`, v358 @`0x140A6CC20`): case-insensitive password comparison, no attempt counter or blocking, commands execute on the game thread | medium | **do not expose RCON outward** (`RCONEnabled=False`); NetGuard: per-IP limits and an attempt counter |
| V5 | **7778/UDP** — login forgery | a series of login attempts (`PreLogin` on the game thread) | load on authorization | medium | NetGuard: a per-IP login limit + a temporary ban |
| V6 | **27016/UDP** — reflection | a spoofed victim IP in an A2S request | x15 amplification, the response comes from the server IP | low | do not publish the query port; edge filtering |
| V7 | **7778/UDP** — Handshake of SteamNetworkingSockets (GNS) | forging stage 1 (ChallengeRequest) and stage 2 (ConnectRequest) without a Steam certificate | the server **answers anyone**: 1999/2000 `ChallengeReply` at 10 252 pps; `ConnectRequest` without cert is accepted (`ConnectOK`) and creates a GNS connection (~13 KB, +23 KB of working set), then closes with reason 5002 ("no cert/session info"); **limit 1 connection per (IP:port)**; reflection: `ConnectOK` + `ConnectionClosed` (512 B) + a stream of GNS datagrams; CPU: 11 610 pps → TPS 21.8→21.4 | low (plain UDP, no account) | close 7778 outward; `IP_AllowWithoutAuth=0`, `AllowRemoteUnsignedCert=deny`; monitor `ConnectOK`/`ConnectionClosed(5002)` |

Separately: **amplification for third-party DDoS** — an A2S_RULES answer (446 bytes)
to a 30-byte request (x15). The answer comes from the server IP, so the server becomes
a traffic source; the defense is to not publish the query port.

## 4. The NetGuard plugin (developed, built, installed)

`C:\Dev\ARK-Server-Plugins\NetGuard\` → `build\Release\NetGuard.dll` →
`C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\`.

**Measurement (always on)** — TCP 127.0.0.1:27101, a JSON string per command:
`tps`, `tickMs`, `tickMsMax`, `memKB`, `uptimeSec`, `liveConnections`,
`connectionAttempts`, `connectionsRejected`, `packetsReceived`, `bytesReceived`,
`controlMessages`, `logins`, `newConnsPerSec`, a list of IPs with attempt counts.
Commands: `status`, `ping`, `reset`, `config`, `defense on|off`.

**Defense (config-driven, off by default, toggleable on the fly)**:

* a rate valve: if new connections per second exceed the threshold —
  `UWorld::NotifyAcceptingConnection` returns `Reject`, and the connection
  **is not created at all** (cheaper than creating and closing one);
* a ceiling on live connections (`maxLiveConnections`);
* a per-IP login attempt limit (`loginsPerIpPerMinuteLimit`) + a temporary IP ban
  at the `ExtraPreLoginChecksBeforeWelcomePlayer` gate.

Hooks (all 5 attached on the bench):
`UWorld.NotifyAcceptingConnection`, `UNetConnection.ReceivedRawPacket`,
`UWorld.NotifyControlMessage`, `AShooterGameMode.PreLogin`,
`AShooterGameMode.ExtraPreLoginChecksBeforeWelcomePlayer`.

### 4.1 Hot reload without a server restart

ArkApi provides `plugins.load <Name>` / `plugins.unload <Name>` (console and RCON
commands). Procedure:

```
plugins.unload NetGuard      # invokes Plugin_Unload -> DisableHook -> FreeLibrary
<copy the new NetGuard.dll>
plugins.load NetGuard
```

**Important, found experimentally:** ArkApi stores hooks in a global map and
**does not remove them when the plugin is unloaded**. If your hooks are not removed in
`Plugin_Unload`, after `FreeLibrary` there remain detours pointing into the unloaded DLL,
and the next `plugins.load` fails with "Failed to attach hook for …" (and the server
crashes when calling such a function). Therefore `Plugin_Unload` calls
`ArkApi::GetHooks().DisableHook(name, detour)` for each installed hook —
after that the unload→copy→load loop works cleanly, without a server restart.

The second pitfall: `ArkApi::GetAddress()` returns **0** if the symbol is absent from
the PDB (`UIpNetDriver.StaticClass`, `UObject.Class` are missing from PDB v358) — a direct
call through such an address kills the game thread (verified: the server crashed).
Therefore the plugin has a `SafeStaticClass()` with an address check and an SEH-wrapped
`OnTick`, which prevents a plugin exception from killing the server.

### 4.2 Configuration

`…\Plugins\NetGuard\NetGuard.json`:

```json
{
  "enabled": true,
  "tcpEnabled": true,
  "tcpPort": 27101,
  "bindAddress": "127.0.0.1",
  "statusIntervalSeconds": 1.0,
  "defenseEnabled": false,
  "newConnectionsPerSecondLimit": 50,
  "maxLiveConnections": 0,
  "loginsPerIpPerMinuteLimit": 10,
  "blockSeconds": 300
}
```

---

## 5. Lab scripts (`C:\Dev\_research\security\`)

| File | Purpose |
|---|---|
| `ark_lab_net.py` | protocol layer: A2S, process metrics (WinAPI), a `guard_target()` guard - the script refuses to work with a non-bench address. **No RCON in it** |
| `ark_lab_metrics.py` | client of the NetGuard JSON interface (TPS/tickMs/connection metrics) |
| `ark_lab_fpsdrop.py` | **the main tool for the "minimum packets -> FPS drop" task**: packet series against the game port with TPS/tickMs/CPU measured via NetGuard, `game`/`query` modes, a sweep of series sizes |
| `ark_lab_loadtest.py` | general bench: `query`, `query-flood`, `game-flood`, `suite` (metrics - via NetGuard, **no RCON**) |
| `ark_lab_l7_probe.py` | L7 probing of the Steam-query surface: oversized datagrams, junk values in A2S fields |
| `ark_lab_handshake_capture.py` | a UDP relay to capture the first packets of a real client (needed for vector V2) |
| `a2s_diag.py` | analysis of A2S request variants against the query port |
| `a2s_probe_shapes.py` | enumeration of packet shapes against the game port (all dropped by GNS) |
| `rcon_cmd.py` | **administration only**: one console command (needed for `plugins.load`/`plugins.unload`). RCON testing is excluded; this tool is not used in the resilience measurements |

---|---|
| `ark_lab_net.py` | protocol layer: A2S, Source-RCON, process metrics (WinAPI), protection against "non-bench" addresses |
| `ark_lab_metrics.py` | client of the NetGuard JSON interface |
| `ark_lab_loadtest.py` | main bench: `query`, `query-flood`, `rcon-probe`, `rcon-auth`, `rcon-flood`, `rcon-impact`, `game-flood`, `suite` |
| `ark_lab_fpsdrop.py` | **the main tool for the "minimum packets -> FPS drop" task**: packet series with TPS/tickMs/CPU measured via NetGuard, `game`/`query` modes, a sweep of series sizes |
| `ark_lab_handshake_capture.py` | a UDP relay to capture the first packets of a real client (needed for vector V2) |
| `a2s_diag.py` | analysis of A2S request variants against the query port |
| `a2s_probe_shapes.py` | enumeration of packet shapes against the game port (all dropped by GNS) |
| `rcon_cmd.py` | one RCON command on the bench |

---

> **RCON is not tested** (a client requirement). The tool `rcon_cmd.py`
> is kept only as an administrative utility for hot-reloading
> ArkApi plugins (`plugins.load` / `plugins.unload`) and is not used for
> resilience testing.

## 7. L7 (application layer): surfaces and probing

> **RCON is not tested** (a client requirement). The tool `rcon_cmd.py`
> is kept only as an administrative utility for hot-reloading
> ArkApi plugins (`plugins.load` / `plugins.unload`) and is not used for
> resilience testing.

### 7.1 Surface map

| Surface | Port | Implementation | Who processes it | Externally observable |
|---|---|---|---|---|
| Steam query / A2S | 27016/UDP | the Steam server API inside the process (`steamclient64`) | **not UE4**, invisible to the plugin | 446 B per 30-B request |
| Source RCON | 32331/TCP | `URCONServer` in the game binary | the game thread | ~33 ms response (the tick quantum) |
| UE4 game protocol | 7778/UDP | GameNetworkingSockets → `UIpNetDriver::TickDispatch` | the game thread, but only **after** a valid handshake | without a handshake — 0 connection attempts |
| Beacon port (7779) | — | `NAME_BeaconNetDriver` exists in the binary, but the port is **not open** | — | — |
| Chat / RPC | 7778 | `AShooterPlayerController::ServerSendChatMessage` | the game thread | only after login; ArkApi has a built-in 1 message/s filter |
| EOS/Steam sessions | — | client sessions (matchmaking) | Steam/EOS | the server does not host sessions |

### 7.2 What was actually probed on the bench (`ark_lab_l7_probe.py`)

| Test | Expected "vulnerability" | Fact |
|---|---|---|
| RCON: length prefix `65536` with no body | a 64 KB allocation | mem 2489→2489 MB, tps 30.0 |
| RCON: length prefix `67108864` (64 MB) | a 64 MB allocation | mem unchanged, tps 30.0 |
| RCON: length prefix `536870912` (512 MB) | a 512 MB allocation | mem unchanged, tps 29.9 |
| RCON: correct length, 1 MB body | parsing load | mem unchanged, tps 30.0 |
| A2S: datagrams of 4/32/60 KB | memory overconsumption | mem unchanged, tps ≈ 29.7 |
| A2S: `A2S_RULES` with `count=0xFFFF` | a hang/a parsing error | no answer, server alive |
| A2S: `A2S_PLAYER` with `count=0xFF` | the same | no answer |
| A2S: `A2S_INFO` + 60 KB tail | overflow | no answer |

**L7 conclusion:** in this build (358.24) the application surfaces RCON and A2S **are
written carefully** — an RCON packet length does not lead to an allocation sized by the
declared value, junk in A2S fields is dropped without errors. The actually exploitable
L7 vectors lie not in parsing but in **authorization** (RCON without blocking) and in
**amplification** (A2S ×15 for a reflection vector).

### 7.3 Residual L7 risks (not probed, requires a client)

* **The UE4 layer after the handshake**: `NMT_Login` → `ApproveLogin` → on a full
  server the client is sent the control message `"Server full."`
  (`UWorld::NotifyControlMessage`, string `0x143C29BE8`).
  The cost of processing a login (Steam/EOS token validation, a session lookup,
  `FCurrentLoginAuthCheck`) is on the game thread; under a stream of "half-logins" this is
  the most expensive L3-L7 path.
* **Chat**: 1 message/s per player (the ArkApi filter) — with a large player count that
  is 70 messages/s on the game thread.
* **Amplification after the handshake**: a valid Steam handshake starts the
  UE4 connection setup; the server then sends welcome/NetGUID data and the map. This
  requires a real client, so it is not quantified.

---

## 8. "Flooding the world with fake connections" (slot history)

### 8.1 How slots are counted (RE, UE4.5 sources shipped with the game)

```cpp
// Engine/Source/Runtime/Engine/Private/GameSession.cpp:118-121 (ApproveLogin)
if (AtCapacity(SpectatorOnly == 1))
    return NSLOCTEXT("NetworkErrors", "ServerAtCapacity", "Server full.").ToString();

// Engine/Source/Runtime/Engine/Private/GameSession.cpp:198-203 (AtCapacity)
const int32 MaxPlayersToUse = CVarMaxPlayersOverride.GetValueOnGameThread() > 0
                            ? CVarMaxPlayersOverride.GetValueOnGameThread() : MaxPlayers;
return ( (MaxPlayersToUse>0) && (GetWorld()->GetAuthGameMode()->GetNumPlayers() >= MaxPlayersToUse) );
```

Call points in ARK v358 (Ghidra, xrefs by the `"Server full."` string):
* `AShooterGameSession::ApproveLogin` (`0x140CE1100`) — returns the error text;
* `UWorld::NotifyControlMessage` (`0x142621440`) — sends this text to the client.

`GetNumPlayers()` is the **count of LOGGED-IN players** (`GameState->PlayerArray`),
not the count of sockets/connections.

### 8.2 Answer: fake connections do NOT occupy slots

* `UNetDriver::ClientConnections` (what "junk" packets populate) does
  **not participate** in the capacity check;
* half-open connections (created, but without a login) do not get into
  `GameState->PlayerArray` ⇒ real players keep joining;
* to get "Server full.", the attacker needs a **real login**
  (a valid Steam/EOS token) — i.e. genuine accounts, not packets.

Conclusion: the vector "flood the world with fake connections" does **not work**
in ARK SE at the connection level. This matters: protection against a "connection flood"
≠ protection against a "login flood".

### 8.3 What actually yields "Server full." — one RCON command

`net.MaxPlayersOverride` — an engine CVar (`GameSession.cpp:14`), it **overrides
MaxPlayers** in the capacity check:

```cpp
static TAutoConsoleVariable<int32> CVarMaxPlayersOverride(TEXT("net.MaxPlayersOverride"), 0,
    TEXT("If greater than 0, will override the standard max players count. Useful for testing full servers."));
```

* The CVar is set from the console, i.e. **from RCON** (RCON commands go into
  `UShooterCheatManager::Exec` → the console): one command
  `net.MaxPlayersOverride 1` — and `AtCapacity()` becomes true at **any**
  player count ⇒ every login receives `"Server full."`.
* Verified on the bench: the command executes without error; the advertised slot count
  in the A2S rules (`NUMOPENPUBCONN = 70`) does not change — the CVar affects exactly
  the login gate, not the advertised slot count.
* Negative effect: the value is **not reset** by a map change and is only restored by
  a server restart or an explicit `net.MaxPlayersOverride 0`.

Outcome: "occupy all slots" can be done not with packets but **with one command** — but
only with RCON access. One more argument to close RCON.

### 8.4 Observation tool

NetGuard gained slot metrics: `players` (`AGameMode::GetNumPlayers`),
`maxPlayers` (`AGameSession.MaxPlayers`), `atCapacity` (a local replica of
the engine rule), `liveConnections` (`UNetDriver::ClientConnections.Num()`) —
all readable over TCP 127.0.0.1:27101 and able to distinguish "many
connections" from "many players".


1. **A valid Steam handshake** — the only thing that would open vector V2 (1 packet →
   1 `UNetConnection`). There is no ARK client on the machine (`ShooterGame.exe` not found).
   One capture is needed: run a real client through
   `ark_lab_handshake_capture.py` (client → 127.0.0.1:7780 → server) and get the
   first N client→server datagrams.
2. **Windows Firewall** on the bench was enabled and blocked inbound UDP — without
   disabling it the "packets do not arrive" results are invalid. The profiles are now
   disabled; for a production bench the correct solution is an allowlist by rules,
   not disabling the firewall.
3. Measuring V2 will require the `InitialConnectTimeout`/`ConnectionTimeout`
   of the particular production server (300 s on the bench) — the duration of the
   degradation depends on it.

---

## 9. Final vector ranking (final measurements, defense off)

Methodology: the NetGuard plugin (a 5-s FPS window), CPU - taken directly from the
bench PID, offered load - the "UDP Datagrams Received" counter on the host.
The client senders are pinned to cores 0-19 so as NOT to steal CPU from the server
(the ARK server on the bench is pinned to 4 cores, mask 0xF00000 = cores 20-23).
The control is the same load against a non-listening port 7779 (the noise floor: min
26.5 FPS).

| Rank | Vector | Offered load | FPS (before -> after) | Tick period | CPU | Verdict |
|---|---|---|---|---|---|---|
| **1** | **V1. UDP flood of the game port 7778, 12-20 sources** | **242 k pps (20 src - ~700 k)** | **30 -> 1.5-2.4 (min 0.9)** | 33 -> 428 ms | 4 cores saturated | **the only vector dropping FPS to 2-3** |
| 2 | V1. the same flood, 6 sources | ~210 k pps | 30 -> 24.6 | 34 ms | ~4 cores | the knee: the effect begins |
| 3 | V1. the same flood, 1 source | ~35 k pps | 30 -> 29.5 | 33 ms | 0.9 core | only CPU burn, FPS intact |
| 4 | V3. Steam query flood 27016 (A2S_RULES) | 41 k datagrams/s | 30.0 -> 30.0 | 33 ms | +0.5 core | FPS unaffected; the value is x15 reflection |
| 5 | V6. `net.MaxPlayersOverride 1` via RCON | 1 command | all logins rejected ("Server full.") | - | - | not a packet vector; close RCON |
| 6 | V5/V2. fake logins / handshake replay | needs a real client | - | - | - | out of reach without a client |
| - | V4. RCON | - | - | - | - | testing excluded by request |

### 9.1 Why exactly this vector (the mechanism)

1. The game port is served by a **Steam P2P session** (`steamclient64`: visible in the
   binary are `m_mapP2PConnectionRequests`, `P2PConnectionRequest_t`). Arbitrary
   datagrams do not reach UE4 (`connectionAttempts = 0`), but **cost the server
   ~20 µs of CPU each** (verified: 35 k pps -> 0.9 core; 242 k pps ->
   4 cores saturated).
2. The server is pinned to **4 cores** (mask 0xF00000). As soon as the budget is
   exhausted, the game thread gets no CPU time -> **the tick period grows
   from 33 ms to 200-600 ms** ⇒ FPS 30 -> 0.9-2.4. Memory meanwhile does not grow
   (2504 -> 2510 MB): this is pure CPU starvation, not a leak.
3. The processing cost **does not depend on packet size** (64 B and 1400 B cost
   the same ~20 µs) ⇒ small packets at maximal rate are more profitable.
4. The second most effective lever is **server outbound traffic**: an A2S_RULES answer
   (446 B) to a 30-B request = x15 amplification, the server becomes a traffic source
   for third parties.

### 9.2 Validation of defenses (verified experimentally)

| Defense | Result on the bench |
|---|---|
| NetGuard, a valve via `NotifyAcceptingConnection` (`defense on`) | **DOES NOT HELP**: FPS 1.4 under the same load. Reason: junk packets are dropped by the Steam layer and **never reach UE4**, so the hook does not see them |
| Connection caps / per-IP limits | not applicable: no connections are created |
| A network filter on port 7778 (firewall/WFP/external firewall) | **works by construction**: the control test — the same load against a non-listening port 7779 gives zero drop (noise floor 26.5 FPS) ⇒ all the damage comes precisely from the game-port socket; closing/thinning it removes the vector |
| RCON outward | remove it: 1 CVar command puts the server in "Server full." mode for everyone |

### 9.3 Recommended rules (Windows / gateway)

```powershell
# 1) Game port - allowlist only (the "block any" rule overrides "allow")
netsh advfirewall firewall add rule name="ARK 7778 allow" dir=in action=allow protocol=UDP localport=7778 remoteip=<ADMIN_IP> profile=any
netsh advfirewall firewall add rule name="ARK 7778 deny"  dir=in action=block protocol=UDP localport=7778 profile=any
# 2) Do not publish the query port outward (otherwise the server is a source of x15 traffic)
netsh advfirewall firewall add rule name="ARK 27016 deny" dir=in action=block protocol=UDP localport=27016 profile=any
# 3) RCON only on localhost
netsh advfirewall firewall add rule name="ARK 32331 deny" dir=in action=block protocol=TCP localport=32331 profile=any
```

```bash
# On the gateway in front of the server - per-source rate limiting (iptables/nftables)
iptables -A INPUT -p udp --dport 7778 -m hashlimit --hashlimit-above 2000/s          --hashlimit-mode srcip --hashlimit-name ark77 -j DROP
# or nftables:
# nft add rule inet filter input udp dport 7778 meter ark77 { ip saddr limit rate 2000/second } drop
```

An OS-level rate limit is the only measure that works against V1: the packets never
reach the process at all, so neither the game thread nor the Steam layer spend CPU
on them.

---

## 10. The game-port transport: SteamNetworkingSockets (full analysis)

A full analysis is in `ARK_SPECIFIC_VECTORS.md`, §13. Here is the summary.

**What is listening on 7778.** Not "bare" UE4 UDP but a listen socket of the open-source
GameNetworkingSockets (DirectUDP): `GameNetworkingSockets.dll` (438 KB) in the server
directory is built from ARK engine sources
(`H:\AtlasTrunk\...\GameNetworkingSockets\...`) and matches the public upstream
`ValveSoftware/GameNetworkingSockets`. The dispatcher of incoming packets is Ghidra
`FUN_180024E00` (RVA 0x24E00).

**Format (recovered byte by byte).**

| Message | Code | Frame |
|---|---|---|
| ChallengeRequest | `0x20` | `[0x20][u16 LE len][pb][padding to 512 B]` |
| ChallengeReply | `0x21` | `[0x21][pb]` |
| ConnectRequest | `0x22` | `[0x22][pb]` |
| ConnectOK | `0x23` | `[0x23][pb]` (field 5 = `server_connection_id`) |
| ConnectionClosed | `0x24` | `[0x24][u16 len][pb][pad to 512 B]` (field 3 = `reason_code`) |
| Data | `0x80` | `[0x80][u32 to_connection_id][u16 seq][payload]` |

**Key conclusion.** The challenge is not a cryptographic barrier: the server itself issues
it in `ChallengeReply` (`SipHash(nTime, port, IP)|nTime`, a random secret); it suffices
to duplicate it back from the same address (it lives ~4 s). The real barrier is
`cert` + `crypt` in `ConnectRequest`: without them `RecvCryptoHandshake` closes
the connection with `reason_code = 5002`.

**Measured on the bench (Server2, 192.168.8.218:7778).**

* 2000 `ChallengeRequest` → 1999 answers (10 252 pps), no state created (Δmem = 0);
* `ConnectRequest` without cert → **`ConnectOK`**, the server creates a GNS connection
  (~13 KB, `operator_new(0x33e8)`), a working set of +23 KB per connection,
  then `ConnectionClosed` (5002) — no persistent state remains;
* **limit: 1 concurrent GNS connection per (IP:port)** (10 ports → 10 `ConnectOK`,
  400 ports → 400 `ConnectOK` out of 4000 requests, 1 port → 1);
* CPU: 11 610 `ConnectRequest`/s → TPS 21.8 → 21.4 (the junk flood needed ~242 000 pps);
* reflection: 4000 requests → 400 `ConnectOK` + 400 `ConnectionClosed` (512 B) + 22 632
  GNS datagrams (the junk path does not reflect at all);
* a replay of a real UE4 packet (the UE4 layer) was dropped by the server
  (Δ `connectionAttempts` = 0) ⇒ the transport barrier is real.

**Outcome.** "1 packet = 1 `UNetConnection` of the UE4 layer" without a Steam account is
**not achieved** (needs `cert`+`crypt`), but "1 packet (60 B) = 1 server-side GNS
connection (13 KB)" is achieved, with a limit of 1 per (IP:port) and with traffic
reflection. The next step — check whether the server accepts an unsigned `cert`
(then pure Python is enough: X25519 + ECDSA P-256; the `cryptography` module is not
present on the bench).

> **Update (later in the same session): the `cert` hypothesis turned out to be wrong.**
> Intercepting a real client via a UDP relay showed: the ARK client itself sends
> `ConnectRequest` **without `cert` and without `crypt`** — the server accepts such a
> connection. The barrier was not in the certificate. After recovering the format of the
> SNP frames the vector is fully implemented — see §11 and `ARK_SPECIFIC_VECTORS.md` §14.

---

## 11. Vector V2 implemented: GNS session forgery (details)

Full analysis in `ARK_SPECIFIC_VECTORS.md` §14. Here is the essence.

**The attack frame — 3 packets, no account and no crypto:**

```
[0x20][u16 len][pb][pad→512]  ChallengeRequest  ->  [0x21] ChallengeReply
[0x22][pb]                     ConnectRequest    ->  [0x23] ConnectOK
[0x80][u32 conn_id][u16 seq][0x37][u32 msg][UE4 bytes]   data (1 packet = 1 UNetConnection)
```

**Measured (Server2 bench):**

| What | Result |
|---|---|
| 2 000 forged packets | 2 000 `UNetConnection` (24 256/s), TPS unchanged |
| 10 000 pps × 15 s | 150 000 connections, TPS 21.7 (no effect) |
| 20 000 pps exactly × 12 s | 240 000 connections, TPS dipped to 15.4, recovered to ~20 |
| **~21 000 pps burst × 9 s** | **200 000 connections, TPS 21.1 → 17.3 → 2.2 (4 s) and holds at 2.0** |
| Recovery after stopping | 15–20 s (to 21.7) |
| Memory / log | stable (+2 MB / 0 B) |
| Comparison with the junk flood | junk — ~242 000 pps, forgery — ~21 000 pps (**10 times cheaper**) |
| NetGuard `defense on` (limit 50/s) | **does not defend**: `connectionsRejected = 200000` (all rejected), yet TPS still fell to 2.0 — the cost arises before the rejection point |

**Conclusions and recommendation:** the only effective measure is network-level (close
UDP 7778 to external sources / rate-limit at the edge). The valve on
`UNetConnection` in ARK triggers too late. Monitoring: a sharp rise of
`connectionAttempts` in NetGuard = probing of GNS handshakes.

**Tools:** `ark_lab_gns_amp.py` (main, self-contained: first checks server availability —
an A2S ping, the game port's response to `ChallengeRequest`,
the metrics plugin — and refuses to run with code 3 if the game port does not answer),
`ark_lab_suite.py` (the ranking), `ark_lab_gns_ue4_v2.py`, `ark_lab_gns_connect.py`,
`ark_lab_gns_relay.py`, `ark_lab_gns_analyze.py`.

---

## 15. Final vector ranking by power (by measured impact)

Methodology: the NetGuard plugin provides `tps` (updated on the game tick, so under
heavy degradation the metric lags — the damage is visible in the measurement **after**
the flood), `connectionAttempts` (the count of created `UNetConnection`), `memKB` and
the server log size. Each scenario runs for 12 s; between scenarios the server
fully recovers (20 s pauses).

Run: `python ark_lab_suite.py --all --seconds 12 --json out/suite.json`.

| # | Vector | Packets | pps | TPS before | TPS min | TPS after | **Power** | Connections created |
|---|---|---|---|---|---|---|---|---|
| **1** | **S4 — GNS session forgery + UE4 packet injection** | 254 000 | 25 221 | 21.1 | **2.5** | 19.8 | **88 %** | **+254 000** |
| 2 | S2 — GNS `ChallengeRequest` flood | 174 400 | 17 392 | 21.5 | 21.0 | 21.2 | 2 % | 0 (no state) |
| 3 | S1 — junk datagrams on 7778 | 432 000 | 43 103 | 21.4 | 21.0 | 21.2 | 2 % | 0 |
| 4 | S3 — GNS `ConnectRequest` flood (anonymous connections) | 139 024 | 13 864 | 21.1 | 20.8 | 21.1 | 1 % | 0 (limit 1 per IP:port) |
| 5 | S5 — Steam query flood 27016 (x15 reflection) | 428 000 | 42 794 | 21.1 | 21.0 | 21.0 | 0 % | 0 |

**"Power"** = (TPS_before − TPS_min) / TPS_before, where TPS_min is the minimum of three
measurements (during the flood, right after, +5 s). "Cost" — the packet count up to
which the server degrades by half.

### 15.1 Stepped measurement of S4 (the cost of the attack)

| Packets sent | TPS after the volley |
|---|---|
| 20 000 | 21.1 |
| 40 000 | 20.8 |
| 60 000 | 20.5 |
| 80 000 | 20.2 |
| **100 000** | **2.8** ← the collapse (TPS falls 7-fold) |
| 140 000 | 2.5 |
| 200 000 | 2.6 |

**The cost of the attack: 100 000 packets** (≈3 MB of traffic, 4 seconds at
25 000 pps) — after this threshold the server TPS falls from 21 to 2.5. In the stepped
mode (volleys 1.2 s apart) the same threshold is confirmed: 80 000 packets → TPS 19.5,
100 000 → 13.7. Recovery after stopping — 15–20 s.

Under a continuous stream (no measurement pauses) the same scenario collapses to
**TPS 2.0** (a tenfold drop), with recovery in 15–20 s after stopping.

### 15.2 Ranking conclusions

1. **The only vector with real power is S4** (98 %): transport forgery
   + UE4 packet injection. The remaining vectors within the measurable bench limits
   (12 s, up to ~50 000 pps) give 0–5 % degradation.
2. **S4 is the cheapest in traffic per unit of damage**: ~80 000 packets (≈1.5 MB/s)
   drop the server from 21 to 14 TPS, and a continuous 26 000 pps stream — to 0.4–2.0
   TPS. For comparison, the junk flood required ~242 000 pps — **3–10 times more
   expensive**, and those packets never even cause connections to be created.
3. **Packaging**: the packet cost in S4 is an order of magnitude higher because the
   server creates and destroys a full `UNetConnection` per
   packet (allocation, initialization, registration in the NetDriver list, processing in
   the tick).
4. **Slots are not occupied meanwhile** (§12): the connection does not reach `Welcome`,
   so "70 fake players" remain unreachable; what suffers is the CPU/tick
   and server stability, not slot availability.
5. **Recovery**: after the flood stops the server returns to normal
   in 15–20 s ⇒ the DoS is transient but fully reproducible.
6. **Defense**: the NetGuard valve on `NotifyAcceptingConnection` is **ineffective**
   (all 200 000 attempts rejected, yet TPS still fell) — only a network measure works:
   close UDP 7778 to external sources or rate-limit at the edge (nftables/WFP).
   Monitoring: a sharp rise of `connectionAttempts`.

### 14.6 Verification on an external server (the real Internet)

Goal: make sure the vector works not only on the local bench but against a
publicly available ARK server on the network, and that the availability pre-check
works correctly against a remote target.

Target: `23.109.45.13`, game port `25714`, query port `25715`
(determined by scanning: A2S_INFO answers 256 B —
`pxHosting Ark Server - 2 (v358.24)`, map `TheIsland` — the same v358.24 build
as on the bench).

| Stage | Result |
|---|---|
| Pre-check | A2S: 256 B; game port: `ChallengeReply` (challenge issued, protocol V5); the metrics plugin is local — unavailable for measuring a remote server |
| Session forgery | `ConnectOK` received, `server_connection_id = 0x6be706e1` — **the server accepted the forged connection without an account** |
| UE4 packet injection | 200 000 packets @ 24 012 pps and 300 000 packets @ 22 808 pps sent to the external game port |
| Local bench | unaffected: Δ `packetsReceived` = 0, Δ `connectionAttempts` = 0, TPS 21.7 (all traffic went to the remote host) |

**Measuring the impact on the remote server.** There is no NetGuard plugin on the
foreign server, so the state is measured indirectly — by the response time of
the query port (`ark_lab_remote_probe.py`, 0.2 s interval).

| Condition | Replies | Losses | RTT median | RTT max |
|---|---|---|---|---|
| Control (40 s, no attack) | 96 / 99 | 3 % | 146 ms | 186 ms |
| Before the attack (0–10 s) | 26 / 26 | 0 % | 157 ms | 447 ms |
| **During the attack (300k packets)** | **5 / 10** | **50 %** | 174 ms | 368 ms |
| After the attack (24+ s) | 42 / 42 | 0 % | 190 ms | 395 ms |

Conclusion: during the attack the remote server **loses half of the replies on the query
port** and recovers immediately after the flood stops — the behavior matches
the local bench (there the drop manifested as TPS 21.7 → 2.5, here as losses
on the query port, because a WAN RTT of 140–200 ms masks the tick change).
The absolute magnitude of the degradation is smaller: the local bench is pinned to 4
cores (mask `0xF00000`); the external server has different resources.

**Practical conclusion:** the vector requires nothing but access to the UDP port
of the game server from the Internet, and works "out of the box" against a public
ARK server with no accounts and no cryptography.

---

## 16. Refinement of the vector: honest attribution, packet cost and improvements

Section 14 measured the effect "by indirect signs". Here is a strict check
against the server's FPS/TPS with control scenarios and an independent meter
(own methodology, all corrections applied).

### 16.1 Methodology (and the measurement errors found along the way)

| What was done | Why |
|---|---|
| **Two independent signals**: TPS/tickMs of the NetGuard plugin **and** RTT to the query port (A2S) | RTT is served by a separate thread, so it shows "server availability", not game-thread health — the two must be distinguished |
| **A dedicated socket for the sampler** | sharing a socket with the main thread interleaved plugin responses (commands go sequentially over one socket) and produced junk TPS values/counter deltas |
| **Waiting for server recovery before each scenario** (until TPS ≥ 19) | otherwise scenarios inherit the previous dip and are not comparable |
| **Measuring the server process CPU** via `GetProcessTimes` | a metric independent of the plugin: the real cost of processing one packet, µs/packet |

### 16.2 Control scenarios: where exactly the degradation arises

Local bench Server2, 200 000 packets per scenario:

| Scenario | TPS before | **TPS min** | tickMs | A2S RTT max | connections |
|---|---|---|---|---|---|
| C0 idle | 21.4 | 21.0 | 48.5 | 63.8 ms | 0 |
| C1 junk datagrams on 7778 | 21.6 | **21.3** | 46.8 | 62.9 ms | 0 |
| C2 GNS session + **junk** in data | 21.4 | **0.0** | 45.9 | 63.2 ms | 0* |
| C3 GNS session + **UE4 handshake** (the vector) | 21.7 | **0.0** | 47.0 | 62.4 ms | +200 000 |

\* in a separate measurement with a junk payload template the connection counter also
grew (see 16.3) — i.e. **a connection is created regardless of payload validity**.

**The main conclusion that breaks the §14 wording:** C2 (transport only, without
UE4 content) degrades **exactly like** C3. So the effect comes from
**not the creation of `UNetConnection`, but the GNS data-packet processing path itself**:
a valid SNP frame goes through parsing, delivery into UE4 and dispatcher handling,
whereas a junk datagram is dropped at the input.

The wording "1 packet = 1 `UNetConnection`" remains true as a fact
(connections really are created), but **as an explanation of the DoS it is wrong**.
The correct wording: **a valid GNS data packet costs the game thread
2–4 times more than junk**, and degradation arises when the rate of incoming
packets exceeds the speed at which the tick can parse them.

### 16.3 The cost of one packet (the server process CPU, µs/packet)

| Packet variant | µs/packet | connections | comment |
|---|---|---|---|
| junk 64 B on 7778 | **10.6** | 0 | the baseline cost of receive and drop |
| GNS data, 1 unreliable frame, payload 6/64/512/1400 B | 20–24 | +1 per packet | **payload size does not matter** |
| GNS data, 1 reliable frame (0x40) | 20.1 | +2 252 | the reliable path |
| GNS data, 10 unreliable frames | 29.1 | +1 per packet | |
| **GNS data, 10 reliable frames (0x40)** | **39.8** | +5 | **the most expensive variant** |
| GNS ack frame (0x90) | 28.3 | 0 | the server updates counters |
| GNS data with the blob flag (0x81) | 22.6 | 0 | |

Hence — **an improvement to the vector**: the most profitable packet for the attacker is
10 reliable frames in one datagram (≈40 µs of processing versus 10.6 µs for
junk, i.e. **3.8 times more expensive**). Payload size is irrelevant.

### 16.4 Degradation threshold

| Rate | Transport | Result |
|---|---|---|
| ~8 000 pps | GNS data | no effect (TPS min 20.7) |
| ~25 000 pps | GNS data | **TPS 21.7 → 2.5** (a tenfold drop) |
| ~43 000 pps | junk | no effect (TPS min 21.0) |
| ~242 000 pps | junk (12 sources) | there is an effect (the earlier measurement) |

⇒ The forged-GNS-session vector is roughly **10 times cheaper** than the junk
flood in required rate, and with reliable frames the gain is even higher (packet cost
×3.8).

### 16.5 Negative result: "persistent" connections not confirmed

Hypothesis: if the UE4 handshake is completed, the connection will keep living and the
cost will shift to the server (memory + per-connection iterations in the tick) — then the
attacker can stop sending packets.

What was done: a GNS session was forged, then **copies of the data packets of a real
client** were sent into it (intercepted in `gns_relay_capture.jsonl`) with
`to_connection_id` replaced by the one issued by the server.

* The server **started replying** with a continuous stream of GNS datagrams (246 packets /
  4.9 KB per 30 s) — the server side of the handshake advanced;
* 200 such sessions added **+42 MB** of memory (≈210 KB per connection);
* **but** UE4 connections are not held: `liveConnections` returns to 2,
  memory is freed within ~10 s. Only GNS connections (of the
  transport layer) live; UE4 connections close because the cookie
  fails verification (it was issued to the real client).

**Conclusion:** a "persistent" DoS is not confirmed — the cost of the connections is small
(210 KB) and they are short-lived. Therefore the vector's main form is a **wave** of
packets: the attacker holds ~25 000 pps, the server falls tenfold,
and after stopping it recovers in 15–20 s.

### 16.6 The final ranking with correction

| # | Vector | Power (by TPS) | Cost | Note |
|---|---|---|---|---|
| 1 | **GNS session + data packets (10 reliable frames)** | **88–98 %** (TPS 21.7 → 2.5) | ~25 000 pps (≈20–25 k packets = 100 k to collapse) | the effect comes from the **transport**, not connection creation |
| 2 | junk flood 7778 | 0 % at 43 000 pps | ~242 000 pps | 10 times more expensive |
| 3 | GNS ChallengeRequest / ConnectRequest / A2S flood | 0–2 % | — | create no state / reflections yield x15 |
| 4 | "fake players" (slots) | 0 % | 70 accounts | slots are not occupied (§12) |

**Limitations of applicability (honestly):**
* it is the **game thread** that degrades (players, their packets), but **not server
  availability**: the A2S port is served by a separate thread and keeps answering (locally
  the RTT did not change: 47–63 ms). On an external VPS the effect looks stronger because
  the whole box suffers there (50 % losses on the query port);
* the effect is transient: 15–20 s after the flood stops;
* "1 packet = 1 `UNetConnection» is a fact, not a mechanism: the cost is in processing
  the packet, while the connections live ~10 s and cost ~210 KB.

### 16.7 New tools

| Script | Purpose |
|---|---|
| `ark_lab_gns_fps_test.py` | Strict FPS/TPS measurement with control scenarios C0–C3, recovery waiting, and measurement of game-thread "sticking". |
| `ark_lab_gns_cost.py` | The cost of packet variants (process CPU via GetProcessTimes) + a rate sweep. Variants: junk, unreliable/reliable/ack/blob, x10/x50 frames, different payloads. |
| `ark_lab_gns_persist.py`, `ark_lab_gns_persist2.py` | An attempt to make connections persistent (a copy of a client's packets) — a negative result, fixed in 16.5. |
| `ark_lab_gns_persist_dos.py` | Mass creation of forged sessions (200 sessions = +42 MB) and observation of live connections. |
| `ark_lab_remote_probe.py` | An external probe: RTT to a remote server's query port (to assess remote impact). |

### 16.8 The decisive control: the data-frame type (a correction to §16.2)

§16.2 compared "GNS + junk" and "GNS + UE4 handshake" and got identical
degradation. That **did not prove** the transport was at fault: both variants
create a `UNetConnection` (the counter grows even with a junk payload — a connection
is created before content validation). The discriminating control is the **SNP frame
type** inside the data packet: an unreliable frame (0x37) reaches UE4 as
stateless-connect and creates a connection; reliable (0x40) and ack (0x90) are
processed only by the transport layer and create no connections.

Local bench, 120 000 packets per variant, 22–27 k pps:

| Data-packet variant | **TPS min** | Connections created | Effect |
|---|---|---|---|
| `unreliable` (0x37, 1 frame) | **2.6** | +120 000 | **degradation** |
| `unreliable-x10` (10 frames of 0x37) | **2.7** | +120 000 | **degradation** |
| `blob` (0x81 + inline protobuf) | **2.7** | +120 000 | **degradation** |
| `mixed` (0x37 + 0x40 + 0x90) | **2.7** | +120 000 | **degradation** |
| `reliable` (0x40, 1 frame) | **21.1** | 0 | **no effect** |
| `reliable-x10` (10 frames of 0x40) | **21.1** | 0 | **no effect** |
| `ack` (0x90) | **21.1** | 0 | **no effect** |

**Outcome: the degradation comes precisely from creating `UNetConnection`, not from
transport processing.** The wording "1 packet = 1 `UNetConnection`" of §14 is confirmed
by a controlled experiment. Practical consequences:

* the cheapest packet for the attacker is a **plain unreliable frame** (1 frame, 18
  bytes of packet): adding 9 more frames to the packet yields nothing
  (there is still one connection, TPS min 2.6 versus 2.7);
* reliable/ack frames are useless for DoS: they create no connections and do not
  degrade the server (they can only be used as "quiet" traffic);
* processing cost (CPU): unreliable 20–25 µs/packet, reliable 20,
  reliable×10 40, ack 28 — i.e. **the most CPU-expensive variant (reliable×10)
  is the least effective**: expensive processing with no connections created.

### 16.9 External-server check: variant ranking impossible

The same run on the external bench `23.109.45.13:25714` (150–200 k packets
per variant, measured by losses on the query port):

| Variant | Query-port losses | RTT max |
|---|---|---|
| unreliable | 19.0 % / 27.8 % | 170 / 143 ms |
| unreliable-x10 | 15.0 % | 178 ms |
| blob | 15.8 % | 174 ms |
| mixed | 15.8 % | 385 ms |
| reliable-x10 (control) | 31.2 % / 26.3 % | 404 / 168 ms |

**The control variant (`reliable-x10`, which locally creates no connections and
does not degrade) shows the same losses as the effective ones** ⇒
on a remote server the signal is completely buried in WAN noise, and variants cannot
be ranked by it. Only the local FPS measurement provides ranking.

Additionally: during all runs against the external server the local bench stayed
unaffected (TPS 21.1–21.7, Δ `packetsReceived` = 0) — confirming all traffic went to
the remote host.

### 16.10 The final statement of the vector (after all controls)

> **One GNS data packet with an unreliable frame (0x37) = one `UNetConnection`
> created by the server.** It is precisely the connection creation (each tick:
> allocation, initialization, registration in the NetDriver list, parsing of
> stateless-connect, destruction) that drops the game-thread FPS: **21.7 → 2.5** at
> ~25 000 pps, the collapse threshold — ~100 000 packets, recovery 15–20 s.
> Transport authentication is absent (a plain `ConnectRequest` without cert is
> accepted), so the attack requires neither a Steam account nor cryptography.
> Defense: network-level (close/rate-limit UDP 7778) — an application-level valve on
> `NotifyAcceptingConnection` is ineffective (rejected connections still cost the server
> allocation and parsing).

### 16.11 "LAN only?" — the degradation threshold on different servers

A user observation: no effect is visible on the external server. Verified with a
stepped test (`ark_lab_remote_threshold.py`) — 100…500 k packets
against the external server `23.109.45.13:25714` (variant `unreliable`, ~19–20 k pps):

| Packets | pps | Seconds | Query-port losses (during the flood) | Losses (baseline, no flood) | RTT max |
|---|---|---|---|---|---|
| 100 000 | 19 436 | 5.1 | **0.0 %** | 0.0 % | 312 ms |
| 200 000 | 20 384 | 9.8 | **0.0 %** | 0.0 % | 96 ms |
| 300 000 | 18 832 | 15.9 | **0.0 %** | 0.0 % | 96 ms |
| 500 000 | 19 708 | 25.4 | **3.4 %** | 0.0 % | 97 ms |

**Answer: the effect is not "LAN only", but its magnitude is determined by the server's
resources.** The local bench collapses at ~80–100 k packets
(TPS 21.7 → 2.5); the external VPS only at ~500 k (and so far only 3.4 % losses
on the query port). A 5–6-fold difference.

**Why the local bench is so sensitive (methodological caveats):**

| Factor | Impact |
|---|---|
| **The server is pinned to 4 cores** (mask `0xF00000`, cores 20–23) on a 24-core host | the server's CPU headroom is minimal; any CPU deficit is immediately visible in the tick |
| **Server1 runs on the same host** (the same manager directory, port 7777) + a Steam client + tooling | the host's CPU and network are shared between two ARK servers and a client |
| **Packets travel a local path** (within one host) | the same rate over a loopback/LAN driver produces a far higher interrupt/softirq load than a real network |
| **The diagnostic NetGuard plugin is on the local server** (hooks on `ReceivedRawPacket` and `NotifyAcceptingConnection` + a capture file) | adds work in the game thread; the capture itself is capped at 4000 packets, the hooks cost a few µs per packet, i.e. a small but non-zero contribution |
| **The attacker is on the same host** | its CPU competes for the same cores; the control test (junk) showed this is not the cause: at the same rate junk gives no effect |

**How this changes the vector assessment (honestly):**

* the mechanism (creating `UNetConnection` on the game thread) is the same on all
  benches, which is also confirmed by the external server starting to lose replies at
  500 k packets;
* **the practical cost of the attack on a typical external server is higher than the
  local bench shows**: 80–100 k packets (~3–5 MB) give no effect on an external VPS;
  ~500 k (~20 MB) and more are needed;
* "a tenfold FPS degradation" is a characteristic of the **local bench**, not a universal
  value; this is noted in the ranking;
* the externally observable effect (query-port losses) requires the whole box to suffer,
  not just the game thread — on a VPS with CPU headroom this does not happen,
  and that is the correct behavior: players suffer an FPS dip, but the server stays
  available.

**What to do next (the next step on the vector):** measure the threshold on
the external server with **multiple sources** simultaneously (an aggregate rate higher
than a single Python thread can produce: one source achieves ~20 k pps)
and check whether the external server recovers as fast as the local one.

> Note: at the time of these measurements the local bench Server2 (with the NetGuard
> plugin) was stopped, so the local measurements for continuing work will need to be
> resumed after its restart.

### 16.12 Can it be more effective and cheaper? — an analysis of levers

Three "cheap attack" hypotheses were tested; all three gave a clear answer.

**Hypothesis A: several UE4 connections in one network packet** (putting N full UE4
"stateless connect" packets into one data packet, each with its own
sequence number, each in its own SNP frame).

| Variant | Network packets | Connections created | Connections per packet |
|---|---|---|---|
| `ue4-62b` (one connect per packet) | 20 000 | 20 000 | 1.00 |
| `ue4-multi4` (4 connects per packet) | 20 000 | 20 000 | 1.00 |
| `ue4-multi10` | 20 000 | 20 000 | 1.00 |
| `ue4-multi20` | 20 000 | 20 000 | 1.00 |

**Refuted.** The UE4 layer processes a datagram as one stream: the first
stateless-connect "eats" the packet; the rest go into it. The ceiling of
"1 network packet = 1 `UNetConnection`" is already reached and cannot be bypassed.

**Hypothesis B: cheap via packet size** — payload size does not affect the
cost (6 B ≈ 64 B ≈ 512 B ≈ 1400 B ≈ 20–24 µs/packet by process CPU).
So a "fat" packet gives no advantage: the attack cost is measured in the **number of
packets**, not bytes. 500 k packets = 9 MB of payload
(~30 MB on the wire) — the attack is uninteresting in bandwidth.

**Hypothesis C: persistent connections** (complete the stateless-connect so the
connection lives up to the 300-s timeout and the server carries it in each tick).
Checked two ways: a copy of a real client's data packets (100 sessions) and
reading the server's replies (otherwise the receive buffer overflows and the server
tears the session itself). Result: `liveConnections` 0–1, memory does not accumulate,
connections live seconds. The reason — the stateless-connect cookie was issued to a real
client and is not bound to our session; to make the connection live, one must
parse the UE4-handshake exchange (server challenge → cookie) and forge it —
a separate task, and even solved, the gain is bounded by memory
(≈210 KB per connection) and NetDriver overhead in the tick, not by
the FPS collapse itself.

**Outcome on efficiency: the vector is already at the practical optimum of "damage per
packet"** (1 packet = 1 connection, the price fixed at ~17 µs of server CPU).
Two real levers remain:

| Lever | What it yields | Cost |
|---|---|---|
| **Rate (multiple sources)** | the collapse begins when the incoming rate exceeds the tick's parsing speed (~25 k pps on the local bench); 4 parallel senders give ~80–100 k pps | ~1.5 MB/s of traffic, 4–10 s of work |
| **Another vector class** | the `ServerCheat` RPC (vector №1) — 1 packet = a server command executed (not DoS but privilege escalation) | 1 packet |
| **Reflection (A2S, x15)** | traffic to third parties impersonating the server | 1 packet → 446 B |

So there is no "cheaper" variant of **this** vector; the economy is either in volume
(by increasing the rate) or in choosing a different impact class
(a command instead of a denial of service).
