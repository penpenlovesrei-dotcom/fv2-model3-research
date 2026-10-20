"""Decode les textures Dreamcast de Fighting Vipers 2 en PNG.

Resolu le 2026-10-20, en partant du `VF3TB_Model_Extractor.py` de
NaomiMod/games-ExtractTools : chez Virtua Fighter 3tb Dreamcast, un modele
porte un tableau de descripteurs de texture de 16 octets, et FV2 fait pareil.

**Le tableau de descripteurs** se trouve dans chaque entree de `MDL_DAT.AFS`
(vers la fin : offset 0x2F5C8 pour l'entree 0, 0x1FEB0 pour l'entree 2). Un
enregistrement de 16 octets :

    +0x00 u32  largeur en bits 0-15, hauteur en bits 16-31
    +0x04 u32  format du pixel en octet 0, format de stockage en octet 1
    +0x08 u32  offset dans l'entree APPARIEE de TEX_DAT.AFS
    +0x0C u32  (role non etabli)

**L'appariement est par indice** : l'entree i de `MDL_DAT.AFS` lit ses textures
dans l'entree i de `TEX_DAT.AFS`. Verifie : les offsets partent de 0 et pavent
l'entree sans trou ni recouvrement.

**Les deux formats de stockage**, deduits du pas entre deux offsets consecutifs
et non supposes :

    0x01  brut, entrelace (twiddle PVR)        w * h * 2 octets
    0x03  VQ, entrelace par blocs de 2x2       2048 + (w * h) / 4 octets

Le 2048 est le livre de codes : 256 entrees de quatre texels de 16 bits. Un
octet d'index y choisit un bloc de 2x2. Mesure a l'appui : un 64x64 en 0x03
occupe 3072 octets = 2048 + 1024, un 256x256 en occupe 18432 = 2048 + 16384, et
un 32x32 en 0x01 occupe 2048 = 32 * 32 * 2.

**Les formats de pixel** sont ceux du PowerVR2 : 0 ARGB1555, 1 RGB565,
2 ARGB4444. Le RGB565 recoupe `docs/formats/TEX.md` de celsowm/vf3-decomp, qui
donne le meme format sans en-tete et le meme entrelacement par tuiles.

**Le sens de l'entrelacement est mesure, et il est le meme partout** : dans
l'index de Morton, c'est **y qui occupe les bits de poids faible**. Verifie en
rendant la meme texture dans les deux sens et en regardant : avec y en bas, la
bande d'herbe d'une texture de sol redevient horizontale et le marquage au sol
coherent ; avec x en bas, l'image est transposee. L'energie de gradient le dit
aussi (921 522 contre 1 353 607 sur ce temoin).

Piege paye une fois : trancher le sens **par entree**, sur une texture temoin
choisie au hasard, donne un faux positif des que le temoin est petit ou uni.
Le sens est une propriete du format, pas de l'entree. `--sens x` force l'autre
convention pour qui voudrait verifier.

L'ecrivain PNG est en bibliotheque standard : aucune dependance.

Usage :
    py -3 textures_dc.py descripteurs <indice>    le tableau d'une entree
    py -3 textures_dc.py png <indice>             -> textures_dc/<indice>/
    py -3 textures_dc.py png 0 15                 une plage d'entrees
    py -3 textures_dc.py planche <i> [j]          une grille de toutes les
                                                  textures, pour identifier
    py -3 textures_dc.py banques                  les banques partagees, dont
                                                  les tableaux sont dans le binaire
    py -3 textures_dc.py banque <k> [--brut]      une banque, texture par texture,
                                                  en taille native
"""

import pathlib
import struct
import sys
import zlib

ICI = pathlib.Path(__file__).parent
DC = ICI / "dreamcast"
TAILLES = {8, 16, 32, 64, 128, 256, 512, 1024}
BRUT, VQ = 0x01, 0x03


def afs(nom):
    d = pathlib.Path(DC / nom).read_bytes()
    if d[:4] != b"AFS\x00":
        raise SystemExit(f"{nom} ne commence pas par AFS\\0")
    n = struct.unpack_from("<I", d, 4)[0]
    return d, [struct.unpack_from("<II", d, 8 + i * 8) for i in range(n)]


def taille_stockee(w, h, stockage):
    return 2048 + (w * h) // 4 if stockage == VQ else w * h * 2


def un_descripteur(blob, p, taille_tex):
    if p + 16 > len(blob):
        return None
    dim, flags, off, extra = struct.unpack_from("<IIII", blob, p)
    w, h = dim & 0xFFFF, dim >> 16
    if w not in TAILLES or h not in TAILLES or flags >> 16:
        return None
    pixel, stockage = flags & 0xFF, (flags >> 8) & 0xFF
    if stockage not in (BRUT, VQ) or pixel > 2:
        return None
    if off + taille_stockee(w, h, stockage) > taille_tex:
        return None
    return {"w": w, "h": h, "pixel": pixel, "stockage": stockage,
            "off": off, "extra": extra}


def descripteurs(blob, taille_tex):
    """La plus longue suite de descripteurs plausibles : (offset, liste)."""
    meilleur = (0, 0, [])
    p = 0
    while p + 16 <= len(blob):
        liste = []
        q = p
        while True:
            d = un_descripteur(blob, q, taille_tex)
            if not d:
                break
            liste.append(d)
            q += 16
        if len(liste) > meilleur[0]:
            meilleur = (len(liste), p, liste)
        p += 4 if not liste else len(liste) * 16
    return meilleur[1], meilleur[2]


def morton(x, y, x_en_bas):
    i = 0
    for b in range(11):
        a, c = ((x, y) if x_en_bas else (y, x))
        i |= ((a >> b) & 1) << (2 * b)
        i |= ((c >> b) & 1) << (2 * b + 1)
    return i


def texel(v, pixel):
    if pixel == 0:                                    # ARGB1555
        a = 255 if v & 0x8000 else 0
        r = (v >> 10) & 0x1F
        g = (v >> 5) & 0x1F
        b = v & 0x1F
        return (r * 255 // 31, g * 255 // 31, b * 255 // 31, a)
    if pixel == 1:                                    # RGB565
        return (((v >> 11) & 0x1F) * 255 // 31, ((v >> 5) & 0x3F) * 255 // 63,
                (v & 0x1F) * 255 // 31, 255)
    a = (v >> 12) & 0xF                               # ARGB4444
    return (((v >> 8) & 0xF) * 17, ((v >> 4) & 0xF) * 17, (v & 0xF) * 17, a * 17)


def decode(brut, d, x_en_bas=False, retourner=True):
    """Rend une liste de (r, g, b, a) en ordre ligne par ligne.

    `retourner` remet l'image a l'endroit : les textures sont stockees la
    premiere ligne en bas. Mesure, pas supposee -- sur une texture de decor
    rien ne le montre, c'est le texte des menus de `TEX[16]` qui l'a revele
    (le generique du staff se lit a l'envers sans ce retournement).
    """
    w, h, pixel = d["w"], d["h"], d["pixel"]
    out = [(0, 0, 0, 0)] * (w * h)
    if d["stockage"] == VQ:
        codes = struct.unpack_from(f"<{1024}H", brut, 0)
        index = brut[2048:]
        for by in range(h // 2):
            for bx in range(w // 2):
                k = index[morton(bx, by, x_en_bas)]
                for sy in range(2):
                    for sx in range(2):
                        v = codes[k * 4 + morton(sx, sy, x_en_bas)]
                        out[(by * 2 + sy) * w + bx * 2 + sx] = texel(v, pixel)
    else:
        mots = struct.unpack_from(f"<{w * h}H", brut, 0)
        for y in range(h):
            for x in range(w):
                out[y * w + x] = texel(mots[morton(x, y, x_en_bas)], pixel)
    if retourner:
        out = [p for y in range(h - 1, -1, -1) for p in out[y * w:(y + 1) * w]]
    return out


def rugosite(pix, w, h):
    """Energie de gradient, gardee pour verifier une convention a la main."""
    s = 0
    for y in range(0, h, 2):
        ligne = y * w
        for x in range(w - 1):
            a, b = pix[ligne + x], pix[ligne + x + 1]
            s += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
    return s


def png(chemin, w, h, pix):
    lignes = []
    for y in range(h):
        lignes.append(b"\x00" + b"".join(bytes(p) for p in pix[y * w:(y + 1) * w]))
    brut = b"".join(lignes)

    def bloc(t, data):
        c = t + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    out = b"\x89PNG\r\n\x1a\n"
    out += bloc(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    out += bloc(b"IDAT", zlib.compress(brut, 6))
    out += bloc(b"IEND", b"")
    pathlib.Path(chemin).write_bytes(out)


def planche(liste, tex, to, cote=96, colonnes=8):
    """Toutes les textures d'une entree, reduites et posees en grille."""
    n = len(liste)
    lignes = (n + colonnes - 1) // colonnes
    W, H = colonnes * cote, lignes * cote
    fond = [(24, 24, 28, 255)] * (W * H)
    for k, d in enumerate(liste):
        taille = taille_stockee(d["w"], d["h"], d["stockage"])
        brut = tex[to + d["off"]: to + d["off"] + taille]
        if len(brut) < taille:
            continue
        pix = decode(brut, d, False)
        ox, oy = (k % colonnes) * cote, (k // colonnes) * cote
        for y in range(cote):
            sy = y * d["h"] // cote
            for x in range(cote):
                sx = x * d["w"] // cote
                fond[(oy + y) * W + ox + x] = pix[sy * d["w"] + sx]
    return W, H, fond


def banques():
    """Les tableaux de descripteurs qui vivent dans 1ST_READ.BIN.

    Les grosses banques de textures partagees ne sont decrites nulle part dans
    MDL_DAT.AFS : leurs tableaux sont dans le binaire, groupes entre 0x000D4A9C
    et 0x000D8404. On les reconnait a ce qu'ils **pavent exactement** une entree
    de TEX_DAT.AFS -- la somme des tailles stockees vaut sa taille au bloc pres.
    Plusieurs entrees pouvant avoir la meme taille, un tableau peut designer
    plusieurs candidates : elles partagent la disposition, pas le contenu.
    """
    tex, te = afs("TEX_DAT.AFS")
    tailles = {}
    for k, (o, s) in enumerate(te):
        tailles.setdefault(s, []).append(k)
    plafond = max(s for _, s in te)
    blob = pathlib.Path(DC / "1ST_READ.BIN").read_bytes()
    out = []
    p = 0
    while p + 16 <= len(blob):
        liste = []
        q = p
        while True:
            d = un_descripteur(blob, q, plafond)
            if not d:
                break
            liste.append(d)
            q += 16
        if len(liste) >= 3:
            total = sum(taille_stockee(d["w"], d["h"], d["stockage"]) for d in liste)
            out.append((p, liste, tailles.get(total, [])))
            p = q
        else:
            p += 4
    return tex, te, out


def cmd_banque(k, retourner=True):
    """Sort une a une les textures d'une banque partagee, en taille native."""
    tex, te, out = banques()
    trouve = [(p, liste) for p, liste, cibles in out if k in cibles]
    if not trouve:
        raise SystemExit(f"aucun tableau du binaire ne pave TEX[{k}]")
    to, ts = te[k]
    dossier = ICI / "textures_dc" / f"banque_{k:03}"
    dossier.mkdir(parents=True, exist_ok=True)
    n = 0
    for p, liste in trouve:
        for i, d in enumerate(liste):
            taille = taille_stockee(d["w"], d["h"], d["stockage"])
            brut = tex[to + d["off"]: to + d["off"] + taille]
            if len(brut) < taille:
                continue
            pix = decode(brut, d, False, retourner)
            png(dossier / f"{i:03}_{d['w']}x{d['h']}_p{d['pixel']}_s{d['stockage']:02x}.png",
                d["w"], d["h"], pix)
            n += 1
    print(f"TEX[{k}] : {n} textures en taille native -> "
          f"{dossier.relative_to(ICI)}"
          f"{' (retournees verticalement)' if retourner else ''}")


def cmd_banques():
    tex, te, out = banques()
    dossier = ICI / "textures_dc"
    dossier.mkdir(exist_ok=True)
    for p, liste, cibles in out:
        total = sum(taille_stockee(d["w"], d["h"], d["stockage"]) for d in liste)
        print(f"  {p:#08x} : {len(liste):>3} descripteurs, {total:>9} octets"
              f"  -> TEX {cibles if cibles else '(aucune entree de cette taille)'}")
        for k in cibles:
            to, ts = te[k]
            W, H, pix = planche(liste, tex, to)
            s = dossier / f"banque_tex{k:03}.png"
            png(s, W, H, pix)
            print(f"      -> {s.relative_to(ICI)}")


def textures_de_lentree(indice):
    """Rend (octets de TEX_DAT, indice de l'entree TEX, descripteurs).

    **L'appariement MDL[i] <-> TEX[i] n'est vrai que pour les entrees 0 a 15.**
    Au-dela il est faux : MDL[16] et MDL[17] pavent TEX[17] ou TEX[18], jamais
    TEX[16]. La seule preuve disponible est le **pavage exact** -- la somme des
    tailles stockees d'un tableau de descripteurs vaut la taille de son entree
    TEX a l'octet pres, sans trou ni recouvrement.

    Piege paye : les commandes de ce script appariaient par indice, et
    rendaient donc des planches fausses au-dela de l'entree 15.

    Rend (None, None, []) si aucune entree ne correspond -- une entree dont le
    tableau vit dans le binaire et non dans le modele, par exemple : voir
    `banques()`.
    """
    tex, _ = afs("TEX_DAT.AFS")
    k, liste = _appariement().get(indice, (None, []))
    return (tex, k, liste) if k is not None else (None, None, liste)


def _descripteurs_de(indice):
    """(offset du tableau, descripteurs) d'une entree de MDL_DAT."""
    mdl, me = afs("MDL_DAT.AFS")
    _, te = afs("TEX_DAT.AFS")
    if not 0 <= indice < len(me):
        return 0, []
    mo, ms = me[indice]
    if ms == 0:
        return 0, []
    plafond = max(s for _, s in te)
    return descripteurs(mdl[mo:mo + ms], plafond)


_cache_appariement = None


def _appariement():
    """Associe chaque entree MDL a son entree TEX, globalement et une fois.

    Plusieurs entrees de TEX_DAT partagent la meme taille -- les deux couleurs
    d'un meme costume, par exemple. Chercher « la premiere entree de cette
    taille » rendait donc toujours la meme pour les deux, et les planches de la
    seconde montraient le contenu de la premiere. On apparie globalement : les
    entrees MDL sont parcourues dans l'ordre, et chacune prend la premiere
    entree TEX **encore libre** de la bonne taille.
    """
    global _cache_appariement
    if _cache_appariement is not None:
        return _cache_appariement
    _, me = afs("MDL_DAT.AFS")
    _, te = afs("TEX_DAT.AFS")
    libres = {}
    for k, (o, s) in enumerate(te):
        libres.setdefault(s, []).append(k)
    table = {}
    for i in range(len(me)):
        _, liste = _descripteurs_de(i)
        if not liste:
            table[i] = (None, [])
            continue
        total = sum(taille_stockee(d["w"], d["h"], d["stockage"]) for d in liste)
        dispo = libres.get(total)
        table[i] = (dispo.pop(0) if dispo else None, liste)
    _cache_appariement = table
    return table


def cmd_planche(premier, dernier):
    mdl, me = afs("MDL_DAT.AFS")
    tex, te = afs("TEX_DAT.AFS")
    dossier = ICI / "textures_dc"
    dossier.mkdir(exist_ok=True)
    for i in range(premier, min(dernier + 1, len(me))):
        tex, k, liste = textures_de_lentree(i)
        if not liste:
            print(f"[{i:3}] aucun descripteur")
            continue
        if k is None:
            print(f"[{i:3}] {len(liste):>3} descripteurs, aucune entree TEX pavee exactement")
            continue
        to, ts = te[k]
        W, H, pix = planche(liste, tex, to)
        s = dossier / f"planche_{i:03}_tex{k:03}.png"
        png(s, W, H, pix)
        print(f"[{i:3}] <-> TEX[{k:3}]  {len(liste):>3} textures  {W}x{H}  "
              f"-> {s.relative_to(ICI)}")


def cmd_descripteurs(indice):
    mdl, me = afs("MDL_DAT.AFS")
    _, te = afs("TEX_DAT.AFS")
    ms = me[indice][1]
    tex, k, liste = textures_de_lentree(indice)
    if not liste:
        raise SystemExit(f"MDL[{indice}] : aucun tableau de descripteurs")
    if k is None:
        raise SystemExit(f"MDL[{indice}] : {len(liste)} descripteurs, "
                         "aucune entree TEX pavee exactement")
    ts = te[k][1]
    plafond = max(s for _, s in te)
    off, _ = descripteurs(mdl[me[indice][0]:me[indice][0] + ms], plafond)
    print(f"MDL[{indice}] {ms} octets  <->  TEX[{k}] {ts} octets")
    print(f"tableau de {len(liste)} descripteurs a l'offset {off:#x}\n")
    couvert = 0
    for k, d in enumerate(liste):
        n = taille_stockee(d["w"], d["h"], d["stockage"])
        couvert += n
        print(f"  [{k:3}] {d['w']:>4}x{d['h']:<4}  pixel {d['pixel']}  "
              f"stockage {d['stockage']:#04x}  offset {d['off']:#09x}  "
              f"{n:>7} octets")
    print(f"\n{couvert} octets decrits sur {ts} ({100 * couvert / ts:.1f} %)")


def cmd_png(premier, dernier, x_en_bas=False):
    mdl, me = afs("MDL_DAT.AFS")
    tex, te = afs("TEX_DAT.AFS")
    for i in range(premier, min(dernier + 1, len(me))):
        tex, k, liste = textures_de_lentree(i)
        if not liste:
            print(f"[{i:3}] aucun descripteur")
            continue
        if k is None:
            print(f"[{i:3}] aucune entree TEX pavee exactement")
            continue
        to, ts = te[k]
        dossier = ICI / "textures_dc" / f"{i:03}_tex{k:03}"
        dossier.mkdir(parents=True, exist_ok=True)
        for k, d in enumerate(liste):
            n = taille_stockee(d["w"], d["h"], d["stockage"])
            b = tex[to + d["off"]: to + d["off"] + n]
            if len(b) < n:
                continue
            pix = decode(b, d, x_en_bas)
            png(dossier / f"{k:03}_{d['w']}x{d['h']}_p{d['pixel']}_s{d['stockage']:02x}.png",
                d["w"], d["h"], pix)
        print(f"[{i:3}] {len(liste):>3} textures  -> {dossier.relative_to(ICI)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    quoi = sys.argv[1]
    if quoi == "descripteurs":
        cmd_descripteurs(int(sys.argv[2]))
    elif quoi == "banque":
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        cmd_banque(int(args[0]), "--brut" not in sys.argv)
    elif quoi == "banques":
        cmd_banques()
    elif quoi == "planche":
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        p = int(args[0]) if args else 0
        cmd_planche(p, int(args[1]) if len(args) > 1 else p)
    elif quoi == "png":
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        x = "--sens" in sys.argv and sys.argv[sys.argv.index("--sens") + 1] == "x"
        p = int(args[0]) if args else 0
        cmd_png(p, int(args[1]) if len(args) > 1 else p, x)
    else:
        raise SystemExit(__doc__)
