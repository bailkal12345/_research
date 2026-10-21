import io, sys, glob, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = r'C:\Games\ARK_SE_game_v361\ShooterGame\Binaries\Win64\logs'
KEY = ('опознан', 'подмена', 'JoinSession', '[browse]', '[travel]', '[pending]',
       '[state]', 'не найден', 'armed', 'arm ', '[connect] attempt', 'console',
       'SearchResults=', 'entry[0] raw')
RX = ('[hb]', 'hook pass', '[net]', 'entry[', 'telemetry')
pat = 'ArkApi_12508*'
if len(sys.argv) > 1:
    pat = 'ArkApi_*' if sys.argv[1] == 'all' else sys.argv[1]
lines = []
for p in glob.glob(os.path.join(d, pat)):
    lines += [(os.path.basename(p), l) for l in
              io.open(p, encoding='utf-8', errors='replace').read().splitlines()]
out = [(f, l) for f, l in lines if not any(k in l for k in RX)]
print('--- %d lines ---' % len(out))
for f, l in out[-int(sys.argv[2]) if len(sys.argv) > 2 else -25:]:
    sys.stdout.buffer.write((f[-7:] + ' | ' + l + '\n').encode('utf-8'))
