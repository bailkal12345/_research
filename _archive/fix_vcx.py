import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.vcxproj"
s = io.open(p, encoding="utf-8").read()
bad = "<WarningLevel>Level3</WarningLevel>`n      <AdditionalOptions>/utf-8 %%(AdditionalOptions)</AdditionalOptions>"
good = "<WarningLevel>Level3</WarningLevel>\n      <AdditionalOptions>/utf-8 %%(AdditionalOptions)</AdditionalOptions>"
s = s.replace(bad, good)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("vcxproj fixed:", s.count("/utf-8"))
