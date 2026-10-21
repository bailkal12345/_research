import io
p="scan_addunique.py"
s=io.open(p,encoding="utf-8").read()
s=s.replace('json.dumps([[n,c,lines_in[n]] for n,c,lines_in.items() if c], ensure_ascii=False)',
            'json.dumps([[n,c,ln] for (n,c),ln in counts.items() if c], ensure_ascii=False)')
io.open(p,"w",encoding="utf-8").write(s)
print("ok")
