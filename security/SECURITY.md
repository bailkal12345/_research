# ARK: Survival Evolved v358 - security research (consolidated)

Merged from the earlier `REPORT_ARK_SE_SECURITY.md` (2026-10-19 survey) and
`ARK_SPECIFIC_VECTORS.md` (game-level analysis). Chronological findings are condensed
below; the curated ARK-specific vector list follows. Git history holds the originals.

Binary: `ShooterGameServer.exe` **v358.24** (Ghidra, program `v358_ShooterGameServer.exe`,
image base `0x140000000`, all addresses image-based RVAs unless written as full VAs).
Short-form addresses (`0x1F3080` etc.) are RVA from `0x140000000`.
Engine reference: UE4.5 sources shipped with the game (`C:\Dev\UnrealEngine-4.5`).

> Stock UE4.5 contains **neither** `ServerCheat_Validate` nor the
> `APlayerController::bIsAdmin` field. Both appear only in the modified ARK engine
> (string literal: `F:\build\LostIsland\Engine\Source\Runtime\Engine\Private\PlayerController.cpp`,
> `RPC_VALIDATE Failed: !S.IsEmpty() && bIsAdmin ... Line: 1781`), so the analyses below
> cover **ARK's own** mechanisms.

Bench: Server2 `C:\asmdata\Servers\Server2` (v358.24) at `192.168.8.218` - game port
7778/UDP, Steam query 27016/UDP, RCON 32331/TCP, beacon 7779 (not open). NetGuard plugin
metrics at `127.0.0.1:27101` (JSON over TCP). External test target: `23.109.45.13`
(game 25714, query 25715). RCON was **not** used as an attack surface (administration only).

---

## Report (previous findings)

Condensed chronological summary. Sources: `C:\Dev\crossplay-research` (PDB DIA cache
`tool-results/symbols-358.txt`, client decompilations `dumps/ShooterGame-client-358.c`,
lines 2532531/3814806 and 3627100-3627138), Ghidra-mcp on the v358 server binary, the
NetGuard plugin on the live bench, and the UE4.5 sources.

### Reused assets (2026-10-19 session; nothing written from scratch)

ServerMonitor (`C:\Dev\ark-bot-research\ServerMonitor`, TPS/tickMs/memory pattern + TCP-JSON
on 127.0.0.1), SrvDiag (`C:\Dev\ARK-Server-Plugins\SrvDiag`, ArkApi hook template:
`PreLogin`, `NotifyControlMessage`, `ExtraPreLoginChecksBeforeWelcomePlayer`), TickProf
(`C:\Dev\ARK-Server-Plugins\TickProf`, server vcxproj template, `x64\Release\ArkApi.lib`),
`rcon.py`/`a2s.py`/`a2s2.py` and `pdbsym.cpp` + `v361.tsv/sqlite` (PDB symbol index,
710k functions) from `C:\Dev\_research`, `game_aquatica.c` + `dump_index.json`
(`C:\Dev\ARK_SE_code_dump`, v361 decompilation, architecture only). New artifacts:
`C:\Dev\ARK-Server-Plugins\NetGuard\` and this lab script directory.

### Network stack

**Game port 7778.** UE4 processing chain (`IpNetDriver.cpp:255-277`): an unknown source
address creates a `UIpConnection` (`ConstructObject`, `InitRemoteConnection`,
`NotifyAcceptedConnection`, `AddClientConnection`) unless `NotifyAcceptingConnection()`
rejects. `UWorld::NotifyAcceptingConnection()` (`World.cpp:3351-3372`) **always returns
Accept** when the server is up and not travelling; there is no player-count check. The
source address is compared **together with the port** (`*TestConnection->RemoteAddr ==
*FromAddr`), so each new source port = a new connection. A half-open connection lives
until `InitialConnectTimeout=300.0` / `ConnectionTimeout=300.0`
(`[/Script/OnlineSubsystemUtils.IpNetDriver]`).

But in ARK the game port is not a raw UE4 socket: it is the listen socket of open-source
GameNetworkingSockets (Steam) in DirectUDP mode (bench log:
`SteamSocketsOpenSource: gethostname failed ()`; the v358 binary contains
`USteamNetDriver`, `FSocketSubsystemSteamOpenSource`; `USteamNetDriver` does not override
`TickDispatch` - it inherits `UIpNetDriver::TickDispatch`). GNS drops junk datagrams
**before UE4 sees them**: measured, 24 000 arbitrary datagrams to 7778 gave
`connectionAttempts = 0`, `packetsReceived = 0` (NetGuard counters). A control replay of a
real UE4 packet was also dropped: D `connectionAttempts` = 0, D `packetsReceived` = 0 -
the transport check in front of UE4 is real. Junk packets do cost CPU: ~20 us/packet
(35 k pps -> 0.9 core, 242 k pps -> 4 cores saturated); cost does not depend on packet
size (64 B and 1400 B cost the same).

**Query port 27016.** No `A2S`/`Source Engine Query`/`GETCHALLENGE` strings in the game
binary (Ghidra `search_strings`, whole image). Strings `P2PADDR`, `CUSTOMSERVERNAME_s`,
`OWNINGID`, `Networking_i` belong to the **client** side (`FillSessionFromServerRules`,
`GetLobbyKeyValuePairsFromSessionInfo`, `FillSessionFromLobbyData`). The port is served by
the Steam server API inside `steamclient64`/GameNetworkingSockets
(`SteamGameServer_Init` with `GameServerQueryPort`) -> invisible to the ArkApi plugin.
Protocol (via `a2s_diag.py`):

| Request | Response |
|---|---|
| `FF FF FF FF 54 "Source Engine Query\0"` | `FF FF FF FF 41 <4-byte challenge>` |
| `FF FF FF FF 56 <challenge>` | `FF FF FF FF 45 <uint16 count=21> key\0value\0 ...` (A2S_RULES) |
| `FF FF FF FF 55 <challenge>` | `FF FF FF FF 44 ...` (A2S_PLAYER; 6 bytes on an empty server) |
| `FF FF FF FF 49 [challenge]` | no response (A2S_INFO not supported here; on the external host A2S_INFO answered 256 B) |

Rules confirm the bench: `CUSTOMSERVERNAME_s = server2 - v358`, `P2PPORT = 7778`,
`NUMOPENPUBCONN = 70`, `SERVERUSESBATTLEYE_b = false`, `OWNINGID = 90295262070632470`
(a later A2S read gave `OWNINGID = 90295266303720470` - both recorded; the server's
SteamID is published in the A2S rules). 21 rules, all ARK-specific: `DAYTIME_s`,
`GAMEMODE_s`, `HASACTIVEMODS_i`, `MODID_l`, `SEARCHKEYWORDS_s`, `SESSIONFLAGS`,
`SESSIONISPVE_i`, `SERVERUSESBATTLEYE_b` ...

**RCON 32331.** `RCONClientConnection::ProcessRCONPacket` `0x140A6CC20` (v358):
case-insensitive password compare (`TChar<wchar_t>::ToLower` per character); wrong
password -> `id = -1`, `IsClosed = true`, connection closes; **no** failed-attempt
counter, no delay, no blocking; an authorized command goes into `UShooterCheatManager`
(vtable+0x1F8) - executed **on the game thread**, so a command responds no faster than the
30 Hz tick quantum: measured 33.0-34.6 ms for an empty command. **Active testing excluded
by the client's request.**

**Surface map:**

| Surface | Port | Implementation | Who processes it | Externally observable |
|---|---|---|---|---|
| Steam query / A2S | 27016/UDP | Steam server API in `steamclient64` | not UE4, invisible to the plugin | 446 B per 30-B request (x15) |
| Source RCON | 32331/TCP | `URCONServer` in the game binary | game thread | ~33 ms response (tick quantum) |
| UE4 game protocol | 7778/UDP | GNS -> `UIpNetDriver::TickDispatch` | game thread, only after a valid handshake | without a handshake: 0 connection attempts |
| Beacon | 7779 | `NAME_BeaconNetDriver` exists in the binary | port not open | - |
| Chat / RPC | 7778 | `AShooterPlayerController::ServerSendChatMessage` | game thread | only after login; ArkApi built-in 1 msg/s filter |
| EOS/Steam sessions | - | client sessions (matchmaking) | Steam/EOS | the server does not host sessions |

### Baseline measurements (NetGuard; TCP 127.0.0.1:27101; CPU from the server PID)

**Junk datagrams on 7778 (pre-GNS, early passes):** background ~13% CPU, tickMs 33.0,
TPS 30.1, 2491 MB. Volleys 1 000 / 3 000 / 6 000 / 10 000 / 15 000 packets at ~4 000-4 392
pps: no change (30.0-30.1 TPS; 6 000 min 25.2). 24 000 @ 6 772 pps: CPU **23.7%**, tick 33.5,
TPS 30.1, memory unchanged. 30 000 @ 3 443 pps: 30.1 (min 26.4). Repeat 24 000 x3 @4 000 pps:
CPU 19.9 / 10.5 / 13.4%, tickMs 32.9 -> **47.9 -> 47.1**, TPS 30.1 -> **20.7 -> 21.3**.

Key point: the dip is **reproducible** and **does not release quickly** - 400 s after the
last volley the tick was still 47 ms vs 33 (TPS 21.1 vs 30.1), while memory grew slowly
(2491 -> 2559 MB, +68 MB) - state accumulates on the Steam-layer side (per the upstream
sources). Recovery curves: after the 24 000 x3 series (20 s sampling): t=0 22.4 TPS
45.6 ms, t=60 22.1 / 46.4, t=140 21.3 / 80.1 ms (a single 80 ms tick "freeze"), t=200 21.6
/ 44.6, t=300 21.9 / 46.8, t=400 21.1 / 47.1, mem 2491 -> 2499 MB. One 24 000 volley
(`out/recovery3.txt`): t=0 21.5 / 46.7 (degraded), t=40 22.7 / 34.3 (recovery begins),
t=60 29.9 / 34.4, t=80 30.1 / 32.7 (normal), t=120 30.0 / 34.2, mem 2489 -> 2492 MB.
Outcome: degradation is directly proportional to the Steam-layer state - one 24k volley
recovers in ~40-60 s, three volleys hold >400 s (later restored to 30 FPS on the same
process); a process restart restores instantly. Cost per packet: about +11 ms/tick for
24 000 packets ~ 0.5 us of game-thread time per packet (~2 000 packets per 1 ms of tick,
~50 000 packets to halve the FPS).

**Query port 27016:** 4 000 @ 20 pps (client throttled by the 50 ms latency): 34.2->34.1
tickMs, TPS 29.6->29.3, within noise. 20 000 @ 4 795 pps: 34.5->33.2 tickMs, TPS 30.1->30.1
(min 29.3) - **no effect**. Fixed response delay ~50 ms per request (median 49.5 ms on one
thread), 100% response rate. Amplification: a 446 B reply to a 30 B request = **x15**
(the server as a reflector); ~26 us CPU per request. The advertised `NUMOPENPUBCONN=70`
is static; the real gate is `AtCapacity()`.

**Vector inventory (V1-V7), measured on the bench:**

| # | Port/protocol | Essence | Impact | Complexity | Defense |
|---|---|---|---|---|---|
| V1 | 7778/UDP game port | storm of junk datagrams from different source ports | +11 ms/tick per 24k packets, TPS 30->21, CPU 13->24%; recovers on its own (one 24k volley ~40-60 s; three volleys >400 s, `out/recovery3.txt`), memory +68 MB | low | network filter (WFP/firewall) on 7778; **cannot be fixed in-process** - packets never reach UE4 |
| V2 | 7778/UDP | GNS transport forgery (SteamNetworkingSockets session, 3 packets, **no Steam account and no crypto**) + data packets with an unreliable frame | **fully implemented**: 1 data packet = 1 `UNetConnection` (control by frame type, below). Local bench: ~25 000 pps -> **TPS 21.7 -> 2.5**, collapse threshold ~100k packets, recovery 15-20 s. **External VPS: effect only from ~500k packets** (100-300k: none) -> magnitude set by the server's CPU headroom. ~10x cheaper than a junk flood | low (plain UDP) | **firewall/rate limit on 7778**; a valve on `NotifyAcceptingConnection` **does not help** (all attempts rejected, FPS still fell) |
| V3 | 27016/UDP | A2S request flood | at 4 800 pps: **no** effect; 446 B per 30 B = **x15 amplification** (reflection) | low | OS-level limit (WFP/firewall) or do not publish the query port |
| V4 | 32331/TCP RCON | password brute force + command execution on the game thread | **active testing excluded by the client's request**; statically: case-insensitive compare, no counter/blocking, commands run on the game thread | medium | do not expose RCON (`RCONEnabled=False`); NetGuard per-IP limits + attempt counter |
| V5 | 7778/UDP | login forgery (PreLogin on the game thread) | load on authorization | medium | NetGuard per-IP login limit + temporary ban |
| V6 | 27016/UDP | spoofed victim IP in an A2S request | x15 amplification, response from the server IP | low | do not publish the query port; edge filtering |
| V7 | 7778/UDP GNS handshake | forging stage 1 (ChallengeRequest) and stage 2 (ConnectRequest) without a Steam certificate | server **answers anyone**: 1999/2000 `ChallengeReply` at 10 252 pps; `ConnectRequest` without cert accepted (`ConnectOK`), creates a GNS connection (~13 KB, +23 KB working set), closes with reason 5002; **limit 1 connection per (IP:port)**; reflection: `ConnectOK` + `ConnectionClosed` (512 B) + a GNS datagram stream; CPU: 11 610 pps -> TPS 21.8->21.4 | low (plain UDP, no account) | close 7778 outward; `IP_AllowWithoutAuth=0`, `AllowRemoteUnsignedCert=deny`; monitor `ConnectOK`/`ConnectionClosed(5002)` |

Signals on RCON snapshots: password comparison findable in `ProcessRCONPacket`; the
`net.MaxPlayersOverride` route (see "Slots" below) pushes V6 to "all logins rejected" with
one command.

### Slots: "Server full." and fake connections

From UE4.5 sources shipped with the game (`GameSession.cpp:118-121` ApproveLogin:
`AtCapacity(SpectatorOnly == 1)` -> `NSLOCTEXT("NetworkErrors", "ServerAtCapacity",
"Server full.")`; `GameSession.cpp:198-203` AtCapacity:
`MaxPlayersToUse = CVarMaxPlayersOverride.GetValueOnGameThread() > 0 ? override : MaxPlayers;
return (MaxPlayersToUse>0) && GetWorld()->GetAuthGameMode()->GetNumPlayers() >= MaxPlayersToUse`).
Call points in ARK v358 (Ghidra, xrefs by the `"Server full."` string):
`AShooterGameSession::ApproveLogin` `0x140CE1100` (returns the text), `UWorld::NotifyControlMessage`
`0x142621440` (sends it to the client), the string is at `0x143C29BE8`.

`GetNumPlayers()` counts **logged-in players** (`GameState->PlayerArray`), not sockets.
`UNetDriver::ClientConnections` does not participate in the capacity check -> a half-open
connection does not take a slot and "Server full." is not shown to others. To get
"Server full." you need a **real login** (a valid Steam/EOS token) or RCON.
`net.MaxPlayersOverride` (engine CVar, `GameSession.cpp:14`, "If greater than 0, will
override the standard max players count. Useful for testing full servers."): set from
RCON to `1`, `AtCapacity()` becomes true at any player count. Verified on the bench: the
command executes, but the advertised `NUMOPENPUBCONN = 70` does not change (it affects the
login gate only). The value **is not reset** by a map change - only by a restart or
`net.MaxPlayersOverride 0`.

Detailed v358 dissection (`AGameSession::AtCapacity` `0x14241BEA0`, 782 B):

```c
bool AGameSession::AtCapacity(bool bSpectator, FString* AuthToken, UNetConnection* Connection)
{
    if (bSpectator) return MaxSpectators <= GameMode->NumSpectators;
    int MaxPlayersToUse = this->MaxPlayers;
    if (IOnlineSession::Get(...)) session->vtable[0x118](session, AuthToken);
    FString MyAddr = Connection->LowLevelGetRemoteAddress();
    int numFromIp = 0, welcomed = 0, total = 0;
    for (i = 0; i < NetDriver->ClientConnections.Num(); ++i) {
        UNetConnection* c = ClientConnections[i];
        if (c && c->Driver && c != Connection) {
            if (StrCmpNoCase(c->LowLevelGetRemoteAddress(), MyAddr) == 0) ++numFromIp;
            if (0 < total + 1 && total + 1 <= numFromIp) return true;   // IP rule
            if (c->PlayerId != NULL && c->bWelcomed) ++welcomed;
        }
        ++total;
    }
    if (MaxPlayersToUse < 1 || welcomed < MaxPlayersToUse) return false;
    return true;
}
```

Counter meanings: `numFromIp` = connections (incl. half-open) from the joiner's IP;
`welcomed` = connections with `PlayerId != NULL && bWelcomed`; slot limit =
`AGameMode::GetNumPlayers()` = `NumTravellingPlayers + NumPlayers` (ARK's own counters).

| Scenario | Verdict | Why |
|---|---|---|
| A "dead" connection (transport exists, login doesn't) takes a slot | **No** | appears in neither `numFromIp` (IP comparison protects the other way), nor `welcomed` (needs `PlayerId`+`bWelcomed`), nor the player counter |
| "Welcomed" connections take a slot | formally yes (`welcomed >= MaxPlayers`), **but inert**: `bWelcomed` is bit 1 of a uint32 at 0xDC and the Welcome path (`UWorld::NotifyControlMessage`, 1572 instructions) contains **not a single write** of it; bit = 0 on a live logged-in connection (measured) | `bWelcomed` would also be needed |
| Mass connections from one IP to cut off logins | **Yes, but only against yourself and NAT neighbors**: if connections from my IP outnumber server players + 1, login is rejected as "Server full." | the `total+1 <= numFromIp` rule |
| Fill every seat with fake connections so **others** cannot join | **NO**; requires 70 **real logins** (70 accounts) or one RCON `net.MaxPlayersOverride 1` | only counters are `GetNumPlayers()` and `welcomed` (non-functional) |

The login gate can block **by account**: the "already a player with this account
connected" check compares **PlayerId (SteamID)**, not connection count - a hanging
connection with the right SteamID blocks login for **that** account (a targeted kick, not
a DoS). The rejection list in `ExtraPreLoginChecksBeforeWelcomePlayer` (`0xC50930`):
`"PreLogin: Invalid login provided."` (no Steam session), `"Rejected connection because
Login Logk Release is pending."` (LoginLock release pending), `"PreLogin: Waiting on
Login Lock. Please try again in a minute."` (Redis-held LoginLock), `"Rejected connection
because there is already a player with this account connected."` /
`"PreLogin: There is already a player with this account connected!"` (same PlayerId),
`"IP for incoming account %s - IP %s"` (account<->IP log). With `PlayerId == NULL`,
`AShooterGameMode::PreLogin` (`0x140C502C0`) rejects with `"A valid login was not
provided." / "PreLogin: Invalid login provided."` - pure protocol emulation can only hang
at the transport level. Protection is fragile by itself: if Redis is unreachable -
`Disabled LoginLock due to loss of redis connection`; on benches/cheap hosts the whole
mechanism may be absent (`bHasArkLoginLock` disabled).

### NetGuard plugin (developed, built, installed)

`C:\Dev\ARK-Server-Plugins\NetGuard\` -> `build\Release\NetGuard.dll` ->
`C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\`.

Measurement (always on), TCP `127.0.0.1:27101`, JSON per command: `tps`, `tickMs`,
`tickMsMax`, `memKB`, `uptimeSec`, `liveConnections`, `connectionAttempts`,
`connectionsRejected`, `packetsReceived`, `bytesReceived`, `controlMessages`, `logins`,
`newConnsPerSec`, per-IP attempt counts, plus slot metrics `players`
(`AGameMode::GetNumPlayers`), `maxPlayers` (`AGameSession.MaxPlayers`), `atCapacity`
(engine-rule replica), and later `totalConnections`/`deadConnections`
(connections not in Open state or without a PlayerId), `welcomedConnections`
(`bWelcomed=1`), `slotHoggers` (welcomed with a PlayerId), `maxConnectionsPerIp`.
Commands: `status`, `ping`, `reset`, `config`, `defense on|off`, and later
`adminforce on|off`, `cheatprobe`.

Defense (config-driven, off by default, toggleable on the fly):
- rate valve: new connections per second above `newConnectionsPerSecondLimit=50` ->
  `UWorld::NotifyAcceptingConnection` returns Reject, connection never created;
- `maxLiveConnections` ceiling;
- `maxDeadConnections`: extra "dead" connections closed right in the tick
  (`UNetConnection::Close`) - the countermeasure against CPU exhaustion via dead
  connections;
- per-IP login attempt limit (`loginsPerIpPerMinuteLimit=10`) + temporary IP ban
  (`blockSeconds=300`) at the `ExtraPreLoginChecksBeforeWelcomePlayer` gate;
- `blockServerCheat`: hooks `ABasePlayerController.ServerCheat_Validate` -> always
  `false` (the RPC is dropped, `GLastRPCFailedReason = "ServerCheat_Validate"`).

Hooks (5 attached on the bench): `UWorld.NotifyAcceptingConnection`,
`UNetConnection.ReceivedRawPacket`, `UWorld.NotifyControlMessage`,
`AShooterGameMode.PreLogin`, `AShooterGameMode.ExtraPreLoginChecksBeforeWelcomePlayer`.

Hot reload: `plugins.unload NetGuard` -> copy DLL -> `plugins.load NetGuard`. Found
experimentally: ArkApi keeps hooks in a global map and **does not remove them on unload**;
if `Plugin_Unload` does not call `ArkApi::GetHooks().DisableHook(name, detour)` for each
hook, detours survive `FreeLibrary` and the next load fails ("Failed to attach hook
for ...") and crashes the server. Second pitfall: `ArkApi::GetAddress()` returns 0 for
symbols missing from PDB v358 (`UIpNetDriver.StaticClass`, `UObject.Class`) - a call
through such an address kills the game thread (verified crash); the plugin has
`SafeStaticClass()` with an address check and an SEH-wrapped `OnTick`.

Config `.../NetGuard.json`: `{"enabled": true, "tcpEnabled": true, "tcpPort": 27101,
"bindAddress": "127.0.0.1", "statusIntervalSeconds": 1.0, "defenseEnabled": false,
"newConnectionsPerSecondLimit": 50, "maxLiveConnections": 0,
"loginsPerIpPerMinuteLimit": 10, "blockSeconds": 300}`.

Note: the plugin's `players` counter reads ARK's `GetNumPlayers()`; on the bench it shows
0 with one logged-in player (the player in spawn state) - ARK appears to increment not at
login but at full entry into the world; verifying needs client-side PostLogin
observation. An empirical test that "70 fake players displace everyone else" needs 70
real Steam accounts - not deployed.

### Early ranking (final measurements, defense off; FPS method with 5-s window)

Sender processes pinned to cores 0-19 (the server is pinned to 4 cores, mask
`0xF00000` = cores 20-23, on a 24-core host); offered load read from "UDP Datagrams
Received"; control: the same load against a non-listening port 7779 (noise floor
26.5 FPS).

| Rank | Vector | Load | FPS (before -> after) | Tick | CPU | Verdict |
|---|---|---|---|---|---|---|
| 1 | V1 junk UDP flood on 7778, 12-20 sources | **242 k pps (20 src ~ up to ~700 k)** | **30 -> 1.5-2.4 (min 0.9)** | 33 -> 428 ms | 4 cores saturated | the only vector dropping FPS to 2-3 |
| 2 | the same, 6 sources | ~210 k pps | 30 -> 24.6 | 34 ms | ~4 cores | the knee where the effect begins |
| 3 | the same, 1 source | ~35 k pps | 30 -> 29.5 | 33 ms | 0.9 core | only CPU burn, FPS intact |
| 4 | V3 Steam query flood 27016 (A2S_RULES) | 41 k datagrams/s | 30.0 -> 30.0 | 33 ms | +0.5 core | FPS unaffected; value = x15 reflection |
| 5 | V6 `net.MaxPlayersOverride 1` via RCON | 1 command | all logins rejected ("Server full.") | - | - | not a packet vector; close RCON |
| 6 | V5/V2 fake logins / handshake replay | needs a real client | - | - | - | out of reach without a client |
| - | V4 RCON | - | - | - | - | testing excluded by request |

Mechanism: junk costs ~20 us CPU each without creating anything; once the 4-core budget
is exhausted the game thread starves -> tick 33 -> 200-600 ms -> FPS 30 -> 0.9-2.4;
memory stays flat (2504 -> 2510 MB) - pure CPU starvation, not a leak. Defense
validation: the NetGuard valve does **not help** (FPS 1.4 under load; junk is dropped by
the Steam layer before the `NotifyAcceptingConnection` hook); connection caps not
applicable (no connections created); a network filter on 7778 **works by construction**
(control: the same load on port 7779 gives zero drop; noise floor 26.5 FPS). Server
outbound traffic (A2S x15) is the second lever.

Recommended rules (verified pattern; block-any overrides allow, so order matters):

```text
netsh advfirewall firewall add rule name="ARK 7778 allow" dir=in action=allow protocol=UDP localport=7778 remoteip=<ADMIN_IP> profile=any
netsh advfirewall firewall add rule name="ARK 7778 deny"  dir=in action=block protocol=UDP localport=7778 profile=any
netsh advfirewall firewall add rule name="ARK 27016 deny" dir=in action=block protocol=UDP localport=27016 profile=any
netsh advfirewall firewall add rule name="ARK 32331 deny" dir=in action=block protocol=TCP localport=32331 profile=any
# gateway (per-source rate limit):
iptables -A INPUT -p udp --dport 7778 -m hashlimit --hashlimit-above 2000/s --hashlimit-mode srcip --hashlimit-name ark77 -j DROP
# nft: nft add rule inet filter input udp dport 7778 meter ark77 { ip saddr limit rate 2000/second } drop
```

Notes from the bench: Windows Firewall had blocked inbound UDP (results invalid while it
was disabled wholesale); the right fix is allowlist rules, not firewall disabling.
Measuring V2/V7 persistence requires the production server's
`InitialConnectTimeout`/`ConnectionTimeout` (300 s on the bench).

### L7 surfaces and probes

Probed with `ark_lab_l7_probe.py` (mem/TPS taken before/after each burst):

| Test | Expected | Fact |
|---|---|---|
| RCON: length prefix 65536, no body | 64 KB allocation | mem 2489->2489 MB, tps 30.0 |
| RCON: length 67108864 (64 MB) | 64 MB allocation | mem unchanged, tps 30.0 |
| RCON: length 536870912 (512 MB) | 512 MB allocation | mem unchanged, tps 29.9 |
| RCON: correct length, 1 MB body | parse load | mem unchanged, tps 30.0 |
| A2S: datagrams 4/32/60 KB | memory overuse | mem unchanged, tps ~29.7 |
| A2S: A2S_RULES with count=0xFFFF | hang / parse error | no answer, server alive |
| A2S: A2S_PLAYER with count=0xFF | same | no answer |
| A2S: A2S_INFO + 60 KB tail | overflow | no answer |

Conclusion: in build 358.24 the RCON/A2S parsers are **written carefully** - RCON packet
length does not drive the allocation, junk in A2S fields is dropped silently. The
exploitable L7 vectors are in **authorization** (RCON without blocking) and
**amplification** (A2S x15), not parsing. Residual risks (not probed, need a client):
after a handshake, `NMT_Login` -> `ApproveLogin` -> "Server full." (the most expensive
L3-L7 path under a stream of half-logins: Steam/EOS token validation, session lookup,
`FCurrentLoginAuthCheck`, all on the game thread); chat (1 msg/s/player - 70 msg/s on the
game thread at 70 players); post-handshake amplification (welcome/NetGUID/map data sent
by the server - needs a real client, not quantified).

### GNS transport dissection (port 7778)

`GameNetworkingSockets.dll` (438 KB) in the server directory is built from the ARK engine
sources (assert paths like `H:\AtlasTrunk\Engine\Source\ThirdParty\GameNetworkingSockets\src\steamnetworkingsockets\clientlib\steamnetworkingsockets_udp.cpp`)
and matches public upstream `ValveSoftware/GameNetworkingSockets` - server behavior can be
checked against the public source. It implements the **server** side (strings
`k_ESteamNetworkingUDPMsg_*`, `CMsgSteamSockets_UDP_*`, `cbEncrypted`,
`SteamNetworkingSockets_Assert`). No AES/SHA/HMAC/curve25519 string markers - but in
open-source GNS the crypto is `crypto_25519_donna` and `crypto_sha1_wpa` with no string
markers; CA/Steam-side secrets come from `steamclient64.dll` (12 MB). Inbound dispatcher:
Ghidra `FUN_180024E00` (RVA 0x24E00) = upstream
`CSteamNetworkListenSocketDirectUDP::ReceivedFromUnknownHost`.

Message format (recovered byte by byte):

| Message | Code | Frame / protobuf fields |
|---|---|---|
| ChallengeRequest | 0x20 | `[0x20][u16 LE len][pb][pad->512]` - field 1 `connection_id` (f32), 3 `my_timestamp` (f64), 4 `protocol_version` (u32) |
| ChallengeReply | 0x21 | `[0x21][pb]` - 1 `connection_id`, 2 `challenge` (f64), 3 `your_timestamp`, 4 `protocol_version` |
| ConnectRequest | 0x22 | `[0x22][pb]` (no length/padding) - 1 `client_connection_id`, 2 `challenge`, 3 `legacy_client_steam_id`, 4 `cert`, 5 `my_timestamp`, 6 `ping_est_ms`, 7 `crypt`, 8 `legacy_protocol_version`, 9 `legacy_identity_binary`, 10 `identity_string` |
| ConnectOK | 0x23 | `[0x23][pb]` - 1 `client_connection_id`, 5 `server_connection_id`, 3 `your_timestamp`, 4 `delay_time_usec`, 7 `crypt`, 8 `cert` |
| ConnectionClosed | 0x24 | `[0x24][u16 len][pb][pad->512]` - 3 `reason_code`, 5 `to_connection_id` |
| NoConnection | 0x25 | `[0x25][pb]` - - |
| Data | 0x80 or flags | `[0x80][u32 to_connection_id][u16 seq][payload]` - the 7 B `UDPDataMsgHdr`; SNP frame `[0x37][u32 msg_num][data]` where data = UE4 packet bytes **verbatim** |

Padding matters: upstream `k_cbSteamNetworkingMinPaddedPacketSize = 512`; a smaller
packet gets `"Packet is %d bytes, must be padded to at least 512 bytes"` and is silently
dropped (this was why the first probes failed).

What the server checks (upstream `Received_ChallengeRequest` /
`Received_ConnectRequest` / `RecvCryptoHandshake`): challenge =
`GenerateChallenge(nTime, adrFrom)` = `SipHash(nTime, port, IP) | nTime` with random
`m_argbChallengeSecret`, `GetChallengeTime(usecNow) = usecNow >> 20` (~1.05 s); the
server issues the challenge itself, so it is **not a cryptographic barrier** - replay it
from the same address (it lives ~4 s). ConnectRequest checks: challenge match
(`"Incorrect challenge. Could be spoofed."`), `client_connection_id != 0`
(`"Missing connection ID"`), identity = cert -> legacy fields -> otherwise
"localhost" (anonymous); anonymous denied only if `GetIPAllowWithoutAuth` is 0
(`"Unauthenticated connections not allowed."`); dedup
`m_mapChildConnections[(identity, client_connection_id)]` ->
`"A connection with that ID already exists."`. `RecvCryptoHandshake`: without
`msgCert.has_cert()` or `msgSessionInfo.has_info()` -> `k_ESteamNetConnectionEnd_Remote_BadCrypt`.

Bench measurements (192.168.8.218:7778):

| Experiment | Result |
|---|---|
| 2000 ChallengeRequests (512 B, 10 252 pps) | **1999 replies**; working set delta = **0** - no state created |
| 1 ConnectRequest without cert | **ConnectOK** (26 B) - anonymous connection accepted, connection object `operator_new(0x33e8)` ~ 13 KB (Ghidra `FUN_1800253A0`); then `ConnectionClosed` `reason_code = 5002` ("Crypto handshake missing cert or session data") |
| Server working set | +23 KB per connection (20 connections -> +460 KB) |
| Connection limit | **1 concurrent GNS connection per (IP:port)**: 10 ports -> 10 ConnectOKs; 400 ports -> 400 of 4000 requests; 1 port -> 1 (rest silently dropped) |
| CPU cost | 11 610 ConnectRequests/s -> TPS **21.8 -> 21.4** (no impact); junk flooding the same port needed ~242 000 pps |
| Reflection | 4000 requests -> 400 ConnectOK + 400 ConnectionClosed (512 B) + **22 632 GNS data packets** (statistics/ack); the junk path gives no reflection at all |
| Global map | code check `g_mapConnections.Count() >= 0x1fff` |

The earlier "cert needed" hypothesis turned out **wrong**: intercepting a real client
through the UDP relay `127.0.0.2:7778` (`ark_lab_gns_relay.py`) showed the ARK client
sends `ConnectRequest` (41 B) **without `cert` and without `crypt`** - the server accepts
it. Intercept analysis tools: `ark_lab_gns_analyze.py` (message types, ChallengeReply,
ConnectRequest cert/crypt, ConnectOK, ConnectionClosed), `ark_lab_gns_datapkt.py`
(`UDPDataMsgHdr`, `to_connection_id`, packet numbers, size distribution), and
`ark_lab_gns_align.py` (GNS payload <-> UE4 packet layer alignment) recovered the framing.
`ark_lab_handshake_capture.py` - early capture relay; `ark_lab_sniff_gns.py` - raw UDP
sniffer (`SIO_RCVALL`, **requires administrator rights**).

### Main vector implemented: GNS session spoofing -> data-packet flood

Attack frame - **3 packets per session, no account, no crypto**:

```text
[0x20][u16 len][protobuf][pad->512]   ChallengeRequest  ->  [0x21] ChallengeReply
[0x22][protobuf]                      ConnectRequest    ->  [0x23] ConnectOK
[0x80][u32 conn_id][u16 seq][0x37][u32 msg][UE4 bytes]   data packets (as many as needed)
```

How the constraints were removed: relay intercept (no cert needed); the challenge is
server-issued; the data-packet structure came from decompiling `FUN_180018BA0` (the
SNP-frame decoder) plus aligning intercepted packets with the UE4 capture; the UE4 layer
accepts "whoever's packets arrive inside the spoofed session" - the server creates a
`UNetConnection` for **every** spoofed data packet.

Impact (Server2 bench):

| Experiment | Result |
|---|---|
| 2 000 spoofed packets | **2 000 `UNetConnection`s** created (24 256/s), TPS unchanged |
| 10 000 pps x 15 s | 150 000 connections, **TPS 21.7 - no effect** |
| 20 000 pps (steady) x 12 s | 240 000 connections, TPS dipped to 15.4, recovered to ~20 |
| **~21 000 pps (burst) x 9 s** | **200 000 connections; TPS 21.1 -> 17.3 (3 s) -> 2.2 (4 s), holds at 2.0** - a 10-fold drop |
| After the flood stops | TPS recovers within 15-20 s (18.0 -> 21.7) |
| Server memory / log | stable (+2 MB per 200 000 connections: objects freed) / 0 B growth |
| vs the junk flood | junk needed ~242 000 pps, spoofing ~21 000 pps - **~10x cheaper**, and the packets look like legitimate GNS traffic |

Pre-check in the main amplifier (`ark_lab_gns_amp.py`, self-contained, stdlib only): A2S
ping of the query port + the game port's response to a `ChallengeRequest` + metrics
plugin availability; refuses to run (exit code 3) if the game port does not answer.
Sample check output: query port ANSWERED 9 B `....A....`; game port ANSWERED,
challenge=0x693193fec5e4e8f4, protocol V5; metrics available (pid=18564, tps=21.5,
uptime=10493). Sample attack output (`--count 200000`): "our address: 0.0.0.0:63952",
"GNS connection forged, server_connection_id=0x2ff0a4cc"; connAttempts 200000 -> 240000
(+40000 = 24596 connections/s), tps 21.5 throughout. The check can be bypassed with
`--skip-check`. (Turning the vector into
persistent connections failed - see "Refinement" below, negative result.)

**External verification** (`23.109.45.13`, game 25714, query 25715, found by scanning:
A2S_INFO 256 B, `pxHosting Ark Server - 2 (v358.24)`, map `TheIsland` - same build
v358.24): pre-check passed (A2S 256 B; game port issued a challenge, protocol V5; metrics
plugin local-only); spoofed session accepted - `ConnectOK`, `server_connection_id =
0x6be706e1`, **no account**; 200 000 packets @ 24 012 pps and 300 000 @ 22 808 pps sent
to the external game port; the local bench stayed unaffected (Delta `packetsReceived` =
0, Delta `connectionAttempts` = 0, TPS 21.7). Remote impact (no plugin there; measured
indirectly via query-port RTT, `ark_lab_remote_probe.py`, 0.2 s interval):

| Condition | Replies | Loss | RTT median | RTT max |
|---|---|---|---|---|
| Control (40 s, no attack) | 96 / 99 | 3% | 146 ms | 186 ms |
| Before the attack (0-10 s) | 26 / 26 | 0% | 157 ms | 447 ms |
| **During the attack (300k packets)** | **5 / 10** | **50%** | 174 ms | 368 ms |
| After the attack (24+ s) | 42 / 42 | 0% | 190 ms | 395 ms |

During the attack the remote server loses half the query-port replies and recovers when
the flood stops; on the WAN, RTT of 140-200 ms masks the tick change (locally the drop
showed as TPS 21.7 -> 2.5). The vector needs nothing but access to the UDP game port and
works "out of the box" against a public ARK server. Attack complexity: low - plain UDP,
3 packets per session, no cryptography, no accounts; a few dozen lines of Python.
Impact: 10x TPS degradation (21 -> 2) at ~21 000 pps (~1.5 MB/s of traffic); recovery
15-20 s after stop. Not "an ARK vulnerability" but the consequence of a publicly
reachable game port without transport authentication.

### Scene ranking (`ark_lab_suite.py --all --seconds 12 --json out/suite.json`)

Methodology: each scenario 12 s, between scenarios the server fully recovers (20 s
pauses); `tps` updates on the game tick so it **lags** under heavy degradation - the
damage shows in the measurement **after** the flood; `connectionAttempts` counts created
`UNetConnection`s. **Power** = (TPS_before - TPS_min) / TPS_before with TPS_min = the
minimum of three measurements (during the flood, right after, +5 s).

| # | Vector | Packets | pps | TPS before | TPS min | TPS after | **Power** | Connections |
|---|---|---|---|---|---|---|---|---|
| **1** | **S4 - GNS session spoofing + UE4 packet injection** | 254 000 | 25 221 | 21.1 | **2.5** | 19.8 | **88%** | **+254 000** |
| 2 | S2 - GNS `ChallengeRequest` flood | 174 400 | 17 392 | 21.5 | 21.0 | 21.2 | 2% | 0 (no state) |
| 3 | S1 - junk datagrams on 7778 | 432 000 | 43 103 | 21.4 | 21.0 | 21.2 | 2% | 0 |
| 4 | S3 - GNS `ConnectRequest` flood (anonymous connections) | 139 024 | 13 864 | 21.1 | 20.8 | 21.1 | 1% | 0 (1-per-IP:port limit) |
| 5 | S5 - Steam query flood on 27016 (x15 reflection) | 428 000 | 42 794 | 21.1 | 21.0 | 21.0 | 0% | 0 |

"The only vector with real power is S4 (98%)" - the text elsewhere says the table's 88%;
both recorded. All other vectors inside the measurable bench limits (12 s, up to
~50 000 pps) give 0-5%. S4 is cheapest per unit of damage: ~80 000 packets (~1.5 MB/s)
drop the server from 21 to 14 TPS; a continuous 26 000 pps stream to 0.4-2.0 TPS; the
junk flood needed ~242 000 pps (**3-10x more expensive**) and creates no connections.
Stepped measurement of S4 (`--stepped --burst 20000 --duration 60`, volleys 1.2 s apart):

| Packets sent | TPS after the volley |
|---|---|
| 20 000 | 21.1 |
| 40 000 | 20.8 |
| 60 000 | 20.5 |
| 80 000 | 20.2 |
| **100 000** | **2.8** <- the collapse (TPS falls 7x) |
| 140 000 | 2.5 |
| 200 000 | 2.6 |

The cost threshold: **100 000 packets** (~3 MB of traffic, 4 s at 25 000 pps) - after it,
TPS 21 -> 2.5 (stepped mode confirmation: 80 000 -> TPS 19.5, 100 000 -> 13.7).

### Refinement: honest attribution, per-packet cost, controls

Methodology corrections: two independent signals (plugin TPS/tickMs **and** A2S RTT - RTT
is served on a separate thread and shows "server availability", not game-thread health);
a dedicated socket for the sampler (sharing a socket with the main thread interleaved the
plugin's sequential replies and produced garbage values); waiting for recovery before
each scenario (until TPS >= 19); server process CPU via `GetProcessTimes`
(independent of the plugin).

Control scenarios (200 000 packets each, local bench): C0 idle 21.4 -> 21.0 (tickMs 48.5,
A2S RTT max 63.8 ms, 0 connections); C1 junk 21.6 -> **21.3** (46.8, 62.9 ms, 0); C2 GNS
session + **junk** payload 21.4 -> **0.0** (45.9, 63.2 ms, 0*); C3 GNS + **UE4
handshake** 21.7 -> **0.0** (47.0, 62.4 ms, +200 000). (*) In a separate measurement the
connection counter grew even with the junk payload pattern - **a connection is created
regardless of payload validity** (before content inspection), which is why C2 vs C3 does
not decide the mechanism. The discriminating control is the SNP-frame type (below).

Per-packet CPU cost (process CPU, us/packet):

| Variant | us/packet | Connections | Comment |
|---|---|---|---|
| junk 64 B on 7778 | **10.6** | 0 | baseline receive-and-drop |
| GNS data, 1 unreliable frame, payload 6/64/512/1400 B | 20-24 | +1 per packet | **payload size does not matter** |
| GNS data, 1 reliable frame (0x40) | 20.1 | +2 252 | the reliable path |
| GNS data, 10 unreliable frames | 29.1 | +1 per packet | |
| **GNS data, 10 reliable frames (0x40)** | **39.8** | +5 | **the most expensive variant** (3.8x junk) |
| GNS ack frame (0x90) | 28.3 | 0 | server updates counters |
| GNS data with the blob flag (0x81) | 22.6 | 0 | |

Decisive control by data-frame type (120 000 packets per variant, 22-27k pps):

| Data-packet variant | **TPS min** | Connections | Effect |
|---|---|---|---|
| `unreliable` (0x37, 1 frame) | **2.6** | +120 000 | **degradation** |
| `unreliable-x10` (10x 0x37) | **2.7** | +120 000 | **degradation** |
| `blob` (0x81 + inline protobuf) | **2.7** | +120 000 | **degradation** |
| `mixed` (0x37 + 0x40 + 0x90) | **2.7** | +120 000 | **degradation** |
| `reliable` (0x40, 1 frame) | **21.1** | 0 | **no effect** |
| `reliable-x10` (10x 0x40) | **21.1** | 0 | **no effect** (most CPU-expensive, least effective) |
| `ack` (0x90) | **21.1** | 0 | **no effect** |

**Final formulation:** one GNS data packet with an unreliable frame (0x37) = one
`UNetConnection` created by the server (an unreliable frame reaches UE4 as a
stateless-connect; reliable/ack frames are handled by the transport only). It is the
connection creation per tick (allocation, initialization, registration in the NetDriver
list, parsing the stateless-connect, destruction) that degrades the game thread:
**21.7 -> 2.5 at ~25 000 pps**, collapse threshold ~100 000 packets, recovery 15-20 s.
(The interim "transport processing" wording of the C2/C3 control was superseded by this
experiment; both documents' evolution is preserved here.) Practical consequences: the
cheapest attack packet is a plain unreliable frame (18 bytes; adding frames gains
nothing - TPS min 2.6 vs 2.7); reliable/ack frames are useless for DoS (no connections,
no degradation; usable only as "quiet" traffic); CPU-wise unreliable is 20-25 us/packet,
reliable 20, reliable x10 40, ack 28. (Source contradiction preserved: the cost table
calls the 10-reliable-frames datagram "the most advantageous packet" at 3.8x junk CPU,
while this control experiment makes plain-unreliable the cheapest effective packet - CPU
expense is not the same as effect.)

Degradation thresholds: ~8 000 pps GNS data -> no effect (TPS min 20.7); ~25 000 pps GNS
data -> TPS 21.7 -> 2.5 (10x drop); ~43 000 pps junk -> no effect (TPS min 21.0);
~242 000 pps junk from 12 sources -> effect. So the spoofed-session vector is roughly
**10x cheaper** than junk in rate.

**Negative result (persistent connections not confirmed):** spoofing a GNS session and
feeding it copies of a real client's data packets (from `gns_relay_capture.jsonl` with
`to_connection_id` substituted): the server started answering with a continuous GNS data
stream (246 packets / 4.9 KB over 30 s) - the server-side handshake progressed; 200 such
sessions cost **+42 MB** of memory (~210 KB per connection); **but** UE4 connections are
not held - `liveConnections` returns to 2 and memory frees within ~10 s. Only GNS
transport-level connections persist; UE4 connections close because the stateless-connect
cookie was issued to the real client and fails verification for the spoofed session. A
persistent DoS would require disassembling and spoofing the UE4-handshake exchange
(server challenge -> cookie); even solved, the gain is bounded by memory (~210 KB per
connection) and NetDriver tick overhead, not an FPS collapse. Hence the vector's primary
form is a **wave**: sustain ~25 000 pps, dip 10x, recovery 15-20 s after stop.

Efficiency levers checked (can it be cheaper?):

- **Hypothesis A - several UE4 connections in one network packet** (N "stateless
  connect" packets per datagram, each own seq, own SNP frame): `ue4-62b` 20 000 packets
  -> 20 000 connections (1.00); `ue4-multi4` 20 000 -> 20 000 (1.00); `ue4-multi10`
  1.00; `ue4-multi20` 1.00. **Refuted** - UE4 processes the datagram as a single stream;
  the first stateless-connect "eats" the packet. The ceiling "1 packet = 1 connection"
  is reached and cannot be bypassed.
- **Hypothesis B - cheap via packet size**: rejected; payload size does not affect cost
  (6 B ~ 64 B ~ 512 B ~ 1400 B ~ 20-24 us/packet). Cost is measured in **packets**,
  not bytes; 500k packets = 9 MB payload (~30 MB on the wire) - uninteresting in
  bandwidth terms.
- **Hypothesis C - persistent connections**: covered above (negative; 100 sessions;
  `liveConnections` 0-1; connections live seconds).

Bottom line: the vector is already at the practical optimum of damage-per-packet
(1 packet = 1 connection; the price is fixed at ~17 us of server CPU). Real levers:

| Lever | What it buys | Cost |
|---|---|---|
| **Rate (multiple sources)** | collapse begins when inbound rate exceeds tick parsing speed (~25k pps local); 4 parallel senders ~ 80-100k pps | ~1.5 MB/s traffic; 4-10 s of work |
| **A different vector class** | the `ServerCheat` RPC - 1 packet = server command executed (privilege escalation, not DoS) | 1 packet |
| **Reflection (A2S, x15)** | traffic to third parties in the server's name | 1 packet -> 446 B |

Transience and scope: it is the **game thread** that degrades (players, their packets),
not server availability - the A2S port is served on a separate thread and keeps
answering (local RTT unchanged: 47-63 ms). On an external VPS the whole-box effect (50%
query losses) appears only with more load. The connections live ~10 s and cost ~210 KB.

**External threshold test** ("local-only?" check; `ark_lab_remote_threshold.py`, variant
`unreliable`, ~19-20k pps, external server 23.109.45.13:25714):

| Packets | pps | Seconds | Query-port losses (during flood) | Baseline losses | RTT max |
|---|---|---|---|---|---|
| 100 000 | 19 436 | 5.1 | **0.0%** | 0.0% | 312 ms |
| 200 000 | 20 384 | 9.8 | **0.0%** | 0.0% | 96 ms |
| 300 000 | 18 832 | 15.9 | **0.0%** | 0.0% | 96 ms |
| 500 000 | 19 708 | 25.4 | **3.4%** | 0.0% | 97 ms |

The effect is not local-only, but its magnitude is set by the server's resources: the
local bench collapses at ~80-100k packets (TPS 21.7 -> 2.5); the external VPS only at
~500k (and even then just 3.4% query losses) - a **5-6x difference**. Why the local bench
is so sensitive: the server is pinned to 4 cores (mask `0xF00000`, cores 20-23) on a
24-core host; Server1 shares the host (same manager directory, port 7777) plus the Steam
client and tooling; packets travel the local path (loopback/LAN gives far higher
interrupt/softirq load than a real network); the diagnostic NetGuard plugin adds
game-thread work (hooks on `ReceivedRawPacket` and `NotifyAcceptingConnection` + a
capture file capped at 4000 packets, a few us per packet of hook cost); and the attacker
runs on the same host (a control junk test at the same rate shows this is not the cause).
Externally-observable degradation needs the whole box to suffer; players suffer the FPS
dip while the server stays available - the correct behavior. Next step: measure the
external threshold with multiple sources (one Python thread produces ~20k pps) and check
external recovery time; note that the local Server2 bench was stopped at the time of
these measurements, so local measurements need a restart to continue.

**External variant ranking is impossible:** the same variant run on
23.109.45.13:25714 (150-200k packets per variant, measured by query-port losses):
`unreliable` 19.0% / 27.8% losses (RTT max 170 / 143 ms), `unreliable-x10` 15.0%
(178 ms), `blob` 15.8% (174 ms), `mixed` 15.8% (385 ms), **`reliable-x10` (control) 31.2% /
26.3% (404 / 168 ms)** - the control, which locally creates no connections and no
degradation, shows as many losses as the effective ones -> the signal is buried in WAN
noise; only the local FPS measurement ranks variants.

### Defense verdict for the GNS/UE4 vector

| Measure | Result |
|---|---|
| NetGuard valve on `NotifyAcceptingConnection` (`defense on`, `newConnectionsPerSecondLimit=50`) | **DOES NOT PROTECT**: all 200 000 attempts rejected (`connectionsRejected = 200000`) yet TPS still fell 21 -> 2.0 - the cost arises **before** the rejection point (packet parsing, connection object create/destroy, NetDriver list work in the tick) |
| Firewall / rate limiting on UDP 7778 | **effective** (the only network-level measure that works) - packets never reach the server process |
| A GNS-level limit (hook on `GameNetworkingSockets.dll` dispatcher + RVA 0x24E00) | not implemented but feasible: PolyHook 2 is already in ARK-Server-API |
| Monitoring | `connectionAttempts` jump from 0 to tens of thousands per second = handshake scanning |

Recommended: close UDP 7778 from the internet (allowlist) or rate-limit at the border
(nftables/WFP); GNS policy `IP_AllowWithoutAuth = 0`, `AllowRemoteUnsignedCert = deny`
(the bench accepted an anonymous `ConnectRequest` - a default-configuration defect);
per-address connection limits in addition to the existing 1 per (IP:port); monitor
`ConnectOK`/`ConnectionClosed` with reason 5002. This is not "an ARK vulnerability" but a
consequence of a publicly reachable game port without transport authentication.

---

## ARK-specific vectors

Curated list of game-level vectors (engine mechanisms are ARK-owned, not shared with
stock UE4.5). "Confirmed live" items were verified on the Server2 bench on 2026-10-20.

### N1. `SHOOTERGAME_ServerCheat` - command-execution RPC (no server-side authorization)

**Verdict (final):** on a **private** ARK server, **any player who logs in** can execute
arbitrary server commands via a single client->server RPC - `UShooterCheatManager`
including `ScriptCommand` = arbitrary Blueprint on the server = full control over the
world. Neither RCON, admin rights, nor the IP allowlist gates it. `bIsAdmin` /
`HasValidAdminIP` affect only the rights *interface* (opening the admin panel), not the
ability to execute a command. Vector #1 by damage.

Mechanism: client `AShooterPlayerController::AdminCheat(FString Cmd)` (truncates to 300
chars, client dump 358 lines 2532531/3814806) -> `ABasePlayerController::ServerCheat`
`0x1412C74E0` (looks up the UFunction `SHOOTERGAME_ServerCheat`, calls `ProcessEvent`) ->
dispatcher `execServerCheat` `0x14170FDE0`:

```c
cVar6 = vtable_11E0(this, &Cmd);        // -> ServerCheat_Validate(Cmd)
if (cVar6 == 0) GLastRPCFailedReason = L"ServerCheat_Validate";
else vtable_11E8(this, &Cmd);           // -> ServerCheat_Implementation(Cmd)
```

Server side:
- `ABasePlayerController::ServerCheat_Validate` `0x1401F3080` (13 B) decompiles to an
  unconditional `return true` - the **base** class implementation (the same on the
  client);
- `ABasePlayerController::ServerCheat_Implementation` `0x1401F3090` (4396 B) - **no**
  instructions referencing `bIsAdmin` (offset 0x5C8) at all;
- log line: `AdminCmd: %s (PlayerName: %s, ARKID: %llu, SteamID: %s)` - the
  **admin-command** channel (neither RCON nor the local console);
- flag geometry: `FDetermineBitMask_APlayerController_bIsAdmin::SetBit` - `bIsAdmin` =
  **bit 4** of a `uint32` at **0x5C8**; `bIsServerAdmin` is a bool at **0x1A44** and a
  **replicated** property of `AShooterCharacter` (`GetLifetimeReplicatedProps`
  `0x140AC3527`) - the flag arrives from the server; the reflection property of
  `bIsAdmin` is in `Z_Construct_UClass_APlayerController` `0x142A1303E`;
- the `RPC_VALIDATE Failed: !S.IsEmpty() && bIsAdmin ...` string is present in the
  binary data (0x143BFE800) but Ghidra finds **no references** to it (0 xrefs; a
  byte-pattern search also comes up empty) - either the check is inlined with a
  different string in this build, or it did not make it into the analysis map;
- `ABasePlayerController::HasValidAdminIP` `0x1401F2BE0` (1177 B): if
  `!GIsOfficialServer` (global at **0x144703BAF**; disassembly
  `1401F2C00: MOVZX EAX, byte ptr [0x144703BAF]` / `JZ 0x1401F306F`) -> return true;
  `bOfficialIgnoreAdminIPCheck` -> true; then Steam subsystem verification; then
  `GameMode->AllowedAdminIPs.FindId(ip) != -1`; else false.

**Rights-model resolution (empirical):** `bIsAdmin` is **not** set from
`HasValidAdminIP()`: bench metrics for a live player (`isquzee1`, ARKID 769454347,
SteamID 76561199331214868) read officialServer 0, validAdminIP 1, admin 1,
serverAdmin 1; after clearing `.../Saved/AllowedCheaterSteamIDs.txt` and a restart, the
same measurements gave `bIsAdmin` 1 -> **0**, `bIsServerAdmin` 1 -> 0, `HasValidAdminIP()`
1 -> **1 (unchanged)**, `GIsOfficialServer` 0 -> 0. Conclusion: `bIsAdmin` comes from the
`AllowedCheaterSteamIDs` list; `HasValidAdminIP()` is always true on a private server
(branch (1) fires before the IP list) but grants **no rights** by itself. The admin
password appears **0 times** in the packet capture - rights are not set by password.

**A/B proof (closed by experiment, same client):**
15:19:41 client `enablespectator` with server `bIsAdmin` = 1 (normal) -> **executed**
(`AdminCmd: ... enablespectator (PlayerName: isquzee1, ARKID: 769454347, SteamID:
76561199331214868)`); plugin `adminforce off` (clears bit 4 @0x5C8; read-back `admin:0`);
15:25:38 client `disablespectator` with `bIsAdmin` = 0 (forced) -> **executed**, same log
format. Therefore there is **no rights check on the `ServerCheat` path** - neither in C++
(0 instructions reading 0x5C8), nor in the Blueprint layer (executes with the flag
cleared). Independent server-side proof (`cheatprobe` in NetGuard, reproducing the RPC
chain server-side for a controller whose rights were removed):
`"bIsAdmin": 0, "validateFn": true, "validateResult": 1, "implFn": true, "executed": 1`
(log: `[net] cheatprobe: bIsAdmin=0 validate=1 executed=1`). Residual caveat for honesty:
the A/B observation came from a client whose IP passes `HasValidAdminIP`; proving it
"from zero" would need a second client with a different account/IP to also rule out a
Blueprint-side check by SteamID/Steam group (only remaining hypothesis). Tooling:
NetGuard's `adminforce on|off` forcibly sets/clears `bIsAdmin` (bit 4 of the 0x5C8
dword) for all players: `adminforce off -> {'ok': True, 'players': 1, 'value': 0}`,
playerList shows admin 0 / serverAdmin 0 / validAdminIP 1; `adminforce on` -> 1/1/1.
Observed: when `bIsAdmin` is cleared, `bIsServerAdmin` (@0x1A44) clears **by itself** -
the server periodically re-derives the server-admin indicator from `bIsAdmin` (the
leading flag), while `validAdminIP` (=1) does not change.

Executed commands reach ARK's `UShooterCheatManager`:

| Command | Strings in binary | Damage |
|---|---|---|
| `ScriptCommand` | 0x1438BBAC0, 0x14394D450, 0x143A5A140 | **arbitrary Blueprint** on the server - full world control |
| `DestroyWildDinos` | 0x14394C910, 0x143A57D60 | heavy pass over all dinos (CPU) |
| `SaveWorld` | 0x14394D420, 0x143A5A0C0 | game-thread freeze for world serialization (measured **3.9-4.3 s** in production) |
| `DoExit` | 0x1438A65AC, 0x143A57C28 | server shutdown |
| `SetGodMode` | 0x1438DDF20 ... | grants god mode |

What is *not* proven: who writes `APlayerController::bIsAdmin` in the general case
(server after PIN/password verification vs the client via login options) - testable by
reading the field by PDB name (`NetGuard` has `SafeFieldPtr`) while a client logs in with
different login options. Defense deployed: NetGuard `blockServerCheat` hook ->
`ServerCheat_Validate` always false. The only barrier that exists in this build is
**client-side** (the ARK client does not surface admin commands when the server sent
`bIsAdmin = 0`; in the post-clear session the command never reached the wire - 0 traces
in the capture) - not server protection: a custom client (mod/repack) calls the UFunction
directly.

### N2. `AShooterGameSession::ApproveLogin` - the pending-authentication map

`0x140CE1100` (7711 bytes):

```c
key  = param_3->PlayerId->ToString();            // SteamID64 as a string
map  = &this->CurrentUsersTryingToAuthAndGetLoginLock;   // TMap<FString,FCurrentLoginAuthCheck>
FScopeLock lock(map);                            // GLOBAL LOCK
if (map->Find(key) == -1) entry = map->Emplace(key);
entry->Connection = param_3;                     // FWeakObjectPtr
entry->TimeStarted = GameState->TimeSeconds;     // a TTL hint
session->vtable_248(this, delegate);             // delegate registration in IOnlineSession
if (!session->vtable_238(this, &token))          // TOKEN CHECK (outbound call to Steam)
    return "Invalid authentication token.";      // xref: AShooterGameMode::StartNewShooterPlayer 0x140C5A40A
```

Properties: every login attempt makes an outbound call to Steam/EOS and takes a **global
lock** -> serialization of all logins on the game thread; the map grows by every new
SteamID (`TimeStarted` hints at a TTL, but no cleanup is visible in the code); the key is
the SteamID, so growth requires many **real** accounts. `FCurrentLoginAuthCheck` -
processing a login is the most expensive L3-L7 path. Ranking among ARK vectors: #4
(mechanism confirmed, not measured) - outbound Steam calls + lock + map on the game
thread, requires many SteamIDs. Open question: whether a TTL/cleanup exists and the
delegate's cost (an outbound Steam call = 100+ ms on the game thread if waited on
synchronously?).

### N3. Per-packet tiny token - an ARK-specific protocol extension (not a barrier)

`UNetConnection::ReceivedRawPacket` `0x1424C6070`:

```c
if (this->bIsUsingPerPacketTinyToken) {
    if (param_2 < 5) return;
    if (*(uint32*)param_1 & 0x80000000) {          // HIGH BIT - just a marker
        if (param_2 != 0x48) return;               // exactly 72 bytes
        if (*(int32*)((char*)param_1 + 0x44) != 0x166) return;   // version 358
        if (++this->RecentFullTinyTokenACKs > 9) return;         // no more than 9
        FNetControlMessage<23>::Send(this, ...);   // server's reply
        return;
    }
    param_1 += 4; param_2 -= 4;                    // strip the 4-byte prefix
}
```

ARK-specific error string: `"ReceivedRawPacket() Packet is too small doesn't include
PerPacketTinyTokenToRecieve() plus 1"`. At the UE4 level the "token" is 4 bytes whose
**high bit is set**; **the value is never compared against a secret**. Confirmed on live
traffic: the client (dump 358, lines 3627100-3627138) sends exactly **72 bytes** =
`[4 B: PerPacketTinyTokenToSend | 0x80000000][64 B "full token"]`; the server (in the
high-bit branch) checks **only** length 0x48 and version 0x166 at offset +0x44; **and in
the captured session the client went down the regular path** (first 4 bytes of every
packet = `5b17b519`, high bit not set -> the token branch was unused,
`bIsUsingPerPacketTinyToken` false). The 64-byte "full token" is P2P crypto material.

**Main conclusion:** the only real barrier in front of the UE4 amplifier is the **Steam
P2P session**. Its key is derived from two SteamIDs, and **the server's SteamID is
published in the A2S rules** (`OWNINGID`, plus `P2PPORT = 7778`) - reconnaissance is free
from the query port. Needed next: the P2P key derivation from `steamclient64.dll`/GNS
(in open-source GNS the key = a hash of two SteamIDs; the Steam implementation uses a
different function; candidates to reverse: `CP2PNetworkingSession` /
`m_mapP2PConnectionRequests`, `P2PConnectionRequest_t`). Once derived, ARK's main DoS
vector opens up: 1 datagram = 1 UE4 connection = full packet parse + an object that
lives until `InitialConnectTimeout` (300 s). Status: GNS-session spoofing was eventually
implemented **without** needing P2P key derivation (see the Report above) - the
transport-level attack works; P2P-key derivation from `steamclient64.dll` (12 MB) remains
open.

### N4. `UPrimalItem::ServerHandleItemNetExecCommand` - a second in-band command channel

`0x1407FBB60` (54 bytes) -> delegates to the Blueprint
`BPServerHandleItemNetExecCommand`. Besides `SHOOTERGAME_ServerCheat`, an **item-based**
command execution channel (the command arrives from an item/structure). The Blueprint
logic lives in a `.uasset`, not in C++ - requires unpacking the cooked asset
(`BPBasePlayerController` too). Status: mechanism confirmed, Blueprint not unpacked;
ranking #6 (needs login + an item).

### N5. Steam query (A2S) - reachable without a client

| Property | Value (measured) |
|---|---|
| Rules | 21, all ARK-specific (`DAYTIME_s`, `GAMEMODE_s`, `HASACTIVEMODS_i`, `MODID_l`, `SEARCHKEYWORDS_s`, `SESSIONFLAGS`, `SESSIONISPVE_i`, `SERVERUSESBATTLEYE_b`, ...) |
| Publishes | `OWNINGID` (the server's SteamID) and `P2PPORT` (the game port) -> free reconnaissance for N3 and the session-spoofing vector |
| Cost | ~26 us CPU per request |
| Amplification | 446 B reply to a 30 B request = **x15** (the server as a reflector against third parties) |
| Slots | advertised `NUMOPENPUBCONN=70` is static; the real gate is `AtCapacity()` -> `net.MaxPlayersOverride` (1 RCON command) -> "Server full." for everyone |

Status: measured; ranked low as a DoS (0% TPS at 41 k pps) but real as a reflection
vector.

### N6. Structure PIN codes (game-level, not DoS)

`ITargetableInterface::ValidatePinCode(int)` validates only the range 0..9999;
`APrimalStructureItemContainer::ValidatedByPinCodePlayerControllers` - the list of players
who passed; `bIsPinLocked` - the lock indicator. No attempt limit is visible in C++ -> a
4-digit code is trivially brute-forced, but the damage is **game-level** (opening
someone's container structure), not denial of service. Confirmed.

### N7. LoginLock - the Redis-backed per-account lock

ARK protects logins with a **Redis lock record per account**:

| Element | Address / string |
|---|---|
| Redis key | `playerloginlock:` (`0x14387E780`) |
| Acquire | `UDatabase_LoginData_Redis::GetLoginLock() for account %s` (`0x14387E9E0`; RVA 0x250750, 1403 B - a real **cpp_redis** client; the key `admin:ips:pc` holds the admin-IP list) |
| Release | `UDatabase_LoginData_Redis::ReleaseLoginLock() for account %s` (`0x14387E870`) |
| Script | `TRY_GETLOGINLOCK_LUA_ID` (a Lua script in Redis; load failure at `0x14387E8F0`) |
| Enforcement point | `AShooterGameMode::ExtraPreLoginChecksBeforeWelcomePlayer` (`0x140C50930`, 4695 B) |
| Maintenance | `TickLoginLocks` (`0x140C67FD0`), `RemoveLoginLock` (`0x140C546B0`), `WasSuccessfulLogin` (`0x140CDA920`) |
| Client rejection | `PreLogin: Waiting on Login Lock. Please try again in a minute.` (`0x1438E2240`), `Waiting on Login Lock. Try again in a few minutes!` (`0x1438E24C0`) |
| Kill switches | `bHasArkLoginLock` (`0x143D0A968`), `bGlobalDisableLoginLockCheck` (`0x143A68220`), `bTempDisableLoginLockCheck` (`0x143A68260`) |
| Degradation | `Disabled LoginLock due to loss of redis connection` (`0x1438E3280`) |
| Metrics | `arkservers.logincheck.preloginerror1/2` (`0x1438E5AC8`), `IncrementPreLoginMetric` (`0x140C017A0`) |

Answer to "can a client be emulated so its connection hangs and blocks others?" - by
level:

| Level | Required | Takes a slot? | Blocks others? |
|---|---|---|---|
| Transport squat | pass Steam P2P + the UE4 handshake, never finish login | **no** | **no** |
| Login-phase squat | a real Steam session (valid token) | **no** | **no** (the lock is on *your own* account) |
| Player squat | completed login (a real account) | **yes** (1 of 70) | **yes, but** 70 accounts are needed |
| Instantly blocking everyone | RCON access | - | `net.MaxPlayersOverride 1` = 1 command |

Justification: slots are counted by logged-in players (`GetNumPlayers()`, not
`ClientConnections`); the LoginLock is keyed `playerloginlock:<account>` - per-account
only; without a real Steam session (`PlayerId == NULL`) you never reach login; but a
transport squat still buys per-connection objects plus Steam P2P state - with a
per-connection cost far above discarded junk (~20 us/packet measured), so degrading the
tick takes far fewer packets (that is the GNS vector, implemented); and the
`ExtraPreLoginChecksBeforeWelcomePlayer` gate touches the pending-auth map
(`TMap<FString,FCurrentLoginAuthCheck>`) and the connection array
(`TArray<UNetConnection*>`) under an `FScopeLock` - many simultaneous logins can make the
server start **rejecting new logins** (throttling legitimate players, not blocking
slots). Bench note (strange artifact): `CurrentUsersTryingToAuthAndGetLoginLock` is
missing from the PDB and the counter reads **-1**; Redis is absent on the bench ->
**on the bench the LoginLock mechanism does not exist at all** (Redis-dependent). To
verify empirically: a live client (BotPlayer) to capture a real P2P handshake and measure
the cost of one hanging connection (ms/tick, memory); extended NetGuard metrics
(`liveConnections` exists; a login-phase connection counter and hanging-connection
lifetime need to be added); and the N1 question of who writes `bIsAdmin`.

### Capture record (what a real login looks like on the wire)

File: `.../ArkApi/Plugins/NetGuard/NetGuard_capture.log` (UE4-level packet capture +
NMT/PreLogin/PostLogin events):

```text
len=6    5b17b519 01 40                       first packet of the connection
len=62   5b17b519 04 8005 ... "135.136.6.19" ...  client address (via VPN) + a 16-byte FGuid
         NMT 0 -> NMT 4 (Challenge) -> the server sends 516 B (challenge with a Steam ticket)
len=516  "140000000640C070AA9956D01406B75101001001D575D66AB8..."  Steam auth ticket, hex
         + "* /Game/Maps/MainMenu?ModId=0?Name=isquzee1"              (travel URL)
         + "76561199331214868"                                        (SteamID64)
         NMT 5 (Failure) -> PreLogin tokenLen=443 -> NMT 4 -> NMT 9 (Login) -> PostLogin
```

The first login attempt was **rejected** (NMT 5 = Failure); the second succeeded. Final
sequence: `0 -> 4 -> 5 -> PreLogin -> 4 -> 9 -> PostLogin`. The admin password does **not
appear** in the capture (0 occurrences) -> `bIsAdmin` is set not by password but by the
IP/SteamID-list logic.

### Rankings of the ARK-specific vectors

Initial ranking (mechanism analysis, before the empirical closure):

| Rank | Vector | Requires | Damage | Status |
|---|---|---|---|---|
| 1 | N1 ServerCheat RPC | normal player login | 1 message = `ScriptCommand`/`DoExit`/`DestroyWildDinos`/`SaveWorld` | mechanism confirmed; bIsAdmin writer unverified |
| 2 | N5 `net.MaxPlayersOverride` -> "Server full." | RCON access | all players rejected (1 command) | confirmed (UE4.5 sources + binary) |
| 3 | N3 Steam P2P key -> 1 packet = 1 `UNetConnection` | key derivation from SteamIDs (data public) | genuine DoS: connection objects + tick work, up to 300 s | analysis complete; key not derived |
| 4 | N2 login-attempt flood | many SteamIDs | outbound Steam calls + lock + map on the game thread | confirmed, not measured |
| 5 | N4 item NetExecCommand | normal login + an item | a second command channel | Blueprint not unpacked |
| 6 | N5 A2S reflection x15 | nothing | the server as a traffic source + reconnaissance | measured |
| 7 | N6 structure PINs | normal login | game-level (not DoS) | confirmed |

Updated ranking after the empirical closure (adds N7):

| Rank | Vector | Requires | Damage | Status |
|---|---|---|---|---|
| **1** | **N1 `ServerCheat` from an ordinary player on a private server** | a normal game login | **full server takeover** (`ScriptCommand` = arbitrary Blueprint), 1 request | path proven by code + flag measurement + A/B; a second (non-admin) client for the final point |
| 2 | N5 `net.MaxPlayersOverride` via RCON | RCON | "Server full." for everyone, 1 command | confirmed |
| 3 | N3 Steam P2P key -> 1 packet = 1 `UNetConnection` | key derivation from `steamclient64` | DoS from ~1 packet per connection | barrier confirmed, key not derived (supplemented: the transport-level GNS variant was implemented; see the Report) |
| 4 | N2 login-attempt flood | many SteamIDs | outbound Steam calls + lock + map | confirmed, not measured |
| 5 | N7 LoginLock as DoS | real accounts | per-account login blocking | Redis-dependent, absent on the bench |
| 6 | N4 Item NetExecCommand | login + an item | a second command channel | Blueprint not unpacked |
| 7 | N5 A2S reflection x15 | nothing | the server as a traffic source | measured |

L7 map of ARK SE surfaces (summary):

| Surface | L7 risk | Status |
|---|---|---|
| `SHOOTERGAME_ServerCheat` (RPC client->server) | **arbitrary server command execution** | vector #1, no gate; defense deployed (`blockServerCheat`) |
| `AdminCheat` -> `ServerCheat` (client-side call) | the same | uses the same RPC |
| `ServerHandleItemNetExecCommand` -> BP | a second command channel | Blueprint not unpacked |
| A2S / Steam query (27016) | x15 reflection, reconnaissance (SteamID + game port) | measured |
| Source RCON (32331) | brute force, command execution | excluded from testing on request |
| Login gate (`ApproveLogin` -> `AtCapacity`) | see the Slots section | dissected; no "occupancy" vector |
| LoginLock (Redis) | per-account login blocking | Redis absent on the bench |

### What remains to be checked (requires data not available on this machine)

1. **The writer of `APlayerController::bIsAdmin`** - server-side check or client
   influence via login options (plugin reads the field via PDB; client logs in with
   different options).
2. **Steam P2P-key derivation** from `steamclient64.dll` (12 MB) - reverse
   `CP2PNetworkingSession` / `m_mapP2PConnectionRequests`, or use open-source GNS as a
   reference.
3. **Cooked assets** (`BPBasePlayerController`, `BPServerHandleItemNetExecCommand`) -
   the Blueprint authorization logic of commands lives in `.uasset` files, not in C++.
4. **A live client** (BotPlayer) - the only way to capture a real P2P handshake and test
   N1 (with a second non-admin client) / N3 on the wire.
5. **The ARK engine sources** (`F:\build\LostIsland\Engine\...`) - not available on this
   machine; stock UE4.5 differs (no `ServerCheat_Validate`, no `bIsAdmin`).
6. A second GNS spoofing question: does the server accept an **unsigned** cert
   (`AllowRemoteUnsignedCert`) and how does ARK's UE4 layer treat an identity of
   "IP-address" type? If yes - "any host => an arbitrary SteamID in the GNS session =>
   a channel down to the UE4 level"; would need ECDH (X25519) + ECDSA P-256 in pure
   Python (the `cryptography` module is not installed on the bench).
