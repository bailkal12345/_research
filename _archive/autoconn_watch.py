import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath("botwatch.py")))
os.chdir(os.path.dirname(os.path.abspath("botwatch.py")))
sys.path.insert(0, ".")
from botwatch import bot_call, tail_state, server_players

t0 = time.time()
last_ev = []
while time.time() - t0 < 1500:
    st, ev = tail_state(300)
    print("%s t+%4ds state=%-12s сервер=%s" % (time.strftime("%H:%M:%S"), int(time.time()-t0), st or "?", server_players()), flush=True)
    for e in ev:
        if e not in last_ev:
            last_ev.append(e)
            print("    " + e, flush=True)
    if st == "Active":
        print(">>> АКТИВНА", flush=True); break
    time.sleep(20)
