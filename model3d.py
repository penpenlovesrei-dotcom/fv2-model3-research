"""Deroule un modele Real3D depuis le VROM, et dit si une adresse en est un.

Le format est celui du Real3D du Model 3, tel qu'il se lit dans les deux
rasteriseurs du port recompile (`src/video/r3d_scene.cpp`). Les adresses sont
en **mots de 32 bits** : sous `0x100000` la polygon RAM, au-dela le VROM. Le
champ est masque sur 24 bits, donc l'espace d'adressage des modeles fait
exactement 16 Mio de mots = **64 Mio**, la taille du VROM. Il est sature.

**Polygone** : 7 mots d'en-tete, puis 4 mots par sommet que le polygone ne
partage pas avec le precedent. Donc une taille **variable, de 7 a 23 mots** :
aucun padding, aucune indexation possible, il faut derouler.

    mot 0  bits 0-3 sommets repris du polygone precedent, bit 6 quad,
           bit 7 speculaire, bits 8-9 ecarte
    mot 1  normale de face X sur les 24 bits hauts (2.22 signe) ;
           bit 1 couleur dans le mot 4, **bit 2 dernier polygone**,
           bit 3 ombrage lisse, bit 4 double face, bit 5 ombrage fixe,
           bit 6 coordonnees de texture 1x (sinon 1/8)
    mot 2  normale de face Y ; bits 0-1 miroir V/U, 4-7 microtexture
    mot 3  normale de face Z ; bits 0-2 hauteur de texture, 3-5 largeur (32 << n)
    mot 4  RGB ou index de couleur ; bit 6 feuille de texture, bits 0-4 X
    mot 5  bits 0-4 Y de la texture, bits 8-31 base du LOD de texture
    mot 6  bit 10 texture, bits 7-9 format, bits 18-22 translucidite, etc.

**Sommet** : X, Y, Z sur les 24 bits hauts de trois mots, les 8 bits bas
portant la normale du sommet ou l'ombrage fixe ; puis U sur les 16 hauts et V
sur les 16 bas. Le point fixe depend du pas de carte : **17.7 sur Step 1.0**
(Virtua Fighter 3), **13.11 sur Step 1.5 et au-dela** (Fighting Vipers 2).

**Le test de validite, et c'est tout l'interet de ce script** : la normale de
face se lit en 2.22 signe, et sa norme doit valoir environ 1. Une adresse qui
n'est pas un modele echoue des le premier polygone. C'est ce qui a permis
d'etablir que les identifiants de ressource `0x00A0xxxx` de la table de decors
ne sont **pas** des adresses de modele (voir `decors.py`).

Le VROM s'obtient par `build_crom.py vrom`.

Usage :
    py -3 model3d.py <adresse en mots> [adresse ...]     teste des adresses
    py -3 model3d.py --step1 <adresse>                   en 17.7 au lieu de 13.11
    py -3 model3d.py --vrom <fv2_vrom.bin> <adresse>
"""

import pathlib
import struct
import sys

ICI = pathlib.Path(__file__).parent
POLY_RAM_MOTS = 0x100000
# nombre de sommets repris, par les bits 0-3 du mot 0
REPRIS = (0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 2, 3, 2, 3, 3, 4)
NORME_MIN, NORME_MAX = 0.5, 1.6
BUDGET = 20000


def signe24(mot):
    """Les 24 bits hauts d'un mot, en entier signe."""
    v = (mot >> 8) & 0xFFFFFF
    return v - 0x1000000 if v & 0x800000 else v


class Vrom:
    def __init__(self, chemin):
        chemin = pathlib.Path(chemin)
        if not chemin.exists():
            raise SystemExit(f"VROM introuvable : {chemin}\n"
                             "la produire avec : py -3 build_crom.py vrom")
        self.d = chemin.read_bytes()
        self.mots = len(self.d) // 4

    def mot(self, adr):
        if not 0 <= adr < self.mots:
            raise IndexError(adr)
        return struct.unpack_from(">I", self.d, adr * 4)[0]


def deroule(vrom, adresse, echelle=1.0 / 2048.0):
    """Deroule les polygones a cette adresse. Rend un dictionnaire de releve."""
    p = adresse
    polys = tris = 0
    xs, ys, zs = [], [], []
    textures = set()
    pourquoi = "budget epuise"
    try:
        while polys < BUDGET:
            h = [vrom.mot(p + i) for i in range(7)]
            if not any(h[:3]):
                pourquoi = f"en-tete nul au polygone {polys}"
                break
            norme = sum((signe24(h[1 + i]) / (1 << 22)) ** 2 for i in range(3)) ** 0.5
            if norme != 0.0 and not NORME_MIN < norme < NORME_MAX:
                pourquoi = f"norme de normale {norme:.3f} au polygone {polys}"
                break
            quad = (h[0] >> 6) & 1
            n = (4 if quad else 3) - REPRIS[h[0] & 0xF]
            if h[6] & 0x400:                      # texture
                tx = ((h[4] & 0x1F) | (((h[5] >> 7) & 1) << 5)) * 32
                ty = (h[5] & 0x1F) * 32
                textures.add((tx, ty, 32 << ((h[3] >> 3) & 7), 32 << (h[3] & 7),
                              (h[6] >> 7) & 7))
            q = p + 7
            for _ in range(n):
                xs.append(signe24(vrom.mot(q)) * echelle)
                ys.append(signe24(vrom.mot(q + 1)) * echelle)
                zs.append(signe24(vrom.mot(q + 2)) * echelle)
                q += 4
            polys += 1
            tris += 2 if quad else 1
            dernier = (h[1] >> 2) & 1
            p = q
            if dernier:
                pourquoi = "fin propre (bit du dernier polygone)"
                break
    except IndexError:
        pourquoi = "sortie du VROM"
    boite = None
    if xs:
        boite = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    return {"adresse": adresse, "polygones": polys, "triangles": tris,
             "pourquoi": pourquoi, "boite": boite, "textures": textures,
             "valide": pourquoi.startswith("fin propre") and polys > 1}


def montre(r):
    a = r["adresse"]
    zone = "polygon RAM" if a < POLY_RAM_MOTS else "VROM"
    print(f"{a:#010x} (mot) = {a * 4:#010x} (octet), {zone}")
    print(f"   {r['polygones']} polygones, {r['triangles']} triangles, "
          f"{len(r['textures'])} texture(s)")
    if r["boite"]:
        b = r["boite"]
        print(f"   boite  x[{b[0]:.2f} {b[1]:.2f}]  y[{b[2]:.2f} {b[3]:.2f}]  "
              f"z[{b[4]:.2f} {b[5]:.2f}]")
    print(f"   arret : {r['pourquoi']}")
    print(f"   -> {'MODELE PLAUSIBLE' if r['valide'] else 'pas un modele'}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    echelle = 1.0 / 2048.0                 # 13.11, Step 2.0
    chemin = ICI / "fv2_vrom.bin"
    adresses = []
    i = 0
    while i < len(args):
        if args[i] == "--step1":
            echelle = 1.0 / 128.0          # 17.7, Step 1.0
        elif args[i] == "--vrom":
            i += 1
            chemin = args[i]
        else:
            adresses.append(int(args[i], 0))
        i += 1
    if not adresses:
        raise SystemExit(__doc__)
    vrom = Vrom(chemin)
    print(f"{pathlib.Path(chemin).name} : {vrom.mots} mots "
          f"({len(vrom.d) // 1048576} Mio), point fixe "
          f"{'17.7' if echelle > 1 / 1000 else '13.11'}\n")
    for a in adresses:
        montre(deroule(vrom, a, echelle))
