import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''\t\tWriteModuleMap(PluginDir() + "\\\\" + name);
\t}\tif (g_wait_stacks)''','''\t\tWriteModuleMap(PluginDir() + "\\\\" + name);

\t\tif (g_wait_stacks)''')
# найти конец блока ожидания и закрыть функцию после него
old_tail = '''\t\t\tdelete[] g_wait_stacks;
\t\t\tg_wait_stacks = nullptr;
\t\t}'''
new_tail = '''\t\t\tdelete[] g_wait_stacks;
\t\t\tg_wait_stacks = nullptr;
\t\t}
\t}'''
assert old_tail in s
s = s.replace(old_tail, new_tail, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
