# -*- coding: utf-8 -*-
# RCON-клиент для ARK: читает ВСЕ пакеты, пропускает keep-alive (id=-1),
# возвращает ответ на команду (id=2).
import socket, struct, io, time

PORT = 32330
PW = '0ub7OuAD6V68cbzc'
HOSTS = ['127.0.0.1', '192.168.8.218']


def _pack(rid, payload):
    b = payload.encode('utf-8') + b'\x00\x00'
    return struct.pack('<ii', len(b) + 8, rid) + b


def _unpack(buf):
    """Разбор пакета: (size, id, payload)."""
    if len(buf) < 4:
        return None
    size = struct.unpack_from('<i', buf, 0)[0]
    if len(buf) < size + 4:
        return None
    rid = struct.unpack_from('<i', buf, 4)[0]
    payload = buf[8:size + 4 - 2]
    return size + 4, rid, payload


def rcon(cmd, timeout=6.0, port=PORT, pw=PW, wait=1.5):
    for h in HOSTS:
        try:
            s = socket.create_connection((h, port), 4)
        except Exception:
            continue
        try:
            s.settimeout(0.5)
            s.sendall(_pack(1, pw))
            t_end = time.time() + wait
            auth_ok = False
            while time.time() < t_end:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    break
                if not d:
                    break
                p = _unpack(d)
                if p and p[1] == 1:
                    auth_ok = True
                    break
            if not auth_ok:
                s.close()
                continue
            s.sendall(_pack(2, cmd))
            buf = b''
            out = []
            t_end = time.time() + timeout
            while time.time() < t_end:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    if buf:
                        break
                    continue
                if not d:
                    break
                buf += d
                while True:
                    p = _unpack(buf)
                    if not p:
                        break
                    ln, rid, payload = p
                    buf = buf[ln:]
                    if rid == 2:
                        out.append(payload)
                    # rid == -1 => keep alive, игнорируем
            s.close()
            if out:
                return b''.join(out).decode('utf-8', 'replace')
            return ''
        except Exception:
            continue
    return None


if __name__ == '__main__':
    import sys
    for c in (sys.argv[1:] or ['status']):
        r = rcon(c)
        print('=== %s ===' % c)
        print(repr(r)[:1500] if r is not None else 'НЕТ ОТВЕТА')
