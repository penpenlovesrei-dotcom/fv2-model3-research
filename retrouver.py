"""Retrouve une texture dumpee d'emulateur parmi celles du disque Dreamcast.

Le probleme : on sait a quoi ressemble une texture d'un decor (dump d'emulateur)
mais pas ou elle vit dans `TEX_DAT.AFS`. La retrouver donne l'entree TEX, donc
l'entree MDL appariee, donc l'index de ressource du decor -- c'est-a-dire la
reponse que ni la recherche statique ni le code n'ont donnee.

**Comment on compare.** Pas octet a octet : le dump de l'emulateur est deja
decode en RGBA, pas compresse en VQ, et peut-etre redimensionne. On compare
donc des **signatures** : une vignette de 16x16 en niveaux de gris, centree sur
sa moyenne et normalisee, ce qui rend la comparaison insensible a la
luminosite et au contraste. La distance est la somme des ecarts absolus.

**Les deux orientations sont essayees**, parce que les textures du disque sont
stockees la premiere ligne en bas (voir `textures_dc.py`) et qu'un dump
d'emulateur, lui, peut etre dans un sens comme dans l'autre.

**Echantillonnage creux** : pour une signature de 16x16 il suffit de 256
lectures de texel, pas de decoder la texture entiere. C'est ce qui permet de
balayer les 115 entrees de l'archive en quelques secondes au lieu d'une heure.

**Refus des textures unies** : une signature plate vaut celle de toute autre
texture plate. Une candidate dont l'ecart-type est quasi nul est ecartee, et le
script le dit plutot que de rendre une correspondance qui ne veut rien dire.

Usage :
    py -3 retrouver.py <image.png> [image2.png ...]
    py -3 retrouver.py <dossier>             tout un dump d'emulateur
"""

import pathlib
import struct
import sys
import zlib

ICI = pathlib.Path(__file__).parent
sys.path.insert(0, str(ICI))
import textures_dc as T

COTE = 16
PLAT = 3.0          # ecart-type en dessous duquel une signature ne distingue rien


# ---------------------------------------------------------------- lecture PNG
def lit_png(chemin):
    """Rend (largeur, hauteur, pixels RGBA). Sans dependance."""
    d = pathlib.Path(chemin).read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("pas un PNG")
    p = 8
    w = h = prof = typ = None
    morceaux = []
    palette = b""
    trans = b""
    while p < len(d):
        n = struct.unpack_from(">I", d, p)[0]
        t = d[p + 4:p + 8]
        data = d[p + 8:p + 8 + n]
        if t == b"IHDR":
            w, h, prof, typ, _, _, entrelace = struct.unpack_from(">IIBBBBB", data, 0)
            if entrelace:
                raise ValueError("PNG entrelace non gere")
            if prof != 8:
                raise ValueError(f"profondeur {prof} non geree")
        elif t == b"PLTE":
            palette = data
        elif t == b"tRNS":
            trans = data
        elif t == b"IDAT":
            morceaux.append(data)
        elif t == b"IEND":
            break
        p += 12 + n
    canaux = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[typ]
    brut = zlib.decompress(b"".join(morceaux))
    pas = w * canaux
    lignes = []
    precedente = bytearray(pas)
    q = 0
    for _ in range(h):
        filtre = brut[q]
        ligne = bytearray(brut[q + 1:q + 1 + pas])
        q += 1 + pas
        for i in range(pas):
            a = ligne[i - canaux] if i >= canaux else 0
            b = precedente[i]
            c = precedente[i - canaux] if i >= canaux else 0
            x = ligne[i]
            if filtre == 1:
                x += a
            elif filtre == 2:
                x += b
            elif filtre == 3:
                x += (a + b) // 2
            elif filtre == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                x += a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            ligne[i] = x & 0xFF
        lignes.append(bytes(ligne))
        precedente = ligne
    pix = []
    for ligne in lignes:
        for i in range(w):
            v = ligne[i * canaux:(i + 1) * canaux]
            if typ == 6:
                pix.append(tuple(v))
            elif typ == 2:
                pix.append((v[0], v[1], v[2], 255))
            elif typ == 4:
                pix.append((v[0], v[0], v[0], v[1]))
            elif typ == 0:
                pix.append((v[0], v[0], v[0], 255))
            else:
                k = v[0] * 3
                a = trans[v[0]] if v[0] < len(trans) else 255
                pix.append((palette[k], palette[k + 1], palette[k + 2], a))
    return w, h, pix


# ------------------------------------------------------------- signatures
def normalise(gris):
    moy = sum(gris) / len(gris)
    ecart = (sum((v - moy) ** 2 for v in gris) / len(gris)) ** 0.5
    return [(v - moy) / ecart for v in gris] if ecart > 1e-6 else None, ecart


def signature_image(w, h, pix, retournee=False):
    gris = []
    for y in range(COTE):
        sy = y * h // COTE
        if retournee:
            sy = h - 1 - sy          # vrai miroir, pas un miroir de rangees
        for x in range(COTE):
            r, g, b, _ = pix[sy * w + x * w // COTE]
            gris.append(0.299 * r + 0.587 * g + 0.114 * b)
    return normalise(gris)


def signature_texture(brut, d):
    """Signature d'une texture du disque, par echantillonnage creux."""
    w, h, pixel = d["w"], d["h"], d["pixel"]
    gris = []
    if d["stockage"] == T.VQ:
        codes = struct.unpack_from("<1024H", brut, 0)
        index = brut[2048:]
        for y in range(COTE):
            sy = y * h // COTE
            for x in range(COTE):
                sx = x * w // COTE
                k = index[T.morton(sx // 2, sy // 2, False)]
                v = codes[k * 4 + T.morton(sx & 1, sy & 1, False)]
                r, g, b, _ = T.texel(v, pixel)
                gris.append(0.299 * r + 0.587 * g + 0.114 * b)
    else:
        for y in range(COTE):
            sy = y * h // COTE
            for x in range(COTE):
                sx = x * w // COTE
                v = struct.unpack_from("<H", brut, T.morton(sx, sy, False) * 2)[0]
                r, g, b, _ = T.texel(v, pixel)
                gris.append(0.299 * r + 0.587 * g + 0.114 * b)
    return normalise(gris)


def toutes_les_textures():
    """Rend [(source, entree TEX, rang, descripteur, signature, ecart)]."""
    mdl, me = T.afs("MDL_DAT.AFS")
    tex, te = T.afs("TEX_DAT.AFS")
    vues = set()
    out = []

    def ajoute(source, k, liste):
        to, ts = te[k]
        for i, d in enumerate(liste):
            cle = (k, d["off"])
            if cle in vues:
                continue
            vues.add(cle)
            n = T.taille_stockee(d["w"], d["h"], d["stockage"])
            brut = tex[to + d["off"]: to + d["off"] + n]
            if len(brut) < n:
                continue
            sig, ecart = signature_texture(brut, d)
            out.append((source, k, i, d, sig, ecart))

    # L'appariement MDL[i] <-> TEX[i] n'est VERIFIE que pour les entrees 0 a 15.
    # Au-dela il est faux (MDL[16] et MDL[17] pavent TEX[17] ou TEX[18], jamais
    # TEX[16]). On apparie donc par la seule preuve disponible : un tableau pave
    # EXACTEMENT une entree, la somme des tailles stockees vaut sa taille.
    tailles = {}
    for k, (o, s) in enumerate(te):
        tailles.setdefault(s, []).append(k)
    plafond = max(s for _, s in te)
    for i, (mo, ms) in enumerate(me):
        if ms == 0:
            continue
        blob = mdl[mo:mo + ms]
        p = 0
        while p + 16 <= len(blob):
            liste = []
            q = p
            while True:
                d = T.un_descripteur(blob, q, plafond)
                if not d:
                    break
                liste.append(d)
                q += 16
            if len(liste) >= 3:
                total = sum(T.taille_stockee(d["w"], d["h"], d["stockage"])
                            for d in liste)
                for k in tailles.get(total, []):
                    ajoute(f"MDL[{i}]", k, liste)
                p = q
            else:
                p += 4
    for p, liste, cibles in T.banques()[2]:
        for k in cibles:
            ajoute(f"binaire {p:#08x}", k, liste)
    return out


def cherche(chemins):
    print("signatures du disque...", flush=True)
    base = toutes_les_textures()
    utiles = [b for b in base if b[4] is not None and b[5] >= PLAT]
    print(f"{len(base)} textures, {len(utiles)} assez contrastees pour servir\n")
    for chemin in chemins:
        try:
            w, h, pix = lit_png(chemin)
        except Exception as e:
            print(f"{pathlib.Path(chemin).name} : illisible ({e})")
            continue
        resultats = []
        for retournee in (False, True):
            sig, ecart = signature_image(w, h, pix, retournee)
            if sig is None or ecart < PLAT:
                print(f"{pathlib.Path(chemin).name} : image trop unie "
                      f"(ecart-type {ecart:.1f}), elle ne distinguerait rien")
                break
            for source, k, i, d, s, _ in utiles:
                dist = sum(abs(a - b) for a, b in zip(sig, s))
                resultats.append((dist, source, k, i, d, retournee))
        if not resultats:
            continue
        resultats.sort()
        print(f"=== {pathlib.Path(chemin).name}  {w}x{h}")
        for dist, source, k, i, d, retournee in resultats[:6]:
            print(f"   ecart {dist:8.1f}   TEX[{k:3}] rang {i:3}  "
                  f"{d['w']:>4}x{d['h']:<4}  {source}"
                  f"{'  (retournee)' if retournee else ''}")
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    chemins = []
    for a in args:
        p = pathlib.Path(a)
        chemins += sorted(str(x) for x in p.glob("*.png")) if p.is_dir() else [a]
    cherche(chemins)
