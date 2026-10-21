import io
p = "sfstack.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''    if base is None:
        print("нет modules.txt рядом — имена не разрешатся")
        return 1''','''    if base is None:
        companion = args.path.replace(".sfstack", ".bin")
        if os.path.exists(companion):
            with open(companion, "rb") as f:
                base = struct.unpack("<Q", f.read(8))[0]
            print("база образа взята из .bin: 0x%X" % base)
        else:
            print("нет ни modules.txt, ни .bin рядом — имена не разрешатся")
            return 1''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
