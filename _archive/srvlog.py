import io, sys, glob, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\logs'
ps = sorted(glob.glob(d + r'\*.log*'), key=os.path.getmtime, reverse=True)
for p in ps[:3]:
    print('%s mtime=%s size=%d' % (os.path.basename(p),
          time.strftime('%H:%M:%S', time.localtime(os.path.getmtime(p))),
          os.path.getsize(p)))
s = io.open(ps[0], encoding='utf-8', errors='replace').read().splitlines()
print('--- tail 25 ---')
for l in s[-25:]:
    print(l)
# hunt join/disconnect keywords across recent files
print('--- keyword hunt ---')
for p in ps[:4]:
    for l in io.open(p, encoding='utf-8', errors='replace').read().splitlines():
        if any(k in l for k in ('Join', 'Login', 'BotPlayer', 'Disconnected', 'Closed')):
            print(os.path.basename(p) + ' | ' + l)
