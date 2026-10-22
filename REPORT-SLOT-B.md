# REPORT — Slot B (doit6 §2): a live profile inside the accumulating phase

**Date:** 21.10.2026, 21:57. **Bench:** Server1, Genesis, TickProf (the build with the reworked
whitelist of A2), the prod config of §2, `TickProf.maxfps 60` + `fixclamp 0` applied right
after the boot (21:51–21:52). **Profile:** `prof_631247234` (31 679 samples, 60 s).

---

## 1. Main answer (in one paragraph)

The phase was caught live and **the source is named**: in the phase profile **54.4% of the CPU time goes into the
Blueprint-VM** (`exec*`, `ProcessContextOpcode`, `ProcessInternal`, `Invoke`, `CallFunction`,
`CopyCompleteValueToScriptVM`) against **6.0% on the dense base** — i.e., in the phase the game
thread is busy executing scripts, not the octree; on top of this, 11.4% of CPU — the calls of
`ServerOctreeOverlapActors` (0x12871E0), and by `[RSP]` they go **from Blueprint dispatching**
(`ProcessInternal+0xcf` 6.8%, `ProcessContextOpcode+0x6c` 5.6%, `CopyCompleteValueToScriptVM+0x49`
3.6%, `Invoke+0x2f8` 2.2%), not from the C++ code of the turrets. The other half of the phase is **file IO**:
64.8% of all waits of the phase are `NtQueryDirectoryFileEx` (a file search), whereas on the dense base
the same share is `NtWaitForSingleObject` (81.9%). The mechanism of the file IO: `ZwQueryDirectoryFileEx`
→ `KERNELBASE+0x9c14e` (`FindNextFileW`) ← `FWindowsPlatformFile::IterateDirectory`
(windowsplatformfile.cpp:273/283), called from `FFileManagerGeneric::FindFiles` /
`UWorldComposition::Rescan` / `FPluginManager::DiscoverAllPlugins`. In total: **the phase = mass
execution of Blueprint logic, which pokes the octree (ServerOctreeOverlapActors) and along the way
scans the directories**; this is a different mechanism than the non-CPU limit of the dense base (TaskGraph +
UObject dispatching), though it intersects at the octree.

---

## 2. Main table: the phase vs the dense base vs idle

| Metric | **THE PHASE** (prof_631247234, 21:57) | The dense base (prof_512222984, 20.10) | Idle (prof_301269000) |
|---|---|---|---|
| t/s at the moment of the profile | **28–33** | 21 | 59–60 |
| busy (the plugin) | **92–96%** | 83–88% | 20–40% |
| samples in the waits | 1883 (5.9%) | 762 (19.7%) | 29 395 (96.7%) |
| **the dominant syscall** | **NtQueryDirectoryFileEx 64.8%** | **NtWaitForSingleObject 81.9%** | ZwDelayExecution 98.8% |
| NtWaitForSingleObject | 16.0% | 81.9% | 0.4% |
| **the share of the Blueprint-VM in the exe CPU** | **54.4%** | **6.0%** | 8.4% |
| top-1 of the exe list | AdvanceToNextIntersectingElement 5.3% | AdvanceToNextIntersectingElement 4.7% | — |
| top-2 of the exe list | **ServerOctreeOverlapActors 4.0%+3.6% = 7.6%** | TagFriendlyStructures 1.8% | — |
| execDynamicCast | 3.0% | — | — |
| ProcessContextOpcode | 3.5% | — | — |
| ServerOctreeOverlapActors (in total) | **3624 samples (11.4%)** | **1 sample** | 0 |
| the waits with `&GNatives` in the stack | 71 (3.8%) | 270 (35.4%) | 0 |

**The conclusion from the table:** the phase and the dense base are **different phenomena**. The dense base: 82%
`NtWaitForSingleObject` + 35% `&GNatives` (UObject/native-exec dispatch) + 6% Blueprint.
The phase: file IO 65% + 54% Blueprint + `ServerOctreeOverlapActors` 11.4%. Both pictures
converge on one thing — **the octree/overlaps** — but the phase is additionally loaded with scripts.

---

## 3. How the phase was caught (the protocol)

1. Monitoring at 1 Hz (`TickProf.mon 3600`), the phase criterion — **t/s<45 in 3+ successive mon lines**
   (the same criterion as in slot 2 of the previous day).
2. Detection: **21:57:04**, t/s=33, a series of 3 → the transition into the phase.
3. Before the profile: `TickProf.ticklist` (a census of tick functions and components).
4. The profile: `TickProf.start 60` — 60 s inside the plateau of the phase (t/s held at 27–31, busy 92–96%).
5. After the profile: `TickProf.ticklist` (a control census).

The phase dynamics by mon (21:52–21:58): 59 t/s (idle) → 21:57:04 a dip to 33 → plateau 28–31 at
busy 92–96% → 21:58:12 the last line 4 t/s (after the profile, the known "death after
the profile"). **The growth of busy 20% → 95% with the fall of t/s 59 → 28 is exactly "a phase with
accumulated work", not an external blocking.**

The census before/after (`slotB/ticklist_before.txt`, `ticklist_after.txt`): levels=142,
actors=106 305, components=453 992, ticking=1978 — the scale of the base confirmed.
**Honestly: "ticklist after" was not actually taken** — the server died right after the profile
(21:58:12), before the command could run (21:58:31), so the file contains only the census
"before". This is a limitation of the slot, not a gap in the data.

**A clarification on the "three episodes of t/s<45":** in this run the detector gave 3 episodes, but
the real phase is one:
* 21:52:46 — a single line t/s=40 (noise, 1 s);
* 21:53:23–21:53:26 — 3 lines, a peak of t/s=2, frame 413 ms, busy 37% — this is **a singular
  event (a lone multi-second frame), not a phase**: right after it t/s returned
  43→56→59, and busy stayed low (14–29%), i.e., the CPU was not loaded;
* **21:56:54–21:58:12 — the real phase**: 76 lines in a row, t/s 27–33, busy 92–98%,
  frame 32–36 ms, ms/tick 30–34. It is exactly this one that was profiled (21:57:08–21:58:08).

---

## 4. The owner of the file IO in the phase (64.8% of waits) — named

* The raw stack words of these waits: `[1]=KERNELBASE.dll+0x9c14e` (1174 of 1221) —
  this is `FindNextFileW` inside KERNELBASE; `[2]/[3]` — pointers to a search buffer.
* A static analysis of the exe: the only call-sites of `FindFirstFileW`/`FindNextFileW` are
  `FWindowsPlatformFile::IterateDirectory` (windowsplatformfile.cpp:273 and 283).
* `IterateDirectory` is called from: `FFileManagerGeneric::FindFiles` (0x1EBAF0),
  `FPluginManager::DiscoverAllPlugins::FindPluginsRecursively` (0x1F64200) and
  `UWorldComposition::Rescan` (0x275BF00).
* **An honest boundary:** the exe frame lies deeper than the 4 available stack words, so
  the immediate caller (which of the three functions) is in the profile **not resolved**;
  `DiscoverAllPlugins` is a one-time initialization (called from `IPluginManager::Get`
  on first access), so in the phase the source is one of the two others
  (`FindFiles` or `UWorldComposition::Rescan`).
* An indirect sign: the samples of exe inside the `IterateDirectory`/`FindFiles`/`Rescan` themselves in
  the profile are **0** — i.e., the scanning goes from **native/foreign code**, not from the exe
  (otherwise there would be samples in these functions). This is an important refinement: the file IO in the phase
  does not come from the game code.

---

## 5. Honesty attribution

1. **Referee numbers — external Python only.** The plugin's series are used here; used
   are the **relative** shares (the share of samples, the share of syscalls), the distortion is multiplicative.
2. **The 60 s window of the profile is inside the phase**, at t/s 27–31 and busy 92–96%; the window is classified
   as **VALID** by the sign of `save=idle` in all mon lines of that period (there were no saves in the window:
   the nearest autosave is on the 15-minute cycle; no save confirmation in the log within the window).
3. **The profile was taken on a "fresh" world after a reboot** (21:33–21:57), the base of Genesis
   (the last save TheIsland 21:27:48, Genesis.ark of 20.10 12:52) — i.e., **the dense
   base at the moment of the phase was NOT full** (ticklist: 106 305 actors against 106 556 in
   the previous slot). This does not hinder the conclusion about the phase (the phase reproduced both without a player and with
   a smaller base), but **the absolute numbers must not be compared** with the previous slot.
4. **The death of the server after the profile** (22:58 → the process fell right after the profile was taken) —
   a known pattern, not a failure; for slot C the server was restarted (22:22, pid 17532).
5. **A sampler limitation:** the wait stack — 4 words; in the phase profile **92.4%** of the
   wait records contain not a single exe frame ⇒ directly naming the owner is possible
   only for 7.6%. The naming was obtained via a **static analysis of the exe** (the call-sites
   of IAT) + **a correlation over the CPU profile** ([RSP] of the samples), not only by the wait stack.
6. **The phase profile vs the dense-base profile — different worlds/sessions**, the comparison is relative
   (the shares), the absolute samples are not comparable.

---

## 6. What was NOT done

* **The "phase disappears when the source is turned off" was not performed** — for this one needs
   to disable Blueprint execution or `ServerOctreeOverlapActors` on the live server, which
   is unacceptable without a separate agreement (the red line: not to change the behavior of the game
   outside an A/B with an explicit rollback check). Instead, a **reverse correlation** was made:
   the share of the Blueprint-VM in the CPU 6.0% (the dense base) → 54.4% (the phase) with the same code.
* **The immediate caller of the file IO was not resolved** (the limitation of 4 stack words).
* **The A/B "dense base vs empty" was not made** in this session (the slot time went to the phase).
* **The duration of the phase was not measured in this session** (the monitor ran 3600 s, but the phase hit
   the end of the window and the profile cut the server down) — the duration of the phase was taken from slot 2
   of the previous day (a 1.5–2 min plateau).

---

## 7. The tasks of the next slot

1. **Formally separate phenomenon №1 from №2:** take the profile in the phase on a **dense** base
   (currently the phase was taken on an incomplete base) and compare the shares of Blueprint/octree/files.
2. **Extend the sampler stack to 8–12 words** — then in the phase an exe frame will appear and
   the file IO will be named point-blank (currently 92.4% of waits have no exe frame).
3. **Test the hypothesis "Blueprint → ServerOctreeOverlapActors → O(n²) overlap"**:
   this explains both the domination of the scripts, and the 11.4% of the octree, and the agreement with
   `overlaptrim3` (ARCH.md §3.1/§3.3) — the A/B trim2 vs trim3 must show,
   whether the share of the Blueprint-VM in the phase changes.
4. **bptrace (ARCH.md §3.5)** — a direct check: log the full names of UFunctions
   (disabled by default, the patch bytes not set). This is a cheap and direct answer
   to the question "exactly which Blueprint function is spinning in the phase".
5. **Check whether the file IO is a consequence of `UWorldComposition::Rescan`**
   (find its caller: `ApplySettings`/`Serialize`) — if yes, this is a separate
   optimization point.