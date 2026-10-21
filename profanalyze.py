# -*- coding: utf-8 -*-
# Анализ профилей TickProf: .bin (RIP), .ret ([RSP]), .wait (rip+4 слова RSP).
# Разрешение имён — через таблицы экспорта PE самих DLL (без的发展 патчей, только чтение).
import struct, sys, bisect, collections

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\\Plugins\_backup\\TickProf'
EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'

def load_data(name, ext):
    return open('%s\\prof_%s.%s' % (TICKPROF, name, ext), 'rb').read()

def load_modules(path):
    mods = []  # (base, size, short_name, full_path)
    SYSCALL_SISTERS = {'ntdll.dll', 'win32u.dll', 'kernel32.dll', 'kernelbase.dll', 'user32.dll', 'gdi32.dll'}
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 3:
                base = int(p[0], 16); size = int(p[1], 16)
                full = p[2].strip()
                short = full.replace('\\', '/').split('/')[-1]
                is_sys = short.lower() in SYSCALL_SISTERS
                mods.append((base, size, short, full, is_sys))
    mods.sort()
    bases = [m[0] for m in mods]
    return mods, bases

def mod_of(addr, mods, bases):
    i = bisect.bisect_right(bases, addr) - 1
    if i >= 0:
        base, size, short, full, is_sys = mods[i]
        if addr < base + size:
            return short, addr - base, is_sys
    return None, None, False

def parse_export_table(path):
    """arg: путь к PE. Возвращает [(rva, name)] экспортов или None."""
    try:
        with open(path, 'rb') as f:
            data = f.read(1 << 20)
        if data[:2] != b'MZ':
            return None
        pe_off = struct.unpack_from('<I', data, 0x3C)[0]
        if pe_off + 6 > len(data) or data[pe_off:pe_off + 4] != b'PE\0\0':
            return None
        coff = pe_off + 4
        num_sections = struct.unpack_from('<H', data, coff + 2)[0]
        opt_size = struct.unpack_from('<H', data, coff + 16)[0]
        opt = coff + 20
        magic = struct.unpack_from('<H', data, opt)[0]
        if magic != 0x20B:
            return None
        # PE32+: DataDirectory начинается на opt+112
        dirs = opt + 112
        exp_dd = dirs + 0  # первый каталог = экспорт
        exp_rva, exp_size = struct.unpack_from('<II', data, exp_dd)
        if exp_rva == 0:
            return None
        # секции для RVA->файловое смещение
        sec_off = opt + opt_size
        sections = []
        for i in range(num_sections):
            s = sec_off + i * 40
            vsize = struct.unpack_from('<I', data, s + 8)[0]
            vaddr = struct.unpack_from('<I', data, s + 12)[0]
            rawsize = struct.unpack_from('<I', data, s + 16)[0]
            rawptr = struct.unpack_from('<I', data, s + 20)[0]
            sections.append((vaddr, max(vsize, rawsize), rawptr))
        def rva2off(rva):
            for vaddr, vsz, rawptr in sections:
                if vaddr <= rva < vaddr + vsz:
                    return rawptr + (rva - vaddr)
            return None
        # ВАЖНО: для больших exe экспорт-таблица может лежать дальше 1МБ — читаем больше
    except OSError:
        return None
    # повторно с полностью загруженным файлом
    with open(path, 'rb') as f:
        data = f.read()
    num_sections = None
    def rva2off2(rva):
        for vaddr, vsz, rawptr in sections:
            if vaddr <= rva < vaddr + vsz:
                return rawptr + (rva - vaddr)
        return None
    exp_off = rva2off2(exp_rva)
    if exp_off is None:
        return None
    try:
        name_rvas = struct.unpack_from('<I', data, exp_off + 32)[0]  # AddressOfNames
        ord_rvas = struct.unpack_from('<I', data, exp_off + 36)[0]   # AddressOfNameOrdinals
        func_rvas = struct.unpack_from('<I', data, exp_off + 28)[0]  # AddressOfFunctions
        n_names = struct.unpack_from('<I', data, exp_off + 24)[0]
        n_funcs = struct.unpack_from('<I', data, exp_off + 20)[0]
        names = rva2off2(name_rvas); ords = rva2off2(ord_rvas); funcs = rva2off2(func_rvas)
        if names is None or ords is None or funcs is None:
            return None
        out = []  # (rva, name)
        for i in range(n_names):
            nr = struct.unpack_from('<I', data, names + i * 4)[0]
            no = struct.unpack_from('<H', data, ords + i * 2)[0]
            fn = struct.unpack_from('<I', data, funcs + no * 4)[0]
            noff = rva2off2(nr)
            end = data.index(b'\0', noff)
            out.append((fn, data[noff:end].decode('ascii', 'replace')))
        return out
    except Exception:
        return None

def parse_sections(path):
    """arg: путь к PE. Возврат [(vaddr, vend, name)] секций."""
    with open(path, 'rb') as f:
        data = f.read(1 << 12)
    if data[:2] != b'MZ':
        return None
    pe_off = struct.unpack_from('<I', data, 0x3C)[0]
    coff = pe_off + 4
    num_sections = struct.unpack_from('<H', data, coff + 2)[0]
    opt_size = struct.unpack_from('<H', data, coff + 16)[0]
    opt = coff + 20
    sec_off = opt + opt_size
    with open(path, 'rb') as f:
        hdr = f.read(sec_off + num_sections * 40 + 64)
    out = []
    for i in range(num_sections):
        s = sec_off + i * 40
        vsize = struct.unpack_from('<I', hdr, s + 8)[0]
        vaddr = struct.unpack_from('<I', hdr, s + 12)[0]
        nm = hdr[s:s + 8].rstrip(b'\0').decode('ascii', 'replace')
        if vsize:
            out.append((vaddr, vaddr + vsize, nm))
    return out

class ExportIndex:
    def __init__(self, path):
        self.path = path
        self.ex = None
        e = parse_export_table(path)
        if e:
            e.sort()
            self.ex = e
            self.rvas = [x[0] for x in e]
    def name_of(self, off):
        if not self.ex or off > 0x10000000:
            return None
        i = bisect.bisect_right(self.rvas, off) - 1
        if 0 <= i:
            rva, nm = self.ex[i]
            if off - rva < 0x400:
                return nm if off == rva else '%s+0x%x' % (nm, off - rva)
        return None

def classify_word(v, mods, bases, ex_by_short):
    short, off, is_sys = mod_of(v, mods, bases)
    if short is None:
        return None
    nm = None
    idx = ex_by_short.get(short)
    if idx is not None:
        nm = idx.name_of(off)
    return short, off, is_sys, nm

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else '512222984'
    mods, bases = load_modules(TICKPROF + '\\prof_%s.modules.txt' % name)

    # индексы экспортов только для модулей, где они есть (системные DLL + exe)
    ex_by_short = {}
    sec_by_short = {}
    seen = set()
    for base, size, short, full, is_sys in mods:
        if short in seen:
            continue
        seen.add(short)
        try:
            ex_by_short[short] = ExportIndex(full)
        except Exception:
            ex_by_short[short] = None
        try:
            sec_by_short[short.lower()] = parse_sections(full)
        except Exception:
            sec_by_short[short.lower()] = None

    def sec_kind(short, off):
        kinds = sec_by_short.get(short.lower())
        if kinds:
            for va, ve, nm in kinds:
                if va <= off < ve:
                    return nm
        return '?'

    bin_data = load_data(name, 'bin')
    base_exe = struct.unpack_from('<Q', bin_data, 0)[0]
    count = struct.unpack_from('<Q', bin_data, 8)[0]
    rips = struct.unpack_from('<%dQ' % count, bin_data, 16)
    ret_data = load_data(name, 'ret')
    rets = struct.unpack_from('<%dQ' % count, ret_data)

    out = []
    out.append('=== prof_%s: сэмплов %d ===' % (name, count))

    # --- распределение листьев по модулям ---
    mod_cnt = collections.Counter()
    leaf_top = collections.Counter()
    ret_cnt = collections.Counter()
    ret_top = collections.Counter()
    pair_top = collections.Counter()
    leaf_status = collections.Counter()  # in-exe / sys / unknown-dll
    for rip, ret in zip(rips, rets):
        short, off, is_sys = mod_of(rip, mods, bases)
        key = '%s+0x%X' % (short, off) if short is not None else 'КРУД(вне модулей/ядро)+0x%X' % rip
        mod_cnt[short if short is not None else '<нет в модулях>'] += 1
        leaf_top[key] += 1
        if short is None:
            leaf_status['вне всех модулей (ядро/аноним)'] += 1
        elif is_sys:
            leaf_status['системная sys-DLL (net)'] += 1
        else:
            leaf_status[short] += 1
        rshort, roff, _ = mod_of(ret, mods, bases)
        if rshort is not None:
            rk = '%s+0x%X' % (rshort, roff)
            ret_cnt[rshort] += 1
            ret_top[rk] += 1
            pair_top[(key, rk)] += 1
        else:
            ret_cnt['<нет/нулевой ret>'] += 1

    out.append('')
    out.append('--- листья по модулям (RIP):')
    for k, v in mod_cnt.most_common():
        out.append('  %-28s %5d  %5.1f%%' % (k, v, 100.0 * v / count))
    out.append('')
    out.append('--- топ-30 листьев (функции; для exe указана секция):')
    for k, v in leaf_top.most_common(30):
        short = k.split('+')[0]
        off = int(k.split('+')[1], 16) if '+' in k else None
        nm = ''
        if short in ex_by_short and ex_by_short[short] is not None and off is not None:
            nm = ex_by_short[short].name_of(off)
        if nm == '' and short == 'ShooterGameServer.exe' and off is not None:
            nm = '[%s]' % sec_kind(short.lower(), off)
        out.append('  %5.1f%% %5d  %-34s %s' % (100.0 * v / count, v, k, nm or ''))
    out.append('')
    out.append('--- топ-30 адресов возврата ([RSP]):')
    for k, v in ret_top.most_common(30):
        short = k.split('+')[0]
        off = int(k.split('+')[1], 16)
        nm = ''
        if short in ex_by_short and ex_by_short[short] is not None:
            nm = ex_by_short[short].name_of(off)
        if nm == '' and short == 'ShooterGameServer.exe':
            nm = '[%s]' % sec_kind(short.lower(), off)
        out.append('  %5.1f%% %5d  %-34s %s' % (100.0 * v / count, v, k, nm or ''))
    out.append('')
    out.append('--- топ-25 пар лист+ret:')
    for (lk, rk), v in pair_top.most_common(25):
        out.append('  %5.1f%% %5d  %s  <-  %s' % (100.0 * v / count, v, lk, rk))

    # --- wait-стопки ---
    wdata = load_data(name, 'wait')
    wcnt = struct.unpack_from('<Q', wdata, 0)[0]
    words = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)
    out.append('')
    out.append('--- wait-записей (blocked rip): %d (=%.1f%% сэмплов)' % (wcnt, 100.0 * wcnt / count))
    wait_rip_top = collections.Counter()
    wait_pattern = collections.Counter()
    wait_next_word = collections.Counter()
    for i in range(wcnt):
        w = words[i * 5:(i + 1) * 5]
        rip, s0, s1, s2, s3 = w
        short, off, is_sys = mod_of(rip, mods, bases)
        key = '%s+0x%X' % (short, off) if short is not None else 'ядро+0x%X' % rip
        nm = ''
        if short in ex_by_short and ex_by_short[short] is not None:
            nm = ex_by_short[short].name_of(off)
        wait_rip_top['%s %s' % (key, nm or '')] += 1
        # dredge стек: попытка найти в s0..s3 возврат в exe/DLL
        frames = []
        for sv in (s0, s1, s2, s3):
            cls = classify_word(sv, mods, bases, ex_by_short)
            if cls is not None:
                fs, fo, _, fnm = cls
                if not fs.startswith('ntdll') and not fs.startswith('KERNEL') and not fs.startswith('kernel') and not fs.startswith('win32u'):
                    sk = '[%s]' % sec_kind(fs.lower(), fo) if fs == 'ShooterGameServer.exe' else ''
                    frames.append('%s+0x%X%s %s%s' % (fs, fo, sk, fnm or '', sk if not fnm else ''))
        pat = ' | '.join(frames[:3]) if frames else '(в s0..s3 нет возвратов в юзер-модули)'
        wait_pattern[pat] += 1
        # для KERNELBASE waits: что лежит ниже по стеку обычнее всего
        sshort, soff, sis_sys = mod_of(s0, mods, bases)
        if sshort is not None:
            wait_next_word['%s+0x%X' % (sshort, soff)] += 1

    out.append('')
    out.append('--- топ rip стека ожидания (syscall-сайты):')
    for k, v in wait_rip_top.most_common(15):
        out.append('  %5.1f%% %5d  %s' % (100.0 * v / wcnt, v, k))
    out.append('')
    out.append('--- топ паттернов стека (возвраты в exe/плагины из s0..s3):')
    for k, v in wait_pattern.most_common(25):
        out.append('  %5.1f%% %5d  %s' % (100.0 * v / wcnt, v, k[:170]))
    out.append('')
    out.append('--- распределение s0 (первое слово RSP):')
    for k, v in wait_next_word.most_common(15):
        out.append('  %5.1f%% %5d  %s' % (100.0 * v / wcnt, v, k))

    # --- экспорт exe присутствует? ---
    exe_idx = ex_by_short.get('ShooterGameServer.exe')
    n = len(exe_idx.ex) if exe_idx and exe_idx.ex else 0
    out.append('')
    out.append('ShooterGameServer.exe: экспортов=%d' % n)
    if n:
        out.append('  примеры: %s' % ', '.join(nm for _, nm in exe_idx.ex[:15]))

    report = '\n'.join(out)
    open(r'C:\Dev\_research\prof_%s_report.txt' % name, 'w', encoding='utf-8').write(report)
    print(report)

if __name__ == '__main__':
    main()
