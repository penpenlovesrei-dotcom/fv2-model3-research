"""Referme les petits trous d'un OBJ, en suivant ses aretes de bord.

Une arete qui n'appartient qu'a UN seul triangle borde un trou : c'est la
definition, et elle se mesure sans rien supposer. On assemble ces aretes en
boucles fermees, et toute boucle assez petite est remplie par un eventail de
triangles.

RECONSTRUCTION : les faces ajoutees n'etaient pas dans les donnees. Elles ne
font qu'utiliser des sommets existants pour refermer un contour qui se referme
deja geometriquement -- on ne cree aucun sommet, et une boucle trop grande ou
non plane est laissee ouverte.

Garde-fous :
  - seules les boucles de 3 a `cotes_max` sommets sont remplies ;
  - leur plus grande arete doit rester sous `arete_max`, pour ne pas reboucher
    le contour exterieur de la piece ;
  - la boucle doit etre a peu pres plane (epaisseur sous `epaisseur_max`).

Usage :
    py -3 fermer_trous.py <fichier.obj> [--cotes 8] [--arete 2.0]
"""

import collections
import pathlib
import sys


def lit(chemin):
    lignes = pathlib.Path(chemin).read_text(encoding="ascii", errors="replace").splitlines()
    V, F = [], []
    for ln in lignes:
        if ln.startswith("v "):
            V.append(tuple(float(x) for x in ln.split()[1:4]))
        elif ln.startswith("f "):
            F.append([int(p.split("/")[0]) - 1 for p in ln.split()[1:4]])
    return lignes, V, F


def boucles(V, F, soude=0.01):
    """Les boucles d'aretes de bord, en indices de sommets soudes."""
    def cle(i):
        v = V[i]
        return (round(v[0] / soude), round(v[1] / soude), round(v[2] / soude))

    rep = {}
    for i in range(len(V)):
        rep.setdefault(cle(i), i)
    soud = [rep[cle(i)] for i in range(len(V))]

    compte = collections.Counter()
    for f in F:
        for i in range(3):
            a, b = soud[f[i]], soud[f[(i + 1) % 3]]
            compte[tuple(sorted((a, b)))] += 1
    bords = [e for e, n in compte.items() if n == 1]

    voisins = collections.defaultdict(list)
    for a, b in bords:
        voisins[a].append(b)
        voisins[b].append(a)

    vus = set()
    out = []
    for depart in list(voisins):
        if depart in vus:
            continue
        boucle = [depart]
        vus.add(depart)
        cur, prec = depart, None
        while True:
            suite = [x for x in voisins[cur] if x != prec and x not in vus]
            if not suite:
                if depart in voisins[cur] and len(boucle) >= 3:
                    out.append(boucle)
                break
            prec, cur = cur, suite[0]
            vus.add(cur)
            boucle.append(cur)
    return out


def remplit(chemin, cotes_max=8, arete_max=2.0, epaisseur_max=0.35, symetrie=True):
    lignes, V, F = lit(chemin)
    bcl = boucles(V, F)
    ajouts = []
    remplies = 0
    for b in bcl:
        if not (3 <= len(b) <= cotes_max):
            continue
        pts = [V[i] for i in b]
        lon = max(sum((pts[i][j] - pts[(i + 1) % len(pts)][j]) ** 2 for j in range(3)) ** 0.5
                  for i in range(len(pts)))
        if lon > arete_max:
            continue
        ep = max(p[1] for p in pts) - min(p[1] for p in pts)
        if ep > epaisseur_max:
            continue
        for k in range(1, len(b) - 1):
            ajouts.append((b[0] + 1, b[k] + 1, b[k + 1] + 1))
        remplies += 1
    # Le ring est symetrique d'ordre 4 : une boucle refermee dans un quadrant
    # doit l'etre dans les quatre. Les sommets tournes existent deja (symetrie
    # des sommets a 100 %), on ne fait donc que retrouver leur indice.
    if ajouts and symetrie:
        import math
        index = {}
        for i, v in enumerate(V):
            index.setdefault((round(v[0] / 0.01), round(v[1] / 0.01),
                              round(v[2] / 0.01)), i)
        copies, manques = [], 0
        for tour in (1, 2, 3):
            a = math.radians(90 * tour)
            ca, sa = math.cos(a), math.sin(a)
            for tri in ajouts:
                neuf = []
                for s in tri:
                    v = V[s - 1]
                    r = (v[0] * ca - v[2] * sa, v[1], v[0] * sa + v[2] * ca)
                    # Les copies issues de la symetrie portent un decalage de
                    # 2 millimes d'unite par tour (voir geometrie_dc) : on
                    # cherche donc aussi aux hauteurs voisines.
                    j = None
                    for e in (0.0, -0.002, -0.004, -0.006, 0.002, 0.004, 0.006):
                        j = index.get((round(r[0] / 0.01), round((r[1] + e) / 0.01),
                                       round(r[2] / 0.01)))
                        if j is not None:
                            break
                    if j is None:
                        neuf = None
                        break
                    neuf.append(j + 1)
                if neuf:
                    copies.append(tuple(neuf))
                else:
                    manques += 1
        ajouts += copies
        print(f"   symetrie : {len(copies)} triangles ajoutes aux trois autres "
              f"quadrants, {manques} sans sommet correspondant")
    if ajouts:
        lignes.append("usemtl texture_00")
        lignes += [f"f {a}/{a}/{a} {c}/{c}/{c} {d}/{d}/{d}" for a, c, d in ajouts]
        pathlib.Path(chemin).write_text("\n".join(lignes) + "\n", encoding="ascii")
    print(f"{len(bcl)} boucles de bord, {remplies} remplies, {len(ajouts)} triangles ajoutes")
    return remplies, len(ajouts)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    cotes = int(sys.argv[sys.argv.index("--cotes") + 1]) if "--cotes" in sys.argv else 8
    arete = float(sys.argv[sys.argv.index("--arete") + 1]) if "--arete" in sys.argv else 2.0
    remplit(args[0], cotes, arete, symetrie="--sans-symetrie" not in sys.argv)
