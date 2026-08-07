"""Fighting Vipers 2 - jouer les personnages cachés (patch runtime).

Lance Supermodel puis maintient le personnage choisi verrouillé en RAM
jusqu'à ce que l'émulateur se ferme. Rien n'est modifié sur disque : ni la
ROM, ni la configuration.

    python play.py kuhn
    python play.py delsol --res 1920,1440
    python play.py bm --fullscreen

Deux règles apprises à la dure, appliquées ici :
  - le verrou est posé AVANT l'entrée dans l'écran de sélection, sinon la
    validation gagne la course et c'est le curseur qui l'emporte ;
  - le compte à rebours n'est jamais touché, sinon le jeu et nous nous le
    réécrivons mutuellement et la transition vers le combat se bloque.

Une fois lancé, le personnage est imposé quelle que soit la position du
curseur : insère un crédit, valide n'importe qui, c'est lui qui sort.
"""

import ctypes as C
import ctypes.wintypes as W
import argparse
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(BASE, "Supermodel.exe")
ROM = os.path.join("ROMs", "fvipers2.zip")

RAM_PTR_RVA = 0x65D098          # Supermodel 0.3a-20251120 x64
SLOTS = (0x00279668, 0x0027966C)  # deux entiers 16 bits, jamais réécrits par le jeu

# Index de region, lu par le jeu dans la table JAPAN/U.S.A./EXPORT/ASIA en
# 0x2924CC. Le menu de test l'affiche mais interdit de l'editer ; l'ecrire
# directement fonctionne et bascule les textes en anglais.
COUNTRY_ADDR = 0x00120557
PAYS = {"japan": 0, "usa": 1, "export": 2, "asia": 3}

PERSOS = {
    "delsol": (11, "Del Sol"),
    "kuhn": (12, "Kuhn"),
    "bm": (13, "BM"),
    "normal": (None, "aucun (jeu non modifié)"),
}

k32 = C.WinDLL("kernel32", use_last_error=True)
psapi = C.WinDLL("psapi")


def swap32(b):
    n = len(b) & ~3
    o = bytearray(b[:n])
    o[0::4], o[1::4], o[2::4], o[3::4] = b[3:n:4], b[2:n:4], b[1:n:4], b[0:n:4]
    return bytes(o)


def attach(pid):
    h = k32.OpenProcess(0x0438, False, pid)   # QUERY | VM_OPERATION | VM_READ | VM_WRITE
    if not h:
        return None, None
    mods = (C.c_void_p * 512)()
    need = W.DWORD()
    ok = psapi.EnumProcessModulesEx(h, C.byref(mods), C.sizeof(mods), C.byref(need), 3)
    # juste apres le demarrage la liste est encore vide et mods[0] vaut NULL,
    # que ctypes renvoie en None : il faut reessayer, pas seulement tester h
    if not ok or not need.value or not mods[0]:
        k32.CloseHandle(h)
        return None, None
    return h, mods[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perso", nargs="?", default="kuhn", choices=sorted(PERSOS))
    ap.add_argument("--res", default="992,768")   # 2x la resolution native du Model 3
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--country", choices=sorted(PAYS), default=None,
                    help="force la region ; 'usa' ou 'export' met le jeu en anglais")
    args = ap.parse_args()

    value, label = PERSOS[args.perso]
    country = PAYS[args.country] if args.country else None
    if not os.path.isfile(EXE):
        sys.exit(f"Supermodel.exe introuvable dans {BASE}")

    cmd = [EXE, ROM, f"-res={args.res}",
           "-fullscreen" if args.fullscreen else "-window"]
    print(f"Fighting Vipers 2 - personnage force : {label}", flush=True)
    proc = subprocess.Popen(cmd, cwd=BASE)

    if value is None and country is None:
        proc.wait()
        return

    # attendre que l'image RAM soit allouee, puis verrouiller jusqu'a la sortie
    h = mod = None
    deadline = time.time() + 60
    while time.time() < deadline and proc.poll() is None:
        h, mod = attach(proc.pid)
        if h and mod:
            break
        time.sleep(0.5)
    if not h:
        proc.wait()
        sys.exit("impossible de s'attacher au process Supermodel")

    def raw(addr, size):
        b = (C.c_char * size)()
        n = C.c_size_t()
        if not k32.ReadProcessMemory(h, C.c_void_p(addr), b, size, C.byref(n)):
            return b""
        return b.raw[: n.value]

    ram = 0
    while time.time() < deadline and proc.poll() is None:
        ram = int.from_bytes(raw(mod + RAM_PTR_RVA, 8) or b"", "little")
        if ram:
            break
        time.sleep(0.2)
    if not ram:
        proc.wait()
        sys.exit("RAM Model 3 introuvable - build de Supermodel different ?")

    print(f"verrou actif (RAM {ram:#x}) - ferme l'emulateur pour l'arreter", flush=True)
    if country is not None:
        print(f"region forcee : {args.country.upper()}", flush=True)
    val = value.to_bytes(2, "big") if value is not None else None
    while proc.poll() is None:
        # Supermodel realloue son pool memoire apres le chargement des ROM :
        # relire le pointeur a chaque passe, sinon on ecrit dans l'ancienne zone
        ram = int.from_bytes(raw(mod + RAM_PTR_RVA, 8) or b"", "little")
        if not ram:
            time.sleep(0.05)
            continue
        targets = []
        if val is not None:
            targets += [(a, val) for a in SLOTS]
        if country is not None:
            targets.append((COUNTRY_ADDR, bytes([country])))
        for a, data in targets:
            start = a & ~3
            cur = raw(ram + start, 4)
            if len(cur) < 4:
                break
            buf = bytearray(swap32(cur))
            buf[a - start: a - start + len(data)] = data
            n = C.c_size_t()
            k32.WriteProcessMemory(h, C.c_void_p(ram + start),
                                   swap32(bytes(buf)), 4, C.byref(n))
        time.sleep(0.01)

    k32.CloseHandle(h)
    print("Supermodel ferme - verrou relache")


if __name__ == "__main__":
    main()
