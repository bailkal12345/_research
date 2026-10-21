import io, json
idx = json.load(io.open("dump_index.json", encoding="utf-8"))
keys = [k for k in idx if "Stasis" in k]
print("функций со Stasis:", len(keys))
for k in sorted(keys)[:24]:
    print("   %-64s line %s" % (k[:64], idx[k]))
