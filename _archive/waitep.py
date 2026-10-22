# -*- coding: utf-8 -*-
# Слот A (v11): ЭПИЗОДЫ ожидания и их атрибуция.
# Wait'ы группируются в непрерывные серии "заблокированных" сэмплов (= один эпизод
# ожидания). Для каждого эпизода:
#   - last_exe  = exe-сэмпл непосредственно ПЕРЕД входом в ожидание (код, из которого
#                 поток ушёл в ожидание);
#   - first_exe = exe-сэмпл сразу ПОСЛЕ выхода из ожидания (куда поток вернулся).
# Это даёт именованного владельца ожидания без разбора глубины стека.
import struct, collections, sys, json
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
PROF = sys.argv[1] if len(sys.argv) > 1 else '512222984'
mods, bases = pa.load_modules(TICKPROF + r'\prof_%s.modules.txt' % PROF)
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)

bdata = open(TICKPROF + r'\prof_%s.bin' % PROF, 'rb').read()
wdata = open(TICKPROF + r'\prof_%s.wait' % PROF, 'rb').read()
ns = len(bdata) // 8
rips = struct.unpack_from('<%dQ' % ns, bdata, 0)
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
wwords = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)


def mi(a):
    return pa.mod_of(a, mods, bases)


def blocked(r):
    short, off, issys = mi(r)
    return True if short is None else bool(issys)


def exe_leaf(a):
    short, off, _ = mi(a)
    if short == 'ShooterGameServer.exe' and off < TXT:
        return namer.name(off) or ('sub_%X' % off)
    return None


def exe_data(a):
    short, off, _ = mi(a)
    if short == 'ShooterGameServer.exe' and off >= TXT:
        return 'exeDATA+0x%X' % off
    return None


# --- маска блокировки по сэмплам (из .bin) ---
mask = [blocked(r) for r in rips]
# --- сопоставление wait-записей с сэмплами ---
pairs = []
k = 0
for i in range(ns):
    if mask[i]:
        if k < wcnt and wwords[k * 5] == rips[i]:
            pairs.append(i)
            k += 1
print('профиль %s: сэмплов=%d, wait=%d, выровнено=%d' % (PROF, ns, wcnt, len(pairs)))

# --- эпизоды: непрерывные серии blocked-сэмплов ---
episodes = []
cur = []
for i in range(ns):
    if mask[i]:
        cur.append(i)
    else:
        if cur:
            episodes.append(cur)
            cur = []
if cur:
    episodes.append(cur)
print('эпизодов ожидания: %d' % len(episodes))
sizes = [len(e) for e in episodes]
print('длины эпизодов (сэмплов): топ-15 %s ; сумма=%d' % (sorted(sizes, reverse=True)[:15], sum(sizes)))
print('распределение: 1сэмпл=%d, 2-3=%d, 4-10=%d, >10=%d' % (
    sum(1 for s in sizes if s == 1), sum(1 for s in sizes if 2 <= s <= 3),
    sum(1 for s in sizes if 4 <= s <= 10), sum(1 for s in sizes if s > 10)))

# --- атрибуция эпизодов ---
owner_ep = collections.Counter()
owner_samples = collections.Counter()
stack_ev = collections.Counter()
rows = []
for e in episodes:
    s, t = e[0], e[-1]
    last = None
    for j in range(s - 1, max(-1, s - 40), -1):
        f = exe_leaf(rips[j])
        if f:
            last = f
            break
    first = None
    for j in range(t + 1, min(ns, t + 40)):
        f = exe_leaf(rips[j])
        if f:
            first = f
            break
    # свидетельство из стека wait'а (первой записи эпизода)
    wi = None
    for kk, i in enumerate(pairs):
        if i == s:
            wi = kk
            break
    se = None
    if wi is not None:
        for x in wwords[wi * 5:wi * 5 + 5]:
            fn_ = exe_leaf(x)
            if fn_:
                se = fn_
                break
            dd = exe_data(x)
            if dd:
                se = dd
                break
    owner_ep[(last, se, first)] += 1
    owner_samples[last] += len(e)
    stack_ev[se] += len(e)
    rows.append((s, t, len(e), last, se, first))

tot_ep = len(episodes)
tot_s = sum(sizes)
print('\n=== ВЛАДЕЛЕЦ: код перед входом в ожидание (по сэмплам) ===')
for o, c in owner_samples.most_common(20):
    print('  %5d сэмплов (%5.1f%%)  %s' % (c, 100.0 * c / tot_s, o))
print('\n=== свидетельство из стека wait\'а (по сэмплам) ===')
for o, c in stack_ev.most_common(12):
    print('  %5d сэмплов (%5.1f%%)  %s' % (c, 100.0 * c / tot_s, o))
print('\n=== (перед | стек | после) топ-20 эпизодов ===')
for (a, b, c), n in owner_ep.most_common(20):
    print('  %4d эпизодов: %-42s | %-40s | %s' % (n, a, b, c))
with open(TICKPROF + ('\\prof_%s.episodes.json' % PROF), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False)
print('\n-> %s' % (TICKPROF + ('\\prof_%s.episodes.json' % PROF)))
