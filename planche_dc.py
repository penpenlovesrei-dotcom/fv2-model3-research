"""Planche d'une entree de TEX_DAT.AFS lue avec le tableau de descripteurs
d'une entree de MDL_DAT.AFS **donnee explicitement**.

Ecrit le 2026-10-21. `textures_dc.py planche` apparie par indice, ce qui est
faux au-dela de l'entree 15 ; ici l'appariement est un argument, pour pouvoir
regarder une entree de personnage avec la bonne entree de textures.

Les PNG vont dans `textures_dc/` comme ceux de `textures_dc.py`.

Usage :
    py -3 planche_dc.py <mdl_i> <tex_k> [cote] [colonnes]
    py -3 planche_dc.py --table <mdl_i>          le tableau, avec un plafond large
"""

import pathlib
import sys

import textures_dc as T

ICI = pathlib.Path(__file__).parent


def table_de(mdl, me, i, plafond):
    mo, ms = me[i]
    return T.descripteurs(mdl[mo:mo + ms], plafond)


def main(i, k, cote=96, colonnes=8):
    mdl, me = T.afs("MDL_DAT.AFS")
    tex, te = T.afs("TEX_DAT.AFS")
    plafond = max(s for _, s in te)
    off, liste = table_de(mdl, me, i, plafond)
    if not liste:
        raise SystemExit(f"MDL[{i}] : aucun descripteur")
    to, ts = te[k]
    total = sum(T.taille_stockee(d["w"], d["h"], d["stockage"]) for d in liste)
    dossier = ICI / "textures_dc"
    dossier.mkdir(exist_ok=True)
    W, H, pix = T.planche(liste, tex, to, cote, colonnes)
    s = dossier / f"planche_mdl{i:03}_tex{k:03}.png"
    T.png(s, W, H, pix)
    print(f"MDL[{i}] ({ms_de(me, i)} o, tableau @{off:#x}, {len(liste)} textures, "
          f"{total} o decrits)  x  TEX[{k}] ({ts} o)"
          f"{'  <- paving exact' if total == ts else ''}")
    print(f"  -> {s}")


def ms_de(me, i):
    return me[i][1]


if __name__ == "__main__":
    if sys.argv[1:2] == ["--png"]:
        # toutes les textures en taille native, dans textures_dc/mdlXXX_texYYY/
        i, k = int(sys.argv[2]), int(sys.argv[3])
        mdl, me = T.afs("MDL_DAT.AFS")
        tex, te = T.afs("TEX_DAT.AFS")
        plafond = max(s for _, s in te)
        off, liste = table_de(mdl, me, i, plafond)
        to, ts = te[k]
        dossier = ICI / "textures_dc" / f"mdl{i:03}_tex{k:03}"
        dossier.mkdir(parents=True, exist_ok=True)
        for n, d in enumerate(liste):
            taille = T.taille_stockee(d["w"], d["h"], d["stockage"])
            brut = tex[to + d["off"]: to + d["off"] + taille]
            if len(brut) < taille:
                continue
            pix = T.decode(brut, d, False)
            T.png(dossier / f"{n:03}_{d['w']}x{d['h']}.png", d["w"], d["h"], pix)
        print(f"{len(liste)} textures -> {dossier}")
    elif sys.argv[1:2] == ["--table"]:
        mdl, me = T.afs("MDL_DAT.AFS")
        tex, te = T.afs("TEX_DAT.AFS")
        plafond = max(s for _, s in te)
        i = int(sys.argv[2])
        off, liste = table_de(mdl, me, i, plafond)
        print(f"MDL[{i}] : tableau @{off:#x}, {len(liste)} descripteurs")
        for n, d in enumerate(liste):
            print(f"  [{n:3}] {d['w']:>4}x{d['h']:<4} pixel {d['pixel']} "
                  f"stockage {d['stockage']:#04x} offset {d['off']:#09x} "
                  f"extra {d['extra']:#010x}")
    else:
        a = [int(x) for x in sys.argv[1:]]
        main(*a)
