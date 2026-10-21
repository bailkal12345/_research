import json,os
d=json.load(open(r"C:\Dev\_research\dump_index.json",encoding="utf-8"))
print("compress ->", d["compress"], "| type", type(d["compress"]))
for k in ["UObject::ProcessInternal","UFunction::Invoke","UObject::ProcessContextOpcode","UObject::CallFunction","UObject::execLocalVariable","UObject::execDynamicCast","UObject::execJump"]:
    print(k,"->",d.get(k))
