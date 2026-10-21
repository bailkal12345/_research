import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RCON_HOST", "192.168.8.218")
os.environ.setdefault("RCON_PORT", "27020")
sys.path.insert(0, HERE)

import slot_measure as S  # noqa: E402
import threadcpu  # noqa: E402

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 240

tid = S.game_tid()
if not tid:
    print("НЕТ tid")
    sys.exit(2)
print("Python-измерение, tid=%d, окно %d с" % (tid, SECONDS), flush=True)

# одновременно ставим окно плагина
S.cmd("TickProf.window %d" % SECONDS)
time.sleep(1)

c0 = S.cpu_of(tid, 3)
t0 = time.time()
while time.time() - t0 < SECONDS + 6:
    time.sleep(5)
c1 = S.cpu_of(tid, 3)

# читаем строку плагина, дописанную ПОСЛЕ нашего запроса
import os as _os
mark = 0
with _os.open(S.LOG, _os.O_RDONLY) if False else open(S.LOG, "rb") as f:
    pass

frames = wall = 0.0
pcpu = 0.0
pvalid = "?"
for ln in reversed(S.log_tail(60)):
    if "window " in ln and "ms/tick" in ln:
        print("ПЛАГИН:", ln, flush=True)
        for tok in ln.split():
            if tok.startswith("t/s="):
                ptps = float(tok[4:])
            if tok.startswith("cpu="):
                pcpu = float(tok[4:].rstrip("s"))
            if tok.startswith("ms/tick="):
                pms = float(tok[8:])
            if tok in ("VALID", "CONTAMINATED"):
                pvalid = tok
        break

rate = (c0 + c1) / 2.0
print("PYTHON : rate=%.3f s/s  (окно %d с)" % (rate, SECONDS), flush=True)
print("Для мс/тик нужен т/с; беру мгновенный т/с плагина.", flush=True)