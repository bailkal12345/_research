import os, sys, time
sys.path.insert(0, r"C:\Dev\_research")
import rcon, threadcpu
LOG = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"
def cmd(t, to=10):
    try: return rcon.rcon(t, timeout=to)
    except Exception as e: return "<%s>" % type(e).__name__
def tail(n=40):
    with open(LOG, encoding="utf-8", errors="replace") as f: return [x.rstrip() for x in f.readlines()[-n:]]
def tid():
    for ln in reversed(tail(400)):
        if "game thread tid=" in ln: return int(ln.strip().split("tid=")[-1])
    return 0
def cpu(t, n=2):
    v=[]
    for _ in range(n):
        x=threadcpu.cpu_times(t)
        if x is not None: v.append(x)
        time.sleep(1)
    return (v[-1]-v[0])/max(1,len(v)-1) if len(v)>1 else 0.0
def meas(label, t, s=25):
    c0=cpu(t); cmd("TickProf.perf %d"%s); time.sleep(s+5); c1=cpu(t)
    fr=wl=0
    for ln in reversed(tail(60)):
        if "perf окно" in ln:
            for tok in ln.split():
                if tok.startswith("frames="): fr=int(tok.split("=")[1])
                if tok.startswith("wall="): wl=float(tok.split("=")[1].rstrip("s"))
            break
    print("   %-28s тиков/с %7.1f | cpu %.3f | %.2f мс/тик" % (label, fr/wl if wl else 0, c1, 1000*c1/(fr/wl) if wl else 0), flush=True)
t = tid()
print("tid=%d" % t, flush=True)
cmd("TickProf.maxfps 200000"); time.sleep(5)
meas("до отключения скелета", t)
cmd("TickProf.tickoff SkeletalMesh"); time.sleep(10)
for ln in tail(20):
    if "tickoff" in ln: print("   " + ln.split(" ",1)[-1])
meas("без SkeletalMesh", t)
cmd("TickProf.tickclasses"); time.sleep(12)
for ln in tail(20):
    if "tickclasses" in ln or ln.strip().startswith(("1 ","2 ","3 ")): print("   " + ln.split(" ",1)[-1])
