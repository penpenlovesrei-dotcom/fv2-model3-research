"""Rend un nuage de points des modeles Dreamcast, pour les voir sans decodeur.

Le format de modele de `MDL_DAT.AFS` n'est pas decode. Mais il n'a pas besoin
de l'etre pour qu'on voie de quoi un modele a l'air : ses positions sont des
flottants petit-boutiens contigus, et il suffit de ramasser les suites de
flottants plausibles par triplets et de les projeter. La methode est celle que
`celsowm/vf3-decomp` valide sur le format POL de Virtua Fighter 3tb Dreamcast
(`docs/formats/POL.md` : *projected point cloud shows the crater-dome stage
silhouette*).

**C'est bruite, et il faut le savoir** : le balayage ramasse aussi les
coordonnees de texture et les normales, qui se melangent aux positions. Ca
suffit a reconnaitre une silhouette, pas a mesurer. Pour une extraction propre
il faudra passer par les compteurs des en-tetes de partie -- un enregistrement
porte sa boite englobante puis des compteurs (`afs.py profil` les montre).

Projection par defaut : **XZ**, le plan du sol. Les deux axes sont mis a
l'echelle par les percentiles 2 et 98, pour qu'un point aberrant ne reduise pas
tout le reste a un pixel.

L'ecrivain PNG est en bibliotheque standard : aucune dependance.

Usage :
    py -3 nuage.py <archive.afs> [premier] [dernier]      -> nuages/
    py -3 nuage.py <archive.afs> 0 15 --plan xy
"""

import math
import pathlib
import struct
import sys
import zlib

ICI = pathlib.Path(__file__).parent
COTE = 320
PLANS = {"xz": (0, 2), "xy": (0, 1), "zy": (2, 1)}


def png(chemin, largeur, hauteur, rgb):
    """Ecrit un PNG couleur 8 bits sans filtre, en bibliotheque standard."""
    brut = b"".join(b"\x00" + rgb[y * largeur * 3:(y + 1) * largeur * 3]
                    for y in range(hauteur))

    def bloc(type_, data):
        c = type_ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    out = b"\x89PNG\r\n\x1a\n"
    out += bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0))
    out += bloc(b"IDAT", zlib.compress(brut, 9))
    out += bloc(b"IEND", b"")
    pathlib.Path(chemin).write_bytes(out)


def points(blob):
    """Suites de flottants plausibles, prises par triplets."""
    pts = []
    suite = []
    for p in range(0, len(blob) - 3, 4):
        v = struct.unpack_from("<f", blob, p)[0]
        if v == 0.0 or (math.isfinite(v) and 1e-4 < abs(v) < 1e4):
            suite.append(v)
            continue
        if len(suite) >= 9:
            pts += [suite[k:k + 3] for k in range(0, len(suite) - 2, 3)]
        suite = []
    if len(suite) >= 9:
        pts += [suite[k:k + 3] for k in range(0, len(suite) - 2, 3)]
    return pts


def borne(valeurs):
    v = sorted(valeurs)
    bas, haut = v[int(len(v) * 0.02)], v[int(len(v) * 0.98) - 1]
    return (bas, haut + 1.0) if haut - bas < 1e-6 else (bas, haut)


def rends(pts, chemin, axes):
    a, b = axes
    x0, x1 = borne([p[a] for p in pts])
    y0, y1 = borne([p[b] for p in pts])
    tampon = bytearray(b"\x10" * (COTE * COTE * 3))
    for p in pts:
        px = int((p[a] - x0) / (x1 - x0) * (COTE - 1))
        py = int((p[b] - y0) / (y1 - y0) * (COTE - 1))
        if 0 <= px < COTE and 0 <= py < COTE:
            k = (py * COTE + px) * 3
            tampon[k] = min(255, tampon[k] + 60)
            tampon[k + 1] = min(255, tampon[k + 1] + 90)
            tampon[k + 2] = min(255, tampon[k + 2] + 60)
    png(chemin, COTE, COTE, bytes(tampon))
    return (x0, x1, y0, y1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    plan = "xz"
    if "--plan" in sys.argv:
        plan = sys.argv[sys.argv.index("--plan") + 1]
    if plan not in PLANS:
        raise SystemExit(f"plan inconnu : {plan} (xz, xy, zy)")
    archive = pathlib.Path(args[0])
    premier = int(args[1]) if len(args) > 1 else 0
    dernier = int(args[2]) if len(args) > 2 else 15
    d = archive.read_bytes()
    if d[:4] != b"AFS\x00":
        raise SystemExit(f"{archive} ne commence pas par AFS\\0")
    n = struct.unpack_from("<I", d, 4)[0]
    ent = [struct.unpack_from("<II", d, 8 + i * 8) for i in range(n)]
    dossier = ICI / "nuages"
    dossier.mkdir(exist_ok=True)
    base = archive.stem
    for i in range(premier, min(dernier + 1, n)):
        o, s = ent[i]
        if s == 0:
            print(f"[{i:3}] entree vide")
            continue
        pts = points(d[o:o + s])
        if not pts:
            print(f"[{i:3}] aucun point")
            continue
        sortie = dossier / f"{base}_{i:03}_{plan}.png"
        x0, x1, y0, y1 = rends(pts, sortie, PLANS[plan])
        print(f"[{i:3}] {len(pts):>7} points  "
              f"{plan[0]}[{x0:9.2f} {x1:9.2f}] {plan[1]}[{y0:9.2f} {y1:9.2f}]  "
              f"-> {sortie.relative_to(ICI)}")
