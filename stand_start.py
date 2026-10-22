# -*- coding: utf-8 -*-
# Server1 stand startup: Genesis + prod config §2 (ARCH.md) + post-boot checklist.
# IMPORTANT (doit6 §2): TickProf.maxfps 60 and fixclamp 0 must be set VIA RCON right after
# boot - the ini value does not reach runtime.
import os, re, socket, struct, subprocess, sys, time, io

EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
CFG = r'C:\asmdata\Servers\Server1\ShooterGame\Saved\Config\WindowsServer'
GUS = os.path.join(CFG, 'GameUserSettings.ini')
MAP = sys.argv[1] if len(sys.argv) > 1 else 'Genesis'
PORT = 32330
PW = '0ub7OuAD6V68cbzc'
HOSTS = ['127.0.0.1', '192.168.8.218']


def _pack(rid, payload):
    b = payload.encode('utf-8') + b'\x00\x00'
    return struct.pack('<ii', len(b) + 8, rid) + b


def rcon(cmd, timeout=8):
    for h in HOSTS:
        try:
            s = socket.create_connection((h, PORT), 4)
        except Exception:
            continue
        try:
            s.settimeout(timeout)
            s.sendall(_pack(1, PW))
            try:
                s.recv(4096)
            except Exception:
                pass
            s.sendall(_pack(2, cmd))
            buf = b''
            try:
                while True:
                    d = s.recv(65536)
                    if not d:
                        break
                    buf += d
            except socket.timeout:
                pass
            s.close()
            return buf.decode('utf-8', 'replace')
        except Exception:
            continue
    return None


def ensure_rcon_keys():
    """The engine loses RCON keys when writing GameUserSettings.ini => we restore them."""
    raw = open(GUS, 'rb').read()
    txt = raw.decode('utf-16', 'replace')
    need = {'RCONEnabled': 'True', 'RCONPort': str(PORT), 'ServerAdminPassword': PW}
    missing = [k for k, v in need.items() if not re.search(r'(?m)^%s=%s\s*$' % (k, re.escape(v)), txt)]
    if missing:
        lines = [l for l in txt.splitlines() if not any(l.startswith(k + '=') for k in need)]
        lines += ['%s=%s' % (k, v) for k, v in need.items()]
        open(GUS, 'wb').write(('\n'.join(lines)).encode('utf-16'))
        print('  RCON keys restored:', missing)
    else:
        print('  RCON keys in place')
    # protect against overwrite by the engine: read-only
    try:
        os.chmod(GUS, 0o444)
        print('  GameUserSettings.ini protected (read-only)')
    except Exception as e:
        print('  chmod failed:', e)


def start():
    args = ("%s?listen?MultiHome=192.168.8.218?Port=7777?QueryPort=27015?MaxPlayers=70"
            "?AllowCrateSpawnsOnTopOfStructures=True -EnableIdlePlayerKick -NoBattlEye -insecure"
            " -forcerespawndinos -servergamelog -servergamelogincludetribelogs -ServerRCONOutputTribeLogs"
            " -NoHangDetection -noundermeshchecking -noundermeshkilling -nosteamclient -game -server -log"
            " -MinimumTimeBetweenInventoryRetrieval=3600 -newsaveformat -usestore -BackupTransferPlayerDatas") % MAP
    # Start with the working directory = Binaries/Win64
    cwd = os.path.dirname(EXE)
    p = subprocess.Popen([EXE] + args.split(), cwd=cwd,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('  started pid=%d map=%s' % (p.pid, MAP))
    return p


def wait_rcon(limit=240):
    t0 = time.time()
    while time.time() - t0 < limit:
        if rcon('status') is not None:
            print('  RCON responding after %.0f s' % (time.time() - t0))
            return True
        time.sleep(5)
    return False


def apply_prod_config():
    """Prod config §2 ARCH.md + doit6 checklist: maxfps 60 and fixclamp 0 - right after boot."""
    seq = [
        ('TickProf.maxfps 60', 'tickrate 60 (the ini value does not reach runtime)'),
        ('TickProf.fixclamp 0', 'remove the tickrate clamp (120 -> 100000)'),
        ('TickProf.fncache 1', 'cache UClass::FindFunctionByName'),
        ('TickProf.iscache 1', 'cache UStruct::IsChildOf'),
        ('TickProf.cachename 1', 'cache DoGetCanvasByName'),
        ('TickProf.nochart 1', 'disable UEngine::TickFPSChart'),
        ('TickProf.overlaptrim 2', 'prod config: overlaptrim 2 (v1 scheme)'),
        ('TickProf.status', 'feature status'),
    ]
    for cmd, desc in seq:
        r = rcon(cmd)
        print('  %-28s %-42s -> %s' % (cmd, desc, (r or 'NO RESPONSE').replace('\x00', ' ')[:120]))
        time.sleep(1.5)


if __name__ == '__main__':
    print('== preparation ==')
    ensure_rcon_keys()
    print('== startup ==')
    start()
    print('== waiting for RCON ==')
    if not wait_rcon():
        print('!! RCON did not come up')
        sys.exit(1)
    time.sleep(20)  # let the world finish loading
    print('== prod config ==')
    apply_prod_config()
    print('== check ==')
    for c in ('TickProf.status', 'status'):
        r = rcon(c)
        print('  %s -> %s' % (c, (r or '').replace('\x00', ' ')[:400]))
