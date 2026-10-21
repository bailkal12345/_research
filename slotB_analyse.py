# -*- coding: utf-8 -*-
# Слот B: атрибуция ожиданий в ПРОФИЛЕ ФАЗЫ (prof_631247234) тем же методом,
# что и в слоте A для плотной базы (prof_512222984) + сопоставление с idle-профилем.
import struct, collections, sys, os, json
sys.path.insert(0, r'C:\Dev\_research')
sys.stdout.reconfigure(encoding='utf-8')
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
PLUG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins'
BACK = os.path.join(PLUG, '_backup', 'TickProf')
# Новый профиль (слот B) лежит в активном каталоге плагина, старые - в _backup.
ACTIVE = os.path.join(PLUG, 'TickProf')


def dir_for(prof):
    p = os.path.join(ACTIVE, 'prof_%s.wait' % prof)
    if os.path.exists(p):
        return ACTIVE
    return BACK
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)


def analyse(prof, tag):
    D0 = dir_for(prof)
    d = os.path.join(D0, 'prof_%s.wait' % prof)
    b = os.path.join(D0, 'prof_%s.bin' % prof)
    r = os.path.join(D0, 'prof_%s.ret' % prof)
    mods, bases = pa.load_modules(os.path.join(D0, 'prof_%s.modules.txt' % prof))
    wd = open(d, 'rb').read()
    bd = open(b, 'rb').read()
    rd = open(r, 'rb').read()
    ns = len(bd) // 8
    rips = struct.unpack_from('<%dQ' % ns, bd, 0)
    nret = len(rd) // 8
    rets = struct.unpack_from('<%dQ' % nret, rd, 0)
    wcnt = struct.unpack_from('<Q', wd, 0)[0]
    ww = struct.unpack_from('<%dQ' % (wcnt * 5), wd, 8)

    def mi(a):
        return pa.mod_of(a, mods, bases)

    def blocked(x):
        s, o, issys = mi(x)
        return True if s is None else bool(issys)

    def exefn(a):
        s, o, _ = mi(a)
        if s == 'ShooterGameServer.exe' and o < TXT:
            return namer.name(o) or ('sub_%X' % o)
        return None

    def exedata(a):
        s, o, _ = mi(a)
        if s == 'ShooterGameServer.exe' and o >= TXT:
            return 'exeDATA+0x%X' % o
        return None

    pairs = []
    k = 0
    for i in range(ns):
        if blocked(rips[i]):
            if k < wcnt and ww[k * 5] == rips[i]:
                pairs.append((i, k))
                k += 1
    sysc = collections.Counter()
    for (i, k) in pairs:
        s, o, _ = mi(ww[k * 5])
        sysc['%s+0x%x' % (s, o) if s else 'raw'] += 1
    # свидетельство в стеке
    stack = collections.Counter()
    for (i, k) in pairs:
        sig = None
        for x in ww[k * 5:k * 5 + 5]:
            f = exefn(x)
            if f:
                sig = f
                break
            d2 = exedata(x)
            if d2:
                sig = d2
                break
        stack[sig or '<нет exe-кадра>'] += 1
    # владелец по ret ПЕРВОГО exe-сэмпла ПОСЛЕ ожидания
    owner = collections.Counter()
    for (i, k) in pairs:
        own = None
        for j in range(i + 1, min(ns, i + 1 + 12)):
            f = exefn(rips[j])
            if f:
                if j < nret:
                    own = exefn(rets[j]) or ('<' + str(rets[j]) + '>')
                else:
                    own = f
                break
        owner[own or '<?>'] += 1
    print('\n########## %s: профиль %s ##########' % (tag, prof))
    print('  сэмплов=%d, wait=%d (%.1f%%), выровнено=%d' % (ns, wcnt, 100.0 * wcnt / ns, len(pairs)))
    print('  syscall-классы (топ-6):')
    for s, c in sysc.most_common(6):
        print('     %5d (%5.1f%%)  %s' % (c, 100.0 * c / wcnt, s))
    print('  свидетельство в стеке (топ-10):')
    for s, c in stack.most_common(10):
        print('     %5d (%5.1f%%)  %s' % (c, 100.0 * c / max(1, wcnt), s))
    print('  владелец по ret после ожидания (топ-10):')
    for s, c in owner.most_common(10):
        print('     %5d (%5.1f%%)  %s' % (c, 100.0 * c / max(1, wcnt), s))
    named = sum(c for s, c in stack.items() if s and s != '<нет exe-кадра>')
    print('  НАЗВАНО по стеку: %d из %d (%.1f%%)' % (named, wcnt, 100.0 * named / max(1, wcnt)))
    return dict(prof=prof, samples=ns, waits=wcnt, sysc=dict(sysc.most_common(8)),
                stack=dict(stack.most_common(12)), owner=dict(owner.most_common(12)))


if __name__ == '__main__':
    res = []
    res.append(analyse('631247234', 'СЛОТ B: ПРОФИЛЬ ФАЗЫ (21:57, t/s 28-33, busy 92-96%)'))
    res.append(analyse('512222984', 'СЛОТ A: плотная база 20.10 12:53 (t/s 21)'))
    res.append(analyse('301269000', 'idle-профиль (Sleep- pacing)'))
    with open(r'C:\Dev\_research\slotB\compare_profiles.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('\nсохранено: C:\\Dev\\_research\\slotB\\compare_profiles.json')
