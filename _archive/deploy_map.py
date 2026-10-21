# -*- coding: utf-8 -*-
"""
deploy_map.py — ЕДИНСТВЕННЫЙ разрешённый способ смены карты на стенде.

    python deploy_map.py --list                 показать очередь архивов
    python deploy_map.py --archive Genesis.zip  развернуть конкретный архив
    python deploy_map.py --next                 развернуть следующий из очереди

Процедура (директива §4):
  распаковка в temp → стоп сервера → бэкап SavedArks → SavedArks.prev/<ts>
  (никогда не удаляется) → копирование содержимого в Saved/SavedArks
  (Config не трогаем) → валидация → запуск предписанной строкой →
  готовность = ответ RCON.

Красные линии: Saved/Config и SavedArks.prev не удаляются никогда.
"""
import argparse
import datetime
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

SERVER = r"C:\asmdata\Servers\Server1\ShooterGame"
SAVES = os.path.join(SERVER, "Saved", "SavedArks")
PREV = os.path.join(SERVER, "Saved", "SavedArks.prev")
EXE = os.path.join(SERVER, "Binaries", "Win64", "ShooterGameServer.exe")
ARCHIVES = r"C:\saves"

# 7z не прописан в PATH — вызывать только по абсолютному пути
SEVENZIP = next((p for p in (r"C:\Program Files\7-Zip\7z.exe",
                              r"C:\Program Files (x86)\7-Zip\7z.exe")
                 if os.path.exists(p)), "7z")

# Порядок очереди из директивы: Genesis → Gen2 → TheIsland → Ragnarok → прочие.
PRIORITY = ["Genesis", "Gen2", "TheIsland", "TheCenter", "ScorchedEarth_P",
            "Ragnarok", "Aberration_P", "Extinction", "Valguero_P",
            "CrystalIsles_P", "LostIsland", "Fjordur"]

RCON_HOST = os.environ.get("RCON_HOST", "192.168.8.218")
RCON_PORT = os.environ.get("RCON_PORT", "27020")


def log(msg):
    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = "%s %s" % (stamp, msg)
    print(line, flush=True)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "worklog.md"),
                  "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def map_name_from_archive(path):
    """Имя карты: из имени архива, а если не узнали — изнутри по *.ark."""
    stem = os.path.splitext(os.path.basename(path))[0]
    for known in PRIORITY:
        if stem.lower().startswith(known.lower()):
            return known
    # попытка вскрыть архив и посмотреть на имя .ark
    try:
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    base = os.path.basename(n)
                    if base.lower().endswith(".ark"):
                        return os.path.splitext(base)[0]
        else:
            out = subprocess.run([SEVENZIP, "l", "-ba", "-slt", path],
                                 capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=120).stdout
            for line in out.splitlines():
                if "Path = " in line and line.strip().lower().endswith(".ark"):
                    return os.path.splitext(os.path.basename(line.split("=", 1)[1].strip()))[0]
    except Exception as exc:  # noqa: BLE001
        log("автоопределение не удалось (%s): %s" % (os.path.basename(path), exc))
    return None


def build_queue():
    found = {}
    for pat in ("*.zip", "*.7z"):
        for p in glob.glob(os.path.join(ARCHIVES, pat)):
            nm = map_name_from_archive(p)
            if nm:
                found[nm] = p
    def rank(n):
        return (PRIORITY.index(n) if n in PRIORITY else len(PRIORITY), n)
    return [(n, found[n]) for n in sorted(found, key=rank)]


def stop_server():
    subprocess.run(["taskkill", "/F", "/IM", "ShooterGameServer.exe"],
                   capture_output=True, text=True)
    for _ in range(30):
        if not subprocess.run(["tasklist", "/FI", "IMAGENAME eq ShooterGameServer.exe"],
                              capture_output=True, text=True).stdout.count("ShooterGameServer.exe"):
            return True
        time.sleep(1)
    return False


def unpack(path, dest):
    os.makedirs(dest, exist_ok=True)
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            z.extractall(dest)
    else:
        r = subprocess.run([SEVENZIP, "x", "-y", f"-o{dest}", path],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900)
        if r.returncode != 0:
            raise RuntimeError("7z вернул %d: %s" % (r.returncode, r.stdout[-300:]))
    # содержимое может лежать во вложенной папке — поднимаем уровнем
    entries = os.listdir(dest)
    if len(entries) == 1 and os.path.isdir(os.path.join(dest, entries[0])):
        inner = os.path.join(dest, entries[0])
        for n in os.listdir(inner):
            shutil.move(os.path.join(inner, n), os.path.join(dest, n))
        os.rmdir(inner)
    return dest


def backup_savedarks():
    """Копия текущего SavedArks в SavedArks.prev/<timestamp>. Никогда не удалять."""
    os.makedirs(PREV, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(PREV, ts)
    os.makedirs(dst, exist_ok=True)
    n = 0
    for n_ in os.listdir(SAVES):
        s = os.path.join(SAVES, n_)
        try:
            shutil.copy2(s, os.path.join(dst, n_))
            n += 1
        except OSError:
            pass
    log("бэкап SavedArks → %s (%d файлов)" % (dst, n))
    return dst


def validate(map_name):
    ark = os.path.join(SAVES, map_name + ".ark")
    if not os.path.exists(ark):
        return False, "нет %s.ark" % map_name
    size = os.path.getsize(ark)
    if size < 5 * 1024 * 1024:
        return False, "размер %s невменяем (%d байт)" % (map_name + ".ark", size)
    profiles = len(glob.glob(os.path.join(SAVES, "*.arkprofile")))
    if profiles == 0:
        return False, "нет ни одного .arkprofile"
    return True, "ark %.1f МБ, профилей %d" % (size / 1048576.0, profiles)


def copy_in(src, map_name):
    # копируем ТОЛЬКО содержимое сейва; Saved/Config не трогаем
    copied = 0
    for n in os.listdir(src):
        s = os.path.join(src, n)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(SAVES, n))
            copied += 1
    log("скопировано файлов в SavedArks: %d" % copied)


def launch(map_name):
    """Прод-строка запуска (Saved/Config/WindowsServer/RunServer.cmd).

    Именно эта строка дважды поднималась нормально, тогда как bench-вариант
    с SessionName=.../RCONEnabled=... замораживал сервер: процесс остаётся жив,
    но CPU = 0 во всех потоках, первый тик не происходит. Флаг -nossteamclient
    задачу не решил (SteamSocketsOpenSource всё равно инициализируется), поэтому
    bench-строка заменена на прод целиком.
    RCON берётся из GameUserSettings.ini: RCONEnabled=True, RCONPort=27020.
    """
    args = ("%s?listen?MultiHome=192.168.8.218?Port=7777?QueryPort=27015"
            "?MaxPlayers=70?AllowCrateSpawnsOnTopOfStructures=True" % map_name)
    flags = ["-EnableIdlePlayerKick", "-NoBattlEye", "-forcerespawndinos",
             "-servergamelog", "-servergamelogincludetribelogs",
             "-ServerRCONOutputTribeLogs", "-NoHangDetection",
             "-noundermeshchecking", "-noundermeshkilling", "-nossteamclient",
             "-game", "-server", "-log", "-MinimumTimeBetweenInventoryRetrieval=3600",
             "-newsaveformat", "-usestore", "-BackupTransferPlayerDatas"]
    cmd = [EXE, args] + flags
    log("запуск (прод-строка, карта %s)" % map_name)
    subprocess.Popen(cmd, cwd=os.path.join(SERVER, "Binaries", "Win64"))


def rcon_ready(timeout_sec=900):
    """Готовность = ответ RCON. Ждём не дольше отведённого времени.

    Дополнительно ловим заморозку: процесс жив, но CPU ≈ 0 две проверки
    подряд — значит мир не пошёл и ждать бессмысленно. Такой случай
    закрывается за ~3 минуты вместо 15.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import freeze
    import threadcpu
    deadline = time.time() + timeout_sec
    freeze_hits = 0
    while time.time() < deadline:
        try:
            r = subprocess.run([sys.executable, os.path.join(here, "rcon.py"), "ListPlayers"],
                               capture_output=True, text=True, timeout=20,
                               env={**os.environ, "RCON_HOST": RCON_HOST, "RCON_PORT": RCON_PORT})
            out = (r.stdout or "") + (r.stderr or "")
            if "timed out" not in out and "ConnectionRefused" not in out and "refused" not in out.lower():
                log("RCON отвечает: %s" % out.strip()[:120])
                return True
        except Exception:
            pass

        p = threadcpu.find_pid()
        pid = (p[0] if isinstance(p, (list, tuple)) else p) if p else 0
        if pid:
            fz, val = freeze.is_frozen(pid, probe=20.0)
            if fz:
                freeze_hits += 1
                log("ЗАМОРОЗКА: pid %d, доля CPU = %.3f (проверка %d/2)" % (pid, val, freeze_hits))
                if freeze_hits >= 2:
                    log("процесс жив, но не тикает — заморозка подтверждена, снимаю его")
                    os.system("taskkill /PID %d /F >nul 2>&1" % pid)
                    return False
            else:
                freeze_hits = 0
                log("стенд грузится, CPU = %.2f" % val)
        time.sleep(10)
    return False


def deploy(path):
    tmp = tempfile.mkdtemp(prefix="arkdeploy_")
    try:
        map_name = map_name_from_archive(path)
        if not map_name:
            log("ПРОПУСК: не распознан архив %s" % os.path.basename(path))
            return False
        log("деплой %s из %s" % (map_name, os.path.basename(path)))
        log("распаковка в %s" % tmp)
        unpack(path, tmp)
        if not stop_server():
            log("ПРОПУСК: сервер не остановился")
            return False
        backup_savedarks()
        copy_in(tmp, map_name)
        ok, msg = validate(map_name)
        log("валидация: %s" % msg)
        if not ok:
            log("ПРОПУСК: валидация не пройдена (%s)" % msg)
            return False
        launch(map_name)
        if not rcon_ready(900):
            log("ПРОПУСК: RCON не ответил за 15 минут")
            return False
        log("ГОТОВ: карта %s, RCON %s:%s" % (map_name, RCON_HOST, RCON_PORT))
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    queue = build_queue()
    if args.list or (not args.archive and not args.next):
        for nm, p in queue:
            log("очередь: %-20s %s" % (nm, os.path.basename(p)))
        return 0
    if args.archive:
        target = next((p for n, p in queue if n.lower() == args.archive.lower()), None) \
            or os.path.join(ARCHIVES, args.archive)
        return 0 if deploy(target) else 2
    for nm, p in queue:
        log("пробую следующий: %s" % nm)
        if deploy(p):
            return 0
    log("все архивы исчерпаны или негодны")
    return 3


if __name__ == "__main__":
    sys.exit(main())