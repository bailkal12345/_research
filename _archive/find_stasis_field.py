import subprocess, os, io
# быстрый поиск по всем полям
out = subprocess.run([r"C:\Dev\_research\fieldcheck.exe", r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.pdb", "APrimalCharacter"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace",
                     env={**os.environ, "DIA_DLL": r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\msdia140.dll"})
hits = [l for l in out.stdout.splitlines() if "tasi" in l.lower()]
print("\n".join(hits[:14]) or "полей со 'tasis' не найдено")
