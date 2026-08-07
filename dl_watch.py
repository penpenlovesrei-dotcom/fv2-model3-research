"""Guette des éléments graphiques dans la liste d'affichage, en continu.

Conçu pour les écrans trop brefs pour être capturés à la main : on lance le
guetteur, on laisse le jeu défiler, et il note lui-même quand les éléments
surveillés apparaissent et disparaissent.

Beaucoup plus rapide que `displaylist.py`, qui recopie les 8 Mo à chaque
fois : ici on s'attache une seule fois et on ne relit que la zone des
paquets, quelques dizaines de kilo-octets.

Usage: python dl_watch.py <id_hex> [id_hex ...] [--secs N]
    ex: python dl_watch.py 8d2 8d7
"""

import ctypes as C
import ctypes.wintypes as W
import struct
import sys
import time

RAM_PTR_RVA = 0x65D098
TABLE = 0x003003CC
ZONE = (0x7D8000, 0x7F0000)
ENTETE = b"\x06\x00\x00\x00"

k32 = C.WinDLL("kernel32", use_last_error=True)
psapi = C.WinDLL("psapi")


def swap32(b):
    n = len(b) & ~3
    o = bytearray(b[:n])
    o[0::4], o[1::4], o[2::4], o[3::4] = b[3:n:4], b[2:n:4], b[1:n:4], b[0:n:4]
    return bytes(o)


arr = (W.DWORD * 4096)()
got = W.DWORD()
psapi.EnumProcesses(C.byref(arr), C.sizeof(arr), C.byref(got))
buf = C.create_unicode_buffer(512)
h = mod = None
for pid in arr[: got.value // 4]:
    hh = k32.OpenProcess(0x0438, False, pid)
    if not hh:
        continue
    if psapi.GetModuleBaseNameW(hh, None, buf, 512) and buf.value.lower() == "supermodel.exe":
        mods = (C.c_void_p * 512)()
        need = W.DWORD()
        psapi.EnumProcessModulesEx(hh, C.byref(mods), C.sizeof(mods), C.byref(need), 3)
        h, mod = hh, mods[0]
        break
    k32.CloseHandle(hh)
if not h:
    sys.exit("Supermodel n'est pas lance")


def raw(a, n):
    b = (C.c_char * n)()
    g = C.c_size_t()
    if not k32.ReadProcessMemory(h, C.c_void_p(a), b, n, C.byref(g)):
        return b""
    return b.raw[: g.value]


ram = int.from_bytes(raw(mod + RAM_PTR_RVA, 8) or b"", "little")
if not ram:
    sys.exit("RAM Model 3 introuvable")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
secs = float(sys.argv[sys.argv.index("--secs") + 1]) if "--secs" in sys.argv else 600.0
ids = [int(a, 16) for a in args] or [0x8D2, 0x8D7]

# pointeur attendu dans le paquet, pour chaque identifiant surveille
attendus = {}
for e in ids:
    v = int.from_bytes(swap32(raw(ram + TABLE + e * 4, 4)), "big")
    attendus[e] = v.to_bytes(4, "big")[::-1]        # tel qu'ecrit dans le paquet
    print(f"  element {e:#06x} -> pointeur {v:#010x}", flush=True)

print(f"guet de {secs:.0f}s - laisse le jeu defiler", flush=True)
t0 = time.time()
prev = None
taille = ZONE[1] - ZONE[0]
while time.time() - t0 < secs:
    d = raw(ram + ZONE[0], taille)
    if len(d) == taille:
        d = swap32(d)
        presents = set()
        a = d.find(ENTETE)
        while a >= 0:
            mot7 = d[a + 28: a + 32]
            for e, att in attendus.items():
                if mot7 == att:
                    presents.add(e)
            a = d.find(ENTETE, a + 4)
        if presents != prev:
            libelle = " ".join(f"{e:#06x}" for e in sorted(presents)) or "(aucun)"
            print(f"  [{time.time() - t0:6.1f}s] a l'ecran : {libelle}", flush=True)
            prev = presents
    time.sleep(0.08)

k32.CloseHandle(h)
print("fin")
