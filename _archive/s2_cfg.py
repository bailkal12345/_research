import io, re
p = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\Config\WindowsServer\GameUserSettings.ini"
raw = open(p, "rb").read()
enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
s = raw.decode(enc)
print("кодировка:", enc)
print("было:", [l.strip() for l in s.splitlines() if "NetServerMaxTickRate" in l])
s = re.sub(r"NetServerMaxTickRate=\d+", "NetServerMaxTickRate=60", s)
if "NetServerMaxTickRate" not in s:
    s = s.rstrip() + "\r\nNetServerMaxTickRate=60"
open(p, "wb").write(s.encode(enc))
print("стало:", [l.strip() for l in s.splitlines() if "NetServerMaxTickRate" in l])
