# -*- coding: utf-8 -*-
# Compatibility shim: everything moved to tputils.py.
from tputils import HOSTS, PORT, PW, _pack, _unpack, rcon

__all__ = ['HOSTS', 'PORT', 'PW', '_pack', '_unpack', 'rcon']

if __name__ == '__main__':
    import sys
    for c in (sys.argv[1:] or ['status']):
        r = rcon(c)
        print('=== %s ===' % c)
        print(repr(r)[:1500] if r is not None else 'NO RESPONSE')
