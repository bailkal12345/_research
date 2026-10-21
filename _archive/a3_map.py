import sqlite3, sys, bisect

DB = r'C:\Dev\_research\v361.sqlite'
con = sqlite3.connect(DB)
rows = con.execute("select rva,name,size from fn where rva is not null and size>0").fetchall()
rows = sorted(set(rows))
addrs = [r[0] for r in rows]
names = {r[0]: (r[1], r[2]) for r in rows}

def lookup(rva):
    i = bisect.bisect_right(addrs, rva) - 1
    if i < 0:
        return None
    base = addrs[i]
    n, s = names[base]
    if rva < base + s:
        return (base, n, s, rva - base)
    return (None, None, None, None)

if __name__ == '__main__':
    for a in sys.argv[1:]:
        v = int(a, 16)
        if v > 0x140000000:
            v -= 0x140000000
        r = lookup(v)
        if r[0] is None:
            print("%s -> NOT FOUND" % a)
        else:
            print("%s -> 0x%x %s (size %d, +0x%x)" % (a, r[0], r[1], r[2], r[3]))
