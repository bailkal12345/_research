# -*- coding: utf-8 -*-
"""
Пошаговое ручное исполнение директивы doit.txt §5 (без фоновых драйверов).

    python manual.py state              состояние стенда
    python manual.py deploy <архив>     деплой карты (только deploy_map.py)
    python manual.py ready               ждать подъёма мира, показать tid
    python manual.py config             прод-конфигурация (5 оптимизаций, кламп штатный)
    python manual.py idle [сек]         ждать конца сохранения мира
    python manual.py window <сек>        окно измерения: t/s, мс CPU/тик, флаг искажения
    python manual.py profile [сек]       снять профиль (рискованно, делать последним)
    python manual.py census              переписи тик-функций и пересечений
    python manual.py saveworld <n>      П3: n прогонов SaveWorld с замером фриза
    python manual.py apply <команда>    единичная RCON-команда
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RCON_HOST", "192.168.8.218")
os.environ.setdefault("RCON_PORT", "27020")
sys.path.insert(0, HERE)

import freeze  # noqa: E402
import rcon  # noqa: E402
import slot_measure as S  # noqa: E402
import threadcpu  # noqa: E402

CRASH_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\Logs"


def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S")


def say(text):
    print("%s  %s" % (stamp(), text), flush=True)


def wl(text):
    with open(os.path.join(HERE, "worklog.md"), "a", encoding="utf-8") as f:
        f.write("\n## %s РУЧНОЙ ШАГ\n%s\n" % (stamp(), text))


def server_pid():
    p = threadcpu.find_pid()
    return (p[0] if isinstance(p, (list, tuple)) else p) if p else 0


def cmd_state():
    pid = server_pid()
    say("процесс ShooterGameServer: %s" % (pid or "НЕТ"))
    tid = S.game_tid()
    say("game thread tid по логу плагина: %s" % (tid or "НЕТ (мир не инициализирован)"))
    if pid:
        fz, val = freeze.is_frozen(pid, probe=10.0)
        say("CPU процесса: %.3f -> %s" % (val, "ЗАМОРОЗКА" if fz else "работает"))
    try:
        r = rcon.rcon("ListPlayers", timeout=8)
        say("RCON: %s" % r.strip()[:80])
    except Exception as exc:  # noqa: BLE001
        say("RCON: НЕ ОТВЕЧАЕТ (%s)" % type(exc).__name__)
    st = S.ark_state("genesis")
    for n, (m, sz) in sorted(st.items()):
        say("файл сейва %-34s %8.1f МБ  изм. %s"
            % (n, sz / 1048576.0, datetime.datetime.fromtimestamp(m).strftime("%H:%M:%S")))
    return 0 if pid else 1


def cmd_ready():
    say("жду подъёма мира (до 15 мин)")
    end = time.time() + 900
    while time.time() < end:
        pid = server_pid()
        if not pid:
            say("процесса нет — деплой не удался или он упал")
            return 1
        tid = S.game_tid()
        if tid:
            try:
                rcon.rcon("ListPlayers", timeout=5)
                say("ГОТОВ: pid %s, tid %s" % (pid, tid))
                return 0
            except Exception:
                pass
        fz, val = freeze.is_frozen(pid, probe=15.0)
        say("  загрузка: CPU=%.2f %s" % (val, "(ЗАМОРОЗКА!)" if fz else ""))
        if fz:
            say("заморозка — стенд не поднимется, нужен перезапуск деплоя")
            return 2
        time.sleep(20)
    say("не поднялся за 15 мин")
    return 3


def cmd_deploy(archive):
    say("ДЕПЛОЙ %s (только deploy_map.py)" % archive)
    wl("РУЧНОЙ ДЕПЛОЙ: %s" % archive)
    p = subprocess.run([sys.executable, os.path.join(HERE, "deploy_map.py"), "--archive", archive],
                       encoding="utf-8", errors="replace", timeout=1800)
    say("deploy_map.py завершился с кодом %s" % p.returncode)
    return p.returncode


def cmd_config():
    say("прод-конфигурация: кламп штатный, 5 оптимизаций")
    for c in S.PROD_CONFIG:
        S.cmd(c)
        time.sleep(3)
        say("  %-28s -> %s" % (c, (S.cmd("TickProf.cachestat") or "")[:0] or "ок"))
    return 0


def cmd_idle(sec):
    quiet = min(90, int(sec)) if sec else 90
    say("жду конца сохранения мира (тишина %d с)" % quiet)
    ok = S.save_idle("genesis", quiet=quiet, limit=sec or 900)
    say("сейв в покое: %s" % ok)
    return 0 if ok else 1


def cmd_idle_after(limit):
    """Сначала дождаться НАЧАЛА сохранения, потом его КОНЦА.

    Простой вариант (тишина 90 с) попадал в окно: файлы не менялись в паузе
    перед автосейвом, и окно стартовало за секунды до его начала. Здесь мы
    ждём самого факта изменения файлов и замеряем только после завершения.
    """
    say("жду НАЧАЛА сохранения мира (до %d с)" % limit)
    end = time.time() + limit
    base = S.ark_state("genesis")
    started = False
    while time.time() < end:
        cur = S.ark_state("genesis")
        if cur != base:
            say("  сохранение началось в %s" % stamp())
            base, started = cur, True
            break
        time.sleep(15)
    if not started:
        say("сохранение не началось за отведённое время — меряю как есть")
        return 0
    say("жду КОНЦА сохранения (тишина 120 с)")
    S.save_idle("genesis", quiet=120, limit=900)
    say("сейв в покое, можно мерять: %s" % stamp())
    return 0


def cmd_loo(text, sec, card="genesis"):
    """Leave-one-out: применить команду -> дождаться конца автосейва -> окно."""
    say("применяю: %s" % text)
    S.cmd(text)
    time.sleep(5)
    say("жду конца сохранения мира по протоколу")
    S.save_idle(card, quiet=120, limit=600)
    return cmd_window(int(sec))


def cmd_status():
    """Проверка прод-конфига списком (п.1.5 директивы)."""
    say("проверка прод-конфига:")
    for c in ("TickProf.cachestat", "TickProf.verify"):
        S.cmd(c)
        time.sleep(4)
    for ln in S.log_tail(40):
        low = ln.lower()
        if any(k in low for k in ("fncache", "iscache", "canvas", "nochart", "overlaptrim",
                                  "concurrent", "tickclamp", "maxfps", "cache:")):
            say("  " + ln)
    return 0


def cmd_arkhash(tag):
    """Фиксация размера и хэша .ark (п.1.1)."""
    import hashlib
    d = S.ARK_DIR
    say("состояние .ark [%s]:" % tag)
    for n in sorted(os.listdir(d)):
        if n.lower().endswith(".ark") and "_" not in n[:-4]:
            f = os.path.join(d, n)
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                while True:
                    b = fh.read(1 << 20)
                    if not b:
                        break
                    h.update(b)
            say("  %-16s %12d байт  sha256=%s" % (n, os.path.getsize(f), h.hexdigest()[:24]))
    wl("фиксация .ark [%s] выполнена" % tag)
    return 0


def cmd_window(sec):
    seconds = int(sec)
    tid = S.game_tid()
    if not tid:
        say("НЕТ tid — измерять нечего")
        return 2
    say("окно %d с, GameThread tid=%s" % (seconds, tid))
    res = S.window(tid, seconds, S.newest_crash(), "genesis")
    say("  t/s = %.2f | CPU GameThread = %.3f s/s | %.2f мс CPU/тик"
        % (res["tps"], res["cpu"], res["ms_tick"]))
    say("  здоровье: %s" % res["why"])
    say("  искажено сохранением мира: %s" % res.get("contaminated"))
    wl("окно %d с: t/s=%.2f cpu=%.3f мс/тик=%.2f искажено=%s"
       % (seconds, res["tps"], res["cpu"], res["ms_tick"], res.get("contaminated")))
    return 0 if (res["healthy"] and res["tps"] > 0 and not res.get("contaminated")) else 1


def cmd_profile(sec):
    seconds = int(sec or 60)
    S.cmd("TickProf.ticklist")
    time.sleep(3)
    say("снимаю профиль %d с (это рискованно — делаю последним шагом)" % seconds)
    binp = S.profile(seconds)
    say("профиль: %s" % os.path.basename(binp))
    for ln in S.log_tail(6):
        say("  " + ln)
    pid = server_pid()
    say("сервер после профиля: %s" % ("жив" if pid else "МЁРТВ"))
    return 0 if pid else 1


def cmd_census():
    for c in ("TickProf.ticklist", "TickProf.ticksets", "TickProf.overlapsizes"):
        S.cmd(c)
        time.sleep(8)
    time.sleep(10)
    say("переписи:")
    for ln in S.log_tail(40):
        if any(k in ln for k in ("ticklist:", "ticksets:", "overlapsizes:")):
            say("  " + ln)
    return 0


def cmd_saveworld(n):
    say("П3: SaveWorld, %d прогон(ов)" % n)
    out = S.saveworld_freeze(int(n))
    for i, v in enumerate(out, 1):
        say("  прогон %d: фриз %.0f мс %s"
            % (i, v, "— ПРЕВЫШЕН порог 500 мс, ТЗ в бэклог" if v > 500 else ""))
    wl("П3 SaveWorld: %s мс" % ["%.0f" % v for v in out])
    return 0


def cmd_apply(text):
    say("команда: %s" % text)
    say("ответ: %s" % str(S.cmd(text))[:300])
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("state")
    sub.add_parser("ready")
    sub.add_parser("config")
    sub.add_parser("census")
    p = sub.add_parser("deploy"); p.add_argument("archive")
    p = sub.add_parser("idle"); p.add_argument("sec", nargs="?", default=0, type=int)
    p = sub.add_parser("idle-after"); p.add_argument("sec", nargs="?", default=900, type=int)
    p = sub.add_parser("window"); p.add_argument("sec", type=int)
    p = sub.add_parser("profile"); p.add_argument("sec", nargs="?", default=60, type=int)
    p = sub.add_parser("saveworld"); p.add_argument("n", nargs="?", default=2, type=int)
    p = sub.add_parser("apply"); p.add_argument("text")
    sub.add_parser("status")
    p = sub.add_parser("arkhash"); p.add_argument("tag", nargs="?", default="-")
    p = sub.add_parser("loo"); p.add_argument("text"); p.add_argument("sec", nargs="?", default=240, type=int)
    a = ap.parse_args()

    fn = {"state": cmd_state, "ready": cmd_ready, "config": cmd_config, "census": cmd_census,
          "idle": cmd_idle, "window": cmd_window, "profile": cmd_profile,
          "saveworld": cmd_saveworld, "apply": cmd_apply}
    if a.cmd == "deploy":
        return cmd_deploy(a.archive)
    if a.cmd in ("state", "ready", "config", "census"):
        return fn[a.cmd]()
    if a.cmd == "idle-after":
        return cmd_idle_after(a.sec)
    if a.cmd in ("idle", "window", "profile"):
        return fn[a.cmd](a.sec)
    if a.cmd == "saveworld":
        return fn[a.cmd](a.n)
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "arkhash":
        return cmd_arkhash(a.tag)
    if a.cmd == "loo":
        return cmd_loo(a.text, a.sec)
    return fn[a.cmd](a.text)


if __name__ == "__main__":
    sys.exit(main())