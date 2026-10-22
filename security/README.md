# Lab scripts - ARK SE v358.24, Server2 bench

All findings, vectors, protocol details: **`SECURITY.md`**.

## Running

Python 3 (bench: `C:\Program Files\Python314\python.exe`). Set
`$env:PYTHONIOENCODING='utf-8'` first or scripts die with `UnicodeEncodeError`
(cp1252 console).

```powershell
cd C:\Dev\_research\security
python ark_lab_suite.py --all --seconds 12 --json out\suite.json  # all scenarios + ranking
python ark_lab_gns_amp.py --count 200000                          # main vector
python ark_lab_gns_amp.py --stepped --burst 20000 --duration 60   # attack cost curve
python ark_lab_remote_probe.py --host 23.109.45.13 --query-port 25715 --seconds 40 --interval 0.2
python ark_lab_metrics.py status
```

Safety: target bench `192.168.8.218` (game 7778, query 27016, NetGuard metrics
`127.0.0.1:27101`); `ark_lab_net.py`'s `guard_target()` refuses non-bench addresses.
**RCON is administration only** (`rcon_cmd.py`), never an attack surface.
`ark_lab_gns_amp.py` pre-checks availability and **refuses to run (exit 3)** if the game
port does not answer (`--skip-check` disables). `ark_lab_sniff_gns.py` needs admin.
Remote runs only against an explicitly authorized host
(`--host --game-port --query-port --no-metrics`).

## Scripts

- Main vector (GNS forgery): `ark_lab_gns_amp.py` (amplifier, self-contained, exports `run_amp()`);
  `ark_lab_gns_ue4_v2.py` (4-packet UE4 handshake debug); `ark_lab_gns_connect.py`
  (stage 2: ConnectRequest/ConnectOK); `ark_lab_gns_probe.py` (stage 1: ChallengeRequest);
  `ark_lab_gns_conn_flood.py` (ConnectRequest flood, 1-per-IP:port limit);
  `ark_lab_gns_challenge_flood.py` (ChallengeRequest flood, no state).
- Measurement: `ark_lab_suite.py` (S1-S5 + ranking); `ark_lab_gns_fps_test.py`
  (controls C0-C3); `ark_lab_gns_cost.py` (us/packet per variant); `ark_lab_variant_compare.py`
  (frame-type variants); `ark_lab_remote_threshold.py` (100-500k stepped test);
  `ark_lab_deadconn.py` (dead-connection lifetime).
- Intercept analysis: `ark_lab_gns_relay.py` (UDP relay, handshake capture);
  `ark_lab_gns_analyze.py` (types, cert/crypt); `ark_lab_gns_datapkt.py` (UDPDataMsgHdr,
  sizes); `ark_lab_gns_align.py` (GNS<->UE4); `ark_lab_handshake_capture.py`
  (early capture relay); `ark_lab_replay_probe.py` (real UE4 replay, dropped);
  `ark_lab_sniff_gns.py` (raw sniffer, admin).
- Baselines: `ark_lab_loadtest.py` (query/query-flood/game-flood/suite);
  `ark_lab_fps_saturate.py` (multi-source saturator); `ark_lab_fps_hunt.py` /
  `ark_lab_fpsdrop.py` (TPS threshold sweeps); `ark_lab_a2s_hunt.py` / `a2s_diag.py` /
  `a2s_probe_shapes.py` (A2S shapes, x15 amplification); `ark_lab_l7_probe.py` (L7
  surfaces); `ark_lab_gns_persist.py` / `ark_lab_gns_persist2.py` /
  `ark_lab_gns_persist_dos.py` (persistence attempts, negative result).
- Infra: `ark_lab_net.py` (UDP/TCP/A2S/process metrics, `guard_target()`);
  `ark_lab_metrics.py` (NetGuard client: status/ping/reset/config/defense/adminforce/cheatprobe);
  `ark_lab_watch.py` (real-time metrics); `rcon_cmd.py` (one RCON command, admin only).