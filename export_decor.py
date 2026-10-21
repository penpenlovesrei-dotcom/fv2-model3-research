"""Sort un decor Dreamcast en OBJ + MTL + textures, par la lecture exacte.

Rien n'est reconstitue ici. Pas de symetrie d'ordre 4, pas de replication de
quart, pas de fermeture de boucles d'aretes, pas de rejet de prototypes : ces
rustines compensaient les 3,2 % de rubans que l'ancien lecteur ratait, et
`rubans_dc.py` ne les rate plus. Ce que ce script ecrit est ce que le fichier
contient, et seulement ca.

La correspondance decor -> entree vient de la table de ressources de scene du
jeu (0x8C118294, rang = index de la table de decors), recoupee par la mesure
des textures. Voir le README.

Usage :
    py -3 export_decor.py TEST                -> export_decor/TEST/
    py -3 export_decor.py 75                  par indice MDL
    py -3 export_decor.py --tous              les treize decors
    py -3 export_decor.py TEST --sans-texture
"""

import pathlib
import struct
import sys

ICI = pathlib.Path(__file__).parent
sys.path.insert(0, str(ICI))
import rubans_dc as R
import textures_dc as T

NL = chr(10)

# rang dans la table de ressources de scene -> (nom interne, MDL, TEX)
DECORS = [
    ("TEST", 75, 112), ("WESTERN", 76, 113), ("AC_CARRIER", 0, 0),
    ("ROOM_00", 60, 89), ("GREAT_BM", 35, 58), ("FURNACE", 34, 56),
    ("STORE", 68, 100), ("HANGAR", 39, 62), ("CAPSULE", 22, 23),
    ("DAM", 26, 33), ("TOWER", 74, 111), ("BUILDING", 19, 20),
    ("MUSEUM", 55, 78),
]
PAR_NOM = {n: (m, t) for n, m, t in DECORS}
PAR_MDL = {m: (n, t) for n, m, t in DECORS}


def textures(dossier, indice_mdl, prefixe):
    """Ecrit les textures de l'entree et rend [(nom, transparente)]."""
    tex, k, liste = T.textures_de_lentree(indice_mdl)
    if k is None:
        return []
    to = T.afs("TEX_DAT.AFS")[1][k][0]
    noms = []
    for i, d in enumerate(liste):
        n = T.taille_stockee(d["w"], d["h"], d["stockage"])
        brut = tex[to + d["off"]: to + d["off"] + n]
        nom = "%s_tex%02d.png" % (prefixe, i)
        transparente = False
        if len(brut) == n:
            pix = T.decode(brut, d)
            T.png(dossier / nom, d["w"], d["h"], pix)
            transparente = sum(1 for q in pix if q[3] < 255) * 100 > len(pix)
        noms.append((nom, transparente))
    return noms


def ecris(dossier, nom, indice_mdl, avec_textures=True):
    dossier.mkdir(parents=True, exist_ok=True)
    b, parts = R.entree(indice_mdl)
    noms_tex = textures(dossier, indice_mdl, nom) if avec_textures else []

    # un sommet OBJ par (partie, offset) : deux parties peuvent partager un
    # offset sans partager ses coordonnees de texture
    lignes_v, lignes_vt = [], []
    index = {}
    faces_par_mat = {}
    exacts = 0
    for num, (en, rub, som) in enumerate(parts):
        if en["exact"]:
            exacts += 1
        mat = en["index_texture"]
        for code, suite in rub:
            tris = R.triangles(suite)
            if not tris:
                continue
            for tri in tris:
                coins = []
                for off in tri:
                    cle = (num, off)
                    if cle not in index:
                        x, y, z, u, v = som[off]
                        lignes_v.append("v %.6f %.6f %.6f" % (x, y, z))
                        # l'axe V des textures est inverse par rapport a OBJ
                        lignes_vt.append("vt %.6f %.6f" % (u, 1.0 - v))
                        index[cle] = len(lignes_v)
                    coins.append(index[cle])
                # une face par triangle, memes indices pour v et vt
                faces_par_mat.setdefault(mat, []).append(coins)

    chemin = dossier / ("%s.obj" % nom)
    mtl = "%s.mtl" % nom
    with open(chemin, "w", encoding="ascii", newline=NL) as f:
        f.write("# %s, entree MDL %d de MDL_DAT.AFS%s" % (nom, indice_mdl, NL))
        f.write("# lecture exacte : %d/%d parties pavees a l'octet pres%s"
                % (exacts, len(parts), NL))
        f.write("mtllib %s%s" % (mtl, NL))
        f.write(NL.join(lignes_v) + NL)
        f.write(NL.join(lignes_vt) + NL)
        nf = 0
        for mat in sorted(faces_par_mat):
            f.write("usemtl tex%02d%s" % (mat, NL))
            f.write("g %s_tex%02d%s" % (nom, mat, NL))
            for coins in faces_par_mat[mat]:
                f.write("f " + " ".join("%d/%d" % (i, i) for i in coins) + NL)
                nf += 1

    with open(dossier / mtl, "w", encoding="ascii", newline=NL) as f:
        for mat in sorted(faces_par_mat):
            f.write("newmtl tex%02d%s" % (mat, NL))
            f.write("Kd 1 1 1%s" % NL)
            if mat < len(noms_tex):
                nom_png, transp = noms_tex[mat]
                f.write("map_Kd %s%s" % (nom_png, NL))
                if transp:
                    f.write("map_d %s%s" % (nom_png, NL))
            f.write(NL)

    print("%-12s MDL %2d : %d partie(s) toutes exactes, %d sommet(s), %d face(s)"
          % (nom, indice_mdl, len(parts), len(lignes_v), nf))
    print("             %s" % chemin)
    return chemin


def main(args):
    avec = "--sans-texture" not in args
    args = [a for a in args if not a.startswith("--")]
    base = ICI / "export_decor"
    cibles = []
    if "--tous" in sys.argv:
        cibles = [(n, m) for n, m, _ in DECORS]
    elif not args:
        raise SystemExit(__doc__)
    else:
        a = args[0]
        if a in PAR_NOM:
            cibles = [(a, PAR_NOM[a][0])]
        else:
            i = int(a, 0)
            cibles = [(PAR_MDL.get(i, ("MDL%02d" % i,))[0], i)]
    for nom, mdl in cibles:
        ecris(base / nom, nom, mdl, avec)


if __name__ == "__main__":
    main(sys.argv[1:])
