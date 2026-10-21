import socket, json, time
def raw(cmd, wait=6):
    s = socket.create_connection(("127.0.0.1", 8082), timeout=20)
    s.sendall((json.dumps(cmd)+"\n").encode())
    s.settimeout(wait)
    buf=b""
    t0=time.time()
    while time.time()-t0 < wait:
        try:
            c = s.recv(65536)
        except socket.timeout:
            break
        if not c: break
        buf += c
        if b"\n" in buf: break
    s.close()
    return buf.decode("utf-8","replace")
print("STATUS ->", repr(raw({"cmd":"status"}))[:900])
print()
print("PING   ->", repr(raw({"cmd":"ping"}))[:400])
