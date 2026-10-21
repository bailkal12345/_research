import io
p="dbg_rip.py"
s=io.open(p,encoding="utf-8").read()
s=s.replace("ok = E.k32.GetThreadContext(h, ctx)","ok = E.k32.GetThreadContext(h, C.cast(ctx, C.c_void_p))")
io.open(p,"w",encoding="utf-8").write(s)
print("ok")
