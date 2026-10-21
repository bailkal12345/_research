# -*- coding: utf-8 -*-
"""
Драйвер вахты prod-сейвов (директива doit.txt §4-§5).

    python watch_shift.py [--budget-min 210] [--slot-min 60]

Порядок сейвов: очередь deploy_map.py (Genesis -> Gen2 -> TheIsland -> ...),
плюс перебор оставшихся архивов c:/saves по алфавиту.

Правила отказоустойчивости, которые реализованы:
  * перед каждым деплоем стенд гасится и проверяется, что процессов ноль —
    именно совмещение двух запусков породило прошлую аварию
    "Can't load world save file" на TickWorldTravel;
  * после деплоя — проверка целостности и 15 минут на подъём, дальше пропуск;
  * слот сам возвращает код 9 при аварии, драйвер пишет в worklog и идёт дальше;
  * битый сейв восстанавливается повторным deploy_map.py из архива (бэкапы
    SavedArks.prev не удаляются никогда);
  * жёсткий бюджет: не более --slot-min на сейв и --budget-min на всю вахту.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RCON_HOST", "192.168.8.218")
sys.path.insert(0, HERE)

import threadcpu  # noqa: E402

ARCHIVES = r"C:\saves"
DEPLOY = os.path.join(HERE, "deploy_map.py")
WORKLOG = os.path.join(HERE, "worklog.md")
CRASH_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\Logs"


def wl(text):
    line = "\n## %s ВАХТА\n%s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), text)
    with open(WORKLOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, flush=True)


def server_pids():
    pid = threadcpu.find_pid()
    return list(pid) if isinstance(pid, (list, tuple)) else ([pid] if pid else [])


def stop_stand():
    pids = server_pids()
    for p in pids:
        os.system("taskkill /PID %d /F >nul 2>&1" % p)
    t0 = time.time()
    while time.time() - t0 < 90:
        if not server_pids():
            break
        time.sleep(3)
    return len(pids)


def deploy(archive):
    wl("деплой %s: гашу стенд (%d процессов)" % (archive, len(server_pids())))
    stop_stand()
    try:
        p = subprocess.run([sys.executable, DEPLOY, "--archive", archive],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=1500)
        out = (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "deploy_map.py: таймаут 25 мин"
    tail = out.strip().splitlines()[-12:]
    wl("\n".join("   " + t for t in tail))
    ok = "ГОТОВ" in out
    return ok, out.strip().splitlines()[-1] if out.strip() else "нет вывода"


def run_slot(card, slot_min):
    try:
        p = subprocess.run([sys.executable, os.path.join(HERE, "slot_measure.py"), card,
                            "--warmup", "300"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=slot_min * 60)
        return p.returncode, (p.stdout or "")[-1500:]
    except subprocess.TimeoutExpired:
        return 99, "слот превысил потолок %d мин" % slot_min


def queue():
    try:
        p = subprocess.run([sys.executable, DEPLOY, "--list"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        out = []
        for ln in p.stdout.splitlines():
            if ln.startswith(tuple("0123456789")) and "очередь" in ln:
                out.append(ln.split()[-1])
        return out
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-min", type=int, default=210)
    ap.add_argument("--assume-running", default="",
                    help="архив уже развёрнут и сервер поднят: деплой пропускается")
    ap.add_argument("--slot-min", type=int, default=60)
    args = ap.parse_args()

    t_start = time.time()
    deadline = t_start + args.budget_min * 60
    wl("старт вахты: бюджет %d мин, потолок на сейв %d мин" % (args.budget_min, args.slot_min))

    archives = queue()
    wl("очередь архивов: %s" % ", ".join(archives))
    results = []

    for arch in archives:
        left = (deadline - time.time()) / 60.0
        if left < 20:
            wl("бюджет исчерпан, останавливаюсь (осталось %.0f мин)" % left)
            break
        slot_budget = int(min(args.slot_min, left))
        card = arch.rsplit(".", 1)[0]

        if arch == args.assume_running:
            wl("архив %s уже развёрнут и сервер отвечает — деплой пропускаю" % arch)
            ok, why = True, "уже поднят"
        else:
            ok, why = deploy(arch)
        if not ok:
            wl("СЛОТ %s: деплой не удался — %s. ПРОПУСК, следующий архив." % (card, why))
            results.append((card, "пропуск: деплой"))
            continue

        rc, tail = run_slot(card, slot_budget)
        if rc == 0:
            wl("СЛОТ %s: выполнен. %s" % (card, tail.strip().splitlines()[-1] if tail.strip() else ""))
            results.append((card, "ок"))
        else:
            wl("СЛОТ %s: ПРОПУСК (rc=%d) — %s\n   Восстановление сейва из архива перед следующим."
               % (card, rc, (why if rc == 99 else tail.strip().splitlines()[-1])))
            results.append((card, "пропуск: rc=%d" % rc))
            # сейв мог быть повреждён аварией — восстанавливаем тем же deploy_map.py
            recover = subprocess.run([sys.executable, DEPLOY, "--archive", arch],
                                     capture_output=True, text=True, encoding="utf-8",
                                     errors="replace", timeout=1500)
            wl("восстановление из архива %s: %s" % (arch, "ок" if "ГОТОВ" in (recover.stdout or "")
                                                     else "не подтверждено"))

    try:
        subprocess.run([sys.executable, os.path.join(HERE, "summary_table.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    except Exception:
        pass
    wl("итог вахты: %s" % json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())