"""Quelle entree de MDL_DAT.AFS porte quel decor, etabli par les textures.

Le code ne le dit pas. Le repartiteur de ressource (0x8C047C9E) ne traite que
l'audio, la liste de 8 identifiants d'un decor est audio de bout en bout, et le
chargeur de modele (0x8C02A5A8) recoit un index dont on ne sait pas d'ou il
vient. Reste la mesure.

`retrouver.py` retrouve UNE texture dumpee parmi les ~3 700 du disque. Mais une
seule texture ne tranche pas : un ciel, un sol, un reflet servent a plusieurs
decors, et la meme signature tombe a l'ecart 0,0 dans deux entrees. D'ou ce
script : il fait **voter tout un dossier de dump**. Chaque image vote pour
chaque source ou elle se retrouve a l'ecart minimal, et l'entree qui porte le
decor est celle qui rafle les voix.

Ce qui est ecarte, et dit plutot que tu :
  - une image trop unie, dont la signature ne distinguerait rien
  - une image dont le meilleur ecart reste grand : elle n'est pas sur ce disque
    (retouche, agrandie, ou venue de la version arcade)

Usage :
    py -3 decor_vers_entree.py <dossier-racine>      un sous-dossier par decor
    py -3 decor_vers_entree.py <dossier> --direct    le dossier est un dump
    py -3 decor_vers_entree.py ... --sous DC         quel sous-dossier lire
"""

import pathlib
import sys
from collections import Counter

import retrouver as R

# Au-dela, l'image n'est pas sur ce disque. Mesure : une correspondance vraie
# tombe a 0,0 ou a quelques unites ; les faux voisins commencent vers 100.
SEUIL = 40.0
# Deux sources a moins de ca l'une de l'autre sont a egalite : la texture vit
# dans les deux, et chacune prend une voix.
EGALITE = 1.0


def charge_base():
    print("signatures du disque...", flush=True)
    base = R.toutes_les_textures()
    utiles = [b for b in base if b[4] is not None and b[5] >= R.PLAT]
    print(f"{len(base)} textures, {len(utiles)} assez contrastees\n", flush=True)
    return utiles


def vote_dossier(utiles, dossier):
    """Rend (voix, lues, unies, hors_disque)."""
    voix = Counter()
    lues = unies = hors = 0
    for png in sorted(pathlib.Path(dossier).glob("*.png")):
        try:
            w, h, pix = R.lit_png(str(png))
        except Exception:
            continue
        lues += 1
        resultats = []
        plate = True
        for retournee in (False, True):
            sig, ecart = R.signature_image(w, h, pix, retournee)
            if sig is None or ecart < R.PLAT:
                continue
            plate = False
            for source, k, i, d, s, _ in utiles:
                dist = sum(abs(a - b) for a, b in zip(sig, s))
                resultats.append((dist, source, k))
        if plate:
            unies += 1
            continue
        if not resultats:
            continue
        resultats.sort()
        mini = resultats[0][0]
        if mini > SEUIL:
            hors += 1
            continue
        gagnants = set()
        for dist, source, k in resultats:
            if dist > mini + EGALITE:
                break
            gagnants.add((source, k))
        for g in gagnants:
            voix[g] += 1
    return voix, lues, unies, hors


def rapport(nom, voix, lues, unies, hors):
    print(f"=== {nom}")
    print(f"    {lues} image(s) : {unies} trop unie(s), {hors} hors du disque, "
          f"{lues - unies - hors} retrouvee(s)")
    if not voix:
        print("    aucune voix")
        return None
    classe = voix.most_common(6)
    tete = classe[0][1]
    for (source, k), n in classe:
        marque = "  <--" if n == tete else ""
        print(f"    {n:3} voix   {source:<12} TEX[{k}]{marque}")
    return classe


def main(args):
    direct = "--direct" in args
    sous = "DC"
    if "--sous" in args:
        i = args.index("--sous")
        sous = args[i + 1]
        args = args[:i] + args[i + 2:]
    args = [a for a in args if not a.startswith("--")]
    racine = pathlib.Path(args[0])
    utiles = charge_base()
    if direct:
        rapport(racine.name, *vote_dossier(utiles, racine))
        return
    bilan = {}
    for d in sorted(p for p in racine.iterdir() if p.is_dir()):
        cible = d / sous
        if not cible.is_dir():
            print(f"=== {d.name}\n    pas de sous-dossier {sous}\n")
            continue
        classe = rapport(d.name, *vote_dossier(utiles, cible))
        if classe:
            bilan[d.name] = classe[0]
        print(flush=True)
    print("=" * 62)
    print("BILAN  decor -> entree")
    for nom, ((source, k), n) in sorted(bilan.items()):
        print(f"  {nom:<28} {source:<12} TEX[{k}]   ({n} voix)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
