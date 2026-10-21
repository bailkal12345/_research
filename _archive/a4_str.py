import re, sys
p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()
print("size", len(data))
pats = [rb'[ -~]{6,120}']
found = {}
keys = [b'SavedWorldSaveInterval', b'AutoSave', b'autosave', b'SaveWorldInterval',
        b'SAVEGAME_', b'NoDialog', b'SaveInterval', b'SaveGameInterval',
        b'IncrementalSave', b'shootergame.Save', b'shootergame.save',
        b'ServerSaveWorld', b'SaveWorld', b'GCObject', b'GameUserSettings']
for k in keys:
    idxs = [m.start() for m in re.finditer(re.escape(k), data)]
    print("%-28s %d" % (k.decode(), len(idxs)))
    for i in idxs[:12]:
        # find ascii run boundaries
        a = i
        while a > 0 and 32 <= data[a-1] < 127: a -= 1
        b = i
        while b < len(data) and 32 <= data[b] < 127: b += 1
        s = data[a:b].decode('latin1')
        print("    @%08X  %s" % (a, s[:150]))
