# -*- coding: utf-8 -*-
"""
Step-by-step manual execution of doit.txt directive §5 (no background drivers).

    python manual.py state              bench state
    python manual.py deploy <archive>   deploy a map (only deploy_map.py)
    python manual.py ready              wait for the world to boot, show tid
    python manual.py config             prod configuration (5 optimizations, stock clamp)
    python manual.py idle [sec]         wait for the end of the world save
    python manual.py window <sec>       measurement window: t/s, ms CPU/tick, contamination flag
    python manual.py profile [sec]      take a profile (risky, do it last)
    python manual.py census             census of tick functions and intersections
    python manual.py saveworld <n>      stage 3: n SaveWorld runs with freeze measurement
    python manual.py apply <command>    a single RCON command
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RCON_HOST", "192.168.8.218")
os.environ.setdefault("RCON_PORT", "27020")
sys.path.insert(0, HERE)

import freeze  # noqa: E402
import rcon  # noqa: E402
import slot_measure as S  # noqa: E402
import threadcpu  # noqa: E402

CRASH_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\Logs"


def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def say(text):
    print("%s  %s" % (stamp(), text), flush=True)


def wl(text):
    with open(os.path.join(HERE, "worklog.md"), "a", encoding="utf-8") as f:
        f.write("\n## %s MANUAL STEP\n%s\n" % (stamp(), text))


def server_pid():
    p = threadcpu.find_pid()
    return (p[0] if isinstance(p, (list, tuple)) else p) if p else 0


def cmd_state():
    pid = server_pid()
    say("ShooterGameServer process: %s" % (pid or "NONE"))
    tid = S.game_tid()
    say("game thread tid from the plugin log: %s" % (tid or "NONE (world not initialized)"))
    if pid:
        fz, val = freeze.is_frozen(pid, probe=10.0)
        say("process CPU: %.3f -> %s" % (val, "FREEZE" if fz else "running"))
    try:
        r = rcon.rcon("ListPlayers", timeout=8)
        say("RCON: %s" % r.strip()[:80])
    except Exception as exc:  # noqa: BLE001
        say("RCON: NOT RESPONDING (%s)" % type(exc).__name__)
    st = S.ark_state("genesis")
    for n, (m, sz) in sorted(st.items()):
        say("save file %-34s %8.1f MB  mtime %s"
            % (n, sz / 1048576.0, datetime.datetime.fromtimestamp(m).strftime("%H:%M:%S")))
    return 0 if pid else 1


def cmd_ready():
    say("waiting for the world to boot (up to 15 min)")
    end = time.time() + 900
    while time.time() < end:
        pid = server_pid()
        if not pid:
            say("no process - deploy failed or it crashed")
            return 1
        tid = S.game_tid()
        if tid:
            try:
                rcon.rcon("ListPlayers", timeout=5)
                say("READY: pid %s, tid %s" % (pid, tid))
                return 0
            except Exception:
                pass
        fz, val = freeze.is_frozen(pid, probe=15.0)
        say("  boot: CPU=%.2f %s" % (val, "(FREEZE!)" if fz else ""))
        if fz:
            say("freeze - the bench will not come up, the deploy needs a restart")
            return 2
        time.sleep(20)
    say("did not come up within 15 min")
    return 3


def cmd_deploy(archive):
    say("DEPLOY %s (only deploy_map.py)" % archive)
    wl("MANUAL DEPLOY: %s" % archive)
    p = subprocess.run([sys.executable, os.path.join(HERE, "deploy_map.py"), "--archive", archive],
                       encoding="utf-8", errors="replace", timeout=1800)
    say("deploy_map.py finished with exit code %s" % p.returncode)
    return p.returncode


def cmd_config():
    say("prod configuration: stock clamp, 5 optimizations")
    for c in S.PROD_CONFIG:
        S.cmd(c)
        time.sleep(3)
        say("  %-28s -> %s" % (c, (S.cmd("TickProf.cachestat") or "")[:0] or "ok"))
    return 0


def cmd_idle(sec):
    quiet = min(90, int(sec)) if sec else 90
    say("waiting for the end of the world save (%d s quiet)" % quiet)
    ok = S.save_idle("genesis", quiet=quiet, limit=sec or 900)
    say("save settled: %s" % ok)
    return 0 if ok else 1


def cmd_idle_after(limit):
    """First wait for the START of the save, then for its END.

    The simple variant (90 s of quiet) hit the window: files were not changing
    during the pause before the autosave, and the window started seconds before
    its beginning. Here we wait for the very fact of file change and measure
    only after it finishes.
    """
    say("waiting for the START of the world save (up to %d s)" % limit)
    end = time.time() + limit
    base = S.ark_state("genesis")
    started = False
    while time.time() < end:
        cur = S.ark_state("genesis")
        if cur != base:
            say("  the save started at %s" % stamp())
            base, started = cur, True
            break
        time.sleep(15)
    if not started:
        say("the save did not start within the allotted time - measuring as is")
        return 0
    say("waiting for the END of the save (120 s quiet)")
    S.save_idle("genesis", quiet=120, limit=900)
    say("save settled, can measure: %s" % stamp())
    return 0


def cmd_loo(text, sec, card="genesis"):
    """Leave-one-out: apply the command -> wait for the autosave to finish -> window."""
    say("applying: %s" % text)
    S.cmd(text)
    time.sleep(5)
    say("waiting for the end of the world save per protocol")
    S.save_idle(card, quiet=120, limit=600)
    return cmd_window(int(sec))


def cmd_status():
    """Checking the prod config by list (item 1.5 of the directive)."""
    say("checking the prod config:")
    for c in ("TickProf.cachestat", "TickProf.verify"):
        S.cmd(c)
        time.sleep(4)
    for ln in S.log_tail(40):
        low = ln.lower()
        if any(k in low for k in ("fncache", "iscache", "canvas", "nochart", "overlaptrim",
                                  "concurrent", "tickclamp", "maxfps", "cache:")):
            say("  " + ln)
    return 0


def cmd_arkhash(tag):
    """Recording the size and hash of .ark (item 1.1)."""
    import hashlib
    d = S.ARK_DIR
    say(".ark state [%s]:" % tag)
    for n in sorted(os.listdir(d)):
        if n.lower().endswith(".ark") and "_" not in n[:-4]:
            f = os.path.join(d, n)
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                while True:
                    b = fh.read(1 << 20)
                    if not b:
                        break
                    h.update(b)
            say("  %-16s %12d bytes  sha256=%s" % (n, os.path.getsize(f), h.hexdigest()[:24]))
    wl(".ark recording [%s] done" % tag)
    return 0


def cmd_window(sec):
    seconds = int(sec)
    tid = S.game_tid()
    if not tid:
        say("NO tid - nothing to measure")
        return 2
    say("window %d s, GameThread tid=%s" % (seconds, tid))
    res = S.window(tid, seconds, S.newest_crash(), "genesis")
    say("  t/s = %.2f | GameThread CPU = %.3f s/s | %.2f ms CPU/tick"
        % (res["tps"], res["cpu"], res["ms_tick"]))
    say("  health: %s" % res["why"])
    say("  contaminated by the world save: %s" % res.get("contaminated"))
    wl("window %d s: t/s=%.2f cpu=%.3f ms/tick=%.2f contaminated=%s"
       % (seconds, res["tps"], res["cpu"], res["ms_tick"], res.get("contaminated")))
    return 0 if (res["healthy"] and res["tps"] > 0 and not res.get("contaminated")) else 1


def cmd_profile(sec):
    seconds = int(sec or 60)
    S.cmd("TickProf.ticklist")
    time.sleep(3)
    say("taking a %d s profile (risky - doing it as the last step)" % seconds)
    binp = S.profile(seconds)
    say("profile: %s" % os.path.basename(binp))
    for ln in S.log_tail(6):
        say("  " + ln)
    pid = server_pid()
    say("server after the profile: %s" % ("alive" if pid else "DEAD"))
    return 0 if pid else 1


def cmd_census():
    for c in ("TickProf.ticklist", "TickProf.ticksets", "TickProf.overlapsizes"):
        S.cmd(c)
        time.sleep(8)
    time.sleep(10)
    say("census:")
    for ln in S.log_tail(40):
        if any(k in ln for k in ("ticklist:", "ticksets:", "overlapsizes:")):
            say("  " + ln)
    return 0


def cmd_saveworld(n):
    say("Stage 3: SaveWorld, %d run(s)" % n)
    out = S.saveworld_freeze(int(n))
    for i, v in enumerate(out, 1):
        say("  run %d: freeze %.0f ms %s"
            % (i, v, "- 500 ms threshold EXCEEDED, ticket for the backlog" if v > 500 else ""))
    wl("Stage 3 SaveWorld: %s ms" % ["%.0f" % v for v in out])
    return 0


def cmd_apply(text):
    say("command: %s" % text)
    say("response: %s" % str(S.cmd(text))[:300])
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("state")
    sub.add_parser("ready")
    sub.add_parser("config")
    sub.add_parser("census")
    p = sub.add_parser("deploy"); p.add_argument("archive")
    p = sub.add_parser("idle"); p.add_argument("sec", nargs="?", default=0, type=int)
    p = sub.add_parser("idle-after"); p.add_argument("sec", nargs="?", default=900, type=int)
    p = sub.add_parser("window"); p.add_argument("sec", type=int)
    p = sub.add_parser("profile"); p.add_argument("sec", nargs="?", default=60, type=int)
    p = sub.add_parser("saveworld"); p.add_argument("n", nargs="?", default=2, type=int)
    p = sub.add_parser("apply"); p.add_argument("text")
    sub.add_parser("status")
    p = sub.add_parser("arkhash"); p.add_argument("tag", nargs="?", default="-")
    p = sub.add_parser("loo"); p.add_argument("text"); p.add_argument("sec", nargs="?", default=240, type=int)
    a = ap.parse_args()

    fn = {"state": cmd_state, "ready": cmd_ready, "config": cmd_config, "census": cmd_census,
          "idle": cmd_idle, "window": cmd_window, "profile": cmd_profile,
          "saveworld": cmd_saveworld, "apply": cmd_apply}
    if a.cmd == "deploy":
        return cmd_deploy(a.archive)
    if a.cmd in ("state", "ready", "config", "census"):
        return fn[a.cmd]()
    if a.cmd == "idle-after":
        return cmd_idle_after(a.sec)
    if a.cmd in ("idle", "window", "profile"):
        return fn[a.cmd](a.sec)
    if a.cmd == "saveworld":
        return fn[a.cmd](a.n)
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "arkhash":
        return cmd_arkhash(a.tag)
    if a.cmd == "loo":
        return cmd_loo(a.text, a.sec)
    return fn[a.cmd](a.text)


if __name__ == "__main__":
    sys.exit(main())