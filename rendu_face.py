"""Rend un OBJ de personnage vu **de face**, avec ses textures, sans Blender.

Ecrit le 2026-10-21. `rendu_dessus.py` projette sur le plan XZ (vue de dessus),
ce qui ne dit rien de la silhouette d'un combattant debout. Ici la projection
est orthographique sur le plan XY, la profondeur est Z, et chaque pixel est
echantillonne dans la texture du materiau de sa face (`map_Kd` du .mtl).

Aucune dependance : le lecteur PNG est celui de `retrouver.py`, l'ecrivain
celui de `textures_dc.py`.

Usage :
    py -3 rendu_face.py <fichier.obj> [--cote 900] [--dos] [--cote-gauche]
                                      [--alpha] [--sortie <x.png>]
"""

import math
import pathlib
import sys

ICI = pathlib.Path(__file__).parent
sys.path.insert(0, str(ICI))
import textures_dc as T
import retrouver as R


def lit_mtl(chemin):
    """newmtl -> chemin de map_Kd."""
    m, courant = {}, None
    p = pathlib.Path(chemin)
    if not p.exists():
        return m
    for ln in open(p, encoding="ascii", errors="replace"):
        q = ln.split()
        if not q:
            continue
        if q[0] == "newmtl":
            courant = q[1]
        elif q[0] == "map_Kd" and courant:
            m.setdefault(courant, p.parent / q[-1])
    return m


def lit_obj(chemin):
    V, VT, F = [], [], []
    mtl = {}
    courant = None
    base = pathlib.Path(chemin).parent
    for ln in open(chemin, encoding="ascii", errors="replace"):
        q = ln.split()
        if not q:
            continue
        if q[0] == "v":
            V.append((float(q[1]), float(q[2]), float(q[3])))
        elif q[0] == "vt":
            VT.append((float(q[1]), float(q[2])))
        elif q[0] == "mtllib":
            mtl = lit_mtl(base / q[1])
        elif q[0] == "usemtl":
            courant = q[1]
        elif q[0] == "f":
            idx, uv = [], []
            for part in q[1:4]:
                c = part.split("/")
                idx.append(int(c[0]) - 1)
                uv.append(int(c[1]) - 1 if len(c) > 1 and c[1] else -1)
            F.append((idx, uv, courant))
    return V, VT, F, mtl


def charge_textures(mtl):
    tex = {}
    for nom, chemin in mtl.items():
        try:
            tex[nom] = R.lit_png(chemin)
        except Exception:
            pass
    return tex


def rends(V, VT, F, tex, cote, axe="face", avec_alpha=False):
    n = cote
    img = [(18, 18, 22)] * (n * n)
    prof = [1e30] * (n * n)

    # cadrage sur la boite englobante, avec une marge
    if axe == "cote":
        h, w_, d = 2, 1, 0           # X en profondeur
    else:
        h, w_, d = 1, 0, 2           # vue de face / de dos : X horizontal, Y vertical
    hs = [v[h] for v in V]
    ws = [v[w_] for v in V]
    cy, cx = (max(hs) + min(hs)) / 2, (max(ws) + min(ws)) / 2
    etendue = max(max(hs) - min(hs), max(ws) - min(ws)) / 2 * 1.08 or 1.0
    sens = -1.0 if axe == "dos" else 1.0

    def ecran(p):
        x = (sens * (p[w_] - cx) + etendue) / (2 * etendue) * (n - 1)
        y = (etendue - (p[h] - cy)) / (2 * etendue) * (n - 1)   # Y vers le haut
        return x, y

    for idx, uv, nom in F:
        p = [V[i] for i in idx]
        e = [ecran(q) for q in p]
        u = [p[1][j] - p[0][j] for j in range(3)]
        w2 = [p[2][j] - p[0][j] for j in range(3)]
        nz = [u[1] * w2[2] - u[2] * w2[1], u[2] * w2[0] - u[0] * w2[2],
              u[0] * w2[1] - u[1] * w2[0]]
        ln_ = math.sqrt(sum(c * c for c in nz)) or 1.0
        ombre = 0.55 + 0.45 * abs(nz[d] / ln_)
        t = tex.get(nom)
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
                z = a * p[0][d] + b * p[1][d] + c * p[2][d]
                z = -z if axe != "dos" else z            # le plus proche gagne
                k = py * n + px
                if z >= prof[k]:
                    continue
                col = (200, 200, 205)
                if t and uv[0] >= 0 and uv[1] >= 0 and uv[2] >= 0:
                    tw, th, tp = t
                    uu = a * VT[uv[0]][0] + b * VT[uv[1]][0] + c * VT[uv[2]][0]
                    vv = a * VT[uv[0]][1] + b * VT[uv[1]][1] + c * VT[uv[2]][1]
                    sx = int(uu % 1.0 * tw) % tw
                    sy = int((1.0 - vv % 1.0) * th) % th
                    r, g, bl, al = tp[sy * tw + sx]
                    if avec_alpha and al < 128:
                        continue
                    col = (r, g, bl)
                prof[k] = z
                img[k] = tuple(min(255, int(v * ombre)) for v in col)
    return img


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    obj = args[0]
    cote = int(sys.argv[sys.argv.index("--cote") + 1]) if "--cote" in sys.argv else 900
    axe = "dos" if "--dos" in sys.argv else ("cote" if "--cote-gauche" in sys.argv else "face")
    V, VT, F, mtl = lit_obj(obj)
    tex = charge_textures(mtl)
    img = rends(V, VT, F, tex, cote, axe, "--alpha" in sys.argv)
    if "--sortie" in sys.argv:
        s = pathlib.Path(sys.argv[sys.argv.index("--sortie") + 1])
    else:
        p = pathlib.Path(obj)
        s = p.with_name(p.stem + f"_{axe}.png")
    T.png(s, cote, cote, [c + (255,) for c in img])
    print(f"{len(V)} sommets, {len(F)} triangles, {len(tex)} textures chargees -> {s}")
