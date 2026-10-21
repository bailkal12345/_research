# -*- coding: utf-8 -*-
# Слот A: выравнивание wait-записей с потоком сэмплов (.bin) -> "кто вызвал ожидание".
# Формат .bin: 8 байт на сэмпл = RIP. Формат .wait: 5 слов (rip, [RSP], [RSP+8], [RSP+16], [RSP+24]).
import struct, collections, sys, bisect
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)


def loc(a):
    short, off, _ = pa.mod_of(a, mods, bases)
    if short == 'ShooterGameServer.exe':
        if off >= TXT:
            return 'exe@Data+%x' % off
        return 'exe:0x%X %s' % (off, namer.name(off) or 'sub_%X' % off)
    if short:
        return '%s+%x' % (short, off)
    return 'raw_%x' % a


def fname(rva):
    return namer.name(rva) or ('sub_%X' % rva)


PROF = '512222984'
bdata = open(TICKPROF + r'\prof_%s.bin' % PROF, 'rb').read()
rdata = open(TICKPROF + r'\prof_%s.ret' % PROF, 'rb').read()
wdata = open(TICKPROF + r'\prof_%s.wait' % PROF, 'rb').read()

ns = len(bdata) // 8
rips = struct.unpack_from('<%dQ' % ns, bdata, 0)
rets = struct.unpack_from('<%dQ' % (len(rdata) // 8), rdata, 0)
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
wwords = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)
print('сэмплов .bin=%d, .ret=%d, wait=%d' % (ns, len(rets), wcnt))

# --- проверка выравнивания: wait[k].rip должен совпадать с RIP очередного "заблокированного" сэмпла ---
# blocked = RIP в системной DLL (is_sys) по модулям
def is_sys_rip(r):
    short, off, issys = pa.mod_of(r, mods, bases)
    return bool(issys) and short is not None


pairs = []
k = 0
for i in range(ns):
    r = rips[i]
    if is_sys_rip(r):
        if k < wcnt and wwords[k * 5] == r:
            pairs.append((i, k))
            k += 1
        else:
            print('РАСХОЖДЕНИЕ на сэмпле %d (rip=%s): ожидалось wait[%d].rip=%s' % (
                i, loc(r), k, loc(wwords[k * 5]) if k < wcnt else '-'))
            break
print('выровнено wait-записей: %d из %d (k=%d)' % (len(pairs), wcnt, k))

# --- для каждого wait: RIP предыдущих сэмплов (контекст вызова) ---
callers = collections.Counter()
callers2 = collections.Counter()
detail = []
for (i, k) in pairs:
    prev = [rips[j] for j in range(max(0, i - 4), i)]
    pname = []
    for r in reversed(prev):
        short, off, _ = pa.mod_of(r, mods, bases)
        pname.append(fname(off) if short == 'ShooterGameServer.exe' else loc(r))
    ctx = ' | '.join(pname)
    callers[ctx] += 1
    # [RSP] предыдущего сэмпла = адрес возврата из функции, в которой стоял поток
    pr = rets[i - 1] if i > 0 else 0
    short, off, _ = pa.mod_of(pr, mods, bases)
    prn = fname(off) if short == 'ShooterGameServer.exe' else loc(pr)
    callers2[(prn, ctx)] += 1
    detail.append((i, k, ctx, prn, [loc(x) for x in wwords[k * 5:k * 5 + 5]]))

print('\n=== контекст вызова (RIP предыдущих 4 сэмплов) ===')
for ctx, c in callers.most_common(25):
    print('  %5d (%4.1f%%)  %s' % (c, 100.0 * c / len(pairs), ctx))

print('\n=== (ret предыдущего сэмпла, контекст) ===')
for (prn, ctx), c in callers2.most_common(25):
    print('  %5d (%4.1f%%)  ret=%-45s ctx=%s' % (c, 100.0 * c / len(pairs), prn, ctx))

import json
with open(TICKPROF + ('\\prof_%s.waitctx.json' % PROF), 'w', encoding='utf-8') as f:
    json.dump(detail, f, ensure_ascii=False)
print('\nдетализация -> %s' % (TICKPROF + ('\\prof_%s.waitctx.json' % PROF)))
