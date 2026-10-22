# -*- coding: utf-8 -*-
# Pass 2: replace remaining Cyrillic comment lines by line number (all pure comments).
import io
import re

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'

BYLINE = {5: '  * phase timers installed on hooks;',
          6: '  * a GameThread sampling profiler (SuspendThread + GetThreadContext,',
          7: '    offline symbolization via PDB; the PDB is not needed at runtime);',
          8: '  * the bAllowConcurrentTicks patch - lifts the UE4.5 prohibition on asynchronous ticks',
          9: '    (in the server build the IsRunningDedicatedServer() check is folded away by the compiler);',
          10: '  * marking tick functions with bRunOnAnyThread (stock 4.5 never sets it);',
          11: '  * a Kismet canvas cache for DoGetCanvasByName (nothing is drawn on a server);',
          12: '  * an overlap event counter grouped by component owners;',
          13: '  * a precise in-process GameThread measurement (frames / cpu / wall).',
          16: '  FTickFunction:      bitfield dword @ +12, bRunOnAnyThread = bit 4 (0x10),',
          24: '  TickProf.start [sec] / .stop / .status      - RIP sampling',
          25: '  TickProf.perf [sec]                          - frames/cpu/wall measurement',
          26: '  TickProf.hook N / .unhook N                  - phase hooks one at a time',
          27: '  TickProf.fix concurrent 1|0                  - the bAllowConcurrentTicks patch',
          28: '  TickProf.verify                              - read the field back',
          29: '  TickProf.ticklist                            - actor/component census',
          30: '  TickProf.tickflags <mode>                    - 0 clear, 1 all, 2 components',
          32: '                                                  4 actor ticks only,',
          33: '                                                  5 all without prerequisites',
          34: '  TickProf.tickflags2 <mode> <filter>          - same, with a keep list from a file',
          36: '  TickProf.overlaps [sec] / .overlapsreport    - overlap event census',
          37: '  TickProf.cachename 1|0                       - the Kismet canvas cache',
          38: '  TickProf.spawn N / .cleardinos / .count      - load generation and census',
          774: '     MOV ECX,0xa               ; < 10  -> 10  (FLOOR)',
          775: '     MOV ECX,0x78              ; >= 10 -> min(rate,120) (CEILING)',
          1133: 'This used to be g_st_mark = now + 3000 (a mark in the future), so uint64',
          1755: '                      bGenerateOverlapEvents = bit 10 of the dword @ +500.',
          2387: '  UStruct+0x38 = the property chain (PropertyLink),',
          2389: '  bit 0x80 = Parm, 0x100 = OutParm, 0x400 = ReturnParm.',
          2545: '------------------------------------------------------- Kismet canvas cache',
          2546: ' 2.5% of the profile - TSet<FName,FFoliageMeshInfo*>::FindId from DoGetCanvasByName /',
          2547: ' GetCanvasByName / FindFunctionByName. Nothing is drawn on a dedicated server.',
          2548: ' PDB signature: UCanvas* __cdecl DoGetCanvasByName(FName)'}

with io.open(CPP, encoding='utf-8', newline='') as f:
    lines = f.read().split('\n')

fixed = 0
for ln, text in BYLINE.items():
    line = lines[ln - 1]
    if not re.search(r'[\u0400-\u04ff\u4e00-\u9fff]', line):
        print('line %d already clean?' % ln)
        continue
    m = re.match(r'^(\s*)//.*$', line)
    assert m, 'line %d is not a bare comment: %r' % (ln, line)
    lines[ln - 1] = m.group(1) + '//' + text
    fixed += 1

with io.open(CPP, 'w', encoding='utf-8', newline='') as f:
    f.write('\n'.join(lines))
print('fixed lines: %d' % fixed)
