# -*- coding: utf-8 -*-
# Слот A (v3): именованная атрибуция 762 wait'ов dense-профиля.
#
# Метод: .bin и .wait пишутся в ОДНОМ цикле сэмплера, поэтому wait[k] соответствует
# k-му "заблокированному" сэмплу (критерий RipIsBlocked из TickProf.cpp).
# Для каждого wait'а:
#   - prev_exe: ближайший ПРЕДЫДУЩИЙ сэмпл в exe (.text) => код, в котором поток был
#     перед входом в ожидание (сторона вызывающего);
#   - next_exe: ближайший СЛЕДУЮЩИЙ exe-сэмпл => куда поток вернулся.
# Плюс: разбор 4 слов стека wait'а ([RSP], [RSP+8], [RSP+16], [RSP+24]).
import struct, collections, sys, json
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)


def modinfo(a):
    return pa.mod_of(a, mods, bases)


def is_exe_code(a):
    short, off, _ = modinfo(a)
    return short == 'ShooterGameServer.exe' and off < TXT


def fname(rva):
    return namer.name(rva) or ('sub_%X' % rva)


def exe_name(a):
    short, off, _ = modinfo(a)
    if short == 'ShooterGameServer.exe' and off < TXT:
        return fname(off)
    return None


def rip_is_blocked(r):
    short, off, issys = modinfo(r)
    if short is None:
        return True
    return bool(issys)


PROF = sys.argv[1] if len(sys.argv) > 1 else '512222984'
bdata = open(TICKPROF + r'\prof_%s.bin' % PROF, 'rb').read()
wdata = open(TICKPROF + r'\prof_%s.wait' % PROF, 'rb').read()
ns = len(bdata) // 8
rips = struct.unpack_from('<%dQ' % ns, bdata, 0)
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
wwords = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)

# выравнивание wait <-> сэмпл
pairs = []
k = 0
for i in range(ns):
    if rip_is_blocked(rips[i]):
        if k < wcnt and wwords[k * 5] == rips[i]:
            pairs.append((i, k))
            k += 1
print('профиль %s: сэмплов=%d, wait=%d, выровнено=%d' % (PROF, ns, wcnt, len(pairs)))

# предыдущий/следующий exe-сэмпл
def prev_exe(i, span=8):
    for j in range(i - 1, max(-1, i - 1 - span), -1):
        if is_exe_code(rips[j]):
            return j, rips[j]
    return None, None


def next_exe(i, span=8):
    for j in range(i + 1, min(ns, i + 1 + span)):
        if is_exe_code(rips[j]):
            return j, rips[j]
    return None, None


rows = []
agg = collections.Counter()
agg_sys = collections.Counter()
agg_sys_prev = collections.Counter()
for (i, k) in pairs:
    pj, pr = prev_exe(i)
    nj, nr = next_exe(i)
    prev = exe_name(pr) if pr else None
    nxt = exe_name(nr) if nr else None
    short, woff, _ = modinfo(wwords[k * 5])
    sysc = ('%s+0x%x' % (short, woff)) if short else 'raw'
    stack = []
    for x in wwords[k * 5:k * 5 + 5]:
        s2, o2, _ = modinfo(x)
        if s2 == 'ShooterGameServer.exe':
            stack.append('exe:0x%X %s' % (o2, fname(o2) if o2 < TXT else 'DATA'))
        elif s2:
            stack.append('%s+0x%x' % (s2, o2))
        else:
            stack.append('raw_%x' % x)
    key = (sysc, prev or '<?>')
    agg[key] += 1
    agg_sys[sysc] += 1
    agg_sys_prev[(sysc, prev or '<?>')] += 1
    rows.append(dict(sample=i, wait=k, syscall=sysc, prev=prev, next=nxt, stack=stack))

tot = len(rows)
print('\n=== syscall-классы ===')
for s, c in agg_sys.most_common():
    print('  %5d (%5.1f%%)  %s' % (c, 100.0 * c / tot, s))

print('\n=== syscall x предыдущий exe-сэмпл (вызывающая сторона) ===')
for (s, p), c in agg_sys_prev.most_common(35):
    print('  %5d (%5.1f%%)  %-22s prev=%s' % (c, 100.0 * c / tot, s, p))

# доля ожиданий, у которых предыдущий exe-сэмпл принадлежит TaskGraph/Event-классам
tg = sum(c for (s, p), c in agg_sys_prev.items() if p and ('Stall' in p or 'ProcessTask' in p or 'Wait' in p))
print('\nTaskGraph/Wait-класс как предыдущий exe-сэмпл: %d (%.1f%%)' % (tg, 100.0 * tg / tot))

with open(TICKPROF + ('\\prof_%s.waitattr.json' % PROF), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False)
print('-> %s' % (TICKPROF + ('\\prof_%s.waitattr.json' % PROF)))
