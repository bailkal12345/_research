# ntdll заглушки: база процесса вычисляется из известного смещения NtDelayExecution
nt = {0x15F484:"NtDelayExecution", 0x15EE84:"NtWaitForSingleObject", 0x15F124:"NtQueryInformationProcess",
      0x15EFC4:"NtSetEvent", 0x15F4C4:"NtQuerySystemInformation", 0x15EEE4:"NtDeviceIoControlFile"}
# подставляем базу так, чтобы NtDelayExecution совпал с наблюдаемым 0x7FF93DEBF484
base = 0x7FF93DEBF484 - 0x15F484
print("база ntdll в процессе: 0x%X" % base)
obs = {0x7FF93DEBF484:76.2, 0x7FF93DEBF124:5.3, 0x7FF93DEBEE84:5.1, 0x7FF93DEBEFC4:3.0,
       0x7FF93B221974:2.3, 0x7FF93DEBF4C4:1.4, 0x7FF93DEBEEE4:0.9, 0x7FF93DEBF584:0.6}
tot = sum(obs.values())
print("%-8s %-26s %s" % ("доля", "вызов", "адрес"))
for a,p in sorted(obs.items(), key=lambda kv:-kv[1]):
    off = a - base
    nm = nt.get(off)
    if nm is None and 0 < a < base:
        nm = "другая DLL (win32u?)"
    print("%6.1f%%  %-26s %016X  +0x%X" % (100.0*p/tot, nm or "не опознан", a, off))
print()
print("Итого NtDelayExecution: %.1f%% сэмплов" % (100.0*obs[0x7FF93DEBF484]/tot))
