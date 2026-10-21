# -*- coding: utf-8 -*-
# Слот A (v9): владелец ожидания по [RSP] ПЕРВОГО exe-сэмпла ПОСЛЕ wait'а.
# Логика: поток стоит в syscall; когда ожидание кончилось, он возвращается в
# вызывающий код. [RSP] этого exe-сэмпла = адрес возврата = вызывающий.
# Валидация: на известной группе (91 шт, стек указывает в ProcessTasksNamedThread)
# метод должен дать TaskGraph-функции.
import struct, collections, sys, json
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)

PROF = sys.argv[1] if len(sys.argv) > 1 else '512222984'
bdata = open(TICKPROF + r'\prof_%s.bin' % PROF, 'rb').read()
rdata = open(TICKPROF + r'\prof_%s.ret' % PROF, 'rb').read()
wdata = open(TICKPROF + r'\prof_%s.wait' % PROF, 'wb' if False else 'rb').read()
ns = len(bdata) // 8
rips = struct.unpack_from('<%dQ' % ns, bdata, 0)
nret = len(rdata) // 8
rets = struct.unpack_from('<%dQ' % nret, rdata, 0)
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
wwords = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)


def mi(a):
    return pa.mod_of(a, mods, bases)


def blocked(r):
    short, off, issys = mi(r)
    return True if short is None else bool(issys)


def exe_fn(a):
    short, off, _ = mi(a)
    if short == 'ShooterGameServer.exe' and off < TXT:
        return namer.name(off) or ('sub_%X' % off)
    return None


def stack_exe(a):
    short, off, _ = mi(a)
    if short == 'ShooterGameServer.exe':
        if off >= TXT:
            return 'exeDATA+0x%X' % off
        return 'exe:0x%X %s' % (off, namer.name(off) or ('sub_%X' % off))
    if short:
        return '%s+0x%x' % (short, off)
    return 'raw_%x' % a


pairs = []
k = 0
for i in range(ns):
    if blocked(rips[i]):
        if k < wcnt and wwords[k * 5] == rips[i]:
            pairs.append((i, k))
            k += 1
print('профиль %s: сэмплов=%d wait=%d выровнено=%d' % (PROF, ns, wcnt, len(pairs)))


def next_exe_sample(i, span=6):
    for j in range(i + 1, min(ns, i + 1 + span)):
        if exe_fn(rips[j]):
            return j
    return None


owner = collections.Counter()
owner_by_group = collections.defaultdict(collections.Counter)
rows = []
for (i, k) in pairs:
    # идентификатор группы по 4-м словам стека wait'а
    sig = tuple(stack_exe(x) for x in wwords[k * 5:k * 5 + 5])
    j = next_exe_sample(i)
    own = None
    if j is not None and j < nret:
        r = rets[j]
        own = exe_fn(r)          # [RSP] = вызывающий
        if own is None:
            own = '<' + stack_exe(r) + '>'
    owner[own or '<?>'] += 1
    owner_by_group[sig][own or '<?>'] += 1
    rows.append((i, k, own, sig))

tot = len(pairs)
print('\n=== ВЛАДЕЛЕЦ ОЖИДАНИЯ (ret первого exe-сэмпла после wait) ===')
for o, c in owner.most_common(30):
    print('  %5d (%5.1f%%)  %s' % (c, 100.0 * c / tot, o))

named = sum(c for o, c in owner.items() if o and o.startswith(('ProcessTask', 'Stall', 'Tick', 'FTick')) )
allnamed = sum(c for o, c in owner.items() if o and not o.startswith('<') and o != '<?>')
print('\nназвано (ret указывает в exe-код): %d из %d (%.1f%%)' % (allnamed, tot, 100.0 * allnamed / tot))

print('\n=== по группам стека ===')
for sig, cc in sorted(owner_by_group.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(cc.values())
    if n < 5:
        continue
    print('\n  группа (%d шт): %s' % (n, ' | '.join(sig)))
    for o, c in cc.most_common(6):
        print('      %5d  %s' % (c, o))
