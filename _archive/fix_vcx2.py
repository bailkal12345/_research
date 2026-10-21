import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.vcxproj"
s = io.open(p, encoding="utf-8").read()
s = s.replace("<AdditionalOptions>/utf-8 %%(AdditionalOptions)</AdditionalOptions>",
              "<AdditionalOptions>/utf-8</AdditionalOptions>")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
