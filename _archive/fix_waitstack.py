import io
p = "waitstack.py"
s = io.open(p, encoding="utf-8").read()
old = '''    if base is None:
        print("нет modules.txt рядом — имена не разрешатся")
        return 1'''
new = '''    if base is None:
        # база образа лежит в заголовке .bin: [base][count][rips...]
        companion = args.path.replace(".wait", ".bin")
        if os.path.exists(companion):
            with open(companion, "rb") as f:
                base = struct.unpack("<Q", f.read(8))[0]
            print("база образа взята из %s: 0x%X" % (os.path.basename(companion), base))
        else:
            print("нет ни modules.txt, ни .bin рядом — имена не разрешатся")
            return 1'''
assert old in s
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
