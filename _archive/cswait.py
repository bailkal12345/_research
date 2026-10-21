"""Быстрый цикл ожидания: опрашивает лог, пока не появится маркер или клиент умрёт."""
import os
import subprocess
import sys
import time

HERE = r"C:\Dev\_research"
MARK = sys.argv[1] if len(sys.argv) > 1 else "JoinSession"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 420

t0 = time.time()
seen = 0
while time.time() - t0 < LIMIT:
    out = subprocess.run(
        [sys.executable, os.path.join(HERE, "cs.py"), "[connect]", "14"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    text = out.stdout or ""
    lines = text.splitlines()
    alive = "ЖИВ" in text
    print(text.rstrip())
    if MARK in text:
        print(">>> найден маркер: %s" % MARK)
        break
    if not alive and seen > 0:
        print(">>> клиент погиб")
        break
    seen += 1
    time.sleep(20)