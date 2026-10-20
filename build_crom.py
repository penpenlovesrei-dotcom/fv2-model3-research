"""Reconstruit les images de ROM de Fighting Vipers 2 depuis le zip MAME.

Trois images, et l'entrelacement n'est pas le meme pour les deux regions :

  * **CROM** (8 Mio) : les quatre EPROM de programme `epr-20596a.17` a
    `epr-20599a.20`, 2 Mio chacune, posees par morceaux de **2 octets** avec un
    pas de **8**, aux deplacements 6, 4, 2, 0 -- `.20` en tete. Le resultat
    demande encore un **echange des deux octets de chaque demi-mot** pour que
    le gzip de Sega se lise (`1f 8b`), d'ou le nom `fv2_crom_swap16.bin`, celui
    qu'attend `gzip_crom.py`.
  * **VROM** (64 Mio) : les seize `mpr-20580.26` a `mpr-20595.41`, 4 Mio
    chacune, morceaux de **2 octets** avec un pas de **32**, deplacements 0 a
    30 dans l'ordre des numeros, et **sans echange** : ce sont deja des mots
    gros-boutiens tels que le Real3D les lit.

L'entrelacement se fait aussi **dans l'autre sens** (`eprom`) : c'est la
derniere marche pour qu'un patch de `gzip_crom.py injecter` redevienne un zip
jouable. Verifie par aller-retour sur les CRC32 des quatre EPROM d'origine,
jamais encore essaye en jeu.

Le zip se surcharge par la variable d'environnement `FV2_ZIP`.

Usage :
    py -3 build_crom.py crom              -> fv2_crom_swap16.bin  (8 Mio)
    py -3 build_crom.py vrom              -> fv2_vrom.bin         (64 Mio)
    py -3 build_crom.py tout              -> les deux
    py -3 build_crom.py eprom <crom.bin>  -> eprom/epr-2059*.bin + leurs CRC32
"""

import os
import pathlib
import sys
import zipfile
import zlib

ICI = pathlib.Path(__file__).parent
ZIP = pathlib.Path(os.environ.get("FV2_ZIP", r"C:\Users\frede\Desktop\FV2\roms\fvipers2.zip"))

# (nom, deplacement en octets) ; pas de 8, morceaux de 2, echange 16 bits ensuite
CROM = [("epr-20599a.20", 0), ("epr-20598a.19", 2), ("epr-20597a.18", 4), ("epr-20596a.17", 6)]
CROM_TAILLE = 0x800000
# les seize ROM de texture ; pas de 32, morceaux de 2, sans echange
VROM = [(f"mpr-{20580 + i}.{26 + i}", i * 2) for i in range(16)]
VROM_TAILLE = 0x4000000


def entrelace(z, roms, taille, pas):
    out = bytearray(taille)
    for nom, dep in roms:
        d = z.read(nom)
        for i in range(0, len(d), 2):
            o = dep + (i // 2) * pas
            out[o:o + 2] = d[i:i + 2]
    return out


def swap16(d):
    d = bytearray(d)
    d[0::2], d[1::2] = d[1::2], d[0::2]
    return d


def crom(z):
    d = swap16(entrelace(z, CROM, CROM_TAILLE, 8))
    if bytes(d[:2]) != b"\x1f\x8b":
        raise SystemExit(f"pas de gzip en tete apres echange : {bytes(d[:2]).hex()} -- entrelacement faux")
    s = ICI / "fv2_crom_swap16.bin"
    s.write_bytes(bytes(d))
    print(f"{s.name} : {len(d)} octets, gzip en tete ({bytes(d[:4]).hex()})")


def vrom(z):
    d = entrelace(z, VROM, VROM_TAILLE, 32)
    s = ICI / "fv2_vrom.bin"
    s.write_bytes(bytes(d))
    vides = sum(1 for i in range(len(d) // 2048) if not any(d[i * 2048:(i + 1) * 2048]))
    print(f"{s.name} : {len(d)} octets, {vides} bloc(s) de 2 Kio entierement nuls sur {len(d) // 2048}")


def eprom(chemin):
    """Decoupe une CROM de 8 Mio en ses quatre EPROM, et rend leurs CRC32."""
    d = pathlib.Path(chemin).read_bytes()
    if len(d) != CROM_TAILLE:
        raise SystemExit(f"{chemin} fait {len(d)} octets, il en faut {CROM_TAILLE}")
    d = swap16(d)                     # on defait l'echange pose par crom()
    dossier = ICI / "eprom"
    dossier.mkdir(exist_ok=True)
    for nom, dep in CROM:
        e = bytearray(CROM_TAILLE // 4)
        for i in range(0, len(e), 2):
            o = dep + (i // 2) * 8
            e[i:i + 2] = d[o:o + 2]
        (dossier / nom).write_bytes(bytes(e))
        print(f"  {nom} : {len(e)} octets, CRC32 {zlib.crc32(bytes(e)):#010x}")
    print(f"ecrites dans {dossier}. Comparer les CRC32 a ceux du zip d'origine "
          f"avant d'en faire un jeu.")


if __name__ == "__main__":
    quoi = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if quoi == "eprom":
        eprom(sys.argv[2])
    else:
        if not ZIP.exists():
            raise SystemExit(f"zip introuvable : {ZIP}\nposer FV2_ZIP sur son chemin")
        with zipfile.ZipFile(ZIP) as z:
            if quoi in ("crom", "tout"):
                crom(z)
            if quoi in ("vrom", "tout"):
                vrom(z)
            if quoi not in ("crom", "vrom", "tout"):
                raise SystemExit(__doc__)
