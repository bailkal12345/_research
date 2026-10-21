import mmap, re
p = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
data = open(p, "rb").read()
for pat in (rb"net\.MaxNetTickRate", rb"MaxNetTickRate", rb"t\.MaxFPS", rb"ServerMaxTickRate"):
    idxs = [m.start() for m in re.finditer(pat, data)][:4]
    print("%-22s %d вхождений, примеры: %s" % (pat.decode(), len([m for m in re.finditer(pat, data)]), idxs))
