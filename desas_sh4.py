"""Desassembleur SH-4, en bibliotheque standard.

Pourquoi en ecrire un : sur 1ST_READ.BIN, Ghidra ne desassemble que 32,4 % du
binaire, et les zones qui portent les tables de ressources tombent dans les
67 % restants. Un desassemblage lineaire demande a une adresse precise n'a pas
ce probleme -- il ne cherche pas a prouver que c'est du code, il le lit.

L'ISA est reguliere : toute instruction fait 16 bits, et le decodage tient
dans une table de (masque, valeur, patron). Les champs sont toujours aux memes
places : n en bits 8-11, m en bits 4-7, d/i en bits 0-7 ou 0-11.

Le piege du SH-4 : les chargements PC-relatifs. `MOV.L @(disp,PC),Rn` et
`MOVA` alignent le PC sur 4 avant d'ajouter, `MOV.W @(disp,PC),Rn` non. Et le
PC vaut l'adresse de l'instruction PLUS 4, parce que le pipeline a deja avance
de deux instructions. Se tromper la-dessus decale la cible d'un mot et rend
une valeur plausible mais fausse.

Usage :
    py -3 desas_sh4.py <adresse> [nombre]
"""

import struct
import sys

# (masque, valeur, patron). Le patron nomme ses champs : n, m, d, i, D (disp12).
# L'ordre compte : les formes specialisees passent avant les generales.
TABLE = [
    (0xFFFF, 0x0008, "clrt"), (0xFFFF, 0x0018, "sett"),
    (0xFFFF, 0x0028, "clrmac"), (0xFFFF, 0x0038, "ldtlb"),
    (0xFFFF, 0x0048, "clrs"), (0xFFFF, 0x0058, "sets"),
    (0xFFFF, 0x0009, "nop"), (0xFFFF, 0x0019, "div0u"),
    (0xFFFF, 0x000B, "rts"), (0xFFFF, 0x001B, "sleep"),
    (0xFFFF, 0x002B, "rte"),
    (0xFFFF, 0xF3FD, "fschg"), (0xFFFF, 0xFBFD, "frchg"),

    (0xF0FF, 0x0003, "bsrf r{n}"), (0xF0FF, 0x0023, "braf r{n}"),
    (0xF0FF, 0x0029, "movt r{n}"),
    (0xF0FF, 0x0002, "stc sr,r{n}"), (0xF0FF, 0x0012, "stc gbr,r{n}"),
    (0xF0FF, 0x0022, "stc vbr,r{n}"), (0xF0FF, 0x0032, "stc ssr,r{n}"),
    (0xF0FF, 0x0042, "stc spc,r{n}"),
    (0xF0FF, 0x000A, "sts mach,r{n}"), (0xF0FF, 0x001A, "sts macl,r{n}"),
    (0xF0FF, 0x002A, "sts pr,r{n}"), (0xF0FF, 0x005A, "sts fpul,r{n}"),
    (0xF0FF, 0x006A, "sts fpscr,r{n}"),
    (0xF0FF, 0x0083, "pref @r{n}"), (0xF0FF, 0x0093, "ocbi @r{n}"),
    (0xF0FF, 0x00A3, "ocbp @r{n}"), (0xF0FF, 0x00B3, "ocbwb @r{n}"),
    (0xF0FF, 0x00C3, "movca.l r0,@r{n}"),

    (0xF00F, 0x0004, "mov.b r{m},@(r0,r{n})"),
    (0xF00F, 0x0005, "mov.w r{m},@(r0,r{n})"),
    (0xF00F, 0x0006, "mov.l r{m},@(r0,r{n})"),
    (0xF00F, 0x0007, "mul.l r{m},r{n}"),
    (0xF00F, 0x000C, "mov.b @(r0,r{m}),r{n}"),
    (0xF00F, 0x000D, "mov.w @(r0,r{m}),r{n}"),
    (0xF00F, 0x000E, "mov.l @(r0,r{m}),r{n}"),
    (0xF00F, 0x000F, "mac.l @r{m}+,@r{n}+"),

    (0xF000, 0x1000, "mov.l r{m},@({d4l:#x},r{n})"),

    (0xF00F, 0x2000, "mov.b r{m},@r{n}"), (0xF00F, 0x2001, "mov.w r{m},@r{n}"),
    (0xF00F, 0x2002, "mov.l r{m},@r{n}"),
    (0xF00F, 0x2004, "mov.b r{m},@-r{n}"), (0xF00F, 0x2005, "mov.w r{m},@-r{n}"),
    (0xF00F, 0x2006, "mov.l r{m},@-r{n}"),
    (0xF00F, 0x2007, "div0s r{m},r{n}"), (0xF00F, 0x2008, "tst r{m},r{n}"),
    (0xF00F, 0x2009, "and r{m},r{n}"), (0xF00F, 0x200A, "xor r{m},r{n}"),
    (0xF00F, 0x200B, "or r{m},r{n}"), (0xF00F, 0x200C, "cmp/str r{m},r{n}"),
    (0xF00F, 0x200D, "xtrct r{m},r{n}"), (0xF00F, 0x200E, "mulu.w r{m},r{n}"),
    (0xF00F, 0x200F, "muls.w r{m},r{n}"),

    (0xF00F, 0x3000, "cmp/eq r{m},r{n}"), (0xF00F, 0x3002, "cmp/hs r{m},r{n}"),
    (0xF00F, 0x3003, "cmp/ge r{m},r{n}"), (0xF00F, 0x3004, "div1 r{m},r{n}"),
    (0xF00F, 0x3005, "dmulu.l r{m},r{n}"), (0xF00F, 0x3006, "cmp/hi r{m},r{n}"),
    (0xF00F, 0x3007, "cmp/gt r{m},r{n}"), (0xF00F, 0x3008, "sub r{m},r{n}"),
    (0xF00F, 0x300A, "subc r{m},r{n}"), (0xF00F, 0x300B, "subv r{m},r{n}"),
    (0xF00F, 0x300C, "add r{m},r{n}"), (0xF00F, 0x300D, "dmuls.l r{m},r{n}"),
    (0xF00F, 0x300E, "addc r{m},r{n}"), (0xF00F, 0x300F, "addv r{m},r{n}"),

    (0xF0FF, 0x4000, "shll r{n}"), (0xF0FF, 0x4001, "shlr r{n}"),
    (0xF0FF, 0x4002, "sts.l mach,@-r{n}"), (0xF0FF, 0x4003, "stc.l sr,@-r{n}"),
    (0xF0FF, 0x4004, "rotl r{n}"), (0xF0FF, 0x4005, "rotr r{n}"),
    (0xF0FF, 0x4006, "lds.l @r{n}+,mach"), (0xF0FF, 0x4007, "ldc.l @r{n}+,sr"),
    (0xF0FF, 0x4008, "shll2 r{n}"), (0xF0FF, 0x4009, "shlr2 r{n}"),
    (0xF0FF, 0x400A, "lds r{n},mach"), (0xF0FF, 0x400B, "jsr @r{n}"),
    (0xF0FF, 0x400E, "ldc r{n},sr"),
    (0xF0FF, 0x4010, "dt r{n}"), (0xF0FF, 0x4011, "cmp/pz r{n}"),
    (0xF0FF, 0x4012, "sts.l macl,@-r{n}"), (0xF0FF, 0x4013, "stc.l gbr,@-r{n}"),
    (0xF0FF, 0x4015, "cmp/pl r{n}"),
    (0xF0FF, 0x4016, "lds.l @r{n}+,macl"), (0xF0FF, 0x4017, "ldc.l @r{n}+,gbr"),
    (0xF0FF, 0x4018, "shll8 r{n}"), (0xF0FF, 0x4019, "shlr8 r{n}"),
    (0xF0FF, 0x401A, "lds r{n},macl"), (0xF0FF, 0x401B, "tas.b @r{n}"),
    (0xF0FF, 0x401E, "ldc r{n},gbr"),
    (0xF0FF, 0x4020, "shal r{n}"), (0xF0FF, 0x4021, "shar r{n}"),
    (0xF0FF, 0x4022, "sts.l pr,@-r{n}"), (0xF0FF, 0x4023, "stc.l vbr,@-r{n}"),
    (0xF0FF, 0x4024, "rotcl r{n}"), (0xF0FF, 0x4025, "rotcr r{n}"),
    (0xF0FF, 0x4026, "lds.l @r{n}+,pr"), (0xF0FF, 0x4027, "ldc.l @r{n}+,vbr"),
    (0xF0FF, 0x4028, "shll16 r{n}"), (0xF0FF, 0x4029, "shlr16 r{n}"),
    (0xF0FF, 0x402A, "lds r{n},pr"), (0xF0FF, 0x402B, "jmp @r{n}"),
    (0xF0FF, 0x402E, "ldc r{n},vbr"),
    (0xF0FF, 0x4052, "sts.l fpul,@-r{n}"), (0xF0FF, 0x4056, "lds.l @r{n}+,fpul"),
    (0xF0FF, 0x405A, "lds r{n},fpul"),
    (0xF0FF, 0x4062, "sts.l fpscr,@-r{n}"), (0xF0FF, 0x4066, "lds.l @r{n}+,fpscr"),
    (0xF0FF, 0x406A, "lds r{n},fpscr"),
    (0xF00F, 0x400C, "shad r{m},r{n}"), (0xF00F, 0x400D, "shld r{m},r{n}"),

    (0xF000, 0x5000, "mov.l @({d4l:#x},r{m}),r{n}"),

    (0xF00F, 0x6000, "mov.b @r{m},r{n}"), (0xF00F, 0x6001, "mov.w @r{m},r{n}"),
    (0xF00F, 0x6002, "mov.l @r{m},r{n}"), (0xF00F, 0x6003, "mov r{m},r{n}"),
    (0xF00F, 0x6004, "mov.b @r{m}+,r{n}"), (0xF00F, 0x6005, "mov.w @r{m}+,r{n}"),
    (0xF00F, 0x6006, "mov.l @r{m}+,r{n}"), (0xF00F, 0x6007, "not r{m},r{n}"),
    (0xF00F, 0x6008, "swap.b r{m},r{n}"), (0xF00F, 0x6009, "swap.w r{m},r{n}"),
    (0xF00F, 0x600A, "negc r{m},r{n}"), (0xF00F, 0x600B, "neg r{m},r{n}"),
    (0xF00F, 0x600C, "extu.b r{m},r{n}"), (0xF00F, 0x600D, "extu.w r{m},r{n}"),
    (0xF00F, 0x600E, "exts.b r{m},r{n}"), (0xF00F, 0x600F, "exts.w r{m},r{n}"),

    (0xF000, 0x7000, "add #{i8s},r{n}"),

    (0xFF00, 0x8000, "mov.b r0,@({d4:#x},r{m4})"),
    (0xFF00, 0x8100, "mov.w r0,@({d4w:#x},r{m4})"),
    (0xFF00, 0x8400, "mov.b @({d4:#x},r{m4}),r0"),
    (0xFF00, 0x8500, "mov.w @({d4w:#x},r{m4}),r0"),
    (0xFF00, 0x8800, "cmp/eq #{i8s},r0"),
    (0xFF00, 0x8900, "bt {bd:#010x}"), (0xFF00, 0x8B00, "bf {bd:#010x}"),
    (0xFF00, 0x8D00, "bt/s {bd:#010x}"), (0xFF00, 0x8F00, "bf/s {bd:#010x}"),

    (0xF000, 0x9000, "mov.w @({d8w:#x},pc),r{n}"),
    (0xF000, 0xA000, "bra {bd12:#010x}"), (0xF000, 0xB000, "bsr {bd12:#010x}"),

    (0xFF00, 0xC000, "mov.b r0,@({d8:#x},gbr)"),
    (0xFF00, 0xC100, "mov.w r0,@({d8w:#x},gbr)"),
    (0xFF00, 0xC200, "mov.l r0,@({d8l:#x},gbr)"),
    (0xFF00, 0xC300, "trapa #{i8:#x}"),
    (0xFF00, 0xC400, "mov.b @({d8:#x},gbr),r0"),
    (0xFF00, 0xC500, "mov.w @({d8w:#x},gbr),r0"),
    (0xFF00, 0xC600, "mov.l @({d8l:#x},gbr),r0"),
    (0xFF00, 0xC700, "mova @({d8l:#x},pc),r0"),
    (0xFF00, 0xC800, "tst #{i8:#x},r0"), (0xFF00, 0xC900, "and #{i8:#x},r0"),
    (0xFF00, 0xCA00, "xor #{i8:#x},r0"), (0xFF00, 0xCB00, "or #{i8:#x},r0"),
    (0xFF00, 0xCC00, "tst.b #{i8:#x},@(r0,gbr)"),
    (0xFF00, 0xCD00, "and.b #{i8:#x},@(r0,gbr)"),
    (0xFF00, 0xCE00, "xor.b #{i8:#x},@(r0,gbr)"),
    (0xFF00, 0xCF00, "or.b #{i8:#x},@(r0,gbr)"),

    (0xF000, 0xD000, "mov.l @({d8l:#x},pc),r{n}"),
    (0xF000, 0xE000, "mov #{i8s},r{n}"),

    (0xFFFF, 0xF3FD, "fschg"),
    (0xF1FF, 0xF1FD, "ftrv xmtrx,fv{n}"),
    (0xF0FF, 0xF00D, "fsts fpul,fr{n}"), (0xF0FF, 0xF01D, "flds fr{n},fpul"),
    (0xF0FF, 0xF02D, "float fpul,fr{n}"), (0xF0FF, 0xF03D, "ftrc fr{n},fpul"),
    (0xF0FF, 0xF04D, "fneg fr{n}"), (0xF0FF, 0xF05D, "fabs fr{n}"),
    (0xF0FF, 0xF06D, "fsqrt fr{n}"), (0xF0FF, 0xF07D, "fsrra fr{n}"),
    (0xF0FF, 0xF08D, "fldi0 fr{n}"), (0xF0FF, 0xF09D, "fldi1 fr{n}"),
    (0xF0FF, 0xF0AD, "fcnvsd fpul,dr{n}"), (0xF0FF, 0xF0BD, "fcnvds dr{n},fpul"),
    (0xF0FF, 0xF0ED, "fipr fv{m},fv{n}"),
    (0xF00F, 0xF000, "fadd fr{m},fr{n}"), (0xF00F, 0xF001, "fsub fr{m},fr{n}"),
    (0xF00F, 0xF002, "fmul fr{m},fr{n}"), (0xF00F, 0xF003, "fdiv fr{m},fr{n}"),
    (0xF00F, 0xF004, "fcmp/eq fr{m},fr{n}"), (0xF00F, 0xF005, "fcmp/gt fr{m},fr{n}"),
    (0xF00F, 0xF006, "fmov @(r0,r{m}),fr{n}"),
    (0xF00F, 0xF007, "fmov fr{m},@(r0,r{n})"),
    (0xF00F, 0xF008, "fmov @r{m},fr{n}"), (0xF00F, 0xF009, "fmov @r{m}+,fr{n}"),
    (0xF00F, 0xF00A, "fmov fr{m},@r{n}"), (0xF00F, 0xF00B, "fmov fr{m},@-r{n}"),
    (0xF00F, 0xF00C, "fmov fr{m},fr{n}"),
    (0xF00F, 0xF00E, "fmac fr0,fr{m},fr{n}"),
]

# Les instructions qui portent un delai : l'instruction suivante s'execute
# avant le saut. On l'indique, parce que c'est ce qui trompe la lecture.
DELAI = {"rts", "rte", "braf", "bsrf", "jmp", "jsr", "bra", "bsr",
         "bt/s", "bf/s"}

# Les formes dont la cible est un mot a lire, et comment la calculer.
PCREL = {0xD000: ("l", 0xF000), 0x9000: ("w", 0xF000), 0xC700: ("a", 0xFF00)}


def champs(h, a):
    d8 = h & 0xFF
    return {
        "n": (h >> 8) & 0xF, "m": (h >> 4) & 0xF, "m4": (h >> 4) & 0xF,
        "d4": h & 0xF, "d4w": (h & 0xF) * 2, "d4l": (h & 0xF) * 4,
        "d8": d8, "d8w": d8 * 2, "d8l": d8 * 4,
        "i8": d8, "i8s": d8 - 256 if d8 >= 128 else d8,
        "bd": a + 4 + (d8 - 256 if d8 >= 128 else d8) * 2,
        "bd12": a + 4 + ((h & 0xFFF) - 4096 if (h & 0xFFF) >= 2048
                         else (h & 0xFFF)) * 2,
    }


def cible_pcrel(h, a):
    """Rend (adresse du mot, taille) ou None. Le PC vaut a+4 ; pour MOV.L et
    MOVA il est d'abord aligne sur 4, pour MOV.W non."""
    if (h & 0xF000) == 0xD000:
        return ((a & 0xFFFFFFFC) + 4 + (h & 0xFF) * 4, 4)
    if (h & 0xFF00) == 0xC700:
        return ((a & 0xFFFFFFFC) + 4 + (h & 0xFF) * 4, 4)
    if (h & 0xF000) == 0x9000:
        return (a + 4 + (h & 0xFF) * 2, 2)
    return None


def une(h, a):
    c = champs(h, a)
    for masque, valeur, patron in TABLE:
        if (h & masque) == valeur:
            return patron.format(**c)
    return ".word %#06x" % h


class Desas:
    def __init__(self, data, base=0x8C010000):
        self.d = data
        self.base = base

    def _off(self, a):
        return a - self.base if self.base <= a < self.base + len(self.d) else None

    def mot(self, a):
        o = self._off(a)
        return struct.unpack_from("<I", self.d, o)[0] if o is not None and o + 4 <= len(self.d) else None

    def demi(self, a):
        o = self._off(a)
        return struct.unpack_from("<H", self.d, o)[0] if o is not None and o + 2 <= len(self.d) else None

    def chaine(self, a, n=48):
        o = self._off(a)
        if o is None:
            return None
        s = self.d[o:o + n].split(b"\x00")[0]
        return s.decode("latin1") if len(s) >= 3 and all(32 <= c < 127 for c in s) else None

    def ligne(self, a):
        h = self.demi(a)
        if h is None:
            return None
        txt = une(h, a)
        note = ""
        pc = cible_pcrel(h, a)
        if pc:
            cible, taille = pc
            v = self.mot(cible) if taille == 4 else self.demi(cible)
            if (h & 0xFF00) == 0xC700:
                note = "  ; = %#010x (adresse de table)" % cible
            elif v is not None:
                note = "  ; = %#010x" % v
                s = self.chaine(v)
                if s:
                    note += ' "%s"' % s
        return "%08x  %04x  %-34s%s" % (a, h, txt, note)

    def bloc(self, a, n=60):
        out = []
        for k in range(n):
            l = self.ligne(a + 2 * k)
            if l is None:
                break
            out.append(l)
        return out

    def fin_de_fonction(self, a, maxi=1200):
        """Jusqu'au premier rts/rte suivi de son delai. Premier rts = fin ;
        c'est faux pour une fonction a plusieurs sorties, et il faut le savoir."""
        out = []
        k = 0
        while k < maxi:
            adr = a + 2 * k
            h = self.demi(adr)
            if h is None:
                break
            out.append(self.ligne(adr))
            if h in (0x000B, 0x002B):
                l = self.ligne(adr + 2)
                if l:
                    out.append(l + "   ; (delai)")
                break
            k += 1
        return out

    def debut_de_fonction(self, a, recul=0x400):
        """Remonte au prologue le plus proche : un `mov.l rN,@-r15` ou
        `sts.l pr,@-r15` precede d'un rts, ou un `add #-n,r15`."""
        meilleur = None
        for k in range(1, recul // 2):
            p = a - 2 * k
            h = self.demi(p)
            if h is None:
                break
            av = self.demi(p - 2)
            # rts + delai, donc ce qui suit est un debut
            if av is not None and av in (0x000B, 0x002B):
                meilleur = p + 2
                break
            if h == 0x4F22 or (h & 0xF0FF) == 0x2F06:  # sts.l pr / mov.l rM,@-r15
                meilleur = p
        return meilleur


def charge(chemin="dreamcast/1ST_READ.BIN", base=0x8C010000):
    with open(chemin, "rb") as f:
        return Desas(f.read(), base)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    ds = charge()
    a = int(sys.argv[1], 0)
    n = int(sys.argv[2], 0) if len(sys.argv) > 2 else 60
    if "--fonction" in sys.argv:
        deb = ds.debut_de_fonction(a) or a
        print("; debut presume %#010x (demande %#010x)" % (deb, a))
        for l in ds.fin_de_fonction(deb):
            print(l)
    else:
        for l in ds.bloc(a, n):
            print(l)
