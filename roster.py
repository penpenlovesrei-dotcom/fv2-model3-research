"""Débloque le roster complet de Fighting Vipers 2 (Del Sol, Kuhn, BM, 14).

Le gestionnaire de curseur a un mode « roster étendu » où le curseur reboucle
sur 14 au lieu de 10. Il est conditionné par `(0x580F00 & 0xC0) == 0xC0`,
c'est-à-dire les deux boutons opérateur Service+Test maintenus - inexploitable
à la main puisque Test ouvre le menu de test. On patche donc la comparaison :

    0x0005F3BC   cmpwi r0,192   ->   cmpwi r0,0

La condition devient vraie quand aucun bouton opérateur n'est pressé, donc en
permanence. Le jeu recharge ce morceau de code (décompression depuis la ROM),
il faut donc réappliquer le patch.

IMPORTANT : ne jamais écrire à l'aveugle. Tant que la zone ne contient pas
l'instruction attendue, le code n'est pas chargé et écrire y corromprait
autre chose - le PowerPC part alors dans le décor et Supermodel affiche des
« unknown R32 / R16 ».

Usage: python roster.py [secondes]
"""

import ctypes as C
import ctypes.wintypes as W
import sys
import time

RAM_PTR_RVA = 0x65D098
SITE = 0x0005F3BC
ATTENDU = bytes.fromhex("2c8000c0")     # cmpwi r0,192
PATCH = bytes.fromhex("2c800000")       # cmpwi r0,0

# Compte a rebours de l'ecran de selection. On le recharge quand il descend,
# sans jamais le figer : le jeu continue de le decrementer, donc les
# transitions d'ecran ne se bloquent pas. Rester sous 99 une fois affiche
# (l'affiche vaut (halfword en 0x58140A) >> 6) sinon indexation hors bornes.
TIMER = 0x00581408
TIMER_HI = 0x1800                       # affiche 96
TIMER_LO = 0x1000

k32 = C.WinDLL("kernel32", use_last_error=True)
psapi = C.WinDLL("psapi")


def swap32(b):
    n = len(b) & ~3
    o = bytearray(b[:n])
    o[0::4], o[1::4], o[2::4], o[3::4] = b[3:n:4], b[2:n:4], b[1:n:4], b[0:n:4]
    return bytes(o)


def attach():
    arr = (W.DWORD * 4096)()
    got = W.DWORD()
    psapi.EnumProcesses(C.byref(arr), C.sizeof(arr), C.byref(got))
    buf = C.create_unicode_buffer(512)
    for pid in arr[: got.value // 4]:
        h = k32.OpenProcess(0x0438, False, pid)
        if not h:
            continue
        if psapi.GetModuleBaseNameW(h, None, buf, 512) and buf.value.lower() == "supermodel.exe":
            mods = (C.c_void_p * 512)()
            need = W.DWORD()
            psapi.EnumProcessModulesEx(h, C.byref(mods), C.sizeof(mods), C.byref(need), 3)
            if mods[0]:
                return h, mods[0]
        k32.CloseHandle(h)
    return None, None


h, mod = attach()
if not h:
    sys.exit("Supermodel n'est pas lance")


def raw(a, n):
    b = (C.c_char * n)()
    g = C.c_size_t()
    if not k32.ReadProcessMemory(h, C.c_void_p(a), b, n, C.byref(g)):
        return b""
    return b.raw[: g.value]


secs = float(sys.argv[1]) if len(sys.argv) > 1 else 3600.0
print(f"deblocage du roster - verification avant chaque ecriture - {secs:.0f}s", flush=True)

t0 = time.time()
poses = 0
while time.time() - t0 < secs:
    ram = int.from_bytes(raw(mod + RAM_PTR_RVA, 8) or b"", "little")
    if not ram:
        time.sleep(0.1)
        continue
    cur = swap32(raw(ram + SITE, 4))
    if cur == PATCH:
        pass                      # deja en place
    elif cur == ATTENDU:          # instruction d'origine reconnue : on patche
        n = C.c_size_t()
        k32.WriteProcessMemory(h, C.c_void_p(ram + SITE), swap32(PATCH), 4, C.byref(n))
        poses += 1
        print(f"  [{time.time() - t0:6.1f}s] patch pose ({poses})", flush=True)
    # sinon : code pas encore charge, on ne touche a rien

    # recharge du compte a rebours, uniquement s'il est actif (non nul)
    tv = int.from_bytes(swap32(raw(ram + TIMER, 4)) or bytes(4), "big")
    if 0 < tv < TIMER_LO:
        n = C.c_size_t()
        k32.WriteProcessMemory(h, C.c_void_p(ram + TIMER),
                               swap32(TIMER_HI.to_bytes(4, "big")), 4, C.byref(n))
    time.sleep(0.05)

k32.CloseHandle(h)
print(f"fin - {poses} pose(s)")
