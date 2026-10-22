"""Parse A/B sampler CSVs.

Two layouts are supported:
  * current  : ts,pid,uptime_s,cpu_s,ws_mb,priv_mb,handles,threads,pagefaults   (9 fields)
  * legacy   : the first sampler wrote decimals with the ru-RU decimal comma, which split
               every fractional field in two, so numbers are glued together:
               ts,pid,uptime,cpu_int,cpu_frac,ws_int,ws_frac,priv_int,priv_frac,handles,threads,pf
"""
import csv
import sys


def parse(path):
    with open(path, encoding="utf-8-sig") as f:
        raw = [row for row in csv.reader(f) if row and row[0] != "ts" and row[1] != "pid"]
    out = []
    for row in raw:
        if len(row) >= 9 and len(row) == 9:
            out.append({
                "ts": row[0], "pid": row[1], "uptime_s": float(row[2]), "cpu_s": float(row[3]),
                "ws_mb": float(row[4]), "priv_mb": float(row[5]), "handles": float(row[6]),
                "threads": float(row[7]), "pagefaults": float(row[8]),
            })
        else:
            # legacy layout: the trailing fields are always (handles, threads, pagefaults),
            # preceded by the split (int, frac) pairs of priv, ws and cpu.
            pf = float(row[-1])
            threads = float(row[-2])
            handles = float(row[-3])
            priv = float(row[-5] + "." + row[-4])
            ws = float(row[-7] + "." + row[-6])
            head = row[:-7]
            uptime = float(head[2])
            cpu = float(head[3] + "." + head[4]) if len(head) > 4 else float(head[3])
            out.append({
                "ts": head[0], "pid": head[1], "uptime_s": uptime, "cpu_s": cpu,
                "ws_mb": ws, "priv_mb": priv, "handles": handles,
                "threads": threads, "pagefaults": pf,
            })
    return out


def report(path):
    rows = parse(path)
    if not rows:
        raise SystemExit("no rows")
    first, last = rows[0], rows[-1]
    span = max(last["uptime_s"] - first["uptime_s"], 1.0)
    d_cpu = last["cpu_s"] - first["cpu_s"]
    d_ws = last["ws_mb"] - first["ws_mb"]
    d_pr = last["priv_mb"] - first["priv_mb"]
    d_pf = last["pagefaults"] - first["pagefaults"]
    ws = [r["ws_mb"] for r in rows]
    pr = [r["priv_mb"] for r in rows]
    print(f"file            : {path}")
    print(f"rows            : {len(rows)}   window: {span/60:.1f} min")
    print(f"uptime          : {first['uptime_s']/60:.1f} min -> {last['uptime_s']/60:.1f} min")
    print(f"cpu             : {first['cpu_s']:.1f}s -> {last['cpu_s']:.1f}s  delta {d_cpu:.1f}s"
          f"  ({d_cpu/span*100:.2f}% of one core)")
    print(f"working set     : {first['ws_mb']:.1f} -> {last['ws_mb']:.1f} MB  delta {d_ws:+.1f} MB"
          f"  ({(d_ws)/span*60:+.2f} MB/min)")
    print(f"private bytes   : {first['priv_mb']:.1f} -> {last['priv_mb']:.1f} MB  delta {d_pr:+.1f} MB"
          f"  ({(d_pr)/span*60:+.2f} MB/min)")
    print(f"page faults     : {first['pagefaults']:.0f} -> {last['pagefaults']:.0f}  delta {d_pf:.0f}"
          f"  ({d_pf/span:.1f}/s)")
    print(f"handles         : {first['handles']:.0f} -> {last['handles']:.0f}")
    print(f"threads         : {first['threads']:.0f} -> {last['threads']:.0f}")
    print(f"ws  min/avg/max : {min(ws):.0f} / {sum(ws)/len(ws):.0f} / {max(ws):.0f} MB")
    print(f"priv min/avg/max: {min(pr):.0f} / {sum(pr)/len(pr):.0f} / {max(pr):.0f} MB")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        report(p)
        print()
