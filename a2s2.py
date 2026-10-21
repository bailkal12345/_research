import socket

HOST = "192.168.8.218"
PORT = 27015


def q(payload, timeout=6):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    s.sendto(payload, (HOST, PORT))
    try:
        data, _ = s.recvfrom(8192)
        return data
    except socket.timeout:
        return None
    finally:
        s.close()


def main():
    # 1) получить челлендж
    ch = q(b"\xff\xff\xff\xff\x54Source Engine Query\x00")
    if not ch:
        print("нет ответа на A2S challenge")
        return
    print("челлендж: %s (%d байт), тип 0x%02x" % (ch[5:].hex(), len(ch), ch[4]))
    challenge = ch[5:9]
    if ch[4] != 0x41:
        print("не A2S_GETCHALLENGE, выходим")
        return

    # 2) A2S_PLAYER_RULES с челленджем (стандартный путь UE4-клиента)
    rules = q(b"\xff\xff\xff\xff\x56" + challenge)
    if rules:
        print("\nA2S_PLAYER_RULES -> %d байт, тип 0x%02x" % (len(rules), rules[4]))
        body = rules[5:]
        parts, i = [], 0
        while i < len(body):
            j = body.find(b"\x00", i)
            if j < 0:
                break
            parts.append(body[i:j].decode("latin1"))
            i = j + 1
        for p in parts:
            print("   %s" % p)
    else:
        print("A2S_PLAYER_RULES: нет ответа")

    # 3) A2S_INFO с челленджем
    info = q(b"\xff\xff\xff\xff\x49" + challenge)
    if info:
        print("\nA2S_INFO -> %d байт, тип 0x%02x" % (len(info), info[4]))
        body = info[5:]
        i = 1  # protocol byte
        fields = []
        while i < len(body):
            if body[i] == 0:
                break
            j = body.find(b"\x00", i)
            if j < 0:
                break
            fields.append(body[i:j].decode("latin1"))
            i = j + 1
        for k, f in enumerate(fields):
            print("   [%d] %s" % (k, f))
        if len(fields) > 7:
            print("\n   keywords: %s" % ", ".join(fields[7:]))
    else:
        print("A2S_INFO: нет ответа")


if __name__ == "__main__":
    main()