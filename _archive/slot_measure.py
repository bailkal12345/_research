# -*- coding: utf-8 -*-
"""
Слот вахты с детектором аварии (директива doit.txt §5 + §4 «отказоустойчивость»).

    python slot_measure.py <Карта> [--warmup 300] [--out slot-<Карта>.json]

Отличия от предыдущей версии: перед каждым этапом и после проверяется здоровье
стенда. Обнаружение падения (процесс мёртв / RCON не отвечает / появился
новый crashstack) немедленно прерывает слот и возвращает код 9 — драйвер
вахты тогда восстанавливает сейв из архива и уходит на следующий архив.
"""
import argparse
import datetime
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RCON_HOST", "192.168.8.218")
sys.path.insert(0, HERE)

import rcon  # noqa: E402
import threadcpu  # noqa: E402

PLUGIN_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf"
LOG = os.path.join(PLUGIN_DIR, "TickProf.log")
CRASH_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\Logs"

PROD_CONFIG = [
    "TickProf.fixclamp 0",
    "TickProf.maxfps 0",
    "TickProf.fncache 1",
    "TickProf.iscache 1",
    "TickProf.cachename 1",
    "TickProf.nochart 1",
    "TickProf.overlaptrim 2",
]

CRASHED = 9


def cmd(text, timeout=10):
    try:
        return rcon.rcon(text, timeout=timeout)
    except Exception:  # noqa: BLE001
        return None


def log_tail(n=120):
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            return [ln.rstrip() for ln in f.readlines()[-n:]]
    except OSError:
        return []


def game_tid():
    for ln in reversed(log_tail(400)):
        if "game thread tid=" in ln:
            return int(ln.strip().split("tid=")[-1])
    return 0


def newest_crash():
    files = glob.glob(os.path.join(CRASH_DIR, "*.crashstack"))
    if not files:
        return 0.0
    return max(os.path.getmtime(f) for f in files)


ARK_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\SavedArks"


def ark_state(card):
    """Слепок файлов сейва: автосохранение меняет mtime/size .ark и .bak.

    Нужен, потому что AutoSavePeriodMinutes=15, а сохранение мира на этом
    сейве занимает минуты и полностью искажает ms CPU/тик: в профиле Genesis
    00:28 весь исполняемый код — это сериализация (SerializeTaggedProperties,
    FSaveFileObjectWriter, UWorld::SaveToFile).
    """
    out = {}
    try:
        for n in os.listdir(ARK_DIR):
            low = n.lower()
            if low.endswith(".ark") or "anticorruption" in low:
                f = os.path.join(ARK_DIR, n)
                try:
                    out[n] = (os.path.getmtime(f), os.path.getsize(f))
                except OSError:
                    pass
    except OSError:
        pass
    return out


def save_idle(card, quiet=90, limit=900):
    """Ждёт, пока сохранение мира закончится (файлы не меняются quiet секунд)."""
    end = time.time() + limit
    last, since = ark_state(card), time.time()
    while time.time() < end:
        cur = ark_state(card)
        if cur != last:
            print("   сохранение мира идёт (%s)" % ",".join(sorted(cur)), flush=True)
            last, since = cur, time.time()
        elif time.time() - since >= quiet:
            return True
        time.sleep(15)
    return False


def health(crash_mark):
    """(ok, описание). Проверка стенда: процесс жив и тикает, RCON отвечает,
    нет нового краша. Заморозка — процесс жив, но CPU ≈ 0."""
    import freeze
    pid = threadcpu.find_pid()
    if isinstance(pid, (list, tuple)):
        pid = pid[0] if pid else 0
    if not pid:
        return False, "процесс ShooterGameServer не найден"
    if not game_tid():
        return False, "мир не инициализирован (нет game thread в логе плагина)"
    if newest_crash() > crash_mark:
        return False, "появился crashstack"
    fz, val = freeze.is_frozen(pid, probe=8.0)
    if fz:
        return False, "заморозка: процесс жив, CPU=%.3f" % val
    if cmd("ListPlayers", timeout=6) is None:
        return False, "RCON не отвечает"
    return True, "жив (pid %s, tid %s, CPU=%.2f)" % (pid, game_tid(), val)


def wait_ready(minutes=15):
    """Ждём готовности мира; заморозку (процесс жив, CPU≈0) ловим за ~3 мин."""
    import freeze
    end = time.time() + minutes * 60
    hits = 0
    while time.time() < end:
        if cmd("ListPlayers", timeout=5) is not None and game_tid():
            return True
        pid = threadcpu.find_pid()
        pid = (pid[0] if isinstance(pid, (list, tuple)) else pid) if pid else 0
        if pid:
            fz, val = freeze.is_frozen(pid, probe=20.0)
            if fz:
                hits += 1
                print("ЗАМОРОЗКА pid %d, CPU=%.3f (%d/2)" % (pid, val, hits), flush=True)
                if hits >= 2:
                    print("заморозка подтверждена — снимаю процесс", flush=True)
                    os.system("taskkill /PID %d /F >nul 2>&1" % pid)
                    return False
            else:
                hits = 0
        time.sleep(8)
    return False


def cpu_of(tid, seconds=4):
    vals = []
    for _ in range(seconds):
        v = threadcpu.cpu_times(tid)
        if v is not None:
            vals.append(v)
        time.sleep(1.0)
    if len(vals) < 2:
        return 0.0
    return (vals[-1] - vals[0]) / (len(vals) - 1)


def window(tid, seconds, crash_mark, card="genesis"):
    ark_mark = ark_state(card)
    # запоминаем конец лога ДО запроса: парсить можно только то, что плагин
    # дописал после него, иначе при упавшем сервере подхватывается строка
    # пер��дыдущего окна и в отчёт идут чужие числа
    try:
        mark = os.path.getsize(LOG)
    except OSError:
        mark = 0
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
    c1 = cpu_of(tid, 3)
    frames = wall = 0.0
    fresh = []
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            f.seek(mark)
            fresh = f.readlines()
    except OSError:
        fresh = []
    # Плагин пишет итог окна строкой вида
    #   window итог: t/s=50 cpu=1390s ms/tick=137 frame_ms=19 busy=695% save=idle VALID
    # (метка "perf окно" - устаревшая, из-за неё парсер молчал и т/с было 0).
    # Поля cpu=/ms/tick=/busy= в этой строке НЕДОСТОВЕРНЫ: базовый отсчёт
    # процессора не вычитается. Достоверны t/s=, frame_ms=, save=, VALID/CONTAMINATED.
    frame_ms = 0.0
    plugin_tps = 0.0
    saved = ""
    valid = ""
    for ln in reversed(fresh):
        if "window" in ln and "t/s=" in ln:
            for tok in ln.split():
                if tok.startswith("t/s="):
                    plugin_tps = float(tok[4:])
                elif tok.startswith("frame_ms="):
                    frame_ms = float(tok[9:])
                elif tok.startswith("save="):
                    saved = tok[5:]
                elif tok in ("VALID", "CONTAMINATED"):
                    valid = tok
            if plugin_tps <= 0 and frames and wall:
                plugin_tps = frames / wall
            break
    ok, why = health(crash_mark)
    tps = plugin_tps or (frames / wall if wall else 0.0)
    cpu = (c0 + c1) / 2.0
    dirty = ark_state(card) != ark_mark
    if valid == "CONTAMINATED":
        dirty = True
    return {"tps": tps, "cpu": cpu,
            "ms_tick": 1000.0 * cpu / tps if tps else 0.0,
            "frame_ms": frame_ms, "save": saved, "verdict": valid,
            "healthy": ok, "why": why, "contaminated": dirty,
            # кросс-чек: кадр плагина против внешнего счёта CPU/тик
            "cross_diff_pct": (abs(1000.0 * cpu / tps - frame_ms) / frame_ms * 100.0)
                               if (tps and frame_ms) else None}


def profile(seconds=60):
    cmd("TickProf.start %d" % seconds)
    time.sleep(seconds + 15)
    files = sorted((f for f in os.listdir(PLUGIN_DIR) if f.endswith(".bin")),
                   key=lambda f: os.path.getmtime(os.path.join(PLUGIN_DIR, f)))
    return os.path.join(PLUGIN_DIR, files[-1]) if files else ""


def top_symbols(bin_path, n=20):
    if not bin_path or not os.path.exists(bin_path):
        return []
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, "symbolize.py"), bin_path,
                              "--exclude-idle", "--top", str(n)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=600).stdout
    except Exception:
        return []
    rows, started = [], False
    for ln in out.splitlines():
        if ln.startswith("cnt") and "function" in ln:
            started = True
            continue
        if started and ln.strip():
            p = ln.split()
            if len(p) >= 3:
                rows.append((p[0] + " " + p[1], " ".join(p[2:])))
    return rows


def saveworld_freeze(runs=2):
    out = []
    for _ in range(runs):
        t0 = time.time()
        cmd("saveworld")
        gap = 0.0
        while time.time() - t0 < 180:
            time.sleep(0.2)
            if cmd("ListPlayers", timeout=1) is not None:
                gap = time.time() - t0
                break
        out.append(gap * 1000.0)
        time.sleep(45)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("map")
    ap.add_argument("--warmup", type=int, default=300)
    ap.add_argument("--no-profile", dest="profile", action="store_false",
                    help="не снимать профиль (он роняет сервер на Genesis)")
    args = ap.parse_args()

    res = {"map": args.map, "started": datetime.datetime.now().isoformat(timespec="seconds")}
    crash_mark = newest_crash()
    print("СЛОТ %s, старт %s" % (args.map, res["started"]), flush=True)

    if not wait_ready():
        res["error"] = "сервер не поднялся за 15 мин (авария на загрузке сейва?)"
        _save(res, args.map)
        print("ПРОПУСК:", res["error"], flush=True)
        return CRASHED

    tid = game_tid()
    res["tid"] = tid
    for c in PROD_CONFIG:
        cmd(c)
        time.sleep(3)
    ok, why = health(crash_mark)
    if not ok:
        res["error"] = "после конфигурации: " + why
        _save(res, args.map)
        print("ПРОПУСК:", res["error"], flush=True)
        return CRASHED

    print("прогрев %d с" % args.warmup, flush=True)
    time.sleep(args.warmup)
    ok, why = health(crash_mark)
    if not ok:
        res["error"] = "на прогреве: " + why
        _save(res, args.map)
        print("ПРОПУСК:", res["error"], flush=True)
        return CRASHED
    res["cpu_warm"] = cpu_of(tid, 6)

    # ---- П0/П1 ----
    print("П0/П1: базовая линия (жду конца сохранения мира)", flush=True)
    save_idle(args.map.lower())
    res["p01"] = window(tid, 240, crash_mark, args.map.lower())
    print("   t/s %.2f | cpu %.3f | %.2f мс/тик | %s | искажено сохранением: %s"
          % (res["p01"]["tps"], res["p01"]["cpu"], res["p01"]["ms_tick"], res["p01"]["why"],
             res["p01"].get("contaminated")), flush=True)
    if not res["p01"]["healthy"] or res["p01"]["tps"] <= 0:
        res["error"] = "П0/П1 без данных: " + res["p01"]["why"]
        _save(res, args.map)
        print("ПРОПУСК:", res["error"], flush=True)
        return CRASHED

    # ---- П2 ----
    print("П2: overlaptrim=0 (жду конца сохранения, оседание 180 с, окно 300 с)", flush=True)
    save_idle(args.map.lower())
    cmd("TickProf.overlaptrim 0")
    time.sleep(180)
    res["p2_off"] = window(tid, 300, crash_mark, args.map.lower())
    print("   trim=0: t/s %.2f | cpu %.3f | %.2f мс/тик | %s"
          % (res["p2_off"]["tps"], res["p2_off"]["cpu"], res["p2_off"]["ms_tick"],
             res["p2_off"]["why"]), flush=True)

    print("П2: overlaptrim=2 (жду конца сохранения, оседание 180 с, окно 300 с)", flush=True)
    save_idle(args.map.lower())
    cmd("TickProf.overlaptrim 2")
    time.sleep(180)
    res["p2_on"] = window(tid, 300, crash_mark, args.map.lower())
    print("   trim=2: t/s %.2f | cpu %.3f | %.2f мс/тик | %s"
          % (res["p2_on"]["tps"], res["p2_on"]["cpu"], res["p2_on"]["ms_tick"],
             res["p2_on"]["why"]), flush=True)

    if not (res["p2_off"]["healthy"] and res["p2_on"]["healthy"]):
        res["error"] = "П2: авария между окнами"
        _save(res, args.map)
        print("ПРОПУСК:", res["error"], flush=True)
        return CRASHED

    d = (res["p2_off"]["ms_tick"] - res["p2_on"]["ms_tick"]) / res["p2_off"]["ms_tick"] * 100 \
        if res["p2_off"]["ms_tick"] else 0.0
    res["p2_delta_pct"] = d
    print("   дельта мс/тик: %+.1f%%" % (-d), flush=True)

    # ---- П3 ----
    print("П3: SaveWorld, два прогона", flush=True)
    res["p3_ms"] = saveworld_freeze()
    print("   фриз: %s мс" % ["%.0f" % v for v in res["p3_ms"]], flush=True)

    # ---- профиль и переписи ПОСЛЕДНИМИ ----
    # На Genesis профилёр (TickProf.start 60) ронял сервер сразу после сэмпла:
    # все .bin/.ret/.wait успевали записаться, но процесс умирал без крашстака
    # и без дампа. Если такое повторится, П0/П1 и П2/П3 уже сохранены.
    if args.profile:
        print("профиль и переписи (последним шагом)", flush=True)
        save_idle(args.map.lower())
        binp = profile(60)
        res["profile"] = os.path.basename(binp) if binp else ""
        res["top20"] = top_symbols(binp, 20)
        cmd("TickProf.ticklist")
        cmd("TickProf.ticksets")
        cmd("TickProf.overlapsizes")
        time.sleep(20)
        res["censuses"] = [ln.split(" ", 1)[-1] for ln in log_tail(60)
                           if any(k in ln for k in ("ticklist:", "ticksets:", "overlapsizes:"))]
        ok, why = health(crash_mark)
        res["alive_after_profile"] = ok
        print("   после профиля: %s" % why, flush=True)

    res["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    _save(res, args.map)
    print("ИТОГ сохранён", flush=True)
    return 0


def _save(res, card):
    res["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    out = os.path.join(HERE, "slot-%s.json" % card)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "make_report.py"), card],
                       capture_output=True, text=True, timeout=180)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())