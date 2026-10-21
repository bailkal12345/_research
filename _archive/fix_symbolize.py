import io
p = "symbolize.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace('''    ap.add_argument("--pid", type=int, default=0)''',
'''    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--exclude-idle", action="store_true",
                    help="выбросить сэмплы в заглушках системных вызовов (Sleep/Wait): это стена, а не CPU")''')

s = s.replace('''    self_counts = collections.Counter()
    class_counts = collections.Counter()
    unknown = 0''',
'''    # Заглушки системных вызовов ntdll: попадание туда = поток спит/ждёт,
    # а не выполняет код игры. Отрезок 0x15E000..0x160000 — NtDelayExecution,
    # NtWaitForSingleObject и соседние (проверено дизассемблированием ntdll).
    idle_lo = 0x15E000
    idle_hi = 0x160000

    def is_idle(name):
        if not name.startswith("[ntdll.dll+"):
            return False
        try:
            off = int(name.split("+0x")[1].rstrip("]"), 16)
        except (IndexError, ValueError):
            return False
        return idle_lo <= off <= idle_hi

    self_counts = collections.Counter()
    class_counts = collections.Counter()
    unknown = 0
    idle = 0''')

s = s.replace('''            if mods:
                i = bisect.bisect_right(mod_starts, rip) - 1
                if i >= 0 and rip < mods[i][1]:
                    self_counts["[%s+0x%X]" % (mods[i][2], rip - mods[i][0])] += 1
                    class_counts["(external module)"] += 1
                    continue''',
'''            if mods:
                i = bisect.bisect_right(mod_starts, rip) - 1
                if i >= 0 and rip < mods[i][1]:
                    label = "[%s+0x%X]" % (mods[i][2], rip - mods[i][0])
                    if args.exclude_idle and is_idle(label):
                        idle += 1
                        continue
                    self_counts[label] += 1
                    class_counts["(external module)"] += 1
                    continue''')

s = s.replace('''    total = count or 1
    print("resolved in image: %.1f%%, external: %.1f%%, unknown: %.1f%%\\n" % (''',
'''    total = count or 1
    if args.exclude_idle:
        print("idle (Sleep/Wait in ntdll): %d samples = %.1f%% of wall time\\n"
              % (idle, 100.0 * idle / total))
        total = count - idle
        print("=> ниже распределение только по исполняемому коду (%d сэмплов)\\n" % total)
    print("resolved in image: %.1f%%, external: %.1f%%, unknown: %.1f%%\\n" % (''')

io.open(p, "w", encoding="utf-8").write(s)
print("patched")
