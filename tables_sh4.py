"""Retrouve, par balayage d'octets, ce que le desassemblage ne voit pas.

Pourquoi un balayage et pas Ghidra : sur 1ST_READ.BIN seuls 32,4 % du binaire
sont desassembles, et les tables de Fighting Vipers 2 sont atteintes par
adresse calculee. Une reference qui n'existe pas dans le graphe de Ghidra
existe quand meme dans les octets -- il suffit de ne demander aucun contexte.

Trois decouvreurs, repris de la technique decrite par celsowm/vf3-decomp
(docs/re/ref_dreamcastrecompiled.md, « BRAF switch-table resolution ») :

  1. tables d'octets   MOVA + MOV.B @(R0,Rm),Rn [+ EXTU.B] + BRAF Rn
  2. tables de mots    base par MOVA ou litteral, [ADD Rn,Rn], MOV.W + BRAF
  3. tables absolues   MOV.L litteral,Rt + MOV.L @(R0,Rt),Rn + JSR/JMP @Rn

Et le decouvreur dont on a besoin ici, qui n'est pas dans leur liste :
quelle instruction charge un litteral donne. Une adresse de table vit dans un
bassin litteral, et c'est un `MOV.L @(disp,PC),Rn` qui l'en sort. Trouver ce
`MOV.L`, c'est nommer la fonction.

Usage :
    py -3 tables_sh4.py charge <adresse> [<adresse> ...]
    py -3 tables_sh4.py braf [--max N]
    py -3 tables_sh4.py mots16 <valeur>
"""

import struct
import sys

BASE = 0x8C010000
CHEMIN = "dreamcast/1ST_READ.BIN"

# Les registres cites dans les traces, pour que les sorties se lisent.
NOMS = [f"r{i}" for i in range(16)]


def charge_binaire(chemin=CHEMIN):
    with open(chemin, "rb") as f:
        return f.read()


class Image:
    def __init__(self, d=None, base=BASE):
        self.d = charge_binaire() if d is None else d
        self.base = base

    def __contains__(self, a):
        return self.base <= a < self.base + len(self.d)

    def off(self, a):
        return a - self.base if a in self else None

    def mot(self, a):
        o = self.off(a)
        return struct.unpack_from("<I", self.d, o)[0] if o is not None and o + 4 <= len(self.d) else None

    def demi(self, a):
        o = self.off(a)
        return struct.unpack_from("<H", self.d, o)[0] if o is not None and o + 2 <= len(self.d) else None

    def octet(self, a):
        o = self.off(a)
        return self.d[o] if o is not None else None

    def chaine(self, a, n=64):
        o = self.off(a)
        if o is None:
            return None
        s = self.d[o:o + n].split(b"\x00")[0]
        return s.decode("latin1") if s and all(32 <= c < 127 for c in s) else None

    def adresses_mots(self):
        """Rend (adresse, valeur) pour chaque mot 32 bits aligne."""
        for o in range(0, len(self.d) - 3, 4):
            yield self.base + o, struct.unpack_from("<I", self.d, o)[0]

    def adresses_demis(self):
        for o in range(0, len(self.d) - 1, 2):
            yield self.base + o, struct.unpack_from("<H", self.d, o)[0]


# ---------------------------------------------------------------- decodage

def pc_mot(a):
    """Cible d'un MOV.L @(disp,PC) ou d'un MOVA : le PC est aligne sur 4."""
    return (a & 0xFFFFFFFC) + 4


def decode(h, a):
    """Rend (mnemonique, champs) pour les seules formes qui nous servent."""
    n = (h >> 8) & 0xF
    m = (h >> 4) & 0xF
    d8 = h & 0xFF
    if (h & 0xF000) == 0xD000:
        return "mov.l@pc", {"n": n, "cible": pc_mot(a) + d8 * 4}
    if (h & 0xF000) == 0x9000:
        return "mov.w@pc", {"n": n, "cible": a + 4 + d8 * 2}
    if (h & 0xFF00) == 0xC700:
        return "mova", {"n": 0, "cible": pc_mot(a) + d8 * 4}
    if (h & 0xF0FF) == 0x0023:
        return "braf", {"n": n}
    if (h & 0xF0FF) == 0x0003:
        return "bsrf", {"n": n}
    if (h & 0xF0FF) == 0x402B:
        return "jmp", {"n": n}
    if (h & 0xF0FF) == 0x400B:
        return "jsr", {"n": n}
    if (h & 0xF00F) == 0x000C:
        return "mov.b@r0", {"n": n, "m": m}
    if (h & 0xF00F) == 0x000D:
        return "mov.w@r0", {"n": n, "m": m}
    if (h & 0xF00F) == 0x000E:
        return "mov.l@r0", {"n": n, "m": m}
    if (h & 0xF00F) == 0x600C:
        return "extu.b", {"n": n, "m": m}
    if (h & 0xF00F) == 0x600D:
        return "extu.w", {"n": n, "m": m}
    if (h & 0xF00F) == 0x6003:
        return "mov", {"n": n, "m": m}
    if (h & 0xF00F) == 0x300C:
        return "add", {"n": n, "m": m}
    if (h & 0xF00F) == 0x3002:
        return "cmp/hs", {"n": n, "m": m}
    if (h & 0xF00F) == 0x3006:
        return "cmp/hi", {"n": n, "m": m}
    if (h & 0xF000) == 0xE000:
        imm = d8 - 256 if d8 >= 128 else d8
        return "mov#", {"n": n, "imm": imm}
    return None, {}


# ------------------------------------------------- decouvreur de chargeurs

def bassins(img, cibles, marge=0):
    """Adresses des mots litteraux qui portent une des cibles.

    `marge` elargit la recherche : un litteral qui pointe dans la table plutot
    que sur son premier octet compte aussi, et c'est souvent ce qui se passe
    quand le compilateur replie un +0x10 dans le litteral.
    """
    vus = {}
    for a, v in img.adresses_mots():
        for c in cibles:
            if c <= v <= c + marge:
                vus.setdefault(a, []).append((c, v))
    return vus


def chargeurs(img, slots):
    """Instructions PC-relatives dont la cible est un de ces slots."""
    out = []
    for a, h in img.adresses_demis():
        mn, ch = decode(h, a)
        if mn in ("mov.l@pc", "mova") and ch["cible"] in slots:
            out.append((a, mn, ch["n"], ch["cible"]))
    return out


def cmd_charge(args):
    img = Image()
    marge = 0
    if "--marge" in args:
        i = args.index("--marge")
        marge = int(args[i + 1], 0)
        args = args[:i]
    cibles = [int(x, 0) for x in args]
    print(f"binaire {len(img.d)} octets, base {img.base:#010x}")
    slots = bassins(img, cibles, marge)
    if not slots:
        print("  AUCUN litteral ne porte ces adresses.")
        print("  (elles sont donc calculees, ou atteintes depuis une structure)")
        return
    for sa, quoi in sorted(slots.items()):
        for c, v in quoi:
            ecart = "" if v == c else f"  (+{v - c:#x})"
            print(f"\n=== litteral {sa:#010x} = {v:#010x}{ecart}")
            tx = img.chaine(v)
            if tx:
                print(f'    la cible est la chaine "{tx}"')
    tous = chargeurs(img, set(slots))
    print(f"\n{len(tous)} instruction(s) chargent ces littéraux")
    for a, mn, n, c in tous:
        v = img.mot(c)
        print(f"  {a:#010x}  {mn:<9s} -> r{n}  = {v:#010x}   (litteral {c:#010x})")
    return tous


# ------------------------------------------------ decouvreurs de dispatch

def remonte_source(img, a, reg, fenetre=40):
    """Qui a ecrit `reg` juste avant `a` ? Suit les copies MOV et EXTU."""
    chaine = [reg]
    cur = reg
    for k in range(1, fenetre):
        p = a - 2 * k
        h = img.demi(p)
        if h is None:
            break
        mn, ch = decode(h, p)
        if mn is None:
            continue
        if ch.get("n") != cur:
            continue
        if mn in ("mov", "extu.b", "extu.w"):
            cur = ch["m"]
            chaine.append(cur)
            continue
        return p, mn, ch, chaine
    return None, None, {}, chaine


def borne(img, a, fenetre=256):
    """Cherche en arriere un CMP/HS ou CMP/HI et l'immediat compare."""
    for k in range(1, fenetre // 2):
        p = a - 2 * k
        h = img.demi(p)
        if h is None:
            break
        mn, ch = decode(h, p)
        if mn in ("cmp/hs", "cmp/hi"):
            for j in range(1, 24):
                q = p - 2 * j
                h2 = img.demi(q)
                if h2 is None:
                    break
                mn2, ch2 = decode(h2, q)
                if mn2 == "mov#" and ch2["n"] == ch["m"]:
                    n = ch2["imm"]
                    return (n if mn == "cmp/hs" else n + 1), mn, q
            return None, mn, p
    return None, None, None


def code_plausible(img, a):
    """Un mot qui tombe dans l'image et dont le demi-mot se decode."""
    return a in img and (a & 1) == 0


def braf_tables(img, maxi=None):
    """Les trois decouvreurs, en une passe."""
    res = []
    for a, h in img.adresses_demis():
        mn, ch = decode(h, a)
        if mn not in ("braf", "jmp", "jsr"):
            continue
        p, smn, sch, _ = remonte_source(img, a, ch["n"])
        if smn not in ("mov.b@r0", "mov.w@r0", "mov.l@r0"):
            continue
        # la base est soit en R0 (MOVA), soit dans Rm (litteral)
        base = None
        genre = None
        pb, bmn, bch, _ = remonte_source(img, p, sch["m"])
        if bmn == "mov.l@pc":
            base = img.mot(bch["cible"])
            genre = "litteral"
        if base is None:
            pm, mmn, mch, _ = remonte_source(img, p, 0)
            if mmn == "mova":
                base = mch["cible"]
                genre = "mova"
        if base is None or base not in img:
            continue
        n, cmp_, _ = borne(img, a)
        pas = {"mov.b@r0": 1, "mov.w@r0": 2, "mov.l@r0": 4}[smn]
        res.append({
            "saut": a, "mn": mn, "charge": p, "forme": smn,
            "base": base, "origine": genre, "pas": pas,
            "borne": n, "cmp": cmp_,
        })
        if maxi and len(res) >= maxi:
            break
    return res


def cmd_braf(args):
    maxi = None
    if "--max" in args:
        maxi = int(args[args.index("--max") + 1], 0)
    img = Image()
    res = braf_tables(img, maxi)
    print(f"{len(res)} table(s) de saut")
    print(f"{'saut':<12}{'forme':<11}{'base':<12}{'pas':<5}{'borne':<8}{'origine'}")
    for r in res:
        b = "?" if r["borne"] is None else str(r["borne"])
        print(f"{r['saut']:#010x}  {r['forme']:<11}{r['base']:#010x}  "
              f"{r['pas']:<5}{b:<8}{r['origine']}")
    return res


def cmd_appels(args):
    """Qui saute ICI par deplacement direct, sans passer par un littéral.

    C'est l'angle mort du balayage par littéraux : `bsr` et `bra` portent un
    deplacement de 12 bits, soit +-4 Ko, et `bt`/`bf` un de 8 bits. Un appel
    vers une fonction voisine ne laisse donc aucune adresse en memoire. La
    moitie des appels d'une bibliotheque compacte comme ADXF sont de ceux-la.
    """
    img = Image()
    cibles = {int(x, 0) for x in args}
    out = []
    for a, h in img.adresses_demis():
        d12 = h & 0xFFF
        d8 = h & 0xFF
        if (h & 0xF000) in (0xA000, 0xB000):
            cible = a + 4 + ((d12 - 4096 if d12 >= 2048 else d12)) * 2
            mn = "bra" if (h & 0xF000) == 0xA000 else "bsr"
        elif (h & 0xFF00) in (0x8900, 0x8B00, 0x8D00, 0x8F00):
            cible = a + 4 + (d8 - 256 if d8 >= 128 else d8) * 2
            mn = {0x8900: "bt", 0x8B00: "bf", 0x8D00: "bt/s", 0x8F00: "bf/s"}[h & 0xFF00]
        else:
            continue
        if cible in cibles:
            out.append((a, mn, cible))
    print(f"{len(out)} saut(s) direct(s) vers ces adresses")
    for a, mn, c in out:
        print(f"  {a:#010x}  {mn:<5s} -> {c:#010x}")
    return out


def _debuts(img):
    import desas_sh4
    return desas_sh4.Desas(img.d, img.base)


def appelants(img, ds, cible):
    """Tous les appelants d'une adresse : par littéral ET par saut direct."""
    out = set()
    slots = {a for a, v in img.adresses_mots() if v == cible}
    for a, h in img.adresses_demis():
        mn, ch = decode(h, a)
        if mn in ("mov.l@pc", "mova") and ch["cible"] in slots:
            out.add(a)
            continue
        d12 = h & 0xFFF
        if (h & 0xF000) in (0xA000, 0xB000):
            if a + 4 + ((d12 - 4096 if d12 >= 2048 else d12)) * 2 == cible:
                out.add(a)
    return sorted(out)


def cmd_remonte(args):
    """Remonte le graphe d'appels depuis une adresse, sur N niveaux.

    Le premier `rts` donne la fin d'une fonction, pas forcement la bonne :
    une fonction a plusieurs sorties se fait couper trop tot. Le debut, lui,
    se repere au prologue. On affiche donc le debut PRESUME, et il faut le
    verifier a l'oeil avant de s'appuyer dessus.
    """
    img = Image()
    ds = _debuts(img)
    profondeur = 3
    if "--niveaux" in args:
        i = args.index("--niveaux")
        profondeur = int(args[i + 1], 0)
        args = args[:i]
    courant = [int(args[0], 0)]
    vus = set(courant)
    for niveau in range(profondeur):
        suivant = []
        for c in courant:
            deb = ds.debut_de_fonction(c) or c
            aps = appelants(img, ds, deb)
            print(f"niveau {niveau}  {c:#010x}  (debut presume {deb:#010x})  "
                  f"{len(aps)} appelant(s)")
            for a in aps:
                d2 = ds.debut_de_fonction(a) or a
                print(f"    depuis {a:#010x}   dans {d2:#010x}")
                if d2 not in vus:
                    vus.add(d2)
                    suivant.append(d2)
        if not suivant:
            print("  (plus d'appelant : racine, ou atteint par adresse calculee)")
            break
        courant = suivant


def cmd_mots16(args):
    """Ou le binaire porte-t-il cette valeur 16 bits, et qui la charge ?"""
    img = Image()
    v = int(args[0], 0)
    cibles = []
    for o in range(0, len(img.d) - 1, 2):
        if struct.unpack_from("<H", img.d, o)[0] == v:
            cibles.append(img.base + o)
    print(f"{len(cibles)} occurrence(s) de {v:#06x} en demi-mot aligne")
    chg = []
    for a, h in img.adresses_demis():
        mn, ch = decode(h, a)
        if mn == "mov.w@pc" and ch["cible"] in set(cibles):
            chg.append((a, ch["n"], ch["cible"]))
    print(f"{len(chg)} instruction(s) MOV.W @(disp,PC) la chargent")
    for a, n, c in chg:
        print(f"  {a:#010x}  -> r{n}   (litteral {c:#010x})")
    return chg


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    quoi, reste = sys.argv[1], sys.argv[2:]
    if quoi == "charge":
        cmd_charge(reste)
    elif quoi == "remonte":
        cmd_remonte(reste)
    elif quoi == "appels":
        cmd_appels(reste)
    elif quoi == "braf":
        cmd_braf(reste)
    elif quoi == "mots16":
        cmd_mots16(reste)
    else:
        raise SystemExit(__doc__)
