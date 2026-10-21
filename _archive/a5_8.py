import re
p=r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
f=open(p,encoding="utf-8",errors="replace")
f.seek(5849641-600000)
buf=f.read(1400000)
for m in re.finditer(r"(?m)^[A-Za-z_].*\b(ProcessInternal|ProcessContextOpcode)\b.*$", buf):
    print(m.start()+5849641-600000, "|", m.group(0)[:150])
