# -*- coding: utf-8 -*-
# Comment cleanup for TickProf.cpp: delete narrative/history full-line comments,
# keep ABI facts (PDB offsets, signatures, patch bytes, safety invariants).
import io, sys

p = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
data = io.open(p, encoding='utf-8', newline='').read()
crlf = data.count('\r\n') * 2 > data.count('\n')
lines = [l.rstrip('\r') for l in data.split('\n')]
if lines and lines[-1] == '':
    lines.pop()

DELETE = [
 '//P12: deferred application of the tickrate clamp patch (see ApplyClampAutoStart)',
 '//string literals are pointers too; check this case first',
 '//Own log next to the plugin: ArkApi messages from a plugin do not always reach',
 '//ArkApi_*.log, and a silent tool is useless.',
 '//Polling the .ark directory (1 Hz, ~24 FindNextFile calls per poll) affects the',
 '//profile: those waits show up as ZwQueryDirectoryFileEx. The flag allows',
 '//disabling the poll to measure the monitor contribution separately.',
 '//P7: samples of waits inside system calls. Capturing context externally from',
 '//Python does not work (GetThreadContext returns zeros), so counting is done',
 '//right here: if RIP does not land in any user module,',
 '//the thread is blocked in a syscall. Stack words are recorded separately.',
 '//Stack samples inside the StartFrame window: RIP + four stack words.',
 '//Needed to learn what exactly the dispatcher calls: if the stack contains',
 '//NtWait/NtDelay, the time goes to waiting, not to accounting.',
 '//Slot D: the plugin crash reproduced manually 2-3 s after a sampling window ended.',
 '//Rule: 60 s of silence after the window ends before new measurements;',
 '//each trigger is written to the log.',
 '//system call stubs live in these DLLs: RIP landing here means a block,',
 '//not engine work',
 '//[RSP] - the return address: for hot leaf functions this is the only way to tell',
 '//who calls them (the sampler does not walk the stack).',
 '//direct calls needed by selftest; the definitions are further down the file',
 '//internal functions that never touch RCONPacket: called by selftest',
 '//Correct argument parsing: the N-th command argument (1 = the first one after',
 '//the command name). The old ArgInt(packet, def) took the LAST token, which made',
 '//' + '"TickProf.overlaptrim 5" return 2 and "selftest 20 120 0" return 0.'.replace('"', '\u0022'),
 '//t[0] - command name; arguments follow',
 '//---- block-wide variables (declared here so the order does not depend on',
 '//where the functions ended up) ----',
 '//Save state: 0 - idle, 1 - a write is in progress.',
 '//Detected via .ark changes: every save goes through renaming .tmp -> .ark,',
 '//so a size or mtime change means a save.',
 '//Called once per second from OnTickPerf.',
 '//Logic: file change -> start the timer; 2 seconds without changes ->',
 '//the save is over, print the duration.',
 '//Toggle .ark directory polling (for attributing file IO in the profile).',
 '//The "window already started" flags: without them the A/B arm phase re-armed the window every frame.',
 '//Catch the autosave start; otherwise a window can land right before it.',
 '//This used to be g_st_mark = now + 3000 (a mark in the future), so uint64',
 '//wrapped, the condition "elapsed_s > 120" was true every frame, the window',
 '//re-armed => hot loop and a stalled auto-run.',
 '//Transitioning into itself was a bug: "arm A closed" logged every frame.',
 '//Now the phase runs once and moves on to ST_AB_B_WINDOW.',
 '//GameThread time: needed by both the monitor and the window',
 '//2.3% of the profile: TSet<TPair<FName,FFoliageMeshInfo*>>::FindId is called from',
 '//UClass::FindFunctionByName, which walks the class chain and interfaces.',
 '//A class function set does not change after load - the cache is safe,',
 '//negative answers are cached too (they are the majority).',
 '//Linear probing over 8 slots: a single-slot cache, once the number of live pairs',
 '//exceeded the table size, evicted keys and added hook overhead plus a miss.',
 '//The UStruct::IsChildOf cache - Cast<>/IsA live underneath it, ARK code calls them',
 '//tens of thousands of times per frame (UStruct::IsChildOf 0.71% + IsA 0.64%).',
 '//The class hierarchy is static on a server, hence (class, parent) -> bool.',
 '//bptrace structure init (fixed-size slots, QPC frequency).',
 '//Report: top by calls and top by self time (with shares).',
 '//Reset counters/window (the patch is not removed).',
 '//Caller top for a function (by rank in the self-time top or by a name substring).',
 '//Dump UFunction flags: whether return/out parameters exist.',
 '//Safety basis for throttling (P4): a function may be skipped only if it',
 '//returns nothing and writes no out parameters.',
 '// 2.5% of the profile - TSet<FName,FFoliageMeshInfo*>::FindId from DoGetCanvasByName /',
 '// GetCanvasByName / FindFunctionByName. Nothing is drawn on a dedicated server.',
 '//UNetDriver::NetServerMaxTickRate is the only',
 '//real limiter: the net.MaxNetTickRate cvar is missing in this build,',
 '//and UEngine::GetMaxTickRate returns 0 and only handles t.MaxFPS.',
 '//clamp, then CVTDQ2PS). A float used to be written here, and its bits were read',
 '//as a huge integer - the tool "worked" but showed nonsense.',
 '//The phase timing showed FTickTaskManager::StartFrame - 3.05 ms per frame, 34%',
 '//of the frame: it queues all tick functions of the levels. So the main lever is',
 '//reducing the number of ticking components.',
 '//UEngine::TickFPSChart - 0.47% of the profile with a player on the server. Pure',
 '//chart and frame counter bookkeeping: nobody looks at it on a dedicated server.',
 '//The decisive question: how many tick tasks actually get queued per frame -',
 '//~700 (ticking only) or ~52,780 (all registered, including the stasis ones that',
 '//the engine queues and releases right away).',
 '//A classic ARK server optimization: do not tick actors beyond the radius from',
 '//The radius is measured from player positions; the list updates once per 30 ticks.',
 '//actor position from the root component, no engine call',
 '//how many tick tasks were queued during the previous frame',
 '//the player position list for tick culling is updated rarely',
 '//the limit value may reset on driver reinitialization',
 '//A census of the manager tick set sizes: this is the "scan" that the brief',
 '//hypothesis named as the source of 3.8 ms. Num() is summed across 104 levels.',
 '//stack: 16 words from RSP',
]

BLOCKS = [
 (
  '//Why. In both vigils, measurement windows were spoiled by autosaves: in the',
  '//For 60 t/s the patch is unnecessary: 60 lies inside [10..120].',
  ['//ms/tick = GameThread CPU (s/s) / t/s - the only budget metric (<=16.6 ms at 60 t/s).'],
 ),
 (
  '//GetThreadTimes returns the thread CUMULATIVE time since it started.',
  '//impossible for one thread. Credible numbers had to come from outside.',
  ['//GetThreadTimes is cumulative since thread start - subtract the base, or busy exceeds 100%.'],
 ),
 (
  '//Called every frame. The monitor, the save detector and selftest must keep',
  '//BEFORE the early exit on g_perf.window == 0.',
  ['//The monitor, the save detector and selftest run before the early exit on g_perf.window == 0.'],
 ),
 (
  '//v1/v2 stripped bGenerateOverlapEvents from all bloated components in a row,',
  '//APrimalProjectileGrapplingHook. v3 keeps classes from the file',
  ['//v1/v2 stripped bGenerateOverlapEvents from components whose overlap events the',
   '//game logic needs (triggers, turrets, traps); v3 keeps classes from the file'],
 ),
]

stripped = [l.strip() for l in lines]
delset = set(DELETE)

# validate: every DELETE text occurs exactly once as a full-line comment
for t in DELETE:
    n = sum(1 for s in stripped if s == t)
    assert n == 1, ('delete text not unique: %r x%d' % (t, n))

# validate: block first/last occur once, in order, comment lines between
pos = {}
for first, last, rep in BLOCKS:
    fi = [i for i, s in enumerate(stripped) if s == first]
    li = [i for i, s in enumerate(stripped) if s == last]
    assert len(fi) == 1 and len(li) == 1 and fi[0] < li[0], (first, fi, li)
    pos[first] = (fi[0], li[0])
    for i in range(fi[0], li[0] + 1):
        assert stripped[i].startswith('//') or stripped[i] == '', (i, repr(lines[i]))

out = []
i = 0
removed = 0
block_starts = {fi: (li, rep) for (first, last, rep) in BLOCKS for fi, li in [pos[first]]}
while i < len(lines):
    if i in block_starts:
        li, rep = block_starts[i]
        out.extend(rep)
        removed += li - i + 1 - len(rep)
        i = li + 1
        continue
    s = stripped[i]
    if s in delset:
        removed += 1
        i += 1
        continue
    out.append(lines[i])
    i += 1

eol = '\r\n' if crlf else '\n'
io.open(p, 'w', encoding='utf-8', newline='').write(eol.join(out) + eol)
print('OK: removed/replaced %d lines, file now %d lines (was %d)' % (removed, len(out), len(lines)))
