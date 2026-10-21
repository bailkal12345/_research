import json
d=json.load(open(r"C:\Dev\_research\dump_index.json",encoding="utf-8"))
f=open(r"C:\Dev\ARK_SE_code_dump\game_aquatica.c",encoding="utf-8",errors="replace")
def grab(name, span=12000):
    off=d[name]
    f.seek(max(0,off-400))
    buf=f.read(span)
    # cut at next top-level function marker
    idx=buf.find("\nvoid ",10)
    open(r"C:\Dev\_research\out_"+name.replace(":","_")+".c","w",encoding="utf-8").write(buf)
    print("=== ",name, "off",off, "len",len(buf))
for n in ["UObject::ProcessInternal","UFunction::Invoke"]:
    grab(n)
