# A6: проверка по датам файлов, был ли завершённый стартовый сейв до окна П0/П1.
# Свидетельство: *_AntiCorruptionBackup.bak создаётся ВО ВРЕМЯ ЗАГРУЗКИ (копия .ark),
# а сам .ark переписывается только в момент реального сохранения.
import os, datetime
ARK = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\SavedArks"
def t(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(ARK, p))).strftime("%m-%d %H:%M:%S")
print("Сейчас на диске (после вахты 1):")
for f in sorted(os.listdir(ARK)):
    if f.lower().endswith(".ark") and "_" not in f.replace(".ark", ""):
        print("   %-34s %s" % (f, t(f)))
print()
print("Хронология слотов вахты 1 (из worklog.md):")
rows = [
 ("Genesis",  "запуск 00:32:48", "RCON готов 00:40:03", "П0/П1 00:42:26-00:46:46",
  "bak=00:37:54 (внутри загрузки)", "ark=00:32:47 -> первый автосейв 01:21:38"),
 ("TheIsland","запуск 01:33:43", "RCON готов 01:39:53", "П0/П1 01:42:13-01:46:32",
  "bak=01:37:56 (внутри загрузки)", "ark=11.11.2025 -> первый автосейв 02:07"),
 ("Fjordur",  "запуск 02:19:19", "RCON готов 02:26:01", "П0/П1 02:28:29-02:32:49",
  "bak=02:23:59 (внутри загрузки)", "ark=11.11.2025 -> первый автосейв 02:38/02:53"),
]
for r in rows:
    print("  %-10s %s | %s | %s" % (r[0], r[1], r[2], r[3]))
    print("             %s ; %s" % (r[4], r[5]))
