import io, re
p = "stackdump.py"
src = io.open(p, encoding="utf-8").read()

new_ctx = '''CONTEXT_CONTROL = 0x00100001  # CONTROL|INTEGER


class CONTEXT(C.Structure):
    """x64 CONTEXT (1232 байт). Порядок полей = порядок в winnt.h."""

    _fields_ = [
        ("P1Home", C.c_ulonglong), ("P2Home", C.c_ulonglong), ("P3Home", C.c_ulonglong),
        ("P4Home", C.c_ulonglong), ("P5Home", C.c_ulonglong), ("P6Home", C.c_ulonglong),
        ("ContextFlags", W.DWORD), ("MxCsr", W.DWORD),
        ("SegCs", W.DWORD), ("SegDs", W.DWORD), ("SegEs", W.DWORD),
        ("SegFs", W.DWORD), ("SegGs", W.DWORD), ("SegSs", W.DWORD),
        ("EFlags", W.DWORD),
        ("Dr0", C.c_ulonglong), ("Dr1", C.c_ulonglong), ("Dr2", C.c_ulonglong),
        ("Dr3", C.c_ulonglong), ("Dr6", C.c_ulonglong), ("Dr7", C.c_ulonglong),
        ("Rax", C.c_ulonglong), ("Rcx", C.c_ulonglong), ("Rdx", C.c_ulonglong),
        ("Rbx", C.c_ulonglong), ("Rsp", C.c_ulonglong), ("Rbp", C.c_ulonglong),
        ("Rsi", C.c_ulonglong), ("Rdi", C.c_ulonglong),
        ("R8", C.c_ulonglong), ("R9", C.c_ulonglong), ("R10", C.c_ulonglong),
        ("R11", C.c_ulonglong), ("R12", C.c_ulonglong), ("R13", C.c_ulonglong),
        ("R14", C.c_ulonglong), ("R15", C.c_ulonglong),
        ("Rip", C.c_ulonglong),
        ("FltSave", C.c_ubyte * 512),
        ("VectorRegister", C.c_ubyte * (26 * 16)),
        ("VectorControl", C.c_ulonglong),
        ("DebugControl", C.c_ulonglong),
        ("LastBranchToRip", C.c_ulonglong),
        ("LastBranchFromRip", C.c_ulonglong),
        ("LastExceptionToRip", C.c_ulonglong),
        ("LastExceptionFromRip", C.c_ulonglong),
    ]


assert C.sizeof(CONTEXT) == 1232, C.sizeof(CONTEXT)
'''

start = src.index("CONTEXT_CONTROL = ")
end = src.index("def find_pid(")
src = src[:start] + new_ctx + "\n\n" + src[end:]
src = src.replace("ctx.ContextFlags = CONTEXT_CONTROL", "ctx.ContextFlags = CONTEXT_CONTROL")
src = src.replace("rip, rsp = ctx.Eip, ctx.Esp", "rip, rsp = ctx.Rip, ctx.Rsp")
io.open(p, "w", encoding="utf-8").write(src)
print("patched")
