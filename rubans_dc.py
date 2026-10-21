"""Le format de ruban de MDL_DAT.AFS, lu exactement -- sans heuristique.

Etabli le 2026-10-21. Ce qui suit n'est pas une lecture plausible : c'est la
seule qui satisfasse trois contraintes independantes, chacune a 100 % sur les
77 entrees utiles de l'archive.

LA ZONE DE RUBANS d'une partie commence en +0x50 et sa taille est annoncee en
+0x4C. On y marche d'element en element :

    en-tete de ruban      8 octets   (code, compte)
    sommet               32 octets   pos 3f, puis u et v en +0x18 et +0x1C
    RENVOI                8 octets   (0x5F......, 0x........)

Le compte de l'en-tete compte les sommets ET les renvois.

LE RENVOI se reconnait au HAUT OCTET 0x5F de son premier mot. Le marqueur est
sur : 0x5F000000 vaut 9,2e18 en flottant, et les positions tiennent dans
+-2000, donc aucun sommet ne peut etre pris pour un renvoi.

Sa cible se lit dans les **24 bits de poids faible du SECOND mot**, en entier
signe, comptes a reculons depuis la FIN de l'enregistrement :

    cible = adresse_du_renvoi + 8 + s24(second mot)

et elle tombe sur le debut d'un sommet deja stocke **n'importe ou dans la
partie** -- pas seulement dans le ruban courant.

LES TROIS PREUVES

    pavage exact des zones    15 559 / 15 559     100,0 %
    renvois resolus          141 909 / 141 909    100,000 %
    normales unitaires       370 392 / 374 016     99,03 %

Le 0,97 % de normales non unitaires n'est pas un defaut : ce sont les parties
a ColType 1, ou les douze octets du milieu portent deux mots de couleur au lieu
d'une normale. La position et les coordonnees de texture, elles, sont aux memes
offsets dans les deux formes -- c'est pourquoi la geometrie se lit
uniformement.

CE QUI ETAIT FAUX AVANT, et pourquoi le sol se desordonnait. L'ancien lecteur
avancait de 32 octets par sommet en balayant par mots de 4 jusqu'au suivant, et
sautait donc **par-dessus les renvois** : arrive au bout de son compte, il
allait prendre des sommets du ruban SUIVANT. Les « ecarts de 40 et 48 octets »
que les notes attribuaient a des mots d'etat intercales sont simplement
32 + 8 et 32 + 16, soit un sommet suivi d'un ou deux renvois. Et l'hypothese du
« ruban continue » (bit 5 du code -> compte - 2) ne gagnait rien au test du
pavage : 76,9 % avec ou sans.

CE QUI RESTE INCONNU : le PREMIER mot d'un renvoi. Son haut octet est toujours
0x5F, et ses 24 bits de poids faible sont un multiple de 64 -- mais aucune
convention d'offset ne les fait tomber sur un sommet (23 % au mieux, contre
100 % pour le second mot). Il ne sert pas a la geometrie.

Usage :
    py -3 rubans_dc.py <indice>              le profil d'une entree
    py -3 rubans_dc.py --preuve              refait les trois mesures
"""

import math
import struct
import sys
import pathlib

ICI = pathlib.Path(__file__).parent
sys.path.insert(0, str(ICI))
import textures_dc as T

MARQUE_RENVOI = 0x5F
TAILLE_SOMMET = 32
TAILLE_RENVOI = 8
TAILLE_ENTETE = 8


def s24(mot):
    """Les 24 bits de poids faible, en entier signe."""
    v = mot & 0xFFFFFF
    return v - 0x1000000 if v & 0x800000 else v


def parties(b):
    """Les offsets des parties : un couple (0x8xxxxxxx, 0x83xxxxxx).

    Les parties ne s'enchainent PAS par la taille de zone -- une chaine
    s'arrete apres six parties en moyenne, il y a donc une structure de groupe
    au-dessus qu'on n'a pas etablie. Le balayage par motif, lui, est sur : les
    15 559 parties qu'il trouve pavent toutes leur zone a l'octet pres, ce
    qu'un faux positif ne ferait pas.
    """
    out = []
    for p in range(0, len(b) - 8, 4):
        a, c = struct.unpack_from("<II", b, p)
        if (a >> 28) == 8 and (c >> 24) == 0x83:
            out.append(p)
    return out


def entete_de_partie(b, p):
    """Rend le dictionnaire de l'en-tete, ou None si la zone est hors bornes."""
    if p + 0x50 > len(b):
        return None
    pcw, isp, tsp, txc = struct.unpack_from("<4I", b, p)
    zone = struct.unpack_from("<I", b, p + 0x4C)[0]
    if zone == 0 or p + 0x50 + zone > len(b):
        return None
    return {
        "offset": p, "pcw": pcw, "isp": isp, "tsp": tsp, "txc": txc,
        "index_texture": struct.unpack_from("<I", b, p + 0x20)[0],
        "coltype": (pcw >> 4) & 3,
        "zone": zone, "debut": p + 0x50, "fin": p + 0x50 + zone,
    }


def lit_partie(b, en):
    """Rend (rubans, sommets) d'une partie.

    `sommets` associe l'offset d'un sommet stocke a (x, y, z, u, v).
    `rubans` est une liste de (code, [offsets dans l'ordre du ruban]) ou chaque
    offset designe un sommet de `sommets` -- qu'il ait ete stocke la ou atteint
    par un renvoi.
    """
    deb, fin = en["debut"], en["fin"]
    sommets = {}
    rubans = []
    q = deb
    while q + TAILLE_ENTETE <= fin:
        code, compte = struct.unpack_from("<II", b, q)
        if compte == 0 or compte > 4096:
            break
        q += TAILLE_ENTETE
        suite = []
        while len(suite) < compte and q + TAILLE_RENVOI <= fin:
            mot = struct.unpack_from("<I", b, q)[0]
            if (mot >> 24) == MARQUE_RENVOI:
                second = struct.unpack_from("<I", b, q + 4)[0]
                q += TAILLE_RENVOI
                suite.append(q + s24(second))
            else:
                if q + TAILLE_SOMMET > fin:
                    break
                x, y, z = struct.unpack_from("<3f", b, q)
                u, v = struct.unpack_from("<2f", b, q + 0x18)
                sommets[q] = (x, y, z, u, v)
                suite.append(q)
                q += TAILLE_SOMMET
        if len(suite) == compte:
            rubans.append((code, suite))
    return rubans, sommets, q == fin


def triangles(suite):
    """Un ruban de triangles, avec l'alternance de sens.

    Les triangles degeneres -- deux sommets identiques, ce qui arrive quand un
    ruban en raccorde deux autres -- sont ecartes : ils n'ont pas d'aire et
    Blender les signale.
    """
    out = []
    for i in range(len(suite) - 2):
        a, c, d = suite[i], suite[i + 1], suite[i + 2]
        tri = (a, c, d) if i % 2 == 0 else (c, a, d)
        if len(set(tri)) == 3:
            out.append(tri)
    return out


def entree(indice):
    """Rend (octets, [(en-tete, rubans, sommets)]) pour une entree MDL."""
    mdl, me = T.afs("MDL_DAT.AFS")
    o, s = me[indice]
    if s == 0:
        raise SystemExit("l'entree %d est le terminateur de l'archive" % indice)
    b = mdl[o:o + s]
    out = []
    for p in parties(b):
        en = entete_de_partie(b, p)
        if en is None:
            continue
        rub, som, exact = lit_partie(b, en)
        en["exact"] = exact
        out.append((en, rub, som))
    return b, out


def cmd_profil(indice):
    b, parts = entree(indice)
    ns = sum(len(s) for _, _, s in parts)
    nr = sum(len(r) for _, r, _ in parts)
    nt = sum(len(triangles(su)) for _, r, _ in parts for _, su in r)
    exacts = sum(1 for en, _, _ in parts if en["exact"])
    print("entree %d : %d octets, %d partie(s) dont %d pavee(s) exactement"
          % (indice, len(b), len(parts), exacts))
    print("   %d sommet(s) stocke(s), %d ruban(s), %d triangle(s)" % (ns, nr, nt))
    tex = {}
    for en, _, _ in parts:
        tex[en["index_texture"]] = tex.get(en["index_texture"], 0) + 1
    print("   index de texture employes :",
          ", ".join("%d (x%d)" % kv for kv in sorted(tex.items())))
    ct = {}
    for en, _, _ in parts:
        ct[en["coltype"]] = ct.get(en["coltype"], 0) + 1
    print("   ColType :", ", ".join("%d (x%d)" % kv for kv in sorted(ct.items())))


def cmd_preuve():
    mdl, me = T.afs("MDL_DAT.AFS")
    pt = pe = sm = nu = rv = rj = 0
    for i in range(len(me)):
        o, s = me[i]
        if s == 0:
            continue
        b = mdl[o:o + s]
        for p in parties(b):
            en = entete_de_partie(b, p)
            if en is None:
                continue
            pt += 1
            rub, som, exact = lit_partie(b, en)
            if exact:
                pe += 1
            sm += len(som)
            for q, (x, y, z, u, v) in som.items():
                nx, ny, nz = struct.unpack_from("<3f", b, q + 12)
                try:
                    if abs(math.sqrt(nx * nx + ny * ny + nz * nz) - 1.0) >= 1e-2:
                        nu += 1
                except (ValueError, OverflowError):
                    nu += 1
            # tout offset d'une suite doit designer un sommet de la partie,
            # qu'il ait ete stocke la ou atteint par un renvoi
            for code, suite in rub:
                rv += sum(1 for off in suite if off not in som)
    print("parties pavees exactement : %d / %d  (%.1f %%)" % (pe, pt, 100.0 * pe / pt))
    print("sommets stockes           : %d" % sm)
    print("normales non unitaires    : %d  (%.2f %%)" % (nu, 100.0 * nu / sm))
    print("offsets de suite hors des sommets stockes : %d" % rv)
    print("(0 attendu : tout renvoi doit tomber sur un sommet de la partie)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "--preuve":
        cmd_preuve()
    else:
        cmd_profil(int(a[0], 0))
