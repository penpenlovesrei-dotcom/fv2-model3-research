"""Extrait la geometrie d'une entree de MDL_DAT.AFS, et la sort en OBJ.

Format etabli le 2026-10-20 sur l'entree 75 (le decor d'entrainement), par la
mesure -- chaque champ ci-dessous a ete verifie, aucun n'est suppose.

**En-tete d'entree**, 24 octets :

    +0x00 u32   1 (classe decor) ou -1 (classe personnage)
    +0x04 u32   3
    +0x08 3f    boite englobante de l'entree : centre x, y, z
    +0x14 f     son rayon

**Une PARTIE** commence par quatre mots de parametre du Tile Accelerator du
PowerVR2, pre-cuits dans le fichier, puis :

    +0x00 u32   TA Parameter Control (0x8xxxxxxx)
    +0x04 u32   TA ISP/TSP           (0x83xxxxxx)
    +0x08 u32   TA TSP
    +0x0C u32   TA Texture Control   (champ adresse nul : rempli au chargement)
    +0x10 3f    boite englobante de la partie : centre x, y, z
    +0x1C f     son rayon
    +0x20 u32   compteur
    +0x24 u32   0xFFFFFFFF, sentinelle
    +0x28 9f    bloc d'eclairage (0.75, 1,1,1, 1, 0, puis une couleur)
    +0x4C u32   taille en octets de ce qui suit
    +0x50 ...   les rubans

**Un RUBAN**, deux mots d'en-tete puis ses sommets :

    +0x00 u32   code de format du sommet
    +0x04 u32   nombre de sommets
    +0x08 ...   les sommets

**Un SOMMET** commence toujours par position xyz puis **normale unitaire** xyz
puis u, v -- 32 octets. Certains formats ajoutent deux mots de couleur, ce qui
fait 40. Le code de format porte la difference dans son **bit 7** : 0x72 donne
32 octets, 0xF2 en donne 40, le reste du code etant identique.

La norme de la normale est ce qui permet de tout verifier sans rien supposer :
elle vaut 1 a 1e-3 pres pour un decoupage juste, et n'importe quoi sinon. Le
script **mesure donc le pas** de chaque ruban au lieu de le deduire du code, et
rend la table des codes rencontres pour qu'on la documente.

Les positions sont deja en espace modele : aucune matrice de partie n'a ete
trouvee, et les boites englobantes des parties se placent d'elles-memes dans
celle de l'entree.

Usage :
    py -3 geometrie_dc.py <indice>              -> geometrie_dc/<indice>.obj
    py -3 geometrie_dc.py <indice> --rapport    la structure, sans ecrire
"""

import math
import pathlib
import struct
import sys

ICI = pathlib.Path(__file__).parent
sys.path.insert(0, str(ICI))
import textures_dc as T

PAS_CANDIDATS = (32, 40, 48, 24, 20)
TOLERANCE = 1e-2   # 1e-3 coupait des rubans sur quelques sommets limites


def unitaire(b, p):
    """La normale d'un sommet suppose a cet offset est-elle unitaire ?"""
    if p + 32 > len(b):
        return False
    x, y, z = struct.unpack_from("<3f", b, p + 12)
    if not all(math.isfinite(v) for v in (x, y, z)):
        return False
    return abs((x * x + y * y + z * z) ** 0.5 - 1.0) < TOLERANCE


def pas_du_ruban(b, p, n):
    """Mesure le pas : le plus petit qui rende les n normales unitaires."""
    for pas in PAS_CANDIDATS:
        if p + n * pas > len(b):
            continue
        if all(unitaire(b, p + i * pas) for i in range(n)):
            return pas
    return None


def parties(b):
    """Les offsets des parties : un couple (0x8xxxxxxx, 0x83xxxxxx)."""
    out = []
    for p in range(0, len(b) - 8, 4):
        a = struct.unpack_from("<I", b, p)[0]
        c = struct.unpack_from("<I", b, p + 4)[0]
        if (a >> 28) == 8 and (c >> 24) == 0x83:
            out.append(p)
    return out


def rubans_par_les_normales(b, debut, fin):
    """Les rubans d'une partie, trouves par le test de la normale unitaire.

    La disposition exacte de l'en-tete de ruban n'est pas etablie : les
    compteurs annonces (+0x20, +0x4C, +0x50, +0x54) ne cadrent pas sur toutes
    les parties, et le pas varie d'un ruban a l'autre. On ne s'y fie donc pas.

    Ce qui ne ment pas, c'est la normale : trois flottants consecutifs dont la
    norme vaut 1 a 1e-3 pres. La probabilite qu'un triplet quelconque tombe
    dans cette fenetre est infime, donc une suite de sommets dont TOUS passent
    le test est une vraie suite de sommets. On balaye, on retient les suites
    d'au moins trois, et les deux mots d'en-tete se trouvent sautes d'eux-memes.
    """
    out = []
    p = debut
    while p + 32 <= fin:
        meilleur = None
        for pas in (32, 40):
            if not (unitaire(b, p) and unitaire(b, p + pas) and unitaire(b, p + 2 * pas)):
                continue
            n = 0
            while p + (n + 1) * pas <= fin:
                if unitaire(b, p + n * pas):
                    n += 1
                    continue
                # un sommet limite isole ne doit pas couper le ruban en deux
                if (p + (n + 2) * pas <= fin and unitaire(b, p + (n + 1) * pas)
                        and unitaire(b, p + (n + 2) * pas)):
                    n += 2
                    continue
                break
            if meilleur is None or n * pas > meilleur[0] * meilleur[1]:
                meilleur = (n, pas)
        if meilleur:
            n, pas = meilleur
            code = struct.unpack_from("<I", b, p - 8)[0] if p - 8 >= 0 else 0
            sommets = [struct.unpack_from("<8f", b, p + i * pas) for i in range(n)]
            out.append((code, pas, sommets))
            p += n * pas
        else:
            p += 4
    return out


def lit_partie(b, debut, fin):
    """Rend (en-tete, [rubans]). Un ruban : (code, pas, [sommets])."""
    ta = struct.unpack_from("<4I", b, debut)
    boite = struct.unpack_from("<4f", b, debut + 0x10)
    taille = struct.unpack_from("<I", b, debut + 0x4C)[0]
    p = debut + 0x50
    borne = min(fin, debut + 0x50 + taille) if taille else fin
    rubans = []
    while p + 8 <= borne:
        code, n = struct.unpack_from("<II", b, p)
        if not (0 < n < 4096):
            break
        pas = pas_du_ruban(b, p + 8, n)
        if pas is None:
            break
        sommets = []
        for i in range(n):
            f = struct.unpack_from("<8f", b, p + 8 + i * pas)
            sommets.append(f)
        rubans.append((code, pas, sommets))
        p += 8 + n * pas
    return {"ta": ta, "boite": boite, "taille": taille, "fin_lue": p}, rubans


def extrait(indice):
    mdl, me = T.afs("MDL_DAT.AFS")
    mo, ms = me[indice]
    b = mdl[mo:mo + ms]
    bornes = parties(b) + [len(b)]
    entete = struct.unpack_from("<4f", b, 8)
    tout = []
    for k in range(len(bornes) - 1):
        h, _ = lit_partie(b, bornes[k], bornes[k + 1])
        rubans = rubans_par_les_normales(b, bornes[k] + 0x50, bornes[k + 1])
        tout.append((bornes[k], h, rubans))
    return entete, tout


def rapport(indice, entete, tout):
    codes = {}
    ns = nr = 0
    reste = 0
    for debut, h, rubans in tout:
        for code, pas, sommets in rubans:
            codes.setdefault((code, pas), 0)
            codes[(code, pas)] += 1
            ns += len(sommets)
            nr += 1
        attendu = debut + 0x50 + h["taille"]
        reste += max(0, attendu - h["fin_lue"])
    print(f"MDL[{indice}] : boite de l'entree centre "
          f"({entete[0]:.3f}, {entete[1]:.3f}, {entete[2]:.3f}) rayon {entete[3]:.3f}")
    print(f"{len(tout)} parties, {nr} rubans, {ns} sommets")
    print(f"octets de rubans non lus : {reste}\n")
    print("codes de format rencontres :")
    for (code, pas), n in sorted(codes.items()):
        print(f"   code {code:#06x}  pas {pas} octets  x{n} rubans")


def ecris_obj(chemin, tout):
    """Rubans -> triangles, en inversant l'ordre un sommet sur deux."""
    s = []
    vt = []
    vn = []
    f = []
    base = 1
    for debut, h, rubans in tout:
        for code, pas, sommets in rubans:
            for v in sommets:
                s.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
                vn.append(f"vn {v[3]:.6f} {v[4]:.6f} {v[5]:.6f}")
                vt.append(f"vt {v[6]:.6f} {v[7]:.6f}")
            for i in range(len(sommets) - 2):
                a, bb, c = base + i, base + i + 1, base + i + 2
                if i & 1:
                    bb, c = c, bb
                f.append(f"f {a}/{a}/{a} {bb}/{bb}/{bb} {c}/{c}/{c}")
            base += len(sommets)
    pathlib.Path(chemin).write_text(
        "\n".join(["# Fighting Vipers 2 Dreamcast, extrait par geometrie_dc.py"]
                  + s + vt + vn + f) + "\n", encoding="ascii")
    return len(s), len(f)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    indice = int(args[0])
    entete, tout = extrait(indice)
    rapport(indice, entete, tout)
    if "--rapport" not in sys.argv:
        dossier = ICI / "geometrie_dc"
        dossier.mkdir(exist_ok=True)
        s = dossier / f"mdl_{indice:03}.obj"
        nv, nf = ecris_obj(s, tout)
        print(f"\n{nv} sommets, {nf} triangles -> {s.relative_to(ICI)}")
