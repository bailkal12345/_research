import io
p = r"C:\Dev\_research\watch_shift.py"
s = io.open(p, encoding="utf-8", newline="").read()
s = s.replace('''    ap.add_argument("--budget-min", type=int, default=210)''',
'''    ap.add_argument("--budget-min", type=int, default=210)
    ap.add_argument("--assume-running", default="",
                    help="архив уже развёрнут и сервер поднят: деплой пропускается")''')
s = s.replace('''        ok, why = deploy(arch)
        if not ok:''',
'''        if arch == args.assume_running:
            wl("архив %s уже развёрнут и сервер отвечает — деплой пропускаю" % arch)
            ok, why = True, "уже поднят"
        else:
            ok, why = deploy(arch)
        if not ok:''')
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s)
print("драйвер: добавлен --assume-running")
