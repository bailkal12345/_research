# -*- coding: utf-8 -*-
# Фикс отчётов bptrace: мини-форматтер S() поддерживает только "{}" и "{:X}",
# все "{:.1f}"/"{:.4f}" шли в hex-ветку (926.3 -> "39E"). Дробные числа теперь
# форматируются заранее (snprintf) и передаются строкой в "{}".
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


HELPER = blk('''
\t// Дробные числа для мини-форматтера S(): он не умеет "{:.Nf}", поэтому
\t// печатаем через snprintf и передаём строкой.
\tstd::string BpFmt(double v, int digits)
\t{
\t\tchar buf[64];
\t\tsnprintf(buf, sizeof(buf), digits == 1 ? "%.1f" : "%.2f", v);
\t\treturn buf;
\t}
''')
i = src.index('\t// Отчёт: топ по вызовам')
src = src[:i] + HELPER + src[i:]

REPL = [
    (r'''\t\t\tLogLine(S("bptrace:   {} вызовов={} total={:.1f}мс self={:.1f}мс мс/вызов={:.4f} {}",
\t\t\t\tr.name, r.calls, r.total_ms, r.self_ms,
\t\t\t\tr.calls ? r.self_ms * 1000.0 / (double)r.calls : 0.0, r.script ? "script" : "native"));''',
     r'''\t\t\tLogLine(S("bptrace:   {} вызовов={} total={}мс self={}мс мкс/вызов={} {}",
\t\t\t\tr.name, r.calls, BpFmt(r.total_ms, 1), BpFmt(r.self_ms, 1),
\t\t\t\tr.calls ? BpFmt(r.self_ms * 1000.0 / (double)r.calls, 2) : std::string("0"),
\t\t\t\tr.script ? "script" : "native"));'''),
    (r'''\t\tLogLine(S("bptrace: ТОП-20 ПО SELF-ВРЕМЕНИ (сумма self={:.1f} мс)", sum_self));''',
     r'''\t\tLogLine(S("bptrace: ТОП-20 ПО SELF-ВРЕМЕНИ (сумма self={} мс)", BpFmt(sum_self, 1)));'''),
    (r'''\t\t\tconst Row& r = by_self[i];
\t\t\tLogLine(S("bptrace:   {} self={:.1f}мс ({:.1f}%) вызовов={} мс/вызов={:.4f} {}",
\t\t\t\tr.name, r.self_ms, sum_self > 0 ? 100.0 * r.self_ms / sum_self : 0.0, r.calls,
\t\t\t\tr.calls ? r.self_ms * 1000.0 / (double)r.calls : 0.0, r.script ? "script" : "native"));''',
     r'''\t\t\tconst Row& r = by_self[i];
\t\t\tLogLine(S("bptrace:   {} self={}мс ({}%) вызовов={} мкс/вызов={} {}",
\t\t\t\tr.name, BpFmt(r.self_ms, 1),
\t\t\t\tBpFmt(sum_self > 0 ? 100.0 * r.self_ms / sum_self : 0.0, 1), r.calls,
\t\t\t\tr.calls ? BpFmt(r.self_ms * 1000.0 / (double)r.calls, 2) : std::string("0"),
\t\t\t\tr.script ? "script" : "native"));'''),
    (r'''\t\tLogLine(S("bptrace.caller: {} (вызовов={}, self={:.1f}мс)", s.name, (uint64_t)s.calls,
\t\t\t(double)s.self_ticks * 1000.0 / (double)g_bp_qpc_freq));''',
     r'''\t\tLogLine(S("bptrace.caller: {} (вызовов={}, self={}мс)", s.name, (uint64_t)s.calls,
\t\t\tBpFmt((double)s.self_ticks * 1000.0 / (double)g_bp_qpc_freq, 1)));'''),
    (r'''\t\t\tLogLine(S("bptrace.caller:   {} вызовов={} ({:.1f}%)", cname, cnt,
\t\t\t\t(uint64_t)s.calls ? 100.0 * (double)cnt / (double)s.calls : 0.0));''',
     r'''\t\t\tLogLine(S("bptrace.caller:   {} вызовов={} ({}%)", cname, cnt,
\t\t\t\tBpFmt((uint64_t)s.calls ? 100.0 * (double)cnt / (double)s.calls : 0.0, 1)));'''),
]

missed = []
for old, new in REPL:
    o = blk(old).replace('{:.1f}'.replace('.', chr(46)), '{:.1f}')
    if blk(old) in src:
        src = src.replace(blk(old), blk(new), 1)
    else:
        missed.append(old.splitlines()[0])

if missed:
    raise SystemExit('ЯКОРЯ НЕ НАЙДЕНЫ:\n' + '\n'.join(missed))

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('форматтер отчётов исправлен')
