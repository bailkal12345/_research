# -*- coding: utf-8 -*-
"""
ark_lab_metrics.py — клиент метрик серверного плагина NetGuard.

NetGuard (ArkApi, version.dll) отдаёт метрики по TCP на 127.0.0.1:27101
одной JSON-строкой на команду. RCON для этого не нужен — он на боевых
серверах обычно закрыт.

Команды:
  status      полный снимок метрик
  ping        проверка живости
  reset       обнулить счётчики
  defense on  включить защиту (клапан + лимиты)
  defense off выключить защиту
  config      текущие пороги защиты
"""

from __future__ import annotations

import json
import socket
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 27101


class MetricsError(RuntimeError):
    pass


class NetGuardClient:
    """Клиент JSON-интерфейса NetGuard (одна команда - один запрос-ответ)."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def connect(self) -> "NetGuardClient":
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

    def __enter__(self) -> "NetGuardClient":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()

    def command(self, cmd: str) -> dict:
        """Отправляет команду и читает JSON-строку ответа."""
        if self.sock is None:
            self.connect()
        assert self.sock is not None
        self.sock.sendall((cmd + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise MetricsError("соединение закрыто плагином")
            buf += chunk
        line = buf.split(b"\n", 1)[0].decode("utf-8", "replace")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise MetricsError("не JSON от плагина: %r (%s)" % (line[:200], exc)) from exc

    def status(self) -> dict:
        return self.command("status")

    def set_defense(self, on: bool) -> dict:
        return self.command("defense on" if on else "defense off")

    def reset(self) -> dict:
        return self.command("reset")


def poll(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, seconds: float = 5.0,
         interval: float = 1.0) -> list[dict]:
    """Снимает ряд снимков метрик (для графика/корреляции с атакой)."""
    out: list[dict] = []
    with NetGuardClient(host, port) as c:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                out.append(c.status())
            except (OSError, MetricsError):
                pass
            time.sleep(interval)
    return out
