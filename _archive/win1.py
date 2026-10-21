import os
import sys

os.environ.setdefault("RCON_HOST", "192.168.8.218")
os.environ.setdefault("RCON_PORT", "27020")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import slot_measure as S  # noqa: E402

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
CARD = sys.argv[2] if len(sys.argv) > 2 else "theisland"

tid = S.game_tid()
print("окно %d с, карта %s, GameThread tid=%s" % (SECONDS, CARD, tid), flush=True)

res = S.window(tid, SECONDS, S.newest_crash(), CARD)

print("ИТОГ ОКНА (TheIsland, игрок в мире, стоит):", flush=True)
print("  t/s (по frames/wall плагина) = %.2f" % res["tps"], flush=True)
print("  CPU GameThread (внешний Python) = %.3f s/s" % res["cpu"], flush=True)
print("  мс CPU на тик = %.2f" % res["ms_tick"], flush=True)
print("  здоровье: %s" % res["why"], flush=True)
print("  загрязнение карты: %s" % res.get("contaminated"), flush=True)

ok = res["healthy"] and res["tps"] > 0 and not res.get("contaminated")
print("  ИТОГ: %s" % ("VALID" if ok else "БРАК"), flush=True)