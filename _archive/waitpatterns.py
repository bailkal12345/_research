# -*- coding: utf-8 -*-
# Слот A (v4): классификация wait-записей по ПАТТЕРНУ 4 слов стека + сравнение профилей.
# Проверяем, специфичен ли кластер "&GNatives" (exe@Data+0x491C6B0) для плотной базы
# или это общий артефакт кадра стека игрового потока.
import struct, collections, sys, os
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)
GNATIVES = 0x1491C6B0


def modinfo(a):
    return pa.mod_of(a, mods, bases)


def kind(a):
    """Категория слова стека."""
    short, off, _ = modinfo(a)
    if a == 0:
        return 'ZERO'
    if a == 0xFFFFFFFFFFFFFFFF or a == 0xFFFF:
        return 'FFFF'
    if short == 'ShooterGameServer.exe':
        return 'exeDATA' if off >= TXT else 'exeCODE'
    if short:
        return 'dll'
    if 0x10000 < a < 0x7FFFFFFFFFFF:
        return 'heap'
    return 'other'


def code_name(a):
    short, off, _ = modinfo(a)
    if short == 'ShooterGameServer.exe' and off < TXT:
        return namer.name(off) or ('sub_%X' % off)
    return None


def analyse(prof):
    p = TICKPROF + r'\prof_%s.wait' % prof
    if not os.path.exists(p):
        return None
    d = open(p, 'rb').read()
    n = struct.unpack_from('<Q', d, 0)[0]
    ws = struct.unpack_from('<%dQ' % (n * 5), d, 8)
    pat = collections.Counter()
    sysc = collections.Counter()
    exe_word = collections.Counter()
    for i in range(n):
        rip, a1, a2, a3, a4 = ws[i * 5:i * 5 + 5]
        short, off, _ = modinfo(rip)
        s = ('%s+0x%x' % (short, off)) if short else 'raw'
        sysc[s] += 1
        ks = (kind(a1), kind(a2), kind(a3), kind(a4))
        pat[ks] += 1
        for a in (a1, a2, a3, a4):
            cn = code_name(a)
            if cn:
                exe_word[cn] += 1
    return n, sysc, pat, exe_word


PROFS = ['512222984', '288561984', '294655390', '298529359', '301269000', '343238843', '383773968']
allp = {}
for pr in PROFS:
    r = analyse(pr)
    if not r:
        continue
    n, sysc, pat, exw = r
    allp[pr] = r
    print('\n########## профиль %s: wait=%d ##########' % (pr, n))
    print('  syscall:', dict(sysc.most_common(4)))
    print('  топ-паттернов 4 слов:')
    for ks, c in pat.most_common(6):
        print('     %5d (%4.1f%%)  %s' % (c, 100.0 * c / n, ' | '.join(ks)))
    print('  exe-код в словах стека (топ-8):')
    for cn, c in exw.most_common(8):
        print('     %5d  %s' % (c, cn))

# доля GNatives по профилям
print('\n=== доля wait-слов, равных &GNatives (0x1491C6B0) ===')
for pr, (n, sysc, pat, exw) in allp.items():
    d = open(TICKPROF + r'\prof_%s.wait' % pr, 'rb').read()
    cnt = struct.unpack_from('<Q', d, 0)[0]
    ws = struct.unpack_from('<%dQ' % (cnt * 5), d, 8)
    g = sum(1 for i in range(cnt) for a in ws[i * 5:i * 5 + 5] if a == GNATIVES)
    print('   %-12s wait=%6d  &GNatives-упоминаний=%5d (%.1f%% от wait)' % (pr, cnt, g, 100.0 * g / max(1, cnt)))
