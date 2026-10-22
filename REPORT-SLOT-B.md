# REPORT - Slot B (doit6 sec 2): a live profile inside the accumulating phase

**Date:** 21.10.2026, 21:57. **Bench:** Server1, Genesis, TickProf (reworked A2 whitelist build), prod
config of sec 2, `TickProf.maxfps 60` + `fixclamp 0` applied right after the boot (21:51-21:52).
**Profile:** `prof_631247234` (31 679 samples, 60 s).

---

## 1. Main answer

The phase was caught live and **the source is named**: in the phase profile **54.4% of CPU time goes
into the Blueprint-VM** (`exec*`, `ProcessContextOpcode`, `ProcessInternal`, `Invoke`, `CallFunction`,
`CopyCompleteValueToScriptVM`) against **6.0% on the dense base**. On top, 11.4% of CPU - the calls of
`ServerOctreeOverlapActors` (0x12871E0), and by `[RSP]` they come **from Blueprint dispatching**
(`ProcessInternal+0xcf` 6.8%, `ProcessContextOpcode+0x6c` 5.6%, `CopyCompleteValueToScriptVM+0x49` 3.6%,
`Invoke+0x2f8` 2.2%), not from the C++ turrets. The other half of the phase is **file IO**: 64.8% of
all phase waits are `NtQueryDirectoryFileEx` (vs 81.9% `NtWaitForSingleObject` on the dense base).
Mechanism: `ZwQueryDirectoryFileEx` -> `KERNELBASE+0x9c14e` (`FindNextFileW`) <-
`FWindowsPlatformFile::IterateDirectory` (windowsplatformfile.cpp:273/283), called from
`FFileManagerGeneric::FindFiles` / `UWorldComposition::Rescan` / `FPluginManager::DiscoverAllPlugins`.
In total: **the phase = mass execution of Blueprint logic, which pokes the octree
(ServerOctreeOverlapActors) and along the way scans directories** - a different mechanism than the
non-CPU limit of the dense base, intersecting at the octree.

---

## 2. Main table

| Metric | **THE PHASE** (prof_631247234, 21:57) | Dense base (prof_512222984, 20.10) | Idle (prof_301269000) |
|---|---|---|---|
| t/s at the moment of the profile | **28-33** | 21 | 59-60 |
| busy (the plugin) | **92-96%** | 83-88% | 20-40% |
| samples in the waits | 1883 (5.9%) | 762 (19.7%) | 29 395 (96.7%) |
| **the dominant syscall** | **NtQueryDirectoryFileEx 64.8%** | **NtWaitForSingleObject 81.9%** | ZwDelayExecution 98.8% |
| NtWaitForSingleObject | 16.0% | 81.9% | 0.4% |
| **Blueprint-VM share in the exe CPU** | **54.4%** | **6.0%** | 8.4% |
| top-1 of the exe list | AdvanceToNextIntersectingElement 5.3% | AdvanceToNextIntersectingElement 4.7% | - |
| top-2 of the exe list | **ServerOctreeOverlapActors 4.0%+3.6% = 7.6%** | TagFriendlyStructures 1.8% | - |
| execDynamicCast | 3.0% | - | - |
| ProcessContextOpcode | 3.5% | - | - |
| ServerOctreeOverlapActors (total) | **3624 samples (11.4%)** | **1 sample** | 0 |
| waits with `&GNatives` in the stack | 71 (3.8%) | 270 (35.4%) | 0 |

**The phase and the dense base are different phenomena**; both converge on the octree/overlaps, the
phase is additionally loaded with scripts.

## 3. How the phase was caught

Monitoring at 1 Hz (`TickProf.mon 3600`); criterion - **t/s<45 in 3+ successive mon lines**; detection
**21:57:04**, t/s=33, a series of 3; `ticklist` -> `TickProf.start 60` (60 s in the plateau, t/s 27-31,
busy 92-96%) -> `ticklist` (died with the server, see below). Dynamics (21:52-21:58): 59 t/s idle ->
21:57:04 a dip to 33 -> plateau 28-31 at busy 92-96% -> 21:58:12 the last line 4 t/s (the known "death
after the profile"). busy 20% -> 95% with t/s 59 -> 28 = a phase with accumulated work.

Census before (`slotB/ticklist_before.txt`): levels=142, actors=106 305, components=453 992,
ticking=1978; **"ticklist after" was not taken** - the server died at 21:58:12 before the command at
21:58:31. The detector gave 3 episodes of t/s<45; the real phase is one: (1) 21:52:46, a single line
t/s=40 (noise, 1 s); (2) 21:53:23-21:53:26, peak t/s=2, frame 413 ms, busy 37% - a lone multi-second
frame, not a phase (t/s returned 43->56->59, busy stayed 14-29%); (3) **21:56:54-21:58:12 - the real
phase**: 76 lines in a row, t/s 27-33, busy 92-98%, frame 32-36 ms, ms/tick 30-34, profiled
21:57:08-21:58:08.

## 4. The owner of the file IO (64.8% of waits)

Raw stack words: `[1]=KERNELBASE.dll+0x9c14e` (1174 of 1221) - `FindNextFileW`; `[2]/[3]` - search
buffer pointers. The only call-sites of `FindFirstFileW`/`FindNextFileW` in the exe are
`FWindowsPlatformFile::IterateDirectory` (windowsplatformfile.cpp:273 and 283); it is called from
`FFileManagerGeneric::FindFiles` (0x1EBAF0), `FPluginManager::DiscoverAllPlugins::FindPluginsRecursively`
(0x1F64200), `UWorldComposition::Rescan` (0x275BF00). **Honest boundary:** the exe frame lies deeper
than the 4 available stack words - the immediate caller is **not resolved**; `DiscoverAllPlugins` is
one-time (from `IPluginManager::Get`), so in the phase it is one of the others. Exe samples inside
`IterateDirectory`/`FindFiles`/`Rescan`: **0** - the scanning goes from **native/foreign code**, not
from the game code.

## 5. Honesty attributes

1. Referee numbers - external Python only; the plugin's series are used relatively, the distortion is
   multiplicative.
2. The 60 s window is inside the phase (t/s 27-31, busy 92-96%), classified **VALID** (`save=idle` in
   all mon lines; nearest autosave on the 15-minute cycle).
3. The profile is on a "fresh" world after a reboot (21:33-21:57); the base was **NOT full** (106 305
   actors vs 106 556 in the previous slot; last save TheIsland 21:27:48, Genesis.ark of 20.10 12:52) -
   the phase conclusion holds, absolute numbers across slots do not compare.
4. The server died right after the profile (a known pattern); restarted for slot C at 22:22, pid 17532.
5. Sampler: 4-word wait stack; **92.4%** of the phase's wait records have no exe frame => direct naming
   for 7.6% only; the naming came from static IAT analysis + CPU-profile correlation (`[RSP]`).
6. Phase and dense-base profiles are different worlds/sessions - relative shares only.

## 6. Not done / next slot

**Not tested:** "the phase disappears when the source is turned off" (would need disabling Blueprint
execution or `ServerOctreeOverlapActors` live - unacceptable outside an A/B with rollback); the
immediate caller of the file IO; the A/B dense vs empty this session; the phase duration (the phase hit
the end of the 3600 s monitor window and the profile killed the server) - taken from slot 2 of the
previous day (1.5-2 min plateau).
**Tasks:** (1) profile the phase on a **dense** base and compare shares; (2) extend the sampler stack to
8-12 words; (3) test "Blueprint -> ServerOctreeOverlapActors -> O(n^2) overlap" via trim2 vs trim3
(consistency with `overlaptrim3`, ARCH.md sec 3.1/3.3); (4) **bptrace** (ARCH.md sec 3.5) - full UFunction
names (disabled by default, patch bytes not set) - the direct answer to "which Blueprint function spins
in the phase"; (5) check whether the file IO is `UWorldComposition::Rescan` (caller:
`ApplySettings`/`Serialize`) - else a separate optimization point.
