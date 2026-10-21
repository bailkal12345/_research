import re
p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()
# ASCII tokens containing 'Save' or 'save'
res = {}
for m in re.finditer(rb'[ -~]{4,80}', data):
    s = m.group().decode('latin1')
    if 'ave' in s and ('Save' in s or 'save' in s):
        res.setdefault(s, m.start())
print("ASCII tokens with 'Save/save':", len(res))
keys = sorted(res.items(), key=lambda kv: kv[1])
for s,a in keys:
    print("  %08X  %s" % (a, s))
