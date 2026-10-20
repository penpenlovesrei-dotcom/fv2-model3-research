"""Ouvre l'image Dreamcast de Fighting Vipers 2 et en sort les fichiers.

Le `.cdi` est un DiscJuggler a secteurs de **2336 octets** -- pas 2352 : il n'y
a **aucune marque de synchro** `00 FF*10 00` dans l'image, donc ni synchro ni
en-tete de secteur, 2048 octets utiles suivis de 288 d'ECC. La piste de donnees
commence a **LBA 45000**, reperee par l'IP.BIN (`SEGA SEGAKATANA`, nom de boot
a +0x60), et le descripteur de volume ISO est 16 secteurs plus loin. D'ou :

    offset(LBA) = base + (LBA - 45000) * 2336

La base se mesure, elle n'est pas devinee : on cherche l'IP.BIN, puis on
verifie que le PVD tombe bien a +16 secteurs. Si les deux ne concordent pas, le
script s'arrete plutot que de lire de travers.

Ce que le disque contient (rip PAL, volume `FightingVipers-2-Pal-DCP`, mkisofs) :
`1ST_READ.BIN` le jeu SH-4, puis cinq archives AFS -- `MDL_DAT` les modeles,
`TEX_DAT` les textures, `MOT_DAT` les animations, `SND_DAT` et `ADX_DAT` le son
-- et un `/0.0` de bourrage de selfboot de 300 Mio. Voir `afs.py` pour l'interieur
des archives.

L'image se surcharge par la variable d'environnement `FV2_CDI`.

Usage :
    py -3 cdi.py lister                   l'arborescence, avec LBA et offsets
    py -3 cdi.py sortir [dossier]         tous les fichiers, sauf le bourrage
    py -3 cdi.py sortir <dossier> <nom>   un seul, par son nom ISO
"""

import os
import pathlib
import struct
import sys

ICI = pathlib.Path(__file__).parent
CDI = pathlib.Path(os.environ.get("FV2_CDI", r"C:\Users\frede\Documents\Dreamcast\Games\Fighting Vipers 2.cdi"))
SECTEUR = 2336
UTILE = 2048
LBA_PISTE = 45000
IP_MAGIE = b"SEGA SEGAKATANA"
# le bourrage de selfboot : 300 Mio de rien, jamais a sortir
BOURRAGE = {"0.0"}


def base(f):
    """Rend l'offset fichier du LBA 45000, mesure puis verifie sur le PVD."""
    pos = 0
    reste = b""
    while True:
        f.seek(pos)
        bloc = f.read(1 << 24)
        if not bloc:
            raise SystemExit("IP.BIN introuvable : ce n'est pas une piste de donnees Dreamcast")
        tampon = reste + bloc
        i = tampon.find(IP_MAGIE)
        if i >= 0:
            b = pos - len(reste) + i
            f.seek(b + 16 * SECTEUR)
            if f.read(6) == b"\x01CD001":
                return b
            raise SystemExit(f"IP.BIN a {b:#x} mais pas de PVD a +16 secteurs de 2336 : "
                             "la taille de secteur n'est pas celle attendue")
        reste = tampon[-len(IP_MAGIE):]
        pos += 1 << 24


def lire(f, b, lba, n):
    out = bytearray()
    i = 0
    while len(out) < n:
        f.seek(b + (lba + i - LBA_PISTE) * SECTEUR)
        out += f.read(UTILE)
        i += 1
    return bytes(out[:n])


def arbre(f, b):
    pvd = lire(f, b, LBA_PISTE + 16, UTILE)
    volume = pvd[40:72].decode("latin1").strip()
    racine = pvd[156:156 + 34]
    lba = struct.unpack_from("<I", racine, 2)[0]
    taille = struct.unpack_from("<I", racine, 10)[0]
    out = []

    def marche(lba, taille, chemin, profondeur):
        d = lire(f, b, lba, taille)
        i = 0
        while i < len(d) - 1:
            L = d[i]
            if L == 0:                      # reste du secteur : bourre de zeros
                i = (i // UTILE + 1) * UTILE
                continue
            ext = struct.unpack_from("<I", d, i + 2)[0]
            sz = struct.unpack_from("<I", d, i + 10)[0]
            drapeaux = d[i + 25]
            nl = d[i + 32]
            nm = d[i + 33:i + 33 + nl]
            if nm not in (b"\x00", b"\x01"):
                nom = nm.decode("latin1").split(";")[0]
                if drapeaux & 2:
                    out.append((chemin + nom + "/", ext, sz, True))
                    if profondeur < 5:
                        marche(ext, sz, chemin + nom + "/", profondeur + 1)
                else:
                    out.append((chemin + nom, ext, sz, False))
            i += L

    marche(lba, taille, "/", 0)
    return volume, out


def lister():
    with CDI.open("rb") as f:
        b = base(f)
        volume, entrees = arbre(f, b)
        print(f"{CDI.name} : piste de donnees a {b:#x} (LBA {LBA_PISTE}), secteurs de {SECTEUR}")
        print(f"volume : {volume!r}\n")
        for nom, lba, taille, rep in sorted(entrees):
            o = b + (lba - LBA_PISTE) * SECTEUR
            print(f"{taille:>12}  LBA {lba:>7}  offset {o:#011x}  {nom}")


def sortir(dossier, un_seul=None):
    dossier = pathlib.Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    with CDI.open("rb") as f:
        b = base(f)
        _, entrees = arbre(f, b)
        for nom, lba, taille, rep in sorted(entrees):
            court = nom.rsplit("/", 1)[-1]
            if rep or taille == 0:
                continue
            if un_seul and court.lower() != un_seul.lower():
                continue
            if not un_seul and court in BOURRAGE:
                print(f"  (saute {court} : bourrage de selfboot, {taille} octets)")
                continue
            s = dossier / court
            s.write_bytes(lire(f, b, lba, taille))
            print(f"  {s} : {taille} octets")


if __name__ == "__main__":
    if not CDI.exists():
        raise SystemExit(f"image introuvable : {CDI}\nposer FV2_CDI sur son chemin")
    quoi = sys.argv[1] if len(sys.argv) > 1 else "lister"
    if quoi == "lister":
        lister()
    elif quoi == "sortir":
        sortir(sys.argv[2] if len(sys.argv) > 2 else ICI / "dreamcast",
               sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        raise SystemExit(__doc__)
