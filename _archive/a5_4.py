import json
d=json.load(open(r"C:\Dev\_research\dump_index.json",encoding="utf-8"))
print(type(d))
if isinstance(d,dict):
    ks=list(d.keys()); print("keys sample:",ks[:10]); print("count",len(ks))
    for k in ks:
        if "ProcessInternal" in k or "ProcessContextOpcode" in k or "UFunction::Invoke" in k:
            print(k,"->",d[k])
else:
    print("len",len(d)); print(d[:3])
