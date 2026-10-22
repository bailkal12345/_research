# -*- coding: utf-8 -*-
# doit6 §4: починка perf.selftest - "горячий цикл: сброс метки времени в фазе".
#
# Баг (TickProf.cpp, фаза ST_AB_A_WINDOW):
#   g_st_mark = now + 3000;   // метка в БУДУЩЕМ
#   elapsed_s = (now - g_st_mark) / 1000;   // uint64 -> подпитка -> огромное число
#   => условие "g_save_state==0 && elapsed_s > 120" всегда истинно => окно
#      переармливается каждый кадр (StWindow + g_st_mark в будущее) => горячий цикл,
#      окно никогда не закрывается, автопрогон виснет.
# Плюс второй баг: ST_AB_B_PREP делает StSet(ST_AB_B_PREP) - переход в себя же,
#   из-за чего "рука A закрыта" логируется каждый кадр.
#
# Исправление:
#  1) метка времени всегда в прошлом (g_st_mark = now) - отдельная отсрочка
#     делается через g_st_mark = now + 3000_ms как ЗАДЕРЖКА, но проверка
#     использует знаковое сравнение (int64), чтобы не было подпитки;
#  2) ST_AB_A_WINDOW: рука A запускается ОДИН раз (флаг g_st_arm_a), дальше ждём
#     закрытия окна (g_perf.window == 0) и переходим в ST_AB_B_PREP;
#  3) ST_AB_B_PREP -> ST_AB_B_WINDOW (без самоперехода), рука B запускается один раз.
import io, re, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
# Нормализация: файл читается с CRLF, а шаблоны в скрипте написаны с LF.
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    """Подгоняет переводы строк шаблона под файл."""
    return t.replace('\n', NL)

# --- 1) знаковая арифметика для elapsed_s ---
old_el = """		const uint64_t now = GetTickCount64();
		const uint64_t elapsed_s = (now - g_st_mark) / 1000;
"""
new_el = """		const uint64_t now = GetTickCount64();
		// ЗНАКОВОЕ вычитание: g_st_mark может быть в будущем (отсрочка запуска окна),
		// при uint64 это давало бы подпитку и "горячий цикл" (условие всегда истинно).
		const int64_t elapsed_s = (static_cast<int64_t>(now) - static_cast<int64_t>(g_st_mark)) / 1000;
"""
assert blk(old_el) in src, 'elapsed_s не найден'
src = src.replace(blk(old_el), blk(new_el), 1)

# --- 2) флаги "окно уже запущено" ---
old_decl = """	std::atomic<int> g_st{ST_IDLE};
	uint64_t g_st_mark = 0;
"""
new_decl = """	std::atomic<int> g_st{ST_IDLE};
	uint64_t g_st_mark = 0;
	// Флаги "окно уже запущено": без них фаза рук A/B переармливала окно каждый кадр.
	bool g_st_arm_a = false;
	bool g_st_arm_b = false;
"""
assert blk(old_decl) in src, 'g_st_mark не найден'
src = src.replace(blk(old_decl), blk(new_decl), 1)

# --- 3) фаза ST_AB_A_WINDOW: запуск один раз + переход в B_PREP ---
old_a = """		case ST_AB_A_WINDOW:
			if (g_save_state.load() == 0 && elapsed_s > 120)
			{
				LogLine("selftest: рука A, окно");
				StWindow(g_st_win_sec);
				g_st.store(ST_AB_A_WINDOW, std::memory_order_relaxed);
				g_st_mark = now + 3000; // дать окну стартовать
			}
			break;
"""
new_a = """		case ST_AB_A_WINDOW:
			// Окно запускается ОДИН раз; дальше ждём его закрытия.
			// Раньше здесь стояло g_st_mark = now + 3000 (метка в будущем) => uint64
			// подпитывался, условие "elapsed_s > 120" выполнялось каждый кадр, окно
			// переармливалось => горячий цикл и зависание автопрогона.
			if (!g_st_arm_a)
			{
				if (g_save_state.load() == 0 && elapsed_s > 120)
				{
					LogLine("selftest: рука A, окно");
					StWindow(g_st_win_sec);
					g_st_arm_a = true;
					g_st_mark = now; // отсчёт от момента запуска окна
				}
				else if (elapsed_s > static_cast<int64_t>(g_st_budget_min) * 60)
				{
					LogLine("selftest: рука A не запустилась (сейв не завершён) - ПРОПУСК");
					StSet(ST_DONE);
				}
			}
			else if (g_perf.window.load() == 0)
			{
				LogLine("selftest: рука A закрыта");
				g_st_vals.push_back(g_win_ms_tick.load());
				LogLine(S("selftest: рука A мс/тик = {}", g_win_ms_tick.load()));
				StSet(ST_AB_B_PREP);
			}
			break;
"""
assert blk(old_a) in src, 'ST_AB_A_WINDOW не найдена'
src = src.replace(blk(old_a), blk(new_a), 1)

# --- 4) фаза ST_AB_B_PREP: без самоперехода ---
old_b = """		case ST_AB_B_PREP:
			if (g_perf.window.load() == 0)
			{
				LogLine("selftest: рука A закрыта");
				g_st_vals.push_back(g_win_ms_tick.load());
				LogLine(S("selftest: рука A мс/тик = {}", g_win_ms_tick.load()));
				DoOverlapTrim(2);
				LogLine("selftest: overlaptrim 2 применён");
				StSet(ST_AB_B_PREP);
			}
			break;
"""
new_b = """		case ST_AB_B_PREP:
			// Переход в себя же был багом: "рука A закрыта" логировалось каждый кадр.
			// Теперь фаза отрабатывает один раз и уходит в ST_AB_B_WINDOW.
			if (!g_st_arm_b)
			{
				DoOverlapTrim(2);
				LogLine("selftest: overlaptrim 2 применён");
				g_st_arm_b = true;
				StWindow(g_st_win_sec);
				StSet(ST_AB_B_WINDOW);
			}
			break;
"""
assert blk(old_b) in src, 'ST_AB_B_PREP не найдена'
src = src.replace(blk(old_b), blk(new_b), 1)

# --- 5) сброс флагов при старте ---
old_start = """		g_st_vals.clear();
		g_game_tid.load();
"""
new_start = """		g_st_vals.clear();
		g_st_arm_a = false;
		g_st_arm_b = false;
		g_game_tid.load();
"""
assert blk(old_start) in src, 'начало CmdSelftest не найдено'
src = src.replace(blk(old_start), blk(new_start), 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('perf.selftest: исправлено 4 места (знаковая elapsed_s, флаги arm_a/arm_b, рука A, рука B)')
