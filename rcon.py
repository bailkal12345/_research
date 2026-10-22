# -*- coding: utf-8 -*-
"""Mini Source RCON client for the ARK server + ArkApi plugin loading."""
import argparse
import os
import sys

sys.path.insert(0, r'C:\Dev\_research')
from tputils import rcon as tputils_rcon

PORT = int(os.environ.get("RCON_PORT", "32330"))
PASSWORD = os.environ.get("RCON_PASS", "0ub7OuAD6V68cbzc")


def rcon(command, port=PORT, password=PASSWORD, timeout=5):
    return tputils_rcon(command, timeout=timeout, port=port, pw=password)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="+")
    args = ap.parse_args()
    cmd = " ".join(args.command)
    out = rcon(cmd)
    if out is None:
        print("rcon failed: no response from any rcon host", file=sys.stderr)
        sys.exit(1)
    print(out if out else "(empty response)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print("rcon failed: %r" % (exc,), file=sys.stderr)
        sys.exit(1)
