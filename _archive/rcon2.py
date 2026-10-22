# -*- coding: utf-8 -*-
# Минимальный RCON-клиент (ARK): auth + команда. Хост/порт из last_rcon_port.txt.
import socket, struct, sys, io

PORT_FILE = r'C:\Dev\_research\last_rcon_port.txt'
PW = '0ub7OuAD6V68cbzc'
HOSTS = ['127.0.0.1', '192.168.8.218']


def _pack(rid, payload):
    b = payload.encode('utf-8') + b'\x00\x00'
    return struct.pack('<ii', len(b) + 8, rid) + b


def rcon(cmd, port=None, pw=PW, host=None, timeout=6):
    if port is None:
        port = int(io.open(PORT_FILE).read().strip())
    hosts = [host] if host else HOSTS
    last = None
    for h in hosts:
        try:
            s = socket.create_connection((h, port), 4)
        except Exception as e:
            last = e
            continue
        try:
            s.settimeout(timeout)
            s.sendall(_pack(1, pw))
            try:
                s.recv(4096)
            except Exception:
                pass
            s.sendall(_pack(2, cmd))
            buf = b''
            try:
                while True:
                    d = s.recv(65536)
                    if not d:
                        break
                    buf += d
            except socket.timeout:
                pass
            s.close()
            return buf.decode('utf-8', 'replace')
        except Exception as e:
            last = e
            continue
    raise IOError('RCON недоступен: %s' % last)


if __name__ == '__main__':
    for c in (sys.argv[1:] or ['status']):
        print('=== %s ===' % c)
        print(rcon(c))
