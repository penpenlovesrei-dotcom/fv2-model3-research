"""Lit les archives AFS de la version Dreamcast : table, profil, extraction.

**Format AFS** (celui de Sega, et ici sans bloc de noms) :

    +0x00  "AFS\0"
    +0x04  uint32 petit-boutien : nombre d'entrees
    +0x08  n x (offset uint32, taille uint32), petit-boutien
           puis le mot qui suivrait la table vaut 0,0 : il n'y a **aucune
           table de noms**, donc l'indice est le seul identifiant.

La premiere entree est toujours a `0x80000` et les entrees sont alignees sur
2 Kio.

Ce que le profil montre sur `MDL_DAT.AFS` (78 entrees) : le premier mot de
chaque entree separe deux classes -- `01000000` et `FFFFFFFF`. Les entrees
**0 a 15** forment un bloc contigu de classe `01000000` ; les suivantes vont
**par paires de taille presque egale**, ce qui est l'armure intacte et brisee
d'un meme combattant.

Un enregistrement commence par quatre mots de parametre du Tile Accelerator du
PowerVR2, **pre-cuits dans le fichier** -- Parameter Control, ISP/TSP, TSP,
Texture Control -- suivis d'une boite englobante (centre xyz + rayon), d'un
compteur, de `FFFFFFFF`, de nine flottants d'eclairage, puis d'autres
compteurs. Le champ adresse du Texture Control vaut **0** : il est renseigne au
chargement, quand le blob de `TEX_DAT.AFS` est pose en VRAM -- c'est pour ca
que les entrees de `TEX_DAT.AFS` n'ont aucun en-tete `PVRT` ni `GBIX`.

Taille et format d'une texture se lisent dans ces mots : **bits 0-5 du TSP**
pour U et V, **bits 30-27 du Texture Control** pour le format (bit 30 = VQ).
Pour le decodage lui-meme, le format est le meme que celui que
`celsowm/vf3-decomp` documente dans `docs/formats/TEX.md` : pas d'en-tete,
RGB565 petit-boutien, twiddle PVR par tuiles.

Usage :
    py -3 afs.py table <archive.afs>           la table des entrees
    py -3 afs.py profil <archive.afs> [n]      classe, ancres TA, boite des n premieres
    py -3 afs.py sortir <archive.afs> <dossier> [indice]
"""

import math
import pathlib
import struct
import sys


def table(chemin):
    d = pathlib.Path(chemin).read_bytes()
    if d[:4] != b"AFS\x00":
        raise SystemExit(f"{chemin} ne commence pas par AFS\0 : {d[:4].hex()}")
    n = struct.unpack_from("<I", d, 4)[0]
    return d, [struct.unpack_from("<II", d, 8 + i * 8) for i in range(n)]


def ancres_ta(blob):
    """Compte les couples (mot 0x8xxxxxxx, mot 0x83xxxxxx) : les etats TA."""
    n = 0
    for p in range(0, len(blob) - 8, 4):
        a = struct.unpack_from("<I", blob, p)[0]
        b = struct.unpack_from("<I", blob, p + 4)[0]
        if (a >> 28) == 8 and (b >> 24) == 0x83:
            n += 1
    return n


def cmd_table(chemin):
    d, ent = table(chemin)
    print(f"{pathlib.Path(chemin).name} : {len(ent)} entrees")
    for i, (o, s) in enumerate(ent):
        print(f"  [{i:3}] offset {o:#010x}  taille {s:>9}")


def cmd_profil(chemin, combien):
    d, ent = table(chemin)
    print(f"{pathlib.Path(chemin).name} : {len(ent)} entrees\n")
    print(" idx     offset      taille  mot0      etats TA  boite englobante (x, y, z, rayon)")
    for i, (o, s) in enumerate(ent[:combien]):
        if s == 0:
            print(f" [{i:3}] {o:#010x} {s:>11}  (vide)")
            continue
        blob = d[o:o + s]
        w0 = struct.unpack_from("<I", blob, 0)[0]
        # la boite suit les deux premiers mots pour la classe 01000000
        bb = struct.unpack_from("<4f", blob, 8)
        bb = tuple(v if math.isfinite(v) else 0.0 for v in bb)
        print(f" [{i:3}] {o:#010x} {s:>11}  {w0:08x}  {ancres_ta(blob):>8}  "
              f"{bb[0]:9.3f} {bb[1]:9.3f} {bb[2]:9.3f} {bb[3]:9.3f}")


def cmd_sortir(chemin, dossier, indice):
    d, ent = table(chemin)
    dossier = pathlib.Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    base = pathlib.Path(chemin).stem
    for i, (o, s) in enumerate(ent):
        if s == 0 or (indice is not None and i != indice):
            continue
        sortie = dossier / f"{base}_{i:03}.bin"
        sortie.write_bytes(d[o:o + s])
        print(f"  {sortie} : {s} octets")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    quoi = sys.argv[1]
    if quoi == "table":
        cmd_table(sys.argv[2])
    elif quoi == "profil":
        cmd_profil(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 16)
    elif quoi == "sortir":
        cmd_sortir(sys.argv[2], sys.argv[3],
                   int(sys.argv[4]) if len(sys.argv) > 4 else None)
    else:
        raise SystemExit(__doc__)
