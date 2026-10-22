# -*- coding: utf-8 -*-
# Waiting for the stand to be ready: RCON responds + TickProf loaded.
import sys, time, subprocess
sys.path.insert(0, r'C:\Dev\_research')
import rcon3

LOG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log'


def proc_alive(pid=6620):
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          "(Get-Process -Id %d -ErrorAction SilentlyContinue) -ne $null" % pid],
                         capture_output=True, text=True).stdout.strip()
    return out.lower() == 'true'


if __name__ == '__main__':
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    for i in range(limit):
        r = rcon3.rcon('status', timeout=3.0, wait=0.8)
        alive = proc_alive()
        ok = bool(r and len(r.strip()) > 3)
        print('iter %2d: alive=%s rcon=%s %s' % (i, alive, ok, (r or '')[:90].replace('\n', ' ')))
        if ok:
            print('READY')
            break
        if not alive:
            print('PROCESS DIED')
            break
        time.sleep(15)
