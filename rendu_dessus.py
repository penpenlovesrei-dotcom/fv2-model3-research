"""Rend un OBJ vu de dessus, faces pleines, sans Blender.

Sert a juger une extraction sans quitter la ligne de commande : rasterisation
de triangles avec tampon de profondeur sur l'axe Y, projection orthographique
sur le plan XZ. Deux modes :

  gris    chaque face eclairee par sa normale geometrique, comme un mode solide
  pieces  une couleur par PIECE, pour voir d'un coup laquelle est fautive

Aucune dependance : l'ecrivain PNG est celui de textures_dc.

Usage :
    py -3 rendu_dessus.py <fichier.obj> [--etendue 9] [--pieces] [--cote 900]
"""

import math
import pathlib
import struct
import sys

ICI = pathlib.Path(__file__).parent
sys.path.insert(0, str(ICI))
import textures_dc as T

COULEURS = [(230, 80, 80), (80, 200, 110), (90, 130, 240), (235, 190, 70),
            (200, 100, 220), (70, 210, 215), (240, 140, 60), (150, 150, 240),
            (120, 220, 150), (220, 120, 160), (170, 200, 80), (100, 170, 230)]


def lit_obj(chemin):
    """Rend (sommets, [(triangle, indice de groupe)]), un groupe par usemtl."""
    V, F = [], []
    groupe = 0
    noms = []
    for ln in open(chemin, encoding="ascii", errors="replace"):
        if ln.startswith("v "):
            V.append(tuple(float(x) for x in ln.split()[1:4]))
        elif ln.startswith("usemtl "):
            nom = ln.split()[1]
            if nom not in noms:
                noms.append(nom)
            groupe = noms.index(nom)
        elif ln.startswith("f "):
            idx = [int(p.split("/")[0]) - 1 for p in ln.split()[1:4]]
            F.append((idx, groupe))
    return V, F, noms


def rends(V, F, cote, etendue, par_piece, par_face=False, centre=(0.0, 0.0)):
    n = cote
    fond = (14, 14, 16)
    img = [fond] * (n * n)
    prof = [1e30] * (n * n)

    def ecran(p):
        x = (p[0] - centre[0] + etendue) / (2 * etendue) * (n - 1)
        y = (p[2] - centre[1] + etendue) / (2 * etendue) * (n - 1)
        return x, y

    for nf, (idx, groupe) in enumerate(F):
        p = [V[i] for i in idx]
        if all(abs(q[0] - centre[0]) > etendue or abs(q[2] - centre[1]) > etendue
               for q in p):
            continue
        # normale geometrique, pour l'eclairage
        u = [p[1][j] - p[0][j] for j in range(3)]
        w = [p[2][j] - p[0][j] for j in range(3)]
        nz = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2],
              u[0] * w[1] - u[1] * w[0]]
        ln_ = math.sqrt(sum(c * c for c in nz)) or 1.0
        face = abs(nz[1] / ln_)                       # vu de dessus
        if par_face:
            h = (nf * 2654435761) & 0xFFFFFF
            base = (80 + (h & 0x7F), 80 + ((h >> 8) & 0x7F), 80 + ((h >> 16) & 0x7F))
            col = tuple(int(c * (0.45 + 0.55 * face)) for c in base)
        elif par_piece:
            base = COULEURS[groupe % len(COULEURS)]
            col = tuple(int(c * (0.35 + 0.65 * face)) for c in base)
        else:
            t = int(60 + 175 * face)
            col = (t, t, t)
        e = [ecran(q) for q in p]
        x0 = max(0, int(min(q[0] for q in e)))
        x1 = min(n - 1, int(max(q[0] for q in e)) + 1)
        y0 = max(0, int(min(q[1] for q in e)))
        y1 = min(n - 1, int(max(q[1] for q in e)) + 1)
        det = ((e[1][1] - e[2][1]) * (e[0][0] - e[2][0])
               + (e[2][0] - e[1][0]) * (e[0][1] - e[2][1]))
        if abs(det) < 1e-9:
            continue
        for py in range(y0, y1 + 1):
            for px in range(x0, x1 + 1):
                a = ((e[1][1] - e[2][1]) * (px - e[2][0])
                     + (e[2][0] - e[1][0]) * (py - e[2][1])) / det
                b = ((e[2][1] - e[0][1]) * (px - e[2][0])
                     + (e[0][0] - e[2][0]) * (py - e[2][1])) / det
                c = 1 - a - b
                if a < -1e-6 or b < -1e-6 or c < -1e-6:
                    continue
                y = a * p[0][1] + b * p[1][1] + c * p[2][1]
                k = py * n + px
                if -y < prof[k]:                      # Y croissant = vers le haut
                    prof[k] = -y
                    img[k] = col
    return img


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    obj = args[0]
    etendue = 9.0
    if "--etendue" in sys.argv:
        etendue = float(sys.argv[sys.argv.index("--etendue") + 1])
    cote = 900
    if "--cote" in sys.argv:
        cote = int(sys.argv[sys.argv.index("--cote") + 1])
    par_piece = "--pieces" in sys.argv
    par_face = "--faces" in sys.argv
    centre = (0.0, 0.0)
    if "--centre" in sys.argv:
        i = sys.argv.index("--centre")
        centre = (float(sys.argv[i + 1]), float(sys.argv[i + 2]))
    V, F, noms = lit_obj(obj)
    img = rends(V, F, cote, etendue, par_piece, par_face, centre)
    s = pathlib.Path(obj).with_name(pathlib.Path(obj).stem
                                    + ("_faces" if par_face else
                                       "_pieces" if par_piece else "_solide") + ".png")
    T.png(s, cote, cote, [c + (255,) for c in img])
    print(f"{len(V)} sommets, {len(F)} triangles, {len(noms)} groupes -> {s}")
    if par_piece:
        for i, nm in enumerate(noms):
            c = COULEURS[i % len(COULEURS)]
            print(f"   {nm} : couleur rgb{c}")
