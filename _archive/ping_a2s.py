# -*- coding: utf-8 -*-
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3)
try:
    s.sendto(b"\xff\xff\xff\xffTSource Engine Query\x00", ("192.168.8.218", 27015))
    d = s.recv(4096)
    print("A2S reply len:", len(d))
except Exception as e:
    print("A2S fail:", e)
