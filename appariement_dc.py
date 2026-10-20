"""Apparie chaque entree de MDL_DAT.AFS avec l'entree de TEX_DAT.AFS que son
tableau de descripteurs **pave exactement**, et resume chaque entree.

Ecrit le 2026-10-21 pour la recherche du costume d'infirmiere de Honey.
N'ecrit aucune donnee de jeu : seulement du texte sur la sortie standard.

L'appariement par indice marche jusqu'a l'entree 15 et pas au dela. La regle
sure est la somme : le tableau de descripteurs d'une entree MDL decrit un
decoupage dont la somme des tailles stockees vaut la taille d'une entree de
TEX_DAT a l'octet (ou au bloc de 2 Kio) pres.

Usage :
    py -3 appariement_dc.py                 toutes les entrees
    py -3 appariement_dc.py <i> [j]         une plage
"""

import pathlib
import struct
import sys

import textures_dc as T


def table_mdl(blob, plafond):
    """La plus longue suite de descripteurs plausibles, plafond = taille max TEX."""
    return T.descripteurs(blob, plafond)


def main(premier, dernier):
    mdl, me = T.afs("MDL_DAT.AFS")
    tex, te = T.afs("TEX_DAT.AFS")
    plafond = max(s for _, s in te)

    par_taille = {}
    for k, (o, s) in enumerate(te):
        par_taille.setdefault(s, []).append(k)

    print(" MDL  taille MDL  mot0      nb tex  octets decrits   TEX candidates (paving exact)")
    for i in range(premier, min(dernier + 1, len(me))):
        mo, ms = me[i]
        if ms == 0:
            print(f" [{i:3}] {ms:>10}  (vide)")
            continue
        blob = mdl[mo:mo + ms]
        w0 = struct.unpack_from("<I", blob, 0)[0]
        off, liste = table_mdl(blob, plafond)
        if not liste:
            print(f" [{i:3}] {ms:>10}  {w0:08x}  aucun descripteur")
            continue
        total = sum(T.taille_stockee(d["w"], d["h"], d["stockage"]) for d in liste)
        # paving exact, puis arrondi au bloc de 2 Kio (alignement de l'archive)
        exact = par_taille.get(total, [])
        arrondi = par_taille.get((total + 2047) // 2048 * 2048, [])
        cands = exact if exact else arrondi
        marque = "" if exact else (" (au bloc)" if arrondi else "")
        dims = ",".join(f"{d['w']}x{d['h']}" for d in liste[:6])
        print(f" [{i:3}] {ms:>10}  {w0:08x}  {len(liste):>5}  {total:>9}"
              f"   {cands}{marque}   tab@{off:#x}  {dims}...")


if __name__ == "__main__":
    a = [int(x) for x in sys.argv[1:]]
    if not a:
        main(0, 77)
    elif len(a) == 1:
        main(a[0], a[0])
    else:
        main(a[0], a[1])
