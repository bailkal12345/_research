import socket
import struct
import sys

HOST = "192.168.8.218"


def a2s_info(port):
    """Классический A2S_INFO: 'A2S' + null + 0xFF 'T' Source Engine Query"""
    # Source (не Source2) вариант
    payload = b"\xff\xff\xff\xff\x54Source Engine Query\x00"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(6)
    s.sendto(payload, (HOST, port))
    try:
        data, _ = s.recvfrom(4096)
    except socket.timeout:
        return None, "таймаут 6 с (нет ответа A2S)"
    finally:
        s.close()
    return data, ""


def parse(data):
    if not data or len(data) < 5:
        return "слишком короткий ответ: %r" % (data,)
    out = []
    if data[:5] == b"\xff\xff\xff\xff\x49":  # A2S_INFO legacy response header
        body = data[5:]
        i = 0
        # protocol byte
        proto = body[0]
        out.append("protocol=%d" % proto)
        i = 1
        fields = []
        while i < len(body):
            b = body[i]
            if b == 0:
                break
            if b == 0xFF:
                i += 1
                break
            j = body.index(0, i)
            fields.append(body[i:j].decode("latin1"))
            i = j + 1
        out.append("server=%r" % (fields[0] if fields else "?"))
        out.append("map=%r" % (fields[1] if len(fields) > 1 else "?"))
        out.append("folder=%r" % (fields[2] if len(fields) > 2 else "?"))
        out.append("game=%r" % (fields[3] if len(fields) > 3 else "?"))
        out.append("appid=%s" % (fields[4] if len(fields) > 4 else "?"))
        out.append("players=%s/%s" % (fields[5] if len(fields) > 5 else "?",
                                      fields[6] if len(fields) > 6 else "?"))
        out.append("keywords=%r" % (",".join(fields[7:]) if len(fields) > 7 else "?"))
    else:
        out.append("заголовок 0x%02x%02x%02x%02x%02x" % tuple(data[:5]))
        out.append("сырые байты: %s" % data[:120].hex())
    return "\n  ".join(out)


if __name__ == "__main__":
    ports = [int(x) for x in sys.argv[1:]] or [27015, 27016, 7777]
    for p in ports:
        data, err = a2s_info(p)
        print("=== A2S %s:%d" % (HOST, p))
        if data is None:
            print("  " + err)
        else:
            print("  ответ %d байт" % len(data))
            print("  " + parse(data))