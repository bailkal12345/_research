import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from botwatch import bot_call, tail_state, server_players  # noqa: E402

LIMIT_NEED_SPAWN = 1200  # 20 минут на коннект, как указал владелец стенда
LIMIT_AFTER_SPAWN = 300


def wait_port(timeout=1200):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = bot_call({"cmd": "ping"}, timeout=8)
        if r.get("ok"):
            print("порт бота отвечает, состояние %s" % r.get("state"), flush=True)
            return True
        time.sleep(10)
    return False


def main():
    if not wait_port():
        print("ПОРТ НЕ ПОДНЯЛСЯ", flush=True)
        return 2

    print("шлю connect", flush=True)
    print(json.dumps(bot_call({"cmd": "connect"}), ensure_ascii=False), flush=True)

    t0 = time.time()
    reached = None
    while time.time() - t0 < LIMIT_NEED_SPAWN:
        st, ev = tail_state(300)
        print("%s t+%4ds state=%-12s сервер=%s"
              % (time.strftime("%H:%M:%S"), int(time.time() - t0), st or "?",
                 server_players()), flush=True)
        if st == "NeedSpawn":
            reached = "NeedSpawn"
            break
        if st == "Active":
            reached = "Active"
            break
        time.sleep(20)

    if not reached:
        print("КОННЕКТ НЕ ЗАВЕРШЁН за %d с" % LIMIT_NEED_SPAWN, flush=True)
        return 3

    print("достигнуто состояние %s, шлю spawn" % reached, flush=True)
    print(json.dumps(bot_call({"cmd": "spawn"}), ensure_ascii=False), flush=True)

    t1 = time.time()
    while time.time() - t1 < LIMIT_AFTER_SPAWN:
        st, ev = tail_state(300)
        print("%s t+%4ds state=%-12s сервер=%s"
              % (time.strftime("%H:%M:%S"), int(time.time() - t1), st or "?",
                 server_players()), flush=True)
        for e in ev[-3:]:
            print("    " + e, flush=True)
        if st == "Active":
            st2, _ = tail_state(300)
            print("СТАДИЯ АКТИВНА", flush=True)
            return 0
        time.sleep(15)
    print("не дошёл до Active", flush=True)
    return 4


if __name__ == "__main__":
    sys.exit(main())