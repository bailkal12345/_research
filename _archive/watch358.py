import sys, time, os, io, re, json, socket, subprocess
DIR = r"C:\Games\ARK_SE_game_v358\ShooterGame\Binaries\Win64\logs"

def latest():
    fs = [os.path.join(DIR, f) for f in os.listdir(DIR)]
    return max(fs, key=os.path.getmtime)

def tail(n=300):
    with io.open(latest(), encoding="utf-8", errors="replace") as f:
        L = f.readlines()[-n:]
    st=""; ev=[]
    for ln in L:
        m = re.search(r"\[hb\] ontick state=(\w+)", ln)
        if m: st = m.group(1)
        if "ontick" not in ln and any(k in ln for k in ("[state]","[connect]","[browse]","[spawn]","[telemetry]","error","fail","warning")):
            ev.append(ln.rstrip()[:148])
    return st, ev

def players():
    try:
        p = subprocess.run([sys.executable, "rcon.py", "ListPlayers"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=25)
        return (p.stdout or p.stderr or "").strip().splitlines()[0][:50]
    except Exception as e:
        return "<err>"

t0=time.time(); seen=[]
while time.time()-t0 < 1500:
    st, ev = tail()
    print("%s t+%4ds state=%-12s сервер=%s" % (time.strftime("%H:%M:%S"), int(time.time()-t0), st or "?", players()), flush=True)
    for e in ev:
        if e not in seen:
            seen.append(e); print("    "+e, flush=True)
    if st == "Active":
        print(">>> АКТИВНА", flush=True); break
    if not os.popen('tasklist /FI "IMAGENAME eq ShooterGame.exe"').read().strip().endswith("N/A"):
        pass
    time.sleep(20)
