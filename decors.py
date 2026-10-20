"""La table de decors de Fighting Vipers 2, dans les deux versions.

Trouvee le 2026-10-20 en cherchant les references aux pointeurs de noms. Elle
n'est documentee nulle part ailleurs, et c'est elle qui porte tout ce qui
definit un decor en dehors de sa geometrie.

**27 enregistrements de 0x70 octets**, dans l'ordre de la liste de noms, aux
deux memes endroits logiques :

  * arcade    : RAM `0x00075170`, noms a `0x000887D9` (adresses de l'image gzip
                decompressee, ou offset fichier == adresse PowerPC)
  * Dreamcast : fichier `0x0010763C`, noms a `0x000CD1D4`, base de chargement
                `0x8C010000`

Champs releves :

    +0x00  pointeur vers le nom
    +0x04  pointeur vers une liste d'octets, partagee entre plusieurs decors
    +0x08  pointeur vers la LISTE DE RESSOURCES : 8 identifiants, voir plus bas
    +0x0C ) jusqu'a trois pointeurs de CODE (arcade : 0x00018424-0x00018CC4).
    +0x10 ) TEST n'en a aucun, WESTERN deux, TOWER et BUILDING utilisent +0x0C.
    +0x18 ) Candidats pour les objets interactifs et destructibles.
    +0x1C  pointeur vers des listes d'octets (arcade 0x001154B0-0x001155CE)
    +0x20  pointeur vers un bloc de 0x1F8 octets, un par decor, dans l'ordre.
           Il contient une famille de triplets de plans normalises
           (+/-0.05, +/-1.083, +/-0.05) : collision ou cage, NON PROUVE.
    +0x24  identique pour les 27 : un bloc commun
    +0x28  identique pour les 27 : le meme
    +0x2C  5.0f, identique pour les 27
    +0x30..+0x48  flottants de camera (distances et limites)
    +0x4C..+0x54  petits flottants, souvent nuls
    +0x58  0.0040833f, identique pour les 27
    +0x5C  paires de couleurs, tres variables
    +0x60  index (0x27-0x3A) en poids fort, 0xFF en poids faible -- role NON ETABLI
    +0x64  ARGB : brouillard ou ambiance (TEST : 0xFFAA0000, unique)
    +0x68  0x000001FF, ou 0x010001FF pour TOWER et BUILDING
    +0x6C  3, identique pour les 27

**Le champ qui tranche est +0x08.** La liste de 8 identifiants qu'il pointe a
pour 4e entree la **geometrie propre du decor**, et c'est la que les deux
versions divergent : sur arcade l'entree de TEST vaut `0x00000000`, sur
Dreamcast `0x001800F0`. **TEST est le decor d'entrainement, et sa geometrie
n'existe que sur Dreamcast.** L'arcade en porte tout le reste -- le nom,
l'enregistrement entier, la camera, le brouillard, le bloc de 0x1F8.

Les genres se correspondent : arcade 0xA0/0x10 <-> DC 0x00F0 (geometrie de
decor), 0xA0/0x2E <-> 0x03A9, 0xA0/0x2F <-> 0x04A9, 0xA1/0x0B <-> 0x00FF. Et
l'enumeration complete du genre geometrie se lit en clair : arcade
`0x000EC048`, 20 creneaux (0x00-0x13) ; Dreamcast `0x00102420`, **25 creneaux
(0x00-0x18)**. La Dreamcast a ajoute 0x14 a 0x18, et TEST pointe sur le dernier.
L'arcade a 8 creneaux enumeres et inutilises : 0, 6, 7, 8, 9, 0xF, 0x11, 0x13.

Resultat negatif a ne pas repayer : les identifiants `0x00A0xxxx` ne sont PAS
des adresses de modele VROM -- deroules avec `model3d.py`, ils echouent des le
premier polygone sur la norme de la normale de face. La resolution
(genre, index) -> entree d'archive n'est **pas encore trouvee**.

Rien n'est code en dur ici : la table se trouve en cherchant le bloc de noms,
puis un pointeur vers le premier d'entre eux. Les deux images s'obtiennent par
`build_crom.py` + `gzip_crom.py extraire` (arcade) et `cdi.py sortir`
(Dreamcast).

Usage :
    py -3 decors.py arcade [foo.bin]
    py -3 decors.py dreamcast [dreamcast/1ST_READ.BIN]
    py -3 decors.py comparer [foo.bin] [dreamcast/1ST_READ.BIN]
"""

import pathlib
import struct
import sys

ICI = pathlib.Path(__file__).parent
PAS = 0x70
# Les noms sont colles sur arcade (TEST a +0, WESTERN a +5) et alignes sur 4 sur
# Dreamcast (WESTERN a +8) : on ancre sur un nom long, puis on recule vers TEST.
ANCRE_LONGUE = b"AC_CARRIER\x00"
ANCRE_PREMIER = b"TEST\x00"
DC_BASE = 0x8C010000
GEOM_ARCADE = 0x10
GEOM_DC = 0x00F0
# genre de ressource : arcade (genre sur 8 bits) -> (genre Dreamcast, libelle)
GENRES = {0x10: (0x00F0, "geometrie du decor"),
          0x2E: (0x03A9, "commun A"),
          0x2F: (0x04A9, "commun B"),
          0x0B: (0x00FF, "commun C")}
DC_GENRES = {dc: (arc, lbl) for arc, (dc, lbl) in GENRES.items()}


class Image:
    """Une des deux images, avec son boutisme et sa base de chargement."""

    def __init__(self, chemin, gros_boutien, base):
        chemin = pathlib.Path(chemin)
        if not chemin.exists():
            raise SystemExit(f"image introuvable : {chemin}")
        self.d = chemin.read_bytes()
        self.nom = chemin.name
        self.gb = gros_boutien
        self.fmt = ">I" if gros_boutien else "<I"
        self.base = base

    def mot(self, off):
        return struct.unpack_from(self.fmt, self.d, off)[0]

    def off(self, ptr):
        """Adresse de chargement -> offset fichier ; None si hors image."""
        o = ptr - self.base
        return o if 0 <= o < len(self.d) - 4 else None

    def chaine(self, ptr):
        o = self.off(ptr)
        if o is None:
            return None
        fin = self.d.find(b"\x00", o)
        return self.d[o:fin].decode("latin1") if 0 <= fin - o < 64 else None

    def trouve_table(self):
        """Rend (offset de la table, nombre d'enregistrements), par la mesure."""
        noms = -1
        i = self.d.find(ANCRE_LONGUE)
        while i >= 0 and noms < 0:
            fenetre = self.d[max(0, i - 0x20):i]
            j = fenetre.rfind(ANCRE_PREMIER)
            if j >= 0:
                noms = max(0, i - 0x20) + j
            i = self.d.find(ANCRE_LONGUE, i + 1)
        if noms < 0:
            raise SystemExit(f"{self.nom} : bloc de noms de decors introuvable")
        occ = self.d.find(struct.pack(self.fmt, noms + self.base))
        if occ < 0:
            raise SystemExit(f"{self.nom} : aucun pointeur vers TEST "
                             f"({noms + self.base:#010x})")
        n = 0
        while occ + (n + 1) * PAS <= len(self.d):
            po = self.off(self.mot(occ + n * PAS))
            if po is None or not (noms <= po < noms + 0x200):
                break
            if not self.chaine(self.mot(occ + n * PAS)):
                break
            n += 1
        return occ, n

    def ressources(self, ptr):
        o = self.off(ptr)
        return [] if o is None else [self.mot(o + i * 4) for i in range(8)]

    def decode(self, v):
        """Rend (genre, index, texte) pour un identifiant de ressource."""
        if v == 0:
            return (None, None, "vide")
        if self.gb:
            famille, genre, index = v >> 16, (v >> 8) & 0xFF, v & 0xFF
            lbl = GENRES.get(genre, (None, f"genre {genre:#04x}"))[1]
            return (genre, index,
                    f"{v:#010x}  famille {famille:#06x}  {lbl} index {index:#04x}")
        genre, index = v & 0xFFFF, v >> 16
        lbl = DC_GENRES.get(genre, (None, f"genre {genre:#06x}"))[1]
        return (genre, index, f"{v:#010x}  {lbl} index {index:#04x}")

    def geometrie(self, ptr):
        """L'identifiant de geometrie d'une liste de ressources, ou 0."""
        attendu = GEOM_ARCADE if self.gb else GEOM_DC
        for v in self.ressources(ptr):
            if self.decode(v)[0] == attendu:
                return v
        return 0

    def enumeration(self):
        """Trouve l'enumeration contigue du genre geometrie : (offset, creneaux)."""
        if self.gb:
            faire = lambda i: struct.pack(">I", 0x00A00000 | (GEOM_ARCADE << 8) | i)
        else:
            faire = lambda i: struct.pack("<I", (i << 16) | GEOM_DC)
        debut = self.d.find(faire(0))
        while debut >= 0:
            n = 0
            while self.d[debut + n * 4: debut + n * 4 + 4] == faire(n):
                n += 1
            if n >= 8:
                return debut, n
            debut = self.d.find(faire(0), debut + 1)
        return None, 0


def arcade(chemin):
    return Image(chemin, True, 0)


def dreamcast(chemin):
    return Image(chemin, False, DC_BASE)


def montre(img):
    base, n = img.trouve_table()
    print(f"{img.nom} : table de decors a {base + img.base:#010x}, "
          f"{n} enregistrements de {PAS:#x} octets\n")
    for k in range(n):
        o = base + k * PAS
        nom = img.chaine(img.mot(o)) or "?"
        liste = img.mot(o + 8)
        res = img.ressources(liste)
        print(f"[{k:2}] {nom:11} geometrie : {img.decode(img.geometrie(liste))[2]}")
        print(f"     +08 {liste:#010x} -> " + " ".join(f"{v:08x}" for v in res))
    off, creneaux = img.enumeration()
    print()
    if off is None:
        print("enumeration du genre geometrie : introuvable")
    else:
        print(f"enumeration du genre geometrie a {off + img.base:#010x} : "
              f"{creneaux} creneaux (0x00-{creneaux - 1:#04x})")


def comparer(ca, cd):
    a, d = arcade(ca), dreamcast(cd)
    ba, na = a.trouve_table()
    bd, nd = d.trouve_table()
    print(f"arcade    : {na} enregistrements a {ba + a.base:#010x}  ({a.nom})")
    print(f"dreamcast : {nd} enregistrements a {bd + d.base:#010x}  ({d.nom})\n")
    print(f"{'decor':12} {'arcade':>12} {'dreamcast':>12}   index arcade / dreamcast")
    for k in range(min(na, nd)):
        nom = a.chaine(a.mot(ba + k * PAS)) or "?"
        ga = a.geometrie(a.mot(ba + k * PAS + 8))
        gd = d.geometrie(d.mot(bd + k * PAS + 8))
        ia, id_ = a.decode(ga)[1], d.decode(gd)[1]
        txt = lambda v: "vide" if v is None else f"{v:#04x}"
        ecart = ""
        if ia != id_:
            ecart = "   <<< DIVERGE" if (ia is None) != (id_ is None) else "   index different"
        print(f"{nom:12} {ga:#012x} {gd:#012x}   "
              f"{txt(ia):>6} / {txt(id_):<6}{ecart}")
    print()
    for img, lbl in ((a, "arcade   "), (d, "dreamcast")):
        off, cr = img.enumeration()
        if off is None:
            print(f"{lbl} : enumeration du genre geometrie introuvable")
        else:
            print(f"{lbl} : genre geometrie a {off + img.base:#010x}, "
                  f"{cr} creneaux (0x00-{cr - 1:#04x})")


if __name__ == "__main__":
    quoi = sys.argv[1] if len(sys.argv) > 1 else "comparer"
    defaut_a = ICI / "foo.bin"
    defaut_d = ICI / "dreamcast" / "1ST_READ.BIN"
    if quoi == "arcade":
        montre(arcade(sys.argv[2] if len(sys.argv) > 2 else defaut_a))
    elif quoi == "dreamcast":
        montre(dreamcast(sys.argv[2] if len(sys.argv) > 2 else defaut_d))
    elif quoi == "comparer":
        comparer(sys.argv[2] if len(sys.argv) > 2 else defaut_a,
                 sys.argv[3] if len(sys.argv) > 3 else defaut_d)
    else:
        raise SystemExit(__doc__)
